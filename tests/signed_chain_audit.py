#!/usr/bin/env python3
"""Real isolated Core wallet signing and electrs confirmation/restart audit."""
import argparse, hashlib, json, os, pathlib, socket, subprocess, tempfile, time

p = argparse.ArgumentParser()
p.add_argument('--core-bin', type=pathlib.Path, required=True)
p.add_argument('--electrs-bin', type=pathlib.Path, required=True)
p.add_argument('--report', type=pathlib.Path, required=True)
p.add_argument('--core-indexes', action='store_true')
a = p.parse_args()
state = pathlib.Path(tempfile.mkdtemp(prefix='jv-signed-regtest-'))
data = state / 'core'; data.mkdir()
processes = []
calls = {}
def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]
rpcport, p2pport, eport, metrics = [port() for _ in range(4)]
def cli(method, *params, wallet=None):
    args = [str(a.core_bin / 'bitcoin-cli'), f'-datadir={data}', '-regtest', f'-rpcport={rpcport}']
    if wallet: args += [f'-rpcwallet={wallet}']
    result = subprocess.run(args + [method] + [json.dumps(v) if not isinstance(v, str) else v for v in params], capture_output=True, text=True)
    if result.returncode: raise RuntimeError(f'{method}: {result.stderr}')
    calls[method] = calls.get(method, 0) + 1
    try: return json.loads(result.stdout)
    except ValueError: return result.stdout.strip()
def erpc(method, params=[]):
    with socket.create_connection(('127.0.0.1', eport), 2) as s:
        s.settimeout(3)
        s.sendall((json.dumps({'id': 1, 'method': method, 'params': params}) + '\n').encode())
        response = json.loads(s.makefile('rb').readline(4*1024*1024))
        if response.get('error'): raise RuntimeError(response['error'])
        return response['result']
def wait(f, seconds=120):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            value=f()
            if value: return value
        except (OSError, ValueError, RuntimeError): pass
        time.sleep(.25)
    raise RuntimeError('real service predicate timed out')
def start_core():
    proc = subprocess.Popen([str(a.core_bin/'bitcoind'),f'-datadir={data}','-regtest','-server=1','-listen=1','-bind=127.0.0.1',f'-port={p2pport}',f'-rpcport={rpcport}','-connect=0','-dnsseed=0','-maxmempool=64']+(['-txindex=1','-txospenderindex=1','-blockfilterindex=1'] if a.core_indexes else []),stdout=open(state/'core.log','ab'),stderr=subprocess.STDOUT)
    processes.append(proc);wait(lambda:cli('getblockchaininfo')); return proc
def start_index():
    proc = subprocess.Popen([str(a.electrs_bin),'--skip-default-conf-files','--network=regtest',f'--daemon-dir={data}',f'--db-dir={state/"index"}',f'--daemon-rpc-addr=127.0.0.1:{rpcport}',f'--daemon-p2p-addr=127.0.0.1:{p2pport}',f'--electrum-rpc-addr=127.0.0.1:{eport}',f'--monitoring-addr=127.0.0.1:{metrics}'],stdout=open(state/'electrs.log','ab'),stderr=subprocess.STDOUT)
    processes.append(proc); return proc
def tip_matches():
    header=erpc('blockchain.headers.subscribe'); raw=bytes.fromhex(header['hex'])
    return header['height']==cli('getblockcount') and hashlib.sha256(hashlib.sha256(raw).digest()).digest()[::-1].hex()==cli('getbestblockhash')
