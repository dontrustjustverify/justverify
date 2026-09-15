'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context=vm.createContext({});vm.runInContext(fs.readFileSync('web/static/dashboard.js','utf8'),context);
const classify=vm.runInContext('CoreStatus.state',context);
function sample(overrides={},stamp=1000){return {collected:stamp,rpc:{getblockchaininfo:{updated:stamp,error:null,value:{blocks:500,headers:500,initialblockdownload:false,verificationprogress:0.9999999,time:1,...overrides}}}};}
assert.equal(classify(sample(),1000),'synced'); // Never wait for another block.
assert.equal(classify(sample({initialblockdownload:true}),1000),'syncing');
assert.equal(classify(sample({blocks:499,verificationprogress:1}),1000),'syncing');
assert.equal(classify(sample({blocks:0,headers:0,initialblockdownload:true,verificationprogress:1}),1000),'syncing');
assert.equal(classify(sample(),1015),'synced');
assert.equal(classify(sample(),1015.01),'delayed');
assert.equal(classify(sample(),1000,true),'delayed');
let s=sample();s.rpc.getblockchaininfo.error='RPC timeout';assert.equal(classify(s,1000),'delayed');
s=sample();s.rpc.getblockchaininfo.updated=980;assert.equal(classify(s,1000),'delayed');
s=sample();s.collected=980;assert.equal(classify(s,1000),'delayed');
for(const value of [null,{},sample({initialblockdownload:null}),sample({blocks:501}),sample({blocks:-1}),sample({headers:null})])assert.equal(classify(value,1000),'delayed');
const sequence=[sample({initialblockdownload:true}),sample(),s,sample(),sample({headers:501}),sample({headers:501,blocks:501})];
assert.deepEqual(sequence.map(x=>classify(x,1000)),['syncing','synced','delayed','synced','syncing','synced']);
for(let now=1000;now<10000;now+=60)assert.equal(classify(sample({},now),now),'synced');
if(process.argv[2]){
 const observations=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 for(const observation of observations)assert.equal(classify(observation.snapshot,observation.at,observation.transportFailed||false),observation.expected,observation.name);
 console.log('PASS: '+observations.length+' real Core/collector observations');
}
console.log('PASS: IBD, header lag, rounded 100%, zero height, stalled/failed data, recovery and idle synced state');
