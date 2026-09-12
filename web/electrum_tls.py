#!/usr/bin/env python3
"""LAN-only TLS transport for the fixed local Electrum server; no request logging."""
import asyncio,contextlib,ipaddress,os,pathlib,ssl

NETWORKS=tuple(ipaddress.ip_network(value) for value in ('127.0.0.0/8','10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16'))
def lan_address(value):
    try:address=ipaddress.ip_address(value)
    except ValueError:return False
    return any(address in network for network in NETWORKS)

class ElectrumTLS:
    def __init__(self):
        self.connections=set()

    async def handle(self,reader,writer):
        peer=writer.get_extra_info('peername');upstream=None;tasks=[]
        try:
            if not peer or not lan_address(peer[0]) or len(self.connections)>=32:return
            self.connections.add(writer)
            backend,upstream=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',50001,limit=65536),5)
            async def relay(source,destination):
                while data:=await asyncio.wait_for(source.read(65536),600):
                    destination.write(data)
                    await asyncio.wait_for(destination.drain(),15)
            tasks=[asyncio.create_task(relay(reader,upstream)),asyncio.create_task(relay(backend,writer))]
            await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        except (OSError,asyncio.TimeoutError):pass
        finally:
            for task in tasks:task.cancel()
            if tasks:await asyncio.gather(*tasks,return_exceptions=True)
            self.connections.discard(writer)
            for stream in (upstream,writer):
                if stream is not None:
                    stream.close()
                    with contextlib.suppress(OSError,asyncio.TimeoutError):await asyncio.wait_for(stream.wait_closed(),3)

async def serve():
    if os.geteuid()==0:raise SystemExit('Electrum TLS must run as a non-root user')
    state=pathlib.Path('/var/lib/justverify/web')
    if state.stat().st_mode&0o077 or not (state/'admin.json').is_file():raise SystemExit('Private enrolled identity required')
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(state/'certificate.pem',state/'private-key.pem')
    bridge=ElectrumTLS()
    server=await asyncio.start_server(bridge.handle,'0.0.0.0',50002,ssl=tls,ssl_handshake_timeout=5,ssl_shutdown_timeout=3,limit=65536,backlog=32)
    async with server:await server.serve_forever()

if __name__=='__main__':asyncio.run(serve())
