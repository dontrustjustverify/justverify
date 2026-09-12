"""Test-only HTTP over a real Tor SOCKS circuit; no credentials or addresses logged."""
import http.client,json,re,socket

def request(host,port,path,body,authorization=None):
 assert re.fullmatch(r'[a-z2-7]{56}\.onion',host)
 stream=socket.create_connection(('127.0.0.1',port),timeout=30)
 def read(count):
  value=b''
  while len(value)<count:
   part=stream.recv(count-len(value))
   if not part:raise OSError('SOCKS connection closed')
   value+=part
  return value
 try:
  stream.sendall(b'\x05\x01\x00');assert read(2)==b'\x05\x00'
  name=host.encode('ascii');stream.sendall(b'\x05\x01\x00\x03'+bytes([len(name)])+name+(8332).to_bytes(2,'big'))
  reply=read(4)
  if reply[:2]!=b'\x05\x00':raise OSError('Tor circuit unavailable')
  if reply[3]==1:read(4)
  elif reply[3]==4:read(16)
  elif reply[3]==3:read(read(1)[0])
  else:raise OSError('Invalid SOCKS response')
  read(2)
  connection=http.client.HTTPConnection(host,8332,timeout=30);connection.sock=stream
  headers={'Content-Type':'application/json'}
  if authorization:headers['Authorization']=authorization
  connection.request('POST',path,json.dumps(body),headers)
  response=connection.getresponse();raw=response.read(4*1024*1024+1);assert len(raw)<=4*1024*1024
  return response.status,json.loads(raw) if response.getheader('Content-Type','').startswith('application/json') else None
 finally:stream.close()
