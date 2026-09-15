'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('web/static/i18n.js','utf8');
// Exercise the shipped pure locale resolver; actual DOM translation is checked in a browser.
const policy=source.slice(source.indexOf('function detect('),source.indexOf('let language=resolve('));
function run(navigator){const ctx=vm.createContext(navigator?{navigator}:{});vm.runInContext(policy+';this.policy={detect,resolve};',ctx);return ctx.policy;}
for(const [languages,expected] of [[['ko-KR'],'ko'],[['en-GB'],'en'],[['ja-JP'],'ja'],[['KO_kr'],'ko'],[['de-DE','ja-JP','en-US'],'ja'],[['fr-FR'],'en'],[[],'en'],[[null,42,'ko'],'ko']]){
 const p=run({languages});assert.equal(p.resolve('auto'),expected);assert.equal(p.detect(languages),expected);
 for(const explicit of ['ko','en','ja'])assert.equal(p.resolve(explicit),explicit);
}
assert.equal(run().resolve('auto'),'en');assert.equal(run({languages:[],language:'ko-KR'}).resolve('auto'),'ko');
const device=fs.readFileSync('web/static/device.js','utf8');assert(device.includes("row('Language/언어설정/言語設定'"));assert(device.includes("languageLabel.setAttribute('translate','no')"));
console.log('PASS: browser preference order, regional locales, unsupported/missing fallback, explicit choice priority and fixed multilingual label');
