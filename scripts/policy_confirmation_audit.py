#!/usr/bin/env python3
"""Check retained policy-test transactions against actual blocks, with wallets disabled."""
import base64,hashlib,http.client,json,pathlib,re,socket,subprocess,time
assert socket.gethostname()=='justverify-dev'
root=pathlib.Path(__file__).resolve().parents[1];source=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
releases={r['version']:r for r in json.loads((root/'catalog/releases.json').read_text())['releases']}
for path in sorted((root/'docs/evidence/policy-semantics').glob('*.json')):
 report=json.loads(path.read_text());version=path.stem;assert report['status']=='PASS'
 data=pathlib.Path(report['private_state']);assert data.parent==pathlib.Path('/tmp') and re.fullmatch(r'jv-policy-semantics-[a-z0-9_]+',data.name)
 assert not data.is_symlink() and (data/'regtest/blocks').is_dir() and not (data/'blocks').exists()
 binary=pathlib.Path('/home/builder/core-matrix')/version/f'bitcoin-{version}/bin/bitcoind'
 assert hashlib.sha256(binary.read_bytes()).hexdigest()==report['binary_sha256']==releases[version]['arm64_binary_sha256']
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 def rpc(method,*params):
  connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
  try:
   cookie=(data/'regtest/.cookie').read_bytes().strip();connection.request('POST','/',json.dumps({'id':1,'method':method,'params':list(params)}),{'Authorization':'Basic '+base64.b64encode(cookie).decode()})
   response=connection.getresponse();value=json.loads(response.read(4*1024*1024));assert response.status==200 and not value.get('error');return value['result']
  finally:connection.close()
 with (data/'confirmation-audit.log').open('ab') as log:
  process=subprocess.Popen([str(binary),f'-datadir={data}','-regtest','-server=1','-disablewallet','-persistmempool=0','-listen=0','-connect=0',f'-rpcport={port}'],stdout=log,stderr=subprocess.STDOUT)
 try:
  deadline=time.monotonic()+30
  while True:
   try:chain=rpc('getblockchaininfo');break
   except (OSError,AssertionError):
    if process.poll() is not None or time.monotonic()>deadline:raise
    time.sleep(.1)
  assert chain['bestblockhash']==report['tip'] and chain['blocks']==report['height']
  txids={case['txid'] for case in report['cases'] if 'txid' in case};found={}
  for height in range(chain['blocks'],0,-1):
   blockhash=rpc('getblockhash',height);block=rpc('getblock',blockhash)
   for txid in set(block['tx'])&txids:found[txid]={'blockhash':blockhash,'height':height,'confirmations':chain['blocks']-height+1}
  for case in report['cases']:
   if case.get('confirmed') or case.get('valid_block_accepted'):assert case['txid'] in found,case['case']
   if 'txid' in case:case['final_block_observation']=found.get(case['txid'],{'confirmations':0,'blockhash':None})
  report['confirmation_audit']={'status':'PASS','source_sha256':source,'wallets_disabled':True,'mempool_loading_disabled':True,'confirmed_distinct_txids':len(found),'tip':chain['bestblockhash']}
  path.write_text(json.dumps(report,indent=2)+'\n');print(version+' actual block inclusion PASS',flush=True)
 finally:
  if process.poll() is None:
   try:rpc('stop');process.wait(timeout=30)
   except Exception:process.terminate();process.wait(timeout=30)
