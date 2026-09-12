#!/usr/bin/env python3
"""Check an explicitly trusted development signing key, signature and exact file bytes."""
import argparse,hashlib,json,pathlib,re,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--directory',type=pathlib.Path,required=True);p.add_argument('--release',required=True);p.add_argument('--public-key',type=pathlib.Path,required=True);p.add_argument('--fingerprint',required=True);a=p.parse_args()
assert re.fullmatch(r'[A-Za-z0-9.-]+',a.release) and re.fullmatch(r'[A-F0-9]{40}',a.fingerprint)
sums=a.directory/f'justverify-{a.release}-SHA256SUMS';signature=sums.with_suffix(sums.suffix+'.asc')
with tempfile.TemporaryDirectory(prefix='jv-signature-') as temporary:
 home=pathlib.Path(temporary);keyring=home/'trusted.gpg'
 subprocess.run(['gpg','--batch','--homedir',str(home),'--dearmor','--output',str(keyring),str(a.public_key)],check=True,capture_output=True)
 checked=subprocess.run(['gpgv','--homedir',str(home),'--keyring',str(keyring),'--status-fd','1',str(signature),str(sums)],capture_output=True,text=True)
 assert checked.returncode==0,'signature rejected'
 fingerprints=[line.split()[2] for line in checked.stdout.splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
 assert fingerprints==[a.fingerprint],'signature not from explicitly selected trust fingerprint'
files=[]
for line in sums.read_text().splitlines():
 match=re.fullmatch(r'([a-f0-9]{64})  ([A-Za-z0-9_.-]+)',line);assert match,'unsafe checksum record'
 digest,name=match.groups();path=a.directory/name
 assert path.is_file() and not path.is_symlink()
 with path.open('rb') as file:assert hashlib.file_digest(file,'sha256').hexdigest()==digest,'checksum mismatch: '+name
 files.append(name)
assert len(files)==len(set(files)) and len(files)>=3
print(json.dumps({'status':'PASS','release':a.release,'fingerprint':a.fingerprint,'files':files,'scope':'signature and bytes only; not hardware acceptance or public identity trust'}))
