#!/usr/bin/env python3
"""Real local HTTP Tor-listener lifecycle with a separate owner/state.
Requires a provisioned published web hostname; does not test the Tor transport.
"""
import asyncio,json,pathlib,secrets,socket,sys,tempfile
import aiohttp
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'web'))
from server import Bridge,atomic,password_hash
async def main():
 with tempfile.TemporaryDirectory(prefix='jv-tor-session-') as tmp:
  state=pathlib.Path(tmp);state.chmod(0o700);password=secrets.token_urlsafe(24);salt=secrets.token_hex(16)
  atomic(state/'admin.json',json.dumps({'salt':salt,'hash':password_hash(password,salt)}))
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  def bridge():
   b=Bridge(state,pathlib.Path('/opt/justverify/bin/justverify'),state/'absent.sock','https://justverify.local');b.remote_web.port=port;return b
  b=bridge();host=b.remote_web.status()['onion_host'];assert host,'published Tor web hostname required'
  headers={'Host':host,'Origin':'http://'+host};url=f'http://127.0.0.1:{port}'
  try:
   await b.remote_web.start();b.remote_web.enabled=True
   async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as client:
    async with client.post(url+'/login',headers=headers,json={'password':password}) as r:
     assert r.status==200;token=r.cookies['jv_tor_session'].value;assert r.cookies['jv_tor_session']['max-age']=='604800';assert r.cookies['jv_tor_session']['httponly']
    assert token not in (state/'sessions.json').read_text()
    await b.remote_web.stop(revoke=False)
    if b.remote_cleanups:await asyncio.gather(*b.remote_cleanups)
    b=bridge();await b.remote_web.start();b.remote_web.enabled=True
    async with client.get(url+'/session',headers=headers) as r:assert r.status==200
    async with client.get(url+'/session',headers={**headers,'Origin':'http://evil.invalid'}) as r:assert r.status==403
    await b.remote_web.stop()
    if b.remote_cleanups:await asyncio.gather(*b.remote_cleanups)
    assert not json.loads((state/'sessions.json').read_text())['sessions']
    b=bridge();await b.remote_web.start();b.remote_web.enabled=True
    async with client.get(url+'/session',headers=headers) as r:assert r.status==401
   print(json.dumps({'status':'PASS','checks':['actual loopback HTTP requests to Tor-specific application','Tor session cookie and hash persistence','graceful listener restart preserves session','foreign Origin refused','explicit remote-web stop revokes session across restart'],'not_run':['Tor network transport in this lifecycle test']}))
  finally:
   await b.remote_web.stop()
   if b.remote_cleanups:await asyncio.gather(*b.remote_cleanups)
asyncio.run(main())
