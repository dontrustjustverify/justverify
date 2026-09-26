// Real login HTTP/cookies; the post-login node screen is outside this auth test.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const origin=process.env.JV_LOGIN_TEST_ORIGIN,password=process.env.JV_LOGIN_TEST_PASSWORD;
 assert(origin?.startsWith('http://127.0.0.1:')&&password);
 const browser=await chromium.launch({headless:true});
 const errors=[];
 try {
  for(const width of [390,1440])for(const language of ['ko','en','ja']) {
   const context=await browser.newContext({viewport:{width,height:950},locale:language}),page=await context.newPage();
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(origin);await page.locator('#login').waitFor({state:'visible'});
   await page.evaluate(l=>{I18n.set(l);terminal=()=>{document.querySelector('#welcome').hidden=true;document.querySelector('#controls').hidden=false;};},language);
   await page.locator('#password').fill(password);
   let requests=0;page.on('request',r=>{if(r.url()===origin+'/login'&&r.method()==='POST')requests++;});
   const response=page.waitForResponse(r=>r.url()===origin+'/login');
   await page.evaluate(()=>{const form=document.querySelector('#login');for(let i=0;i<3;i++)form.dispatchEvent(new Event('submit',{cancelable:true}));});
   assert.equal((await response).status(),200);
   await page.locator('#controls').waitFor({state:'visible'});
   assert.equal(requests,1,'rapid submits produce one request');
   assert.equal(await page.locator('#password').inputValue(),'');
   assert.equal(await page.locator('#status').textContent(),'');
   assert((await context.cookies()).some(c=>c.name==='jv_lan_session'&&c.httpOnly&&c.sameSite==='Strict'));
   assert.equal((await context.request.get(origin+'/session')).status(),200);
   await page.evaluate(()=>{document.querySelector('#device-view').hidden=false;return DeviceView.open();});
   await page.locator('#manage-sessions').click();
   await page.locator('[data-current-session]').waitFor();
   const total=await page.locator('.session-item').count();assert(total>=2);
   assert.equal(await page.locator('[data-current-session]').count(),1);
   for(const theme of ['teal','amber','green','ice']) {
    await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
    assert(await page.evaluate(()=>{
     const d=document.querySelector('#device-dialog'),r=d.getBoundingClientRect();
     return r.left>=0&&r.right<=innerWidth+1&&d.scrollWidth<=d.clientWidth+1;
    }),language+' '+width+' '+theme+' session dialog fits');
   }
   await page.locator('#revoke-other-sessions').click();
   assert(await page.locator('#session-cancel').evaluate(e=>e===document.activeElement));
   await page.keyboard.press('Enter');
   await page.locator('#session-list').waitFor();assert.equal(await page.locator('.session-item').count(),total);
   const other=page.locator('.session-item').filter({hasNot:page.locator('[data-current-session]')}).first();
   await other.locator('[data-revoke-session]').click();await page.locator('#session-confirm').click();
   await page.waitForFunction(n=>document.querySelectorAll('.session-item').length===n,total-1);
   await page.locator('#revoke-other-sessions').click();await page.locator('#session-confirm').click();
   await page.waitForFunction(()=>document.querySelectorAll('.session-item').length===1);
   assert.equal((await context.request.get(origin+'/session')).status(),200);
   assert(await page.locator('#revoke-other-sessions').isDisabled());
   await page.locator('[data-revoke-session]').click();await page.locator('#session-confirm').click();
   await page.locator('#login').waitFor({state:'visible'});
   assert.equal((await context.request.get(origin+'/session')).status(),401);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await context.close();
   // Leave another valid browser for the next management/revocation case.
   for(let i=0;i<2;i++){const seed=await browser.newContext();const seeded=await seed.request.post(origin+'/login',{headers:{Origin:origin},data:{password}});
   assert.equal(seeded.status(),200);await seed.close();}
  }
  const context=await browser.newContext({viewport:{width:390,height:950}}),page=await context.newPage();
  await page.goto(origin);await page.locator('#login').waitFor({state:'visible'});
  for(let i=0;i<6;i++) {
   await page.locator('#password').fill('invalid-test-password');
   const response=page.waitForResponse(r=>r.url()===origin+'/login');
   await page.locator('#submit').click();
   const r=await response;assert.equal(r.status(),i===5?429:401);
   await page.waitForFunction(()=>!document.querySelector('#submit').disabled);
   if(i===5)assert(Number(r.headers()['retry-after'])>0);
  }
  for(const [language,pattern] of [['ko',/시도가 많아.*\d+초/],['en',/Too many attempts.*\d+ seconds/],['ja',/試行回数が多すぎます。\d+秒/]]) {
   await page.evaluate(l=>I18n.set(l),language);
   assert.match(await page.locator('#status').textContent(),pattern);
  }
  // Client rendering of a legacy response without Retry-After is a separate fixture.
  await page.route(origin+'/login',route=>route.fulfill({status:429,body:'429: Too Many Requests'}));
  await page.evaluate(()=>I18n.set('ko'));
  const response=page.waitForResponse(r=>r.url()===origin+'/login');await page.locator('#submit').click();await response;
  await page.waitForFunction(()=>!document.querySelector('#submit').disabled);
  assert.match(await page.locator('#status').textContent(),/로그인이 제한/);
  assert(!/300/.test(await page.locator('#status').textContent()));
  for(const [language,pattern] of [['en',/Login is temporarily limited/],['ja',/ログインが一時的に制限/]]) {
   await page.evaluate(l=>I18n.set(l),language);assert.match(await page.locator('#status').textContent(),pattern);
  }
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await context.close();assert.deepEqual(errors,[]);
  console.log(JSON.stringify({status:'PASS',real_http:['six fresh browsers','390px and 1440px','three languages and four themes','cancel focused, Enter cancels without revoking','individual and other-device logout','self logout returns to sign-in','single request for rapid submit','cookie and session endpoint','actual failed-password throttle'],render_fixture:['legacy429 without Retry-After has no invented300seconds']}));
 } finally {await browser.close();}
})().catch(e=>{console.error('FAIL browser login regression: '+e.message);process.exit(1);});
