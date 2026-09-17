#!/usr/bin/env python3
"""Prepare ONLY an explicitly named disposable VM clone for native reset tests."""
import hashlib,json,os,pathlib,pwd,shutil,subprocess
assert os.geteuid()==0
assert subprocess.check_output(['hostname'],text=True).strip()=='justverify-reset-test'
source=pathlib.Path('/var/tmp/jv-version-reset-source')
assert (source/'scripts/chain_reset.py').is_file()
state=pathlib.Path('/var/tmp/jv-reset-native')
state.mkdir(mode=0o700,exist_ok=False)
def run(*args):return subprocess.run(args,check=True,capture_output=True,text=True)
old=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())
assert old['network']=='regtest', 'never use an existing mainnet profile for this test'
units=['justverify-web','justverify-storage','justverify-versions','justverify-policy','justverify-electrum-tls','justverify-electrs','justverify-core','justverify-manager','justverify-backup']
run('systemctl','stop',*units)
# Keep the original fixture volume as-is; mount a newly created image instead.
run('umount','/srv/justverify/data')
image=state/'data.img'
with image.open('xb') as f:f.truncate(2*1024**3)
run('mkfs.ext4','-F','-q','-m','0',str(image))
run('mount','-o','loop',str(image),'/srv/justverify/data')
fstab=pathlib.Path('/etc/fstab');lines=[line for line in fstab.read_text().splitlines() if '/srv/justverify/data' not in line]
fstab.write_text('\n'.join(lines)+f'\n{image} /srv/justverify/data ext4 loop 0 0\n')
data=pathlib.Path('/srv/justverify/data');(data/'instances').mkdir(mode=0o700)
user=pwd.getpwnam('justverify');os.chown(data/'instances',user.pw_uid,user.pw_gid)
uuid=run('findmnt','-n','-o','UUID','--target',str(data)).stdout.strip()
(data/'justverify-volume.json').write_text(json.dumps({'schema':1,'uuid':uuid,'layout':'versioned-instances'}))
versions=pathlib.Path('/var/lib/justverify/versions')
if versions.exists():versions.rename(state/'original-version-state')
versions.mkdir(mode=0o700);os.chown(versions,user.pw_uid,user.pw_gid)
for name in ('config','preflight'):
 p=pathlib.Path('/var/lib/justverify')/name;p.mkdir(mode=0o700,exist_ok=True);os.chown(p,user.pw_uid,user.pw_gid)
for name in ('node-ready.json','version-reset-guard.json'):
 p=pathlib.Path('/etc/justverify')/name
 if p.exists():p.rename(state/name)
for version in ('31.1','22.0'):
 origin=pathlib.Path('/home/builder/core-matrix')/version/('bitcoin-'+version)/'bin/bitcoind'
 dest=pathlib.Path('/opt/justverify/versions')/version/('bitcoin-'+version)/'bin/bitcoind';dest.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(origin,dest);dest.chmod(0o755)
shutil.copytree(source/'catalog','/opt/justverify/catalog',dirs_exist_ok=True)
shutil.copyfile('/home/builder/justverify/target/debug/justverify','/opt/justverify/bin/justverify')
for file in (source/'scripts').glob('*.py'):shutil.copyfile(file,pathlib.Path('/opt/justverify/scripts')/file.name)
shutil.copyfile(source/'scripts/profile_helper.py','/usr/libexec/justverify-profile');pathlib.Path('/usr/libexec/justverify-profile').chmod(0o755)
shutil.copyfile(source/'image/restart-core.sh','/usr/libexec/justverify-restart-core');pathlib.Path('/usr/libexec/justverify-restart-core').chmod(0o755)
for name in ('core','electrs','manager','policy','versions','i2p'):
 shutil.copyfile(source/f'image/systemd/justverify-{name}.service',f'/etc/systemd/system/justverify-{name}.service')
# Old fixture drop-ins point to its preserved volume, so keep them in the test archive.
for name in ('core','electrs','manager','policy'):
 folder=pathlib.Path(f'/etc/systemd/system/justverify-{name}.service.d')
 if folder.exists():shutil.move(folder,state/f'{name}-dropins')
config=json.loads((source/'image/versions.json').read_text());config['allow_initial_selection']=True
pathlib.Path('/etc/justverify/versions.json').write_text(json.dumps(config))
# The actual backup daemon runs, sharing operations.lock with version/policy APIs.
shutil.copyfile(source/'image/systemd/justverify-backup.service','/etc/systemd/system/justverify-backup.service')
run('systemctl','daemon-reload');run('systemctl','reset-failed')
run('systemctl','enable','justverify-versions')
run('systemctl','start','justverify-backup','justverify-versions')
print(json.dumps({'status':'READY','network':'regtest','disposable_volume':True}))
