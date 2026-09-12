#!/usr/bin/env python3
"""Real ext4 regression: a provisioned mount resolves its UUID before reboot."""
import json,os,pathlib,subprocess,sys,tempfile,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from volume_setup import Volumes

assert os.geteuid()==0 and subprocess.check_output(['hostname'],text=True).strip()=='justverify-dev'
work=pathlib.Path(tempfile.mkdtemp(prefix='jv-mount-identity-',dir='/var/tmp'))
work.chmod(0o755)
image=work/'new-test-volume.img'
with image.open('xb') as file:file.truncate(128*1024**2)
image.chmod(0o600)
loop=subprocess.check_output(['losetup','--find','--show',str(image)],text=True).strip()
mount=work/'mount';fstab=work/'fstab';fstab.write_text('# isolated test only\n')
volume=Volumes(work/'state',mount,fstab)
identifier=str(uuid.uuid4())
plan={'id':os.urandom(24).hex(),'phase':'formatted','uuid':identifier,'mount':str(mount),'fstab_path':str(fstab),'fstab_before':fstab.read_text()}
try:
 subprocess.run(['mkfs.ext4','-q','-U',identifier,loop],check=True)
 descriptor=os.open(loop,os.O_RDONLY|os.O_NOFOLLOW)
 try:assert volume.attach(plan,descriptor)['phase']=='committed'
 finally:os.close(descriptor)
 # The original /proc/self/fd mount source fails this after its handle closes.
 for prefix in ([],['runuser','-u','justverify','--']):
  observed=subprocess.check_output(prefix+['findmnt','-n','-o','UUID','--target',str(mount)],text=True).strip()
  assert observed==identifier,(prefix,observed)
 assert json.loads((mount/'justverify-volume.json').read_text())['uuid']==identifier
 assert fstab.read_text().count('UUID='+identifier)==1
 print('PASS real newly formatted ext4 mount UUID visible to root and justverify after descriptor closes, before reboot',flush=True)
 print('Preserved isolated fixture: '+str(work),flush=True)
finally:
 if os.path.ismount(mount):subprocess.run(['umount',str(mount)],check=True)
 subprocess.run(['losetup','--detach',loop],check=True)
