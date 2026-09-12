#!/usr/bin/env python3
"""Real regtest historical blocks, enforced upload cap, and actual electrs P2P.
setmocktime controls only the isolated Core clock while it mines real blocks.
No RPC or indexer responses are replaced.
"""
import argparse,hashlib,json,os,pathlib,socket,subprocess,tempfile,time
p=argparse.ArgumentParser();p.add_argument('--core-bin',type=pathlib.Path,required=True);p.add_argument('--electrs-bin',type=pathlib.Path,required=True);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
os.umask(0o077);state=pathlib.Path(tempfile.mkdtemp(prefix='jv-historical-index-'));data=state/'core';data.mkdir();children=[]
def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
rpcport,p2pport,backend,eport,metrics=[port() for _ in range(5)]
def cli(method,*params):
 result=subprocess.run([str(a.core_bin/'bitcoin-cli'),f'-datadir={data}','-regtest',f'-rpcport={rpcport}',method,*[v if isinstance(v,str) else json.dumps(v) for v in params]],capture_output=True,text=True,timeout=15)
 if result.returncode:raise RuntimeError(method+' RPC failed')
 try:return json.loads(result.stdout)
 except ValueError:return result.stdout.strip()
def wait(predicate,seconds=45):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  try:
   value=predicate()
   if value:return value
  except (OSError,ValueError,RuntimeError):pass
  time.sleep(.1)
 raise RuntimeError('historical indexing predicate timeout')
def start_electrs(target,folder):
 child=subprocess.Popen([str(a.electrs_bin),'--skip-default-conf-files','--network=regtest',f'--daemon-dir={data}',f'--daemon-rpc-addr=127.0.0.1:{rpcport}',f'--daemon-p2p-addr=127.0.0.1:{target}',f'--db-dir={state/folder}',f'--electrum-rpc-addr=127.0.0.1:{eport}',f'--monitoring-addr=127.0.0.1:{metrics}'],stdout=open(state/(folder+'.log'),'ab'),stderr=subprocess.STDOUT);children.append(child);return child
def stop(child):
 if child.poll() is None:child.terminate();child.wait(timeout=20)
def header():
 with socket.create_connection(('127.0.0.1',eport),1) as s:
  s.settimeout(2);s.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');v=json.loads(s.makefile('rb').readline())
  if v.get('error'):raise RuntimeError('Electrum not ready')
  return v['result']
try:
 core=subprocess.Popen([str(a.core_bin/'bitcoind'),f'-datadir={data}','-regtest','-server=1','-disablewallet=1','-listen=1','-listenonion=0',f'-bind=127.0.0.1:{p2pport}',f'-whitebind=download,noban@127.0.0.1:{backend}',f'-rpcport={rpcport}','-connect=0','-dnsseed=0','-maxmempool=64','-dbcache=32','-maxuploadtarget=1','-debug=net'],stdout=open(state/'core.log','ab'),stderr=subprocess.STDOUT);children.append(core);wait(lambda:cli('getblockchaininfo'))
 cli('setmocktime',int(time.time())-14*86400);cli('generatetodescriptor',64,'raw(51)');cli('setmocktime',0);cli('generatetodescriptor',1,'raw(51)')
 chain=cli('getblockchaininfo');assert not chain['initialblockdownload'] and chain['blocks']==65
 old=cli('getblockheader',cli('getblockhash',1));assert old['time']<time.time()-7*86400
 target=cli('getnettotals')['uploadtarget'];assert target['target']==1048576 and target['serve_historical_blocks'] is False
 plain=start_electrs(p2pport,'unprivileged-index')
 wait(lambda:'historical block serving limit reached' in (data/'regtest/debug.log').read_text())
 stop(plain)
 # Fresh index, same real chain and unchanged enforced upload cap.
 trusted=start_electrs(backend,'download-index')
 wait(lambda:header()['height']==65)
 h=header();raw=bytes.fromhex(h['hex']);assert hashlib.sha256(hashlib.sha256(raw).digest()).digest()[::-1].hex()==chain['bestblockhash']
 peer=next(v for v in cli('getpeerinfo') if v.get('addrbind','').endswith(':'+str(backend)))
 assert {'download','noban'}<=set(peer['permissions']) and not {'forcerelay','mempool'}&set(peer['permissions'])
 assert cli('getnettotals')['uploadtarget']['serve_historical_blocks'] is False
 report={'status':'PASS','core':cli('getnetworkinfo')['subversion'],'network':'regtest','electrs':'0.11.1','height':65,'tip':chain['bestblockhash'],'old_block_time':old['time'],'upload_target_bytes':1048576,'unprivileged_historical_download':'EXPECTED_REFUSAL: actual Core log','dedicated_backend_indexing':'PASS: fresh electrs index/header equality','backend_permissions':peer['permissions'],'private_state':str(state)}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='private_state'}),flush=True)
finally:
 for child in reversed(children):stop(child)
