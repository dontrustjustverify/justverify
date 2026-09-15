#!/usr/bin/env python3
"""Real Core regtest responses, with delayed coinbase reads and a paused Core process."""
import argparse,base64,hashlib,http.client,http.server,json,os,pathlib,signal,socket,subprocess,tempfile,threading,time
R=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--core',type=pathlib.Path,default=R/'.cache/core/31.1/arm64-apple-darwin/bitcoin-31.1/bin');p.add_argument('--binary',type=pathlib.Path,default=R/'target/debug/justverify');a=p.parse_args()
def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
with tempfile.TemporaryDirectory(prefix='jv-collector-') as tmp:
 d=pathlib.Path(tmp);d.chmod(0o700);rpcport=port();core=manager=None;hold=threading.Event();entered=threading.Event();release=threading.Event();paused=False
 class Proxy(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_POST(self):
   body=self.rfile.read(int(self.headers['Content-Length']));request=json.loads(body)
   if request['method'] in ('getblock','getrawtransaction') and hold.is_set():entered.set();release.wait(9)
   c=http.client.HTTPConnection('127.0.0.1',rpcport,timeout=15)
   try:
    c.request('POST',self.path,body,{'Authorization':self.headers['Authorization']});r=c.getresponse();raw=r.read()
    self.send_response(r.status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
   except (OSError,http.client.HTTPException):self.close_connection=True
   finally:c.close()
 proxy=http.server.ThreadingHTTPServer(('127.0.0.1',0),Proxy);threading.Thread(target=proxy.serve_forever,daemon=True).start()
 def cli(*args):return subprocess.check_output([str(a.core/'bitcoin-cli'),'-regtest',f'-datadir={d}',f'-rpcport={rpcport}','-rpcwait',*map(str,args)],text=True).strip()
 def snap():
  with socket.socket(socket.AF_UNIX) as s:
   s.settimeout(1);s.connect(str(d/'manager.sock'));s.sendall(b'snapshot\n');raw=b''
   while b:=s.recv(65536):raw+=b
   return json.loads(raw)
 def wait(predicate,seconds=20):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   try:
    s=snap()
    if predicate(s):return s
   except (OSError,KeyError,TypeError,IndexError):pass
   time.sleep(.1)
  raise AssertionError('collector condition timed out')
 def tip_is(tip):return lambda s:s['rpc']['getblockchaininfo']['value']['bestblockhash']==tip and not s['rpc']['getblockchaininfo']['error'] and s['rpc']['recentblocks']['value'][0]['hash']==tip and not s['rpc']['recentblocks']['error']
 try:
  core=subprocess.Popen([str(a.core/'bitcoind'),'-regtest',f'-datadir={d}',f'-rpcport={rpcport}','-listen=0','-networkactive=0','-server=1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  cli('createwallet','delay-test');address=cli('getnewaddress')
  manager=subprocess.Popen([str(a.binary),'daemon','--cookie',str(d/'regtest/.cookie'),'--rpc-port',str(proxy.server_port),'--socket',str(d/'manager.sock')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  genesis=wait(lambda s:s['rpc']['recentblocks']['value'][0].get('size',0)>0)
  assert genesis['rpc']['recentblocks']['value'][0]['size']==len(cli('getblock',cli('getbestblockhash'),0))//2
  cli('generatetoaddress',8,address)
  wait(tip_is(cli('getbestblockhash')))
  hold.set();cli('generatetoaddress',1,address);assert entered.wait(10),'coinbase read was not intercepted'
  t=time.monotonic();cli('generatetoaddress',1,address);tip=cli('getbestblockhash');s=wait(tip_is(tip),6);latency=round(time.monotonic()-t,3)
  assert not release.is_set() and s['rpc']['getnetworkinfo']['error'] is None
  assert time.time()-s['rpc']['getnetworkinfo']['updated']<6
  release.set();hold.clear();wait(lambda s:s['rpc']['recentblocks']['value'][0]['miner']['status']!='pending')
  def verify_sizes():
   s=wait(lambda s:len(s['rpc']['recentblocks']['value'])==6 and all(b.get('size',0)>0 for b in s['rpc']['recentblocks']['value']))
   for block in s['rpc']['recentblocks']['value']:
    actual=json.loads(cli('getblock',block['hash'],1))
    assert block['size']==actual['size']==len(cli('getblock',block['hash'],0))//2
   return s
  verify_sizes()
  cli('invalidateblock',tip);cli('generatetoaddress',2,address);newtip=cli('getbestblockhash');s=wait(tip_is(newtip));assert tip not in [b['hash'] for b in s['rpc']['recentblocks']['value']]
  sized=verify_sizes();time.sleep(3);assert [(b['hash'],b['size']) for b in sized['rpc']['recentblocks']['value']]==[(b['hash'],b['size']) for b in snap()['rpc']['recentblocks']['value']]
  core.send_signal(signal.SIGSTOP);paused=True;time.sleep(18)
  s=snap();assert s['rpc']['getblockchaininfo']['error'];assert time.time()-s['rpc']['getblockchaininfo']['updated']>15;assert time.time()-s['host']['updated']<5;assert s['rpc']['getblockchaininfo']['value']['bestblockhash']==newtip
  core.send_signal(signal.SIGCONT);paused=False;s=wait(tip_is(newtip),20)
  assert not s['rpc']['getblockchaininfo']['error']
  print(json.dumps({'status':'PASS','binary_sha256':hashlib.sha256(a.binary.read_bytes()).hexdigest(),'core':cli('-version').splitlines()[0],'network':'isolated regtest','chain_and_headers_seconds_while_coinbase_held':latency,'tip':newtip,'checks':['real forwarded RPC responses only','genesis and all six block sizes match serialized block bytes','block sizes retained across header refresh and keyed by hash after reorg','blocked coinbase read does not block chain/headers/network','hash-linked reorg replacement','Core SIGSTOP retains stale last value while host refreshes','SIGCONT restores real status without manager restart']}))
 finally:
  release.set()
  if paused:core.send_signal(signal.SIGCONT)
  if manager and manager.poll() is None:manager.terminate();manager.wait(timeout=10)
  if core and core.poll() is None:cli('stop');core.wait(timeout=20)
  proxy.shutdown();proxy.server_close()
