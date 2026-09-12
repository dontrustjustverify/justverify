"""Profile-bound wallet authorization; no external wallet path reaches Core."""
import asyncio,base64,hashlib,json,pathlib
from aiohttp import ClientSession,ClientTimeout,web
from watch_only import WatchOnly,WalletBoundaryError

class WalletAccess:
 def __init__(self,clients,profile,identifier,grant=False):
  self.clients=clients;self.path=profile;self.identifier=identifier;self.granting=grant
  self.snapshot=profile.read_bytes();self.profile=json.loads(self.snapshot)
  self.profile_digest=hashlib.sha256(self.snapshot).hexdigest()
  self.registration=profile.parent/'node-ready.json'
  ready=json.loads(self.registration.read_bytes());self.uuid=ready['uuid']
  if not isinstance(self.uuid,str) or not self.uuid or ready['configs']['profile.json']!=self.profile_digest:raise web.HTTPConflict(text='Profile registration incomplete.')
  self.digest=hashlib.sha256(self.snapshot+b'\0'+self.uuid.encode()).hexdigest()
  if self.profile.get('watch_only') is not True:raise web.HTTPConflict(text='Select a watch-only profile first.')
  self.wallet=WatchOnly(self.call,identifier)
  self.check()
 def check(self):
  record=self.clients.records().get(self.identifier)
  if not record or record['revoked']:raise web.HTTPUnauthorized()
  if self.path.read_bytes()!=self.snapshot:raise web.HTTPConflict(text='Node profile changed; retry after selection completes.')
  ready=json.loads(self.registration.read_bytes())
  if ready['uuid']!=self.uuid or ready['configs']['profile.json']!=self.profile_digest:raise web.HTTPConflict(text='Registered volume or profile changed.')
  if not self.granting and (record.get('scope')!='watch-only' or record.get('wallet_profile')!=self.digest):
   raise web.HTTPForbidden(text='Wallet permission does not cover this profile.')
 def finish_grant(self):
  with self.clients.lock():
   self.check();records=self.clients.records();record=records[self.identifier]
   record.update(scope='watch-only',wallet_profile=self.digest,wallet=self.wallet.name)
   record['wallet_profiles']=sorted(set(record.get('wallet_profiles',[])+[self.digest]))
   self.clients.atomic(self.clients.path,json.dumps(records))
  return {'scope':'watch-only','wallet':self.wallet.name,'version':self.profile['version'],'network':self.profile['network']}
 async def call(self,method,params,wallet=None):
  self.check();port=self.profile['rpc_port']
  if type(port) is not int or not 1<=port<=65535:raise ValueError('invalid local port')
  if wallet not in (None,self.wallet.name):raise WalletBoundaryError('Wrong wallet')
  credential=pathlib.Path(self.profile['cookie']).read_bytes().strip()
  if not credential or len(credential)>1024:raise ValueError('invalid cookie')
  route='/' if wallet is None else '/wallet/'+wallet
  async with ClientSession(timeout=ClientTimeout(total=15)) as session:
   async with session.post(f'http://127.0.0.1:{port}'+route,headers={'Authorization':'Basic '+base64.b64encode(credential).decode()},json={'jsonrpc':'1.0','id':1,'method':method,'params':params},allow_redirects=False) as response:
    payload=bytearray()
    async for part in response.content.iter_chunked(65536):
     payload.extend(part)
     if len(payload)>4*1024*1024:raise web.HTTPBadGateway(text='Wallet response too large.')
    value=json.loads(payload)
  self.check()
  if not isinstance(value,dict) or value.get('error') is not None or 'result' not in value:raise WalletBoundaryError('Wallet operation failed')
  return value['result']
 async def grant(self):
  async with asyncio.timeout(15):
   record=self.clients.records()[self.identifier]
   if self.digest in record.get('wallet_profiles',[]) or record.get('wallet_profile')==self.digest:
    loaded=await self.call('listwallets',[])
    existing=await self.call('listwalletdir',[])
    if self.wallet.name not in loaded and not any(w.get('name')==self.wallet.name for w in existing['wallets']):
     raise web.HTTPConflict(text='Previously assigned wallet data is missing; restore it before granting access.')
   await self.wallet.provision()
  return self.finish_grant()
 async def enable_transactions(self):
  async with asyncio.timeout(15):await self.wallet.verify()
  with self.clients.lock():
   self.check();records=self.clients.records();record=records[self.identifier]
   record['transaction_profiles']=sorted(set(record.get('transaction_profiles',[])+[self.digest]))
   self.clients.atomic(self.clients.path,json.dumps(records))
  return {'transactions':True,'wallet':self.wallet.name}
 async def dispatch(self,method,params,path_wallet=None):
  if path_wallet is not None and path_wallet!=self.wallet.name:raise web.HTTPForbidden(text='Wallet is not assigned to this client.')
  async with asyncio.timeout(15):
   if method in WatchOnly.TRANSACTION_METHODS:
    if self.digest not in self.clients.records()[self.identifier].get('transaction_profiles',[]):raise web.HTTPForbidden(text='Transaction permission must be explicitly granted.')
    return await self.wallet.transaction(method,params)
   if method in ('listwallets','listwalletdir'):
    if params not in ([],{}):raise WalletBoundaryError('Unexpected wallet list parameters')
    await self.wallet.verify()
    return [self.wallet.name] if method=='listwallets' else {'wallets':[{'name':self.wallet.name}]}
   if method=='importdescriptors':
    if isinstance(params,list) and len(params)==1:requests=params[0]
    elif isinstance(params,dict) and set(params)=={'requests'}:requests=params['requests']
    else:raise WalletBoundaryError('Invalid import request')
    return await self.wallet.import_descriptors(requests)
   return await self.wallet.read(method,params)
