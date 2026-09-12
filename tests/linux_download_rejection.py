#!/usr/bin/env python3
import hashlib,json,os,pathlib,socket,subprocess,time
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
cache=pathlib.Path('/var/lib/justverify/downloads/core/23.2');sums=cache/'SHA256SUMS';original=sums.read_bytes()
staged=cache/'aarch64-linux-gnu/bitcoin-23.2/bin/bitcoind';installed=pathlib.Path('/opt/justverify/versions/23.2/bitcoin-23.2/bin/bitcoind');digest=hashlib.sha256(installed.read_bytes()).hexdigest()
def api(value):
 with socket.socket(socket.AF_UNIX) as sock:
  sock.settimeout(5);sock.connect('/run/justverify-versions/control.sock');sock.sendall((json.dumps(value)+'\n').encode());out=b''
  while chunk:=sock.recv(65536):out+=chunk
 return json.loads(out)
def finish():
 end=time.monotonic()+40
 while time.monotonic()<end:
  status=api({'method':'state'})['result']['download']
  if status['phase'] in ('complete','failed'):return status
  time.sleep(.2)
 raise AssertionError('download did not finish')
subprocess.run(['systemctl','start','justverify-versions'],check=True)
try:
 end=time.monotonic()+10
 while True:
  try:api({'method':'state'});break
  except OSError:
   if time.monotonic()>end:raise
   time.sleep(.1)
 # Alter signed material, not the verifier or its expectations.
 sums.write_bytes(original+b'\n00  tampered-test\n')
 assert api({'method':'download','version':'23.2'})['ok']
 assert finish()['phase']=='failed'
 assert hashlib.sha256(installed.read_bytes()).hexdigest()==digest
 sums.write_bytes(original)
 # Independently exercise the root installer's hash boundary with invalid bytes.
 saved=staged.with_name('bitcoind.valid-test');staged.rename(saved)
 try:
  staged.write_bytes(b'not a verified executable')
  result=subprocess.run(['runuser','-u','justverify','--','sudo','-n','/usr/libexec/justverify-install-core'],input=json.dumps({'version':'23.2'}),text=True,capture_output=True)
  assert result.returncode!=0
  assert hashlib.sha256(installed.read_bytes()).hexdigest()==digest
 finally:staged.unlink();saved.rename(staged)
 assert api({'method':'download','version':'23.2'})['ok']
 assert finish()['phase']=='complete'
 print(json.dumps({'status':'PASS','checks':['actual GPG rejects modified signed checksum list','failed verification leaves installed binary intact','fixed privileged installer rejects altered executable','restored official files verify and install successfully']},indent=2))
finally:
 sums.write_bytes(original)
 subprocess.run(['systemctl','stop','justverify-versions'],check=True)
