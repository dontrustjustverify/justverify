#!/usr/bin/env python3
"""Real isolated Core wallet boundary tests; never prints descriptors or credentials."""
import asyncio,base64,hashlib,json,pathlib,secrets,socket,subprocess,sys,tempfile,time
import aiohttp
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'web'))
from watch_only import WatchOnly,WalletBoundaryError

async def run(version):
 binary=pathlib.Path.home()/'core-matrix'/version/('bitcoin-'+version)/'bin/bitcoind'
 release=next(r for r in json.loads((ROOT/'catalog/releases.json').read_text())['releases'] if r['version']==version)
 assert hashlib.sha256(binary.read_bytes()).hexdigest()==release['arm64_binary_sha256']
 work=pathlib.Path(tempfile.mkdtemp(prefix='jv-watch-'+version+'-'));data=work/'data';data.mkdir(mode=0o700)
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 args=[str(binary),f'-datadir={data}','-regtest','-server','-listen=0','-connect=0','-dnsseed=0','-keypool=1',f'-rpcport={port}','-printtoconsole=0']
 process=None
 async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),connector=aiohttp.TCPConnector(force_close=True)) as session:
  async def rpc(method,params,wallet=None):
   cookie=(data/'regtest/.cookie').read_bytes().strip()
   route='/' if wallet is None else '/wallet/'+wallet
   async with session.post(f'http://127.0.0.1:{port}'+route,headers={'Authorization':'Basic '+base64.b64encode(cookie).decode()},json={'jsonrpc':'1.0','id':1,'method':method,'params':params}) as response:
    value=await response.json()
    if value.get('error'):raise RuntimeError('Core RPC failed: '+str(value['error']['code']))
    return value['result']
  async def start():
   p=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   for _ in range(200):
    try:await rpc('getblockchaininfo',[]);return p
    except (OSError,aiohttp.ClientError,RuntimeError):
     if p.poll() is not None:raise RuntimeError('Core startup failed')
     await asyncio.sleep(.05)
   p.terminate();p.wait(timeout=30);raise RuntimeError('Core startup timeout')
  try:
   process=await start();a=WatchOnly(rpc,'a'*32);b=WatchOnly(rpc,'b'*32)
   await a.provision();await b.provision();await a.provision()
   # Separate regtest-only key wallet supplies public descriptors and private-key rejection input.
   await rpc('createwallet',{'wallet_name':'test-key-source','descriptors':True})
   address=await rpc('getnewaddress',[], 'test-key-source')
   public=(await rpc('getaddressinfo',[address],'test-key-source'))['desc']
   # Generate a disposable test WIF in memory; Core22 cannot export private descriptors.
   raw=b'\xef'+secrets.token_bytes(32)+b'\x01';raw+=hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
   number=int.from_bytes(raw,'big');encoded='';alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
   while number:number,remainder=divmod(number,58);encoded=alphabet[remainder]+encoded
   private='wpkh('+encoded+')'
   before=await a.read('listdescriptors',[])
   assert await a.read('listdescriptors',[False])==before
   try:await a.import_descriptors([{'desc':public,'timestamp':'now'},{'desc':private,'timestamp':'now'}])
   except WalletBoundaryError:pass
   else:raise AssertionError('Private descriptor accepted')
   assert await a.read('listdescriptors',[])==before
   assert all(r['success'] for r in await a.import_descriptors([{'desc':public,'timestamp':'now'}]))
   await rpc('generatetoaddress',[1,address])
   assert (await a.read('getbalances',[]))!= (await b.read('getbalances',[]))
   assert (await b.read('listdescriptors',[]))['descriptors']==[]
   for method,params in [('importprivkey',[]),('listdescriptors',[True]),('backupwallet',['/tmp/no-export'])]:
    try:await a.read(method,params)
    except WalletBoundaryError:pass
    else:raise AssertionError('Forbidden wallet operation accepted')
   snapshot=await a.read('getbalances',[])
   await rpc('stop',[]);process.wait(timeout=30);process=await start()
   await a.provision();assert await a.read('getbalances',[])==snapshot;await b.verify()
   # A preexisting private-key wallet at the assigned name must never be adopted.
   c=WatchOnly(rpc,'c'*32);await rpc('createwallet',{'wallet_name':c.name,'descriptors':True})
   try:await c.provision()
   except WalletBoundaryError:pass
   else:raise AssertionError('Private wallet adopted')
  finally:
   if process and process.poll() is None:
    try:await rpc('stop',[])
    finally:
     await session.close()
     if process.poll() is None:process.terminate()
     process.wait(timeout=30)
 print(json.dumps({'version':version,'status':'PASS','checks':['watch-only creation','idempotent provision','whole-batch private-key rejection','public import','isolated balances/descriptors','forbidden exports','actual Core restart','unsafe existing wallet rejected','clean shutdown']}),flush=True)

async def main():
 for version in sys.argv[1:]:await run(version)
asyncio.run(main())
