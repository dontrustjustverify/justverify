#!/usr/bin/env python3
"""Real signed transactions test policy acceptance, mining and persistence in regtest."""
import argparse,base64,http.client,decimal,hashlib,json,pathlib,socket,struct,subprocess,tempfile,time
p=argparse.ArgumentParser();p.add_argument('--core-bin',type=pathlib.Path,required=True);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
root=pathlib.Path(tempfile.mkdtemp(prefix='jv-policy-semantics-')).resolve();root.chmod(0o700)
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
proc=None;results=[];settings={'acceptnonstdtxn':'0','minrelaytxfee':'0.00001','incrementalrelayfee':'0.00001','dustrelayfee':'0.00003','datacarrier':'1','datacarriersize':'42','permitbaremultisig':'1','persistmempool':'1'}
def rpc(method,*params,wallet=False):
 connection=http.client.HTTPConnection('127.0.0.1',port,timeout=30)
 try:
  cookie=(root/'regtest/.cookie').read_bytes().strip()
  connection.request('POST','/wallet/policy' if wallet else '/',json.dumps({'id':1,'method':method,'params':list(params)}),{'Authorization':'Basic '+base64.b64encode(cookie).decode()})
  response=connection.getresponse();result=json.loads(response.read(4*1024*1024),parse_float=decimal.Decimal)
  if response.status!=200 or result.get('error'):raise RuntimeError(method+': '+str(result.get('error')))
  return result['result']
 except (OSError,http.client.HTTPException) as error:raise RuntimeError(method+': RPC unavailable') from error
 finally:connection.close()

def stop():
 global proc
 if proc and proc.poll() is None:
  rpc('stop');proc.wait(timeout=30)
 proc=None
def start(*,load_wallet=True,**changes):
 global proc
 stop();settings.update(changes)
 (root/'bitcoin.conf').write_text('\n'.join(k+'='+str(v) for k,v in settings.items())+'\n')
 with (root/'console.log').open('ab') as log:proc=subprocess.Popen([str(a.core_bin/'bitcoind'),f'-datadir={root}','-regtest','-server=1','-listen=0','-connect=0','-dnsseed=0',f'-rpcport={port}'],stdout=log,stderr=subprocess.STDOUT)
 end=time.monotonic()+30
 while True:
  try:rpc('getblockchaininfo');break
  except RuntimeError:
   if proc.poll() is not None or time.monotonic()>end:raise
   time.sleep(.1)
 if load_wallet and (root/'regtest/wallets/policy').exists():
  if 'policy' not in rpc('listwallets'):rpc('loadwallet','policy')
def vint(n):
 return bytes([n]) if n<253 else b'\xfd'+struct.pack('<H',n) if n<=65535 else b'\xfe'+struct.pack('<I',n)
def push(data):
 n=len(data);return (bytes([n]) if n<76 else b'\x4c'+bytes([n]) if n<=255 else b'\x4d'+struct.pack('<H',n) if n<=65535 else b'\x4e'+struct.pack('<I',n))+data
def signed(outputs,fee=10000):
 coin=max((item for item in rpc('listunspent',1,9999999,[],True,wallet=True) if item['spendable']),key=lambda item:item['amount'])
 value=int(coin['amount']*100000000)
 change=bytes.fromhex(rpc('getaddressinfo',rpc('getnewaddress','','bech32',wallet=True),wallet=True)['scriptPubKey'])
 outputs=[(value-sum(v for v,_ in outputs)-fee,change)]+outputs
 raw=struct.pack('<I',2)+b'\x01'+bytes.fromhex(coin['txid'])[::-1]+struct.pack('<I',coin['vout'])+b'\x00'+b'\xfd\xff\xff\xff'+vint(len(outputs))
 for value,script in outputs:raw+=struct.pack('<Q',value)+vint(len(script))+script
 raw+=b'\x00'*4
 result=rpc('signrawtransactionwithwallet',raw.hex(),wallet=True);assert result['complete'];return result['hex']
def record(case,raw,allowed,reason=None,mine=True):
 result=rpc('testmempoolaccept',[raw])[0]
 assert result['allowed']==allowed,(case,result)
 if not allowed and reason:assert reason in result.get('reject-reason',''),(case,result)
 item={'case':case,'allowed':allowed,'txid':result['txid'],'settings':dict(settings)}
 if allowed:
  assert rpc('sendrawtransaction',raw)==result['txid'];assert result['txid'] in rpc('getrawmempool')
  if mine:rpc('generatetoaddress',1,mine_address);assert result['txid'] not in rpc('getrawmempool');item['confirmed']=True
 else:item['reject_reason']=result['reject-reason']
 results.append(item);print('PASS '+case,flush=True);return result['txid']
