#!/usr/bin/env python3
"""Real HTTPS owner control, durable state and actual existing regtest Core query."""
import asyncio,base64,json,pathlib,secrets,socket,ssl,sys,tempfile
import aiohttp
from aiohttp import web
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'web'),str(ROOT/'scripts')]
from server import Bridge,app_for,atomic
from web_identity import ensure_identity

def closed():
 with socket.socket() as s:return s.connect_ex(('127.0.0.1',28443))!=0
async def main():
 assert closed()
 state=pathlib.Path(tempfile.mkdtemp(prefix='jv-remote-control-',dir='/var/tmp'));ensure_identity(state)
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 origin=f'https://127.0.0.1:{port}';password=secrets.token_urlsafe(32)
 tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(state/'certificate.pem',state/'private-key.pem')
 context=ssl.create_default_context(cafile=str(state/'certificate.pem'))
 async def start():
  bridge=Bridge(state,ROOT/'target/release/justverify',state/'unused.sock',origin)
  runner=web.AppRunner(app_for(bridge),access_log=None);await runner.setup()
  await web.TCPSite(runner,'127.0.0.1',port,ssl_context=tls).start()
  return bridge,runner
 bridge,runner=await start()
 async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=context,force_close=True),cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
  async def post(path,body,csrf=None):
   async with session.post(origin+path,json=body,headers={'Origin':origin,**({'X-CSRF-Token':csrf} if csrf else {})}) as r:
    raw=await r.read();return r.status,json.loads(raw) if r.content_type=='application/json' else None
  async def login(first=False):
   body={'password':password}
   if first:body['setup_token']=(state/'setup-token').read_text().strip()
   status,result=await post('/login',body);assert status==200;return result['csrf']
  try:
   assert (await post('/remote-rpc',{'action':'state'}))[0]==401
   csrf=await login(True)
   assert (await post('/remote-rpc',{'action':'state'}))[0]==403
   assert (await post('/remote-rpc',{'action':'state'},csrf))[1]['running'] is False and closed()
   status,client=await post('/rpc-clients',{'action':'create','label':'remote-test'},csrf);assert status==200
   _,plan=await post('/remote-rpc',{'action':'preview','enabled':True},csrf);assert closed()
   apply={'action':'apply','token':plan['token'],'password':'wrong-password-value'}
   assert (await post('/remote-rpc',apply,csrf))[0]==401 and closed()
   apply['password']=password
   status,result=await post('/remote-rpc',apply,csrf);assert status==200 and result['running'] and result['stored_enabled']
   auth='Basic '+base64.b64encode((client['id']+':'+client['password']).encode()).decode()
   async def query():
    async with session.post('http://127.0.0.1:28443/',json={'id':1,'method':'getblockcount'},headers={'Authorization':auth}) as r:
     assert r.status==200;assert type((await r.json())['result']) is int
   await query()
   print('PASS owner/CSRF/reauthentication, preview causes no listener, actual Core RPC after committed enable',flush=True)
   await runner.cleanup();assert closed();bridge,runner=await start();await query();csrf=await login()
   _,plan=await post('/remote-rpc',{'action':'preview','enabled':False},csrf)
   status,result=await post('/remote-rpc',{'action':'apply','token':plan['token'],'password':password},csrf)
   assert status==200 and not result['running'] and not result['stored_enabled'] and closed()
   print('PASS new server lifecycle restores committed enable/client identity; reviewed disable closes listener and persists',flush=True)
   await runner.cleanup()
   atomic(state/'remote-rpc.json',json.dumps({'schema':1,'enabled':True,'phase':'applying'}))
   bridge,runner=await start();assert closed();csrf=await login()
   status,result=await post('/remote-rpc',{'action':'state'},csrf);assert status==200 and result['needs_recovery']
   _,stale=await post('/remote-rpc',{'action':'preview','enabled':True},csrf)
   atomic(state/'remote-rpc.json',json.dumps({'schema':1,'enabled':False,'phase':'applying'}))
   assert (await post('/remote-rpc',{'action':'apply','token':stale['token'],'password':password},csrf))[0]==409 and closed()
   _,plan=await post('/remote-rpc',{'action':'preview','enabled':False},csrf)
   status,result=await post('/remote-rpc',{'action':'apply','token':plan['token'],'password':password},csrf)
   assert status==200 and not result['needs_recovery'] and closed()
   assert password not in (state/'remote-rpc.json').read_text()
   print('PASS persisted applying state fails closed, stale review refused, explicit review recovers; no password in setting',flush=True)
   with socket.socket() as blocker:
    blocker.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    blocker.bind(('127.0.0.1',28443));blocker.listen()
    _,plan=await post('/remote-rpc',{'action':'preview','enabled':True},csrf)
    assert (await post('/remote-rpc',{'action':'apply','token':plan['token'],'password':password},csrf))[0]==503
    status,result=await post('/remote-rpc',{'action':'state'},csrf)
    assert status==200 and not result['running'] and result['needs_recovery']
   assert closed()
   _,plan=await post('/remote-rpc',{'action':'preview','enabled':False},csrf)
   status,result=await post('/remote-rpc',{'action':'apply','token':plan['token'],'password':password},csrf)
   assert status==200 and not result['needs_recovery'] and closed()
   print('PASS actual occupied-port failure remains closed with recovery state; HTTPS owner recovery remains available',flush=True)
  finally:await runner.cleanup()
 assert closed()
asyncio.run(main())
