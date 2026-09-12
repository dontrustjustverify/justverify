#!/usr/bin/env python3
"""Test-only installed-image setup against one explicitly named NEW virtual disk."""
import os,asyncio,base64,hashlib,json,pathlib,socket,ssl,subprocess,sys,time
import aiohttp
SERIAL='JV_IMAGE_DATA_01'
async def version(request):
 process=await asyncio.create_subprocess_exec('runuser','-u','justverify','--','/opt/justverify/venv/bin/python','/opt/jv-image-data-probe.py','--version-request',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
 out,_=await asyncio.wait_for(process.communicate(json.dumps(request).encode()),120)
 assert process.returncode==0
 response=json.loads(out);assert response['ok'];return response['result']
async def policy(request):
 process=await asyncio.create_subprocess_exec('runuser','-u','justverify','--','/opt/justverify/venv/bin/python','/opt/jv-image-data-probe.py','--policy-request',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
 out,_=await asyncio.wait_for(process.communicate(json.dumps(request).encode()),120)
 assert process.returncode==0
 response=json.loads(out);assert response['ok'];return response['result']
async def configure(session,owner,previous,client):
 headers={'Origin':'https://justverify.local','X-CSRF-Token':owner['csrf']}
 async def post(path,request):
  async with session.post('https://127.0.0.1'+path,headers=headers,json=request) as response:
   assert response.status==200;result=await response.json()
   if path=='/storage':assert result['ok'];return result['result']
   return result
 if previous is None:
  inventory=await post('/storage',{'action':'inventory'})
  if pathlib.Path('/etc/justverify-factory.json').exists():
   factory=inventory['factory_volume'];assert factory['source']=='single-os-image'
   assert not any(item['serial']==SERIAL for item in inventory['devices'])
   verified=json.loads(subprocess.check_output(['/usr/bin/python3','/opt/justverify/scripts/factory_volume.py','--verify']))
   assert verified==factory
   layout=json.loads(pathlib.Path('/etc/justverify-factory.json').read_text())
   assert factory['uuid']!=layout['factory_data_uuid']
   size=os.statvfs('/srv/justverify/data');assert size.f_blocks*size.f_frsize>1024**3
   assert (await post('/storage',{'action':'prepare_profile'}))['profile_ready'] is True
   print('JV_DATA_STAGE single boot disk factory data expanded, unique UUID verified; no erase API used',flush=True)
  else:
   candidates=[item for item in inventory['devices'] if item['serial']==SERIAL]
   assert len(candidates)==1
   disk=candidates[0];assert disk['type']=='disk'
   plan=await post('/storage',{'action':'preview','name':disk['name'],'identity_digest':disk['identity_digest']})
   assert plan['device']['serial']==SERIAL and plan['confirmation']=='ERASE '+SERIAL
   result=await post('/storage',{'action':'apply','id':plan['id'],'confirmation':'ERASE '+SERIAL})
   if result.get('profile_ready') is not True:
    print('JV_DATA_DIAG profile preparation failed; committed='+str(result.get('phase')=='committed'),flush=True)
    subprocess.run(['findmnt','-n','-o','SOURCE,UUID','--target','/srv/justverify/data'])
    subprocess.run(['journalctl','--no-pager','-u','justverify-versions','-n','20'])
   assert result['phase']=='committed' and result['profile_ready'] is True
   print('JV_DATA_STAGE new virtual volume committed through installed HTTPS storage API',flush=True)
  preview=await version({'method':'preview','version':'31.1','network':'regtest','watch_only':True})
  assert (await version({'method':'apply','token':preview['token']}))['phase']=='committed'
  print('JV_DATA_STAGE installed version API committed watch-only profile',flush=True)
 active=(await version({'method':'state'}))['active'];assert active['instance']['watch_only'] is True and active['instance']['network']=='regtest'
 profile=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())
 async def core(method,params):
  credential=pathlib.Path(profile['cookie']).read_bytes().strip()
  async with session.post('http://127.0.0.1:'+str(profile['rpc_port'])+'/',headers={'Authorization':'Basic '+base64.b64encode(credential).decode()},json={'jsonrpc':'1.0','id':1,'method':method,'params':params}) as response:
   value=await response.json();assert value.get('error') is None;return value['result']
 if previous is None:
  assert (await policy({'method':'state'}))['requested'].get('txindex')=='1', 'Fresh image must enable the explorer transaction index'
  await core('generatetodescriptor',[1,'raw(51)'])
 end=time.monotonic()+90
 while True:
  try:
   reader,writer=await asyncio.open_connection('127.0.0.1',50001)
   writer.write(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');await writer.drain()
   reply=json.loads(await asyncio.wait_for(reader.readline(),3));writer.close();await writer.wait_closed()
   if reply.get('result',{}).get('height')==1:break
  except (OSError,ValueError,asyncio.TimeoutError):pass
  if time.monotonic()>end:raise AssertionError('image electrs did not index block')
  await asyncio.sleep(.25)
 candidate={'listen':'tor','onlynet':'ipv4,ipv6,onion','proxy':'1','maxmempool':'420','bantime':'120','maxconnections':'16','maxreceivebuffer':'4096','maxsendbuffer':'2048','peertimeout':'45','timeout':'1500','maxuploadtarget':'10','dbcache':'32','rpcworkqueue':'17','txindex':'1','txospenderindex':'1','blockfilterindex':'1','peerblockfilters':'1','peerbloomfilters':'1','rest':'1','asmap':'1'}
 if previous is None:
  reviewed=await policy({'method':'preview','values':candidate})
  assert (await policy({'method':'apply','token':reviewed['token']}))['phase']=='committed'
 state=await policy({'method':'state'})
 assert state['requested']==candidate
 assert next(e for e in state['entries'] if e['key']=='limitclustercount')['default']=='64'
 assert (await core('getnettotals',[]))['uploadtarget']['target']==10*1048576
 assert (await core('getmempoolinfo',[]))['maxmempool']==420000000
 networks={n['name']:n for n in (await core('getnetworkinfo',[]))['networks']}
 assert all(not networks[n]['limited'] for n in ('ipv4','ipv6','onion'))
 assert all(networks[n]['proxy']=='127.0.0.1:9050' for n in ('ipv4','ipv6','onion'))
 lan=subprocess.check_output(['hostname','-I'],text=True).split()[0]
 with socket.socket() as test:
  test.settimeout(1);assert test.connect_ex((lan,18444))!=0
 for port in (18444,18445,18446):
  with socket.create_connection(('127.0.0.1',port),timeout=1):pass
 assert profile['p2p_backend_port']==18446
 with socket.socket() as test:
  test.settimeout(1);assert test.connect_ex((lan,18446))!=0
 peer=next(p for p in await core('getpeerinfo',[]) if p.get('addrbind','').endswith(':18446') and p['version']>0)
 assert set(peer['permissions'])=={'download','noban'}
 deadline=time.monotonic()+30
 while True:
  indexes=await core('getindexinfo',[])
  if all(n in indexes and indexes[n]['synced'] and indexes[n]['best_block_height']==1 for n in ('txindex','txospenderindex','basic block filter index')):break
  assert time.monotonic()<deadline;await asyncio.sleep(.25)
 async with session.get('http://127.0.0.1:'+str(profile['rpc_port'])+'/rest/chaininfo.json') as response:
  assert response.status==200 and (await response.json())['chain']=='regtest'
 async with session.get('https://127.0.0.1/rest/chaininfo.json') as response:
  assert response.status==404
 assert await core('getblockcount',[])==1
 tls=ssl.create_default_context(cafile='/var/lib/justverify/web/certificate.pem')
 deadline=time.monotonic()+30
 while True:
  writer=None
  try:
   reader,writer=await asyncio.open_connection('127.0.0.1',50002,ssl=tls,server_hostname='justverify.local')
   writer.write(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');await writer.drain()
   secure_header=json.loads(await asyncio.wait_for(reader.readline(),5))
   if secure_header.get('result',{}).get('height')==1:break
  except (OSError,ValueError,asyncio.TimeoutError):pass
  finally:
   if writer is not None:
    writer.close()
    try:await writer.wait_closed()
    except OSError:pass
  if time.monotonic()>deadline:raise AssertionError('TLS indexer did not recover after settings restart')
  await asyncio.sleep(.25)
 assert secure_header['result']['height']==1
 tip=await core('getbestblockhash',[])
 raw=bytes.fromhex(secure_header['result']['hex']);assert hashlib.sha256(hashlib.sha256(raw).digest()).digest()[::-1].hex()==tip
 uuid=subprocess.check_output(['findmnt','-n','-o','UUID','--target','/srv/justverify/data'],text=True).strip()
 assert uuid==json.loads(pathlib.Path('/etc/justverify/node-ready.json').read_text())['uuid']
 for service in ('core','electrs','electrum-tls','tor','manager','policy','web'):
  assert subprocess.run(['systemctl','is-active','--quiet','justverify-'+service]).returncode==0
 if previous is None:
  await post('/rpc-clients',{'action':'grant_watch_only','id':client['id']})
  await post('/rpc-clients',{'action':'grant_transactions','id':client['id']})
 auth='Basic '+base64.b64encode((client['id']+':'+client['password']).encode()).decode()
 async def rpc(method,params):
  async with session.post('https://127.0.0.1/rpc',headers={'Authorization':auth},json={'jsonrpc':'2.0','id':1,'method':method,'params':params}) as response:
   assert response.status==200;return (await response.json())['result']
 assert (await rpc('getwalletinfo',[]))['private_keys_enabled'] is False
 assert isinstance(await rpc('createpsbt',[[],[{'data':'00'}]]),str)
 assert await rpc('listlockunspent',[])==[]
 assert await rpc('lockunspent',[True]) is True
 tor_identity={name:hashlib.sha256(pathlib.Path('/run/justverify-tor/'+name+'.hostname').read_bytes()).hexdigest() for name in ('p2p','electrum','rpc')}
 result={'policy':candidate,'indexes':indexes,'tip':tip,'uuid':uuid,'height':1,'lan_tls':True,'tor_identity':tor_identity,'wallet':(await rpc('getwalletinfo',[]))['walletname']}
 if previous is not None:assert result==previous['data']
 print('JV_DATA_STAGE installed Core/electrs/Tor services, TLS assigned wallet and PSBT verified',flush=True)
 return result

if __name__=='__main__':
 assert sys.argv[1:] in (['--version-request'],['--policy-request'])
 request=sys.stdin.buffer.read(4096)
 with socket.socket(socket.AF_UNIX) as connection:
  connection.settimeout(120);connection.connect('/run/justverify-policy/control.sock' if sys.argv[1]=='--policy-request' else '/run/justverify-versions/control.sock');connection.sendall(request+b'\n');out=b''
  while part:=connection.recv(65536):out+=part
 sys.stdout.buffer.write(out)
