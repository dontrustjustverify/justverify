#!/usr/bin/env python3
"""Public testnet4 audit confined to the dedicated disposable VM volume."""
import argparse,base64,collections,hashlib,http.client,http.server,json,os,pathlib,socket,subprocess,threading,time,urllib.request
ROOT=pathlib.Path('/srv/jv-testnet4')
EVIDENCE=ROOT/'evidence'

def guard():
    assert subprocess.check_output(['systemd-detect-virt'],text=True).strip()=='qemu'
    assert subprocess.check_output(['findmnt','-n','-o','SOURCE',str(ROOT)],text=True).strip()=='/dev/vdb'
    assert subprocess.check_output(['lsblk','-dn','-o','SERIAL','/dev/vdb'],text=True).strip()=='JVTESTNET4'
    assert 'chain=testnet4\n' in (ROOT/'core/bitcoin.conf').read_text()

def atomic(name,value):
    target=EVIDENCE/name;temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.chmod(0o600);temporary.replace(target)

def rpc(method,params=None):
    cookie=(ROOT/'core/testnet4/.cookie').read_bytes().strip()
    request=urllib.request.Request('http://127.0.0.1:48332',json.dumps({'id':1,'method':method,'params':params or []}).encode(),{'Authorization':'Basic '+base64.b64encode(cookie).decode()})
    with urllib.request.urlopen(request,timeout=15) as response:value=json.load(response)
    if value.get('error'):raise RuntimeError('Core RPC not ready')
    return value['result']

def snapshot():
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3);connection.connect(str(ROOT/'runtime/manager.sock'));connection.sendall(b'snapshot\n');body=b''
        while chunk:=connection.recv(65536):
            body+=chunk
            if len(body)>4*1024*1024:raise ValueError('snapshot limit')
        return json.loads(body)

def electrum(method,params=None):
    with socket.create_connection(('127.0.0.1',50003),3) as connection:
        connection.settimeout(30);connection.sendall((json.dumps({'id':1,'method':method,'params':params or []})+'\n').encode())
        with connection.makefile('rb') as stream:body=stream.readline(8*1024*1024+1)
        if len(body)>8*1024*1024:raise ValueError('Electrum response limit')
        result=json.loads(body)
        if result.get('error'):raise RuntimeError('Electrum query failed')
        return result['result']

def process_metrics(pid):
    if not pid:return None
    try:
        status=pathlib.Path('/proc',str(pid),'status').read_text().splitlines()
        fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in status if ':' in line}
        io=pathlib.Path('/proc',str(pid),'io').read_text().splitlines()
        descriptors=list(pathlib.Path('/proc',str(pid),'fd').iterdir());sockets=[]
        for descriptor in descriptors:
            try:
                target=os.readlink(descriptor)
                if target.startswith('socket:'):sockets.append(target)
            except OSError:pass
        return {'fds':len(descriptors),'socket_fds':len(sockets),'unique_sockets':len(set(sockets)),'rss_kib':int(fields['VmRSS'].split()[0]),'threads':int(fields['Threads']),'io':{line.split(':')[0]:int(line.split(':')[1]) for line in io if line.split(':')[0] in ('read_bytes','write_bytes')}}
    except (OSError,KeyError,ValueError):return None

def observe_once():
    chain=rpc('getblockchaininfo');assert chain['chain']=='testnet4'
    value={'time':int(time.time()),'network':'testnet4','core':{key:chain[key] for key in ('blocks','headers','bestblockhash','initialblockdownload','verificationprogress','size_on_disk','time')},'peers':rpc('getnetworkinfo')['connections'],'indexes':rpc('getindexinfo')}
    try:
        manager=snapshot();value['electrs']=manager.get('host',{}).get('electrs');recent=manager.get('rpc',{}).get('recentblocks',{}).get('value',[])
        value['recent_blocks']=[{key:b.get(key) for key in ('height','hash','size','details_deferred','miner')} for b in recent or []]
    except (OSError,ValueError):value['collector_unavailable']=True
    try:
        runtime=json.loads(pathlib.Path('/run/justverify-electrs/status.json').read_text());value['runtime']=runtime;value['electrs_process']=process_metrics(runtime['pid'])
    except (OSError,ValueError,KeyError):pass
    try:value['rpc_audit']=json.loads((EVIDENCE/'rpc-counts.json').read_text())
    except (OSError,ValueError):pass
    free=os.statvfs(ROOT);value['free_bytes']=free.f_bavail*free.f_frsize
    atomic('progress.json',value)
    with (EVIDENCE/'timeline.jsonl').open('a') as output:output.write(json.dumps(value)+'\n')
    if value['free_bytes']<10*1024**3:rpc('stop');raise RuntimeError('Isolated data reserve reached')
    return value

