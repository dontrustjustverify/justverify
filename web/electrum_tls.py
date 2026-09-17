#!/usr/bin/env python3
"""LAN-only TLS transport for the fixed local Electrum server; no request logging."""
import asyncio,contextlib,ipaddress,os,pathlib,socket,ssl

NETWORKS=tuple(ipaddress.ip_network(value) for value in ('127.0.0.0/8','10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16','::1/128','fc00::/7','fe80::/10'))
def lan_address(value):
    try:address=ipaddress.ip_address(value)
    except ValueError:return False
    if isinstance(address,ipaddress.IPv6Address) and address.ipv4_mapped:address=address.ipv4_mapped
    return any(address in network for network in NETWORKS)

class ElectrumTLS:
    def __init__(self,backend_port=50001,idle_seconds=600):
        self.connections=set()
        self.backend_port,self.idle_seconds=backend_port,idle_seconds

    async def handle(self,reader,writer):
        peer=writer.get_extra_info('peername');upstream=None;tasks=[]
        try:
            if not peer or not lan_address(peer[0]) or len(self.connections)>=32:return
            self.connections.add(writer)
            backend,upstream=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',self.backend_port,limit=65536),5)
            last_activity=asyncio.get_running_loop().time()
            async def relay(source,destination):
                nonlocal last_activity
                while data:=await source.read(65536):
                    last_activity=asyncio.get_running_loop().time()
                    destination.write(data)
                    await asyncio.wait_for(destination.drain(),15)
            async def idle():
                while True:
                    remaining=self.idle_seconds-(asyncio.get_running_loop().time()-last_activity)
                    if remaining<=0:return
                    await asyncio.sleep(remaining)
            tasks=[asyncio.create_task(relay(reader,upstream)),asyncio.create_task(relay(backend,writer)),asyncio.create_task(idle())]
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
    options=dict(ssl=tls,ssl_handshake_timeout=5,ssl_shutdown_timeout=3,limit=65536,backlog=32)
    servers=[await asyncio.start_server(bridge.handle,'0.0.0.0',50002,**options)]
    try:
        # Separate IPv6 socket keeps IPv4 working when IPv6 is disabled.
        servers.append(await asyncio.start_server(bridge.handle,'::',50002,family=socket.AF_INET6,**options))
    except OSError as error:
        import errno
        if error.errno not in (errno.EAFNOSUPPORT,errno.EADDRNOTAVAIL):raise
    try:await asyncio.gather(*(server.serve_forever() for server in servers))
    finally:
        for server in servers:server.close()
        await asyncio.gather(*(server.wait_closed() for server in servers))

if __name__=='__main__':asyncio.run(serve())
