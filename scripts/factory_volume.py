#!/usr/bin/env python3
"""Fixed single-OS image data provisioning; never formats a device at runtime."""
import json, os, pathlib, pwd, stat, subprocess, uuid
from backup_bundle import _atomic
LAYOUT=pathlib.Path('/etc/justverify-factory.json')
STATE=pathlib.Path('/var/lib/justverify-factory')
DATA=pathlib.Path('/srv/justverify/data')
MARKER=b'JustVerify single-OS factory data v1\n'
def run(args, **kwargs):
 return subprocess.run(args,check=True,capture_output=True,**kwargs)
def read_root(path,private=False):
 info=path.lstat()
 if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&(0o077 if private else 0o022) or info.st_size>16384:raise ValueError('untrusted factory metadata')
 return json.loads(path.read_bytes())
def save(path,value):
 _atomic(path,(json.dumps(value,sort_keys=True)+'\n').encode(),0o600,0,0)
def fs_uuid(device):
 return run(['/usr/sbin/blkid','-s','UUID','-o','value',str(device)],text=True).stdout.strip()
def devices(disk,layout):
 if layout.get('schema')!=1 or layout.get('kind')!='single-os' or len(layout.get('partitions',[]))!=3:raise ValueError('unsupported factory layout')
 table=json.loads(run(['/usr/sbin/sfdisk','--json',str(disk)],text=True).stdout)['partitiontable']
 total=int(run(['/usr/sbin/blockdev','--getsz',str(disk)],text=True).stdout)
 if table['label']!='gpt' or table['id'].lower()!=layout['disk_uuid'] or table['sectorsize']!=512 or len(table['partitions'])!=3:raise ValueError('unexpected boot disk layout')
 result={};end=2048
 for role,expected,actual in zip(('boot','root','data'),layout['partitions'],table['partitions']):
  if expected['role']!=role or actual['start']!=expected['start'] or actual['uuid'].lower()!=expected['partuuid'] or actual['type'].lower()!=expected['type']:raise ValueError('partition identity mismatch')
  if actual['start']<end or actual['start']+actual['size']>total-33:raise ValueError('partition outside disk or overlapping')
  if actual['size']!=expected['size'] and not (role=='data' and actual['size']>expected['size']):raise ValueError('protected partition size changed')
  end=actual['start']+actual['size'];result[role]=pathlib.Path(actual['node']).resolve()
 return result

def boot_disk(layout):
 root=pathlib.Path(run(['/usr/bin/findmnt','-n','-o','SOURCE','--target','/'],text=True).stdout.strip()).resolve()
 if not stat.S_ISBLK(root.stat().st_mode):raise ValueError('root is not a block partition')
 parent=run(['/usr/bin/lsblk','-n','-o','PKNAME',str(root)],text=True).stdout.strip()
 if not parent or '/' in parent:raise ValueError('root parent is ambiguous')
 disk=pathlib.Path('/dev')/parent
 if devices(disk,layout)['root']!=root:raise ValueError('root differs from factory layout')
 return disk

def mount_data(device,data):
 if data.is_symlink():raise ValueError('linked mount target')
 if os.path.ismount(data):
  if data.stat().st_dev!=device.stat().st_rdev:raise ValueError('wrong mounted data device')
  return
 if data.exists() and any(data.iterdir()):raise ValueError('unmounted data destination contains files')
 data.mkdir(mode=0o755,parents=True,exist_ok=True)
 run(['/usr/bin/mount','-t','ext4','-o','nodev,nosuid,noexec',str(device),str(data)])

