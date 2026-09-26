// Real browser and authenticated Electrum API on the disposable regtest VM.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'ko-KR'}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const origin=process.env.JV_UI_TEST_ORIGIN||'http://127.0.0.1:28646';
 const password=process.env.JV_UI_TEST_PASSWORD;
 assert(password,'disposable test password required');
 try {
  await page.goto(origin);await page.locator('#password').fill(password);
  if(await page.locator('#confirm').isVisible())await page.locator('#confirm').fill(password);
  await page.locator('#submit').click();await page.locator('#controls').waitFor({state:'visible',timeout:30000});
  for(const width of [1440,390])for(const language of ['ko','en','ja']) {
   await page.setViewportSize({width,height:1000});await page.evaluate(l=>I18n.set(l),language);
   await page.locator('[data-group="wallet"]').click();
   await page.waitForFunction(()=>document.querySelector('#electrum-address').value==='justverify.local:50001'&&!document.querySelector('#electrum-details').hidden);
   assert.equal(await page.locator('[data-electrum-transport="tcp"]').getAttribute('aria-pressed'),'true');
   assert.equal(await page.locator('#electrum-fingerprint').textContent(),'');
   assert(!((await page.locator('#electrum-data').textContent()).includes('Electrum TLS')));
   await page.locator('[data-electrum-transport="tls"]').click();
   await page.waitForFunction(()=>document.querySelector('#electrum-address').value==='justverify.local:50002');
   assert.match(await page.locator('#electrum-fingerprint').textContent(),/[a-f0-9]{64}/);
   await page.locator('[data-network="tor"]').click();
   await page.waitForFunction(()=>document.querySelector('#electrum-address').value.endsWith('.onion:50001'));
   assert(await page.locator('#electrum-transport').isHidden());
   await page.locator('[data-network="lan"]').click();
   await page.waitForFunction(()=>document.querySelector('#electrum-address').value==='justverify.local:50001');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   // The rendered QR must encode exactly the selected API matrix, including quiet zone.
   assert(await page.evaluate(async()=>{
    const response=await fetch('/electrum?network=lan',{headers:{'X-CSRF-Token':csrf}}),d=await response.json();
    const canvas=document.querySelector('#electrum-qr'),pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
    return canvas.width===d.matrix.length*8&&d.matrix.every((row,y)=>row.every((on,x)=>pixels[((y*8+4)*canvas.width+x*8+4)*4]===(on?0:255)));
   }));
  }
  const checks=await page.evaluate(async()=>{
   const result=[];
   for(const query of ['network=invalid','network=lan&transport=bad','network=tor&transport=tls'])result.push((await fetch('/electrum?'+query,{headers:{'X-CSRF-Token':csrf}})).status);
   result.push((await fetch('/electrum?network=lan')).status);return result;
  });assert.deepEqual(checks,[400,400,400,403]);
  assert.deepEqual(errors,[]);
  console.log('PASS real browser TCP default / optional TLS / Tor, both viewports, three languages, exact QR pixels, transport validation and CSRF');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
