// Actual bundled frontend + regtest API. No intercepted or fabricated responses.
const {chromium}=require('playwright'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try {
  const base=process.env.JV_MEMPOOL_ORIGIN||'http://127.0.0.1:29006';
  for(const width of [1440,390]) {
   await page.setViewportSize({width,height:1000});await page.goto(base+'/ko/');
   await page.waitForFunction(()=>document.body.innerText.includes('107'),null,{timeout:45000});
   assert.equal(await page.evaluate(()=>document.querySelector('app-root').innerText.trim().length>100),true);
   const info=await page.evaluate(async()=>{const r=await fetch('/api/v1/backend-info');return [r.status,await r.json()];});
   assert.equal(info[0],200);assert.equal(info[1].version,'3.3.1');
   await page.screenshot({path:`.state/electrs-mempool-20260917/mempool-${width}.png`,fullPage:false});
  }
  assert.deepEqual(errors,[]);
  fs.writeFileSync('.state/electrs-mempool-20260917/browser-result.json',JSON.stringify({status:'PASS',widths:[1440,390],actual_block_height:107,checks:['rendered bundled Korean frontend','actual Core-backed API data','no page errors'],browser:await browser.version()},null,2));
 } finally {await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1});
