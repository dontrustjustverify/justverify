// Replay real observations from the isolated public testnet4 VM through the UI formatter.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const input = process.argv[2];
assert(input, 'Provide the recorded VM timeline');
const rows = fs.readFileSync(input, 'utf8').trim().split('\n').map(JSON.parse);
const context = vm.createContext({});
vm.runInContext(fs.readFileSync('web/static/electrs_status.js', 'utf8') + '\nthis.view = ElectrsStatus;', context);
let waiting = 0, ready = 0, indexing = 0;
for (const row of rows) {
  assert.equal(row.network, 'testnet4');
  const status = row.electrs;
  if (!status) continue;
  const rendered = context.view.progress(status, row.time);
  if (status.core_ibd) {
    assert.equal(context.view.isReady(status, row.time), false);
    assert.notEqual(rendered.state, '동기화 완료');
    waiting++;
  }
  if (status.state === 'INDEXING' || status.state === 'FINALIZING') {
    assert.equal(context.view.isReady(status, row.time), false);
    assert.notEqual(rendered.state, '동기화 완료');
    indexing++;
  }
  if (context.view.isReady(status, row.time)) {
    assert.equal(status.height, status.target_height);
    assert.equal(rendered.percent, 100);
    assert.equal(rendered.state, '동기화 완료');
    ready++;
  }
}
assert(waiting > 0, 'Real IBD observations required');
assert(indexing > 0, 'Real indexing observations required');
assert(ready > 0, 'Real completed observations required');
console.log(JSON.stringify({status: 'PASS', network: 'testnet4', observations: rows.length,
  core_waiting: waiting, indexing_or_finalizing: indexing, ready,
  checks: ['IBD and indexing never labelled complete', 'actual READY renders 100.00% and synchronization complete']}));
