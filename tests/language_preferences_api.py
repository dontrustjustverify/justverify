#!/usr/bin/env python3
"""Language persistence and API boundaries on an explicitly isolated web fixture."""
import argparse,asyncio,json
import aiohttp
p=argparse.ArgumentParser();p.add_argument('--origin',default='http://127.0.0.1:28648');a=p.parse_args()
async def main():
 async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as c:
  async with c.get(a.origin+'/auth-status') as r:
   assert r.headers.get('X-JustVerify-Test')=='language-preferences','Refusing a non-fixture endpoint'
  headers={'Origin':a.origin}
  async def post(path,body,status=200,custom=None):
   async with c.post(a.origin+path,json=body,headers=custom or headers) as r:
    assert r.status==status,(path,r.status);return await r.json() if status==200 else None
  await post('/device-settings',{'action':'state'},401)
  auth=await post('/login',{'password':'Language-Test-2026!'});headers['X-CSRF-Token']=auth['csrf']
  initial=await post('/device-settings',{'action':'state'});assert initial['preferences']['language']=='auto'
  await post('/device-settings',{'action':'preferences','theme':'teal','language':'auto'},403,{'Origin':'http://invalid.test','X-CSRF-Token':auth['csrf']})
  await post('/device-settings',{'action':'preferences','theme':'teal','language':'auto'},403,{'Origin':a.origin,'X-CSRF-Token':'wrong'})
  for invalid in ('de','en-US',None,[],True):await post('/device-settings',{'action':'preferences','theme':'teal','language':invalid},400)
  for language in ('en','ko','ja','auto'):
   result=await post('/device-settings',{'action':'preferences','theme':'teal','language':language});assert result['preferences']['language']==language
   await post('/device-settings',{'action':'name','name':'Language Test'})
   assert (await post('/device-settings',{'action':'state'}))['preferences']['language']==language
  await post('/device-settings',{'action':'preferences','theme':'amber','language':'auto'})
  assert (await post('/device-settings',{'action':'state'}))['preferences']=={'schema':1,'name':'Language Test','theme':'amber','language':'auto'}
  await post('/logout',{})
  auth=await post('/login',{'password':'Language-Test-2026!'});headers['X-CSRF-Token']=auth['csrf']
  assert (await post('/device-settings',{'action':'state'}))['preferences']['language']=='auto'
 print(json.dumps({'status':'PASS','checks':['fresh default auto','all explicit languages and auto persist','name/theme changes preserve language choice','logout/login persistence','Origin and CSRF enforced','invalid values rejected']}))
asyncio.run(main())