try:
 start();version=rpc('getnetworkinfo')['subversion'];modern=rpc('getnetworkinfo')['version']>=300000;data_reason='datacarrier' if modern else 'scriptpubkey';rpc('createwallet','policy');mine_address=rpc('getnewaddress','','bech32',wallet=True);rpc('generatetoaddress',201,mine_address)
 record('OP_RETURN script exactly 42 bytes',signed([(0,b'\x6a'+push(b'x'*40))]),True)
 oversized=signed([(0,b'\x6a'+push(b'x'*41))]);record('OP_RETURN script 43 exceeds 42',oversized,False,data_reason)
 block=rpc('generateblock',mine_address,[oversized]);assert rpc('getblock',block['hash'])['tx'][1]==rpc('decoderawtransaction',oversized)['txid'];results[-1]['valid_block_accepted']=True
 start(datacarrier='0');record('datacarrier disabled',signed([(0,b'\x6a\x00')]),False,data_reason)
 start(datacarrier='0',datacarriersize='83');record('JustVerify default off with 83-byte size',signed([(0,b'\x6a\x00')]),False,data_reason)
 start(datacarrier='1');record('enabled OP_RETURN script exactly 83 bytes',signed([(0,b'\x6a'+push(b'x'*80))]),True)
 record('enabled OP_RETURN script 84 exceeds 83',signed([(0,b'\x6a'+push(b'x'*81))]),False,data_reason)
 start(datacarrier='0',datacarriersize='42')
 start(datacarrier='1');record('multiple OP_RETURN within total budget',signed([(0,b'\x6a'+push(b'x'*10)),(0,b'\x6a'+push(b'y'*10))]),modern,None if modern else 'multi-op-return')
 if modern:record('multiple OP_RETURN exceeds total 42-byte budget',signed([(0,b'\x6a'+push(b'x'*20)),(0,b'\x6a'+push(b'y'*20))]),False,'datacarrier')
 pub=bytes.fromhex(rpc('getaddressinfo',mine_address,wallet=True)['pubkey']);bare=b'\x51'+push(pub)+b'\x51\xae'
 record('bare multisig enabled',signed([(100000,bare)]),True)
 start(permitbaremultisig='0');record('bare multisig disabled',signed([(100000,bare)]),False,'bare-multisig')
 script=bytes.fromhex(rpc('getaddressinfo',rpc('getnewaddress','','bech32',wallet=True),wallet=True)['scriptPubKey'])
 record('P2WPKH dust 293 at 3 sat/vB',signed([(293,script)]),False,'dust');record('P2WPKH dust boundary 294',signed([(294,script)]),True)
 start(dustrelayfee='0.00006');record('P2WPKH dust 587 at 6 sat/vB',signed([(587,script)]),False,'dust');record('P2WPKH dust boundary 588',signed([(588,script)]),True)
 start(dustrelayfee='0');record('dust fee zero permits 1 sat',signed([(1,script)]),True)
 start(minrelaytxfee='0.00005');record('5 sat/vB minimum rejects low fee',signed([],fee=100),False,'min relay fee')
 record('5 sat/vB minimum accepts funded fee',signed([],fee=10000),True)
 start(minrelaytxfee='0.00001');pending=signed([]);txid=record('persistmempool stores real transaction',pending,True,mine=False)
 rpc('unloadwallet','policy',False)
 start(load_wallet=False);assert txid in rpc('getrawmempool');results.append({'case':'persistmempool=1 restart','txid':txid,'present':True})
 start(load_wallet=False,persistmempool='0');assert txid not in rpc('getrawmempool');results.append({'case':'persistmempool=0 restart','txid':txid,'present':False})
 rpc('generateblock',mine_address,[pending])
 start(persistmempool='1',blockmintxfee='0.001');pending=signed([],fee=1000);txid=record('block fee policy permits mempool',pending,True,mine=False)
 rpc('generatetoaddress',1,mine_address);assert txid in rpc('getrawmempool');results.append({'case':'high blockmintxfee omits low-fee mempool tx','txid':txid})
 start(blockmintxfee='0.00001');rpc('generatetoaddress',1,mine_address);assert txid not in rpc('getrawmempool');results.append({'case':'lower blockmintxfee mines retained tx','txid':txid})
 start(acceptnonstdtxn='1',datacarrier='0');record('regtest standardness disabled permits otherwise rejected data',signed([(0,b'\x6a\x00')]),True)
 start(acceptnonstdtxn='0',datacarrier='1',mempoolexpiry='1');pending=signed([]);txid=record('expiry transaction initially present',pending,True,mine=False)
 rpc('unloadwallet','policy',False)
 start(load_wallet=False,mocktime=str(int(time.time())+7200));assert txid not in rpc('getrawmempool');results.append({'case':'one-hour expiry excludes saved tx after two-hour clock advance without wallet reacceptance','txid':txid})
 rpc('generateblock',mine_address,[pending])
 start(mocktime='0',maxmempool='5',datacarriersize='90010')
 submitted=[]
 for index in range(80):
  raw=signed([(0,b'\x6a'+push(b'x'*90000))],fee=100000+index*30000)
  txid=rpc('sendrawtransaction',raw);submitted.append(txid)
 mempool=rpc('getmempoolinfo');remaining=rpc('getrawmempool')
 assert mempool['maxmempool']==5000000 and mempool['usage']<=5000000
 assert submitted[0] not in remaining and submitted[-1] in remaining and mempool['mempoolminfee']>mempool['minrelaytxfee']
 results.append({'case':'5 MB pressure evicts lower fee and retains highest fee real signed transactions','submitted':len(submitted),'remaining':len(remaining),'usage':mempool['usage'],'maxmempool':mempool['maxmempool'],'mempoolminfee':str(mempool['mempoolminfee']),'first_txid':submitted[0],'last_txid':submitted[-1]})
 print('PASS expiry and actual 5 MB mempool pressure eviction',flush=True)
 report={'status':'PASS','core':version,'binary_sha256':hashlib.sha256((a.core_bin/'bitcoind').read_bytes()).hexdigest(),'network':'regtest','test_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'cases':results,'height':rpc('getblockcount'),'tip':rpc('getbestblockhash'),'not_run':['electrs in this policy-only test','all remaining policy semantics','public network propagation'],'private_state':str(root)}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n')
finally:stop()