def provision(disk,layout,state=STATE,data=DATA):
 found=devices(disk,layout);device=found['data']
 if state.is_symlink():raise ValueError('linked factory state')
 state.mkdir(mode=0o700,parents=True,exist_ok=True)
 meta=state.stat()
 if meta.st_uid!=0 or meta.st_mode&0o077:raise ValueError('untrusted factory state directory')
 journal=state/'provision.json'
 if journal.exists():
  plan=read_root(journal,True)
  if set(plan)!={'schema','phase','disk_uuid','uuid','mount'} or plan['schema']!=1 or plan['disk_uuid']!=layout['disk_uuid'] or plan['mount']!=str(data) or plan['phase'] not in ('prepared','committed') or str(uuid.UUID(plan['uuid']))!=plan['uuid']:raise ValueError('invalid factory journal')
 else:
  if fs_uuid(device)!=layout['factory_data_uuid']:raise ValueError('not an unused factory filesystem')
  mount_data(device,data)
  try:
   if {p.name for p in data.iterdir()}!={'.jv-factory','lost+found'} or (data/'.jv-factory').is_symlink() or (data/'.jv-factory').read_bytes()!=MARKER:raise ValueError('factory filesystem contents changed')
  finally:run(['/usr/bin/umount',str(data)])
  plan={'schema':1,'phase':'prepared','disk_uuid':layout['disk_uuid'],'uuid':str(uuid.uuid4()),'mount':str(data)}
  save(journal,plan)
 current=fs_uuid(device)
 if plan['phase']=='committed':
  if current!=plan['uuid']:raise ValueError('registered factory UUID changed')
  mount_data(device,data)
  if read_root(data/'justverify-volume.json')!={'schema':1,'uuid':plan['uuid'],'layout':'versioned-instances'}:raise ValueError('registered volume marker changed')
  return plan
 if current not in (layout['factory_data_uuid'],plan['uuid']):raise ValueError('interrupted UUID differs')
 if subprocess.run(['/usr/bin/findmnt','-rn','-S',str(device)],capture_output=True).returncode==0:raise ValueError('unfinished data filesystem is mounted; preserve and reboot for recovery')
 check=subprocess.run(['/usr/sbin/e2fsck','-p',str(device)],capture_output=True)
 if check.returncode not in (0,1):raise ValueError('filesystem repair requires review')
 if current!=plan['uuid']:run(['/usr/sbin/tune2fs','-U',plan['uuid'],str(device)])
 run(['/usr/sbin/sfdisk','--no-reread','--no-tell-kernel','--relocate','gpt-bak-std',str(disk)])
 run(['/usr/sbin/sfdisk','--no-reread','--no-tell-kernel','-N','3',str(disk)],input='size=+\n',text=True)
 run(['/usr/bin/partx','--update','--nr','3',str(disk)])
 device=devices(disk,layout)['data']
 # resize2fs requires a full check after identity/partition changes, even when
 # a prior preen run considered the filesystem clean. Never bypass this gate.
 check=subprocess.run(['/usr/sbin/e2fsck','-f','-p',str(device)],capture_output=True)
 if check.returncode not in (0,1):raise ValueError('full filesystem check failed before expansion')
 run(['/usr/sbin/resize2fs',str(device)])
 mount_data(device,data)
 allowed={'lost+found','.jv-factory','instances','justverify-volume.json'}
 if any(p.name not in allowed for p in data.iterdir()):raise ValueError('unexpected factory contents')
 owner=pwd.getpwnam('justverify');instances=data/'instances'
 if instances.is_symlink():raise ValueError('linked instances')
 instances.mkdir(mode=0o700,exist_ok=True);os.chown(instances,owner.pw_uid,owner.pw_gid)
 _atomic(data/'justverify-volume.json',(json.dumps({'schema':1,'uuid':plan['uuid'],'layout':'versioned-instances'})+'\n').encode(),0o644,0,0)
 (data/'.jv-factory').unlink(missing_ok=True)
 directory=os.open(data,os.O_RDONLY);os.fsync(directory);os.close(directory)
 plan['phase']='committed';save(journal,plan)
 return plan

def verify():
 layout=read_root(LAYOUT);found=devices(boot_disk(layout),layout);plan=read_root(STATE/'provision.json',True)
 if plan.get('schema')!=1 or plan.get('phase')!='committed' or plan.get('disk_uuid')!=layout['disk_uuid'] or plan.get('mount')!=str(DATA):raise ValueError('factory registration incomplete')
 if DATA.is_symlink() or not os.path.ismount(DATA) or DATA.stat().st_dev!=found['data'].stat().st_rdev or fs_uuid(found['data'])!=plan['uuid']:raise ValueError('factory data not on this boot disk')
 if read_root(DATA/'justverify-volume.json')!={'schema':1,'uuid':plan['uuid'],'layout':'versioned-instances'}:raise ValueError('factory volume marker differs')
 return {'uuid':plan['uuid'],'mount':str(DATA),'source':'single-os-image'}
if __name__=='__main__':
 import sys
 if os.geteuid()!=0 or sys.argv[1:] not in ([],['--verify']):raise SystemExit('fixed root helper only')
 if sys.argv[1:]:print(json.dumps(verify()))
 else:
  layout=read_root(LAYOUT);provision(boot_disk(layout),layout);print('Factory data ready on the single OS boot disk')
