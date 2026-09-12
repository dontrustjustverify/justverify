#!/usr/bin/env python3
"""Submit actual tagged coinbase blocks to isolated Core (no peers, txindex or funds)."""
import argparse,hashlib,json,os,pathlib,socket,struct,subprocess,tempfile,time
R=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--core',type=pathlib.Path,default=R/'.cache/core/31.1/arm64-apple-darwin/bitcoin-31.1/bin');p.add_argument('--binary',type=pathlib.Path,default=R/'target/debug/justverify');a=p.parse_args()
sha=lambda b:hashlib.sha256(hashlib.sha256(b).digest()).digest()
with socket.socket() as reserve:reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
with tempfile.TemporaryDirectory(prefix='jv-miner-') as tmp:
 d=pathlib.Path(tmp);os.chmod(d,0o700);core=manager=None
 def cli(*args):return subprocess.check_output([str(a.core/'bitcoin-cli'),'-regtest',f'-datadir={d}',f'-rpcport={port}','-rpcwait',*map(str,args)],text=True).strip()
 def snapshot():
  with socket.socket(socket.AF_UNIX) as c:
   c.connect(str(d/'manager.sock'));c.sendall(b'snapshot\n');out=b''
   while chunk:=c.recv(65536):out+=chunk
   return json.loads(out)
 def await_tip(tip):
  for _ in range(150):
   try:
    s=snapshot();b=s['rpc']['recentblocks']['value']
    if b and b[0]['hash']==tip and not s['rpc']['recentblocks']['error']:return b
   except (OSError,KeyError,TypeError):pass
   time.sleep(.1)
  raise AssertionError('collector did not publish submitted block')
 def mine(tag):
  prev=cli('getbestblockhash');head=json.loads(cli('getblockheader',prev));height=head['height']+1
  # BIP34 script number, then inert coinbase tag. One OP_TRUE reward output.
  number=height.to_bytes((height.bit_length()+7)//8,'little')
  if number[-1]&128:number+=b'\0'
  height_script=bytes([0x50+height]) if 1<=height<=16 else bytes([len(number)])+number
  script=height_script+tag
  tx=struct.pack('<I',2)+b'\x01'+b'\0'*32+b'\xff'*4+bytes([len(script)])+script+b'\xff'*4+b'\x01'+struct.pack('<Q',50*100_000_000)+b'\x01\x51'+b'\0'*4
  bits=int(head['bits'],16);target=(bits&0x007fffff)<<(8*((bits>>24)-3))
  header=struct.pack('<I',0x20000000)+bytes.fromhex(prev)[::-1]+sha(tx)+struct.pack('<II',max(head['time']+1,int(time.time())),bits)
  for nonce in range(1000000):
   candidate=header+struct.pack('<I',nonce)
   if int.from_bytes(sha(candidate),'little')<=target:break
  else:raise AssertionError('regtest proof of work not found')
  result=cli('submitblock',(candidate+b'\x01'+tx).hex());assert result=='',result
  tip=sha(candidate)[::-1].hex();assert cli('getbestblockhash')==tip;return tip
 try:
  core=subprocess.Popen([str(a.core/'bitcoind'),'-regtest',f'-datadir={d}',f'-rpcport={port}','-listen=0','-networkactive=0','-disablewallet','-txindex=0','-server=1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  cli('getblockchaininfo')
  manager=subprocess.Popen([str(a.binary),'daemon','--cookie',str(d/'regtest/.cookie'),'--rpc-port',str(port),'--socket',str(d/'manager.sock')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  records=[]
  for tag,status,name in [(b'/LUXOR/','identified','Luxor'),(b'private solo node','unknown',None),(b'/LUXOR//Noderunners/','ambiguous',None)]:
   tip=mine(tag);blocks=await_tip(tip);miner=blocks[0]['miner'];assert miner['status']==status,(status,miner)
   assert miner.get('name')==name;records.append({'hash':tip,'miner':miner})
  stamp=blocks[0]['miner']['checked'];time.sleep(2.5);assert await_tip(tip)[0]['miner']['checked']==stamp,'unchanged tip fetched twice'
  cli('invalidateblock',tip);newtip=mine(b'/Noderunners/');blocks=await_tip(newtip);assert blocks[0]['miner']['name']=='Noderunners';assert tip not in [b['hash'] for b in blocks]
  assert json.loads(cli('getindexinfo'))=={},'txindex unexpectedly enabled'
  print(json.dumps({'status':'PASS','core':cli('--version').splitlines()[0],'network':'isolated regtest','txindex':False,'checks':['actual tagged coinbase + valid proof of work + submitblock','unknown','ambiguous','unchanged tip cache','reorg miner reassignment'],'blocks':records,'reorg_tip':newtip}))
 finally:
  if manager and manager.poll() is None:manager.terminate();manager.wait(timeout=10)
  if core and core.poll() is None:cli('stop');core.wait(timeout=15)
