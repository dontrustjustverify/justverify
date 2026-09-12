#!/usr/bin/env python3
"""Real HTTP owner API against the explicitly installed Linux fixture."""
import asyncio,json,os,pathlib,sys
import aiohttp
ORIGIN=os.environ.get('JV_DEVICE_TEST_ORIGIN','http://127.0.0.1:28646')
PASSWORD='Device-Test-2026!'
async def main():
 async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as c:
  headers={'Origin':ORIGIN}
  async def post(path,body,expected=200,custom=None):
   async with c.post(ORIGIN+path,json=body,headers=custom or headers) as r:
    text=await r.text();assert r.status==expected,(path,r.status,text)
    return json.loads(text) if expected==200 else None
  async def login(password=PASSWORD):
   result=await post('/login',{'password':password});headers['X-CSRF-Token']=result['csrf']
  await post('/device-settings',{'action':'state'},401)
  await login();state=await post('/device-settings',{'action':'state'});assert state['device']['model'] and state['device']['uptime_seconds']>0,state
  assert state['device']['hostname']=='justverify-dev';assert not state['remote_web']['running']
  await post('/device-settings',{'action':'preferences','theme':'amber','language':'en'},403,{'Origin':'http://evil.invalid','X-CSRF-Token':headers['X-CSRF-Token']})
  await post('/device-settings',{'action':'preferences','theme':'amber','language':'en'},403,{'Origin':ORIGIN,'X-CSRF-Token':'wrong'})
  await post('/device-settings',{'action':'preferences','theme':'invalid','language':'ko'},400)
  await post('/device-settings',{'action':'name','name':'bad\u001bname'},400)
  for theme,language in [('amber','en'),('green','ja'),('ice','ko')]:
   result=await post('/device-settings',{'action':'preferences','theme':theme,'language':language});assert result['preferences']['theme']==theme and result['preferences']['language']==language
  await post('/device-settings',{'action':'name','name':'검증 노드'})
  state=await post('/device-settings',{'action':'state'});assert state['preferences']=={'schema':1,'name':'검증 노드','theme':'ice','language':'ko'}
  await post('/device-settings',{'action':'password','current_password':'wrong-password','password':'Replacement-Test-2026!','password_confirm':'Replacement-Test-2026!'},401)
  async with c.get(ORIGIN+'/session') as r:assert r.status==200,'wrong current password must not log out the owner'
  oldcsrf=headers['X-CSRF-Token']
  await post('/device-settings',{'action':'password','current_password':PASSWORD,'password':'Replacement-Test-2026!','password_confirm':'Replacement-Test-2026!'})
  async with c.get(ORIGIN+'/session') as r:assert r.status==401,'password change must revoke existing session'
  await post('/login',{'password':PASSWORD},401)
  await login('Replacement-Test-2026!')
  await post('/device-settings',{'action':'password','current_password':'Replacement-Test-2026!','password':PASSWORD,'password_confirm':PASSWORD})
  await login()
  await post('/device-settings',{'action':'power_preview','operation':'reboot; touch /tmp/escaped'},400)
  plan=await post('/device-settings',{'action':'tor_preview','enabled':True})
  await post('/device-settings',{'action':'apply','token':plan['token'],'password':'wrong-password'},401)
  # A rejected apply consumes its review: cannot silently replay it later.
  await post('/device-settings',{'action':'apply','token':plan['token'],'password':PASSWORD},409)
  plan=await post('/device-settings',{'action':'tor_preview','enabled':True})
  result=await post('/device-settings',{'action':'apply','token':plan['token'],'password':PASSWORD});assert result['running'] and result['stored_enabled'] and result['url'].endswith('.onion/')
  # The RPC route is still independently disabled.
  result=await post('/remote-rpc',{'action':'state'});assert not result['running']
  print(json.dumps({'status':'PASS','checks':['device facts','Origin/CSRF enforcement','input validation','all themes/languages persist','name persists','wrong current password retains session','password rotation revokes sessions','old password rejected','power schema rejects injection','Tor review requires password and cannot replay','Tor running; RPC remains disabled']},ensure_ascii=False))
asyncio.run(main())
