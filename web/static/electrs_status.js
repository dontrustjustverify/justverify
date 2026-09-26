'use strict';
// Progress is an indexer observation; wallet readiness additionally requires Electrum RPC.
const ElectrsStatus=(()=>{
 const labels={READY:'동기화 완료',FINALIZING:'DB 정리 중',INDEXING:'블록 인덱싱 중',CATCHING_UP:'최신 블록 반영 중',INDEX_ERROR:'인덱스 오류 · 점검 필요',CONNECTION_ERROR:'Electrum 수신 연결 오류',RESOURCE_ERROR:'파일·소켓 한도 오류',CORE_SYNCING:'Core 동기화 대기',VERIFYING:'연결 준비 확인 중',UNAVAILABLE:'연결 확인 필요',STALE:'응답 대기',STARTING:'첫 응답 대기'};
 function ready(status={},at=Date.now()/1000){return status.wallet_ready===true&&status.state==='READY'&&!status.height_stale&&!status.target_stale&&status.rpc_updated>0&&status.rpc_updated<=at&&at-status.rpc_updated<=15&&status.height_updated>0&&at-status.height_updated<=15;}
 function progress(status={},at=Date.now()/1000){
  const valid=Number.isSafeInteger(status.height)&&status.height>=0&&Number.isSafeInteger(status.target_height)&&status.target_height>0;
  const isReady=ready(status,at),db=status.state==='FINALIZING';
  const points=status.compaction_percent_basis_points;
  const percent=db?(Number.isSafeInteger(points)&&points>=0&&points<10000?points/100:null):valid?Math.min(isReady?100:99.99,Math.floor(status.height/status.target_height*10000)/100):null;
  const state=status.state==='READY'&&!isReady?labels.STALE:labels[status.state]||'첫 응답 대기';
  const text=percent===null?'—':db?'약 '+percent.toFixed(2)+'%':percent.toFixed(2)+'% ('+status.height.toLocaleString('ko-KR')+' / '+status.target_height.toLocaleString('ko-KR')+')';
  return {percent,text,state};
 }
 function rows(status={},at=Date.now()/1000){
  const valid=Number.isSafeInteger(status.height)&&status.height>=0;
  const state=progress(status,at).state;
  const height=valid?status.height.toLocaleString('ko-KR'):'—';
  const p=progress(status,at);
  return [['electrs',p.percent===null&&status.state!=='FINALIZING'?height:p.text],['인덱싱 상태',state]];
 }
 function note(status={},at=Date.now()/1000){
  if(status.state==='STALE'||status.height_stale||status.target_stale||(status.state==='READY'&&!ready(status,at)))return '이전에 확인한 진행률 · 자동 재확인';
  if(status.state==='FINALIZING')return '';
  if(status.state==='CORE_SYNCING'||status.state==='INDEXING'||status.state==='CATCHING_UP'||ready(status,at))return '';
  return status.rpc_error==='Electrum response delayed'?'응답 대기 · 자동 재확인':'';
 }
 return {rows,progress,note,isReady:ready};
})();
