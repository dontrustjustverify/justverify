#!/usr/bin/env python3
"""Exercise authenticated config preview against a running test web instance and real Core."""
import asyncio,json,pathlib,sys
import aiohttp
async def main():
 origin=sys.argv[1];password=sys.argv[2];report=pathlib.Path(sys.argv[3])
 async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),timeout=aiohttp.ClientTimeout(total=90)) as c:
  async with c.post(origin+'/policy',headers={'Origin':origin},json={'method':'preview_config','config':'datacarrier=0'}) as r:assert r.status==401
  async with c.post(origin+'/login',headers={'Origin':origin},json={'password':password}) as r:
   assert r.status==200;token=(await r.json())['csrf']
  h={'Origin':origin,'X-CSRF-Token':token}
  async def request(body,code=200,headers=h):
   async with c.post(origin+'/policy',headers=headers,json=body) as r:
    assert r.status==code,(r.status,await r.text())
    return await r.json() if code==200 else None
  await request({'method':'preview_config','config':'datacarrier=0'},403,{'Origin':origin})
  await request({'method':'preview_config','config':'datacarrier=0'},403,{**h,'Origin':'http://wrong.invalid'})
  before=await request({'method':'state'})
  for text in ['rpcbind=0.0.0.0','includeconf=other.conf','maxorphantx=100','datacarrier=0\ndatacarrier=1','debug=not-a-category']:
   await request({'method':'preview_config','config':text},409)
  # More than 4 KiB of comments exercises the bounded editor-specific HTTP body limit.
  text='# '+('x'*5000)+'\n'+before['config']+'\ndebug=mempoolrej\n'
  preview=await request({'method':'preview_config','config':text})
  assert preview['plan']['requested']['debug']=='mempoolrej'
  assert preview['plan']['requested']['datacarrier']=='0'
  assert preview['plan']['requested']['datacarriersize']=='83'
  assert preview['preflight']['observed']['maxdatacarriersize']==0
  await request({'method':'preview_config','config':'#'+('x'*8192)},409)
  after=await request({'method':'state'});assert after['requested']==before['requested']
  async with c.get(origin+'/session') as r:assert r.status==200
  report.write_text(json.dumps({'status':'PASS','core':before['version'],'network':before['network'],'checks':['anonymous rejected','CSRF rejected','cross-origin rejected','protected/duplicate/removed/invalid options rejected','large valid editor request exercised real Core preflight','oversize editor rejected','preview preserved active configuration','session resumed'],'active_settings':after['requested']},indent=2)+'\n')
  async with c.post(origin+'/logout',headers=h) as r:assert r.status==200
asyncio.run(main())
