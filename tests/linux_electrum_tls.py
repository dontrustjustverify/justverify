#!/usr/bin/env python3
"""Installed nonroot TLS unit against the real development electrs, no mock data."""
import asyncio,json,pathlib,ssl,subprocess,time
assert subprocess.check_output(['hostname'],text=True).strip()=='justverify-dev'
certificate=pathlib.Path('/var/lib/justverify/web/certificate.pem')
context=ssl.create_default_context(cafile=str(certificate))
async def header(tls=True,ctx=context):
 reader,writer=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',50002 if tls else 50001,**({'ssl':ctx,'server_hostname':'justverify.local'} if tls else {})),5)
 try:
  writer.write(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');await writer.drain()
  result=json.loads(await asyncio.wait_for(reader.readline(),5));assert 'result' in result
  return result['result']
 finally:writer.close();await writer.wait_closed()
async def ready():
 deadline=time.monotonic()+30
 while True:
  try:return await header()
  except (OSError,ValueError,asyncio.TimeoutError):
   if time.monotonic()>deadline:raise
   await asyncio.sleep(.2)
async def main():
 original=await header(False);assert await ready()==original
 pid=int(subprocess.check_output(['systemctl','show','justverify-electrum-tls','-p','MainPID','--value']).strip())
 assert pid>0
 uid=pathlib.Path('/proc/'+str(pid)).stat().st_uid
 assert uid!=0
 try:await header(ctx=ssl.create_default_context())
 except ssl.SSLCertVerificationError:pass
 else:raise AssertionError('untrusted certificate accepted')
 print('PASS installed nonroot Electrum TLS: trusted certificate and real header equality; untrusted certificate rejected',flush=True)
 reader,writer=await asyncio.open_connection('127.0.0.1',50002)
 writer.write(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');await writer.drain()
 try:
  try:assert await asyncio.wait_for(reader.read(1024),7)==b''
  except ConnectionResetError:pass
 finally:writer.close()
 print('PASS plaintext Electrum request cannot bypass TLS',flush=True)
 try:
  subprocess.run(['systemctl','stop','justverify-electrs'],check=True)
  assert subprocess.run(['systemctl','is-active','--quiet','justverify-electrum-tls']).returncode!=0
  subprocess.run(['systemctl','start','justverify-electrs'],check=True)
  assert await ready()==original
  subprocess.run(['systemctl','restart','justverify-electrum-tls'],check=True)
  assert await ready()==original
 finally:subprocess.run(['systemctl','start','justverify-electrs','justverify-electrum-tls'],check=True)
 print('PASS actual electrs stop/start propagates to TLS service; TLS restart preserves certificate and indexed header',flush=True)
 # A temporary documentation-range address on loopback tests the WAN refusal.
 address='198.51.100.254/32'
 interfaces=json.loads(subprocess.check_output(['ip','-j','address','show','dev','lo']))
 assert not any(a['local']=='198.51.100.254' for i in interfaces for a in i['addr_info'])
 subprocess.run(['ip','address','add',address,'dev','lo'],check=True)
 try:
  try:
   reader,writer=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',50002,ssl=context,server_hostname='justverify.local',local_addr=('198.51.100.254',0)),3)
  except (OSError,asyncio.TimeoutError):pass
  else:
   try:
    writer.write(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');await writer.drain()
    assert await asyncio.wait_for(reader.read(1024),3)==b''
   except (ConnectionError,asyncio.TimeoutError):pass
   finally:writer.close()
 finally:subprocess.run(['ip','address','del',address,'dev','lo'],check=True)
 assert await header()==original
 print('PASS actual non-LAN source refused; temporary address removed and normal TLS still works',flush=True)
asyncio.run(main())
