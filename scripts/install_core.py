#!/usr/bin/python3 -I
"""Install only the exact catalog-verified ARM Core executable from unprivileged staging."""
import hashlib,json,os,pathlib,re,sys,tempfile,stat
CATALOG=pathlib.Path('/opt/justverify/catalog/releases.json')
CACHE=pathlib.Path('/var/lib/justverify/downloads/core')
DEST=pathlib.Path('/opt/justverify/versions')
def main():
 if os.geteuid()!=0 or len(sys.argv)!=1:raise ValueError('fixed root helper requires no arguments')
 raw=sys.stdin.buffer.read(4097)
 if len(raw)>4096:raise ValueError('oversized request')
 request=json.loads(raw)
 if not isinstance(request,dict) or set(request)!={'version'}:raise ValueError('version identifier only')
 version=request['version']
 if not isinstance(version,str) or not re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?',version):raise ValueError('invalid version')
 release=next((v for v in json.loads(CATALOG.read_text())['releases'] if v['version']==version),None)
 if not release or release['availability']!='OFFICIAL_BINARY_VERIFIED':raise ValueError('release not verified')
 source=CACHE/version/'aarch64-linux-gnu'/('bitcoin-'+version)/'bin/bitcoind'
 # Untrusted staging is read as bytes; no file there is executed with privileges.
 directory=os.open(CACHE,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  parts=source.relative_to(CACHE).parts
  for part in parts[:-1]:
   next_directory=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);os.close(directory);directory=next_directory
  fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
  if not stat.S_ISREG(os.fstat(fd).st_mode):os.close(fd);raise ValueError('regular staged executable required')
  with os.fdopen(fd,'rb') as file:payload=file.read(128*1024*1024+1)
 finally:os.close(directory)
 if len(payload)>128*1024*1024 or hashlib.sha256(payload).hexdigest()!=release['arm64_binary_sha256']:raise ValueError('executable differs from verified official artifact')
 target=DEST/version/('bitcoin-'+version)/'bin/bitcoind'
 current=DEST
 if current.is_symlink():raise ValueError('linked install root refused')
 for part in target.parent.relative_to(DEST).parts:
  current=current/part
  if current.is_symlink():raise ValueError('linked installation directory refused')
  current.mkdir(exist_ok=True)
  current.chmod(0o755)
 if target.exists():
  if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=release['arm64_binary_sha256']:raise ValueError('existing installation requires explicit repair')
  print(json.dumps({'ok':True,'already_present':True}));return
 fd,name=tempfile.mkstemp(prefix='.verified-core-',dir=target.parent)
 try:
  with os.fdopen(fd,'wb') as file:file.write(payload);file.flush();os.fchmod(file.fileno(),0o755);os.fsync(file.fileno())
  os.replace(name,target)
  directory=os.open(target.parent,os.O_RDONLY);os.fsync(directory);os.close(directory)
 finally:
  if os.path.exists(name):os.unlink(name)
 print(json.dumps({'ok':True,'version':version}))
if __name__=='__main__':
 try:main()
 except Exception as error:print(json.dumps({'ok':False,'error':type(error).__name__}));sys.exit(1)
