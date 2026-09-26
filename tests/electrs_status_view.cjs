const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx=vm.createContext({});
vm.runInContext(fs.readFileSync('web/static/electrs_status.js','utf8')+';globalThis.rows=ElectrsStatus.rows;globalThis.progress=ElectrsStatus.progress;globalThis.note=ElectrsStatus.note;',ctx);
let rows=ctx.rows({state:'INDEXING',height:1234,height_updated:100,height_stale:false,rpc_error:'Electrum response delayed'},102);
assert.equal(rows[1][1],'블록 인덱싱 중');assert.equal(rows[0][1],'1,234');assert.equal(rows.length,2);
assert.equal(ctx.note({state:'INDEXING',rpc_error:'Electrum response delayed'},102),'');
assert.equal(ctx.note({state:'VERIFYING',rpc_error:'Electrum response delayed'},102),'응답 대기 · 자동 재확인');
rows=ctx.rows({state:'STALE',height:1234,height_updated:100,height_stale:true},108);
assert.equal(rows[0][1],'1,234');assert.equal(rows[1][1],'응답 대기');assert.equal(ctx.note({state:'STALE',height_updated:100,height_stale:true},108),'이전에 확인한 진행률 · 자동 재확인');
rows=ctx.rows({state:'READY',height:42,height_updated:100,rpc_updated:100,wallet_ready:true},102);
assert.equal(rows[1][1],'동기화 완료');assert.equal(ctx.note({state:'READY',height:42,height_updated:100,rpc_updated:100,wallet_ready:true},102),'');
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

assert.equal(ctx.progress({state:'FINALIZING',height:100,target_height:100}).state,'DB 정리 중');

assert.equal(ctx.progress({state:'RESOURCE_ERROR',height:99,target_height:100}).state,'파일·소켓 한도 오류');
assert.equal(ctx.progress({state:'CONNECTION_ERROR'}).state,'Electrum 수신 연결 오류');
vm.runInContext('globalThis.isReady=ElectrsStatus.isReady',ctx);
assert(ctx.isReady({state:'READY',wallet_ready:true,height_updated:100,rpc_updated:100},102));
assert(!ctx.isReady({state:'READY',wallet_ready:true,height_updated:100,rpc_updated:100},120));
assert(!ctx.isReady({state:'RESOURCE_ERROR',wallet_ready:false,height_updated:100,rpc_updated:100},102));
assert(fs.readFileSync('web/static/dashboard.js','utf8').includes('!ElectrsStatus.isReady(electrsSnapshot)'));

// Whole-DB progress uses measured work, independently of the near-tip height.
for(const compaction of ['config','headers','txid','funding','spending']){
 const status={state:'FINALIZING',compaction,compaction_percent_basis_points:6400,height:968196,target_height:968197};
 assert.equal(ctx.progress(status,101).percent,64);
 assert.equal(ctx.progress(status,101).text,'약 64.00%');
 assert.equal(ctx.progress(status,101).state,'DB 정리 중');
 assert.equal(ctx.rows(status,101).length,2);
 assert.equal(ctx.note(status,101),'');assert(!ctx.isReady(status,101));
}
for(const points of [null,undefined,-1,10000,NaN,'6400'])assert.equal(ctx.progress({state:'FINALIZING',compaction_percent_basis_points:points}).percent,null);
assert.equal(ctx.progress({state:'CATCHING_UP',height:100,target_height:100}).percent,99.99);
assert.equal(ctx.progress({state:'CATCHING_UP'}).state,'최신 블록 반영 중');
assert.equal(ctx.progress({state:'READY',height:100,target_height:100,wallet_ready:true,height_updated:100,rpc_updated:100},101).percent,100);
assert.equal(ctx.progress({state:'READY',compaction:'funding',wallet_ready:true,height_updated:100,rpc_updated:100},101).state,'동기화 완료');
console.log('PASS: separate DB percentage, no stage counters or additional rows, catch-up and strict readiness');
