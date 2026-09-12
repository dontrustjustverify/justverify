#!/usr/bin/env python3
"""Signed topology and replacement policy; prove rejection reverses on the same graph."""
import argparse,base64,decimal,hashlib,http.client,json,pathlib,socket,struct,subprocess,tempfile,time
p=argparse.ArgumentParser();p.add_argument('--version',required=True);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
ROOT=pathlib.Path(__file__).resolve().parents[1];release=next(r for r in json.loads((ROOT/'catalog/releases.json').read_text())['releases'] if r['version']==a.version)
binary=pathlib.Path('/home/builder/core-matrix')/a.version/f'bitcoin-{a.version}/bin/bitcoind';assert release['verification']=='PASS' and hashlib.sha256(binary.read_bytes()).hexdigest()==release['arm64_binary_sha256']
state=pathlib.Path(tempfile.mkdtemp(prefix='jv-policy-topology-')).resolve();state.chmod(0o700);process=None;address=None;cases=[]
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
options={'acceptnonstdtxn':'0','persistmempool':'1','minrelaytxfee':'0.00001','incrementalrelayfee':'0.00001','datacarriersize':'20000','maxmempool':'64'}
def rpc(method,*params,wallet=False):
 connection=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
 try:
  cookie=(state/'regtest/.cookie').read_bytes().strip();connection.request('POST','/wallet/policy' if wallet else '/',json.dumps({'id':1,'method':method,'params':params},default=str),{'Authorization':'Basic '+base64.b64encode(cookie).decode()})
  response=connection.getresponse();v=json.loads(response.read(4*1024*1024),parse_float=decimal.Decimal)
  if response.status!=200 or v.get('error'):raise RuntimeError(method+': '+str(v.get('error')))
  return v['result']
 except OSError as error:raise RuntimeError('RPC unavailable') from error
 finally:connection.close()
