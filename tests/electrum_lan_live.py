#!/usr/bin/env python3
"""Installed LAN transports against real regtest, never an operating node."""
import asyncio,contextlib,json,pathlib,socket,ssl,subprocess,sys,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'web'),str(ROOT/'scripts')]
from electrum_tls import ElectrumTLS,listeners
from electrum_qr import lan_endpoint
assert socket.gethostname()=='justverify-reset-test'
assert json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())['network']=='regtest'
context=ssl.create_default_context(cafile='/var/lib/justverify/web/certificate.pem')
async def header(host,port,tls=False):
    reader,writer=await asyncio.wait_for(asyncio.open_connection(host,port,**({'ssl':context,'server_hostname':'justverify.local'} if tls else {})),4)
    try:
        writer.write(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');await writer.drain()
        value=json.loads(await asyncio.wait_for(reader.readline(),4));assert 'result' in value
        return value['result']
    finally:
        writer.close();await writer.wait_closed()
async def ready():
    deadline=time.monotonic()+90
    while True:
        try:
            backend=await header('127.0.0.1',50003)
            assert await header('127.0.0.1',50001)==backend
            assert await header('::1',50002,True)==backend
            return backend
        except (OSError,ValueError,asyncio.TimeoutError):
            if time.monotonic()>deadline:raise
            await asyncio.sleep(.5)
async def main():
    original=await ready()
    for host in ('127.0.0.1','::1'):
        assert await header(host,50001)==original
        assert await header(host,50002,True)==original
    for tls in (False,True):
        endpoint=await asyncio.to_thread(lan_endpoint,True,tls)
        assert endpoint['service_active'] and endpoint['tls']==tls
        assert endpoint['payload']==('justverify.local:50002' if tls else 'justverify.local:50001')
        assert bool(endpoint['certificate_sha256'])==tls
    pid=int(subprocess.check_output(['systemctl','show','justverify-electrum-tls','-p','MainPID','--value']))
    assert pathlib.Path('/proc',str(pid)).stat().st_uid!=0
    sockets=subprocess.check_output(['ss','-lntH'],text=True).splitlines()
    backend=[line.split()[3] for line in sockets if line.split()[3].endswith(':50003')]
    assert backend==['127.0.0.1:50003'],backend
    print('PASS installed nonroot IPv4/IPv6 TCP50001 and TLS50002, loopback-only backend, endpoint selection',flush=True)
    # Missing or malformed optional certificates cannot interrupt the default path.
    with tempfile.TemporaryDirectory(prefix='jv-lan-certificate-') as folder:
        state=pathlib.Path(folder)
        for malformed in (False,True):
            if malformed:(state/'certificate.pem').write_text('invalid certificate')
            servers=await listeners(state,ElectrumTLS(),tcp_port=0,tls_port=0,hosts=('127.0.0.1','::1'))
            try:
                assert len(servers)==2
                for server in servers:
                    host,port,*_=server.sockets[0].getsockname()
                    assert await header(host,port)==original
            finally:
                for server in servers:server.close();await server.wait_closed()
    print('PASS default TCP with absent/malformed TLS identity, both IP families',flush=True)
    address='198.51.100.254/32'
    subprocess.run(['ip','address','add',address,'dev','lo'],check=True)
    try:
        for port,tls in ((50001,False),(50002,True)):
            writer=None
            try:
                reader,writer=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',port,local_addr=('198.51.100.254',0),**({'ssl':context,'server_hostname':'justverify.local'} if tls else {})),3)
                writer.write(b'{"id":1,"method":"server.ping","params":[]}\n');await writer.drain()
                assert await asyncio.wait_for(reader.read(1024),3)==b''
            except (OSError,asyncio.TimeoutError):pass
            finally:
                if writer:writer.close()
    finally:subprocess.run(['ip','address','del',address,'dev','lo'],check=True)
    subprocess.run(['systemctl','stop','justverify-electrs'],check=True)
    assert subprocess.run(['systemctl','is-active','--quiet','justverify-electrum-tls']).returncode!=0
    subprocess.run(['systemctl','start','justverify-electrs','justverify-electrum-tls'],check=True)
    await ready()
    assert await header('127.0.0.1',50001)==original
    assert await header('::1',50002,True)==original
    from backup_service import health
    result=await asyncio.to_thread(health)
    assert result['electrs_height']==original['height']
    print('PASS WAN source refusal on both ports, service stop/start propagation, TCP backup health with real Core hash',flush=True)
asyncio.run(main())
