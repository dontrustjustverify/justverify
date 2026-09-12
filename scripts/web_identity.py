#!/usr/bin/env python3
"""Generate per-device TLS identity and consume an optional private owner provisioning file."""
import argparse,hashlib,hmac,json,os,pathlib,re,secrets,ssl,subprocess,tempfile

def write_private(path,data):
 fd,name=tempfile.mkstemp(prefix='.identity-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as file:file.write(data);file.flush();os.fsync(file.fileno())
  os.replace(name,path)
  folder=os.open(path.parent,os.O_RDONLY);os.fsync(folder);os.close(folder)
 finally:
  if os.path.exists(name):os.unlink(name)

def ensure_identity(state,owner_file=None):
 state=pathlib.Path(state);state.mkdir(parents=True,exist_ok=True);state.chmod(0o700)
 key=state/'private-key.pem';certificate=state/'certificate.pem'
 valid=False
 if key.exists() and certificate.exists():
  try:
   context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(certificate,key);valid=True
  except ssl.SSLError:pass
 if not valid and (state/'admin.json').exists():raise ValueError('claimed TLS identity needs explicit recovery; refusing rotation')
 if not valid:
  # Build a complete pair before replacing either path; a partial prior generation is repaired.
  with tempfile.TemporaryDirectory(prefix='.tls-',dir=state) as work:
   work=pathlib.Path(work)
   subprocess.run(['openssl','req','-x509','-newkey','rsa:3072','-nodes','-days','365','-subj','/CN=justverify.local','-addext','subjectAltName=DNS:justverify.local,DNS:localhost,IP:127.0.0.1','-keyout',str(work/'key'),'-out',str(work/'cert')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   write_private(key,(work/'key').read_bytes());write_private(certificate,(work/'cert').read_bytes())
 context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(certificate,key)
 token=state/'setup-token';admin=state/'admin.json'
 if owner_file is not None and pathlib.Path(owner_file).exists():
  source=pathlib.Path(owner_file)
  if source.is_symlink() or not source.is_file() or source.stat().st_size>2048:raise ValueError('invalid owner provisioning file')
  value=json.loads(source.read_text())
  if set(value)!={'format','setup_token'} or value['format']!='justverify-owner-v1' or not isinstance(value['setup_token'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{43,128}',value['setup_token']):raise ValueError('invalid owner provisioning data')
  if admin.exists():raise ValueError('device already claimed; provisioning cannot replace its owner')
  if token.exists() and not hmac.compare_digest(token.read_text().strip(),value['setup_token']):raise ValueError('existing setup identity differs; owner file not consumed')
  if not token.exists():write_private(token,(value['setup_token']+'\n').encode())
  source.unlink()
 if not admin.exists() and not token.exists():write_private(token,(secrets.token_urlsafe(32)+'\n').encode())
 return hashlib.sha256(ssl.PEM_cert_to_DER_cert(certificate.read_text())).hexdigest()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('state',type=pathlib.Path);parser.add_argument('--owner-file',type=pathlib.Path);args=parser.parse_args()
 ensure_identity(args.state,args.owner_file)
 print('Device identity ready; ownership secrets are not printed to logs.')
