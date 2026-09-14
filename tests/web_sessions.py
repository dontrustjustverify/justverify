#!/usr/bin/env python3
"""Actual HTTP server restarts, private durable sessions and revocation boundaries.
Expiry cases age only this disposable fixture's stored timestamps, not the clock.
"""
import asyncio,json,pathlib,secrets,socket,subprocess,tempfile,time,stat
import aiohttp
R=pathlib.Path(__file__).resolve().parents[1]
def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
async def main():
 with tempfile.TemporaryDirectory(prefix='jv-sessions-',dir=R/'.state') as tmp:
  state=pathlib.Path(tmp);state.chmod(0o700);plain,tls=port(),port();origin=f'http://127.0.0.1:{plain}';password=secrets.token_urlsafe(24)
  subprocess.run([str(R/'.cache/tools-venv/bin/python'),str(R/'scripts/web_identity.py'),str(state)],check=True,stdout=subprocess.DEVNULL)
  args=[str(R/'.cache/tools-venv/bin/python'),str(R/'web/server.py'),'--state',str(state),'--binary',str(R/'target/debug/justverify'),'--socket',str(state/'absent.sock'),'--origin',f'https://localhost:{tls}','--port',str(tls),'--http-lan-port',str(plain),'--lan-onboarding']
  server=None
  async def start():
   nonlocal server
   server=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
   for _ in range(100):
    if server.poll() is not None:raise RuntimeError(server.stderr.read().decode())
    try:
     with socket.create_connection(('127.0.0.1',plain),timeout=.1):return
    except OSError:await asyncio.sleep(.1)
   raise AssertionError('server did not start')
  def stop():
   if server and server.poll() is None:server.terminate();server.wait(timeout=15)
  headers={'Origin':origin};store=state/'sessions.json';results=[]
  try:
   await start()
   async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as c:
    async with c.post(origin+'/setup',headers=headers,json={'password':password,'password_confirm':password}) as response:
     assert response.status==200,await response.text();csrf=(await response.json())['csrf'];token=response.cookies['jv_lan_session'].value
     assert response.cookies['jv_lan_session']['max-age']=='604800';assert response.cookies['jv_lan_session']['httponly'];assert response.cookies['jv_lan_session']['samesite']=='Strict'
    assert token not in store.read_text();assert stat.S_IMODE(store.stat().st_mode)==0o600
    async with c.get(origin+'/sessions.json') as response:assert response.status==404
    stop();saved=json.loads(store.read_text());key=next(iter(saved['sessions']));entry=saved['sessions'][key]
    entry['renewed']=time.time()-3700;entry['expires']=entry['renewed']+604800;before=entry['expires'];store.write_text(json.dumps(saved))
    await start()
    async with c.get(origin+'/session') as response:
     assert response.status==200 and (await response.json())['csrf']==csrf
     assert response.cookies['jv_lan_session']['max-age']=='604800'
    assert json.loads(store.read_text())['sessions'][key]['expires']>before+3600
    results+=['HTTP-only Strict cookie lasts7days','only token hash persisted with0600','session survives actual web restart','authenticated renewal refreshes cookie and durable expiry']
    original=store.read_bytes()
    async with c.get(origin+'/session',headers={'Origin':'http://evil.invalid'}) as response:assert response.status==403 and not response.cookies
    assert store.read_bytes()==original
    async with c.get(origin+'/session',headers={'Sec-Fetch-Site':'cross-site'}) as response:assert response.status==403
    # The LAN bearer cannot be used by renaming its cookie to the HTTPS audience.
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as other:
     async with other.get(f'https://localhost:{tls}/session',headers={'Cookie':'jv_session='+token}) as response:assert response.status==401
    async with c.post(origin+'/device-settings',headers={**headers,'X-CSRF-Token':csrf},json={'action':'password','current_password':password,'password':'New-Disposable-Pass-2026','password_confirm':'New-Disposable-Pass-2026'}) as response:assert response.status==200,await response.text()
    assert not json.loads(store.read_text())['sessions']
    async with c.get(origin+'/session') as response:assert response.status==401
    stop();await start()
    async with c.get(origin+'/session') as response:assert response.status==401
    async with c.post(origin+'/login',headers=headers,json={'password':'New-Disposable-Pass-2026'}) as response:
     assert response.status==200;csrf=(await response.json())['csrf'];newtoken=response.cookies['jv_lan_session'].value
    async with c.post(origin+'/logout',headers={**headers,'X-CSRF-Token':csrf}) as response:assert response.status==200
    stop();await start()
    async with c.get(origin+'/session',headers={'Cookie':'jv_lan_session='+newtoken}) as response:assert response.status==401
    async with c.post(origin+'/login',headers=headers,json={'password':'New-Disposable-Pass-2026'}) as response:assert response.status==200
    stop();saved=json.loads(store.read_text())
    for entry in saved['sessions'].values():entry['expires']=time.time()-1
    store.write_text(json.dumps(saved));await start()
    async with c.get(origin+'/session') as response:assert response.status==401 and not response.cookies
    results+=['cross-origin renewal refused','LAN/HTTPS cookie audiences isolated','password change revokes across restart','logout bearer replay rejected across restart','expired persisted session rejected']
   print(json.dumps({'status':'PASS','checks':results,'long_duration_wait':'NOT RUN; only private fixture timestamps aged for expiry boundaries'},indent=2))
  finally:stop()
asyncio.run(main())