try:
    core=start_core()
    cli('createwallet','audit-sender');cli('createwallet','audit-recipient')
    mine=cli('getnewaddress',wallet='audit-sender')
    destination=cli('getnewaddress',wallet='audit-recipient')
    cli('generatetoaddress',101,mine)
    available=cli('help')
    methods=[line.split()[0] for line in available.splitlines() if line and not line.startswith('==')]
    index=start_index();wait(tip_matches)
    raw=cli('createrawtransaction',[],{destination:1})
    funded=cli('fundrawtransaction',raw,{'fee_rate':2},wallet='audit-sender')
    signed=cli('signrawtransactionwithwallet',funded['hex'],wallet='audit-sender'); assert signed['complete']
    assert cli('testmempoolaccept',[signed['hex']])[0]['allowed']
    txid=erpc('blockchain.transaction.broadcast',[signed['hex']]); assert txid in cli('getrawmempool')
    script=cli('getaddressinfo',destination,wallet='audit-recipient')['scriptPubKey']
    sh=hashlib.sha256(bytes.fromhex(script)).digest()[::-1].hex()
    wait(lambda:any(t['tx_hash']==txid and t['height']<=0 for t in erpc('blockchain.scripthash.get_history',[sh])))
    assert cli('gettransaction',txid,wallet='audit-recipient')['confirmations']==0
    cli('generatetoaddress',1,mine);wait(tip_matches)
    wait(lambda:any(t['tx_hash']==txid and t['height']==102 for t in erpc('blockchain.scripthash.get_history',[sh])))
    assert cli('gettransaction',txid,wallet='audit-recipient')['confirmations']==1
    cli('generatetoaddress',2,mine);wait(tip_matches)
    assert cli('gettransaction',txid,wallet='audit-recipient')['confirmations']==3
    if a.core_indexes:
        wait(lambda:(lambda i:all(n in i and i[n]['synced'] and i[n]['best_block_height']==104 for n in ['txindex','txospenderindex','basic block filter index']))(cli('getindexinfo')))
        decoded=cli('decoderawtransaction',signed['hex'])
        spent=[{'txid':v['txid'],'vout':v['vout']} for v in decoded['vin']]
        indexed=cli('gettxspendingprevout',spent)
        assert len(indexed)==len(spent)>0 and all(v['spendingtxid']==txid for v in indexed)
        assert cli('getrawtransaction',txid,True)['confirmations']==3
        assert cli('getblockfilter',cli('getbestblockhash'))['filter']
    tip=cli('getbestblockhash')
    for method in ['getnetworkinfo','getnettotals','getmempoolinfo','getpeerinfo','getindexinfo','getrpcinfo','getblockchaininfo','uptime']:
        cli(method)
    cli('getblockheader',tip);cli('getblock',tip);cli('estimatesmartfee',6)
    cli('getmempoolentry',txid) if txid in cli('getrawmempool') else None
    assert cli('getmempoolinfo')['maxmempool']==64000000
    index.terminate();index.wait(timeout=30);cli('stop');core.wait(timeout=30)
    core=start_core();cli('loadwallet','audit-sender');cli('loadwallet','audit-recipient');index=start_index();wait(tip_matches)
    assert cli('getbestblockhash')==tip
    assert cli('getmempoolinfo')['maxmempool']==64000000
    assert cli('gettransaction',txid,wallet='audit-recipient')['confirmations']==3
    assert any(t['tx_hash']==txid and t['height']==102 for t in erpc('blockchain.scripthash.get_history',[sh]))
    if a.core_indexes:
        wait(lambda:(lambda i:all(n in i and i[n]['synced'] and i[n]['best_block_height']==104 for n in ['txindex','txospenderindex','basic block filter index']))(cli('getindexinfo')))
        assert cli('gettxspendingprevout',spent)==indexed
        assert cli('getrawtransaction',txid,True)['confirmations']==3
        assert cli('getblockfilter',tip)['filter']
    report={'status':'PASS' ,'core_indexes_tested':a.core_indexes,'network':'regtest','core':cli('getnetworkinfo')['subversion'],'electrs':'0.11.1','txid':txid,'confirmations':3,'height':104,'tip':tip,'rpc_success_counts':calls,'rpc_inventory':methods,'unexercised_rpc':sorted(set(methods)-set(calls)),'checks':['real wallet funding/signature','Electrum broadcast','Core and electrs mempool','wallet confirmations 0/1/3','Core/electrs height and header hash','both processes restarted, wallet reload, policy/chain/index retained'],'not_run':['device reboot in this test','public network propagation','all unexercised RPC semantics'],'private_state':str(state)}
    if a.core_indexes:report['checks'].append('Core txindex/txospenderindex/blockfilterindex synced at104; confirmed spend lookup and block filter survive restart')
    a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('rpc_inventory','unexercised_rpc','rpc_success_counts')}))
finally:
    for proc in reversed(processes):
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=30)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
