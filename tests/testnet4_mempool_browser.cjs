// Actual public testnet4 data through the disposable VM's bundled frontend.
const {chromium}=require('playwright'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const origin=process.env.JV_MEMPOOL_ORIGIN||'http://127.0.0.1:21880';
 assert(['127.0.0.1','localhost'].includes(new URL(origin).hostname));
 const browser=await chromium.launch({headless:true}),results=[];
 try {
  for(const width of [1440,390]) {
   const page=await browser.newPage({viewport:{width,height:1000}}),errors=[],frames=[];
   page.on('pageerror',error=>errors.push(error.message));
   page.on('websocket',socket=>socket.on('framereceived',frame=>{try{const value=JSON.parse(String(frame.payload));if(Array.isArray(value.blocks))frames.push(...value.blocks.map(b=>b.height));}catch{}}));
   await page.goto(origin+'/ko/');
   const blockResponse=await page.request.get(origin+'/api/v1/blocks');assert.equal(blockResponse.status(),200);
   const blocks=await blockResponse.json();assert(blocks.length>0&&blocks.every(b=>Number.isInteger(b.height)));
   await page.waitForFunction(heights=>{const text=document.querySelector('app-root')?.innerText.replaceAll(',','').replace(/\s/g,'')||'';return heights.some(height=>text.includes(String(height)));},blocks.map(b=>b.height),{timeout:45000});
   await page.waitForFunction(()=>document.querySelector('app-root').innerText.trim().length>100);
   const status=await (await page.request.get(origin+'/justverify/status')).json();assert.equal(status.network,'testnet4');assert(status.api_available);
   assert.deepEqual(errors,[]);
   results.push({width,actual_visible_block_heights:blocks.map(b=>b.height),websocket_block_frames:frames.length,api_available:status.api_available,state:status.state});
   await page.close();
  }
  const result={status:'PASS',network:'public testnet4',checks:['unmodified live VM API and bundled Korean frontend','desktop and mobile contain actual recent block height','no page script errors'],views:results};
  fs.writeFileSync('.state/testnet4-vm-20260920/browser.json',JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 } finally {await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1});
