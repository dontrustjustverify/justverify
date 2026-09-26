#!/usr/bin/env python3
"""Actual LAN/Tor HTTP session lifecycle, scale, revocation and schema migration.

Only private fixture timestamps are aged for expiry/renewal boundaries.
Tor-specific routes are reached over loopback; this is not a Tor network test.
"""
import argparse,asyncio,hashlib,json,os,pathlib,secrets,sys,tempfile,time
import aiohttp
from aiohttp import web
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web'))
from server import Bridge,app_for,atomic,password_hash,SESSION_SECONDS

async def main(browser_node=None):
 with tempfile.TemporaryDirectory(prefix='jv-session-management-') as temporary:
  state=pathlib.Path(temporary);password=secrets.token_urlsafe(24);salt=secrets.token_hex(16)
  atomic(state/'admin.json',json.dumps({'salt':salt,'hash':password_hash(password,salt)}))
  names=state/'hostnames';names.mkdir();host='a'*56+'.onion';(names/'web.hostname').write_text(host)
  def create_bridge():
   b=Bridge(state,ROOT/'target/debug/justverify',state/'absent.sock','https://localhost');b.lan_http=True
   b.remote_web.hostname_directory=names;b.remote_web.enabled=True;return b
  b=create_bridge();runners=[]
  async def listen(app):
   r=web.AppRunner(app,access_log=None);await r.setup();site=web.TCPSite(r,'127.0.0.1',0);await site.start();runners.append(r)
   return 'http://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1])
  async def stop():
   for r in reversed(runners):await r.cleanup()
   runners.clear()
  try:
   lan=await listen(app_for(b,lan_http=True));tor=await listen(b.remote_web.application())
   async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as c:
    async def login(is_tor=False,ua='Mozilla/5.0 (iPhone) Version/17.0 Mobile Safari/604.1',secret=None):
     origin=tor if is_tor else lan;headers={'Origin':'http://'+host if is_tor else lan,'User-Agent':ua}
     if is_tor:headers['Host']=host
     async with c.post(origin+'/login',headers=headers,json={'password':secret or password}) as r:
      assert r.status==200,('login',r.status)
      data=await r.json();name='jv_tor_session' if is_tor else 'jv_lan_session';token=r.cookies[name].value
      assert r.cookies[name]['max-age']==str(SESSION_SECONDS) and r.cookies[name]['httponly'] and r.cookies[name]['samesite']=='Strict'
      return {'url':origin,'headers':{**headers,'Cookie':name+'='+token,'X-CSRF-Token':data['csrf']},'token':token,'key':b.session_key(token)}
    async def call(owner,path='/sessions',body=None,headers=None):
     async with c.request('POST' if body is not None else 'GET',owner['url']+path,headers=headers or owner['headers'],json=body) as r:
      raw=await r.text()
      return r.status,json.loads(raw) if raw.startswith('{') else None
    owner=await login();first=await login(True)
    # Exceed both the former count limit and the former 131072-byte reload limit
    # using real password verification and HTTP logins, never fabricated sessions.
    for i in range(410):await login(bool(i%2))
    assert len(b.sessions)==412 and (state/'sessions.json').stat().st_size>131072
    assert (await call(first,'/session'))[0]==200 and (await call(owner,'/session'))[0]==200
    status,listed=await call(owner);assert status==200 and len(listed['sessions'])==412
    assert len({s['id'] for s in listed['sessions']})==412 and sum(s['current'] for s in listed['sessions'])==1
    assert listed['sessions'][0]['current'] and listed['sessions'][0]['browser']=='Safari' and listed['sessions'][0]['platform']=='iOS'
    assert all(set(s)=={'id','created_at','last_seen_at','expires_at','browser','platform','current','connection'} for s in listed['sessions'])
    for record in (json.dumps(listed),(state/'sessions.json').read_text()):
     assert owner['token'] not in record and first['token'] not in record and 'Mozilla' not in record
    # Request metadata cannot inject user-supplied markup or personal labels.
    malicious=await login(ua='<script>untrusted-name</script> private-host')
    entry=b.sessions[malicious['key']];assert entry['browser']==entry['platform']=='Unknown'
    assert 'untrusted-name' not in (state/'sessions.json').read_text()
    # Renewal extends the same ID without creating another session or rotating tokens.
    entry=b.sessions[first['key']];entry['renewed']-=3700;entry['last_seen']-=3700;before=entry['expires'];count=len(b.sessions);identity=entry['id']
    assert (await call(first,'/session'))[0]==200
    assert entry['expires']>before and entry['id']==identity and len(b.sessions)==count
    assert entry['last_seen']>time.time()-2
    # No credentials / wrong CSRF / foreign Origin / malformed IDs cannot revoke.
    saved=(state/'sessions.json').read_bytes()
    async with c.get(lan+'/sessions') as r:assert r.status==401
    assert (await call(owner,body={'action':'revoke_others'},headers={**owner['headers'],'X-CSRF-Token':'wrong'}))[0]==403
    assert (await call(owner,body={'action':'revoke_others'},headers={**owner['headers'],'Origin':'http://invalid.test'}))[0]==403
    assert (await call(owner,body={'action':'revoke','id':'../private'}))[0]==400
    assert (await call(owner,body={'action':'revoke_others','path':'private'}))[0]==400
    assert (state/'sessions.json').read_bytes()==saved
    # An already authenticated live TUI socket is closed when its exact session is revoked.
    async with c.ws_connect(first['url']+'/terminal',headers={k:v for k,v in first['headers'].items() if k!='Origin'},origin=first['headers']['Origin']) as ws:
     for _ in range(50):
      msg=await asyncio.wait_for(ws.receive(),3)
      if msg.type==aiohttp.WSMsgType.BINARY and b'JustVerify' in msg.data:break
     else:raise AssertionError('real fixed TUI did not respond')
     status,result=await call(owner,body={'action':'revoke','id':identity})
     assert status==200 and result=={'revoked_count':1,'revoked_current':False}
     for _ in range(50):
      msg=await asyncio.wait_for(ws.receive(),3)
      if msg.type in (aiohttp.WSMsgType.CLOSE,aiohttp.WSMsgType.CLOSED):break
     else:raise AssertionError('revoked TUI remained connected')
    assert (await call(first,'/session'))[0]==401 and (await call(owner,'/session'))[0]==200
    assert (await call(owner,body={'action':'revoke','id':identity}))[1]['revoked_count']==0
    # Reload the >128KiB store on a fresh bridge after closing the old listeners.
    await stop();b=create_bridge();lan=await listen(app_for(b,lan_http=True));tor=await listen(b.remote_web.application())
    owner['url']=lan;owner['headers']['Origin']=lan;first['url']=tor
    assert len(b.sessions)>300 and (await call(owner,'/session'))[0]==200 and (await call(first,'/session'))[0]==401
    # Invalid passwords do not change sessions; actual throttle expires independently.
    before=set(b.sessions)
    for _ in range(5):
     async with c.post(lan+'/login',headers={'Origin':lan},json={'password':'incorrect-test-password'}) as r:assert r.status==401
    async with c.post(lan+'/login',headers={'Origin':lan},json={'password':password}) as r:assert r.status==429 and int(r.headers['Retry-After'])>0
    assert set(b.sessions)==before
    attempts={k:list(v) for k,v in b.attempts.items()}
    async with c.post(lan+'/login',headers={'Origin':lan},json={'password':password}) as r:assert r.status==429
    assert b.attempts==attempts
    for vals in b.attempts.values():vals[:]=[v-301 for v in vals]
    recent=await login(True)
    # A slow request cannot recreate a session after another browser revokes it.
    async def delayed(path,headers,body):
     sent=asyncio.Event();release=asyncio.Event();payload=json.dumps(body).encode()
     async def chunks():
      yield payload[:1];sent.set();await release.wait();yield payload[1:]
     async def send():
      async with c.post(lan+path,headers=headers,data=chunks()) as r:return r.status
     task=asyncio.create_task(send());await sent.wait();await asyncio.sleep(.1)
     return task,release
    pending,release=await delayed('/login',{'Origin':lan,'Content-Type':'application/json'},{'password':password})
    assert (await call(owner,body={'action':'revoke_others'}))[0]==200
    release.set();assert await pending==409 and set(b.sessions)=={owner['key']}
    victim=await login();pending,release=await delayed('/sessions',victim['headers'],{'action':'revoke_others'})
    assert (await call(owner,body={'action':'revoke','id':b.sessions[victim['key']]['id']}))[0]==200
    release.set();assert await pending==401 and set(b.sessions)=={owner['key']}
    recent=await login(True);await login()
    expired_key=next(k for k in b.sessions if k not in (owner['key'],recent['key']))
    b.sessions[expired_key]['expires']=time.time()-1
    status,listed=await call(owner);assert status==200 and expired_key not in b.sessions
    # Bulk logout keeps this session and revokes every other audience, durably.
    expected=len(b.sessions)-1;status,result=await call(owner,body={'action':'revoke_others'})
    assert status==200 and result=={'revoked_count':expected,'revoked_current':False}
    assert set(b.sessions)=={owner['key']} and set(create_bridge().sessions)=={owner['key']}
    assert (await call(recent,'/session'))[0]==401 and (await call(owner,'/session'))[0]==200
    # Self-revocation clears the session cookie; ordinary logout follows the same path.
    session_id=b.sessions[owner['key']]['id'];status,result=await call(owner,body={'action':'revoke','id':session_id})
    assert status==200 and result['revoked_current'] and not b.sessions and not create_bridge().sessions
    owner=await login();assert (await call(owner,'/logout',{}))[0]==200
    assert not b.sessions
    # Old-format sessions migrate without losing a valid bearer; unknown creation time stays unknown.
    owner=await login();stored=json.loads((state/'sessions.json').read_text());old=stored['sessions'][owner['key']]
    stored['schema']=1;stored['sessions']={owner['key']:{k:old[k] for k in ('expires','renewed','csrf','audience','tor_web')}}
    await stop();atomic(state/'sessions.json',json.dumps(stored));b=create_bridge();lan=await listen(app_for(b,lan_http=True));tor=await listen(b.remote_web.application());owner['url']=lan;owner['headers']['Origin']=lan
    assert (await call(owner,'/session'))[0]==200
    status,listed=await call(owner);assert listed['sessions'][0]['created_at'] is None
    await login();assert json.loads((state/'sessions.json').read_text())['schema']==2
    if browser_node:
     env=dict(os.environ,JV_LOGIN_TEST_ORIGIN=lan,JV_LOGIN_TEST_PASSWORD=password,PYTHONDONTWRITEBYTECODE='1')
     child=await asyncio.create_subprocess_exec(browser_node,str(ROOT/'tests/web_login_browser.cjs'),env=env)
     assert await child.wait()==0,'browser session management failed'
   print(json.dumps({'status':'PASS','checks':['412 real logins without rejection or eviction','reload session store over 128KiB','stable ID and bearer on renewal','safe device labels, no raw agent/IP/bearer in list','authenticated list and CSRF/Origin guards','individual revocation and live TUI closure','all other audiences revoked, current preserved','durable revocation and self logout','slow login/revocation races rejected after session invalidation','failure throttle remains independent','expiry and legacy-session migration'],'not_run':['external Tor network','physical iPhone','wall-clock 7 day wait']}))
  finally:await stop()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--browser-node');a=p.parse_args();asyncio.run(main(a.browser_node))
