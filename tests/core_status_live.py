#!/usr/bin/env python3
"""Interactive browser checks backed by isolated real Core and collector processes."""
import argparse,asyncio,json,os,pathlib,signal,socket,subprocess,tempfile,time
from aiohttp import web
R=pathlib.Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser();a.add_argument('--port',type=int,default=28647);a.add_argument('--evidence',type=pathlib.Path,required=True);args=a.parse_args();args.evidence.mkdir(parents=True,exist_ok=True)
B=R/'.cache/core/31.1/arm64-apple-darwin/bitcoin-31.1/bin';temporary=tempfile.TemporaryDirectory(prefix='jv-status-');base=pathlib.Path(temporary.name);cores=[];manager=None;paused=False;observations=[];hold_http=False

def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
ports=[port(),port()]
def cli(n,*argv):return subprocess.check_output([str(B/'bitcoin-cli'),'-regtest',f'-datadir={base/str(n)}',f'-rpcport={ports[n]}','-rpcwait',*map(str,argv)],text=True).strip()
def snap():
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(3);s.connect(str(base/'manager.sock'));s.sendall(b'snapshot\n');raw=b''
  while part:=s.recv(65536):raw+=part
 return json.loads(raw)
def record(name,expected,condition,timeout=30):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  try:
   value=snap();chain=value['rpc']['getblockchaininfo']
   if condition(chain):
    value={'collected':value['collected'],'rpc':{'getblockchaininfo':chain}};observations.append({'name':name,'expected':expected,'at':time.time(),'snapshot':value});(args.evidence/'live-observations.json').write_text(json.dumps(observations,indent=2));return
  except (OSError,KeyError,TypeError):pass
  time.sleep(.15)
 raise AssertionError(name+' timed out')
def current(c):return c['updated']>0 and c['error'] is None and time.time()-c['updated']<5
async def dashboard(request):
 if hold_http:await asyncio.sleep(30)
 return web.json_response(await asyncio.to_thread(snap),headers={'Cache-Control':'no-store'})
async def action(request):
 global paused,hold_http
 name=await request.text()
 def run():
  global paused,hold_http
  if name=='mine':
   cli(0,'generatetoaddress',1,cli(0,'getnewaddress'));record('caught-up','synced',lambda c:current(c) and not c['value']['initialblockdownload'])
  elif name=='pause':
   cores[0].send_signal(signal.SIGSTOP);paused=True;record('Core RPC paused','delayed',lambda c:bool(c['error']) and time.time()-c['updated']>15)
  elif name=='resume':
   cores[0].send_signal(signal.SIGCONT);paused=False;record('Core RPC recovered','synced',lambda c:current(c) and not c['value']['initialblockdownload'])
  elif name=='headers':
   tip=cli(0,'getbestblockhash');cli(1,'submitblock',cli(0,'getblock',tip,0));cli(1,'generatetoaddress',1,cli(1,'getnewaddress'));nexttip=cli(1,'getbestblockhash');cli(0,'submitheader',cli(1,'getblockheader',nexttip,'false'));record('known header ahead after IBD','syncing',lambda c:current(c) and c['value']['headers']>c['value']['blocks'])
  elif name=='block':
   tip=cli(1,'getbestblockhash');cli(0,'submitblock',cli(1,'getblock',tip,0));record('caught up with new block','synced',lambda c:current(c) and c['value']['blocks']==c['value']['headers'])
  elif name=='idle':
   old=cli(0,'getbestblockhash');time.sleep(20);assert cli(0,'getbestblockhash')==old;record('no new block for20seconds','synced',lambda c:current(c) and not c['value']['initialblockdownload'])
  elif name=='http-pause':hold_http=True
  elif name=='http-resume':hold_http=False
  else:raise ValueError('Unknown test action')
 await asyncio.to_thread(run);return web.json_response({'done':name})
