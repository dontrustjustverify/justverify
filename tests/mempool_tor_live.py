#!/usr/bin/env python3
"""Real Tor, authenticated HTTP/WebSocket and isolated mempool_live regtest.

Keep mempool_live.py running with --hold; this test never opens other node data.
Test dependencies: aiohttp==3.13.3, aiohttp-socks==0.10.1, python-socks==2.8.2.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

import aiohttp
from aiohttp_socks import ProxyConnector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web'))
from server import Bridge,atomic,password_hash

def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]

async def until(check,seconds=60):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        value=await check()
        if value:return value
        await asyncio.sleep(.5)
    raise TimeoutError('Readiness deadline exceeded')

async def main(a):
    assert os.geteuid()!=0 and not a.state.exists()
    assert a.fixture.name.startswith('jv-mempool-test-') and (a.fixture/'ready').is_file()
    profile=json.loads((a.fixture/'profile.json').read_text())
    assert profile['network']=='regtest' and profile['rpc_port']==19643
    a.state.mkdir(mode=0o700)
    owner=a.state/'owner';owner.mkdir(mode=0o700)
    hostnames=a.state/'hostnames';hostnames.mkdir(mode=0o700)
    password=secrets.token_urlsafe(24);salt=secrets.token_hex(16)
    atomic(owner/'admin.json',json.dumps({'salt':salt,'hash':password_hash(password,salt)}))
    ports=[free_port() for _ in range(5)];assert len(set(ports))==5
    admin_port,mempool_port,server_socks,client_socks,control_port=ports
    processes=[];logs=[]
    result={'status':'FAIL','network':'isolated regtest','checks':[]}
    def bridge():
        b=Bridge(owner,ROOT/'target/release/justverify',owner/'absent.sock','https://justverify.local')
        remote=b.remote_web;remote.port=admin_port;remote.mempool_port=mempool_port
        remote.hostname_directory=hostnames;remote.mempool_bundle=a.bundle
        remote.mempool_runtime=a.fixture/'runtime';remote.mempool_profile=a.fixture/'profile.json'
        remote.mempool_backend='http://127.0.0.1:18999'
        return b
    b=bridge();descriptor_task=None;control_writer=None
    def cli(method,*args):
        command=[str(a.core/'bitcoin-cli'),'-regtest','-datadir='+str(a.fixture/'core'),'-rpcport=19643',method]
        command += [arg if isinstance(arg,str) else json.dumps(arg) for arg in args]
        run=subprocess.run(command,capture_output=True,text=True,timeout=30)
        assert run.returncode==0,method+' failed'
        try:return json.loads(run.stdout)
        except ValueError:return run.stdout.strip()
    async def stop(revoke=True):
        await b.remote_web.stop(revoke=revoke)
        if b.remote_cleanups:await asyncio.gather(*b.remote_cleanups)
    async def enable(value):
        plan=await b.remote_web.manage({'action':'preview','enabled':value})
        await b.remote_web.manage({'action':'apply','token':plan['token']})
    try:
        for name,socks in [('server',server_socks),('client',client_socks)]:
            data=a.state/name;data.mkdir(mode=0o700)
            config='DataDirectory '+str(data)+'\nSocksPort 127.0.0.1:'+str(socks)+'\nLog notice stdout\n'
            if name=='server':
                config+='HiddenServiceDir '+str(data/'web')+'\nHiddenServicePort 80 127.0.0.1:'+str(admin_port)+'\nHiddenServicePort 3006 127.0.0.1:'+str(mempool_port)+'\n'
                config+='ControlPort 127.0.0.1:'+str(control_port)+'\nCookieAuthentication 1\n'
            config_file=a.state/(name+'.conf');config_file.write_text(config)
            log=(a.state/(name+'.log')).open('wb');logs.append(log)
            processes.append(subprocess.Popen(['tor','-f',str(config_file)],stdout=log,stderr=log))
        async def published():return (a.state/'server/web/hostname').exists()
        await until(published,20)
        host=(a.state/'server/web/hostname').read_text().strip()
        (hostnames/'web.hostname').write_text(host+'\n')
        reader,control_writer=await asyncio.open_connection('127.0.0.1',control_port)
        cookie=(a.state/'server/control_auth_cookie').read_bytes().hex()
        control_writer.write(('AUTHENTICATE '+cookie+'\r\n').encode());await control_writer.drain()
        assert await reader.readline()==b'250 OK\r\n'
        control_writer.write(b'SETEVENTS HS_DESC\r\n');await control_writer.drain()
        assert await reader.readline()==b'250 OK\r\n'
        async def descriptor_uploaded():
            while line:=await reader.readline():
                if line.startswith(b'650 HS_DESC UPLOADED '):return True
            raise RuntimeError('Tor control closed before descriptor upload')
        descriptor_task=asyncio.create_task(descriptor_uploaded())
        await enable(True)

        async def suite(transport):
            nonlocal b
            over_tor=transport=='tor'
            admin='http://'+host if over_tor else 'http://127.0.0.1:'+str(admin_port)
            explorer='http://'+host+':3006' if over_tor else 'http://127.0.0.1:'+str(mempool_port)
            ah={'Host':host,'Origin':'http://'+host}
            mh={'Host':host+':3006','Origin':'http://'+host+':3006'}
            connector=ProxyConnector.from_url('socks5://127.0.0.1:'+str(client_socks)) if over_tor else None
            async with aiohttp.ClientSession(connector=connector,cookie_jar=aiohttp.CookieJar(unsafe=True),timeout=aiohttp.ClientTimeout(total=90)) as c:
                async def get(path,expected=200,headers=None):
                    async with c.get(explorer+path,headers=headers or mh,allow_redirects=False) as response:
                        body=await response.text()
                        assert response.status==expected,(transport,path,response.status)
                        return body,response.headers
                await get('/api/blocks/tip/height',401)
                _,headers=await get('/ko/',303,{**mh,'Accept':'text/html'})
                assert headers['Location']=='http://'+host+'/'
                async def login():
                    async with c.post(admin+'/login',headers=ah,json={'password':password}) as response:
                        assert response.status==200
                        assert response.cookies['jv_tor_session']['httponly']
                        return (await response.json())['csrf']
                csrf=await login()
                for locale in ('ko','en-US','ja'):
                    html,_=await get('/'+locale+'/')
                    assert '<app-root' in html and '/justverify-integration.js' in html
                config,_=await get('/resources/config.js')
                assert '"NGINX_HOSTNAME": "'+host+'"' in config and '"NGINX_PORT": "3006"' in config
                assert 'justverify.patch' in (await get('/source/'))[0]
                assert 'url.port' in (await get('/justverify-integration.js'))[0]
                height=int((await get('/api/blocks/tip/height'))[0]);tip=(await get('/api/blocks/tip/hash'))[0]
                assert height==cli('getblockcount') and tip==cli('getbestblockhash')
                await get('/api/mempool',403,{**mh,'Origin':'http://evil.invalid'})
                await get('/api/mempool',403,{**mh,'Host':'justverify.local:3006'})
                async with c.post(explorer+'/api/tx',data='00',headers={'Host':host+':3006'}) as response:assert response.status==403
                # Both the HTML app and arbitrary API methods require the Tor session.
                async def websocket():
                    ws=await c.ws_connect(explorer+'/api/v1/ws',headers=mh)
                    await ws.send_json({'action':'init'})
                    await ws.send_json({'action':'want','data':['blocks','stats']})
                    async with asyncio.timeout(30):
                        async for message in ws:
                            if message.type==aiohttp.WSMsgType.TEXT:
                                data=json.loads(message.data)
                                blocks=data.get('blocks',[])+([data['block']] if 'block' in data else [])
                                if any(block['id']==tip and block['height']==height for block in blocks):return ws
                    raise AssertionError('Actual WebSocket tip missing')
                ws=await websocket()
                async with c.post(admin+'/logout',headers={**ah,'X-CSRF-Token':csrf}) as response:assert response.status==200
                async with asyncio.timeout(15):
                    async for _ in ws:pass
                assert ws.closed
                await get('/api/mempool',401)
                await login()
                await stop(revoke=False)
                b=bridge();await b.remote_web.restore()
                await get('/api/mempool')
                if not over_tor:
                    ws=await websocket()
                    for session in b.sessions.values():session['expires']=time.time()-1
                    async with asyncio.timeout(15):
                        async for _ in ws:pass
                    assert ws.closed
                    await get('/api/mempool',401)
                    await login()
                    for session in b.sessions.values():session['renewed']=time.time()-3600
                    _,headers=await get('/api/mempool')
                    assert 'jv_tor_session=' in headers.get('Set-Cookie','')
                    result['checks'].append('session deadline closes WebSocket; authenticated HTTP renews cookie')
                # A real signed transaction traverses the Tor HTTP proxy.
                if over_tor:
                    receiver=cli('getnewaddress')
                    raw=cli('createrawtransaction',[],{receiver:1})
                    funded=cli('fundrawtransaction',raw,{'fee_rate':2})
                    signed=cli('signrawtransactionwithwallet',funded['hex']);assert signed['complete']
                    async with c.post(explorer+'/api/tx',data=signed['hex'],headers={**mh,'Content-Type':'text/plain'}) as response:
                        assert response.status==200;txid=await response.text()
                    assert txid in cli('getrawmempool')
                    async def unconfirmed():
                        text,_=await get('/api/tx/'+txid)
                        return json.loads(text)['status']['confirmed'] is False
                    await until(unconfirmed)
                    tip=cli('generatetoaddress',1,receiver)[0];height=cli('getblockcount')
                    async def confirmed():
                        text,_=await get('/api/tx/'+txid)
                        return json.loads(text)['status']['confirmed']
                    await until(confirmed)
                    text,_=await get('/api/blocks/tip/hash');assert text==tip
                    with socket.create_connection(('127.0.0.1',19601),3) as sock:
                        sock.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n')
                        header=json.loads(sock.makefile('rb').readline())['result']
                    assert header['height']==height
                    assert hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()==tip
                    result.update(txid=txid,confirmations=cli('gettransaction',txid)['confirmations'],height=height,tip=tip)
                ws=await websocket()
                await enable(False)
                async with asyncio.timeout(15):
                    async for _ in ws:pass
                assert ws.closed
                for port in (admin_port,mempool_port):
                    with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',port))!=0
                assert not json.loads((owner/'sessions.json').read_text())['sessions']
                if b.remote_cleanups:await asyncio.gather(*b.remote_cleanups)
                await enable(True)
                await get('/api/mempool',401)
                result['checks'].append(transport+': locales/config/source, shared login, actual tip and WebSocket, Host/Origin/POST guards, logout, restart, disable and session revocation')
                print(json.dumps({'stage':transport,'status':'PASS'}),flush=True)

        await suite('loopback')
        await stop()
        with socket.socket() as occupied:
            occupied.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            occupied.bind(('127.0.0.1',mempool_port));occupied.listen()
            try:await enable(True)
            except OSError:pass
            else:raise AssertionError('Port collision was accepted')
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',admin_port))!=0
        assert not b.remote_web.enabled
        result['checks'].append('real port collision fails closed on both listeners')
        if b.remote_cleanups:await asyncio.gather(*b.remote_cleanups)
        await enable(True)
        async def bootstrapped():
            assert all(process.poll() is None for process in processes),'Tor exited'
            return all('Bootstrapped 100%' in (a.state/(name+'.log')).read_text() for name in ('server','client')) and descriptor_task.done() and descriptor_task.result()
        await until(bootstrapped,240)
        result['checks'].append('independent Tor bootstraps and HS_DESC UPLOADED observed before requests')
        await suite('tor')
        result['status']='PASS'
    except Exception as error:
        result['error']=type(error).__name__
        raise
    finally:
        await stop()
        if descriptor_task:
            descriptor_task.cancel();await asyncio.gather(descriptor_task,return_exceptions=True)
        if control_writer:control_writer.close();await control_writer.wait_closed()
        for process in processes:
            if process.poll() is None:process.terminate()
        for process in processes:
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        for log in logs:log.close()
        (a.state/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('state','fixture','core','bundle'):parser.add_argument('--'+name,type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
