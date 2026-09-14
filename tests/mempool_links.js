'use strict';
// Execute the shipped URL transformations for LAN, IP, onion and all languages.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const app=fs.readFileSync(path.join(root,'web/static/app.js'),'utf8');
const initial=app.split('\n').find(line=>line.startsWith('{const url=new URL(location.href);'));
const device=fs.readFileSync(path.join(root,'web/static/device.js'),'utf8');
const language=device.match(/if\(link\)\{(const url=new URL\(link.href\);[^}]+)\}/)[1];
const integration=fs.readFileSync(path.join(root,'web/static/mempool-integration.js'),'utf8');
const back=integration.match(/(const url=new URL\(location.href\);.*?home.href=url.href;)/)[1];
const onion='a'.repeat(56)+'.onion';
let count=0;
for(const origin of ['http://justverify.local','http://192.168.1.50','http://[fd00::1]','http://'+onion]) {
  for(const lang of ['ko','en','ja']) {
    const link={href:''};
    vm.runInNewContext(initial,{URL,location:{href:origin+'/settings?x=1#account'},$:selector=>{assert.equal(selector,'#mempool-link');return link;}});
    vm.runInNewContext(language,{URL,link,prefs:{language:lang}});
    assert.equal(link.href,origin+':3006/'+(lang==='en'?'en-US':lang)+'/');
    const home={href:''};
    vm.runInNewContext(back,{URL,location:{href:link.href+'?x=1#block'},home});
    assert.equal(home.href,origin+'/');count++;
  }
}
console.log(JSON.stringify({status:'PASS',scope:'shipped JavaScript URL transformations; browser/network tests separate',cases:count}));
