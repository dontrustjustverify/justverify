#!/usr/bin/env python3
"""Observe and recheck an existing disposable image after a failed network probe.

No production state is reset. A separate baseline records the state observed
after failure; a subsequent real reboot must preserve it. Tor failure remains
BLOCKED and never turns the overall result into PASS.
"""
import asyncio,base64,hashlib,json,os,pathlib,re,ssl,subprocess,sys,time
import aiohttp
sys.path[:0]=['/opt','/opt/jv-test-modules']
import pyte
import importlib.util
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
data_probe=module('image_data_probe','/opt/jv-image-data-probe.py')
onion_http=module('onion_http','/opt/jv-onion-http.py')
STATE=pathlib.Path('/var/lib/jv-image-boot-probe')
BASE=STATE/'recovery-baseline.json'
async def run():
 assert os.geteuid()==0 and pathlib.Path('/opt/jv-image-boot-probe.py').is_file()
 assert subprocess.check_output(['systemctl','show','jv-image-boot-probe','-p','MainPID','--value']).strip()==b'0'
 credentials=json.loads((STATE/'failure-credentials.json').read_text())
 previous=json.loads(BASE.read_text()) if BASE.exists() else None
 profile=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())
 boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 password=credentials['password'];client=credentials['client']
 tls=ssl.create_default_context(cafile='/var/lib/justverify/web/certificate.pem')
 auth='Basic '+base64.b64encode((client['id']+':'+client['password']).encode()).decode()
 checks={};result={'scope':'Existing disposable image after failed Tor boot probe; no factory identity reset','phase':'after_reboot' if previous else 'baseline_after_failure','checks':checks}
 async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=tls),cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
  async def core(method,params=[]):
   cookie=pathlib.Path(profile['cookie']).read_bytes().strip()
   async with session.post('http://127.0.0.1:'+str(profile['rpc_port']),headers={'Authorization':'Basic '+base64.b64encode(cookie).decode()},json={'id':1,'method':method,'params':params}) as response:
    value=await response.json();assert value.get('error') is None;return value['result']
  async def gateway(method):
   async with session.post('https://127.0.0.1/rpc',headers={'Authorization':auth},json={'id':1,'method':method,'params':[]}) as response:
    assert response.status==200;value=await response.json();assert value.get('error') is None;return value['result']
  assert (await core('getblockchaininfo'))['chain']=='regtest'
  assert await core('getblockcount')==1
  async with session.post('https://127.0.0.1/login',headers={'Origin':'https://justverify.local'},json={'password':password}) as response:
   assert response.status==200;owner=await response.json()
  candidate={'listen':'tor','onlynet':'ipv4,ipv6,onion','proxy':'1','maxmempool':'420','bantime':'120','maxconnections':'16','maxreceivebuffer':'4096','maxsendbuffer':'2048','peertimeout':'45','timeout':'1500','maxuploadtarget':'10','dbcache':'32','rpcworkqueue':'17','txindex':'1','txospenderindex':'1','blockfilterindex':'1','peerblockfilters':'1','peerbloomfilters':'1','rest':'1','asmap':'1'}
  identity_paths=['/etc/machine-id','/var/lib/justverify/web/certificate.pem','/var/lib/justverify/web/admin.json','/etc/ssh/ssh_host_ed25519_key.pub']
  identity={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in identity_paths}
  observed={'policy':candidate,'indexes':await core('getindexinfo'),'tip':await core('getbestblockhash'),'uuid':subprocess.check_output(['findmnt','-n','-o','UUID','--target','/srv/justverify/data'],text=True).strip(),'height':1,'lan_tls':True,'tor_identity':{name:hashlib.sha256(pathlib.Path('/run/justverify-tor/'+name+'.hostname').read_bytes()).hexdigest() for name in ('p2p','electrum','rpc')},'wallet':(await gateway('getwalletinfo'))['walletname']}
  if previous:
   assert previous['boot_id']!=boot_id
   assert previous['identity']==identity and previous['data']==observed
   checks['actual_reboot_same_identity_tip_wallet_uuid']=True
  data=await data_probe.configure(session,owner,previous or {'data':observed},client)
  checks['existing_policy_core_indexes_electrs_tls_watch_only_psbt']=True
  if pathlib.Path('/etc/systemd/system/justverify-mempool.service').is_file():
   for name in ('justverify-mempool','justverify-mempool-web'):
    assert subprocess.check_output(['systemctl','is-active',name],text=True).strip()=='active'
   deadline=time.monotonic()+90
   while True:
    async with session.get('http://127.0.0.1:3006/justverify/status') as response:
     assert response.status==200;explorer=await response.json()
    if explorer['state']=='running':break
    assert time.monotonic()<deadline,'Installed explorer did not recover'
    await asyncio.sleep(.5)
   async with session.get('http://127.0.0.1:3006/api/blocks/tip/hash') as response:
    assert response.status==200;explorer_tip=(await response.text()).strip()
   assert explorer_tip==await core('getbestblockhash')
   for locale in ('ko','en-US','ja'):
    async with session.get('http://127.0.0.1:3006/'+locale+'/') as response:
     assert response.status==200 and 'mempool' in (await response.text()).lower()
   listeners=subprocess.check_output(['ss','-lntH'],text=True)
   assert '127.0.0.1:8999' in listeners and ':3306 ' not in listeners
   checks['packaged_mempool_restarted_sql_locales_core_tip']=True
   result['mempool']={'version':explorer['version'],'tip':explorer_tip,'height':await core('getblockcount')}
  async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as lan:
   async with lan.post('http://127.0.0.1/login',headers={'Origin':'http://127.0.0.1'},json={'password':password}) as response:
    assert response.status==200;login=await response.json()
   async with lan.get('http://127.0.0.1/session') as response:
    assert response.status==200 and (await response.json())['csrf']==login['csrf']
   for name in ('favicon.svg','favicon.ico','apple-touch-icon.png'):
    async with lan.get('http://127.0.0.1/'+name) as response:
     assert response.status==200 and await response.read()==(pathlib.Path('/opt/justverify/web/static')/name).read_bytes()
   async with lan.post('http://127.0.0.1/device-settings',headers={'Origin':'http://127.0.0.1','X-CSRF-Token':login['csrf']},json={'action':'state'}) as response:
    assert response.status==200;device=await response.json()
    assert device['preferences']['language']=='ko' and not device['remote_web']['running']
   checks['http_login_refresh_favicon_device_preferences']=True
  async with session.ws_connect('https://127.0.0.1/terminal',origin='https://justverify.local') as ws:
   screen=pyte.Screen(120,40);stream=pyte.Stream(screen);deadline=time.monotonic()+20
   import codecs
   decoder=codecs.getincrementaldecoder('utf-8')()
   while 'JustVerify' not in '\n'.join(screen.display):
    assert time.monotonic()<deadline
    message=await asyncio.wait_for(ws.receive(),5)
    if message.type==aiohttp.WSMsgType.BINARY:stream.feed(decoder.decode(message.data))
    elif message.type==aiohttp.WSMsgType.TEXT:stream.feed(message.data)
    else:raise AssertionError('fixed TUI websocket closed')
   checks['actual_packaged_fixed_tui']=True
  async with session.post('https://127.0.0.1/remote-rpc',headers={'Origin':'https://justverify.local','X-CSRF-Token':owner['csrf']},json={'action':'state'}) as response:
   assert response.status==200;remote=await response.json()
   assert remote['stored_enabled'] and remote['running'] and not remote['needs_recovery']
  try:
   deadline=time.monotonic()+120
   while True:
    journal=subprocess.check_output(['journalctl','-b','-u','justverify-tor','-o','cat','--no-pager'],text=True)
    values=re.findall(r'Bootstrapped (\d+)%',journal);progress=int(values[-1]) if values else 0
    result['tor_bootstrap_percent']=progress
    if progress==100:break
    if time.monotonic()>deadline:raise TimeoutError('bootstrap')
    await asyncio.sleep(1)
   deadline=time.monotonic()+90
   while True:
    try:
     status,reply=await asyncio.to_thread(onion_http.request,remote['onion_host'],9050,'/rpc',{'id':1,'method':'getblockchaininfo','params':[]},auth)
     break
    except (OSError,TimeoutError):
     if time.monotonic()>deadline:raise
     await asyncio.sleep(3)
   assert status==200 and reply['result']['chain']=='regtest'
   assert (await asyncio.to_thread(onion_http.request,remote['onion_host'],9050,'/rpc',{'id':1,'method':'getblockcount'}))[0]==401
   assert (await asyncio.to_thread(onion_http.request,remote['onion_host'],9050,'/login',{}))[0]==404
   checks['same_onion_actual_authenticated_rpc_and_denials']=True
  except (OSError,TimeoutError) as error:
   result['tor_transport']={'status':'BLOCKED','error':type(error).__name__}
  if not previous:
   fd=os.open(BASE,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
   with os.fdopen(fd,'w') as f:json.dump({'boot_id':boot_id,'identity':identity,'data':data},f);f.flush();os.fsync(f.fileno())
 result['status']='PARTIAL' if result.get('tor_transport') else 'PASS'
 print('JV_IMAGE_RECOVERY '+json.dumps(result),flush=True)
asyncio.run(run())
