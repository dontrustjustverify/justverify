#!/usr/bin/env python3
"""Wait for authenticated local Core RPC before starting electrs; never log credentials."""
import base64,http.client,json,pathlib,time

def wait_ready(profile,timeout=120):
 config=json.loads(pathlib.Path(profile).read_text());port=config['rpc_port'];network=config['network']
 if type(port) is not int or not 1<=port<=65535:raise ValueError('invalid RPC port')
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  connection=None
  try:
   cookie=pathlib.Path(config['cookie']).read_bytes().strip()
   if not cookie or len(cookie)>1024:raise ValueError('invalid RPC credential')
   connection=http.client.HTTPConnection('127.0.0.1',port,timeout=min(2,max(.1,end-time.monotonic())))
   connection.request('POST','/',json.dumps({'jsonrpc':'1.0','id':'startup','method':'getblockchaininfo','params':[]}),{'Authorization':'Basic '+base64.b64encode(cookie).decode()})
   response=connection.getresponse();body=response.read(1024*1024)
   value=json.loads(body)
   if response.status==200 and value.get('error') is None and value.get('result',{}).get('chain')==network:return
  except (OSError,ValueError,http.client.HTTPException):pass
  finally:
   if connection:connection.close()
  time.sleep(.25)
 raise TimeoutError('local Core RPC not ready; electrs was not started')
if __name__=='__main__':
 import sys
 if len(sys.argv)!=1:raise SystemExit('fixed readiness helper takes no arguments')
 try:wait_ready('/etc/justverify/profile.json')
 except Exception:raise SystemExit('Core RPC readiness failed; credentials omitted')
