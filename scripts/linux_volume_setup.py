#!/usr/bin/env python3
"""Destructive test ONLY for the dedicated project VM disk serial JUSTVERIFY_TEST_DATA."""
import hashlib,json,multiprocessing,os,pathlib,pwd,signal,subprocess,tempfile,time
from volume_setup import Volumes,probe

def main():
 rows=[r for r in probe.devices.inventory()['devices'] if r['serial']=='JUSTVERIFY_TEST_DATA']
 assert len(rows)==1
 row=rows[0]
 assert row['size_bytes']==2*1024**3 and row['review_action']=='REVIEW_NEW' and not row['mountpoints']
 root=pathlib.Path(tempfile.mkdtemp(prefix='jv-volume-',dir='/var/tmp'));target=root/'mount';fstab=root/'fstab';fstab.write_text('# isolated fstab fixture\n')
 real_fstab=pathlib.Path('/etc/fstab').read_bytes();original_data=os.stat('/srv/justverify/data').st_dev
 volume=Volumes(root/'state',target,fstab);plan=volume.preview(row['name'],row['identity_digest'])
 try:volume.apply(plan['id'],'ERASE wrong-device')
 except ValueError:pass
 else:raise AssertionError('incorrect confirmation accepted')
 assert probe.inspect(row['name'],row['identity_digest'])['scan_digest']==plan['scan_digest']
 print('PASS wrong confirmation preserves blank device',flush=True)
 class Interrupted(Volumes):
  def attach(self,plan,descriptor):
   (root/'formatted').write_text('ready')
   time.sleep(180)
 process=multiprocessing.get_context('fork').Process(target=lambda:Interrupted(root/'state',target,fstab).apply(plan['id'],plan['confirmation']))
 process.start()
 deadline=time.monotonic()+90
 while not (root/'formatted').exists() and process.is_alive() and time.monotonic()<deadline:time.sleep(.2)
 if not (root/'formatted').exists():
  process.kill();process.join();raise AssertionError('actual format did not reach durable checkpoint')
 process.kill();process.join();assert process.exitcode==-signal.SIGKILL
 assert json.loads(volume.path(plan['id']).read_text())['phase']=='formatted'
 print('PASS actual mkfs ext4 then SIGKILL at durable formatted checkpoint',flush=True)
 try:volume.apply(plan['id'],plan['confirmation'])
 except ValueError:pass
 else:raise AssertionError('repeat format accepted')
 result=volume.recover(plan['id']);assert result['phase']=='committed' and os.path.ismount(target)
 assert (target/'instances').stat().st_uid==pwd.getpwnam('justverify').pw_uid
 assert (target/'instances').stat().st_mode&0o777==0o700
 assert json.loads((target/'justverify-volume.json').read_text())['uuid']==plan['uuid']
 assert f'UUID={plan["uuid"]}' in fstab.read_text()
 print('PASS read-only fsck and UUID-bound recovery mount/ownership/fstab commit',flush=True)
 # Replay a crash after fstab commit, before the final durable phase update.
 saved=json.loads(volume.path(plan['id']).read_text());saved['phase']='mounted';volume.save(saved)
 before=fstab.read_bytes();assert volume.recover(plan['id'])['phase']=='committed';assert before==fstab.read_bytes()
 assert fstab.read_text().count('UUID=')==1
 print('PASS mounted recovery completes without duplicate fstab entry',flush=True)
 assert pathlib.Path('/etc/fstab').read_bytes()==real_fstab and os.stat('/srv/justverify/data').st_dev==original_data
 subprocess.run(['umount',str(target)],check=True)
 saved['phase']='formatted';volume.save(saved)
 assert volume.recover(plan['id'])['phase']=='committed'
 subprocess.run(['umount',str(target)],check=True)
 print('PASS committed filesystem remount recovery; original root/data/fstab preserved',flush=True)
 print('Evidence fixture: '+str(root),flush=True)
if __name__=='__main__':main()
