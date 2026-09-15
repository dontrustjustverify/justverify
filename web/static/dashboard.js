'use strict';
// Core sync is independent of block arrival intervals and displayed percentages.
const CoreStatus=(()=>{
 const labels={syncing:'동기화 중',delayed:'상태갱신 지연',synced:'동기화 완료'};
 function state(snapshot,now=Date.now()/1000,transportFailed=false){
  const sample=snapshot?.rpc?.getblockchaininfo,chain=sample?.value;
  const fresh=stamp=>Number.isFinite(stamp)&&stamp>0&&now-stamp<=15;
  if(transportFailed||!fresh(snapshot?.collected)||!fresh(sample?.updated)||sample?.error)return 'delayed';
  if(typeof chain?.initialblockdownload!=='boolean'||!Number.isSafeInteger(chain.blocks)||!Number.isSafeInteger(chain.headers)||chain.blocks<0||chain.headers<chain.blocks)return 'delayed';
  return chain.initialblockdownload||chain.blocks<chain.headers?'syncing':'synced';
 }
 function render(target,value){
  if(target.dataset.syncState===value&&target.querySelector('svg'))return;
  target.dataset.syncState=value;target.setAttribute('aria-live','polite');target.setAttribute('aria-atomic','true');
  const slot=document.createElement('span');slot.className='sync-icon';slot.setAttribute('aria-hidden','true');
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('focusable','false');
  // Independent line artwork matching the existing logout/copy icon style.
  const paths={syncing:['M4 10a8 8 0 0 1 14-4l3 3m0-5v5h-5','M20 14a8 8 0 0 1-14 4l-3-3m0 5v-5h5'],delayed:['M6 3h12M6 21h12','M7 3v4c0 2 3 3.5 5 5-2 1.5-5 3-5 5v4M17 3v4c0 2-3 3.5-5 5 2 1.5 5 3 5 5v4'],synced:['m5 12 4.5 4.5L19 7']};
  for(const d of paths[value]){const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',d);svg.append(path);}
  slot.append(svg);const label=document.createElement('span');label.className='sync-label';label.textContent=labels[value];target.replaceChildren(slot,label);
 }
 return {state,render};
})();
// Read-only presentation of the same snapshot used by the native TUI.
const NodeView=(()=>{
 const find=id=>document.getElementById(id);let timer,watchdog,mode='lan',generation=0,controller,endpointInfo,electrsSnapshot,coreIbd,lastSnapshot,transportFailed=false;
 function updateStatus(){CoreStatus.render(find('live-state'),CoreStatus.state(lastSnapshot,Date.now()/1000,transportFailed));}
 const text=v=>v===null||v===undefined?'—':String(v).replace(/[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]/g,'');
 const fmt=v=>v===null||v===undefined?'—':Number(v).toLocaleString('ko-KR');
 const bytes=v=>v==null?'—':Number(v)>=1073741824?(v/1073741824).toFixed(1)+' GiB':Number(v)>=1048576?(v/1048576).toFixed(1)+' MiB':fmt(v)+' B';
 function duration(v){if(v==null)return '—';v=Math.max(0,Math.floor(v));return v>=86400?Math.floor(v/86400)+'일 '+Math.floor(v%86400/3600)+'시간':v>=3600?Math.floor(v/3600)+'시간 '+Math.floor(v%3600/60)+'분':v>=60?Math.floor(v/60)+'분':v+'초';}
 function element(tag,value,cls){const e=document.createElement(tag);if(value!==undefined)e.textContent=text(value);if(cls)e.className=cls;return e;}
 function rows(id,entries){const target=find(id);target.replaceChildren();for(const [label,val] of entries){target.append(element('dt',label),element('dd',text(val)));}}
 function meter(label,value,max){const row=element('div',undefined,'meter-row');row.append(element('span',label),element('strong',value==null||!max?'—':(value/max*100).toFixed(1)+'%'));const bar=element('meter');bar.min=0;bar.max=max||100;bar.value=value||0;bar.setAttribute('aria-label',label);row.append(bar);return row;}
 async function api(path,signal){const r=await fetch(path,{headers:{'X-CSRF-Token':csrf},signal});if(r.status===401)throw Error('로그인이 만료되었습니다. 다시 로그인하세요.');if(!r.ok)throw Error(await r.text());return r.json();}
 function render(s){
  const now=Date.now()/1000,rpc=s.rpc||{},host=s.host||{};
  const sample=m=>rpc[m]||{},v=(m,k)=>sample(m).value?.[k],sampleAge=m=>Math.max(0,now-(sample(m).updated||0)),fresh=m=>!!sample(m).updated&&!sample(m).error&&sampleAge(m)<=15;
  for(const [panel,methods] of [['summary',['getblockchaininfo','getnetworkinfo']],['network',['getnetworkinfo','getnettotals','getmempoolinfo','estimatesmartfee']],['blocks',['recentblocks']],['peers',['getpeerinfo']]]){document.querySelector('.panel.'+panel).classList.toggle('stale-data',methods.some(m=>sample(m).updated>0&&!fresh(m)));}
  const core=sample('getblockchaininfo'),ok=fresh('getblockchaininfo');
  lastSnapshot=s;transportFailed=false;updateStatus();
  find('node-notice').hidden=true;find('node-notice').textContent='';
  rows('summary-data',[
   ['버전',v('getnetworkinfo','subversion')],['네트워크',v('getblockchaininfo','chain')],['블록 / 헤더',fmt(v('getblockchaininfo','blocks'))+' / '+fmt(v('getblockchaininfo','headers'))],
   ['검증 진행률',v('getblockchaininfo','verificationprogress')==null?'—':(v('getblockchaininfo','verificationprogress')*100).toFixed(3)+'%'],['초기 동기화 (IBD)',v('getblockchaininfo','initialblockdownload')==null?'대기':v('getblockchaininfo','initialblockdownload')?'진행 중':'완료'],['체인 용량',bytes(v('getblockchaininfo','size_on_disk'))],['기기 가동 시간',duration(host.uptime)]]);
  rows('network-data',[['연결된 피어',fmt(v('getnetworkinfo','connections'))],['들어옴 / 나감',fmt(v('getnetworkinfo','connections_in'))+' / '+fmt(v('getnetworkinfo','connections_out'))],['수신 / 송신',bytes(v('getnettotals','totalbytesrecv'))+' / '+bytes(v('getnettotals','totalbytessent'))],['미확인 거래',fmt(v('getmempoolinfo','size'))+' tx'],['Mempool 크기',bytes(v('getmempoolinfo','bytes'))]]);
  const fee=(m,k)=>v(m,k)==null?'추정 불가':(Number(v(m,k))*100000).toFixed(3);
  rows('fees-data',[['6블록 이내 추정',fee('estimatesmartfee','feerate')],['Mempool 최저',fee('getmempoolinfo','mempoolminfee')],['Relay 최저',fee('getmempoolinfo','minrelaytxfee')]]);
  const blocks=find('blocks-data');blocks.replaceChildren();const list=sample('recentblocks').value||[];
  if(sample('recentblocks').error&&sample('recentblocks').updated>0)blocks.append(element('p','블록 목록 갱신 지연 · 이전에 확인한 블록입니다.','hint'));
  else if(list.length&&list[0].hash!==core.value?.bestblockhash)blocks.append(element('p',v('getblockchaininfo','initialblockdownload')?'초기 동기화 중 · 블록 목록은 15초 간격으로 갱신합니다.':'새 블록 목록을 갱신하고 있습니다.','hint'));
  for(const b of list){const card=element('article',undefined,'block-row');const heading=element('h4',undefined,'block-heading');const miner=b.miner||{};const name=miner.status==='identified'?miner.name:miner.status==='pending'?'채굴 풀 확인 중':miner.status==='unavailable'?'조회 불가':miner.status==='ambiguous'?'식별 불확실':'알 수 없음';const pool=element('span',name,'block-miner');pool.title=miner.status==='identified'?'보상 거래의 태그·주소로 추정한 채굴 풀입니다. 실제 채굴자 신원을 보증하지 않습니다.':'블록의 보상 거래에서 채굴 풀을 식별하지 못했습니다.';const identity=element('span',undefined,'block-identity');const size=element('span',Number.isSafeInteger(b.size)&&b.size>0?(b.size/1000000).toFixed(2)+' MB':'— MB','block-size');identity.append(element('span','블록 '+fmt(b.height)),size);heading.append(identity,pool);card.append(heading,element('p',fmt(b.nTx)+' transactions · '+duration(now-b.time)+' 전'),element('code',b.hash));blocks.append(card);}
  if(!list.length)blocks.append(element('p','첫 블록 정보를 기다리고 있습니다.','empty'));
  const peers=find('peers-data');peers.replaceChildren();const peersList=sample('getpeerinfo').value||[];
  for(const p of peersList){const row=element('div',undefined,'peer-row');row.append(element('span',p.inbound?'IN':'OUT','direction'),element('code',p.addr),element('small',p.subver));peers.append(row);}
  if(!peersList.length)peers.append(element('p',ok?'현재 연결된 피어가 없습니다.':'Core 연결 후 피어가 표시됩니다.','empty'));
  find('system-meters').replaceChildren(meter('CPU',host.cpu_percent==null?null:Number(host.cpu_percent),100),meter('RAM',host.used_memory_mib,host.total_memory_mib));
  const disk=(host.disks||[]).find(d=>d.mount==='/srv/justverify/data');
  rows('system-data',[['메모리',fmt(host.used_memory_mib)+' / '+fmt(host.total_memory_mib)+' MiB'],['데이터 여유 공간',disk?bytes(disk.available):'—'],...ElectrsStatus.rows(host.electrs,now)]);
 }
 async function refresh(current){
  const request=new AbortController();controller=request;const timeout=setTimeout(()=>request.abort(),10000);
  try{const s=await api('/dashboard',request.signal);if(current===generation)render(s);}
  catch(e){if(current===generation){transportFailed=true;updateStatus();}}
  finally{clearTimeout(timeout);if(controller===request)controller=null;if(current===generation)timer=setTimeout(()=>refresh(current),2000);}
 }
 function start(){stop();lastSnapshot=null;transportFailed=false;updateStatus();watchdog=setInterval(updateStatus,1000);refresh(generation);}
 function stop(){clearTimeout(timer);clearInterval(watchdog);generation++;controller?.abort();controller=null;}
 function updateElectrumNotice(){
  if(!endpointInfo)return;
  find('electrum-state').textContent=coreIbd===true?'Core 초기 동기화 중 · electrs와 지갑 연결 준비는 동기화가 끝난 뒤 확인하세요.':ElectrsStatus.progress(electrsSnapshot).state!=='준비 완료'?'electrs 인덱싱·연결 대기 · 아래 주소는 설정된 주소이며, 아직 지갑 연결 준비가 확인되지 않았습니다.':endpointInfo.service_active&&endpointInfo.backend_active?'연결 서비스 실행 중 · 주소 또는 QR 이미지를 사용하세요. 지갑에서 동기화 상태를 확인하세요.':'연결 대기 · 아래는 기기에 설정된 주소입니다. 연결 서비스를 시작해야 사용할 수 있습니다.';
 }
 function renderElectrumProgress(status,ibd){
  electrsSnapshot=status;coreIbd=ibd;
  const p=ElectrsStatus.progress(status),bar=find('electrum-progress');
  bar.value=p.percent===null?0:p.percent;
  bar.setAttribute('aria-valuetext',p.text);find('electrum-progress-value').textContent=p.text;
  find('electrum-progress-state').textContent=p.state;
  const detail=ElectrsStatus.rows(status);
  find('electrum-progress-note').textContent=I18n.text(detail[2][1])+' · '+I18n.text(detail[3][1]);
  updateElectrumNotice();
 }
 async function refreshElectrum(current){
  const request=new AbortController();controller=request;const timeout=setTimeout(()=>request.abort(),8000);
  try{const s=await api('/dashboard',request.signal);if(current===generation)renderElectrumProgress(s.host?.electrs,s.rpc?.getblockchaininfo?.value?.initialblockdownload);}
  catch(e){if(current===generation){electrsSnapshot={...electrsSnapshot,state:'STALE',wallet_ready:false};find('electrum-progress-state').textContent='상태 갱신 지연';find('electrum-progress-note').textContent='이전에 확인한 진행률 · 자동 재확인';updateElectrumNotice();}}
  finally{clearTimeout(timeout);if(controller===request)controller=null;if(current===generation)timer=setTimeout(()=>refreshElectrum(current),2000);}
 }
 async function connection(selected='lan'){
  stop();mode=selected;endpointInfo=null;const current=generation;refreshElectrum(current);find('electrum-details').hidden=true;find('electrum-state').textContent='연결 정보를 확인하는 중…';find('qr-save').removeAttribute('href');
  document.querySelectorAll('[data-network]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.network===mode)));
  try{const d=await api('/electrum?network='+mode);if(current!==generation)return;
   const matrix=d.matrix,n=matrix?.length;if(!Array.isArray(matrix)||n<21||n>185||!matrix.every(row=>Array.isArray(row)&&row.length===n&&row.every(x=>typeof x==='boolean')))throw Error('QR 데이터를 확인할 수 없습니다.');
   rows('electrum-data',[['접속 방식',mode==='lan'?'로컬 네트워크':'Tor'],['프로토콜',d.protocol],['TLS / SSL',d.tls?'사용 · 지갑에서 SSL/TLS 선택':'사용 안 함 · Tor 전송'],['포트',d.payload.split(':').at(-1)]]);
   find('electrum-address').value=d.payload;CopyAddress.enhance(find('electrum-address'));find('electrum-help').textContent=mode==='lan'?'같은 LAN의 지갑에서 SSL/TLS를 선택하고 기기 인증서를 확인하세요.':'지갑에서 Tor를 활성화하거나 Tor SOCKS 프록시를 설정하세요.';
   find('electrum-fingerprint').textContent=d.certificate_sha256?'인증서 SHA256: '+d.certificate_sha256:'';
   const canvas=find('electrum-qr'),scale=8;canvas.width=canvas.height=n*scale;const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#000';matrix.forEach((row,y)=>row.forEach((on,x)=>{if(on)ctx.fillRect(x*scale,y*scale,scale,scale);}));
   find('qr-save').href=canvas.toDataURL('image/png');endpointInfo=d;updateElectrumNotice();find('electrum-details').hidden=false;
  }catch(e){if(current===generation)find('electrum-state').textContent=e.message;}
 }
 return {start,stop,connection};
})();
