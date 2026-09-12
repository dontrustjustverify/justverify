#!/usr/bin/env python3
"""Resume only the dedicated testnet4 audit; never accesses a default datadir."""
import datetime, hashlib, json, os, pathlib, shutil, signal, socket, subprocess, sys, time, urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
STATE=ROOT/'.state/public-testnet4-audit'
BIN=ROOT/'.cache/core/31.1/arm64-apple-darwin/bitcoin-31.1/bin'
INDEX=ROOT/'.cache/electrs-0.11.1/target/release/electrs'
REPORT=ROOT/'docs/evidence/public-testnet4-audit.json'
assert STATE.is_dir() and not STATE.is_symlink()
assert 'chain=testnet4' in (STATE/'core/bitcoin.conf').read_text()
def save(path,value):
    temporary=path.with_suffix('.new');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.chmod(0o600);temporary.replace(path)
def rpc(method,*params):
    proc=subprocess.run([str(BIN/'bitcoin-cli'),f'-datadir={STATE/"core"}','-rpcport=29443','-rpcwallet=audit-testnet4',method,*[p if isinstance(p,str) else json.dumps(p) for p in params]],capture_output=True,text=True,timeout=30)
    if proc.returncode:raise RuntimeError(method+' RPC failed')
    try:return json.loads(proc.stdout)
    except ValueError:return proc.stdout.strip()
def electrum(method,params=[]):
    with socket.create_connection(('127.0.0.1',29401),3) as s:
        s.settimeout(10);s.sendall((json.dumps({'id':1,'method':method,'params':params})+'\n').encode())
        value=json.loads(s.makefile('rb').readline(4*1024*1024))
        if value.get('error'):raise RuntimeError('Electrum error')
        return value['result']
def external(path):
    with urllib.request.urlopen('https://mempool.space/testnet4/api/'+path,timeout=20) as response:
        value=response.read().decode()
        try:return json.loads(value)
        except ValueError:return value
