#!/usr/bin/env python3
"""Actual initial selection with production eligibility guard, on dedicated VM data only."""
import hashlib,json,os,pathlib,secrets,shutil,socket,subprocess,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
backup=pathlib.Path(tempfile.mkdtemp(prefix='jv-initial-profile-',dir='/var/tmp'));backup.chmod(0o700)
units=['justverify-policy','justverify-electrs','justverify-core','justverify-manager','justverify-web']
def system(*args):subprocess.run(['systemctl',*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
paths=[pathlib.Path('/etc/fstab')]+[pathlib.Path('/etc/systemd/system')/f'justverify-{n}.service' for n in ('core','electrs','policy')]+[pathlib.Path('/etc/justverify')/n for n in ('bitcoin.conf','electrs.toml','profile.json','torrc','versions.json','node-ready.json')]+[pathlib.Path('/etc/systemd/system')/f'justverify-{n}.service.d/20-profile.conf' for n in ('core','electrs','manager','policy')]+[pathlib.Path('/var/lib/justverify/versions')/n for n in ('active.json','transition.json')]+[pathlib.Path('/usr/libexec/justverify-profile'),pathlib.Path('/opt/justverify/bin/justverify'),pathlib.Path('/var/lib/justverify/web/admin.json')]
manifest=[]
legacy_manager=pathlib.Path('/etc/systemd/system/justverify-manager.service.d/regtest.conf')
paths.append(legacy_manager)
paths.append(pathlib.Path('/usr/libexec/justverify-restart-core'))
paths.append(pathlib.Path('/opt/justverify/templates/torrc'))
resource_catalogs=list((ROOT/'catalog').glob('resources-*.json'))+list((ROOT/'catalog').glob('policy-*.json'))
paths.extend(pathlib.Path('/opt/justverify/catalog')/p.name for p in resource_catalogs)
for index,path in enumerate(paths):
 record={'path':str(path),'backup':str(backup/str(index)),'exists':path.exists()}
 if path.exists():
  st=path.stat();record.update(mode=st.st_mode&0o777,uid=st.st_uid,gid=st.st_gid);shutil.copyfile(path,record['backup'])
 manifest.append(record)
(backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
fixture=pathlib.Path('/var/tmp/jv-ui-format-2afymm60');plan=next(json.loads(p.read_text()) for p in (fixture/'state').glob('*.json') if json.loads(p.read_text())['phase']=='committed')
assert plan['device']['serial']=='JUSTVERIFY_UI_TEST'
data=pathlib.Path('/srv/justverify/data');original_uuid=subprocess.check_output(['findmnt','-n','-o','UUID','--target',str(data)],text=True).strip();assert original_uuid!=plan['uuid']
keep_for_reboot=False
journal=pathlib.Path('/var/lib/justverify-storage')/(secrets.token_hex(24)+'.json');swapped=False
print('Recovery backup: '+str(backup),flush=True)
def api(value,okay=True,socket_path='/run/justverify-versions/control.sock'):
 with socket.socket(socket.AF_UNIX) as connection:
  connection.settimeout(120);connection.connect(socket_path);connection.sendall((json.dumps(value)+'\n').encode());out=b''
  while part:=connection.recv(65536):out+=part
 response=json.loads(out);assert response['ok']==okay,response
 return response.get('result',response)
try:
 system('stop','justverify-versions',*units)
 system('reset-failed','justverify-versions')  # Independent fixture run, after all prior processes stopped.
 for source in resource_catalogs:
  target=pathlib.Path('/opt/justverify/catalog')/source.name;shutil.copyfile(source,target);target.chmod(0o644);os.chown(target,0,0)
 # The development-only legacy drop-in sorts after 20-profile.conf and would
 # override the production cookie path. Preserve it in the manifest and restore
 # it in finally; production image has no such override.
 legacy_manager.unlink(missing_ok=True)
 pathlib.Path('/opt/justverify/templates').mkdir(exist_ok=True)
 shutil.copyfile(ROOT/'image/torrc','/opt/justverify/templates/torrc');os.chmod('/opt/justverify/templates/torrc',0o644)
 shutil.copyfile(ROOT/'image/restart-core.sh','/usr/libexec/justverify-restart-core');os.chmod('/usr/libexec/justverify-restart-core',0o755)
 subprocess.run(['umount',str(data)],check=True);swapped=True
 subprocess.run(['mount','-t','ext4','-o','nodev,nosuid,noexec','UUID='+plan['uuid'],str(data)],check=True)
 assert (data/'tui-proof').exists();shutil.move(str(data/'tui-proof'),str(backup/'tui-proof'))
 if any((data/'instances').iterdir()):
  shutil.move(str(data/'instances'),str(backup/'previous-test-instances'));(data/'instances').mkdir(mode=0o700);shutil.chown(data/'instances',user='justverify',group='justverify')
 assert not any((data/'instances').iterdir())
 plan['mount']=str(data);plan['fstab_path']='/etc/fstab';plan['id']=journal.stem;journal.write_text(json.dumps(plan));journal.chmod(0o600)
 owner=pathlib.Path('/var/lib/justverify/web/admin.json');owner.write_text(json.dumps({'salt':secrets.token_hex(16),'hash':secrets.token_hex(64)}));owner.chmod(0o600);shutil.chown(owner,user='justverify',group='justverify')
 config=json.loads((ROOT/'image/versions.json').read_text());assert not config.get('allow_initial_selection',False)
 pathlib.Path('/etc/justverify/versions.json').write_text(json.dumps(config))
 for name in ('active.json','transition.json'):pathlib.Path('/var/lib/justverify/versions',name).unlink(missing_ok=True)
 shutil.copyfile(ROOT/'scripts/profile_helper.py','/usr/libexec/justverify-profile');os.chmod('/usr/libexec/justverify-profile',0o755)
 shutil.copyfile(ROOT/'target/release/justverify','/opt/justverify/bin/justverify');os.chmod('/opt/justverify/bin/justverify',0o755)
 shutil.copyfile(ROOT/'scripts/wait_core_rpc.py','/opt/justverify/scripts/wait_core_rpc.py')
 shutil.copyfile(ROOT/'scripts/node_ready.py','/opt/justverify/scripts/node_ready.py')
 for name in ('core','electrs','policy'):shutil.copyfile(ROOT/f'image/systemd/justverify-{name}.service',f'/etc/systemd/system/justverify-{name}.service')
 pathlib.Path('/etc/justverify/node-ready.json').unlink(missing_ok=True)
 system('daemon-reload');system('start','justverify-core','justverify-electrs','justverify-policy')
 for name in ('core','electrs','policy'):
  assert subprocess.run(['systemctl','is-active','justverify-'+name],capture_output=True,text=True).stdout.strip()=='inactive'
 print('PASS actual systemd skips Core/electrs/policy before registration',flush=True)
 system('daemon-reload')
 import sys
 sys.path.insert(0,str(ROOT/'scripts'))
 from storage_service import StorageAPI,prepare_profile
 from volume_setup import Volumes
 storage=StorageAPI(Volumes(),profile_starter=prepare_profile)
 assert storage.dispatch({'action':'recover','id':journal.stem})['profile_ready'] is True
 assert storage.dispatch({'action':'prepare_profile'})['profile_ready'] is True
 assert subprocess.run(['systemctl','is-active','justverify-core'],capture_output=True,text=True).stdout.strip()=='inactive'
 print('PASS committed-volume completion/retry starts version API without starting Core or reformatting',flush=True)
 end=time.monotonic()+20
 while True:
  try:state=api({'method':'state'});break
  except OSError:
   if time.monotonic()>end:raise
   time.sleep(.2)
 assert state['active'] is None
 system('stop','justverify-versions')
 from pty_initial_profile import review_initial_profile
 review_initial_profile()
 assert api({'method':'state'})['active'] is None
 assert subprocess.run(['systemctl','is-active','justverify-core'],capture_output=True,text=True).stdout.strip()=='inactive'
 preview=api({'method':'preview','version':'31.1','network':'regtest'})
 # Apply must revalidate eligibility after preview, without creating instance data.
 obstruction=data/'instances'/'preserve-me';obstruction.mkdir()
 api({'method':'apply','token':preview['token']},False);assert obstruction.is_dir();obstruction.rmdir()
 assert api({'method':'state'})['active'] is None
 print('PASS production first preview; changed-volume apply refused with data preserved',flush=True)
 preview=api({'method':'preview','version':'31.1','network':'regtest'})
 result=api({'method':'apply','token':preview['token']});assert result['phase']=='committed',result
 active=api({'method':'state'})['active'];assert active['instance']['core_version']=='31.1' and active['instance']['network']=='regtest'
 system('is-active','--quiet',*units[:-1])
 folder=data/'instances/regtest/31.1';cookie=folder/'core/regtest/.cookie'
 import base64,http.client
 connection=http.client.HTTPConnection('127.0.0.1',18443,timeout=10);connection.request('POST','/',json.dumps({'jsonrpc':'2.0','id':1,'method':'getblockchaininfo','params':[]}),{'Authorization':'Basic '+base64.b64encode(cookie.read_bytes().strip()).decode()});response=json.loads(connection.getresponse().read());connection.close();assert response['result']['chain']=='regtest'
 # Regtest genesis alone remains IBD. Mine a real block before demanding indexed readiness.
 connection=http.client.HTTPConnection('127.0.0.1',18443,timeout=10);connection.request('POST','/',json.dumps({'jsonrpc':'2.0','id':2,'method':'generatetodescriptor','params':[1,'raw(51)']}),{'Authorization':'Basic '+base64.b64encode(cookie.read_bytes().strip()).decode()});mined=json.loads(connection.getresponse().read());connection.close();assert mined.get('error') is None and len(mined['result'])==1
 deadline=time.monotonic()+60
 while True:
  try:
   with socket.create_connection(('127.0.0.1',50001),timeout=2) as electrum:
    electrum.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');reply=json.loads(electrum.makefile('rb').readline())
   if reply.get('result',{}).get('height')==1:break
  except (OSError,ValueError):pass
  if time.monotonic()>deadline:raise AssertionError('actual electrs indexing did not reach mined height 1')
  time.sleep(.25)
 print('PASS first version apply without bootstrap override; actual Core regtest RPC and electrs indexed height agree',flush=True)
 # Check the packaged collector, not only the test observer's height.
 deadline=time.monotonic()+30
 while True:
  snapshot=json.loads(subprocess.check_output(['/opt/justverify/bin/justverify','snapshot','--socket','/run/justverify/manager.sock'],text=True))
  chain=snapshot.get('rpc',{}).get('getblockchaininfo',{}).get('value',{})
  index=snapshot.get('host',{}).get('electrs',{})
  if index.get('state')=='READY':
   assert index['tip']==chain['bestblockhash'] and index['height']==chain['blocks']
   break
  if time.monotonic()>deadline:
   print(json.dumps({'collector_diagnostic':{'chain':chain,'index':index,'rpc_error':snapshot.get('rpc',{}).get('getblockchaininfo',{}).get('error')}}),flush=True)
   raise AssertionError('product collector never verified Core/electrs tip')
  time.sleep(.25)
 networks={n['name']:n for n in snapshot['rpc']['getnetworkinfo']['value']['networks']}
 assert networks['onion']['proxy']=='127.0.0.1:9050'
 assert networks['ipv4']['proxy']=='' and networks['ipv6']['proxy']==''
 print('PASS product READY checks header hash; Tor outbound proxy and direct clearnet effective RPC',flush=True)
 if os.environ.get('JV_WEB_SETTINGS_AUDIT')=='1':
  subprocess.run(['/opt/justverify/venv/bin/python',str(ROOT/'tests/web_settings_live.py')],check=True)
 subprocess.run(['/opt/justverify/venv/bin/python',str(ROOT/'tests/linux_outgoing_policy.py')],check=True)
 subprocess.run(['/opt/justverify/venv/bin/python',str(ROOT/'tests/linux_incoming_policy.py')],check=True)
 subprocess.run(['/opt/justverify/venv/bin/python',str(ROOT/'tests/linux_resource_policy.py')],check=True)
 subprocess.run(['/opt/justverify/venv/bin/python',str(ROOT/'tests/linux_auxiliary_policy.py')],check=True)
 if os.environ.get('JV_BACKUP_AUDIT')=='1':
  subprocess.run(['/opt/justverify-tests/bin/python',str(ROOT/'tests/linux_backup_production.py')],check=True)
  if os.environ.get('JV_BACKUP_ONLY')=='1':
   print('PASS focused registered backup audit; other regressions not rerun in this invocation',flush=True)
   raise SystemExit(0)
 subprocess.run(['/opt/justverify/venv/bin/python',str(ROOT/'tests/linux_tor_outbound.py')],env={**os.environ,'JV_EXPECT_TAGGED_ONION':'1'},check=True)
 tui_fixture=pathlib.Path(tempfile.mkdtemp(prefix='jv-outgoing-tui-',dir='/var/tmp'));tui_fixture.chmod(0o755)
 tui_script=tui_fixture/'test.py';shutil.copyfile(ROOT/'tests/linux_policy_tui.py',tui_script);tui_script.chmod(0o644)
 try:
  for key in ('onlynet','proxy','listen','maxuploadtarget'):
   subprocess.run(['runuser','-u','justverify','--','env','JV_POLICY_TEST_KEY='+key,'/opt/justverify-tests/bin/python',str(tui_script)],check=True)
 finally:
  tui_script.unlink();tui_fixture.rmdir()
 subprocess.run(['/opt/justverify/venv/bin/python',str(ROOT/'tests/linux_electrum_tls.py')],check=True)
 subprocess.run(['/opt/justverify-tests/bin/python',str(ROOT/'tests/linux_electrum_qr.py'),'--lan'],check=True)
 # Exercise the production bridge and registration gate for the separate watch-only profile.
 watch=api({'method':'preview','version':'31.1','network':'regtest','watch_only':True})
 assert watch['preview']['target']['instance']['core_data']!=str(folder/'core')
 assert api({'method':'apply','token':watch['token']})['phase']=='committed'
 watch_folder=data/'instances/regtest/31.1-watch-only'
 def wallet_rpc(method,params):
  c=http.client.HTTPConnection('127.0.0.1',18443,timeout=10)
  c.request('POST','/',json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}),{'Authorization':'Basic '+base64.b64encode((watch_folder/'core/regtest/.cookie').read_bytes().strip()).decode()})
  result=json.loads(c.getresponse().read());c.close();assert result.get('error') is None;return result['result']
 wallet_rpc('createwallet',{'wallet_name':'profile-test','disable_private_keys':True,'blank':True,'descriptors':True,'load_on_startup':True})
 assert wallet_rpc('getwalletinfo',[])['private_keys_enabled'] is False
 assert json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())['watch_only'] is True
 subprocess.run(['/opt/justverify-tests/bin/python',str(ROOT/'tests/linux_client_tui.py')],env={**os.environ,'JV_EXPECT_WATCH_PROFILE':'1','JV_EXPECT_TOR_RPC':'1'},check=True)
 wallet_names=wallet_rpc('listwallets',[]);assert len(wallet_names)==2 and 'profile-test' in wallet_names and sum(name.startswith('jv-watch-') for name in wallet_names)==1
 for mode in (False,True,False):
  plan_mode=api({'method':'preview','version':'31.1','network':'regtest','watch_only':mode})
  assert api({'method':'apply','token':plan_mode['token']})['phase']=='committed'
  system('is-active','--quiet','justverify-electrum-tls')
  if mode:assert sorted(wallet_rpc('listwallets',[]))==sorted(wallet_names)
 assert (folder/'core/regtest/blocks').is_dir() and (watch_folder/'core/regtest/wallets/profile-test').exists()
 print('PASS production watch-only profile switches/resumes separate wallet data and returns to original node profile',flush=True)
 ready=pathlib.Path('/etc/justverify/node-ready.json');original_ready=ready.read_bytes();changed=json.loads(original_ready);changed['uuid']='00000000-0000-0000-0000-000000000000'
 system('stop','justverify-electrs','justverify-core');ready.write_text(json.dumps(changed))
 failed=subprocess.run(['systemctl','start','justverify-core'],capture_output=True);assert failed.returncode!=0
 assert subprocess.check_output(['systemctl','show','justverify-core','-p','MainPID','--value'],text=True).strip()=='0'
 ready.write_bytes(original_ready);system('reset-failed','justverify-core');system('start','justverify-core','justverify-electrs')
 print('PASS actual systemd rejects wrong-volume registration before Core starts; valid marker restores startup',flush=True)
 from pty_version_recovery import recover_missing_target
 recover_missing_target(api,system)
 if os.environ.get('JV_KEEP_REGISTERED_FOR_REBOOT')=='1':
  policy_socket='/run/justverify-policy/control.sock'
  outgoing={**api({'method':'state'},socket_path=policy_socket)['requested'],'onlynet':'ipv4,ipv6,onion','proxy':'1','listen':'tor'}
  review=api({'method':'preview','values':outgoing},socket_path=policy_socket)
  assert api({'method':'apply','token':review['token']},socket_path=policy_socket)['phase']=='committed'
  fstab=pathlib.Path('/etc/fstab');lines=fstab.read_text().splitlines();matches=[i for i,line in enumerate(lines) if not line.lstrip().startswith('#') and len(line.split())>1 and line.split()[1]==str(data)];assert len(matches)==1
  lines[matches[0]]=f'UUID={plan["uuid"]} {data} ext4 defaults,nodev,nosuid,noexec,nofail,x-systemd.device-timeout=15s 0 2';fstab.write_text('\n'.join(lines)+'\n')
  enabled={name:subprocess.run(['systemctl','is-enabled',name],capture_output=True,text=True).stdout.strip() for name in ('justverify-versions','justverify-storage')}
  identity_paths=['/etc/machine-id','/var/lib/justverify/web/certificate.pem','/var/lib/justverify-tor/p2p/hostname','/var/lib/justverify-tor/electrum/hostname','/var/lib/justverify-tor/rpc/hostname']
  identities={path:hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() for path in identity_paths}
  checkpoint={'phase':'prepared','uuid':plan['uuid'],'original_uuid':original_uuid,'journal':str(journal),'identities':identities,'enabled':enabled,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
  checkpoint['outgoing_policy']=outgoing
  if os.environ.get('JV_INTERRUPT_VERSION_BEFORE_REBOOT')=='1':
   from interrupted_version_boot import interrupt
   interrupt(api,system);checkpoint['interrupted']=True
  (backup/'reboot.json').write_text(json.dumps(checkpoint,indent=2));system('daemon-reload');system('enable','justverify-versions','justverify-storage');subprocess.run(['sync'],check=True)
  keep_for_reboot=True;print('READY FOR REBOOT: '+str(backup),flush=True)
finally:
 if not keep_for_reboot:
  system('stop','justverify-versions',*units)
  if swapped:
   if os.path.ismount(data):
    if (backup/'tui-proof').exists():shutil.move(str(backup/'tui-proof'),str(data/'tui-proof'))
    subprocess.run(['umount',str(data)],check=True)
   fstab_record=next(r for r in manifest if r['path']=='/etc/fstab');shutil.copyfile(fstab_record['backup'],'/etc/fstab')
   system('daemon-reload');subprocess.run(['mount',str(data)],check=True)
  journal.unlink(missing_ok=True)
  for record in manifest:
   path=pathlib.Path(record['path'])
   if record['exists']:
    shutil.copyfile(record['backup'],path);os.chmod(path,record['mode']);os.chown(path,record['uid'],record['gid'])
   else:path.unlink(missing_ok=True)
  system('daemon-reload');system('reset-failed',*units);system('start',*units)
  system('reload-or-restart','justverify-tor')
  assert subprocess.check_output(['findmnt','-n','-o','UUID','--target',str(data)],text=True).strip()==original_uuid
  print('PASS original node volume/configuration/binaries restored; version API left stopped',flush=True)
