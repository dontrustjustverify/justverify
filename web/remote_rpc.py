"""Owner-reviewed persistent RPC listener state; interrupted changes fail closed."""
import asyncio,hashlib,json,pathlib,re,secrets,time
from aiohttp import web

class RemoteRPC:
 def __init__(self,state,atomic,application,*,service='rpc',port=28443):
  self.service=service;self.port=port;self.path=state/('remote-'+service+'.json');self.state=state;self.atomic=atomic;self.application=application
  self.runner=None;self.enabled=False;self.plans={};self.lock=asyncio.Lock()
 def saved(self):
  raw=self.path.read_bytes() if self.path.exists() else b''
  if len(raw)>4096:raise ValueError('Remote configuration too large')
  value=json.loads(raw) if raw else {'schema':1,'enabled':False,'phase':'committed'}
  if not isinstance(value,dict) or set(value)!={'schema','enabled','phase'} or type(value['schema']) is not int or value['schema']!=1 or type(value['enabled']) is not bool or value['phase'] not in ('applying','committed'):raise ValueError('Invalid remote configuration')
  return value,hashlib.sha256(raw).hexdigest()
 def status(self):
  value,revision=self.saved()
  try:
   onion=(pathlib.Path('/run/justverify-tor')/(self.service+'.hostname')).read_text().strip()
   if not re.fullmatch(r'[a-z2-7]{56}\.onion',onion):onion=None
  except (OSError,UnicodeError):onion=None
  return {'stored_enabled':value['enabled'],'running':self.enabled,'needs_recovery':value['phase']!='committed' or value['enabled']!=self.enabled,'revision':revision,'onion_host':onion,'onion_port':8332 if self.service=='rpc' else 80,'transport':'HTTP inside Tor to a restricted loopback RPC gateway; HTTPS administration stays separate'}
 async def start(self):
  if self.runner is not None:return
  runner=web.AppRunner(self.application(),access_log=None,shutdown_timeout=5)
  await runner.setup()
  try:await web.TCPSite(runner,'127.0.0.1',self.port).start()
  except BaseException:await runner.cleanup();raise
  self.runner=runner
 async def stop(self):
  self.enabled=False
  runner,self.runner=self.runner,None
  if runner is not None:await runner.cleanup()
 async def restore(self):
  value,_=self.saved()
  if value['phase']=='committed' and value['enabled'] and (self.state/'admin.json').is_file():
   await self.start();self.enabled=True
 async def guarded(self,handler,request):
  if not self.enabled:raise web.HTTPServiceUnavailable(text='Remote RPC is disabled.')
  response=await handler(request)
  if not self.enabled:raise web.HTTPServiceUnavailable(text='Remote RPC was disabled.')
  return response
 async def manage(self,body):
  async with self.lock:
   if not isinstance(body,dict):raise ValueError('Object required')
   if body=={'action':'state'}:return self.status()
   if set(body)=={'action','enabled'} and body['action']=='preview' and type(body['enabled']) is bool:
    current=self.status();now=time.monotonic();self.plans={key:p for key,p in self.plans.items() if p['expires']>now}
    if len(self.plans)>=16:raise ValueError('Too many pending reviews')
    token=secrets.token_urlsafe(32);self.plans[token]={'enabled':body['enabled'],'revision':current['revision'],'expires':now+120}
    return {'token':token,'enabled':body['enabled'],'current':current,'warning':'Existing issued RPC clients can use Tor when its route is configured. Wallet and transaction grants remain required. Disabling stops remote requests, not transactions already broadcast.'}
   if set(body)=={'action','token'} and body['action']=='apply' and isinstance(body['token'],str):
    plan=self.plans.pop(body['token'],None)
    if not plan or plan['expires']<=time.monotonic() or plan['revision']!=self.status()['revision']:raise ValueError('Review expired or configuration changed')
    self.enabled=False
    try:
     self.atomic(self.path,json.dumps({'schema':1,'enabled':plan['enabled'],'phase':'applying'}))
     if plan['enabled']:await self.start()
     else:await self.stop()
     self.atomic(self.path,json.dumps({'schema':1,'enabled':plan['enabled'],'phase':'committed'}))
     self.enabled=plan['enabled']
    except BaseException:
     await self.stop();raise
    return self.status()
   raise ValueError('Unsupported remote setting request')
