#!/usr/bin/env python3
"""Actual Core/electrs/mempool/SQL/HTTP integration on a fresh regtest only."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request

p=argparse.ArgumentParser()
p.add_argument('--state',type=Path,required=True)
p.add_argument('--core',type=Path,required=True)
p.add_argument('--electrs',type=Path,required=True)
p.add_argument('--bundle',type=Path,required=True)
p.add_argument('--hold',type=int,default=0)
p.add_argument('--version',default='31.1')
a=p.parse_args()
ROOT=Path(__file__).resolve().parents[1]
assert os.geteuid()!=0 and not a.state.exists() and a.state.name.startswith('jv-mempool-test-')
a.state.mkdir(mode=0o700)
for name in ('core','runtime','mempool'): (a.state/name).mkdir(mode=0o700)
processes=[];logs=[]
result={'status':'FAIL','network':'isolated regtest','checks':[]}

def start(args,name,env=None):
 log=(a.state/(name+'.log')).open('ab');logs.append(log)
 process=subprocess.Popen([str(x) for x in args],stdout=log,stderr=log,env=env);processes.append(process);return process

def cli(method,*args):
 values=[json.dumps(v) if not isinstance(v,str) else v for v in args]
 command=[str(a.core/'bitcoin-cli'),'-regtest','-datadir='+str(a.state/'core'),'-rpcport=19643',method,*values]
 r=subprocess.run(command,capture_output=True,text=True,timeout=30)
 if r.returncode: raise RuntimeError(method+' failed')
 try:return json.loads(r.stdout)
 except ValueError:return r.stdout.strip()

def wait(check,seconds=120):
 end=time.monotonic()+seconds;last=None
 while time.monotonic()<end:
  try:
   v=check()
   if v:return v
  except (OSError,ValueError,KeyError,RuntimeError) as error:last=type(error).__name__
  time.sleep(.5)
 raise TimeoutError('Actual integration readiness: '+str(last))

def http(path,body=None,headers=None):
 r=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:13006'+path,data=body,headers=headers or {}),timeout=10)
 data=r.read()
 try:return json.loads(data)
 except ValueError:return data.decode()

try:
 core_command=[a.core/'bitcoind','-regtest','-datadir='+str(a.state/'core'),'-server=1','-txindex=1','-connect=0','-dnsseed=0','-bind=127.0.0.1','-port=19644','-rpcport=19643','-maxmempool=64','-dbcache=32']
 core=start(core_command,'core')
 wait(lambda:cli('getblockchaininfo'))
 cli('createwallet','mempool-integration')
 address=cli('getnewaddress')
 cli('generatetoaddress',105,address)
 index_command=[a.electrs,'--skip-default-conf-files','--network=regtest','--daemon-dir='+str(a.state/'core'),'--db-dir='+str(a.state/'index'),'--daemon-rpc-addr=127.0.0.1:19643','--daemon-p2p-addr=127.0.0.1:19644','--electrum-rpc-addr=127.0.0.1:19601','--monitoring-addr=127.0.0.1:19624']
 index=start(index_command,'electrs')
 assert cli('getnetworkinfo')['subversion'].startswith('/Satoshi:'+a.version+'.')
 profile={'version':a.version,'network':'regtest','cookie':str(a.state/'core/regtest/.cookie'),'rpc_port':19643}
 (a.state/'profile.json').write_text(json.dumps(profile))
 proxy=start(['/opt/justverify/venv/bin/python',ROOT/'web/mempool_proxy.py','--bundle',a.bundle,'--runtime',a.state/'runtime','--profile',a.state/'profile.json','--port','13006','--backend','http://127.0.0.1:18999'],'proxy')
 def service():return start(['/usr/bin/python3',ROOT/'scripts/mempool_service.py','--bundle',a.bundle,'--runtime',a.state/'runtime','--profile',a.state/'profile.json','--data',a.state/'mempool','--api-port','18999','--web-port','13006','--electrum-port','19601'],'service')
 runner=service()
 wait(lambda:http('/justverify/status')['state']=='running',240)
 assert http('/api/blocks/tip/height')==cli('getblockcount')==105
 assert http('/api/blocks/tip/hash')==cli('getbestblockhash')
 info=http('/api/v1/backend-info');assert info['version']=='3.3.1'
 result['versions']={'core':cli('getnetworkinfo')['subversion'],'mempool':info['version'],'mempool_commit':info['gitCommit']}
 result['checks']+=['actual SQL startup/migrations','Core/electrs-backed HTTP tip agreement']
 receiver=cli('getnewaddress')
 raw=cli('createrawtransaction',[],{receiver:1})
 funded=cli('fundrawtransaction',raw,{'fee_rate':2})
 signed=cli('signrawtransactionwithwallet',funded['hex']);assert signed['complete']
 txid=http('/api/tx',signed['hex'].encode(),{'Content-Type':'text/plain'})
 assert txid in cli('getrawmempool')
 wait(lambda:http('/api/mempool')['count']==1)
 wait(lambda:http('/api/tx/'+txid)['status']['confirmed'] is False)
 wait(lambda:http('/api/address/'+receiver)['mempool_stats']['funded_txo_sum']==100000000)
 fees=http('/api/v1/fees/recommended');assert 'fastestFee' in fees
 result['checks']+=['signed transaction broadcast through local mempool HTTP','Core mempool and unconfirmed explorer transaction','Electrum-backed address lookup and fees']
 block=cli('generatetoaddress',1,address)[0]
 wait(lambda:http('/api/blocks/tip/hash')==block)
 wait(lambda:http('/api/tx/'+txid)['status']['confirmed'])
 wait(lambda:http('/api/address/'+receiver)['chain_stats']['funded_txo_sum']==100000000)
 async def websocket():
  import aiohttp
  async with aiohttp.ClientSession() as c:
   async with c.ws_connect('http://127.0.0.1:13006/api/v1/ws',origin='http://127.0.0.1:13006') as ws:
    await ws.send_json({'action':'init'})
    await ws.send_json({'action':'want','data':['blocks','stats']})
    async with asyncio.timeout(15):
     async for message in ws:
      if message.type==aiohttp.WSMsgType.TEXT:
       value=json.loads(message.data)
       blocks=value.get('blocks',[])+([value['block']] if 'block' in value else [])
       if any(item['id']==block and item['height']==106 for item in blocks):return
    raise AssertionError('No actual block update over WebSocket')
 asyncio.run(websocket())
 result['checks']+=['confirmed transaction and address index','real WebSocket block data']
 for headers in ({'Host':'evil.invalid:13006'},{'Origin':'http://evil.invalid'}):
  try:http('/api/mempool',headers=headers)
  except urllib.error.HTTPError as error:assert error.code==403
  else:raise AssertionError('foreign host/origin accepted')
 for locale in ('en-US','ko','ja'):
  html=http('/'+locale+'/');assert '<app-root' in html and 'justverify-integration.js' in html
 assert 'justverify.patch' in http('/source/')
 runner.terminate();runner.wait(timeout=120)
 runner=service()
 wait(lambda:http('/justverify/status')['state']=='running',180)
 wait(lambda:http('/api/blocks/tip/hash')==block)
 wait(lambda:http('/api/tx/'+txid)['status']['confirmed'])
 # A new cookie and an unavailable Core must not leave a false running status.
 core.terminate();core.wait(timeout=60)
 wait(lambda:http('/justverify/status')['state']=='waiting',30)
 if index.poll() is None:
  index.terminate();index.wait(timeout=60)
 core=start(core_command,'core-restart')
 wait(lambda:cli('getblockchaininfo'))
 wait(lambda:http('/justverify/status')['state']=='waiting',30)
 index=start(index_command,'electrs-restart')
 cli('loadwallet','mempool-integration')
 block=cli('generatetoaddress',1,address)[0]
 wait(lambda:http('/justverify/status')['state']=='running',120)
 wait(lambda:http('/api/blocks/tip/hash')==block)
 assert cli('gettransaction',txid)['confirmations']==2
 assert index.poll() is None
 wait(lambda:http('/api/address/'+receiver)['chain_stats']['funded_txo_sum']==100000000)
 with socket.create_connection(('127.0.0.1',19601),3) as sock:
  sock.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n')
  header=json.loads(sock.makefile('rb').readline())['result']
 assert header['height']==107 and hashlib.sha256(hashlib.sha256(bytes.fromhex(header['hex'])).digest()).digest()[::-1].hex()==block
 assert http('/api/tx/'+txid)['status']['confirmed']
 result['checks']+=['Core outage shown as waiting, cookie refresh and electrs reconnect','new block after Core restart and two wallet confirmations']
 result.update(status='PASS',txid=txid,confirmations=2,core_electrs_mempool_height=107,tip=block)
 result['checks']+=['foreign host and Origin rejection','three real localized frontends','corresponding source access','SQL/cache/backend restart persists confirmed transaction']
 (a.state/'ready').write_text('actual regtest browser inspection ready')
 print(json.dumps(result),flush=True)
 if a.hold:
  end=time.monotonic()+a.hold
  while (a.state/'ready').exists() and time.monotonic()<end:time.sleep(1)
except Exception as error:
 result['error']=type(error).__name__+': '+str(error)
 raise
finally:
 for process in reversed(processes):
  if process.poll() is None:
   process.terminate()
   try:process.wait(timeout=130)
   except subprocess.TimeoutExpired:process.kill();process.wait()
 for log in logs:log.close()
 (a.state/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result),flush=True)
