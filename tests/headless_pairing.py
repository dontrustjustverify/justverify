#!/usr/bin/env python3
"""Real TLS ownership proof and replay rejection, without printing any credential."""
import hashlib,http.client,http.server,importlib.util,json,os,pathlib,secrets,shutil,socket,ssl,subprocess,threading,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
identity=module('identity',ROOT/'scripts/web_identity.py');pairing=module('pairing',ROOT/'scripts/verify_pairing.py')
work=ROOT/'.state'/('pairing-'+str(os.getpid()));work.mkdir(mode=0o700,parents=True)
owner=work/'owner.json';token=secrets.token_urlsafe(32);owner.write_text(json.dumps({'format':'justverify-owner-v1','setup_token':token}));owner.chmod(0o600)
state=work/'device';incoming=work/'boot-owner.json';shutil.copyfile(owner,incoming)
identity.ensure_identity(state,incoming);assert not incoming.exists()
assert (state/'setup-token').read_text().strip()==token
before=(state/'certificate.pem').read_bytes();identity.ensure_identity(state);assert (state/'certificate.pem').read_bytes()==before
# An interrupted unclaimed key/cert generation is repairable and does not change the owner token.
partial=work/'partial';partial.mkdir(mode=0o700);shutil.copyfile(state/'private-key.pem',partial/'private-key.pem');identity.ensure_identity(partial)
ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(partial/'certificate.pem',partial/'private-key.pem')
with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
log=(work/'server.log').open('wb')
process=subprocess.Popen([str(ROOT/'.cache/tools-venv/bin/python'),'web/server.py','--state',str(state),'--binary',str(ROOT/'target/debug/justverify'),'--socket',str(work/'unused.sock'),'--origin',f'https://127.0.0.1:{port}','--port',str(port)],cwd=ROOT,stdout=log,stderr=log)
spoof=None
try:
 end=time.monotonic()+15
 while True:
  try:der=pairing.verify('127.0.0.1',port,owner);break
  except OSError:
   assert process.poll() is None
   if time.monotonic()>end:raise
   time.sleep(.1)
 assert der==ssl.PEM_cert_to_DER_cert(before.decode())
 context=ssl.create_default_context(cafile=str(state/'certificate.pem'))
 connection=http.client.HTTPSConnection('127.0.0.1',port,context=context)
 connection.request('GET','/pairing-proof');proof=connection.getresponse().read();connection.close()
 wrong=work/'wrong.json';wrong.write_text(json.dumps({'format':'justverify-owner-v1','setup_token':secrets.token_urlsafe(32)}))
 try:pairing.verify('127.0.0.1',port,wrong);raise AssertionError('wrong owner accepted')
 except ValueError:pass
 class Relay(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
   assert self.path=='/pairing-proof' and 'Authorization' not in self.headers and 'Cookie' not in self.headers
   self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(proof)
  def log_message(self,*args):pass
 spoof=http.server.HTTPServer(('127.0.0.1',0),Relay)
 tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(partial/'certificate.pem',partial/'private-key.pem');spoof.socket=tls.wrap_socket(spoof.socket,server_side=True)
 thread=threading.Thread(target=spoof.serve_forever,daemon=True);thread.start()
 try:pairing.verify('127.0.0.1',spoof.server_port,owner);raise AssertionError('proof replay across TLS identity accepted')
 except ValueError:pass
 # Only after successful certificate authentication is an ownership secret submitted over verified TLS.
 connection=http.client.HTTPSConnection('127.0.0.1',port,context=context)
 connection.request('POST','/login',json.dumps({'setup_token':token,'password':secrets.token_urlsafe(24)}),{'Content-Type':'application/json','Origin':f'https://127.0.0.1:{port}'})
 response=connection.getresponse();assert response.status==200;response.read();connection.close();assert not (state/'setup-token').exists()
 try:pairing.verify('127.0.0.1',port,owner);raise AssertionError('claimed device still exposes pairing proof')
 except ValueError:pass
 identity.ensure_identity(state);assert (state/'certificate.pem').read_bytes()==before
 # A claimed identity must never silently rotate during recovery.
 damaged=state/'certificate.pem';saved=damaged.read_bytes();damaged.unlink()
 try:identity.ensure_identity(state);raise AssertionError('claimed identity rotated')
 except ValueError:pass
 damaged.write_bytes(saved)
 assert token.encode() not in (work/'server.log').read_bytes()
 print(json.dumps({'status':'PASS','checks':['per-device owner file consumed','valid TLS pair generation and idempotent rerun','unclaimed partial identity repaired','headless certificate proof matches live TLS peer','wrong owner secret rejected','valid proof replayed through different TLS certificate rejected','ownership claimed over verified TLS','pairing proof disabled after claim','claimed identity refuses silent rotation','ownership secret absent from logs']},indent=2))
finally:
 if spoof:spoof.shutdown();spoof.server_close()
 process.terminate();process.wait(timeout=5);log.close()
