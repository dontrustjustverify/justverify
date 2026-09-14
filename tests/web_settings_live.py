#!/usr/bin/env python3
"""Real web transactions inside the registered, disposable Linux regtest fixture."""
import asyncio,json,os,pathlib,pwd,shutil,socket,subprocess,tempfile,time
import aiohttp
R=pathlib.Path(__file__).resolve().parents[1]
assert os.geteuid()==0 and socket.gethostname()=='justverify-dev'
ORIGIN='http://127.0.0.1:28646'
async def main():
 root=pathlib.Path(tempfile.mkdtemp(prefix='jv-settings-web-',dir='/var/tmp'));root.chmod(0o755)
 shutil.copytree(R/'web',root/'web');state=root/'state';state.mkdir(mode=0o700);account=pwd.getpwnam('justverify');os.chown(state,account.pw_uid,account.pw_gid)
 script=root/'serve.py';script.write_text("import sys,pathlib\nsys.path.insert(0,str(pathlib.Path(__file__).parent/'web'))\nfrom server import Bridge,app_for,web\nb=Bridge(pathlib.Path(__file__).parent/'state',pathlib.Path('/opt/justverify/bin/justverify'),pathlib.Path('/run/justverify/manager.sock'),'https://justverify.local');b.lan_http=True;b.lan_onboarding=True\nweb.run_app(app_for(b,lan_http=True),host='127.0.0.1',port=28646,access_log=None,print=None)\n")
 log=open(root/'server.log','wb');server=subprocess.Popen(['sudo','-u','justverify','/opt/justverify/venv/bin/python',str(script)],stdout=log,stderr=log)
 original=None
 try:
  for _ in range(100):
   if server.poll() is not None:raise RuntimeError('test web failed')
   try:
    with socket.create_connection(('127.0.0.1',28646),timeout=.2):break
   except OSError:await asyncio.sleep(.1)
  async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),timeout=aiohttp.ClientTimeout(total=300)) as c:
   for path in ('/versions','/policy','/node-start'):
    async with c.post(ORIGIN+path,headers={'Origin':ORIGIN},json={}) as r:assert r.status==401
   async with c.post(ORIGIN+'/setup',headers={'Origin':ORIGIN},json={'password':'Browser-Test-2026!','password_confirm':'Browser-Test-2026!'}) as r:assert r.status==200;csrf=(await r.json())['csrf']
   headers={'Origin':ORIGIN,'X-CSRF-Token':csrf}
   async def request(path,body,status=200):
    async with c.post(ORIGIN+path,headers=headers,json=body) as r:
     assert r.status==status,(path,r.status,await r.text())
     return await r.json() if status==200 else await r.text()
   async with c.get(ORIGIN+'/session') as r:assert r.status==200 and (await r.json())['csrf']==csrf
   for path in ('/versions','/policy','/node-start'):
    async with c.post(ORIGIN+path,headers={'Origin':ORIGIN},json={}) as r:assert r.status==403
    async with c.post(ORIGIN+path,headers={**headers,'Origin':'http://evil.invalid'},json={}) as r:assert r.status==403
   active=(await request('/versions',{'method':'state'}))['active'];assert active['instance']['network']=='regtest'
   started=await request('/node-start',{});assert not started['started'] and started['active']==active
   await request('/versions',{'method':'preview','version':'31.1','network':'invalid','watch_only':False},409)
   await request('/versions',{'method':'preview','version':active['instance']['core_version'],'network':'regtest','watch_only':False},409)
   p=await request('/versions',{'method':'preview','version':'23.2','network':'regtest','watch_only':False})
   applied=await request('/versions',{'method':'apply','token':p['token']});assert applied['phase']=='committed'
   await request('/versions',{'method':'apply','token':p['token']},409)
   assert (await request('/versions',{'method':'state'}))['active']['instance']['core_version']=='23.2'
   p=await request('/versions',{'method':'preview','version':active['instance']['core_version'],'network':'regtest','watch_only':False})
   assert (await request('/versions',{'method':'apply','token':p['token']}))['phase']=='committed'
   s=await request('/policy',{'method':'state'});original=s['requested'];values={**original,'persistmempool':'0','maxconnections':'42','maxuploadtarget':'10'}
   await request('/policy',{'method':'preview','values':{**values,'onlynet':'unknown-network'}},409)
   i2p=await request('/policy',{'method':'preview','values':{**values,'onlynet':'i2p'}})
   assert i2p['plan']['requested']['onlynet']=='i2p'
   await request('/policy',{'method':'preview','values':{'maxconnections':42}},409)
   p=await request('/policy',{'method':'preview','values':values});assert p['plan']['requested']==values
   await request('/policy',{'method':'apply','token':p['token']})
   s=await request('/policy',{'method':'state'});assert s['requested']==values
   config=json.loads(pathlib.Path('/etc/justverify/profile.json').read_text());native=pathlib.Path(config['managed_config']).read_text();assert 'persistmempool=0' in native and 'maxconnections=42' in native
   # CLI reads the actual regtest instance configuration/cookie, never a mock.
   cli=['/opt/justverify/core/bin/bitcoin-cli','-datadir='+str(pathlib.Path(config['cookie']).parents[1]),'-regtest']
   info=json.loads(subprocess.check_output(cli+['getnetworkinfo'],text=True));assert info['version']==310100
   totals=json.loads(subprocess.check_output(cli+['getnettotals'],text=True));assert totals['uploadtarget']['target']==10*1048576
   logtext=(pathlib.Path(config['cookie']).parent/'debug.log').read_text();assert 'Using at most 42' in logtext
   with socket.create_connection(('127.0.0.1',50001),timeout=10) as electrum:
    electrum.sendall(b'{"id":1,"method":"blockchain.headers.subscribe","params":[]}\n');height=json.loads(electrum.makefile('rb').readline())['result']['height']
   chain=json.loads(subprocess.check_output(cli+['getblockchaininfo'],text=True));assert height==chain['blocks']
   print('PASS web session restore/access controls, real version commit/token replay, policy validation/restart/effective RPC and electrs height',flush=True)
   marker=pathlib.Path('/var/tmp/jv-settings-browser-ready');marker.write_text(str(root))
   if os.environ.get('JV_WEB_BROWSER_HOLD')=='1':
    deadline=time.monotonic()+600
    while marker.exists() and time.monotonic()<deadline:await asyncio.sleep(1)
   marker.unlink(missing_ok=True)
   p=await request('/policy',{'method':'preview','values':original});await request('/policy',{'method':'apply','token':p['token']});assert (await request('/policy',{'method':'state'}))['requested']==original;original=None
   async with c.post(ORIGIN+'/logout',headers=headers) as r:assert r.status==200
   async with c.get(ORIGIN+'/session') as r:assert r.status==401
 finally:
  server.terminate();server.wait(timeout=15);log.close()
  # The enclosing registered fixture restores all original node data/config even
  # if an assertion fails before policy restoration.
  shutil.rmtree(root)
asyncio.run(main())
