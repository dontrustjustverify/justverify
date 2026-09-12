#!/usr/bin/env python3
"""Initial volume provisioning. API callers must authenticate the owner before invoking it."""
import fcntl,importlib.util,json,os,pathlib,pwd,re,secrets,stat,subprocess,tempfile,time,uuid
spec=importlib.util.spec_from_file_location('storage_probe',pathlib.Path(__file__).with_name('storage_probe.py'));probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
def atomic(path,data,mode=0o600):
 fd,name=tempfile.mkstemp(prefix='.volume-',dir=path.parent)
 try:
  with os.fdopen(fd,'w') as file:file.write(data);file.flush();os.fchmod(file.fileno(),mode);os.fsync(file.fileno())
  os.replace(name,path);directory=os.open(path.parent,os.O_RDONLY);os.fsync(directory);os.close(directory)
 finally:
  if os.path.exists(name):os.unlink(name)
class Volumes:
 def __init__(self,state=pathlib.Path('/var/lib/justverify-storage'),mount=pathlib.Path('/srv/justverify/data'),fstab=pathlib.Path('/etc/fstab')):
  self.state=pathlib.Path(state);self.mount=pathlib.Path(mount);self.fstab=pathlib.Path(fstab)
  self.state.mkdir(parents=True,exist_ok=True);self.state.chmod(0o700)
 def free_destination(self):
  if self.mount.is_symlink() or os.path.ismount(self.mount):raise ValueError('data target already mounted or linked; migration is not permitted')
  if self.mount.exists() and any(self.mount.iterdir()):raise ValueError('data target contains existing files')
  for line in self.fstab.read_text().splitlines():
   fields=line.split()
   if fields and not line.lstrip().startswith('#') and len(fields)>1 and fields[1]==str(self.mount):raise ValueError('existing fstab target requires explicit migration review')
 def path(self,identifier):
  if not isinstance(identifier,str) or not re.fullmatch(r'[a-f0-9]{48}',identifier):raise ValueError('invalid plan identifier')
  return self.state/(identifier+'.json')
 def save(self,plan):atomic(self.path(plan['id']),json.dumps(plan,indent=2)+'\n')
 def ensure_no_interrupted(self,exclude=None):
  for path in self.state.glob('*.json'):
   if path.stem!=exclude and json.loads(path.read_text()).get('phase') not in ('prepared','committed'):raise ValueError('recover the interrupted volume before starting another format')
 def preview(self,name,identity_digest):
  with self.lock():
   self.ensure_no_interrupted()
   return self._preview(name,identity_digest)
 def _preview(self,name,identity_digest):
  self.free_destination();scan=probe.inspect(name,identity_digest)
  if scan['device']['review_action']!='REVIEW_NEW' or scan['review']!='NO_KNOWN_SIGNATURES_CONTENTS_NOT_PROVEN_EMPTY':raise ValueError('existing signatures require preservation review; initial format refused')
  device=scan['device'];identity=device['serial'] or device['wwn'] or device['partuuid']
  if not identity:raise ValueError('stable device identifier required')
  plan={'id':secrets.token_hex(24),'phase':'prepared','created':time.time(),'device':device,'scan_digest':scan['scan_digest'],'uuid':str(uuid.uuid4()),'confirmation':'ERASE '+identity,'mount':str(self.mount),'fstab_path':str(self.fstab),'fstab_before':self.fstab.read_text(),'warning':'This erases all contents of the selected device, including unrecognized data. No existing node data is moved.'}
  self.save(plan);return plan
 def lock(self):
  file=(self.state/'operation.lock').open('a');fcntl.flock(file,fcntl.LOCK_EX);return file
 def validate_plan_destination(self,plan):
  if plan['mount']!=str(self.mount) or plan.get('fstab_path')!=str(self.fstab):raise ValueError('plan destination mismatch; refusing device mutation')
 def apply(self,identifier,confirmation):
  with self.lock():
   plan=json.loads(self.path(identifier).read_text());self.validate_plan_destination(plan)
   self.ensure_no_interrupted(identifier)
   if plan['phase']!='prepared' or time.time()-plan['created']>900:raise ValueError('plan expired or already attempted; explicit recovery required')
   if not secrets.compare_digest(str(confirmation),plan['confirmation']):raise ValueError('exact device erasure confirmation required')
   self.free_destination()
   if self.fstab.read_text()!=plan['fstab_before']:raise ValueError('fstab changed after preview')
   scan=probe.inspect(plan['device']['name'],plan['device']['identity_digest'])
   if scan['scan_digest']!=plan['scan_digest']:raise ValueError('device signatures changed after preview')
   descriptor=os.open(plan['device']['name'],os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
   try:
    metadata=os.fstat(descriptor)
    if not stat.S_ISBLK(metadata.st_mode) or f'{os.major(metadata.st_rdev)}:{os.minor(metadata.st_rdev)}'!=plan['device']['maj:min']:raise ValueError('device handle mismatch')
    fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
    plan['phase']='formatting';self.save(plan)
    subprocess.run(['/usr/sbin/mkfs.ext4','-q','-F','-U',plan['uuid'],'-L','JustVerify-data',f'/proc/self/fd/{descriptor}'],pass_fds=(descriptor,),check=True,capture_output=True,timeout=180)
    plan['phase']='formatted';self.save(plan)
    return self.attach(plan,descriptor)
   finally:os.close(descriptor)
 def tags(self,descriptor):
  output=subprocess.run(['/usr/sbin/blkid','-p','-o','export',f'/proc/self/fd/{descriptor}'],pass_fds=(descriptor,),check=True,capture_output=True,text=True,timeout=15).stdout
  return dict(line.split('=',1) for line in output.splitlines() if '=' in line)
 def fstab_after(self,plan):
  return plan['fstab_before'].rstrip()+'\n'+f'\n# JustVerify data volume\nUUID={plan["uuid"]} {self.mount} ext4 defaults,nodev,nosuid,noexec,nofail,x-systemd.device-timeout=15s 0 2\n'
 def attach(self,plan,descriptor):
  tags=self.tags(descriptor)
  if tags.get('UUID')!=plan['uuid'] or tags.get('TYPE')!='ext4':raise ValueError('formatted filesystem identity mismatch')
  if plan['mount']!=str(self.mount):raise ValueError('plan destination mismatch')
  if self.fstab.read_text() not in (plan['fstab_before'],self.fstab_after(plan)):raise ValueError('fstab changed; formatted volume preserved for recovery')
  if self.mount.is_symlink():raise ValueError('linked mount target refused')
  if not os.path.ismount(self.mount):
   if self.mount.exists() and any(self.mount.iterdir()):raise ValueError('unmounted destination contains files')
   self.mount.mkdir(parents=True,exist_ok=True)
   # A /proc/self/fd source becomes unusable as soon as mount exits, so
   # findmnt/registration cannot resolve its UUID until a reboot. Use the
   # kernel device-number link, verified against the still-open locked handle.
   device=os.fstat(descriptor).st_rdev
   source=f'/dev/block/{os.major(device)}:{os.minor(device)}'
   source_stat=os.stat(source)
   if not stat.S_ISBLK(source_stat.st_mode) or source_stat.st_rdev!=device:raise ValueError('mount source identity mismatch')
   subprocess.run(['/usr/bin/mount','--no-canonicalize','-t','ext4','-o','nodev,nosuid,noexec',source,str(self.mount)],check=True,capture_output=True,timeout=20)
  if self.mount.stat().st_dev!=os.fstat(descriptor).st_rdev:raise ValueError('mounted device mismatch')
  plan['phase']='mounted';self.save(plan)
  owner=pwd.getpwnam('justverify');instances=self.mount/'instances'
  if instances.is_symlink():raise ValueError('linked instances directory refused')
  instances.mkdir(mode=0o700,exist_ok=True);instances.chmod(0o700);os.chown(instances,owner.pw_uid,owner.pw_gid)
  atomic(self.mount/'justverify-volume.json',json.dumps({'schema':1,'uuid':plan['uuid'],'layout':'versioned-instances'})+'\n')
  atomic(self.fstab,self.fstab_after(plan),mode=0o644)
  plan['phase']='committed';self.save(plan);return plan
 def recover(self,identifier):
  with self.lock():
   plan=json.loads(self.path(identifier).read_text());self.validate_plan_destination(plan)
   if plan['phase']=='committed':return plan
   if plan['phase'] not in ('formatting','formatted','mounted'):raise ValueError('phase needs manual review; no automatic reformat')
   original=plan['device']
   def matches(row):
    keys=[key for key in ('serial','wwn','partuuid') if original[key]]
    return bool(keys) and all(row[key]==original[key] for key in keys) and row['size_bytes']==original['size_bytes'] and row['type']==original['type']
   rows=[row for row in probe.devices.inventory()['devices'] if matches(row)]
   if len(rows)!=1:raise ValueError('original device not uniquely identified')
   row=rows[0]
   if row['read_only'] or row['reason'] in ('SYSTEM_DEVICE','CHILD_IN_USE','AMBIGUOUS_FILESYSTEM_UUID') or any(m!=str(self.mount) for m in row['mountpoints']):raise ValueError('original device is protected or in use elsewhere')
   descriptor=os.open(row['name'],os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
   try:
    metadata=os.fstat(descriptor)
    if not stat.S_ISBLK(metadata.st_mode) or f'{os.major(metadata.st_rdev)}:{os.minor(metadata.st_rdev)}'!=row['maj:min']:raise ValueError('recovery device handle mismatch')
    fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
    tags=self.tags(descriptor)
    if tags.get('UUID')!=plan['uuid'] or tags.get('TYPE')!='ext4':raise ValueError('recovery filesystem identity mismatch; no automatic reformat')
    if not row['mountpoints']:
     check=subprocess.run(['/usr/sbin/e2fsck','-f','-n',f'/proc/self/fd/{descriptor}'],pass_fds=(descriptor,),capture_output=True,timeout=120)
     if check.returncode!=0:raise ValueError('filesystem is incomplete; refusing automatic reformat or repair')
    return self.attach(plan,descriptor)
   finally:os.close(descriptor)
