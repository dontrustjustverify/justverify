'use strict';
// Progress is an indexer observation; wallet readiness additionally requires Electrum RPC.
const ElectrsStatus=(()=>{
 const labels={READY:'준비 완료',INDEXING:'인덱싱 중',INDEX_ERROR:'인덱스 오류 · 점검 필요',CORE_SYNCING:'Core 동기화 대기',VERIFYING:'인덱스·지갑 응답 확인 중',UNAVAILABLE:'연결 확인 필요',STALE:'상태 갱신 지연',STARTING:'첫 응답 대기'};
 function ready(status,at){return status.wallet_ready===true&&status.state==='READY'&&!status.height_stale&&!status.target_stale&&status.rpc_updated>0&&status.rpc_updated<=at&&at-status.rpc_updated<=15&&status.height_updated>0&&at-status.height_updated<=15;}
 function progress(status={},at=Date.now()/1000){
  const valid=Number.isSafeInteger(status.height)&&status.height>=0&&Number.isSafeInteger(status.target_height)&&status.target_height>=0;
  // Floor avoids rounding an unfinished index to 100%. Height completion is not wallet readiness.
  const percent=valid?(status.target_height===0?(status.height===0?100:null):Math.min(100,Math.floor(status.height/status.target_height*10000)/100)):null;
  return {percent,text:percent===null?'—':percent.toFixed(2)+'% ('+status.height.toLocaleString('ko-KR')+' / '+status.target_height.toLocaleString('ko-KR')+')',state:status.state==='READY'&&!ready(status,at)?labels.STALE:labels[status.state]||'첫 응답 대기'};
 }
 function rows(status={},at=Date.now()/1000){
  const valid=Number.isSafeInteger(status.height)&&status.height>=0;
  const updated=Number.isFinite(status.height_updated)&&status.height_updated>0?status.height_updated:0;
  const age=updated?Math.max(0,Math.floor(at-updated)):null;
  const stale=status.height_stale===true||age===null||age>15;
  const state=progress(status,at).state;
  const height=valid?status.height.toLocaleString('ko-KR'):'—';
  const freshness=status.target_stale?'Core 높이 갱신 지연':age===null?'아직 확인하지 못함':stale?'마지막 확인 · '+age+'초 전':age+'초 전';
  const wallet=ready(status,at)?'준비 완료':status.rpc_error==='Electrum response delayed'?'응답 지연 · 자동 재확인':status.rpc_error?'연결 확인 필요':status.state==='INDEXING'?'인덱싱 완료 대기':'확인 중';
  const p=progress(status,at);
  return [['electrs',p.percent===null?height:p.text],['인덱싱 상태',state],['높이 조회',freshness],['지갑 응답',wallet]];
 }
 return {rows,progress};
})();
