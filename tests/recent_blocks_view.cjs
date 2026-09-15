'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context=vm.createContext({});vm.runInContext(fs.readFileSync('web/static/dashboard.js','utf8'),context);
const create=vm.runInContext('RecentBlocks.create',context);
const row=(hash,ready=true)=>({hash,height:10,size:ready?1234567:undefined,miner:{status:ready?'identified':'pending',name:ready?'Pool':undefined}});
const snapshot=(list,chain='regtest',error=null)=>({rpc:{getblockchaininfo:{value:{chain}},recentblocks:{value:list,error}}});
const hashes=value=>Array.from(value.list,b=>b.hash);
let view=create();
assert.deepEqual(hashes(view.update(snapshot([row('a',false)]),0)),[]);
assert.deepEqual(hashes(view.update(snapshot([row('a')]),100)),['a']);
let next=[row('b',false),row('a')];
let value=view.update(snapshot(next),200);assert.deepEqual(hashes(value),['a']);assert(value.waiting);
next[0].size=100;assert.equal(value.list[0].hash,'a'); // Snapshot mutations cannot alter the visible batch.
value=view.update(snapshot([row('b'),row('a')]),300);assert.deepEqual(hashes(value),['b','a']);assert(!value.waiting);
value=view.update(snapshot([row('b',false),row('a',false)]),400);assert(!value.waiting);assert.equal(value.list[0].size,1234567);
view.update(snapshot([row('c',false)]),1000);
assert.deepEqual(hashes(view.update(snapshot([row('d',false)]),30999)),['b','a']);
value=view.update(snapshot([row('e',false)]),31000);assert.deepEqual(hashes(value),['e']);assert(value.partial); // Advancing IBD cannot postpone the bound.
value=view.update(snapshot([row('e')]),31001);assert(!value.partial);assert.equal(value.list[0].size,1234567);
value=view.update(snapshot([{hash:'failed',miner:{status:'unavailable'}}]),31002);assert.deepEqual(hashes(value),['failed']);assert.equal(value.list[0].size,undefined);
view.update(snapshot([row('fork',false)]),32000);
value=view.update(snapshot([row('fork')]),32001);assert.deepEqual(hashes(value),['fork']); // Whole-list replacement also removes invalidated blocks.
assert.deepEqual(hashes(view.update(snapshot([], 'regtest', 'timeout'),32002)),['fork']);
assert.deepEqual(hashes(view.update(snapshot([row('other',false)],'testnet4'),32003)),[]);
assert.deepEqual(hashes(view.update(snapshot([row('other')],'testnet4'),32004)),['other']);
view=create();view.update(snapshot([row('unknown',false)]),0);
value=view.update(snapshot([row('unknown',false)]),30000);assert(value.partial);assert.equal(value.list[0].size,undefined);
for(const status of ['unknown','ambiguous'])assert(!view.update(snapshot([{...row(status),miner:{status}}]),30001).waiting);
if(process.argv[2]){
 const trace=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));assert.equal(trace.status,'PASS');
 view=create();let previous=[],swaps=0,held=0;
 for(const observation of trace.observations){
  const output=view.update(observation.snapshot,observation.elapsed_ms),current=hashes(output);
  if(output.waiting&&previous.length&&JSON.stringify(current)===JSON.stringify(previous))held++;
  if(current.length&&JSON.stringify(current)!==JSON.stringify(previous)){
   swaps++;assert(!output.partial,'Real delayed RPC should resolve before the fallback bound');
   for(const b of output.list)assert(Number.isSafeInteger(b.size)&&b.size>0,'Published live batch must contain actual sizes');
  }
  previous=current;
 }
 assert(swaps>=3,'Expected initial, mined and reorganized batches');assert(held>0,'Expected retention while real RPC was delayed');
 console.log(JSON.stringify({status:'PASS',observations:trace.observations.length,complete_batch_swaps:swaps,retained_pending_observations:held}));
}
console.log('PASS: atomic details, first load, bounded wait across changing tips, failed lookup, recovery, hash retention, reorg and network isolation');
