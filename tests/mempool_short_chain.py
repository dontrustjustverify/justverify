#!/usr/bin/env python3
"""Reopen genuine saved explorer caches after a real regtest tip rollback."""
import argparse,hashlib,json,os,pathlib,signal,subprocess,time,urllib.request
p=argparse.ArgumentParser();p.add_argument('--state',type=pathlib.Path,required=True);p.add_argument('--core',type=pathlib.Path,required=True);p.add_argument('--electrs',type=pathlib.Path,required=True);p.add_argument('--bundle',type=pathlib.Path,required=True);a=p.parse_args()
assert os.geteuid()!=0 and a.state.name.startswith('jv-mempool-test-') and not (a.state/'ready').exists()
ROOT=pathlib.Path(__file__).resolve().parents[1];processes=[]
profile=json.loads((a.state/'profile.json').read_text());assert profile['network']=='regtest'
folder=a.state/('mempool/regtest-'+profile.get('data_id',profile['version']))
db=folder/'mysql';before=db.stat().st_ino
def start(command):
    proc=subprocess.Popen([str(v) for v in command],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(proc);return proc
def cli(method,*params):
    result=subprocess.check_output([str(a.core/'bitcoin-cli'),'-regtest','-datadir='+str(a.state/'core'),'-rpcport=19643',method,*map(str,params)],timeout=10,text=True)
    try:return json.loads(result)
    except ValueError:return result.strip()
def wait(fn,seconds=120):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            if fn():return
        except (OSError,ValueError,KeyError,subprocess.CalledProcessError):pass
        time.sleep(.5)
    raise TimeoutError('actual short chain recovery')
def status():return json.loads((a.state/'runtime/status.json').read_text())
def runner():return start(['/usr/bin/python3',ROOT/'scripts/mempool_service.py','--bundle',a.bundle,'--runtime',a.state/'runtime','--profile',a.state/'profile.json','--data',a.state/'mempool','--api-port','18999','--web-port','13006','--electrum-port','19601'])
def cached_height():
    blocks=json.loads((folder/'cache/cache.json').read_text())['blocks']
    return max((b['height'] for b in blocks),default=-1)
try:
    start([a.core/'bitcoind','-regtest','-datadir='+str(a.state/'core'),'-server=1','-txindex=1','-connect=0','-dnsseed=0','-bind=127.0.0.1','-port=19644','-rpcport=19643','-dbcache=32'])
    wait(lambda:cli('getblockcount')==107)
    start([a.electrs,'--skip-default-conf-files','--network=regtest','--daemon-dir='+str(a.state/'core'),'--db-dir='+str(a.state/'index'),'--daemon-rpc-addr=127.0.0.1:19643','--daemon-p2p-addr=127.0.0.1:19644','--electrum-rpc-addr=127.0.0.1:19601','--monitoring-addr=127.0.0.1:19624'])
    start(['/opt/justverify/venv/bin/python',ROOT/'web/mempool_proxy.py','--bundle',a.bundle,'--runtime',a.state/'runtime','--profile',a.state/'profile.json','--port','13006','--backend','http://127.0.0.1:18999'])
    service=runner();wait(lambda:status()['state']=='running',240)
    # Ask the real backend to flush its current in-memory tip, not a fixture JSON.
    children=pathlib.Path(f'/proc/{service.pid}/task/{service.pid}/children').read_text().split()
    node=next(int(pid) for pid in children if b'/usr/bin/node\0' in pathlib.Path('/proc/'+pid+'/cmdline').read_bytes())
    os.kill(node,signal.SIGINT);wait(lambda:cached_height()==107,15)
    service.terminate();service.wait(timeout=130)
    assert cached_height()==107
    cli('invalidateblock',cli('getblockhash',1));assert cli('getblockcount')==0
    cli('generatetodescriptor',2,'raw(51)');tip=cli('getbestblockhash')
    runner()
    wait(lambda:status()['state']=='running',240)
    with urllib.request.urlopen('http://127.0.0.1:13006/api/blocks/tip/hash',timeout=10) as response:assert response.read().decode()==tip
    with urllib.request.urlopen('http://127.0.0.1:13006/api/blocks',timeout=10) as response:
        assert all(b['height']<=2 for b in json.load(response))
    assert db.stat().st_ino==before
    assert {x.name for x in (a.state/'mempool').iterdir()}=={folder.name}
    print('PASS actual cached height107 -> Core genesis -> new height2; Electrs/explorer follow new tip and SQL directory stays fixed',flush=True)
finally:
    for proc in reversed(processes):
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=130)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