async def index(request):
 import re
 html=(R/'web/static/index.html').read_text();html=re.sub(r'<section id="welcome".*?</section>','',html,flags=re.S);html=html.replace('<section hidden id="controls">','<section id="controls">').replace('<section id="overview" hidden','<section id="overview"')
 html=html.replace('<script src="/app.js"></script>','<script src="/test-controls.js"></script>')
 toolbar='''<fieldset id="test-controls"><legend>Isolated regtest checks</legend><button data-action="mine">Mine</button><button data-action="pause">Pause Core</button><button data-action="resume">Resume Core</button><button data-action="headers">Header ahead</button><button data-action="block">Catch up</button><button data-action="idle">Wait without blocks</button><button data-action="http-pause">Pause HTTP</button><button data-action="http-resume">Resume HTTP</button><select aria-label="Test theme" id="test-theme"><option>teal</option><option>amber</option><option>green</option><option>ice</option></select><select aria-label="Test background" id="test-background"><option value="dark">Dark</option><option value="light">Light</option></select><select aria-label="Test language" id="test-language"><option>ko</option><option>en</option><option>ja</option></select><select aria-label="Test motion rule" id="test-motion-rule"><option value="system">System preference</option><option value="reduce">Reduced-motion rule</option></select><p id="test-result"></p><p id="test-motion"></p></fieldset>'''
 html=html.replace('<div class="node-heading">',toolbar+'<div class="node-heading">')
 html+='''<style>#test-controls{padding:8px;border:1px solid var(--border);margin:16px 0}#test-controls button,#test-controls select{font-size:11px;padding:4px;margin:3px;width:auto}#test-controls p{font-size:10px;margin:0}[data-test-background=light]{color-scheme:light;--page:#fff;--panel:#f7faf9;--surface:#e5eeeb;--text:#182b29;--muted:#405b57;--accent:#006b63;--border:#647e78}[data-test-background=light] body{background:var(--page)}</style>'''
 return web.Response(text=html,content_type='text/html')
async def js(request):return web.Response(text='''const csrf='';NodeView.start();document.querySelector('#test-motion-rule').onchange=e=>{document.querySelector('#test-motion-style')?.remove();if(e.target.value==='reduce'){const rule=[...document.styleSheets].flatMap(s=>[...s.cssRules]).find(r=>r.conditionText==='(prefers-reduced-motion: reduce)');if(!rule)throw Error('Reduced-motion rule missing');const style=document.createElement('style');style.id='test-motion-style';style.textContent=[...rule.cssRules].map(r=>r.cssText).join('\\n');document.head.append(style);}};document.querySelectorAll('[data-action]').forEach(b=>b.onclick=async()=>{const o=document.querySelector('#test-result');o.textContent='Running '+b.dataset.action;const r=await fetch('/test-action',{method:'POST',body:b.dataset.action});o.textContent=r.ok?'PASS '+(await r.json()).done:'FAILED '+await r.text();});document.querySelector('#test-theme').onchange=e=>document.documentElement.dataset.theme=e.target.value;document.querySelector('#test-background').onchange=e=>document.documentElement.dataset.testBackground=e.target.value;document.querySelector('#test-language').onchange=e=>I18n.set(e.target.value);setInterval(()=>document.querySelector('#test-motion').textContent='Reduced motion: '+matchMedia('(prefers-reduced-motion: reduce)').matches,500);''',content_type='application/javascript')
async def static(request):
 name=request.match_info['name'];p=R/'web/static'/name
 if '/' in name or not p.is_file():raise web.HTTPNotFound()
 return web.FileResponse(p,headers={'Cache-Control':'no-store'})
try:
 for n in (0,1):
  d=base/str(n);d.mkdir(mode=0o700);cores.append(subprocess.Popen([str(B/'bitcoind'),'-regtest',f'-datadir={d}',f'-rpcport={ports[n]}','-listen=0','-networkactive=0','-server=1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL));cli(n,'createwallet','status-test')
 manager=subprocess.Popen([str(R/'target/debug/justverify'),'daemon','--cookie',str(base/'0/regtest/.cookie'),'--rpc-port',str(ports[0]),'--socket',str(base/'manager.sock')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 record('initial IBD','syncing',lambda c:current(c) and c['value']['initialblockdownload'])
 app=web.Application();app.router.add_get('/',index);app.router.add_get('/dashboard',dashboard);app.router.add_post('/test-action',action);app.router.add_get('/test-controls.js',js);app.router.add_get('/{name}',static)
 print(f'READY http://127.0.0.1:{args.port}',flush=True);web.run_app(app,host='127.0.0.1',port=args.port,access_log=None,print=None)
finally:
 if paused:cores[0].send_signal(signal.SIGCONT)
 if manager:manager.terminate();manager.wait(timeout=10)
 for n,c in enumerate(cores):
  if c.poll() is None:cli(n,'stop');c.wait(timeout=20)
 temporary.cleanup()
