#!/usr/bin/env python3
"""Explicit disposable Linux fixture, keeps originals through reboot/poweroff."""
import json,os,pathlib,pwd,shutil,socket,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=pathlib.Path('/var/tmp/jv-device-settings-fixture')
def run(*args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
if sys.argv[1]=='prepare':
 assert not BASE.exists(),'existing fixture must be restored first'
 BASE.mkdir(mode=0o700)
 paths=['/etc/justverify/torrc','/opt/justverify/scripts/publish_onions.py','/opt/justverify/scripts/device_service.py','/etc/systemd/system/justverify-device.service','/var/lib/justverify/web/admin.json','/etc/justverify/os-release.json']
 record=[]
 for i,name in enumerate(paths):
  path=pathlib.Path(name);exists=path.exists()
  if exists:shutil.copy2(path,BASE/str(i))
  record.append({'path':name,'exists':exists,'uid':path.stat().st_uid if exists else 0,'gid':path.stat().st_gid if exists else 0})
 (BASE/'originals.json').write_text(json.dumps(record))
 state=pathlib.Path('/var/lib/justverify-device-test');state.mkdir(mode=0o700)
 user=pwd.getpwnam('justverify');os.chown(state,user.pw_uid,user.pw_gid)
 run('/usr/bin/python3',str(ROOT/'scripts/web_identity.py'),str(state))
 import hashlib,secrets
 salt=secrets.token_hex(16);password='Device-Test-2026!'
 owner=json.dumps({'salt':salt,'hash':hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()})
 (state/'admin.json').write_text(owner)
 for item in state.iterdir():os.chown(item,user.pw_uid,user.pw_gid);item.chmod(0o600)
 globalowner=pathlib.Path('/var/lib/justverify/web/admin.json')
 if not globalowner.exists():globalowner.write_text(owner);globalowner.chmod(0o600);os.chown(globalowner,user.pw_uid,user.pw_gid)
 shutil.copytree(ROOT/'web','/opt/justverify/device-test-web',ignore=shutil.ignore_patterns('__pycache__'))
 # ROOT lookup expects /opt/justverify/web, so fixture directory mirrors an install.
 shutil.move('/opt/justverify/device-test-web','/opt/justverify/device-test')
 pathlib.Path('/opt/justverify/device-fixture').mkdir()
 shutil.move('/opt/justverify/device-test','/opt/justverify/device-fixture/web')
 shutil.copy2(ROOT/'scripts/device_service.py','/opt/justverify/scripts/device_service.py')
 shutil.copy2(ROOT/'scripts/publish_onions.py','/opt/justverify/scripts/publish_onions.py')
 shutil.copy2(ROOT/'image/systemd/justverify-device.service','/etc/systemd/system/justverify-device.service')
 tor=pathlib.Path('/etc/justverify/torrc');suffix='HiddenServiceDir /var/lib/justverify-tor/web\nHiddenServiceVersion 3\nHiddenServicePort 80 127.0.0.1:28444\n'
 assert '/justverify-tor/web' not in tor.read_text()
 tor.write_text(tor.read_text().rstrip()+'\n'+suffix)
 pathlib.Path('/etc/systemd/system/jv-device-web-test.service').write_text('''[Unit]
After=network-online.target justverify-device.service
Wants=justverify-device.service
[Service]
User=justverify
ExecStart=/opt/justverify/venv/bin/python /opt/justverify/device-fixture/web/server.py --state /var/lib/justverify-device-test --binary /opt/justverify/bin/justverify --socket /run/justverify/manager.sock --origin https://localhost:28645 --listen 127.0.0.1 --port 28645 --http-lan-port 28646 --lan-onboarding
Restart=on-failure
[Install]
WantedBy=multi-user.target
''')
 run('systemctl','daemon-reload');run('systemctl','enable','--now','justverify-device','jv-device-web-test');run('systemctl','restart','justverify-tor')
 print('fixture prepared; originals retained, no Core data changes')
elif sys.argv[1]=='restore':
 run('systemctl','disable','--now','jv-device-web-test','justverify-device')
 for i,item in enumerate(json.loads((BASE/'originals.json').read_text())):
  path=pathlib.Path(item['path'])
  if item['exists']:shutil.copy2(BASE/str(i),path);os.chown(path,item['uid'],item['gid'])
  else:path.unlink(missing_ok=True)
 pathlib.Path('/etc/systemd/system/jv-device-web-test.service').unlink()
 run('systemctl','daemon-reload');run('systemctl','restart','justverify-tor')
 shutil.rmtree('/opt/justverify/device-fixture');shutil.rmtree('/var/lib/justverify-device-test')
 shutil.rmtree(BASE)
 print('fixture restored; temporary credentials removed')
else:raise SystemExit('prepare or restore required')
