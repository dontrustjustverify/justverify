#!/usr/bin/env python3
"""Root-owned Unix API: read device facts, queue orderly reboot or poweroff."""
import asyncio, contextlib, ipaddress, json, os, pathlib, pwd, socket, struct, subprocess
SOCKET=pathlib.Path('/run/justverify-device/control.sock')
pending=False

def device_state():
    try: model=pathlib.Path('/proc/device-tree/model').read_text().rstrip('\x00\n')
    except OSError: model=os.uname().machine+' · '+os.uname().sysname
    try: release=json.loads(pathlib.Path('/etc/justverify/os-release.json').read_text())['version']
    except (OSError,ValueError,KeyError): release=None
    data=json.loads(subprocess.run(['/usr/sbin/ip','-j','address','show','scope','global'],check=True,capture_output=True,timeout=5).stdout)
    addresses=[]
    for link in data:
        for item in link.get('addr_info',[]):
            if 'local' not in item: continue
            address=ipaddress.ip_address(item['local'])
            if address.is_private and not address.is_loopback: addresses.append(str(address))
    return {'model':model[:120],'os_version':release,'local_ip':addresses,'uptime_seconds':int(float(pathlib.Path('/proc/uptime').read_text().split()[0])),'hostname':socket.gethostname(),'power_pending':pending}

async def power(operation):
    await asyncio.sleep(4)  # Let HTTP deliver its response before service shutdown.
    process=await asyncio.create_subprocess_exec('/usr/bin/systemctl','--no-block',{'reboot':'reboot','shutdown':'poweroff'}[operation])
    await process.wait()
    global pending
    pending=False

async def request(reader,writer):
    global pending
    try:
        peer=writer.get_extra_info('socket');uid=struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]
        if uid not in (0,pwd.getpwnam('justverify').pw_uid): raise ValueError('Caller refused')
        body=json.loads(await asyncio.wait_for(reader.readline(),3))
        if not isinstance(body,dict) or set(body)!={'action'} or body['action'] not in ('state','reboot','shutdown'): raise ValueError('Unsupported device request')
        if body['action']=='state': result=await asyncio.to_thread(device_state)
        else:
            if not pathlib.Path('/var/lib/justverify/web/admin.json').is_file(): raise ValueError('Owner enrollment required')
            if pending: raise ValueError('Power operation already queued')
            pending=True;asyncio.create_task(power(body['action']));result={'queued':body['action'],'delay_seconds':4}
        writer.write(json.dumps({'ok':True,'result':result}).encode()+b'\n')
    except Exception: writer.write(b'{"ok":false,"error":"Device request refused"}\n')
    finally:
        with contextlib.suppress(OSError): await writer.drain()
        writer.close()

async def main():
    if os.geteuid()!=0:raise SystemExit('Root device service required')
    # RuntimeDirectory is created and owned by systemd; never accept user paths.
    SOCKET.unlink(missing_ok=True)
    server=await asyncio.start_unix_server(request,str(SOCKET),limit=4096)
    os.chown(SOCKET,0,pwd.getpwnam('justverify').pw_gid);SOCKET.chmod(0o660)
    async with server: await server.serve_forever()
if __name__=='__main__':asyncio.run(main())
