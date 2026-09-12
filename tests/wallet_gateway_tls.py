#!/usr/bin/env python3
"""Real Core + TLS server owner grants and per-client wallet isolation."""
import asyncio,base64,hashlib,json,os,pathlib,secrets,socket,ssl,subprocess,sys,tempfile,time
import aiohttp
from aiohttp import web
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'web'),str(ROOT/'scripts')]
from server import Bridge,app_for
from web_identity import ensure_identity

def port():
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
async def main():
 audit={'core_success':{},'gateway_outcomes':{}}
 work=pathlib.Path(tempfile.mkdtemp(prefix='jv-wallet-tls-'));data=work/'data';data.mkdir(mode=0o700);state=work/'web';ensure_identity(state)
 version=sys.argv[1] if len(sys.argv)>1 else '31.1'
 assert sys.argv[2:] in ([],['--tor'])
 with_tor=sys.argv[2:]==['--tor']
 binary=pathlib.Path.home()/'core-matrix'/version/('bitcoin-'+version)/'bin/bitcoind'
 release=next(r for r in json.loads((ROOT/'catalog/releases.json').read_text())['releases'] if r['version']==version)
 assert hashlib.sha256(binary.read_bytes()).hexdigest()==release['arm64_binary_sha256']
 rpcport=port();tlsport=port();origin=f'https://127.0.0.1:{tlsport}'
 process=subprocess.Popen([str(binary),f'-datadir={data}','-regtest','-server','-listen=0','-connect=0','-dnsseed=0','-keypool=1',f'-rpcport={rpcport}','-printtoconsole=0'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 profile=work/'profile.json';profile.write_text(json.dumps({'version':version,'network':'regtest','watch_only':False,'cookie':str(data/'regtest/.cookie'),'rpc_port':rpcport}))
 registration=work/'node-ready.json';volume='test-volume-'+secrets.token_hex(16)
 def register():registration.write_text(json.dumps({'uuid':volume,'configs':{'profile.json':hashlib.sha256(profile.read_bytes()).hexdigest()}}))
 register()
 bridge=Bridge(state,ROOT/'target/release/justverify',work/'unused.sock',origin);bridge.gateway.profile=profile
 runner=web.AppRunner(app_for(bridge,tor_rpc=with_tor),access_log=None);await runner.setup()
 tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(state/'certificate.pem',state/'private-key.pem');await web.TCPSite(runner,'127.0.0.1',tlsport,ssl_context=tls).start()
 context=ssl.create_default_context(cafile=str(state/'certificate.pem'))
 async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=context,force_close=True),cookie_jar=aiohttp.CookieJar(unsafe=True),timeout=aiohttp.ClientTimeout(total=20)) as session:
  async def core(method,params,wallet=None):
   cookie=(data/'regtest/.cookie').read_bytes().strip()
   async with session.post(f'http://127.0.0.1:{rpcport}/'+('wallet/'+wallet if wallet else ''),headers={'Authorization':'Basic '+base64.b64encode(cookie).decode()},json={'jsonrpc':'1.0','id':1,'method':method,'params':params}) as response:
    value=await response.json();assert value.get('error') is None
    audit['core_success'][method]=audit['core_success'].get(method,0)+1
    return value['result']
  async def request(path,body,headers=None):
   async with session.post(origin+path,json=body,headers={'Origin':origin,**(headers or {})}) as response:
    raw=await response.read()
    return response.status,json.loads(raw) if response.content_type=='application/json' else None
  try:
   for _ in range(200):
    try:await core('getblockchaininfo',[]);break
    except (OSError,aiohttp.ClientError,AssertionError):await asyncio.sleep(.05)
   else:raise AssertionError('Core did not start')
   token=(state/'setup-token').read_text().strip();status,login=await request('/login',{'setup_token':token,'password':secrets.token_urlsafe(32)});assert status==200
   owner={'X-CSRF-Token':login['csrf']}
   clients=[]
   for label in ('phone-a','phone-b'):
    status,client=await request('/rpc-clients',{'action':'create','label':label},owner);assert status==200;clients.append(client)
   a,b=clients
   def authorization(client):return {'Authorization':'Basic '+base64.b64encode((client['id']+':'+client['password']).encode()).decode()}
   async def rpc(client,method,params=None,path='/rpc'):
    status,value=await request(path,{'jsonrpc':'2.0','id':7,'method':method,'params':[] if params is None else params},authorization(client))
    outcome=str(status)+('/rpc-error' if isinstance(value,dict) and value.get('error') else '')
    counts=audit['gateway_outcomes'].setdefault(method,{})
    counts[outcome]=counts.get(outcome,0)+1
    return status,value
   grant={'action':'grant_watch_only','id':a['id']}
   assert (await request('/rpc-clients',grant))[0]==403
   assert (await request('/rpc-clients',grant,owner))[0]==409
   config=json.loads(profile.read_text());config['watch_only']=True;profile.write_text(json.dumps(config));register();original=profile.read_bytes()
   assert (await rpc(a,'getwalletinfo'))[0]==403
   for client in clients:
    status,result=await request('/rpc-clients',{'action':'grant_watch_only','id':client['id']},owner);assert status==200;client['wallet']=result['wallet']
   assert (await request('/rpc-clients',grant,owner))[0]==200
   assert (await rpc(a,'listwallets'))[1]['result']==[a['wallet']]
   assert (await rpc(a,'getwalletinfo',path='/wallet/'+b['wallet']))[0]==403
   assert (await rpc(a,'getwalletinfo',path='/wallet/'+a['wallet']))[1]['result']['private_keys_enabled'] is False
   await core('createwallet',{'wallet_name':'test-source','descriptors':True});address=await core('getnewaddress',[],'test-source');desc=(await core('getaddressinfo',[address],'test-source'))['desc']
   assert (await rpc(a,'importdescriptors',[[{'desc':desc,'timestamp':'now'}]]))[1]['result'][0]['success']
   await core('generatetoaddress',[1,address])
   assert (await rpc(a,'getbalances'))[1]['result']!=(await rpc(b,'getbalances'))[1]['result']
   assert (await rpc(b,'listdescriptors'))[1]['result']['descriptors']==[]
   raw=b'\xef'+secrets.token_bytes(32)+b'\x01';raw+=hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
   number=int.from_bytes(raw,'big');encoded='';alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
   while number:number,remainder=divmod(number,58);encoded=alphabet[remainder]+encoded
   assert (await rpc(b,'importdescriptors',[[{'desc':desc,'timestamp':'now'},{'desc':'wpkh('+encoded+')','timestamp':'now'}]]))[0]==403
   assert (await rpc(b,'listdescriptors'))[1]['result']['descriptors']==[]

   status,c=await request('/rpc-clients',{'action':'create','label':'transaction-client'},owner);assert status==200
   assert (await request('/rpc-clients',{'action':'grant_watch_only','id':c['id']},owner))[0]==200
   assert (await rpc(c,'decodepsbt',['not-a-psbt']))[0]==403
   assert (await request('/rpc',{'id':1,'method':'walletprocesspsbt','params':['invalid']},{**authorization(c),'Origin':'https://untrusted.invalid'}))[0]==403
   assert (await request('/rpc-clients',{'action':'grant_transactions','id':c['id']}))[0]==403
   assert (await request('/rpc-clients',{'action':'grant_transactions','id':c['id']},owner))[0]==200
   assert (await rpc(c,'walletcreatefundedpsbt',[[],[{address:'1'}],0,{'solving_data':{'descriptors':['wpkh('+encoded+')']}}]))[0]==403
   assert (await rpc(c,'walletcreatefundedpsbt',[[],[{address:'1'}],0,{'feeRate':'0.00002','fee_rate':'2'}]))[0]==403
   assert (await rpc(c,'importdescriptors',[[{'desc':desc,'timestamp':'now'}]]))[1]['result'][0]['success']
   status,d=await request('/rpc-clients',{'action':'create','label':'coin-control-client'},owner);assert status==200
   assert (await request('/rpc-clients',{'action':'grant_watch_only','id':d['id']},owner))[0]==200
   assert (await rpc(d,'importdescriptors',[[{'desc':desc,'timestamp':'now'}]]))[1]['result'][0]['success']
   await core('generatetoaddress',[101,address])
   destination=await core('getnewaddress',[],'test-source')
   coins=(await rpc(d,'listunspent'))[1]['result'];assert len(coins)>1
   outpoints=[{key:coin[key] for key in ('txid','vout')} for coin in coins]
   assert (await rpc(d,'listlockunspent'))[1]['result']==[]
   assert (await rpc(d,'lockunspent',[False,outpoints]))[0]==403
   assert (await request('/rpc-clients',{'action':'grant_transactions','id':d['id']},owner))[0]==200
   assert (await rpc(d,'lockunspent',[False,outpoints]))[1]['result'] is True
   assert len((await rpc(d,'listlockunspent'))[1]['result'])==len(outpoints)
   assert (await rpc(d,'listunspent'))[1]['result']==[]
   assert (await rpc(a,'listlockunspent'))[1]['result']==[]
   funding=[[],[{destination:'1.00000000'}],0,{'changeAddress':address,'fee_rate':'2','includeWatching':True}]
   assert (await rpc(d,'walletcreatefundedpsbt',funding))[0]==403
   assert (await rpc(d,'lockunspent',{'unlock':True,'transactions':[outpoints[0]]}))[1]['result'] is True
   assert (await rpc(d,'walletcreatefundedpsbt',funding))[0]==200
   assert (await rpc(d,'lockunspent',[True],path='/wallet/'+a['wallet']))[0]==403
   for invalid in (["false",outpoints],{'unlock':False,'transactions':outpoints,'persistent':True},[False,[{'txid':outpoints[0]['txid'],'vout':True}]]):
    assert (await rpc(d,'lockunspent',invalid))[0]==403
   assert len((await rpc(d,'listlockunspent'))[1]['result'])==len(outpoints)-1
   assert (await rpc(d,'lockunspent',[True]))[1]['result'] is True
   assert (await rpc(d,'listlockunspent'))[1]['result']==[]
   print('PASS '+version+' TLS coin locks require transaction grant, exclude funding inputs, isolate wallets, reject malformed arguments and unlock',flush=True)
   status,funded=await rpc(c,'walletcreatefundedpsbt',[[],[{destination:'1.00000000'}],0,{'changeAddress':address,'fee_rate':'2','includeWatching':True}]);assert status==200
   psbt=funded['result']['psbt']
   assert (await rpc(c,'walletprocesspsbt',[psbt,True]))[0]==403
   status,processed=await rpc(c,'walletprocesspsbt',[psbt]);assert status==200 and processed['result']['complete'] is False
   status,decoded=await rpc(c,'decodepsbt',[processed['result']['psbt']]);assert status==200 and all(not item.get('partial_signatures') for item in decoded['result']['inputs'])
   # Separate test-only signing wallet via direct internal RPC, never through the gateway.
   signed=await core('walletprocesspsbt',[processed['result']['psbt'],True],'test-source')
   status,finalized=await rpc(c,'finalizepsbt',[signed['psbt']]);assert status==200 and finalized['result']['complete'] is True
   raw_transaction=finalized['result']['hex']
   assert (await rpc(c,'testmempoolaccept',[[raw_transaction]]))[1]['result'][0]['allowed'] is True
   status,sent=await rpc(c,'sendrawtransaction',[raw_transaction]);assert status==200;txid=sent['result']
   assert txid in await core('getrawmempool',[])
   await core('generatetoaddress',[1,address])
   status,confirmed=await rpc(c,'gettransaction',[txid]);assert status==200 and confirmed['result']['confirmations']==1
   assert (await request('/rpc-clients',{'action':'revoke','id':c['id']},owner))[0]==200
   assert (await rpc(c,'sendrawtransaction',[raw_transaction]))[0]==401
   print('PASS '+version+' TLS PSBT explicit permission/fund/no-node-signing/separate test signer/finalize/mempool/broadcast/confirmation/revocation',flush=True)

   # Exercise every published node-read method with valid chain-dependent arguments.
   status,node_client=await request('/rpc-clients',{'action':'create','label':'rpc-node-coverage'},owner);assert status==200
   tip=await core('getbestblockhash',[])
   node_cases={'getblockchaininfo':[],'getnetworkinfo':[],'getmempoolinfo':[],'getblockcount':[],
    'getblockhash':[103],'getblockheader':[tip],'getblock':[tip],
    'getrawtransaction':[txid,True,tip],'gettxout':[txid,0],'getrawmempool':[],
    'estimatesmartfee':[6],'uptime':[]}
   from rpc_gateway import READ_METHODS
   assert set(node_cases)==READ_METHODS
   for method,params in node_cases.items():
    status,value=await rpc(node_client,method,params);assert status==200 and not value.get('error'),(method,status)
   status,extra=await request('/rpc-clients',{'action':'create','label':'rpc-wallet-coverage'},owner);assert status==200
   assert (await request('/rpc-clients',{'action':'grant_watch_only','id':extra['id']},owner))[0]==200
   assert (await request('/rpc-clients',{'action':'grant_transactions','id':extra['id']},owner))[0]==200
   assert (await rpc(extra,'importdescriptors',[[{'desc':desc,'timestamp':0}]]))[1]['result'][0]['success']
   wallet_cases={'getwalletinfo':[],'getbalances':[],'getbalance':[],'listunspent':[],
    'listlockunspent':[],'gettransaction':[txid],'listtransactions':[],'listsinceblock':[],
    'getaddressinfo':[address],'listdescriptors':[],'listwalletdir':[],'listwallets':[]}
   for method,params in wallet_cases.items():
    status,value=await rpc(extra,method,params);assert status==200 and not value.get('error'),(method,status)
   status,p1=await rpc(extra,'createpsbt',[[{'txid':txid,'vout':0}],[{destination:'0.10000000'}]]);assert status==200
   status,p2=await rpc(extra,'createpsbt',[[{'txid':txid,'vout':1}],[{address:'0.10000000'}]]);assert status==200
   for method,params in [('analyzepsbt',[p1['result']]),('combinepsbt',[[p1['result'],p1['result']]]),('joinpsbts',[[p1['result'],p2['result']]]),('decoderawtransaction',[raw_transaction])]:
    status,value=await rpc(extra,method,params);assert status==200 and not value.get('error'),(method,status)
   from watch_only import WatchOnly
   expected=READ_METHODS|WatchOnly.READ_METHODS|WatchOnly.TRANSACTION_METHODS|{'listwallets','listwalletdir','importdescriptors'}
   assert all(audit['gateway_outcomes'].get(method,{}).get('200',0)>0 for method in expected)
   print('PASS every published node/wallet/transaction RPC has an actual successful TLS call',flush=True)

   for method,params in [('createwallet',['forbidden']),('importprivkey',['forbidden']),('listdescriptors',[True]),('backupwallet',['/tmp/forbidden'])]:assert (await rpc(a,method,params))[0]==403
   config['network']='main';profile.write_text(json.dumps(config));register();assert (await rpc(a,'getwalletinfo'))[0]==403;profile.write_bytes(original);register()
   prior_volume=volume;volume='other-volume';register();assert (await rpc(a,'getwalletinfo'))[0]==403
   volume=prior_volume;register()
   assert (await rpc(a,'getwalletinfo'))[0]==200
   await core('unloadwallet',[a['wallet']])
   wallet_path=data/'regtest/wallets'/a['wallet'];held=work/'held-wallet';wallet_path.rename(held)
   try:
    assert (await request('/rpc-clients',grant,owner))[0]==409 and not wallet_path.exists()
   finally:held.rename(wallet_path)
   assert (await request('/rpc-clients',grant,owner))[0]==200
   assert (await request('/rpc-clients',{'action':'revoke','id':a['id']},owner))[0]==200
   assert (await rpc(a,'getwalletinfo'))[0]==401
   assert (await rpc(b,'getwalletinfo'))[0]==200
   if with_tor:
    async def tor_request(path,body,client=None,method='POST'):
     async with session.request(method,'http://127.0.0.1:28443'+path,json=body,headers=authorization(client) if client else {}) as response:
      raw=await response.read()
      return response.status,json.loads(raw) if response.content_type=='application/json' else None
    assert (await tor_request('/',{'id':1,'method':'getblockcount'}))[0]==401
    for path in ('/login','/rpc-clients','/storage','/terminal','/pairing-proof','/app.js'):
     assert (await tor_request(path,{},b))[0]==404
    assert (await tor_request('/',None,b,method='GET'))[0]==405
    assert (await tor_request('/wallet/'+b['wallet'],{'id':1,'method':'getwalletinfo'},b))[1]['result']['private_keys_enabled'] is False
    assert (await tor_request('/wallet/'+a['wallet'],{'id':1,'method':'getwalletinfo'},b))[0]==403
    assert (await tor_request('/',{'id':1,'method':'stop'},b))[0]==403
    status,quota=await request('/rpc-clients',{'action':'create','label':'shared-quota'},owner);assert status==200
    for index in range(30):
     if index%2:status,_=await rpc(quota,'getblockcount')
     else:status,_=await tor_request('/',{'id':1,'method':'getblockcount'},quota)
     assert status==200
    assert (await tor_request('/',{'id':1,'method':'getblockcount'},quota))[0]==429
    assert (await rpc(quota,'getblockcount'))[0]==429
    assert (await request('/rpc-clients',{'action':'revoke','id':quota['id']},owner))[0]==200
    assert (await tor_request('/',{'id':1,'method':'getblockcount'},quota))[0]==401
    print('PASS '+version+' Tor loopback RPC-only listener shares HTTPS identity/quotas/revocation; no owner/static/TUI routes; assigned wallet isolation',flush=True)
    if os.environ.get('JV_TOR_TEST'):
     from onion_http import request as onion_request
     fixture=json.loads(pathlib.Path(os.environ['JV_TOR_TEST']).read_text())
     host=(pathlib.Path(fixture['work'])/'rpc/hostname').read_text().strip()
     deadline=time.monotonic()+120
     while True:
      try:
       status,_=await asyncio.to_thread(onion_request,host,fixture['socks_port'],'/',{'id':1,'method':'getblockcount'})
       assert status==401;break
      except OSError:
       if time.monotonic()>deadline:raise
       await asyncio.sleep(3)
     auth=authorization(b)['Authorization']
     status,value=await asyncio.to_thread(onion_request,host,fixture['socks_port'],'/',{'id':1,'method':'getblockcount'},auth)
     assert status==200 and value['result']==await core('getblockcount',[])
     status,value=await asyncio.to_thread(onion_request,host,fixture['socks_port'],'/wallet/'+b['wallet'],{'id':1,'method':'getwalletinfo'},auth)
     assert status==200 and value['result']['private_keys_enabled'] is False
     assert (await asyncio.to_thread(onion_request,host,fixture['socks_port'],'/login',{},auth))[0]==404
     assert (await asyncio.to_thread(onion_request,host,fixture['socks_port'],'/',{'id':1,'method':'getblockcount'},authorization(quota)['Authorization']))[0]==401
     print('PASS '+version+' actual Tor SOCKS/v3 onion -> RPC authentication, Core height, assigned watch-only wallet, owner-route exclusion and revoked-client refusal',flush=True)
   records=(state/'rpc-clients.json').read_text();assert all(c['password'] not in records for c in clients)
   print('PASS real TLS owner CSRF/profile-gated grant, idempotent provisioning, assigned wallet routing, public import, balances isolation, forbidden methods, profile binding, revocation and secret non-persistence',flush=True)
   if os.environ.get('JV_RPC_AUDIT_REPORT'):
    pathlib.Path(os.environ['JV_RPC_AUDIT_REPORT']).write_text(json.dumps({'status':'PASS','core':version,'network':'regtest',**audit},indent=2)+'\n')
  finally:
   if process.poll() is None:await core('stop',[])
   await runner.cleanup();await session.close()
   process.wait(timeout=30)
asyncio.run(main())
