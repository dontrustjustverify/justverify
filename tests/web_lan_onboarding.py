#!/usr/bin/env python3
"""Real HTTP/TLS server, persistent enrollment and actual fixed TUI WebSocket."""
import asyncio,json,pathlib,secrets,socket,subprocess,tempfile
import aiohttp
R=pathlib.Path(__file__).resolve().parents[1]
async def main():
 with tempfile.TemporaryDirectory(dir=R/'.state') as tmp:
  state=pathlib.Path(tmp);state.chmod(0o700)
  subprocess.run([str(R/'.cache/tools-venv/bin/python'),str(R/'scripts/web_identity.py'),str(state)],check=True,stdout=subprocess.DEVNULL)
  origin='http://127.0.0.1:28446';headers={'Origin':origin};password=secrets.token_urlsafe(24)
  args=[str(R/'.cache/tools-venv/bin/python'),str(R/'web/server.py'),'--state',str(state),'--binary',str(R/'target/debug/justverify'),'--socket',str(state/'absent.sock'),'--origin','https://localhost:28445','--port','28445','--http-lan-port','28446','--lan-onboarding']
  server=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  try:
   for _ in range(80):
    if server.poll() is not None:raise RuntimeError(server.stderr.read().decode())
    try:
     with socket.create_connection(('127.0.0.1',28446),timeout=.1):break
    except OSError:await asyncio.sleep(.1)
   async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as c:
    for name,kind in [('favicon.svg','image/svg+xml'),('favicon.ico','image/vnd.microsoft.icon'),('apple-touch-icon.png','image/png')]:
     async with c.get(origin+'/'+name) as r:
      assert r.status==200 and r.content_type==kind,(name,r.status,r.content_type)
      assert await r.read()==(R/'web/static'/name).read_bytes()
    async with c.get(origin+'/auth-status') as r:assert await r.json()=={'setup_required':True,'requires_code':False}
    async with c.post(origin+'/setup',headers=headers,json={'password':password,'password_confirm':'different'}) as r:assert r.status==400
    assert not (state/'admin.json').exists()
    async with c.post(origin+'/setup',headers={'Origin':'http://evil.invalid'},json={'password':password,'password_confirm':password}) as r:assert r.status==403
    async with c.post(origin+'/setup',headers=headers,json={'password':password,'password_confirm':password}) as r:
     assert r.status==200,await r.text();csrf=(await r.json())['csrf'];cookie=r.headers['Set-Cookie'];assert 'HttpOnly' in cookie and 'Secure' not in cookie
    assert (state/'admin.json').exists() and not (state/'setup-token').exists()
    saved=(state/'admin.json').read_bytes()
    async with c.post(origin+'/setup',headers=headers,json={'password':password,'password_confirm':password}) as r:assert r.status==409
    assert (state/'admin.json').read_bytes()==saved
    async with c.get(origin+'/session') as r:assert r.status==200 and (await r.json())['csrf']==csrf
    async with c.get(origin+'/session',headers={'Origin':'http://evil.invalid'}) as r:assert r.status==403
    async with c.get(origin+'/auth-status') as r:assert not (await r.json())['setup_required']
    async with c.ws_connect(origin+'/terminal',origin=origin) as ws:
     data=b''
     for _ in range(40):
      msg=await asyncio.wait_for(ws.receive(),3)
      if msg.type==aiohttp.WSMsgType.BINARY:data+=msg.data
      if b'JustVerify' in data:break
     assert b'JustVerify' in data
    async with c.post(origin+'/rpc',json={}) as r:assert r.status==404
    async with c.post(origin+'/logout',headers={**headers,'X-CSRF-Token':csrf}) as r:assert r.status==200
    async with c.get(origin+'/session') as r:assert r.status==401
    async with c.post(origin+'/login',headers=headers,json={'password':password}) as r:assert r.status==200
    for _ in range(5):
     async with c.post(origin+'/login',headers=headers,json={'password':'incorrect-password'}) as r:assert r.status==401
    async with c.post(origin+'/login',headers=headers,json={'password':'incorrect-password'}) as r:assert r.status==429 and int(r.headers['Retry-After'])>0
   server.terminate();server.wait(timeout=10)
   server=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
   for _ in range(80):
    if server.poll() is not None:raise RuntimeError(server.stderr.read().decode())
    try:
     with socket.create_connection(('127.0.0.1',28446),timeout=.1):break
    except OSError:await asyncio.sleep(.1)
   async with aiohttp.ClientSession() as c:
    async with c.get(origin+'/auth-status') as r:assert not (await r.json())['setup_required']
    async with c.post(origin+'/login',headers=headers,json={'password':password}) as r:assert r.status==200
   assert (state/'admin.json').read_bytes()==saved
   print('PASS: no-code LAN setup, confirmation validation, CSRF, persistent registration, login/logout, actual TUI WS, no plain RPC route, rate limit')
  finally:
   server.terminate();server.wait(timeout=10)
asyncio.run(main())
