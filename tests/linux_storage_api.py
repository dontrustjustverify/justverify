#!/usr/bin/env python3
"""Real TLS + root Unix API integration; never submits a format request."""
import http.client,json,os,pathlib,pwd,secrets,shutil,socket,ssl,subprocess,sys,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from web_identity import ensure_identity
from storage_service import StorageAPI
from volume_setup import Volumes

def main():
 work=pathlib.Path(tempfile.mkdtemp(prefix='jv-storage-api-',dir='/var/tmp'));state=work/'web';ensure_identity(state)
 account=pwd.getpwnam('justverify')
 for source in (ROOT/'web').glob('*.py'):shutil.copyfile(source,work/source.name)
 for path in [work,*work.rglob('*')]:os.chown(path,account.pw_uid,account.pw_gid)
 token=(state/'setup-token').read_text().strip()
 with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
 origin=f'https://127.0.0.1:{port}';context=ssl.create_default_context(cafile=str(state/'certificate.pem'))
 subprocess.run(['systemctl','stop','justverify-storage'],check=True)
 pathlib.Path('/run/justverify-storage').mkdir(mode=0o755,exist_ok=True)
 worker=subprocess.Popen(['python3','-c',"import sys,pathlib,pwd;sys.path.insert(0,sys.argv[1]);from storage_service import StorageAPI,serve;from volume_setup import Volumes;serve(StorageAPI(Volumes(),pathlib.Path(sys.argv[2])),'/run/justverify-storage/api.sock',pwd.getpwnam('justverify').pw_uid)",str(ROOT/'scripts'),str(state/'admin.json')])
 log=(work/'server.log').open('wb')
 process=subprocess.Popen(['runuser','-u','justverify','--','/opt/justverify/venv/bin/python',str(work/'server.py'),'--state',str(state),'--binary','/opt/justverify/bin/justverify','--socket','/run/justverify/manager.sock','--origin',origin,'--port',str(port)],stdout=log,stderr=log)
 def request(path,body,headers=None):
  connection=http.client.HTTPSConnection('127.0.0.1',port,context=context,timeout=10)
  connection.request('POST',path,json.dumps(body),{'Content-Type':'application/json','Origin':origin,**(headers or {})})
  response=connection.getresponse();result=(response.status,dict(response.getheaders()),response.read());connection.close();return result
 try:
  end=time.monotonic()+15
  while True:
   try:status,_,_=request('/storage',{'action':'inventory'});break
   except OSError:
    assert process.poll() is None
    if time.monotonic()>end:raise
    time.sleep(.1)
  assert status==401
  status,headers,body=request('/login',{'setup_token':token,'password':secrets.token_urlsafe(24)});assert status==200
  credentials={'Cookie':headers['Set-Cookie'].split(';')[0],'X-CSRF-Token':json.loads(body)['csrf']}
  assert request('/storage',{'action':'inventory'},{'Cookie':credentials['Cookie']})[0]==403
  assert request('/storage',{'action':'inventory'},{**credentials,'Origin':'https://untrusted.invalid'})[0]==403
  assert request('/storage',{'action':'inventory','command':'id'},credentials)[0]==400
  print('PASS real TLS unauthenticated/CSRF/cross-Origin/extra-field requests rejected',flush=True)
  status,_,body=request('/storage',{'action':'inventory'},credentials);assert status==200
  devices=json.loads(body)['result']['devices'];assert any(r['reason']=='SYSTEM_DEVICE' for r in devices)
  root=next(r for r in devices if r['reason']=='SYSTEM_DEVICE')
  assert request('/storage',{'action':'preview','name':root['name'],'identity_digest':root['identity_digest']},credentials)[0]==409
  assert b'fstab_before' not in body
  print('PASS authenticated TLS bridges to actual root inventory; system device preview refused',flush=True)
  refused=subprocess.run(['runuser','-u','nobody','--','python3','-c',"import socket;s=socket.socket(socket.AF_UNIX);s.connect('/run/justverify-storage/api.sock')"],capture_output=True)
  assert refused.returncode!=0
  try:StorageAPI(Volumes(work/'unclaimed-state',work/'unused',work/'fstab'),work/'absent-admin').dispatch({'action':'inventory'})
  except ValueError:pass
  else:raise AssertionError('unclaimed owner accepted')
  import base64
  assert request('/rpc',{'id':1,'method':'getblockchaininfo'})[0]==401
  assert request('/rpc-clients',{'action':'create','label':'test'},{'Cookie':credentials['Cookie']})[0]==403
  status,_,body=request('/rpc-clients',{'action':'create','label':'VM read client'},credentials);assert status==200;client=json.loads(body)
  auth={'Authorization':'Basic '+base64.b64encode((client['id']+':'+client['password']).encode()).decode()}
  status,_,body=request('/rpc',{'jsonrpc':'2.0','id':1,'method':'getblockchaininfo','params':[]},auth);assert status==200 and json.loads(body)['result']['chain']=='regtest'
  assert request('/rpc',{'id':2,'method':'stop','params':[]},auth)[0]==403
  assert request('/rpc',{'id':3,'method':'createwallet','params':['forbidden']},auth)[0]==403
  assert request('/rpc',[{'id':4,'method':'getblockcount'}],auth)[0]==400
  status,_,listed=request('/rpc-clients',{'action':'list'},credentials);assert status==200 and client['password'].encode() not in listed and b'"hash"' not in listed
  assert client['password'] not in (state/'rpc-clients.json').read_text()
  statuses=[request('/rpc',{'id':100+i,'method':'getblockcount'},auth)[0] for i in range(30)]
  assert 200 in statuses and 429 in statuses
  print('PASS per-client RPC request budget enforced against actual Core',flush=True)
  assert request('/rpc-clients',{'action':'revoke','id':client['id']},credentials)[0]==200
  assert request('/rpc',{'id':5,'method':'getblockcount'},auth)[0]==401
  assert client['password'].encode() not in (work/'server.log').read_bytes()
  print('PASS real TLS per-client RPC issue/Core query/administrative denial/revocation; plaintext secret absent from disk and logs',flush=True)
  assert token.encode() not in (work/'server.log').read_bytes()
  print('PASS unrelated Unix user and unclaimed-owner requests refused; owner token absent from logs',flush=True)
 finally:
  process.terminate();process.wait(timeout=10);log.close();worker.terminate();worker.wait(timeout=10)
  subprocess.run(['systemctl','start','justverify-storage'],check=True)
if __name__=='__main__':main()
