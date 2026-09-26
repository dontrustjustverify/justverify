// Actual UI and authenticated HTTP. The isolated server has no manager socket.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),os=require('node:os'),{spawn}=require('node:child_process');
// Default automation forces visible/focused pages. Use an ordinary browser context
// without that override so the actual hidden/frozen page behavior can be measured.
async function checkLifecycle(origin,password){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'jv-rain-browser-'));
 const proc=spawn(chromium.executablePath(),['--headless','--no-first-run','--remote-debugging-port=0','--user-data-dir='+dir]);let browser;
 try{
  const endpoint=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Browser startup deadline')),15000);proc.stderr.on('data',data=>{const match=data.toString().match(/DevTools listening on (ws:\/\/\S+)/);if(match){clearTimeout(timer);resolve(match[1]);}});proc.once('error',reject);});
  browser=await chromium.connectOverCDP(endpoint,{noDefaults:true});const context=browser.contexts()[0];
  await context.addInitScript(()=>{window.rainDraws=0;const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...args){if(this.canvas.id==='genesis-rain')rainDraws++;return draw.apply(this,args)};});
  const page=await context.newPage();await page.goto(origin);await page.locator('#password').fill(password);await page.locator('#submit').click();await page.locator('#controls').waitFor({state:'visible'});await page.locator('[data-group=device]').click();await page.locator('#background-toggle').waitFor();
  if(await page.locator('#background-toggle').getAttribute('aria-checked')==='false')await page.locator('#background-toggle').click();
  await page.locator('#genesis-rain').waitFor({state:'visible'});await page.bringToFront();let count=await page.evaluate(()=>rainDraws);await page.waitForTimeout(200);assert(await page.evaluate(()=>rainDraws)>count);
  const front=await context.newPage();await front.bringToFront();await page.waitForFunction(()=>document.hidden);await page.waitForTimeout(100);count=await page.evaluate(()=>rainDraws);await page.waitForTimeout(250);assert.equal(await page.evaluate(()=>rainDraws),count,'actual hidden page');
  const cdp=await context.newCDPSession(page);await cdp.send('Page.setWebLifecycleState',{state:'frozen'});await page.waitForTimeout(150);assert.equal(await page.evaluate(()=>rainDraws),count,'actual frozen page');await cdp.send('Page.setWebLifecycleState',{state:'active'});await front.close();await page.bringToFront();await page.waitForFunction(()=>!document.hidden);await page.waitForTimeout(250);assert(await page.evaluate(()=>rainDraws)>count,'visible page resumes');
 }finally{
  if(browser)await browser.close();
  if(proc.exitCode===null&&proc.signalCode===null){const ended=new Promise(resolve=>proc.once('exit',resolve));proc.kill();await ended;}
  fs.rmSync(dir,{recursive:true,force:true});
 }
}
(async()=>{
 const origin=process.env.JV_RAIN_ORIGIN,password=process.env.JV_RAIN_PASSWORD;
 assert(origin?.startsWith('http://127.0.0.1:')&&password);
 const browser=await chromium.launch({headless:true}),errors=[];let cases=0;
 try{
  for(const width of [390,1440])for(const language of ['ko','en','ja']){
   const context=await browser.newContext({viewport:{width,height:1000},locale:language});
   await context.addInitScript(()=>{window.rainDraws=0;const draw=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(...args){if(this.canvas.id==='genesis-rain')window.rainDraws++;return draw.apply(this,args)};});
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));const requests=[];page.on('request',r=>requests.push(new URL(r.url()).pathname));
   await page.goto(origin);await page.locator('#login').waitFor({state:'visible'});await page.locator('#password').fill(password);await page.locator('#submit').click();await page.locator('#controls').waitFor({state:'visible'});
   await page.evaluate(async l=>{const r=await fetch('/device-settings',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({action:'preferences',theme:'teal',language:l})});if(!r.ok)throw Error('preference fixture failed');const saved=await fetch('/device-settings',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({action:'background',background:{enabled:false,brightness:40,speed:160,density:140}})});if(!saved.ok)throw Error('background fixture failed');await DeviceView.loadPreferences();},language);
   await page.locator('[data-group=device]').click();await page.locator('#background-toggle').waitFor();
   assert.equal(await page.locator('#background-toggle').getAttribute('aria-checked'),'false');assert.equal(await page.locator('#background-controls').count(),0);assert(await page.locator('#genesis-rain').count()===0||await page.locator('#genesis-rain').isHidden());
   const enabled=page.waitForResponse(r=>r.url()===origin+'/device-settings'&&r.request().postDataJSON()?.action==='background');await page.locator('#background-toggle').click();assert.equal((await enabled).status(),200);await page.locator('#background-brightness').waitFor();await page.locator('#genesis-rain').waitFor({state:'visible'});
   assert.equal(await page.locator('#background-brightness').inputValue(),'40');assert.equal(await page.locator('#background-speed').inputValue(),'160');assert.equal(await page.locator('#background-density').inputValue(),'140');
   let count=await page.evaluate(()=>rainDraws);await page.waitForTimeout(250);assert(await page.evaluate(()=>rainDraws)>count);
   await page.locator('#background-brightness').fill('100');await page.locator('#background-speed').fill('400');await page.locator('#background-density').fill('300');
   assert.equal(await page.locator('#background-brightness-value').textContent(),'100%');assert.equal(await page.locator('#background-speed-value').textContent(),'4.00×');
   const saved=page.waitForResponse(r=>r.url()===origin+'/device-settings'&&r.request().postDataJSON()?.action==='background');await page.locator('#background-save').click();assert.equal((await saved).status(),200);await page.waitForFunction(()=>document.querySelector('#background-save')?.disabled);
   await page.reload();await page.locator('#controls').waitFor({state:'visible'});await page.locator('[data-group=device]').click();await page.locator('#background-brightness').waitFor();assert.equal(await page.locator('#background-brightness').inputValue(),'100');assert.equal(await page.locator('#background-speed').inputValue(),'400');assert.equal(await page.locator('#background-density').inputValue(),'300');
   await page.locator('#background-brightness').fill('5');await page.locator('[data-group=core]').click();await page.locator('[data-group=device]').click();await page.locator('#background-brightness').waitFor();assert.equal(await page.locator('#background-brightness').inputValue(),'100');
   for(const theme of ['teal','green','amber','ice']){await page.locator(`[data-color=${theme}]`).click();await page.waitForFunction(t=>document.documentElement.dataset.theme===t,theme);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));cases++;}
   if(process.env.JV_RAIN_SCREENSHOTS&&language==='ko'){
    await page.locator('[data-color=teal]').click();await page.waitForFunction(()=>document.documentElement.dataset.theme==='teal');
    await page.locator('#background-toggle').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.JV_RAIN_SCREENSHOTS,`settings-${width}.png`)});
   }
   await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(150);count=await page.evaluate(()=>rainDraws);await page.waitForTimeout(250);assert.equal(await page.evaluate(()=>rainDraws),count,'reduced motion');assert(await page.locator('#genesis-rain').isVisible());
   await page.emulateMedia({reducedMotion:'no-preference'});await page.waitForTimeout(150);assert(await page.evaluate(()=>rainDraws)>count);
   const disabled=page.waitForResponse(r=>r.url()===origin+'/device-settings'&&r.request().postDataJSON()?.action==='background');await page.locator('#background-toggle').click();assert.equal((await disabled).status(),200);await page.locator('#genesis-rain').waitFor({state:'hidden'});count=await page.evaluate(()=>rainDraws);await page.waitForTimeout(200);assert.equal(await page.evaluate(()=>rainDraws),count,'disabled effect');
   assert(await page.locator('#genesis-rain').evaluate(c=>c.width*c.height===1));assert(requests.every(p=>!p.includes('genesis')||p==='/genesis-rain.js'));await context.close();
  }
  await checkLifecycle(origin,password);assert.deepEqual(errors,[]);console.log(JSON.stringify({status:'PASS',theme_language_viewport_cases:cases,checks:['real login and settings APIs','default off; toggle and sliders','live preview; explicit save; discard on navigation','reload persists all values','four themes and three languages at390/1440px','reduced-motion stops redraw; re-enable resumes','disabled renderer stops and releases canvas','actual hidden/frozen browser stops; visibility resumes','no horizontal overflow'],scope:'Manager not running in this fixture; no Core/electrs status integration claim'}));
 }finally{await browser.close();}
})().catch(e=>{console.error('Digital Rain browser check failed: '+e.message);process.exit(1)});
