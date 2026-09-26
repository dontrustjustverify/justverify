#!/usr/bin/env python3
"""Real bounded Electrum readiness checks on a fresh isolated regtest."""
import argparse,contextlib,json,pathlib,signal,socket,subprocess,sys,tempfile,time
p=argparse.ArgumentParser();p.add_argument('--core',type=pathlib.Path,required=True);p.add_argument('--electrs',type=pathlib.Path,required=True);a=p.parse_args()
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from mempool_service import electrs_status, _probes

def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
rpc,p2p,electrum,metrics=[port() for _ in range(4)]
processes=[];paused=False
with tempfile.TemporaryDirectory(prefix='jv-electrum-connection-',dir='/var/tmp') as temporary:
 root=pathlib.Path(temporary);(root/'core').mkdir()
 def start(command):
  process=subprocess.Popen(list(map(str,command)),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(process);return process
 def cli(method,*values):
  result=subprocess.run([str(a.core/'bitcoin-cli'),'-regtest','-datadir='+str(root/'core'),'-rpcport='+str(rpc),method,*map(str,values)],capture_output=True,text=True,timeout=5)
  if result.returncode:raise RuntimeError('Core RPC not ready')
  try:return json.loads(result.stdout)
  except ValueError:return result.stdout.strip()
 def wait(check):
  end=time.monotonic()+45
  while time.monotonic()<end:
   try:
    value=check()
    if value:return value
   except (OSError,ValueError,RuntimeError):pass
   time.sleep(.2)
  raise AssertionError('real readiness checkpoint not reached')
 try:
  core=start([a.core/'bitcoind','-regtest','-server','-datadir='+str(root/'core'),'-rpcport='+str(rpc),'-port='+str(p2p),'-bind=127.0.0.1','-connect=0','-dnsseed=0'])
  wait(lambda:cli('getblockchaininfo'))
  descriptor=cli('getdescriptorinfo','raw(51)')['descriptor'];cli('generatetodescriptor',2,descriptor)
  index=start([a.electrs,'--skip-default-conf-files','--network=regtest','--daemon-dir='+str(root/'core'),'--db-dir='+str(root/'index'),'--daemon-rpc-addr=127.0.0.1:'+str(rpc),'--daemon-p2p-addr=127.0.0.1:'+str(p2p),'--electrum-rpc-addr=127.0.0.1:'+str(electrum),'--monitoring-addr=127.0.0.1:'+str(metrics)])
  wait(lambda:electrs_status(electrum)['ready'])
  value=electrs_status(electrum);assert value['height']==2 and value['tip']==cli('getbestblockhash')
  before_fds=len(list(pathlib.Path('/proc',str(index.pid),'fd').iterdir()));connection=_probes[electrum].sock
  index.send_signal(signal.SIGSTOP);paused=True;started=time.monotonic()
  try:electrs_status(electrum)
  except OSError:pass
  else:raise AssertionError('paused indexer unexpectedly answered')
  assert 2.8<=time.monotonic()-started<4.5
  pending=_probes[electrum].pending;sequence=_probes[electrum].sequence
  for _ in range(10):
   try:electrs_status(electrum)
   except TimeoutError:pass
   else:raise AssertionError('paused indexer unexpectedly answered')
   assert _probes[electrum].sock is connection and _probes[electrum].pending is pending
   assert _probes[electrum].sequence==sequence
  assert len(list(pathlib.Path('/proc',str(index.pid),'fd').iterdir()))==before_fds
  index.send_signal(signal.SIGCONT);paused=False
  wait(lambda:electrs_status(electrum)['ready'])
  print(json.dumps({'status':'PASS','checks':['real header and ping readiness match Core','paused Electrs is bounded by three-second deadline','33 second pause retains one socket and one pending request pair without FD growth','recovery after SIGCONT']}))
 finally:
  if paused:index.send_signal(signal.SIGCONT)
  for process in reversed(processes):
   if process.poll() is None:
    process.terminate()
    try:process.wait(timeout=30)
    except subprocess.TimeoutExpired:process.kill();process.wait()
