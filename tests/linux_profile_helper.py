#!/usr/bin/env python3
"""Exercise real root profile bridge on disposable VM; restore original services/configuration."""
import json,os,pathlib,subprocess,time
assert os.geteuid()==0 and subprocess.check_output(['hostname'],text=True).strip()=='justverify-dev'
ROOT=pathlib.Path('/home/builder/justverify');ETC=pathlib.Path('/etc/justverify');DATA=pathlib.Path('/srv/justverify/data')
UNITS=['justverify-policy','justverify-electrs','justverify-core','justverify-manager']
files=[ETC/name for name in ('bitcoin.conf','electrs.toml','profile.json','torrc')]+[pathlib.Path('/etc/systemd/system')/f'justverify-{name}.service.d/20-profile.conf' for name in ('core','electrs','manager','policy')]
saved={path:path.read_bytes() if path.exists() else None for path in files}
def cmd(*args,**kwargs):return subprocess.run(args,check=True,capture_output=True,text=True,**kwargs)
def system(*args):return cmd('systemctl',*args)
def cli(*args):
 out=cmd('/opt/justverify/core/bin/bitcoin-cli','-datadir='+str(DATA/'core'),'-conf='+str(ETC/'bitcoin.conf'),*args).stdout
 try:return json.loads(out)
 except ValueError:return out.strip()
def rpc():
 profile=json.loads((ETC/'profile.json').read_text());cookie=pathlib.Path(profile['cookie']);data=cookie.parent.parent if profile['network']!='main' else cookie.parent
 return json.loads(cmd('/opt/justverify/core/bin/bitcoin-cli','-datadir='+str(data),'-conf='+str(ETC/'bitcoin.conf'),'getblockchaininfo').stdout)
def wait(f):
 end=time.monotonic()+25
 while time.monotonic()<end:
  try:
   value=f()
   if value:return value
  except (OSError,ValueError,subprocess.CalledProcessError):pass
  time.sleep(.2)
 raise AssertionError('readiness timeout')
def helper(request,okay=True):
 result=subprocess.run(['runuser','-u','justverify','--','sudo','-n','/usr/libexec/justverify-profile'],input=json.dumps(request),capture_output=True,text=True)
 if okay:assert result.returncode==0,result.stdout
 else:assert result.returncode!=0,'unsafe input accepted'
 return result
before=cli('getblockchaininfo')['blocks']
try:
 for request in ({'action':'stop','command':'id'},{'action':'activate','version':'../31.1','network':'regtest'},{'action':'activate','version':'30.0','network':'regtest'},{'action':'activate','version':'22.0','network':'testnet4'}):helper(request,False)
 assert rpc()['blocks']==before
 for version in ('31.1','22.0','31.1'):
  helper({'action':'activate','version':version,'network':'regtest'})
  state=wait(rpc);assert state['chain']=='regtest'
  profile=json.loads((ETC/'profile.json').read_text());assert profile['version']==version
  assert '/instances/regtest/'+version+'/' in profile['cookie']
  assert system('is-active','justverify-core').stdout.strip()=='active'
  wait(lambda: pathlib.Path('/run/justverify-policy/control.sock').exists())
  system('is-active','justverify-electrs','justverify-manager','justverify-policy')
 assert (DATA/'core/regtest/blocks').is_dir()
 print(json.dumps({'status':'PASS','checks':['strict root helper identifiers','unsafe and withdrawn inputs rejected before service stop','actual systemd31.1 to22.0 to31.1 profile switch','version-specific cookie/data/index paths','Core/electrs/manager/policy services restart','original data directory preserved']},indent=2))
finally:
 system('stop',*UNITS)
 for path,content in saved.items():
  if content is None:path.unlink(missing_ok=True)
  else:path.write_bytes(content)
 system('daemon-reload');system('reset-failed',*UNITS);system('start',*UNITS)
 system('is-active','justverify-tor')
 assert wait(rpc)['blocks']==before
 print('PASS original profile and original regtest height restored')
