const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx=vm.createContext({});
vm.runInContext(fs.readFileSync('web/static/electrs_status.js','utf8')+';globalThis.rows=ElectrsStatus.rows;globalThis.progress=ElectrsStatus.progress;globalThis.note=ElectrsStatus.note;',ctx);
let rows=ctx.rows({state:'INDEXING',height:1234,height_updated:100,height_stale:false,rpc_error:'Electrum response delayed'},102);
assert.equal(rows[1][1],'인덱싱 중');assert.equal(rows[0][1],'1,234');assert.equal(rows.length,2);
assert.equal(ctx.note({state:'INDEXING',rpc_error:'Electrum response delayed'},102),'');
assert.equal(ctx.note({state:'VERIFYING',rpc_error:'Electrum response delayed'},102),'응답 대기 · 자동 재확인');
rows=ctx.rows({state:'STALE',height:1234,height_updated:100,height_stale:true},108);
assert.equal(rows[0][1],'1,234');assert.equal(rows[1][1],'응답 대기');assert.equal(ctx.note({state:'STALE',height_updated:100,height_stale:true},108),'이전에 확인한 진행률 · 자동 재확인');
rows=ctx.rows({state:'READY',height:42,height_updated:100,rpc_updated:100,wallet_ready:true},102);
assert.equal(rows[1][1],'준비 완료');assert.equal(ctx.note({state:'READY',height:42,height_updated:100,rpc_updated:100,wallet_ready:true},102),'');
assert.equal(ctx.rows({state:'STARTING'},102)[0][1],'—');
assert.equal(ctx.rows({state:'READY',height:42,height_updated:100},120)[1][1],'응답 대기');
for(const status of [{state:'READY',height:42,height_updated:100,rpc_updated:100,wallet_ready:true},{state:'READY',height:42,height_updated:119,rpc_updated:100,wallet_ready:true},{state:'READY',height:42,height_updated:119,rpc_updated:119,wallet_ready:true,target_stale:true}]){
 assert.equal(ctx.progress(status,120).state,'응답 대기');assert.equal(ctx.note(status,120),'이전에 확인한 진행률 · 자동 재확인');
}
assert.equal(ctx.progress({height:99,target_height:100}).percent,99);
assert.equal(ctx.progress({height:999999,target_height:1000000}).percent,99.99);
assert.equal(ctx.progress({height:100,target_height:100,state:'VERIFYING'}).state,'연결 준비 확인 중');
assert.equal(ctx.progress({height:0,target_height:0,state:'CORE_SYNCING'}).percent,null);
assert.equal(ctx.progress({height:42}).percent,null);
const index=fs.readFileSync('web/static/index.html','utf8');assert(index.indexOf('/electrs_status.js')<index.indexOf('/dashboard.js'));
assert(fs.readFileSync('web/server.py','utf8').includes("'electrs_status.js'"));
console.log('PASS: compact progress/state, stale retention and waiting label, readiness timestamps, no routine age/wallet row, initial state and routing');
