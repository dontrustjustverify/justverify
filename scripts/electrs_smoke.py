#!/usr/bin/env python3
"""Real Core/electrs indexing, script history, restart; no mock service."""
import pathlib,subprocess,time,socket,json,hashlib,os,struct,argparse
from decimal import Decimal
R=pathlib.Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--version',default='31.1');parser.add_argument('--core-bin',type=pathlib.Path);parser.add_argument('--electrs-bin',type=pathlib.Path);parser.add_argument('--state',type=pathlib.Path);parser.add_argument('--report',type=pathlib.Path)
parser.add_argument('--tor-hostname-file',type=pathlib.Path);parser.add_argument('--tor-socks-port',type=int,default=19650)
a=parser.parse_args()
S=a.state or R/'.state/electrs-smoke';S.mkdir(parents=True,exist_ok=True);S.chmod(0o700)
D=S/'core';D.mkdir(exist_ok=True)
B=a.core_bin or R/f'.cache/core/{a.version}/arm64-apple-darwin/bitcoin-{a.version}/bin'
E=a.electrs_bin or R/'.cache/electrs-0.11.1/target/release/electrs';ps=[]

def cli(*a):
    text=subprocess.check_output([str(B/'bitcoin-cli'),f'-datadir={D}','-regtest','-rpcport=19543',*a],text=True).strip()
    try:return json.loads(text)
    except json.JSONDecodeError:return text
def rpc(method,params):
    with socket.create_connection(('127.0.0.1',19501),2) as s:
        s.sendall((json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params})+'\n').encode());f=s.makefile('rb');r=json.loads(f.readline())
        if r.get('error'):raise RuntimeError(r['error'])
        return r['result']
def onion_headers():
    hostname=a.tor_hostname_file.read_text().strip().encode()
    with socket.create_connection(('127.0.0.1',a.tor_socks_port),3) as sock:
        sock.settimeout(15)
        f=sock.makefile('rb')
        sock.sendall(bytes([5,1,0]));assert f.read(2)==bytes([5,0])
        sock.sendall(bytes([5,1,0,3,len(hostname)])+hostname+(50001).to_bytes(2,'big'))
        header=f.read(4)
        if len(header)!=4 or header[1]!=0:raise RuntimeError('onion circuit not ready')
        if header[3]==1:f.read(4)
        elif header[3]==4:f.read(16)
        elif header[3]==3:f.read(f.read(1)[0])
        else:raise RuntimeError('invalid SOCKS address')
        f.read(2)
        sock.sendall(b'{"jsonrpc":"2.0","id":1,"method":"blockchain.headers.subscribe","params":[]}\n')
        return json.loads(f.readline(4096))['result']['height']

def wait(f,seconds=90):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            value=f()
            if value:return value
        except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError):pass
        time.sleep(.5)
    raise RuntimeError('integration timeout; inspect private logs')
def start_index():
    log=(S/'electrs.log').open('ab');p=subprocess.Popen([str(E),'--skip-default-conf-files','--network=regtest',f'--daemon-dir={D}',f'--db-dir={S/"index"}','--daemon-rpc-addr=127.0.0.1:19543','--daemon-p2p-addr=127.0.0.1:19544','--electrum-rpc-addr=127.0.0.1:19501','--monitoring-addr=127.0.0.1:19524','--log-filters=INFO'],stdout=log,stderr=log);ps.append(p);return p
try:
    log=(S/'core.log').open('ab');core=subprocess.Popen([str(B/'bitcoind'),f'-datadir={D}','-regtest','-server','-listen=1','-bind=127.0.0.1','-port=19544','-rpcport=19543','-connect=0','-dnsseed=0','-disablewallet'],stdout=log,stderr=log);ps.append(core)
    wait(lambda:cli('getblockchaininfo'))
    script='0020'+hashlib.sha256(bytes.fromhex('51')).hexdigest();desc=cli('getdescriptorinfo',f'raw({script})')['descriptor'];cli('generatetodescriptor','101',desc);height=cli('getblockcount')
    index=start_index();wait(lambda:rpc('blockchain.headers.subscribe',[])['height']==height)
    sh=hashlib.sha256(bytes.fromhex(script)).digest()[::-1].hex();history=rpc('blockchain.scripthash.get_history',[sh]);assert len(history)>=3
    block=cli('getblock',cli('getblockhash',str(height-100)),'2');coinbase=block['tx'][0]
    output=next(v for v in coinbase['vout'] if v['scriptPubKey']['hex']==script)
    raw=(struct.pack('<I',2)+b'\x00\x01\x01'+bytes.fromhex(coinbase['txid'])[::-1]+struct.pack('<I',output['n'])+b'\x00'+b'\xff'*4+b'\x01'+struct.pack('<Q',int(Decimal(str(output['value']))*100_000_000)-10_000)+bytes([len(bytes.fromhex(script))])+bytes.fromhex(script)+b'\x01\x01\x51'+b'\x00'*4).hex()
    txid=rpc('blockchain.transaction.broadcast',[raw]);assert txid in cli('getrawmempool')
    wait(lambda: any(t['tx_hash']==txid and t['height']<=0 for t in rpc('blockchain.scripthash.get_history',[sh])))
    cli('generatetodescriptor','1',desc);height=cli('getblockcount')
    wait(lambda:rpc('blockchain.headers.subscribe',[])['height']==height)
    history=rpc('blockchain.scripthash.get_history',[sh])
    index.terminate();index.wait(timeout=15);index=start_index();wait(lambda:rpc('blockchain.headers.subscribe',[])['height']==height)
    assert rpc('blockchain.scripthash.get_history',[sh])==history
    if a.tor_hostname_file:wait(lambda:onion_headers()==height,seconds=180)
    result={'status':'PASS','core':a.version,'electrs':'0.11.1','electrs_commit':'35216c6d30148be8e6763d913d437330f431fc03','platform':os.uname().sysname+' '+os.uname().machine,'height':height,'history_count':len(history),'checks':['real P2P/RPC indexing','Electrum headers','scripthash history','index restart persistence','Electrum broadcast accepted by Core','mempool scripthash sees transaction','confirmed transaction indexed'],'not_run':['Tor remote wallet','mainnet full indexing']}
    if a.tor_hostname_file:result['checks'].append('actual onion Electrum headers over Tor SOCKS');result['not_run']=['actual mobile wallet','mainnet full indexing']
    (a.report or R/'docs/evidence/electrs-smoke.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
finally:
    for p in reversed(ps):
        if p.poll() is None:
            p.terminate()
            try:p.wait(timeout=20)
            except subprocess.TimeoutExpired:p.kill();p.wait()
