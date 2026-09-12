#!/usr/bin/env python3
"""Actual onion HTTP requests via Tor SOCKS, authenticated dashboard + controls."""
import base64,hashlib,json,pathlib,socket,struct,time,urllib.parse,os
HOST=pathlib.Path('/run/justverify-tor/web.hostname').read_text().strip()
PASSWORD='Device-Test-2026!'
def http(path,body=None,cookie='',csrf='',origin=None,host=None):
 s=socket.create_connection(('127.0.0.1',9050),timeout=10);s.settimeout(45)
 s.sendall(b'\x05\x01\x00');assert s.recv(2)==b'\x05\x00'
 encoded=HOST.encode();s.sendall(b'\x05\x01\x00\x03'+bytes([len(encoded)])+encoded+struct.pack('!H',80))
 reply=s.recv(4);assert reply[:2]==b'\x05\x00',reply
 length={1:4,4:16}.get(reply[3]);length=s.recv(1)[0] if reply[3]==3 else length
 data=b''
 while len(data)<length+2:data+=s.recv(length+2-len(data))
 payload=json.dumps(body).encode() if body is not None else b''
 request=f'{"POST" if body is not None else "GET"} {path} HTTP/1.1\r\nHost: {host or HOST}\r\nConnection: close\r\nOrigin: {origin or "http://"+HOST}\r\nContent-Type: application/json\r\nContent-Length: {len(payload)}\r\nCookie: {cookie}\r\nX-CSRF-Token: {csrf}\r\n\r\n'.encode()+payload
 s.sendall(request);raw=b''
 while True:
  chunk=s.recv(65536)
  if not chunk:break
  raw+=chunk
 s.close();header,data=raw.split(b'\r\n\r\n',1);lines=header.decode().split('\r\n');status=int(lines[0].split()[1]);headers={k.lower():v.strip() for k,v in (line.split(':',1) for line in lines[1:])}
 return status,headers,data
for attempt in range(8):
 try:
  status,_,page=http('/');assert status==200 and b'JustVerify' in page;break
 except (OSError,AssertionError):
  if attempt==7:raise
  time.sleep(5)
assert http('/setup',{})[0]==404
assert http('/dashboard')[0]==401
assert http('/',host='evil.invalid')[0]==403
status,headers,data=http('/login',{'password':PASSWORD});assert status==200,(status,data)
cookie=headers['set-cookie'].split(';')[0];assert cookie.startswith('jv_tor_session=');csrf=json.loads(data)['csrf']
assert http('/session',cookie=cookie)[0]==200
status,_,data=http('/dashboard',cookie=cookie,csrf=csrf);assert status==200 and 'rpc' in json.loads(data)
assert http('/device-settings',{'action':'state'},cookie,csrf,origin='http://evil.invalid')[0]==403
status,_,data=http('/device-settings',{'action':'state'},cookie,csrf);assert status==200 and json.loads(data)['remote_web']['running']
assert http('/rpc',{})[0]==404
print(json.dumps({'status':'PASS','path':'actual public Tor SOCKS onion HTTP','checks':['login required','setup denied','Host/Origin rejected','distinct Tor cookie','session resume','real Core dashboard','device settings','no RPC route']}))

if os.environ.get('JV_DISABLE_TOR')=='1':
 status,_,data=http('/device-settings',{'action':'tor_preview','enabled':False},cookie,csrf);assert status==200
 token=json.loads(data)['token']
 status,_,data=http('/device-settings',{'action':'apply','token':token,'password':PASSWORD},cookie,csrf);assert status==200,(status,data)
 assert not json.loads(data)['running']
 time.sleep(1)
 try:
  socket.create_connection(('127.0.0.1',28444),timeout=1).close()
  raise AssertionError('disabled listener remains open')
 except ConnectionRefusedError:pass
 print('PASS: disabling over the same Tor session returns successfully and closes the loopback listener')
