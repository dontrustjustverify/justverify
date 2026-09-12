#!/usr/bin/env python3
"""Profile boundary/reopen test against an already isolated, ready live regtest."""
import argparse,json,os,pathlib,subprocess,time,urllib.request
p=argparse.ArgumentParser();p.add_argument('--fixture',type=pathlib.Path,required=True);p.add_argument('--state',type=pathlib.Path,required=True);p.add_argument('--bundle',type=pathlib.Path,required=True);a=p.parse_args()
assert os.geteuid()!=0 and a.fixture.name.startswith('jv-mempool-test-') and a.state.name.startswith('jv-mempool-profile-') and not a.state.exists()
root=pathlib.Path(__file__).resolve().parents[1]
a.state.mkdir(mode=0o700)
for name in ('data','runtime'):(a.state/name).mkdir(mode=0o700)
profile=json.loads((a.fixture/'profile.json').read_text());assert profile['network']=='regtest'
path=a.state/'profile.json';path.write_text(json.dumps({**profile,'network':'signet'}))
result={'status':'FAIL','network':'isolated regtest','checks':[]}
def wait(fn,seconds=90):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  try:
   value=fn()
   if value:return value
  except (OSError,ValueError,KeyError):pass
  time.sleep(.5)
 raise TimeoutError('Live profile validation')
def status():return json.loads((a.state/'runtime/status.json').read_text())
log=(a.state/'runner.log').open('wb')
runner=subprocess.Popen(['/usr/bin/python3',str(root/'scripts/mempool_service.py'),'--profile',str(path),'--data',str(a.state/'data'),'--runtime',str(a.state/'runtime'),'--bundle',str(a.bundle),'--api-port','19999','--web-port','13006','--electrum-port','19601'],stdout=log,stderr=log)
try:
 wait(lambda:status()['state']=='waiting')
 assert status()['reason']=='AssertionError'
 assert list((a.state/'data').iterdir())==[]
 result['checks'].append('mismatched actual Core chain rejected before SQL/data creation')
 path.write_text(json.dumps(profile))
 wait(lambda:status()['state']=='running')
 old=a.state/'data/regtest-31.1/mysql';assert (old/'mysql').is_dir()
 path.write_text(json.dumps({**profile,'watch_only':True}))
 new=a.state/'data/regtest-31.1-watch-only/mysql'
 wait(lambda:(new/'mysql').is_dir())
 wait(lambda:status()['state']=='running')
 assert (old/'mysql').is_dir() and old.stat().st_ino!=new.stat().st_ino
 def actual_tip():
  with urllib.request.urlopen('http://127.0.0.1:19999/api/v1/blocks/tip/height') as response:return int(response.read())==107
 wait(actual_tip)
 config=json.loads((a.state/'runtime/config.json').read_text())
 assert str(new.parent/'cache')==config['MEMPOOL']['CACHE_DIR']
 result.update(status='PASS',height=107)
 result['checks']+=['valid regtest starts after profile correction','watch-only profile switch closes and reopens a separate SQL store; prior store retained','actual backend tip after profile switch']
finally:
 runner.terminate()
 try:runner.wait(timeout=200)
 except subprocess.TimeoutExpired:runner.kill();runner.wait()
 log.close();(a.state/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
