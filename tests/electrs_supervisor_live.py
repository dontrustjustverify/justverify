#!/usr/bin/env python3
"""Reproduce a real accept-loop FD failure on an isolated index, then recover it."""
import argparse,contextlib,http.client,http.server,json,pathlib,resource,signal,socket,subprocess,sys,tempfile,threading,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from electrs_service import supervise
from mempool_service import ElectrumProbe
p=argparse.ArgumentParser();p.add_argument('--core',type=pathlib.Path);p.add_argument('--electrs',type=pathlib.Path);p.add_argument('--worker',type=pathlib.Path);a=p.parse_args()
if a.worker:
    config=json.loads(a.worker.read_text());resource.setrlimit(resource.RLIMIT_NOFILE,(65536,65536))
    raise SystemExit(supervise(config['command'],config['port'],pathlib.Path(config['status'])))
def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def wait(check,seconds=45):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            value=check()
            if value:return value
        except (OSError,ValueError,KeyError,RuntimeError):pass
        time.sleep(.1)
    raise AssertionError('Real supervisor checkpoint not reached')
processes=[];connections=[];gate=threading.Event();entered=threading.Event()
rpc,p2p,ep,mp=[port() for _ in range(4)]
class CoreProxy(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*_):pass
    def do_POST(self):
        body=self.rfile.read(int(self.headers['Content-Length']));entered.set();gate.wait(90)
        remote=http.client.HTTPConnection('127.0.0.1',rpc,timeout=5)
        try:
            remote.request('POST',self.path,body,{'Authorization':self.headers['Authorization']})
            response=remote.getresponse();body=response.read();self.send_response(response.status)
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        except OSError:self.close_connection=True
        finally:remote.close()
proxy=http.server.ThreadingHTTPServer(('127.0.0.1',0),CoreProxy)
threading.Thread(target=proxy.serve_forever,daemon=True).start()
with tempfile.TemporaryDirectory(prefix='jv-electrs-supervisor-',dir='/var/tmp') as tmp:
    root=pathlib.Path(tmp);(root/'core').mkdir();status=root/'status.json'
    def cli(*values):
        result=subprocess.run([str(a.core/'bitcoin-cli'),'-regtest','-datadir='+str(root/'core'),'-rpcport='+str(rpc),*map(str,values)],capture_output=True,text=True,timeout=5)
        if result.returncode:raise RuntimeError('Core RPC not ready')
        try:return json.loads(result.stdout)
        except ValueError:return result.stdout.strip()
    def start(command,name):
        with open(root/(name+'.log'),'wb') as log:child=subprocess.Popen(list(map(str,command)),stdout=log,stderr=log)
        processes.append(child);return child
    def read():return json.loads(status.read_text())
    try:
        core_command=[a.core/'bitcoind','-regtest','-server','-datadir='+str(root/'core'),'-rpcport='+str(rpc),'-port='+str(p2p),'-bind=127.0.0.1','-connect=0','-dnsseed=0']
        core=start(core_command,'core')
        wait(lambda:cli('getblockchaininfo'));descriptor=cli('getdescriptorinfo','raw(51)')['descriptor'];cli('generatetodescriptor',10,descriptor)
        command=[str(a.electrs),'--skip-default-conf-files','--network=regtest','--daemon-dir='+str(root/'core'),'--db-dir='+str(root/'index'),'--daemon-rpc-addr=127.0.0.1:'+str(proxy.server_port),'--daemon-p2p-addr=127.0.0.1:'+str(p2p),'--electrum-rpc-addr=127.0.0.1:'+str(ep),'--monitoring-addr=127.0.0.1:'+str(mp),'--log-filters=INFO,electrs::db=DEBUG']
        config=root/'worker.json';config.write_text(json.dumps({'command':command,'port':ep,'status':str(status)}))
        worker=start([sys.executable,__file__,'--worker',config],'supervisor-fault')
        wait(lambda:status.exists() and read()['running']);assert entered.wait(15)
        child=read()['pid'];assert resource.prlimit(child,resource.RLIMIT_NOFILE)==(65536,65536)
        # Lower only this disposable process. Leave its event loop waiting on real Core RPC.
        resource.prlimit(child,resource.RLIMIT_NOFILE,(8,65536))
        for _ in range(2):
            try:
                connection=socket.create_connection(('127.0.0.1',ep),.2);connections.append(connection)
            except OSError:break
            time.sleep(.02)
        failure=wait(lambda:read() if read()['listener_error'] and read()['resource_error'] else None)
        assert worker.poll() is None and failure['running'] and not failure['recovery_pending']
        for connection in connections:connection.close()
        connections.clear();resource.prlimit(child,resource.RLIMIT_NOFILE,(65536,65536))
        gate.set();assert worker.wait(timeout=45)==1
        phases=[json.loads(line) for line in (root/'supervisor-fault.log').read_text().splitlines()]
        if not any(row['electrs_phase']=='compacting' for row in phases):print(json.dumps({'phases':phases,'runtime':read()}),flush=True)
        assert any(row['electrs_phase']=='compacting' for row in phases)
        assert any(row['electrs_phase']=='catching_up' for row in phases)
        assert read()['recovery_pending'] and not read()['running']
        identity=(root/'index/regtest/IDENTITY').read_text()
        worker=start([sys.executable,__file__,'--worker',config],'supervisor-recovered')
        probe=ElectrumProbe(ep)
        state=wait(lambda: (value if value['ready'] else None) if (value:=probe.poll()) else None)
        assert state['height']==10 and state['tip']==cli('getbestblockhash')
        assert (root/'index/regtest/IDENTITY').read_text()==identity,'Existing index must be reopened without rebuilding'
        assert read()['running'] and not read()['listener_error']
        assert resource.prlimit(read()['pid'],resource.RLIMIT_NOFILE)==(65536,65536)
        cli('stop');core.wait(timeout=30)
        assert worker.wait(timeout=30)==1,'Unexpected clean upstream exit must request recovery'
        assert read()['phase']=='failed' and not read()['running']
        core=start(core_command,'core-restarted');wait(lambda:cli('getblockchaininfo'))
        worker=start([sys.executable,__file__,'--worker',config],'supervisor-reconnected')
        probe.close();probe=ElectrumProbe(ep)
        wait(lambda:probe.poll()['ready'])
        worker.terminate();assert worker.wait(timeout=30)==0
        phases=[json.loads(line) for line in (root/'supervisor-recovered.log').read_text().splitlines()]
        assert any(row['electrs_phase']=='catching_up' for row in phases),'Existing compacted DB readiness marker not detected'
        assert not any(row['electrs_phase']=='compacting' for row in phases),'Recovery unexpectedly rebuilt the index'
        assert read()['phase']=='stopped' and not read()['running']
        print(json.dumps({'status':'PASS','core':cli('getnetworkinfo')['subversion'],'electrs':subprocess.check_output([str(a.electrs),'--version'],text=True).strip(),'fault_nofile':8,'configured_nofile':65536,'checks':['actual accept_loop EMFILE captured while Core RPC held','no early recovery before first compaction','real compaction completed before graceful retry exit','same RocksDB identity and matching Core tip after restart','already-compacted DB detected on reopen','Core disconnect requests restart even if upstream exits successfully','nonprivileged supervisor signal forwarding and clean stop']}))
    finally:
        gate.set()
        for connection in connections:connection.close()
        for child in reversed(processes):
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=30)
                except subprocess.TimeoutExpired:child.kill();child.wait()
        proxy.shutdown();proxy.server_close()