def start(changes=None,clear=True):
 global process
 if process and process.poll() is None:
  if clear and address:rpc('generatetoaddress',1,address);assert rpc('getrawmempool')==[]
  rpc('stop');process.wait(timeout=30)
 if changes:options.update(changes)
 (state/'bitcoin.conf').write_text(''.join(k+'='+v+'\n' for k,v in options.items()))
 with (state/'console.log').open('ab') as log:process=subprocess.Popen([str(binary),f'-datadir={state}','-regtest','-server=1','-listen=0','-connect=0',f'-rpcport={port}'],stdout=log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+30
 while True:
  try:rpc('getblockchaininfo');break
  except RuntimeError:
   if process.poll() is not None or time.monotonic()>deadline:raise
   time.sleep(.1)
 if address and 'policy' not in rpc('listwallets'):rpc('loadwallet','policy')
def vi(n):return bytes([n]) if n<253 else b'\xfd'+struct.pack('<H',n)
def make(coin=None,fee=10000,split=False,payload=0,sequence=0xfffffffd):
 if coin is None:coin=max(rpc('listunspent',1,9999999,[],True,wallet=True),key=lambda c:c['amount'])
 script=bytes.fromhex(rpc('getaddressinfo',address,wallet=True)['scriptPubKey']);value=int(coin['amount']*100000000)-fee
 outputs=[(100000000,script),(value-100000000,script)] if split else [(value,script)]
 if payload:outputs.append((0,b'\x6a\x4d'+struct.pack('<H',payload)+b'x'*payload))
 raw=struct.pack('<I',2)+b'\x01'+bytes.fromhex(coin['txid'])[::-1]+struct.pack('<I',coin['vout'])+b'\x00'+struct.pack('<I',sequence)+vi(len(outputs))
 for amount,code in outputs:raw+=struct.pack('<Q',amount)+vi(len(code))+code
 raw+=b'\x00'*4
 prev=[{'txid':coin['txid'],'vout':coin['vout'],'scriptPubKey':coin['scriptPubKey'],'amount':str(coin['amount'])}]
 signed=rpc('signrawtransactionwithwallet',raw.hex(),prev,wallet=True);assert signed['complete'];return signed['hex']
def output(raw,vout=0):
 tx=rpc('decoderawtransaction',raw);return {'txid':tx['txid'],'vout':vout,'amount':tx['vout'][vout]['value'],'scriptPubKey':tx['vout'][vout]['scriptPubKey']['hex']}
def accept(name,raw,wanted):
 result=rpc('testmempoolaccept',[raw])[0];assert result['allowed']==wanted,(name,result)
 if wanted:assert rpc('sendrawtransaction',raw)==result['txid'] and result['txid'] in rpc('getrawmempool')
 cases.append({'case':name,'allowed':wanted,'txid':result['txid'],'reason':result.get('reject-reason'),'options':dict(options)});print('PASS '+name,flush=True)
try:
 start();rpc('createwallet','policy');address=rpc('getnewaddress','','bech32',wallet=True);rpc('generatetoaddress',110,address)
 modern=int(a.version.split('.')[0])>=31
 count_key='limitclustercount' if modern else 'limitancestorcount'
 start({count_key:'2'})
 parent=make();accept(count_key+' parent',parent,True);child=make(output(parent));accept(count_key+' child',child,True);third=make(output(child));accept(count_key+' third rejected at 2',third,False)
 start({count_key:'3'},clear=False);assert len(rpc('getrawmempool'))==2;accept(count_key+' same third accepted at 3',third,True)
 start({count_key:'64' if modern else '25'})
 size_key='limitclustersize' if modern else 'limitancestorsize'
 start({size_key:'1'});parent=make();accept(size_key+' parent',parent,True);child=make(output(parent),fee=20000,payload=1500);accept(size_key+' aggregate rejected at 1 kB',child,False)
 start({size_key:'101'},clear=False);accept(size_key+' same child accepted at 101 kB',child,True)
 if not modern:
  start({'limitdescendantcount':'2'});parent=make(split=True);accept('descendant parent',parent,True);first=make(output(parent,0));accept('first descendant',first,True);second=make(output(parent,1),fee=50000,payload=12000);accept('second descendant exceeds count; larger than CPFP carve-out',second,False)
  start({'limitdescendantcount':'3'},clear=False);accept('same second descendant accepted at 3',second,True)
  start({'limitdescendantcount':'25','limitdescendantsize':'1'});parent=make();accept('descendant-size parent',parent,True);child=make(output(parent),fee=50000,payload=12000);accept('descendant aggregate exceeds 1 kB without carve-out',child,False)
  start({'limitdescendantsize':'101'},clear=False);accept('same descendant accepted at 101 kB',child,True)
 entries={r['key']:r for r in json.loads((ROOT/'catalog'/f'policy-{a.version}.json').read_text())}
 toggle='mempoolfullrbf' in entries and not entries['mempoolfullrbf']['ignored_or_wallet_only']
 start({'mempoolfullrbf':'0'} if toggle else {})
 coin=max(rpc('listunspent',1,9999999,[],True,wallet=True),key=lambda c:c['amount']);original=make(coin,fee=1000,sequence=0xffffffff);replacement=make(coin,fee=2000,sequence=0xffffffff)
 accept('non-signaling original',original,True);accept('non-signaling replacement under selected RBF mode',replacement,int(a.version.split('.')[0])>=29)
 if toggle:
  start({'mempoolfullrbf':'1'},clear=False);accept('same non-signaling replacement with full RBF enabled',replacement,True)
 start({'incrementalrelayfee':'0.001'})
 coin=max(rpc('listunspent',1,9999999,[],True,wallet=True),key=lambda c:c['amount']);original=make(coin,fee=1000);replacement=make(coin,fee=2000)
 accept('opt-in original',original,True);accept('replacement delta below 100 sat/vB incremental fee',replacement,False)
 start({'incrementalrelayfee':'0.00001'},clear=False);accept('same replacement accepted with 1 sat/vB incremental fee',replacement,True)
 rpc('generatetoaddress',1,address)
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({'status':'PASS','core':a.version,'network':'regtest','binary_sha256':release['arm64_binary_sha256'],'test_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'cases':cases,'height':rpc('getblockcount'),'tip':rpc('getbestblockhash'),'private_state':str(state),'not_run':['remaining whitelist/private-broadcast/block-template limits','all input ranges','other networks']},indent=2)+'\n')
finally:
 if process and process.poll() is None:
  try:rpc('stop');process.wait(timeout=30)
  except Exception:process.terminate();process.wait(timeout=30)
