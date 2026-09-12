#!/usr/bin/env python3
"""Privileged read-only signature inspection bound to a fresh device identity."""
import hashlib,importlib.util,json,os,pathlib,stat,subprocess,sys,tempfile
spec=importlib.util.spec_from_file_location('inventory',pathlib.Path(__file__).with_name('disk_inventory.py'));devices=importlib.util.module_from_spec(spec);spec.loader.exec_module(devices)
def inspect(name,identity_digest):
 rows=devices.inventory()['devices'];entry=next((r for r in rows if r['name']==name),None)
 if entry is None or entry['identity_digest']!=identity_digest:raise ValueError('device identity changed; refresh inventory')
 if entry['reason'] in ('SYSTEM_DEVICE','READ_ONLY','CURRENT_DATA_MOUNT','ALREADY_MOUNTED','CHILD_IN_USE'):raise ValueError('protected or in-use device cannot enter provisioning review')
 descriptor=os.open(name,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
 try:
  metadata=os.fstat(descriptor)
  if not stat.S_ISBLK(metadata.st_mode):raise ValueError('block device required')
  before_device=metadata.st_rdev
  # Passing only fixed, read-only options is intentional. Never add --all/--force.
  signatures=subprocess.run(['/usr/sbin/wipefs','--no-act','--json','--',name],check=True,capture_output=True,text=True,timeout=15)
  if len(signatures.stdout)>1024*1024:raise ValueError('signature result too large')
  values=json.loads(signatures.stdout)
  probe=subprocess.run(['/usr/sbin/blkid','-p','-c','/dev/null','-o','export','--',name],capture_output=True,text=True,timeout=15)
  if probe.returncode not in (0,2,8):raise ValueError('filesystem signature probe failed')
  tags={}
  for line in probe.stdout.splitlines():
   if '=' in line:
    key,value=line.split('=',1)
    if key in ('TYPE','UUID','LABEL','PTTYPE','PTUUID','USAGE','VERSION'):tags[key]=devices.clean(value)
  current=next((r for r in devices.inventory()['devices'] if r['name']==name),None)
  if current is None or current['identity_digest']!=identity_digest or os.stat(name).st_rdev!=before_device:raise ValueError('device changed during inspection')
  result={'device':entry,'signatures':[{k:devices.clean(v) for k,v in row.items()} for row in values.get('signatures',[])],'filesystem':tags,'ambiguous':probe.returncode==8,'mutations_performed':False}
  # Absence of recognized signatures is not proof that a disk has no valuable contents.
  result['review']='EXISTING_SIGNATURES_PRESERVE' if result['signatures'] or tags else 'NO_KNOWN_SIGNATURES_CONTENTS_NOT_PROVEN_EMPTY'
  result['scan_digest']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  return result
 finally:os.close(descriptor)
def review_contents(name,identity_digest):
 scan=inspect(name,identity_digest)
 if scan['ambiguous'] or scan['filesystem'].get('TYPE')!='ext4':raise ValueError('only unambiguous ext4 content review is supported')
 descriptor=os.open(name,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
 folder=pathlib.Path(tempfile.mkdtemp(prefix='justverify-review-',dir='/run'))
 mounted=False
 try:
  if not stat.S_ISBLK(os.fstat(descriptor).st_mode):raise ValueError('block device required')
  current=next((r for r in devices.inventory()['devices'] if r['name']==name),None)
  if current is None or current['identity_digest']!=identity_digest:raise ValueError('device changed before content review')
  subprocess.run(['/usr/bin/mount','--no-canonicalize','-t','ext4','-o','ro,noload,nodev,nosuid,noexec','--',f'/proc/self/fd/{descriptor}',str(folder)],pass_fds=(descriptor,),check=True,capture_output=True,timeout=15)
  mounted=True
  if folder.stat().st_dev!=os.fstat(descriptor).st_rdev:raise ValueError('mounted device identity mismatch')
  entries=list(folder.iterdir())
  regular_entries=[entry for entry in entries if entry.name!='lost+found']
  lost=folder/'lost+found'
  lost_has_contents=lost.exists() and (lost.is_symlink() or not lost.is_dir() or any(lost.iterdir()))
  # Only counts and classification leave the private review mount, never user filenames or contents.
  scan['contents']='EXISTING_CONTENTS_PRESERVED' if regular_entries or lost_has_contents else 'EMPTY_EXCEPT_LOST_FOUND'
  scan['top_level_entry_count']=len(entries)
  scan['inspection_mount_options']='ro,noload,nodev,nosuid,noexec'
  return scan
 finally:
  if mounted:subprocess.run(['/usr/bin/umount','--',str(folder)],check=True,capture_output=True,timeout=15)
  os.close(descriptor);folder.rmdir()
def main():
 if os.geteuid()!=0 or len(sys.argv)!=1:raise ValueError('fixed privileged read-only helper requires no arguments')
 raw=sys.stdin.buffer.read(4097)
 if len(raw)>4096:raise ValueError('request too large')
 request=json.loads(raw)
 if request=={'action':'inventory'}:return devices.inventory()
 if not isinstance(request,dict) or set(request)!={'action','name','identity_digest'} or request['action'] not in ('inspect','review_contents'):raise ValueError('unsupported request')
 return (inspect if request['action']=='inspect' else review_contents)(request['name'],request['identity_digest'])
if __name__=='__main__':
 try:print(json.dumps({'ok':True,'result':main()},ensure_ascii=False))
 except Exception as error:print(json.dumps({'ok':False,'error':str(error) if isinstance(error,ValueError) else type(error).__name__}));sys.exit(1)
