#!/usr/bin/env python3
"""Additional I2P/systemd acceptance in a disposable, booted factory image.

Never run on a physical node. The normal image boot/Tor suite is separate.
"""
import asyncio,base64,hashlib,json,os,pathlib,secrets,socket,subprocess,time
import aiohttp
P=pathlib.Path('/var/lib/jv-i2p-image-probe')
REPORT={'status':'RUNNING','environment':'QEMU virt; external Debian kernel, not Pi firmware','checks':[]}
def note(s):
 REPORT['checks'].append(s);print('JV_I2P_STAGE '+s,flush=True)
def system(*args):return subprocess.check_output(['systemctl',*args],text=True).strip()
def digest(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
async def wait(check,seconds,label):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  try:
   value=await check()
   if value:return value
  except (OSError,ValueError,KeyError,aiohttp.ClientError):pass
  await asyncio.sleep(.5)
 raise AssertionError(label+' deadline exceeded')
async def main():
 assert subprocess.check_output(['systemd-detect-virt','--vm'],text=True).strip()=='qemu'
 P.mkdir(mode=0o700,exist_ok=True);checkpoint=P/'checkpoint.json'
 previous=json.loads(checkpoint.read_text()) if checkpoint.exists() else None
 REPORT['boot']='second' if previous else 'first'
 password=previous['password'] if previous else secrets.token_urlsafe(32)
 origin='http://127.0.0.1'
 async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),timeout=aiohttp.ClientTimeout(total=150)) as c:
  payload={'password':password}
  if not previous:payload['setup_token']=(pathlib.Path('/var/lib/justverify/web/setup-token')).read_text().strip()
  async with c.post(origin+'/login',headers={'Origin':origin},json=payload) as r:
   assert r.status==200,await r.text();auth=await r.json()
  headers={'Origin':origin,'X-CSRF-Token':auth['csrf']}
  async def post(path,body):
   async with c.post(origin+path,headers=headers,json=body) as r:
    value=await r.json();assert r.status==200,(path,r.status,value);return value
  async def version(body):return await post('/versions',body)
  async def policy(body):return await post('/policy',body)
  if not previous:
   storage=await post('/storage',{'action':'prepare_profile'});assert storage['ok'] and storage['result']['profile_ready']
   review=await version({'method':'preview','version':'31.1','network':'regtest','watch_only':False})
   assert (await version({'method':'apply','token':review['token']}))['phase']=='committed'
  config=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text());assert config['network']=='regtest'
  async def rpc(method,params=None):
   credentials=pathlib.Path(config['cookie']).read_bytes().strip()
   async with c.post('http://127.0.0.1:'+str(config['rpc_port']),headers={'Authorization':'Basic '+base64.b64encode(credentials).decode()},json={'id':1,'method':method,'params':params or []}) as r:
    value=await r.json();assert not value.get('error'),value.get('error');return value['result']
  async def sam():
   try:
    reader,writer=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',7656),1)
    writer.write(b'HELLO VERSION MIN=3.1 MAX=3.1\n');await writer.drain()
    line=await asyncio.wait_for(reader.readline(),1);writer.close();await writer.wait_closed()
    return b'RESULT=OK' in line and b'VERSION=3.1' in line
   except OSError:return False
  async def address():return next((a['address'] for a in (await rpc('getnetworkinfo'))['localaddresses'] if a['address'].endswith('.b32.i2p')),None)
  async def indexed():
   reader,writer=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',50001),2)
   writer.write(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');await writer.drain()
   value=json.loads(await asyncio.wait_for(reader.readline(),2));writer.close();await writer.wait_closed()
   header=value.get('result',{});tip=await rpc('getbestblockhash')
   return header.get('height')==(await rpc('getblockcount')) and hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()==tip
  async def apply(values):
   review=await policy({'method':'preview','values':values})
   assert (await policy({'method':'apply','token':review['token']}))['phase']=='committed'
   assert (await policy({'method':'state'}))['requested']==values
   await wait(indexed,60,'electrs tip after policy save')
  key=pathlib.Path(config['cookie']).parent/'i2p_private_key'
  boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
  if previous:
   assert previous['boot_id']!=boot_id and previous['key_sha256']==digest(key)
   assert (await policy({'method':'state'}))['requested']==previous['values']
   assert await wait(address,600,'persistent address after reboot')==previous['address']
   assert await wait(sam,15,'SAM after reboot')
   assert await rpc('getbestblockhash')==previous['tip'];await wait(indexed,60,'electrs after reboot')
   assert system('is-active','justverify-i2p')=='active'
   note('actual reboot preserves policy, Core I2P identity/address, chain and electrs tip; SAM is active')
  else:
   assert system('show','justverify-i2p','-p','MainPID','--value')=='0' and not await sam()
   await rpc('generatetodescriptor',[1,'raw(51)']);await wait(indexed,60,'first block indexed')
   note('factory profile registration and real regtest Core/electrs tip; I2P off by default')
   original=(await policy({'method':'state'}))['requested']
   both={**original,'listen':'i2p','onlynet':'i2p','proxy':'0'}
   await apply(both);assert await wait(sam,15,'SAM enabled')
   assert system('show','justverify-i2p','-p','DynamicUser','--value')=='yes'
   pid=system('show','justverify-i2p','-p','MainPID','--value');assert int(pid)>0
   uid=next(l for l in pathlib.Path('/proc/'+pid+'/status').read_text().splitlines() if l.startswith('Uid:')).split()[1];assert int(uid)!=0
   local=await wait(address,600,'Core I2P identity');identity=digest(key)
   info=await rpc('getnetworkinfo');network=next(n for n in info['networks'] if n['name']=='i2p')
   assert not network['limited'] and network['proxy']=='127.0.0.1:7656'
   listeners=subprocess.check_output(['ss','-ltnp'],text=True)
   assert any('127.0.0.1:7656' in l for l in listeners.splitlines())
   assert not any(':7656' in l and '127.0.0.1:7656' not in l for l in listeners.splitlines())
   note('HTTP policy preview/save starts packaged nonroot router; loopback SAM and real Core identity verified')
   incoming={**both,'onlynet':'ipv4,ipv6,onion'};await apply(incoming)
   assert system('show','justverify-i2p','-p','MainPID','--value')==pid
   assert next(n for n in (await rpc('getnetworkinfo'))['networks'] if n['name']=='i2p')['limited']
   assert digest(key)==identity
   note('incoming-only policy keeps outgoing I2P limited and preserves running router')
   outgoing={**both,'listen':'none'};await apply(outgoing)
   assert await address() is None and digest(key)==identity
   note('outgoing-only policy removes advertised incoming identity while preserving its key')
   off={**both,'listen':'none','onlynet':'ipv4,ipv6,onion'};await apply(off)
   assert system('show','justverify-i2p','-p','MainPID','--value')=='0' and not await sam()
   note('both directions off stops router and SAM; Core/electrs recover at identical tip')
   await apply(both);assert await wait(address,600,'restored I2P address')==local
   corelog=pathlib.Path(config['cookie']).parent/'debug.log';offset=corelog.stat().st_size
   oldpid=system('show','justverify-i2p','-p','MainPID','--value');os.kill(int(oldpid),9)
   async def restarted():return system('show','justverify-i2p','-p','MainPID','--value') not in ('0',oldpid) and await sam()
   await wait(restarted,60,'automatic router crash recovery')
   async def new_core_session():
    with corelog.open() as log:log.seek(offset);lines=log.read().splitlines()
    return any('Persistent I2P SAM session ' in l and ' created, my address=' in l for l in lines)
   await wait(new_core_session,600,'new Core SAM session after router crash')
   assert await wait(address,600,'Core reconnect after router crash')==local and digest(key)==identity
   note('forced router failure triggers systemd recovery with same Core identity')
   with os.fdopen(os.open(checkpoint,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
    json.dump({'password':password,'boot_id':boot_id,'key_sha256':identity,'address':local,'values':both,'tip':await rpc('getbestblockhash')},f)
  REPORT['status']='PASS'
try:asyncio.run(main())
except Exception as error:REPORT['status']='FAIL';REPORT['error']=type(error).__name__+': '+str(error)
finally:
 print('JV_IMAGE_I2P '+json.dumps(REPORT),flush=True)
 P.mkdir(mode=0o700,exist_ok=True);(P/('result-'+REPORT.get('boot','unknown')+'.json')).write_text(json.dumps(REPORT,indent=2)+'\n')
 subprocess.run(['systemctl','reboot' if REPORT['status']=='PASS' and REPORT['boot']=='first' else 'poweroff'],check=True)
