#!/usr/bin/env python3
"""Actual GPG and production guarded restore on the registered disposable VM volume."""
import base64,hashlib,http.client,json,os,pathlib,secrets,shutil,signal,socket,ssl,subprocess,sys,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from backup_bundle import production_bundle
from backup_service import BackupAPI,quiesce,resume,health
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
profile=json.loads(pathlib.Path('/etc/justverify/profile.json').read_bytes());assert profile['network']=='regtest' and '/instances/regtest/' in profile['managed_config']
state=pathlib.Path('/var/lib/justverify-backup');destination=pathlib.Path('/boot/firmware/justverify-backup.jvb');private=pathlib.Path(tempfile.mkdtemp(prefix='jv-backup-production-',dir='/var/tmp'));private.chmod(0o700)
owner=pathlib.Path('/var/lib/justverify/web/admin.json');owner_before=owner.read_bytes();passphrase=secrets.token_urlsafe(28);password=secrets.token_urlsafe(24)
for path in (state,destination):
 if path.exists():shutil.move(str(path),str(private/path.name))
state.mkdir(mode=0o700)
node=__import__('pwd').getpwnam('justverify')
def write_owner(value):
 owner.write_bytes(value);owner.chmod(0o600);os.chown(owner,node.pw_uid,node.pw_gid)
def policy(request):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(90);s.connect('/run/justverify-policy/control.sock');s.sendall((json.dumps(request)+'\n').encode());out=b''
  while chunk:=s.recv(65536):out+=chunk
 v=json.loads(out);assert v['ok'],v;return v['result']
def change(value):
 old=policy({'method':'state'})['requested'];review=policy({'method':'preview','values':{**old,'maxmempool':str(value)}});assert policy({'method':'apply','token':review['token']})['phase']=='committed'
def rpc(method):
 c=http.client.HTTPConnection('127.0.0.1',profile['rpc_port'],timeout=5);c.request('POST','/',json.dumps({'id':1,'method':method,'params':[]}),{'Authorization':'Basic '+base64.b64encode(pathlib.Path(profile['cookie']).read_bytes().strip()).decode()});v=json.loads(c.getresponse().read());c.close();assert not v.get('error');return v['result']
class RemoteAPI:
 def dispatch(self,request):
  with socket.socket(socket.AF_UNIX) as client:
   client.settimeout(180);client.connect('/run/justverify-backup/control.sock');client.sendall((json.dumps(request)+'\n').encode());data=b''
   while chunk:=client.recv(65536):data+=chunk
  result=json.loads(data)
  if not result.get('ok'):raise ValueError(result.get('error','backup refused'))
  return result['result']
