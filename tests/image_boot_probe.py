#!/usr/bin/env python3
"""Test-only probe inside a disposable image clone; never package in releases."""
import asyncio,base64,codecs,hashlib,hmac,json,os,pathlib,re,secrets,ssl,subprocess,sys,time
import aiohttp
sys.path.insert(0,'/opt/jv-test-modules')
import pyte
STATE=pathlib.Path('/var/lib/justverify/web')
CHECKPOINT=pathlib.Path('/var/lib/jv-image-boot-probe/checkpoint.json')
async def probe():
 result={'environment':'QEMU virt with external Debian kernel; NOT Raspberry Pi boot','checks':{}}
 checks=result['checks'];previous=json.loads(CHECKPOINT.read_text()) if CHECKPOINT.exists() else None
 result['boot']='second' if previous else 'first'
 data_test=pathlib.Path('/opt/jv-image-data-probe.py').exists();data_result=None
 try:
  assert subprocess.run(['systemctl','is-enabled','userconfig'],capture_output=True,text=True).stdout.strip()=='masked'
  assert subprocess.check_output(['systemctl','show','userconfig','-p','MainPID','--value']).strip()==b'0'
  checks['os_user_dialog_masked']=True
  for name in ('justverify-firstboot','justverify-manager','justverify-web'):
   assert subprocess.run(['systemctl','is-active','--quiet',name]).returncode==0
  checks['installed_services_active']=True
  assert len(pathlib.Path('/etc/machine-id').read_text().strip())==32
  assert (STATE/'private-key.pem').stat().st_mode&0o077==0
  if not data_test or not previous:
   assert not pathlib.Path('/etc/justverify/node-ready.json').exists()
   for name in ('justverify-core','justverify-electrs'):
    assert subprocess.check_output(['systemctl','show',name,'-p','MainPID','--value']).strip()==b'0'
  checks['identity_permissions_verified' if data_test and previous else 'identity_created_and_unregistered_node_blocked']=True
  context=ssl.create_default_context(cafile=str(STATE/'certificate.pem'))
  der=ssl.PEM_cert_to_DER_cert((STATE/'certificate.pem').read_text())
  identity={'certificate':hashlib.sha256(der).hexdigest(),'machine_id':pathlib.Path('/etc/machine-id').read_text().strip()}
  boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
  password=previous['password'] if previous else secrets.token_urlsafe(32)
  if previous:
   assert previous['identity']==identity and previous['boot_id']!=boot_id
   assert not (STATE/'setup-token').exists();checks['actual_reboot_identity_preserved']=True
  async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=context),cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
   login={'password':password}
   if not previous:
    token=(STATE/'setup-token').read_text().strip();login['setup_token']=token
    async with session.get('https://127.0.0.1/pairing-proof') as response:
     assert response.status==200;proof=await response.json()
    expected=hmac.new(token.encode(),b'JustVerify TLS pairing v1\0'+hashlib.sha256(der).digest(),hashlib.sha256).hexdigest()
    assert hmac.compare_digest(expected,proof['proof']);checks['pairing_proof']=True
   async with session.post('https://127.0.0.1/login',headers={'Origin':'https://justverify.local'},json=login) as response:
    assert response.status==200;owner_session=await response.json()
   assert not (STATE/'setup-token').exists();checks['https_owner_login_after_reboot' if previous else 'https_owner_claim']=True
   # Actual packaged LAN listener and favicon, with an independent HTTP cookie.
   async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as lan:
    for filename in ('favicon.svg','favicon.ico','apple-touch-icon.png'):
     async with lan.get('http://127.0.0.1/'+filename) as response:
      assert response.status==200
      assert await response.read()==(pathlib.Path('/opt/justverify/web/static')/filename).read_bytes()
    async with lan.post('http://127.0.0.1/login',headers={'Origin':'http://127.0.0.1'},json={'password':password}) as response:
     assert response.status==200;lan_auth=await response.json()
    async with lan.get('http://127.0.0.1/session') as response:
     assert response.status==200 and (await response.json())['csrf']==lan_auth['csrf']
    async with lan.post('http://127.0.0.1/device-settings',headers={'Origin':'http://127.0.0.1','X-CSRF-Token':lan_auth['csrf']},json={'action':'state'}) as response:
     assert response.status==200;device=await response.json()
     assert device['device']['os_version']==json.loads(pathlib.Path('/etc/justverify/os-release.json').read_text())['version']
     assert device['preferences']['language']=='ko'
     assert not device['remote_web']['running']
    checks['packaged_lan_login_session_favicon_device_settings']=True
   if previous:client=previous['client']
   else:
    async with session.post('https://127.0.0.1/rpc-clients',headers={'Origin':'https://justverify.local','X-CSRF-Token':owner_session['csrf']},json={'action':'create','label':'Image boot client'}) as response:
     assert response.status==200;client=await response.json()
   if data_test and not previous:
    CHECKPOINT.parent.mkdir(mode=0o700,exist_ok=True)
    with os.fdopen(os.open(CHECKPOINT.parent/'failure-credentials.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as file:
     json.dump({'password':password,'client':client},file);file.flush();os.fsync(file.fileno())
   if data_test:
    sys.path.insert(0,'/opt');import importlib.util
    spec=importlib.util.spec_from_file_location('image_data_probe','/opt/jv-image-data-probe.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data_result=await module.configure(session,owner_session,previous,client)
    checks['registered_image_core_electrs_wallet_psbt']=True
    # Installed nonroot units, private SQL, local explorer, and rebooted index.
    for name in ('justverify-mempool','justverify-mempool-web'):
     assert subprocess.check_output(['systemctl','is-active',name],text=True).strip()=='active'
    deadline=time.monotonic()+90
    while True:
     async with session.get('http://127.0.0.1:3006/justverify/status') as response:
      explorer=await response.json()
     if explorer['state']=='running':break
     assert time.monotonic()<deadline, 'Installed explorer did not become ready: '+explorer['state']
     await asyncio.sleep(.5)
    async with session.get('http://127.0.0.1:3006/api/blocks/tip/hash') as response:
     explorer_tip=await response.text()
    profile=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())
    cookie=pathlib.Path(profile['cookie']).read_bytes().strip()
    async with session.post('http://127.0.0.1:'+str(profile['rpc_port']),headers={'Authorization':'Basic '+base64.b64encode(cookie).decode()},json={'id':1,'method':'getbestblockhash','params':[]}) as response:
     assert (await response.json())['result']==explorer_tip
    for locale in ('en-US','ko','ja'):
     async with session.get('http://127.0.0.1:3006/'+locale+'/') as response:
      assert response.status==200 and '<app-root' in await response.text()
    async with session.get('http://127.0.0.1:3006/source/') as response:
     assert 'justverify.patch' in await response.text()
    sockets=subprocess.check_output(['ss','-lnt'],text=True)
    assert '127.0.0.1:8999' in sockets and ':3306 ' not in sockets
    result['mempool']={'version':'3.3.1','tip':explorer_tip,'core_index_ready':True}
    checks['packaged_mempool_units_sql_locales_tip_reboot' if previous else 'packaged_mempool_units_sql_locales_tip']=True

   auth='Basic '+base64.b64encode((client['id']+':'+client['password']).encode()).decode()
   async with session.post('https://127.0.0.1/rpc',headers={'Authorization':auth},json={'jsonrpc':'2.0','id':1,'method':'getblockchaininfo','params':[]}) as response:
    # Authentication succeeds but the intentionally unregistered Core is unavailable.
    assert response.status==(200 if data_test else 502);await response.read()
   checks['client_credentials_persisted' if previous else 'owner_client_issuance']=True
   if data_test:
    owner_headers={'Origin':'https://justverify.local','X-CSRF-Token':owner_session['csrf']}
    async def remote(request):
     async with session.post('https://127.0.0.1/remote-rpc',headers=owner_headers,json=request) as response:
      assert response.status==200;return await response.json()
    if not previous:
     state=await remote({'action':'state'});assert not state['stored_enabled'] and not state['running']
     plan=await remote({'action':'preview','enabled':True})
     state=await remote({'action':'apply','token':plan['token'],'password':password})
    else:state=await remote({'action':'state'})
    assert state['stored_enabled'] and state['running'] and not state['needs_recovery']
    onion=state['onion_host'];assert re.fullmatch(r'[a-z2-7]{56}\.onion',onion) and state['onion_port']==8332
    spec=importlib.util.spec_from_file_location('onion_http','/opt/jv-onion-http.py');onion_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(onion_module)
    # systemd active/hostname existence precedes Tor network readiness. Keep the
    # circuit deadline separate from bootstrap, within the existing300s probe.
    result['clock']={'unix':int(time.time()),'ntp_synchronized':subprocess.check_output(['timedatectl','show','-p','NTPSynchronized','--value'],text=True).strip()}
    bootstrap_start=time.monotonic();bootstrap_deadline=bootstrap_start+120
    bootstrap=0
    while bootstrap<100:
     journal=subprocess.check_output(['journalctl','-b','-u','justverify-tor','-o','cat','--no-pager'],text=True)
     progress=re.findall(r'Bootstrapped (\d+)%',journal)
     bootstrap=int(progress[-1]) if progress else 0
     result['tor_bootstrap']={'percent':bootstrap,'wait_seconds':round(time.monotonic()-bootstrap_start,2)}
     if bootstrap==100:break
     if time.monotonic()>=bootstrap_deadline:raise TimeoutError('Tor bootstrap did not complete; onion test not started')
     await asyncio.sleep(1)
    checks['actual_tor_bootstrap_complete']=True
    try:
     onion_deadline=time.monotonic()+90
     while True:
      try:
       status,reply=await asyncio.to_thread(onion_module.request,onion,9050,'/rpc',{'jsonrpc':'2.0','id':9,'method':'getblockchaininfo','params':[]},auth)
       break
      except (OSError,TimeoutError):
       if time.monotonic()>=onion_deadline:raise
       await asyncio.sleep(3)
     assert status==200 and reply['result']['chain']=='regtest'
     if not previous:
      assert (await asyncio.to_thread(onion_module.request,onion,9050,'/rpc',{'id':10,'method':'getblockcount'}))[0]==401
      assert (await asyncio.to_thread(onion_module.request,onion,9050,'/login',{}))[0]==404
     checks['remote_rpc_actual_reboot_restore' if previous else 'reviewed_remote_rpc_product_onion']=True
    except (OSError,TimeoutError) as error:
     result['tor_transport_failure']=type(error).__name__
     # Continue independent TUI/QR assertions, but never permit overall PASS.
   async with session.ws_connect('https://127.0.0.1/terminal',origin='https://justverify.local') as ws:
    screen=pyte.Screen(120,40);stream=pyte.Stream(screen);decoder=codecs.getincrementaldecoder('utf-8')()
    def visible(message):
     if message.type==aiohttp.WSMsgType.BINARY:stream.feed(decoder.decode(message.data))
     elif message.type==aiohttp.WSMsgType.TEXT:stream.feed(message.data)
     else:raise AssertionError('terminal closed')
     return '\n'.join(screen.display)
    text='';deadline=time.monotonic()+20
    while 'JustVerify' not in text and time.monotonic()<deadline:
     message=await asyncio.wait_for(ws.receive(),5)
     text=visible(message)
    assert 'JustVerify' in text;checks['packaged_tui_over_authenticated_websocket']=True
    if pathlib.Path('/etc/justverify-factory.json').exists():
     await ws.send_json({'input':'\x1b[19~'});text='';deadline=time.monotonic()+20
     while 'Included NVMe data is ready.' not in text and time.monotonic()<deadline:text=visible(await asyncio.wait_for(ws.receive(),5))
     assert 'Included NVMe data is ready.' in text
     checks['packaged_single_nvme_storage_ready_screen']=True
     await ws.send_json({'input':'\x1b'});text='';deadline=time.monotonic()+20
     while 'Esc 현황' not in text and time.monotonic()<deadline:text=visible(await asyncio.wait_for(ws.receive(),5))
     assert 'Esc 현황' in text
    await ws.send_json({'input':'c'});text='';deadline=time.monotonic()+20
    while 'T transactions' not in text and time.monotonic()<deadline:
     message=await asyncio.wait_for(ws.receive(),5)
     text=visible(message)
    assert 'RPC CLIENTS' in text and 'T transactions' in text
    checks['packaged_client_wallet_transaction_menu']=True
    if data_test:
     if not previous:
      await ws.send_json({'input':'a'});text='';deadline=time.monotonic()+20
      while 'Client name>' not in text and time.monotonic()<deadline:text=visible(await asyncio.wait_for(ws.receive(),5))
      await ws.send_json({'input':'Image phone\r'});text='';deadline=time.monotonic()+20
      while 'Password:' not in text and time.monotonic()<deadline:text=visible(await asyncio.wait_for(ws.receive(),5))
      identifier=re.search(r'Username: ([a-f0-9]{32})',text).group(1);secret=re.search(r'Password: ([a-f0-9]{48})',text).group(1)
      await ws.send_json({'input':'q'});text='';deadline=time.monotonic()+20
      while ('FULLY NODED QUICK CONNECT' not in text or '▀' not in text) and time.monotonic()<deadline:text=visible(await asyncio.wait_for(ws.receive(),5))
      while True:
       try:text=visible(await asyncio.wait_for(ws.receive(),.1))
       except asyncio.TimeoutError:break
      sys.path.insert(0,'/opt/justverify/web');from rpc_qr import quick_connect
      qr=quick_connect({'id':identifier,'password':secret,'label':'Image phone'});size=len(qr['matrix']);bits=[]
      for y in range((size+1)//2):
       cells=[screen.buffer[5+y][1+x] for x in range(size)]
       assert all(cell.fg in ('black','000000') and cell.bg in ('white','brightwhite','ffffff') for cell in cells)
       bits.append([cell.data in ('█','▀') for cell in cells]);bits.append([cell.data in ('█','▄') for cell in cells])
      assert bits[:size]==qr['matrix'] and secret not in text and client['password'] not in text
      await ws.send_json({'input':'\x1b'});text='';deadline=time.monotonic()+20
      while 'NEW CLIENT' not in text and time.monotonic()<deadline:text=visible(await asyncio.wait_for(ws.receive(),5))
      assert 'NEW CLIENT' in text
      await ws.send_json({'input':'\x1b'});text='';deadline=time.monotonic()+20
      while ('A add' not in text or 'NEW CLIENT' in text) and time.monotonic()<deadline:text=visible(await asyncio.wait_for(ws.receive(),5))
      assert 'A add' in text and 'NEW CLIENT' not in text
      checks['packaged_sensitive_quick_connect_qr']=True
     await ws.send_json({'input':'o'});text='';deadline=time.monotonic()+20
     remote_summary='Saved: true | Listener: true | Recovery: false'
     while not ('REMOTE RPC' in text and remote_summary in text and onion in text) and time.monotonic()<deadline:
      text=visible(await asyncio.wait_for(ws.receive(),5))
     if remote_summary not in text or onion not in text:
      result['safe_diagnostic']={
       'remote_title_visible':'REMOTE RPC' in text,
       'remote_summary_visible':remote_summary in text,
       'remote_onion_visible':onion in text,
       'client_request_refused_visible':'Client request refused' in text,
      }
     assert remote_summary in text and onion in text
     checks['packaged_remote_rpc_state_screen']=True
     await ws.send_json({'input':'\x1b'});text='';deadline=time.monotonic()+20
     while ('A add' not in text or 'REMOTE RPC' in text) and time.monotonic()<deadline:
      text=visible(await asyncio.wait_for(ws.receive(),5))
     assert 'A add' in text and 'REMOTE RPC' not in text
     for key,expected in (('\x1b','Esc 현황'),('q','TOR ELECTRUM'),('l','LAN ELECTRUM')):
      await ws.send_json({'input':key});text='';deadline=time.monotonic()+20
      while expected not in text and time.monotonic()<deadline:
       text=visible(await asyncio.wait_for(ws.receive(),5))
      assert expected in text
     assert 'Select SSL/TLS' in text and 'Certificate SHA256:' in text
     checks['packaged_lan_tls_connection_screen']=True
  if result.get('tor_transport_failure'):raise TimeoutError('actual onion transport failed; independent UI checks completed')
  if not previous:
   CHECKPOINT.parent.mkdir(mode=0o700,exist_ok=True)
   with os.fdopen(os.open(CHECKPOINT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as file:
    json.dump({'password':password,'identity':identity,'boot_id':boot_id,'client':client,'data':data_result},file);file.flush();os.fsync(file.fileno())
  result['status']='PASS'
 except Exception as error:
  result['status']='FAIL';result['error_type']=type(error).__name__
  # Keep private diagnostic logs local; report only counts, never onion identities.
  CHECKPOINT.parent.mkdir(mode=0o700,exist_ok=True)
  journal=subprocess.check_output(['journalctl','-b','-u','justverify-tor','-o','cat','--no-pager'])
  with os.fdopen(os.open(CHECKPOINT.parent/'tor-failure.log',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'wb') as file:file.write(journal)
  result['tor_diagnostics']={'warnings':journal.count(b'[warn]'),'errors':journal.count(b'[err]'),'bootstrap_complete':b'Bootstrapped 100%' in journal}
  import traceback
  result['error_frames']=[{'file':pathlib.Path(frame.filename).name,'line':frame.lineno,'function':frame.name} for frame in traceback.extract_tb(error.__traceback__)]
 pathlib.Path('/boot/firmware/jv-virt-probe.json').write_text(json.dumps(result,indent=2)+'\n')
 print('JV_IMAGE_PROBE '+json.dumps(result),flush=True)
 subprocess.run(['sync'],check=True)
 subprocess.run(['systemctl','reboot' if result['status']=='PASS' and not previous else 'poweroff'],check=True)
asyncio.run(probe())
