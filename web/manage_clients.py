#!/usr/bin/env python3
"""Fixed non-root local-console client management. Secrets go only to the caller's popup."""
import asyncio,json,os,pathlib,sys
from rpc_gateway import Clients
from server import atomic

def main():
 if os.geteuid()==0 or len(sys.argv)!=1:raise ValueError('fixed non-root helper required')
 state=pathlib.Path('/var/lib/justverify/web')
 if state.is_symlink() or state.stat().st_uid!=os.geteuid() or state.stat().st_mode&0o077:raise ValueError('private owner state required')
 if not (state/'admin.json').is_file():raise ValueError('owner enrollment required')
 raw=sys.stdin.buffer.read(4097)
 if len(raw)>4096:raise ValueError('oversized request')
 request=json.loads(raw);clients=Clients(state/'rpc-clients.json',atomic)
 if isinstance(request,dict) and request.get('action')=='remote_rpc' and set(request)=={'action','request'}:
  import aiohttp
  async def remote():
   async with aiohttp.ClientSession(connector=aiohttp.UnixConnector(path=str(state/'remote-control.sock')),timeout=aiohttp.ClientTimeout(total=20)) as session:
    async with session.post('http://localhost/remote-rpc',json=request['request']) as response:
     if response.status!=200:raise ValueError('Remote setting refused')
     return await response.json()
  return asyncio.run(remote())
 if request=={'action':'list'}:return clients.list()
 if isinstance(request,dict) and set(request)=={'action','label'} and request['action']=='create':
  result=clients.create(request['label'])
  try:
   from rpc_qr import quick_connect
   result['quick_connect']=quick_connect(result)
  except (OSError,ValueError):result['quick_connect']=None
  return result
 if isinstance(request,dict) and set(request)=={'action','id'} and request['action']=='revoke' and isinstance(request['id'],str):clients.revoke(request['id']);return {'revoked':True}
 if isinstance(request,dict) and request.get('action') in ('preview_watch_only','grant_watch_only','preview_transactions','grant_transactions'):
  from wallet_gateway import WalletAccess
  expected={'action','id'} if request['action'].startswith('preview_') else {'action','id','profile_hash'}
  if set(request)!=expected:raise ValueError('invalid grant request')
  access=WalletAccess(clients,pathlib.Path('/etc/justverify/profile.json'),request['id'],grant=request['action'] in ('preview_watch_only','grant_watch_only'))
  if request['action'].startswith('preview_'):return {'profile_hash':access.digest,'version':access.profile['version'],'network':access.profile['network'],'wallet':access.wallet.name,'transactions':request['action']=='preview_transactions'}
  if request['profile_hash']!=access.digest:raise ValueError('profile changed after review')
  return asyncio.run(access.enable_transactions() if request['action']=='grant_transactions' else access.grant())
 raise ValueError('unsupported request')
if __name__=='__main__':
 try:print(json.dumps({'ok':True,'result':main()}))
 except Exception:print(json.dumps({'ok':False,'error':'Client request refused; verify owner enrollment and input.'}));sys.exit(1)
