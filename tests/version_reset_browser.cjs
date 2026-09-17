// Real browser, HTTP/session/CSRF, Unix API and regtest services; no route mocks.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1050},locale:'ko-KR'});const page=await context.newPage(),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 const origin=process.env.JV_RESET_WEB_ORIGIN||'http://127.0.0.1:28652';
 const output=process.env.JV_RESET_EVIDENCE||'.state/version-reset';
 const password='Version-Reset-Fixture-2026!';
 try {
  await page.goto(origin);await page.locator('#password').fill(password);
  if(await page.locator('#confirm').isVisible())await page.locator('#confirm').fill(password);
  await page.locator('#submit').click();await page.locator('#controls').waitFor({state:'visible',timeout:30000});
  await page.evaluate(()=>I18n.set('ko'));await page.locator('[data-fkey="2"]').click();
  await page.locator('#all-versions').check();await page.locator('.version-card[data-version="22.0"]').click();
  // Selection must not change the actual active Core.
  const api=(body)=>page.evaluate(async body=>{const r=await fetch('/versions',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)});return {status:r.status,body:await r.json()};},body);
  const before=(await api({method:'state'})).body.active;assert.equal(before.instance.core_version,'31.1');
  await page.getByRole('button',{name:'이 버전으로 변경 내용 확인',exact:true}).click();
  const review=page.locator('#settings-review');await review.waitFor({state:'visible',timeout:60000});
  assert.equal(await page.evaluate(()=>document.activeElement.textContent),'취소');
  const scope=await review.locator('li').allTextContents();assert(scope.some(x=>x.endsWith('/blocks')));assert(scope.some(x=>x.endsWith('electrs-0.11.1/regtest')));assert(!(await review.innerText()).includes('/srv/'));
  const destroy=review.getByRole('button',{name:'데이터 삭제 후 버전 변경',exact:true});
  await destroy.focus();await page.keyboard.press('Enter');await page.keyboard.press('Enter');
  assert.equal((await api({method:'state'})).body.active.instance.core_version,'31.1');
  for(const width of [1440,390])for(const language of ['ko','en','ja']) {
   await page.setViewportSize({width,height:1050});await page.evaluate(l=>I18n.set(l),language);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   const label=await review.locator('button').last().innerText();assert(label.length>5);
   if(language==='ko')await review.screenshot({path:`${output}/reset-review-${width}.png`});
  }
  await page.evaluate(()=>I18n.set('ko'));await review.getByRole('button',{name:'취소',exact:true}).click();await review.waitFor({state:'hidden'});
  assert.equal((await api({method:'state'})).body.active.instance.core_version,'31.1');
  // Review again and perform the precise explicitly named action.
  await page.getByRole('button',{name:'이 버전으로 변경 내용 확인',exact:true}).click();await review.waitFor({state:'visible',timeout:60000});
  await review.getByRole('button',{name:'데이터 삭제 후 버전 변경',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#settings-status').textContent.includes('대상 버전 시작'),{},{timeout:180000});
  assert.equal((await api({method:'state'})).body.active.instance.core_version,'22.0');
  assert.deepEqual(errors,[]);
  fs.writeFileSync(`${output}/browser-result.json`,JSON.stringify({status:'PASS',checks:['real authenticated version UI and regtest backend','selection leaves active Core unchanged','authoritative deletion allowlist shown','cancel focused by default','Enter repeats on destructive button do not apply','cancel does not change version','mobile/desktop Korean English Japanese layout','explicit destructive action commits target'],layout_cases:6,browser:await browser.version()},null,2));
  console.log('PASS real web reset review, cancellation, keyboard guard, six layouts and explicit apply');
 }finally {await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
