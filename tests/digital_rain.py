#!/usr/bin/env python3
"""Real authenticated preferences HTTP, legacy migration and browser rendering.

The manager socket is absent in this disposable fixture; no live node is used.
"""
import argparse,asyncio,hashlib,json,os,pathlib,re,secrets,stat,sys,tempfile
import aiohttp
from aiohttp import web
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web'))
from server import Bridge,app_for,atomic,password_hash
from device_settings import BACKGROUND,validate

async def main(node):
 data=bytes.fromhex(re.search(r"const hex='([a-f0-9]+)'",(ROOT/'web/static/genesis-rain.js').read_text())[1])
 twice=lambda b:hashlib.sha256(hashlib.sha256(b).digest()).digest()
 assert len(data)==285 and twice(data[:80])[::-1].hex()=='000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f'
 assert twice(data[81:])==data[36:68]
 with tempfile.TemporaryDirectory(prefix='jv-rain-') as temp:
  state=pathlib.Path(temp);password=secrets.token_urlsafe(24);salt=secrets.token_hex(16)
  atomic(state/'admin.json',json.dumps({'salt':salt,'hash':password_hash(password,salt)}))
  legacy={'schema':1,'name':'fixture','theme':'amber','language':'ja'}
  atomic(state/'preferences.json',json.dumps(legacy));before=(state/'preferences.json').read_bytes()
  bridge=Bridge(state,ROOT/'target/debug/justverify',state/'absent.sock','https://localhost');bridge.lan_http=True
  runner=web.AppRunner(app_for(bridge,lan_http=True),access_log=None);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
  origin='http://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1])
  try:
   async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as client:
    headers={'Origin':origin}
    async def post(body,expected=200,custom=None,path='/device-settings'):
     async with client.post(origin+path,json=body,headers=custom or headers) as response:
      assert response.status==expected,(body.get('action'),response.status,expected)
      return await response.json() if expected==200 else None
    await post({'action':'background','background':BACKGROUND},401)
    auth=await post({'password':password},path='/login');headers['X-CSRF-Token']=auth['csrf']
    prefs=(await post({'action':'state'}))['preferences'];assert prefs=={**legacy,'schema':2,'background':{'enabled':False,'brightness':40,'speed':160,'density':140}}
    assert (state/'preferences.json').read_bytes()==before,'Reading legacy settings must not rewrite them'
    good={'enabled':True,'brightness':100,'speed':400,'density':300}
    await post({'action':'background','background':good},403,{**headers,'Origin':'http://evil.invalid'})
    await post({'action':'background','background':good},403,{**headers,'X-CSRF-Token':'invalid'})
    for bad in [None,{}, {**good,'enabled':1}, {**good,'path':'private'},*({**good,key:value} for key,values in [('brightness',[True,2,101,18.5,'18']),('speed',[14,401,None]),('density',[29,301])] for value in values)]:
     await post({'action':'background','background':bad},400)
     assert (state/'preferences.json').read_bytes()==before
    prefs=(await post({'action':'background','background':good}))['preferences'];assert prefs['background']==good
    assert stat.S_IMODE((state/'preferences.json').stat().st_mode)==0o600
    second=Bridge(state,ROOT/'target/debug/justverify',state/'absent.sock','https://localhost')
    assert second.device_settings.preferences()['background']==good
    prefs=(await post({'action':'preferences','theme':'green','language':'ko'}))['preferences'];assert prefs['background']==good
    prefs=(await post({'action':'background','background':{**good,'enabled':False}}))['preferences'];assert prefs['background']=={**good,'enabled':False}
    assert prefs['theme']=='green' and prefs['language']=='ko' and prefs['name']=='fixture'
    async with client.get(origin+'/genesis-rain.js') as response:assert response.status==200 and await response.read()==(ROOT/'web/static/genesis-rain.js').read_bytes()
    async with client.get(origin+'/preferences.json') as response:assert response.status==404
   if node:
    env={**os.environ,'JV_RAIN_ORIGIN':origin,'JV_RAIN_PASSWORD':password}
    proc=await asyncio.create_subprocess_exec(node,str(ROOT/'tests/digital_rain_browser.cjs'),env=env)
    assert await proc.wait()==0,'Browser validation failed'
   print(json.dumps({'status':'PASS','genesis_header_and_merkle':'PASS','real_http':['owner authentication and Origin/CSRF','legacy read-only migration','strict ranges/types and unknown-field rejection','atomic0600 save','fresh server object reload','theme/language/name preserved','static asset allowlist; no settings file exposure'],'browser':'PASS' if node else 'NOT RUN','pi_applied':False}))
  finally:await runner.cleanup()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--browser-node');args=parser.parse_args();asyncio.run(main(args.browser_node))
