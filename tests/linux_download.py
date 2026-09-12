#!/usr/bin/env python3
import hashlib,json,os,pathlib,socket,subprocess,time
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
def api(value):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(5);s.connect('/run/justverify-versions/control.sock');s.sendall((json.dumps(value)+'\n').encode());out=b''
  while b:=s.recv(65536):out+=b
 return json.loads(out)
subprocess.run(['systemctl','start','justverify-versions'],check=True)
try:
 end=time.monotonic()+10
 while True:
  try:state=api({'method':'state'});break
  except OSError:
   if time.monotonic()>end:raise
   time.sleep(.1)
 assert not api({'method':'download','version':'30.0'})['ok']
 assert not api({'method':'download','version':'23.2','url':'https://example.invalid/'})['ok']
 before=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())
 assert api({'method':'download','version':'23.2'})['ok']
 assert not api({'method':'download','version':'24.1'})['ok']
 end=time.monotonic()+240
 while time.monotonic()<end:
  # State must remain responsive while the download process runs.
  state=api({'method':'state'});assert state['ok']
  status=state['result']['download']
  if status['phase'] in ('complete','failed'):break
  time.sleep(.5)
 assert status['phase']=='complete',status
 assert json.loads(pathlib.Path('/etc/justverify/profile.json').read_text())==before
 release=next(r for r in state['result']['releases'] if r['version']=='23.2')
 binary=pathlib.Path('/opt/justverify/versions/23.2/bitcoin-23.2/bin/bitcoind')
 assert release['downloaded'] and hashlib.sha256(binary.read_bytes()).hexdigest()==release['arm64_binary_sha256']
 proof=json.loads(pathlib.Path('/var/lib/justverify/downloads/evidence/core-23.2-aarch64-linux-gnu-download.json').read_text())
 assert proof['status']=='SIGNATURE_AND_CHECKSUM_PASS' and proof['signers']
 preview=api({'method':'preview','version':'23.2','network':'regtest'});assert preview['ok'],preview
 print(json.dumps({'status':'PASS','version':'23.2','checks':['official archive download/verification','pinned trusted signer and official checksum','fixed root installer binary hash match','background status stays responsive','concurrent download refused','withdrawn and arbitrary URL rejected','active services unchanged','downloaded binary passes real preflight'],'download_evidence':proof},indent=2))
finally:subprocess.run(['systemctl','stop','justverify-versions'],check=True)
