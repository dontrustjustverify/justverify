#!/usr/bin/env python3
"""Verify a prepared registered-profile reboot, then restore the persistent VM baseline."""
import base64,hashlib,http.client,json,os,pathlib,shutil,socket,subprocess,sys,time
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
backup=pathlib.Path(sys.argv[1]);checkpoint=json.loads((backup/'reboot.json').read_text());manifest=json.loads((backup/'manifest.json').read_text());data=pathlib.Path('/srv/justverify/data')
units=['justverify-policy','justverify-electrs','justverify-core','justverify-manager','justverify-web']
def system(*args):subprocess.run(['systemctl',*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=checkpoint['boot_id']
 assert subprocess.check_output(['findmnt','-n','-o','UUID','--target',str(data)],text=True).strip()==checkpoint['uuid']
 for path,digest in checkpoint['identities'].items():assert hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()==digest
 if checkpoint.get('interrupted'):
  from interrupted_version_boot import recover_after_boot
  recover_after_boot()
 subprocess.run(['runuser','-u','justverify','--','python3','/opt/justverify/scripts/node_ready.py'],check=True)
 end=time.monotonic()+60
 while True:
  try:
   system('is-active','--quiet',*units,'justverify-versions','justverify-storage','justverify-tor')
   cookie=(data/'instances/regtest/31.1/core/regtest/.cookie').read_bytes().strip()
   connection=http.client.HTTPConnection('127.0.0.1',18443,timeout=2);connection.request('POST','/',json.dumps({'jsonrpc':'2.0','id':1,'method':'getblockchaininfo','params':[]}),{'Authorization':'Basic '+base64.b64encode(cookie).decode()});core=json.loads(connection.getresponse().read());connection.close();assert core['result']['chain']=='regtest' and core['result']['blocks']==1
   with socket.create_connection(('127.0.0.1',50001),timeout=2) as s:
    s.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');electrs=json.loads(s.makefile('rb').readline());assert electrs['result']['height']==1
   header=bytes.fromhex(electrs['result']['hex']);assert len(header)==80
   assert hashlib.sha256(hashlib.sha256(header).digest()).digest()[::-1].hex()==core['result']['bestblockhash']
   snapshot=json.loads(subprocess.check_output(['/opt/justverify/bin/justverify','snapshot','--socket','/run/justverify/manager.sock'],text=True))
   assert snapshot['host']['electrs']['state']=='READY'
   assert snapshot['host']['electrs']['tip']==core['result']['bestblockhash']
   networks={n['name']:n for n in snapshot['rpc']['getnetworkinfo']['value']['networks']}
   expected_proxy='127.0.0.1:9050' if checkpoint.get('outgoing_policy',{}).get('proxy')=='1' else ''
   assert networks['onion']['proxy']=='127.0.0.1:9050' and networks['ipv4']['proxy']==expected_proxy
   if checkpoint.get('outgoing_policy'):
    assert all(networks[n]['limited'] is False for n in ('ipv4','ipv6','onion'))
   profile=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())
   assert profile['p2p_backend_port']==18446
   connection=http.client.HTTPConnection('127.0.0.1',18443,timeout=2)
   connection.request('POST','/',json.dumps({'id':2,'method':'getpeerinfo','params':[]}),{'Authorization':'Basic '+base64.b64encode(cookie).decode()})
   peers=json.loads(connection.getresponse().read())['result'];connection.close()
   peer=next(p for p in peers if p.get('addrbind','').endswith(':18446') and p['version']>0)
   assert set(peer['permissions'])=={'download','noban'}
   lan=subprocess.check_output(['hostname','-I'],text=True).split()[0]
   with socket.socket() as probe:
    probe.settimeout(1);assert probe.connect_ex((lan,18446))!=0
   if checkpoint.get('outgoing_policy',{}).get('listen')=='tor':
    with socket.create_connection(('127.0.0.1',18444),timeout=1):pass
    with socket.create_connection(('127.0.0.1',18445),timeout=1):pass
    lan=subprocess.check_output(['hostname','-I'],text=True).split()[0]
    with socket.socket() as probe:
     probe.settimeout(1);assert probe.connect_ex((lan,18444))!=0
    print('PASS selected Tor-only incoming persists after reboot; loopback/indexer/onion available and clearnet closed',flush=True)
   break
  except (OSError,ValueError,AssertionError,subprocess.CalledProcessError):
   if time.monotonic()>end:raise
   time.sleep(.5)
 print('PASS actual new boot ID; registered UUID/identity preserved; startup gate/Core/electrs height1 and services ready',flush=True)
 checkpoint['phase']='verified'
finally:
 system('stop','justverify-versions',*units)
 if os.path.ismount(data):
  assert subprocess.check_output(['findmnt','-n','-o','UUID','--target',str(data)],text=True).strip()==checkpoint['uuid']
  if (backup/'tui-proof').exists():shutil.move(str(backup/'tui-proof'),str(data/'tui-proof'))
  subprocess.run(['umount',str(data)],check=True)
 pathlib.Path(checkpoint['journal']).unlink(missing_ok=True)
 for record in manifest:
  path=pathlib.Path(record['path'])
  if record['exists']:
   shutil.copyfile(record['backup'],path);os.chmod(path,record['mode']);os.chown(path,record['uid'],record['gid'])
  else:path.unlink(missing_ok=True)
 for name,status in checkpoint['enabled'].items():system('enable' if status=='enabled' else 'disable',name)
 system('daemon-reload');subprocess.run(['mount',str(data)],check=True);system('reset-failed',*units);system('start',*units)
 system('reload-or-restart','justverify-tor')
 assert subprocess.check_output(['findmnt','-n','-o','UUID','--target',str(data)],text=True).strip()==checkpoint['original_uuid']
 checkpoint['restored']=True;(backup/'reboot.json').write_text(json.dumps(checkpoint,indent=2))
 print('PASS baseline UUID/fstab/profile/owner/binaries/unit enablement restored',flush=True)
