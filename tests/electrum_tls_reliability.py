#!/usr/bin/env python3
"""Real Electrum over trusted TLS on both IP families in isolated regtest."""
import argparse,asyncio,hashlib,json,pathlib,ssl,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web'))
from electrum_tls import ElectrumTLS,lan_address
p=argparse.ArgumentParser();p.add_argument('--core',type=pathlib.Path,required=True);p.add_argument('--state',type=pathlib.Path,required=True)
a=p.parse_args()
assert a.state.name.startswith('jv-mempool-test-') and (a.state/'ready').exists()
def cli(method,*values):
    out=subprocess.check_output([str(a.core/'bitcoin-cli'),'-regtest','-datadir='+str(a.state/'core'),'-rpcport=19643',method,*values],text=True,timeout=20)
    try:return json.loads(out)
    except ValueError:return out.strip()
async def main():
    tlsdir=a.state/'tls-test';tlsdir.mkdir()
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=justverify.local','-days','1','-keyout',str(tlsdir/'key.pem'),'-out',str(tlsdir/'cert.pem')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    server_tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server_tls.minimum_version=ssl.TLSVersion.TLSv1_2
    server_tls.load_cert_chain(tlsdir/'cert.pem',tlsdir/'key.pem')
    trusted=ssl.create_default_context(cafile=str(tlsdir/'cert.pem'))
    bridge=ElectrumTLS(backend_port=19601,idle_seconds=3)
    servers=[await asyncio.start_server(bridge.handle,host,0,ssl=server_tls) for host in ('127.0.0.1','::1')]
    try:
        for server in servers:
            host,port,*_=server.sockets[0].getsockname()
            reader,writer=await asyncio.open_connection(host,port,ssl=trusted,server_hostname='justverify.local')
            async def call(method,params=[]):
                writer.write(json.dumps({'id':1,'method':method,'params':params}).encode()+b'\n');await writer.drain()
                while True:
                    reply=json.loads(await asyncio.wait_for(reader.readline(),5))
                    if reply.get('id')==1:
                        assert not reply.get('error'),reply.get('error')
                        return reply['result']
            header=await call('blockchain.headers.subscribe')
            assert hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()==cli('getbestblockhash')
            # Genuine ping traffic keeps the connection alive beyond the idle deadline.
            for _ in range(4):
                await asyncio.sleep(1);assert await call('server.ping') is None
            receiver=cli('getnewaddress')
            raw=cli('createrawtransaction','[]',json.dumps({receiver:0.1}))
            funded=cli('fundrawtransaction',raw,'{"fee_rate":2}')
            signed=cli('signrawtransactionwithwallet',funded['hex']);assert signed['complete']
            txid=await call('blockchain.transaction.broadcast',[signed['hex']])
            assert txid in cli('getrawmempool')
            assert await asyncio.wait_for(reader.read(1),5)==b''
            writer.close();await writer.wait_closed()
            reader,writer=await asyncio.open_connection(host,port,ssl=trusted,server_hostname='justverify.local')
            writer.write(b'{"id":2,"method":"server.ping","params":[]}\n');await writer.drain()
            assert json.loads(await asyncio.wait_for(reader.readline(),5))['result'] is None
            writer.close();await writer.wait_closed()
            try:await asyncio.open_connection(host,port,ssl=ssl.create_default_context(),server_hostname='justverify.local')
            except ssl.SSLCertVerificationError:pass
            else:raise AssertionError('untrusted TLS accepted')
        for address in ('::1','fd00::2','fe80::2','::ffff:192.168.1.2'):assert lan_address(address)
        for address in ('2001:4860:4860::8888','198.51.100.2','::ffff:8.8.8.8'):assert not lan_address(address)
        print('PASS actual IPv4/IPv6 TLS headers, signed broadcast into Core, ping persistence, idle closure/reconnect, certificate and LAN boundaries')
    finally:
        for server in servers:server.close();await server.wait_closed()
asyncio.run(main())
