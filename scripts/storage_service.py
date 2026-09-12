#!/usr/bin/env python3
"""Narrow root storage service. Only authenticated owner-facing callers may use it."""
import json,os,pathlib,pwd,socket,stat,struct,subprocess
from volume_setup import Volumes,probe

def prepare_profile():
 data=pathlib.Path('/srv/justverify/data');state=pathlib.Path('/var/lib/justverify-storage')
 if data.is_symlink() or not os.path.ismount(data):raise ValueError('provisioned volume is not mounted')
 marker=data/'justverify-volume.json';metadata=marker.lstat()
 if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=0 or metadata.st_mode&0o022:raise ValueError('untrusted volume marker')
 volume=json.loads(marker.read_text())
 uuid=subprocess.run(['/usr/bin/findmnt','-n','-o','UUID','--target',str(data)],check=True,capture_output=True,text=True,timeout=10).stdout.strip()
 if not uuid or volume.get('uuid')!=uuid or volume.get('layout')!='versioned-instances':raise ValueError('provisioned volume mismatch')
 records=[json.loads(path.read_text()) for path in state.glob('*.json')]
 committed=any(p.get('uuid')==uuid and p.get('mount')==str(data) and p.get('phase')=='committed' for p in records)
 if not committed and pathlib.Path('/etc/justverify-factory.json').exists():
  factory=json.loads(subprocess.run(['/usr/bin/python3','/opt/justverify/scripts/factory_volume.py','--verify'],check=True,capture_output=True,text=True,timeout=30).stdout)
  committed=factory.get('uuid')==uuid and factory.get('mount')==str(data)
 if not committed:raise ValueError('committed volume record required')
 if any(p.get('phase') not in ('prepared','committed') for p in records):raise ValueError('finish volume recovery first')
 subprocess.run(['/usr/bin/systemctl','daemon-reload'],check=True,capture_output=True,timeout=30)
 subprocess.run(['/usr/bin/systemctl','start','justverify-versions'],check=True,capture_output=True,timeout=30)
 subprocess.run(['/usr/bin/systemctl','is-active','--quiet','justverify-versions'],check=True,capture_output=True,timeout=10)
 return {'profile_ready':True}

class StorageAPI:
 def __init__(self,volumes,owner=pathlib.Path('/var/lib/justverify/web/admin.json'),profile_starter=None):
  self.volumes=volumes;self.owner=pathlib.Path(owner);self.profile_starter=profile_starter
 def dispatch(self,request):
  if not self.owner.is_file() or self.owner.is_symlink():raise ValueError('owner enrollment required')
  if not isinstance(request,dict):raise ValueError('object required')
  action=request.get('action')
  schemas={'inventory':{'action'},'prepare_profile':{'action'},'preview':{'action','name','identity_digest'},'apply':{'action','id','confirmation'},'recover':{'action','id'}}
  if action not in schemas or set(request)!=schemas[action] or any(not isinstance(v,str) for v in request.values()):raise ValueError('unsupported storage request')
  if action=='prepare_profile':
   if self.profile_starter is None:raise ValueError('profile activation unavailable in this isolated service')
   return self.profile_starter()
  if action=='inventory':
   result=probe.devices.inventory();result['plans']=[]
   if pathlib.Path('/etc/justverify-factory.json').exists():
    result['factory_volume']=json.loads(subprocess.run(['/usr/bin/python3','/opt/justverify/scripts/factory_volume.py','--verify'],check=True,capture_output=True,text=True,timeout=30).stdout)
   for path in sorted(self.volumes.state.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:64]:
    plan=json.loads(path.read_text())
    result['plans'].append({key:plan[key] for key in ('id','phase','created','device','uuid','confirmation','mount','warning')})
   return result
  if action=='preview':plan=self.volumes.preview(request['name'],request['identity_digest'])
  elif action=='apply':plan=self.volumes.apply(request['id'],request['confirmation'])
  else:plan=self.volumes.recover(request['id'])
  # Never disclose host configuration or root-owned journal internals.
  result={key:plan[key] for key in ('id','phase','created','device','uuid','confirmation','mount','warning')}
  if plan['phase']=='committed' and self.profile_starter is not None:
   try:result.update(self.profile_starter())
   except Exception:result.update(profile_ready=False,profile_error='Volume committed; retry profile preparation without formatting.')
  return result

def serve(api,address,allowed_uid):
 address=pathlib.Path(address)
 if address.exists():
  if not stat.S_ISSOCK(address.lstat().st_mode):raise ValueError('socket path is occupied by a non-socket')
  # Refuse replacing a live service endpoint.
  with socket.socket(socket.AF_UNIX) as check:
   try:check.connect(str(address))
   except ConnectionRefusedError:address.unlink()
   else:raise ValueError('storage service already running')
 with socket.socket(socket.AF_UNIX) as server:
  server.bind(str(address));os.chown(address,0,pwd.getpwuid(allowed_uid).pw_gid);os.chmod(address,0o660);server.listen(8)
  while True:
   connection,_=server.accept()
   with connection:
    try:
     _,uid,_=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
     if uid not in (0,allowed_uid):raise ValueError('unauthorized peer')
     connection.settimeout(3);data=bytearray()
     while b'\n' not in data:
      chunk=connection.recv(4097-len(data))
      if not chunk:raise ValueError('incomplete request')
      data.extend(chunk)
      if len(data)>4096:raise ValueError('request too large')
     line,extra=data.split(b'\n',1)
     if extra:raise ValueError('one request per connection required')
     result={'ok':True,'result':api.dispatch(json.loads(line))}
    except (ValueError,UnicodeError):result={'ok':False,'error':'Storage request refused; verify enrollment, device selection and saved plan.'}
    except Exception:result={'ok':False,'error':'Storage operation did not complete. Preserve the plan ID and request recovery; do not repeat formatting.'}
    try:connection.sendall(json.dumps(result).encode()+b'\n')
    except OSError:pass

if __name__=='__main__':
 import sys
 if len(sys.argv)!=1 or os.geteuid()!=0:raise SystemExit('root service takes no arguments')
 serve(StorageAPI(Volumes(),profile_starter=prepare_profile),'/run/justverify-storage/api.sock',pwd.getpwnam('justverify').pw_uid)
