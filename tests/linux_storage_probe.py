#!/usr/bin/env python3
"""Actual blank/ext4 signature scans on a newly created project-owned loop image only."""
import hashlib,importlib.util,json,os,pathlib,socket,subprocess
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
root=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('probe',root/'scripts/storage_probe.py');probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
folder=root/'.state'/('storage-probe-'+str(os.getpid()));folder.mkdir(mode=0o700,parents=True)
image=folder/'blank.img'
with image.open('xb') as file:file.truncate(32*1024*1024)
loop=subprocess.check_output(['/usr/sbin/losetup','--find','--show',str(image)],text=True).strip()
def digest():
 with image.open('rb') as file:return hashlib.file_digest(file,'sha256').hexdigest()
def entry():return next(r for r in probe.devices.inventory()['devices'] if r['name']==loop)
try:
 initial=digest();first=entry();scan=probe.inspect(loop,first['identity_digest'])
 assert scan['review']=='NO_KNOWN_SIGNATURES_CONTENTS_NOT_PROVEN_EMPTY' and digest()==initial
 try:probe.inspect(loop,'stale');raise AssertionError('stale selection accepted')
 except ValueError:pass
 # Verify the loop backing path immediately before formatting this disposable test fixture.
 association=json.loads(subprocess.check_output(['/usr/sbin/losetup','--json','--output','NAME,BACK-FILE',loop],text=True))['loopdevices'][0]
 assert pathlib.Path(association['back-file']).resolve()==image.resolve()
 subprocess.run(['/usr/sbin/mkfs.ext4','-q','-F',loop],check=True)
 before=digest();current=entry();scan=probe.inspect(loop,current['identity_digest'])
 assert scan['filesystem']['TYPE']=='ext4' and scan['review']=='EXISTING_SIGNATURES_PRESERVE'
 assert digest()==before and not scan['mutations_performed']
 content=probe.review_contents(loop,current['identity_digest'])
 assert content['contents']=='EMPTY_EXCEPT_LOST_FOUND' and digest()==before
 mount=folder/'fixture-mount';mount.mkdir()
 subprocess.run(['/usr/bin/mount','--',loop,str(mount)],check=True)
 try:(mount/'preserve-me').write_bytes(b'existing user data fixture')
 finally:subprocess.run(['/usr/bin/umount','--',str(mount)],check=True);mount.rmdir()
 before=digest();current=entry();content=probe.review_contents(loop,current['identity_digest'])
 assert content['contents']=='EXISTING_CONTENTS_PRESERVED' and digest()==before
 system=next(r for r in probe.devices.inventory()['devices'] if '/' in r['mountpoints'])
 try:probe.inspect(system['name'],system['identity_digest']);raise AssertionError('system device accepted')
 except ValueError:pass
 print(json.dumps({'status':'PASS','checks':['new project loop image backing identity verified','blank signature scan changes no bytes','stale identity rejected','real ext4 signature detected after test fixture formatting','ext4 scan changes no bytes','system device cannot enter provisioning review','read-only no-journal-replay inspection preserves entire filesystem bytes','existing content distinguished without exporting filenames'],'probe':scan},indent=2))
finally:
 subprocess.run(['/usr/sbin/losetup','--detach',loop],check=True)
 image.unlink();folder.rmdir()
