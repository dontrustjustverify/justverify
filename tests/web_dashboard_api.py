#!/usr/bin/env python3
"""Read-only API verification against the dedicated live Linux VM UI service."""
import asyncio,hashlib,json,pathlib,os
import aiohttp,zxingcpp
from PIL import Image
R=pathlib.Path(__file__).resolve().parents[1];OUT=R/'.state/browser-ui'
async def main():
 origin=os.environ.get('JV_UI_TEST_ORIGIN','http://127.0.0.1:28646');password=os.environ['JV_UI_TEST_PASSWORD'];evidence=[]
 async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as c:
  for path in ['/dashboard','/electrum?network=lan','/electrum?network=tor']:
   async with c.get(origin+path) as r:assert r.status==401
  async with c.post(origin+'/login',headers={'Origin':origin},json={'password':password}) as r:assert r.status==200;csrf=(await r.json())['csrf']
  async with c.get(origin+'/dashboard') as r:assert r.status==403
  headers={'X-CSRF-Token':csrf}
  async with c.get(origin+'/dashboard',headers={**headers,'Origin':'http://evil.invalid'}) as r:assert r.status==403
  async with c.get(origin+'/dashboard',headers=headers) as r:
   assert r.status==200;s=await r.json();assert s['rpc']['getblockchaininfo']['updated']>0
  for mode in ('lan','tor'):
   async with c.get(origin+'/electrum?network='+mode,headers=headers) as r:assert r.status==200,await r.text();d=await r.json()
   matrix=d['matrix'];n=len(matrix);assert all(len(row)==n for row in matrix)
   img=Image.new('RGB',(n*8,n*8),'white');pix=img.load()
   for y,row in enumerate(matrix):
    for x,on in enumerate(row):
     if on:
      for yy in range(y*8,(y+1)*8):
       for xx in range(x*8,(x+1)*8):pix[xx,yy]=(0,0,0)
   img.save(OUT/f'vm-{mode}-qr.png');decoded=zxingcpp.read_barcode(img);assert decoded and decoded.text==d['payload']
   if mode=='lan':assert d['payload']=='justverify.local:50002' and d['tls'] and len(d['certificate_sha256'])==64
   else:assert d['payload'].endswith('.onion:50001') and not d['tls']
   evidence.append({'network':mode,'payload_sha256':hashlib.sha256(d['payload'].encode()).hexdigest(),'qr_exact':True,'service_active':d['service_active']})
  async with c.get(origin+'/electrum?network=wrong',headers=headers) as r:assert r.status==400
  async with c.post(origin+'/logout',headers={**headers,'Origin':origin}) as r:assert r.status==200
  async with c.get(origin+'/dashboard',headers=headers) as r:assert r.status==401
 (OUT/'api-evidence.json').write_text(json.dumps({'scope':os.environ.get('JV_UI_TEST_TARGET','Actual Linux VM collector')+' and configured endpoints; QR digital decode, not camera/wallet connection','checks':evidence},indent=2))
 print('PASS authenticated live snapshot, missing CSRF, cross-origin, invalid network, logout revocation, actual LAN/Tor QR exact decoding')
asyncio.run(main())
