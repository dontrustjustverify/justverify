#!/usr/bin/env python3
"""External feature metadata and wallet operations against fresh Core/electrs."""
import argparse,asyncio,hashlib,json,pathlib,socket,ssl,subprocess,sys,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web'))
from electrum_tls import ElectrumTLS,lan_address
p=argparse.ArgumentParser();p.add_argument('--core',type=pathlib.Path,required=True);p.add_argument('--electrs',type=pathlib.Path,required=True);a=p.parse_args()
def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
rpc,p2p,backend,metrics=[port() for _ in range(4)]
processes=[]
with tempfile.TemporaryDirectory(prefix='jv-electrum-features-',dir='/var/tmp') as temporary:
    root=pathlib.Path(temporary);(root/'core').mkdir()
    def start(command):
        process=subprocess.Popen(list(map(str,command)),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(process);return process
    def cli(method,*args):
        result=subprocess.run([str(a.core/'bitcoin-cli'),'-regtest','-datadir='+str(root/'core'),'-rpcport='+str(rpc),method,*map(str,args)],capture_output=True,text=True,timeout=20)
        if result.returncode:raise RuntimeError('Isolated Core RPC failed: '+method)
        try:return json.loads(result.stdout)
        except ValueError:return result.stdout.strip()
    async def exchange(reader,writer,method,params=None,identifier=50003):
        writer.write(json.dumps({'id':identifier,'method':method,'params':params or []}).encode()+b'\n');await writer.drain()
        while True:
            reply=json.loads(await asyncio.wait_for(reader.readline(),5))
            if reply.get('id')==identifier:
                assert not reply.get('error'),method
                return reply['result']
    async def close(writer):writer.close();await writer.wait_closed()
    async def run():
        deadline=time.monotonic()+90
        while True:
            writer=None
            try:
                reader,writer=await asyncio.open_connection('127.0.0.1',backend)
                header=await exchange(reader,writer,'blockchain.headers.subscribe')
                if header['height']==101:break
            except (OSError,ValueError,asyncio.TimeoutError):pass
            finally:
                if writer:await close(writer)
            assert time.monotonic()<deadline,'Electrs readiness deadline'
            await asyncio.sleep(.25)
        reader,writer=await asyncio.open_connection('127.0.0.1',backend)
        upstream=await exchange(reader,writer,'server.features');await close(writer)
        assert upstream['hosts']=={'tcp_port':backend}
        expected=json.loads(json.dumps(upstream));expected['hosts']['tcp_port']=50001
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=justverify.local','-days','1','-keyout',str(root/'key.pem'),'-out',str(root/'cert.pem')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(root/'cert.pem',root/'key.pem')
        trusted=ssl.create_default_context(cafile=str(root/'cert.pem'))
        bridge=ElectrumTLS(backend,idle_seconds=3)
        servers=[]
        try:
            for tls in (False,True):
                for host in ('127.0.0.1','::1'):
                    server=await asyncio.start_server(bridge.handle,host,0,ssl=context if tls else None);servers.append(server)
                    endpoint=server.sockets[0].getsockname()[:2]
                    options={'ssl':trusted,'server_hostname':'justverify.local'} if tls else {}
                    reader,writer=await asyncio.open_connection(*endpoint,**options)
                    assert await exchange(reader,writer,'server.features')==expected
                    header=await exchange(reader,writer,'blockchain.headers.subscribe')
                    assert hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()==cli('getbestblockhash')
                    writer.write(json.dumps([{'id':50003,'method':'server.features','params':[]},{'id':'ping50003','method':'server.ping','params':[]}]).encode()+b'\n');await writer.drain()
                    replies=json.loads(await asyncio.wait_for(reader.readline(),5))
                    assert {r['id']:r['result'] for r in replies}=={50003:expected,'ping50003':None}
                    for _ in range(4):
                        await asyncio.sleep(1);assert await exchange(reader,writer,'server.ping') is None
                    address=cli('getnewaddress');raw=cli('createrawtransaction','[]',json.dumps({address:.1}))
                    funded=cli('fundrawtransaction',raw,'{"fee_rate":2}')
                    signed=cli('signrawtransactionwithwallet',funded['hex']);assert signed['complete']
                    txid=await exchange(reader,writer,'blockchain.transaction.broadcast',[signed['hex']])
                    assert txid in cli('getrawmempool')
                    assert await exchange(reader,writer,'blockchain.transaction.get',[txid])==signed['hex']
                    # A newly mined block must still arrive through the unchanged subscription.
                    cli('generatetoaddress',1,cli('getnewaddress'));tip=cli('getbestblockhash')
                    deadline=time.monotonic()+30
                    while True:
                        message=json.loads(await asyncio.wait_for(reader.readline(),5))
                        if message.get('method')=='blockchain.headers.subscribe':
                            got=message['params'][0]
                            if hashlib.sha256(hashlib.sha256(bytes.fromhex(got['hex'])).digest()).digest()[::-1].hex()==tip:break
                        assert time.monotonic()<deadline
                    # Three seconds of actual inactivity closes this connection.
                    assert await asyncio.wait_for(reader.read(1),5)==b'';await close(writer)
                    reader,writer=await asyncio.open_connection(*endpoint,**options)
                    assert await exchange(reader,writer,'server.features')==expected
                    assert await exchange(reader,writer,'server.ping') is None;await close(writer)
                    if tls:
                        try:await asyncio.open_connection(*endpoint,ssl=ssl.create_default_context(),server_hostname='justverify.local')
                        except ssl.SSLCertVerificationError:pass
                        else:raise AssertionError('Untrusted TLS certificate accepted')
            for address in ('::1','fd00::2','fe80::2','::ffff:192.168.1.2'):assert lan_address(address)
            for address in ('2001:4860:4860::8888','198.51.100.2','::ffff:8.8.8.8'):assert not lan_address(address)
            print(json.dumps({'status':'PASS','core_version':cli('getnetworkinfo')['version'],
                'electrs_version':upstream['server_version'],'checks':[
                'actual Core/electrs on isolated regtest; upstream announces its actual private port',
                'IPv4/IPv6 TCP and trusted TLS advertise50001 and retain all other feature fields',
                'batch request IDs unchanged; ping keeps connections alive beyond idle deadline',
                'four actual signed broadcasts accepted by Core and exact transaction hex retrieved',
                'four subsequent mined blocks delivered by existing header subscriptions',
                'idle closure/reconnect, certificate validation and LAN boundaries']}))
        finally:
            for server in servers:server.close();await server.wait_closed()
    try:
        start([a.core/'bitcoind','-regtest','-server','-datadir='+str(root/'core'),'-rpcport='+str(rpc),'-port='+str(p2p),'-bind=127.0.0.1','-connect=0','-dnsseed=0'])
        deadline=time.monotonic()+30
        while True:
            try:cli('getblockchaininfo');break
            except RuntimeError:assert time.monotonic()<deadline;time.sleep(.2)
        cli('createwallet','fixture');cli('generatetoaddress',101,cli('getnewaddress'))
        start([a.electrs,'--skip-default-conf-files','--network=regtest','--daemon-dir='+str(root/'core'),'--db-dir='+str(root/'index'),'--daemon-rpc-addr=127.0.0.1:'+str(rpc),'--daemon-p2p-addr=127.0.0.1:'+str(p2p),'--electrum-rpc-addr=127.0.0.1:'+str(backend),'--monitoring-addr=127.0.0.1:'+str(metrics)])
        asyncio.run(run())
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=30)
                except subprocess.TimeoutExpired:process.kill();process.wait()
