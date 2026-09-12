#!/usr/bin/env python3
"""Real HTTPS + WebSocket + fixed executable, using temporary credentials."""
import asyncio, importlib.util, json, os, pathlib, secrets, socket, ssl, subprocess, tempfile, time
import aiohttp
R=pathlib.Path(__file__).resolve().parents[1]
async def run():
    with tempfile.TemporaryDirectory(prefix='jv-web-',dir=R/'.state') as temp:
        state=pathlib.Path(temp);state.chmod(0o700)
        subprocess.run(['python3',str(R/'scripts/web_identity.py'),str(state)],check=True,stdout=subprocess.DEVNULL)
        token=(state/'setup-token').read_text().strip();password=secrets.token_urlsafe(24)
        origin='https://localhost:28443'
        server=subprocess.Popen([str(R/'.cache/tools-venv/bin/python'),str(R/'web/server.py'),'--state',str(state),'--binary',str(R/'target/debug/justverify'),'--socket',str(state/'absent.sock'),'--origin',origin,'--port','28443'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        tls=ssl.create_default_context(cafile=str(state/'certificate.pem'))
        try:
            for _ in range(60):
                if server.poll() is not None:raise RuntimeError(server.stderr.read().decode())
                try:
                    with socket.create_connection(('127.0.0.1',28443),timeout=.2):break
                except OSError:await asyncio.sleep(.1)
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=tls)) as c:
                async with c.get(origin+'/terminal',headers={'Origin':origin}) as r:assert r.status==401
                async with c.post(origin+'/login',json={'password':password,'setup_token':token},headers={'Origin':'https://evil.invalid'}) as r:assert r.status==403
                async with c.post(origin+'/login',json={'password':password,'setup_token':'wrong'},headers={'Origin':origin}) as r:assert r.status==401
                async with c.post(origin+'/login',json={'password':password,'setup_token':token},headers={'Origin':origin}) as r:
                    assert r.status==200;csrf=(await r.json())['csrf'];cookie=r.headers['Set-Cookie'];assert all(x in cookie for x in ['Secure','HttpOnly','SameSite=Strict'])
                assert not (state/'setup-token').exists()
                async with c.get(origin+'/private-key.pem') as r:assert r.status==404
                async with c.ws_connect(origin+'/terminal',origin=origin) as ws:
                    payload=b''
                    for _ in range(60):
                        msg=await asyncio.wait_for(ws.receive(),3)
                        if msg.type==aiohttp.WSMsgType.BINARY:payload+=msg.data
                        if b'JustVerify' in payload:break
                    assert b'JustVerify' in payload and b'UNAVAILABLE' in payload
                    await ws.send_json({'input':'\x03'})
                    for _ in range(10):
                        msg=await asyncio.wait_for(ws.receive(),3)
                        if msg.type in (aiohttp.WSMsgType.CLOSE,aiohttp.WSMsgType.CLOSED):break
                    else:raise AssertionError('TUI exit must close socket, never shell')
                async with c.post(origin+'/logout',headers={'Origin':origin}) as r:assert r.status==403
                async with c.post(origin+'/logout',headers={'Origin':origin,'X-CSRF-Token':csrf}) as r:assert r.status==200
                async with c.get(origin+'/terminal',headers={'Origin':origin}) as r:assert r.status==401
                for _ in range(5):
                    async with c.post(origin+'/login',json={'password':'wrong-password'},headers={'Origin':origin}) as r:pass
                assert r.status==429
                assert password not in (state/'admin.json').read_text()
            report={'status':'PASS','transport':'actual TLS with certificate verification','checks':['unauthenticated WS denied','cross-Origin denied','wrong setup token denied','one-time owner setup','secure cookie','secret path not routed','actual fixed TUI PTY over WS','TUI exit closes WS','logout CSRF','session revocation','login rate limit','password hashed']}
            (R/'docs/evidence/web-security.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
        finally:
            server.terminate();server.wait(timeout=10)
if __name__=='__main__':asyncio.run(run())
