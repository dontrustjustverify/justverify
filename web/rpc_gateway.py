"""Per-client node queries and explicitly granted watch-only wallet access."""
import fcntl,asyncio,base64,hashlib,hmac,json,os,pathlib,secrets,time
from aiohttp import web,ClientSession,ClientTimeout

READ_METHODS=frozenset(('getblockchaininfo','getnetworkinfo','getmempoolinfo','getblockcount','getblockhash','getblockheader','getblock','getrawtransaction','gettxout','getrawmempool','estimatesmartfee','uptime'))
class Clients:
 def __init__(self,path,atomic):self.path=path;self.atomic=atomic
 def records(self):return json.loads(self.path.read_text()) if self.path.exists() else {}
 def lock(self):
  file=self.path.with_suffix('.lock').open('a');os.chmod(file.name,0o600);fcntl.flock(file,fcntl.LOCK_EX);return file
 def create(self,label):
  with self.lock():return self._create(label)
 def _create(self,label):
  if not isinstance(label,str) or not 1<=len(label)<=64 or any(ord(c)<32 or ord(c)==127 for c in label):raise ValueError('invalid client label')
  records=self.records()
  if sum(not r['revoked'] for r in records.values())>=16:raise ValueError('active client limit reached')
  identifier=secrets.token_hex(16);secret=secrets.token_hex(24)
  records[identifier]={'label':label,'hash':hashlib.sha256(secret.encode()).hexdigest(),'revoked':False,'created':int(time.time()),'scope':'node-read'}
  self.atomic(self.path,json.dumps(records));return {'id':identifier,'password':secret,'label':label,'scope':'node-read'}
 def revoke(self,identifier):
  with self.lock():return self._revoke(identifier)
 def _revoke(self,identifier):
  records=self.records()
  if identifier not in records:raise ValueError('unknown client')
  records[identifier]['revoked']=True;self.atomic(self.path,json.dumps(records))
 def list(self):return [{'id':key,**{k:v for k,v in value.items() if k!='hash'}} for key,value in self.records().items()]
 def authenticate(self,authorization):
  try:
   kind,encoded=authorization.split(' ',1)
   if kind!='Basic' or len(encoded)>512:return None
   identifier,secret=base64.b64decode(encoded,validate=True).decode('ascii').split(':',1)
   record=self.records().get(identifier)
   if record and not record['revoked'] and hmac.compare_digest(record['hash'],hashlib.sha256(secret.encode()).hexdigest()):return identifier
  except (ValueError,UnicodeError):pass
  return None

class Gateway:
 def __init__(self,clients,profile=pathlib.Path('/etc/justverify/profile.json'),origin=None):
  self.clients=clients;self.profile=profile;self.origin=origin;self.calls={};self.inflight=0
 async def rpc(self,request):
  if 'Origin' in request.headers and request.headers['Origin']!=self.origin:raise web.HTTPForbidden(text='RPC browser Origin rejected.')
  identifier=self.clients.authenticate(request.headers.get('Authorization',''))
  if not identifier:raise web.HTTPUnauthorized(headers={'WWW-Authenticate':'Basic realm="JustVerify node"'})
  now=time.monotonic();self.calls={key:[t for t in times if now-t<60] for key,times in self.calls.items() if any(now-t<60 for t in times)}
  calls=self.calls.setdefault(identifier,[])
  if len(calls)>=30 or self.inflight>=4:raise web.HTTPTooManyRequests()
  calls.append(now)
  try:body=await request.json()
  except ValueError:raise web.HTTPBadRequest()
  if not isinstance(body,dict) or set(body)-{'jsonrpc','id','method','params'} or 'id' not in body or isinstance(body['id'],(dict,list,bool)) or body.get('jsonrpc','1.0') not in ('1.0','2.0') or not isinstance(body.get('params',[]),(list,dict)):raise web.HTTPBadRequest()
  if not isinstance(body.get('method'),str):raise web.HTTPBadRequest()
  from watch_only import WatchOnly
  wallet_methods={'listwallets','listwalletdir','importdescriptors'}|WatchOnly.READ_METHODS
  if body['method'] in wallet_methods or body['method'] in WatchOnly.TRANSACTION_METHODS:
   from wallet_gateway import WalletAccess
   from watch_only import WalletBoundaryError
   self.inflight+=1
   try:
    access=WalletAccess(self.clients,self.profile,identifier)
    result=await access.dispatch(body['method'],body.get('params',[]),request.match_info.get('wallet'))
    access.check()
    value={'result':result,'id':body['id']}
    if body.get('jsonrpc')=='2.0':value['jsonrpc']='2.0'
    else:value['error']=None
    return web.json_response(value)
   except web.HTTPException:raise
   except WalletBoundaryError:raise web.HTTPForbidden(text='Wallet request refused by watch-only policy.')
   except Exception:raise web.HTTPBadGateway(text='Local wallet is unavailable.')
   finally:self.inflight-=1
  if body['method'] not in READ_METHODS or request.match_info.get('wallet') is not None:raise web.HTTPForbidden(text='RPC method is outside this client profile.')
  self.inflight+=1
  try:
   profile=json.loads(self.profile.read_text());port=profile['rpc_port']
   if type(port) is not int or not 1<=port<=65535:raise ValueError('invalid local profile')
   credential=pathlib.Path(profile['cookie']).read_bytes().strip()
   if not credential or len(credential)>1024:raise ValueError('invalid local credential')
   headers={'Authorization':'Basic '+base64.b64encode(credential).decode()}
   async with ClientSession(timeout=ClientTimeout(total=15)) as session:
    async with session.post(f'http://127.0.0.1:{port}/',json=body,headers=headers,allow_redirects=False) as response:
     payload=bytearray()
     async for part in response.content.iter_chunked(65536):
      payload.extend(part)
      if len(payload)>4*1024*1024:raise web.HTTPBadGateway(text='RPC response exceeds client limit.')
     value=json.loads(payload)
     if not isinstance(value,dict) or ('result' not in value and 'error' not in value):raise ValueError('invalid upstream response')
     # Recheck revocation after an in-flight query before returning private node data.
     if self.clients.authenticate(request.headers.get('Authorization',''))!=identifier:raise web.HTTPUnauthorized()
     return web.json_response(value)
  except web.HTTPException:raise
  except Exception:raise web.HTTPBadGateway(text='Local node RPC is unavailable.')
  finally:self.inflight-=1