original_policy=pathlib.Path(profile['managed_config']).read_bytes()
service_started=False
try:
 salt=secrets.token_hex(16);write_owner(json.dumps({'salt':salt,'hash':hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()}).encode())
 change(420)
 bundle=production_bundle();assert bundle.by_key['config/managed.conf'].path==pathlib.Path(profile['managed_config'])
 subprocess.run(['/usr/bin/systemd-run','--quiet','--collect','--unit=justverify-backup-integration','--property=RuntimeDirectory=justverify-backup','--property=RuntimeDirectoryMode=0755','--property=Type=notify','--property=NotifyAccess=main','--property=UMask=0077','--property=NoNewPrivileges=yes','--property=RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6','/usr/bin/python3',str(ROOT/'scripts/backup_service.py')],check=True)
 service_started=True
 deadline=time.monotonic()+15
 while not pathlib.Path('/run/justverify-backup/control.sock').exists():
  if time.monotonic()>deadline:raise TimeoutError('actual backup service startup')
  time.sleep(.1)
 api=RemoteAPI()
 values=bundle.snapshot()
 for key,payload in [('systemd/core-profile.conf',b'[Service]\nUser=root\nExecStart=\nExecStart=/bin/false\n'),('etc/torrc',b'SocksPort 0.0.0.0:9050\n'),('etc/versions.json',b'{"binaries":"/tmp"}'),('config/managed.conf',b'rpcbind=0.0.0.0\n')]:
  altered={**values,key:payload}
  try:bundle._validate_snapshot(altered);raise AssertionError('untrusted backup configuration accepted')
  except ValueError:pass
 print('PASS canonical root drop-in/Tor/version roots and policy injection refused before write',flush=True)
 changed=json.loads(values['etc/node-ready.json']);changed['uuid']='00000000-0000-0000-0000-000000000000'
 try:bundle._validate_snapshot({**values,'etc/node-ready.json':json.dumps(changed).encode()});raise AssertionError('wrong volume accepted')
 except ValueError:pass
 for action in ('restore_preview','create_apply','recover'):
  request={'action':action,'password':'wrong','passphrase':passphrase}
  if action=='create_apply':request['token']='unused'
  if action=='recover':request.pop('passphrase')
  try:api.dispatch(request);raise AssertionError('wrong owner password accepted')
  except ValueError:pass
 plan=api.dispatch({'action':'create_preview'});made=api.dispatch({'action':'create_apply','token':plan['token'],'passphrase':passphrase,'password':password});assert made['exists']
 before=production_bundle().snapshot();assert b'BEGIN PRIVATE KEY' not in destination.read_bytes()
 change(430);assert rpc('getmempoolinfo')['maxmempool']==430000000
 plan=api.dispatch({'action':'restore_preview','passphrase':passphrase,'password':password})
 result=api.dispatch({'action':'restore_apply','token':plan['token'],'passphrase':passphrase,'password':password,'confirmation':'RESTORE DEVICE IDENTITY'})
 assert result['phase']=='committed' and rpc('getmempoolinfo')['maxmempool']==420000000
 assert production_bundle().snapshot()==before
 assert rpc('getblockchaininfo')['blocks']==1
 # Startup failure after file replacement must roll back rather than commit.
 change(430);before_failure=production_bundle().snapshot()
 def reject_health():raise RuntimeError('isolated deliberate health fault')
 faulty=BackupAPI(production_bundle,health_callback=reject_health)
 plan=faulty.dispatch({'action':'restore_preview','passphrase':passphrase,'password':password})
 try:faulty.dispatch({'action':'restore_apply','token':plan['token'],'passphrase':passphrase,'password':password,'confirmation':'RESTORE DEVICE IDENTITY'});raise AssertionError('health failure committed')
 except RuntimeError:pass
 assert production_bundle().snapshot()==before_failure
 assert json.loads((state/'restore.json').read_bytes())['phase']=='rolled_back'
 assert rpc('getmempoolinfo')['maxmempool']==430000000
 # Real process termination after all replacement writes but before commit.
 plan=api.dispatch({'action':'restore_preview','passphrase':passphrase,'password':password})
 quiesce()
 child=os.fork()
 if child==0:
  interrupted=production_bundle();apply_values=interrupted._apply_values
  def die_after_replace(values):
   apply_values(values)
   os.kill(os.getpid(),signal.SIGKILL)
  interrupted._apply_values=die_after_replace
  interrupted.restore(passphrase,plan['sha256'])
  os._exit(99)
 _,status=os.waitpid(child,0)
 assert os.WIFSIGNALED(status) and os.WTERMSIG(status)==signal.SIGKILL
 assert json.loads((state/'restore.json').read_bytes())['phase']=='applying'
 subprocess.run(['/usr/bin/systemctl','restart','justverify-backup-integration'],check=True,timeout=120)
 health()
 assert json.loads((state/'restore.json').read_bytes())['phase']=='rolled_back'
 assert production_bundle().snapshot()==before_failure and rpc('getmempoolinfo')['maxmempool']==430000000
 print('PASS actual SIGKILL after restore writes; systemd service startup recovered journal and restored policy430 and original identities with live Core RPC',flush=True)
 print('PASS actual GPG, selected-policy420->430->restore420, original TLS/Tor/auth records preserved, Core/electrs service recovery; injected health failure rolled back430',flush=True)
finally:
 if service_started:subprocess.run(['/usr/bin/systemctl','stop','justverify-backup-integration'],check=True)
 quiesce()
 pathlib.Path(profile['managed_config']).write_bytes(original_policy);os.chown(profile['managed_config'],node.pw_uid,node.pw_gid);os.chmod(profile['managed_config'],0o600)
 write_owner(owner_before)
 if state.exists():shutil.rmtree(state)
 destination.unlink(missing_ok=True)
 for path in (state,destination):
  saved=private/path.name
  if saved.exists():shutil.move(str(saved),str(path))
 resume();health()
 print('PASS original registered fixture policy/owner/backup files restored',flush=True)
