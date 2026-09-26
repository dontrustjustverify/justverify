// Component rendering with production markup, styles, formatter and translations.
// This is a layout test, not a live-node synchronization test.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync('web/static/index.html','utf8');
  const panel=html.match(/<section id="electrum-view"[\s\S]*?<\/section>/)[0].replace(' hidden','');
  const css=fs.readFileSync('web/static/app.css','utf8');
  await page.setContent('<!doctype html><html><head><meta charset="utf-8"><style>'+css+'</style></head><body><main>'+panel+'</main></body></html>');
  await page.addScriptTag({path:path.resolve('web/static/electrs_status.js')});
  await page.addScriptTag({path:path.resolve('web/static/i18n.js')});
  let cases=0;
  for(const width of [390,1440])for(const language of ['ko','en','ja'])for(const theme of ['teal','amber','green','ice'])for(const [i,compaction] of ['config','headers','txid','funding','spending'].entries()){
   await page.setViewportSize({width,height:1000});
   await page.evaluate(({compaction,language,theme})=>{
    document.documentElement.dataset.theme=theme;
    const s={state:'FINALIZING',compaction,compaction_percent_basis_points:6400,height:968196,target_height:968197};const p=ElectrsStatus.progress(s);
    document.querySelector('#electrum-progress-state').textContent=p.state;
    document.querySelector('#electrum-progress-value').textContent=p.text;
    document.querySelector('#electrum-progress').value=p.percent;
    document.querySelector('#electrum-progress-note').textContent=ElectrsStatus.note(s);
    I18n.set(language);
   },{compaction,language,theme});
   assert.equal(await page.locator('#electrum-progress-state').innerText(),language==='ko'?'DB 정리 중':language==='en'?'Finalizing database':'DB整理中');
   assert.equal(await page.locator('#electrum-progress-value').innerText(),language==='ko'?'약 64.00%':language==='en'?'≈ 64.00%':'約 64.00%');
   const note=await page.locator('#electrum-progress-note').innerText();
   assert.equal(note,'');
   assert.equal(await page.locator('#electrum-progress').evaluate(el=>el.value),64);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));cases++;
  }
  assert.deepEqual(errors,[]);console.log(JSON.stringify({status:'PASS',scope:'component layout',cases,widths:[390,1440],languages:['ko','en','ja'],themes:['teal','amber','green','ice'],checks:['internal stages hidden without additional UI rows','DB percentage replaces block-height ratio during finalization','estimated percentage and state translated','no horizontal overflow or script errors']}));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