def sync():
    chain=rpc('getblockchaininfo');assert chain['chain']=='testnet4' and not chain['pruned']
    result={'chain':chain,'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'peer_count':rpc('getnetworkinfo')['connections'],'status':'SYNCING'}
    result['handshaken_peers']=sum(p.get('version',0)>0 for p in rpc('getpeerinfo'))
    try:
        header=electrum('blockchain.headers.subscribe');raw=bytes.fromhex(header['hex'])
        assert len(raw)==80
        tip=hashlib.sha256(hashlib.sha256(raw).digest()).digest()[::-1].hex()
        result['electrs']={'height':header['height'],'tip':tip}
        # Core31.1 chain.h permits blocks up to MAX_FUTURE_BLOCK_TIME=2h.
        # Preserve the two-hour freshness bound while recording valid future skew.
        age=time.time()-chain['time'];recent=-7200<=age<7200
        result['block_time_age_seconds']=age
        result['future_time_bound_source']='https://github.com/bitcoin/bitcoin/blob/9be056a8a72b624dae9623b2f7bded92c2a21c91/src/chain.h'
        result['recent_block_within_two_hours']=recent
        if not chain['initialblockdownload'] and chain['blocks']==chain['headers']==header['height'] and chain['bestblockhash']==tip and recent and result['handshaken_peers']>0:
            result['local_sync']=True
            observed=external('block-height/'+str(chain['blocks']))
            result['independent_tip_at_height']=observed
            if observed==tip:result['status']='PASS'
    except (OSError,ValueError,RuntimeError):pass
    save(STATE/'sync-progress.json',result)
    return result
def await_sync(seconds=14400, allow_independent_divergence=False):
    deadline=time.monotonic()+seconds;last=None
    while time.monotonic()<deadline:
        if shutil.disk_usage(STATE).free<20*1024**3:
            rpc('stop');raise RuntimeError('host reserve reached; stopped dedicated Core')
        result=sync()
        if result['status']=='PASS':return result
        # Continue independent transaction/restart tests without declaring the
        # external-chain agreement gate passed or changing Core fork selection.
        if allow_independent_divergence and result.get('local_sync') and 'independent_tip_at_height' in result:
            result['status']='LOCAL_SYNCED_EXTERNAL_TIP_DIVERGENCE'
            save(STATE/'sync-progress.json',result);return result
        current=(result['chain']['blocks']//5000,result.get('electrs',{}).get('height',0)//5000)
        if current!=last:print('testnet4 progress',result['chain']['blocks'],result['chain']['headers'],result.get('electrs'),flush=True);last=current
        time.sleep(10)
    raise RuntimeError('sync deadline; checkpoint retained')
def restart():
    info=json.loads((STATE/'electrs-process.json').read_text());pid=info['pid']
    command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
    assert str(INDEX) in command and str(STATE/'index') in command
    os.kill(pid,signal.SIGTERM)
    rpc('stop')
    # A stopped RPC endpoint alone does not prove the datadir lock was released.
    corepid=json.loads((STATE/'process.json').read_text())['pid']
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        if subprocess.run(['ps','-p',str(corepid)],stdout=subprocess.DEVNULL).returncode and subprocess.run(['ps','-p',str(pid)],stdout=subprocess.DEVNULL).returncode:break
        time.sleep(1)
    else:raise RuntimeError('graceful process exit deadline')
    conf=STATE/'core/bitcoin.conf';text=conf.read_text()
    if 'maxmempool=' not in text:conf.write_text('maxmempool=420\n'+text)
    proc=subprocess.Popen([str(BIN/'bitcoind'),f'-datadir={STATE/"core"}'],stdout=open(STATE/'core-console.log','ab'),stderr=subprocess.STDOUT,start_new_session=True)
    save(STATE/'process.json',{'pid':proc.pid,'network':'testnet4','data':str(STATE/'core'),'binary':str(BIN/'bitcoind')})
    proc=subprocess.Popen([str(INDEX),'--skip-default-conf-files','--network=testnet4',f'--daemon-dir={STATE/"core"}',f'--db-dir={STATE/"index"}','--daemon-rpc-addr=127.0.0.1:29443','--daemon-p2p-addr=127.0.0.1:29444','--electrum-rpc-addr=127.0.0.1:29401','--monitoring-addr=127.0.0.1:29424','--log-filters=INFO'],stdout=open(STATE/'electrs.log','ab'),stderr=subprocess.STDOUT,start_new_session=True)
    save(STATE/'electrs-process.json',{'pid':proc.pid,'network':'testnet4'})
    deadline=time.monotonic()+60
    while True:
        try:rpc('getblockchaininfo');break
        except RuntimeError:
            if time.monotonic()>deadline:raise
            time.sleep(1)
    if 'audit-testnet4' not in rpc('listwallets'):rpc('loadwallet','audit-testnet4')
    assert rpc('getmempoolinfo')['maxmempool']==420000000
try:
    if sys.argv[1:]==['--observe']:
        report=json.loads(REPORT.read_text());report['latest_sync']=sync()
        own=rpc('gettransaction',report['txid']);report['confirmations']=own.get('confirmations',0)
        report['independent_status']=external('tx/'+report['txid']+'/status')
        spend=json.loads((STATE/'spend.json').read_text());assert spend['txid']==report['txid']
        script=rpc('getaddressinfo',spend['address'])['scriptPubKey'];sh=hashlib.sha256(bytes.fromhex(script)).digest()[::-1].hex()
        history=next(t for t in electrum('blockchain.scripthash.get_history',[sh]) if t['tx_hash']==report['txid'])
        report['electrs_transaction_height']=history['height']
        if report['confirmations']>0:
            block=rpc('getblockheader',own['blockhash']);height=block['height']
            assert history['height']==height and report['independent_status']['confirmed']
            assert report['independent_status']['block_hash']==own['blockhash']
            proof=electrum('blockchain.transaction.get_merkle',[report['txid'],height])
            assert proof['block_height']==height
            value=bytes.fromhex(report['txid'])[::-1];position=proof['pos']
            for sibling in proof['merkle']:
                other=bytes.fromhex(sibling)[::-1];combined=other+value if position&1 else value+other
                value=hashlib.sha256(hashlib.sha256(combined).digest()).digest();position>>=1
            assert position==0 and value[::-1].hex()==block['merkleroot']
            report['confirmed_merkle_proof']={'status':'PASS','block_height':height,'block_hash':own['blockhash'],'branch_length':len(proof['merkle'])}
        else:assert history['height']<=0
        if report['latest_sync']['status']=='PASS':report['status']='PASS_WITH_LIMITS'
        save(REPORT,report);print(json.dumps({'sync':report['latest_sync']['status'],'confirmations':report['confirmations'],'independent_status':report['independent_status']}));sys.exit(0)
    assert not sys.argv[1:],'unsupported argument'
    before=await_sync(allow_independent_divergence=True)
    spendfile=STATE/'spend.json'
    if spendfile.exists():spend=json.loads(spendfile.read_text())
    else:
        address=rpc('getnewaddress','public-spend-audit','bech32')
        raw=rpc('createrawtransaction',[],{address:0.001})
        funded=rpc('fundrawtransaction',raw,{'fee_rate':2,'include_unsafe':True})
        signed=rpc('signrawtransactionwithwallet',funded['hex']);assert signed['complete']
        decoded=rpc('decoderawtransaction',signed['hex']);txid=decoded['txid']
        accepted=rpc('testmempoolaccept',[signed['hex']]);assert accepted[0]['allowed']
        # Persist exact signed transaction before broadcast so retries never double-spend new funds.
        spend={'txid':txid,'signed_hex':signed['hex'],'address':address,'phase':'signed'};save(spendfile,spend)
    txid=spend['txid']
    if spend['phase']=='signed':
        assert rpc('sendrawtransaction',spend['signed_hex'])==txid
        spend['phase']='broadcast';save(spendfile,spend)
    deadline=time.monotonic()+180
    while True:
        try:independent=external('tx/'+txid+'/status');break
        except OSError:
            if time.monotonic()>deadline:raise
            time.sleep(5)
    script=rpc('getaddressinfo',spend['address'])['scriptPubKey'];sh=hashlib.sha256(bytes.fromhex(script)).digest()[::-1].hex()
    deadline=time.monotonic()+120
    while not any(t['tx_hash']==txid for t in electrum('blockchain.scripthash.get_history',[sh])):
        if time.monotonic()>deadline:raise RuntimeError('electrs did not index own transaction')
        time.sleep(2)
    own=rpc('gettransaction',txid)
    if own.get('confirmations',0)==0:
        assert txid in rpc('getrawmempool')
        assert any(t['tx_hash']==txid and t['height']<=0 for t in electrum('blockchain.scripthash.get_history',[sh]))
    report={'status':'IN_PROGRESS','network':'testnet4','core':'31.1','electrs':'0.11.1','sync_before':before,'txid':txid,'confirmations':own.get('confirmations',0),'independent_status':independent,'propagation':'PASS: independent mempool.space lookup','wallet_and_electrs':'PASS','device_reboot':'NOT RUN'}
    save(REPORT,report)
    restart();report['sync_after_restart']=await_sync(900,allow_independent_divergence=True)
    assert rpc('gettransaction',txid)['txid']==txid
    assert any(t['tx_hash']==txid for t in electrum('blockchain.scripthash.get_history',[sh]))
    if rpc('gettransaction',txid).get('confirmations',0)==0:assert txid in rpc('getrawmempool')
    agreed=before['status']=='PASS' and report['sync_after_restart']['status']=='PASS'
    report.update(status='PASS_WITH_LIMITS' if agreed else 'PARTIAL_EXTERNAL_TIP_DIVERGENCE',settings_restart='PASS maxmempool420 MB actual RPC; chain/wallet/electrs retained',confirmations=rpc('gettransaction',txid).get('confirmations',0),independent_status=external('tx/'+txid+'/status'))
    save(REPORT,report);print(json.dumps(report),flush=True)
except Exception as error:
    save(STATE/'runner-error.json',{'error':type(error).__name__,'message':str(error),'time':time.time()});raise
