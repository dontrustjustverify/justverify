#!/usr/bin/env python3
"""Real Unix API + systemd + Core/electrs, only in the named disposable VM."""
import base64,hashlib,http.client,json,os,pathlib,socket,subprocess,time
assert os.geteuid()==0 and subprocess.check_output(['hostname'],text=True).strip()=='justverify-reset-test'
assert pathlib.Path('/var/tmp/jv-reset-native/data.img').is_file()
STATE=pathlib.Path('/var/lib/justverify/versions')
SOCKET='/run/justverify-versions/control.sock'
def api(method,**values):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
  s.settimeout(330);s.connect(SOCKET);s.sendall(json.dumps({'method':method,**values}).encode()+b'\n')
  b=bytearray()
  while chunk:=s.recv(65536):b.extend(chunk)
  return json.loads(b)
def okay(method,**values):
 value=api(method,**values)
 assert value['ok'],value
 return value['result']
def rpc(method,params=[]):
 profile=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text());cookie=pathlib.Path(profile['cookie']).read_text().strip()
 c=http.client.HTTPConnection('127.0.0.1',profile['rpc_port'],timeout=5)
 try:
  c.request('POST','/',json.dumps({'id':1,'method':method,'params':params}),{'Authorization':'Basic '+base64.b64encode(cookie.encode()).decode()})
  value=json.load(c.getresponse());assert not value.get('error'),value.get('error');return value['result']
 finally:c.close()
def preview(version):return okay('preview',version=version,network='regtest',watch_only=False)
def apply(p):return okay('apply',token=p['token'])
def run_initial():
 assert okay('state')['active'] is None
 assert apply(preview('31.1'))['phase']=='committed'
 d=rpc('getdescriptorinfo',['raw(51)'])['descriptor'];rpc('generatetodescriptor',[7,d]);assert rpc('getblockcount')==7
 old=json.loads((STATE/'active.json').read_text());core=pathlib.Path(old['instance']['core_data']);index=pathlib.Path(old['instance']['electrs_data'])
 # Secrets here are synthetic, retained only inside the disposable VM.
 for path in (core/'auth-fixture',index/'device-fixture'):path.write_text('preserve-fixture')
 p=preview('22.0');assert p['preview']['destructive'];assert not any(str(v).startswith('/srv/') for v in p['preview']['delete_scope'])
 assert not api('apply',token=p['token'],path='/')['ok']
 assert not api('preview',version='22.0',network='regtest',watch_only=False,delete_scope=['/'])['ok']
 assert rpc('getblockcount')==7
 result=apply(p);assert result['phase']=='committed',result
 assert not api('apply',token=p['token'])['ok']
 active=json.loads((STATE/'active.json').read_text());assert active['instance']['core_data']==str(core) and active['instance']['electrs_data']==str(index)
 assert rpc('getblockcount')==0
 assert (core/'auth-fixture').read_text()=='preserve-fixture'
 assert (index/'device-fixture').read_text()=='preserve-fixture'
 assert not api('preview',version='22.0',network='regtest',watch_only=False)['ok']
 assert apply(preview('31.1'))['phase']=='committed'
 assert rpc('getblockcount')==0
 print(json.dumps({'status':'PASS','checks':['native systemd start and registered-volume guard','31.1 to22.0 to31.1 at same data paths, new genesis','client delete-path/list rejected','one-use token replay rejected','same-version refusal','preserved fixtures']}))
if __name__=='__main__':run_initial()