def proxy():
    lock=threading.Lock()
    try:counts=json.loads((EVIDENCE/'rpc-counts.json').read_text())
    except (OSError,ValueError):counts={'methods':{},'ibd_detail_requests':0,'detail_requests':0,'last_ibd':None,'recent_detail_hashes':[]}
    class Forward(http.server.BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*_):pass
        def do_POST(self):
            body=self.rfile.read(int(self.headers['Content-Length']));request=json.loads(body);method=request['method']
            with lock:
                counts['methods'][method]=counts['methods'].get(method,0)+1
                if method in ('getblock','getrawtransaction'):
                    counts['detail_requests']+=1;counts['ibd_detail_requests']+=int(counts['last_ibd'] is True)
                    digest=request['params'][0 if method=='getblock' else 2]
                    counts['recent_detail_hashes']=(counts['recent_detail_hashes']+[digest])[-24:]
            remote=http.client.HTTPConnection('127.0.0.1',48332,timeout=15)
            try:
                remote.request('POST','/',body,{'Authorization':self.headers['Authorization']})
                response=remote.getresponse();data=response.read(16*1024*1024)
                if method=='getblockchaininfo' and response.status==200:
                    result=json.loads(data).get('result')
                    if result:
                        with lock:counts['last_ibd']=result['initialblockdownload']
                self.send_response(response.status);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except (OSError,ValueError,http.client.HTTPException):self.close_connection=True
            finally:remote.close()
    server=http.server.ThreadingHTTPServer(('127.0.0.1',48432),Forward)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    while True:
        with lock:atomic('rpc-counts.json',{**counts,'updated':int(time.time())})
        time.sleep(2)

def check():
    value=observe_once();chain=value['core'];index=value['electrs']
    assert not chain['initialblockdownload'] and chain['blocks']==chain['headers']
    assert index['state']=='READY' and index['wallet_ready'] and not index['height_stale'] and not index['target_stale']
    assert index['height']==chain['blocks'] and index['tip']==chain['bestblockhash']
    header=electrum('blockchain.headers.subscribe');digest=hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()
    assert header['height']==chain['blocks'] and digest==chain['bestblockhash'];assert electrum('server.ping') is None
    assert value['rpc_audit']['ibd_detail_requests']==0
    assert len(value['recent_blocks'])==6 and all(b['size'] and not b['details_deferred'] for b in value['recent_blocks'])
    for b in value['recent_blocks']:assert b['size']==rpc('getblock',[b['hash'],1])['size']
    block=rpc('getblock',[chain['bestblockhash'],1]);txid=block['tx'][0];tx=rpc('getrawtransaction',[txid,True,chain['bestblockhash']])
    output=next(v for v in tx['vout'] if v['value']>0 and v['scriptPubKey']['type']!='nulldata');script=bytes.fromhex(output['scriptPubKey']['hex']);sh=hashlib.sha256(script).digest()[::-1].hex()
    history=electrum('blockchain.scripthash.get_history',[sh]);assert any(t['tx_hash']==txid and t['height']==chain['blocks'] for t in history)
    proof=electrum('blockchain.transaction.get_merkle',[txid,chain['blocks']]);digest=bytes.fromhex(txid)[::-1];position=proof['pos']
    for sibling in proof['merkle']:
        other=bytes.fromhex(sibling)[::-1];data=other+digest if position&1 else digest+other
        digest=hashlib.sha256(hashlib.sha256(data).digest()).digest();position>>=1
    assert position==0 and digest[::-1].hex()==block['merkleroot']
    with urllib.request.urlopen('https://mempool.space/testnet4/api/block-height/'+str(chain['blocks']),timeout=30) as response:external=response.read().decode().strip()
    assert external==chain['bestblockhash'],'Independent public chain differs at the checked height'
    result={'status':'PASS','network':'testnet4','height':chain['blocks'],'tip':chain['bestblockhash'],'public_tip_agreement':True,'core_ibd':False,'electrs_wallet_ready':True,'transaction_history_and_merkle_proof':'PASS','ibd_detail_requests':value['rpc_audit']['ibd_detail_requests'],'current_six_block_sizes':'PASS','runtime':value['runtime'],'resources':value['electrs_process']}
    atomic('acceptance.json',result);return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['proxy','observe','once','check']);args=parser.parse_args();guard()
    if args.mode=='proxy':proxy()
    elif args.mode=='check':print(json.dumps(check()))
    elif args.mode=='once':print(json.dumps(observe_once()))
    else:
        while True:
            try:observe_once()
            except (OSError,ValueError,RuntimeError) as error:atomic('observer-error.json',{'type':type(error).__name__,'time':int(time.time())})
            time.sleep(30)
