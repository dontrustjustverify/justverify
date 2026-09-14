#!/usr/bin/env python3
"""Actual Core/electrs regtest, delayed forwarded responses, process outage and recovery."""
import argparse, contextlib, hashlib, http.server, json, pathlib, signal, socket, socketserver, subprocess, tempfile, threading, time, urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('--core',type=pathlib.Path,required=True)
parser.add_argument('--electrs',type=pathlib.Path,required=True)
parser.add_argument('--binary',type=pathlib.Path,required=True)
args=parser.parse_args()
def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
rpcport,p2pport,ep,mp=[port() for _ in range(4)]
delay=threading.Event();metrics_delay=threading.Event()
class TCP(socketserver.ThreadingTCPServer):
    allow_reuse_address=True;daemon_threads=True
class Forward(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self.request.settimeout(5);raw=b''
            while raw.count(b'\n')<2:
                chunk=self.request.recv(4096)
                if not chunk:return
                raw+=chunk
            with socket.create_connection(('127.0.0.1',ep),5) as remote:
                remote.sendall(raw);raw=b''
                while raw.count(b'\n')<2:
                    chunk=remote.recv(4096)
                    if not chunk:break
                    raw+=chunk
                if delay.is_set():time.sleep(3)
                self.request.sendall(raw)
        except OSError:pass
class Metrics(http.server.BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        try:
            with urllib.request.urlopen('http://127.0.0.1:'+str(mp)+'/metrics',timeout=2) as r:raw=r.read(262144)
            if metrics_delay.is_set():time.sleep(3)
            self.send_response(200);self.end_headers();self.wfile.write(raw)
        except OSError:self.close_connection=True
tcp=TCP(('127.0.0.1',0),Forward);metrics=http.server.ThreadingHTTPServer(('127.0.0.1',0),Metrics)
for s in (tcp,metrics):threading.Thread(target=s.serve_forever,daemon=True).start()
processes=[];paused=False
with tempfile.TemporaryDirectory(prefix='jv-electrs-status-') as tmp:
    root=pathlib.Path(tmp);root.chmod(0o700);(root/'core').mkdir()
    def start(command,name):
        log=open(root/(name+'.log'),'ab');p=subprocess.Popen(list(map(str,command)),stdout=log,stderr=log);log.close();processes.append(p);return p
    def cli(*values):
        r=subprocess.run([str(args.core/'bitcoin-cli'),'-regtest','-datadir='+str(root/'core'),'-rpcport='+str(rpcport),*map(str,values)],capture_output=True,text=True,timeout=10)
        if r.returncode:raise RuntimeError('Core RPC not ready')
        try:return json.loads(r.stdout)
        except ValueError:return r.stdout.strip()
    def snapshot():
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(1);s.connect(str(root/'manager.sock'));s.sendall(b'snapshot\n');raw=b''
            while chunk:=s.recv(65536):raw+=chunk
            return json.loads(raw)
    def wait(predicate,seconds=45):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            try:
                value=predicate()
                if value:return value
            except (OSError,ValueError,KeyError,TypeError,RuntimeError):pass
            time.sleep(.2)
        with contextlib.suppress(Exception):
            s=snapshot();print(json.dumps({'failure_state':s.get('host',{}).get('electrs'),'core':s['rpc']['getblockchaininfo'],'index_exit':index.poll()}),flush=True)
        raise AssertionError('Expected real service state not observed')
    def state_is(name):
        s=snapshot();return s if s['host']['electrs']['state']==name else None
    def ready():
        s=state_is('READY')
        return s if s and s['host']['electrs']['tip']==cli('getbestblockhash') else None
    core_command=[args.core/'bitcoind','-regtest','-datadir='+str(root/'core'),'-server=1','-connect=0','-dnsseed=0','-bind=127.0.0.1','-port='+str(p2pport),'-rpcport='+str(rpcport),'-dbcache=32']
    index_command=[args.electrs,'--skip-default-conf-files','--network=regtest','--daemon-dir='+str(root/'core'),'--db-dir='+str(root/'index'),'--daemon-rpc-addr=127.0.0.1:'+str(rpcport),'--daemon-p2p-addr=127.0.0.1:'+str(p2pport),'--electrum-rpc-addr=127.0.0.1:'+str(ep),'--monitoring-addr=127.0.0.1:'+str(mp)]
    try:
        core=start(core_command,'core');wait(lambda:cli('getblockchaininfo'))
        cli('createwallet','status-test');address=cli('getnewaddress');cli('generatetoaddress',105,address)
        index=start(index_command,'electrs')
        manager=start([args.binary,'daemon','--cookie',root/'core/regtest/.cookie','--rpc-port',rpcport,'--electrs-port',tcp.server_address[1],'--electrs-metrics-port',metrics.server_port,'--socket',root/'manager.sock'],'manager')
        first=wait(ready);assert first['host']['electrs']['wallet_ready']
        # A READY observation must correspond to an actual wallet query as well.
        script=bytes.fromhex(cli('getaddressinfo',address)['scriptPubKey']);sh=hashlib.sha256(script).digest()[::-1].hex()
        with socket.create_connection(('127.0.0.1',ep),5) as s:
            s.sendall((json.dumps({'id':1,'method':'blockchain.scripthash.get_balance','params':[sh]})+'\n').encode())
            wallet=json.loads(s.makefile('rb').readline())
            assert wallet['result']['confirmed']>0 and wallet.get('error') is None
        delay.set();cli('generatetoaddress',1,address)
        def delayed():
            s=snapshot();e=s['host']['electrs']
            return s if e['height']==106 and e['rpc_error']=='Electrum response delayed' and not e['wallet_ready'] else None
        s=wait(delayed);assert not s['host']['electrs']['height_stale'];assert time.time()-s['host']['updated']<5
        # Both endpoints can fail; retain the old height and its original observation time.
        metrics_delay.set();s=wait(lambda:state_is('STALE'));e=s['host']['electrs'];stamp=e['height_updated']
        assert e['height']==106 and e['height_stale'] and not e['wallet_ready']
        time.sleep(4);assert snapshot()['host']['electrs']['height_updated']==stamp
        delay.clear();metrics_delay.clear();wait(ready)
        index.send_signal(signal.SIGSTOP);paused=True
        s=wait(lambda:state_is('STALE'));assert s['host']['electrs']['height']==106 and s['host']['electrs']['height_stale']
        assert time.time()-s['host']['updated']<5 and time.time()-s['rpc']['getblockchaininfo']['updated']<5
        index.send_signal(signal.SIGCONT);paused=False;wait(ready)
        index.terminate();index.wait(timeout=30)
        s=wait(lambda:state_is('UNAVAILABLE'));assert s['host']['electrs']['height']==106 and not s['host']['electrs']['wallet_ready']
        index=start(index_command,'electrs-restarted');wait(ready)
        # An invalidate-only shorter chain can send no new P2P headers to electrs.
        # It must not stay READY. electrs defaults to keeping its old tip on an empty
        # getheaders response; its explicit regtest recovery option reloads recent blocks.
        cli('invalidateblock',cli('getbestblockhash'))
        def mismatched():
            s=snapshot()
            return s if s['rpc']['getblockchaininfo']['value']['blocks']==105 and not s['host']['electrs']['wallet_ready'] else None
        wait(mismatched)
        index.terminate();index.wait(timeout=30);index=start(index_command+['--reindex-last-blocks=2'],'electrs-shorter-chain')
        s=wait(ready);assert s['host']['electrs']['height']==105
        cli('generatetoaddress',2,address);wait(ready)
        print(json.dumps({'status':'PASS','core':cli('getnetworkinfo')['subversion'],'electrs':subprocess.check_output([str(args.electrs),'--version'],text=True).strip(),'binary_sha256':hashlib.sha256(args.binary.read_bytes()).hexdigest(),'height':107,'tip':cli('getbestblockhash'),'checks':['actual Core/electrs tip and wallet query','3s forwarded Electrum response does not block metrics or host collection','timeout preserves last height/timestamp with stale flag','actual SIGSTOP and SIGCONT','actual process stop/restart and unavailable state','shorter chain mismatch is not READY; explicit regtest reindex-last-blocks=2 recovers height105','new fork grows and tips agree']}))
    finally:
        if paused:index.send_signal(signal.SIGCONT)
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=30)
                except subprocess.TimeoutExpired:p.kill();p.wait()
        tcp.shutdown();metrics.shutdown();tcp.server_close();metrics.server_close()
