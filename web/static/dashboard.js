'use strict';
// Read-only presentation of the same snapshot used by the native TUI.
const NodeView=(()=>{
 const find=id=>document.getElementById(id);let timer,mode='lan',generation=0;
 const text=v=>v===null||v===undefined?'—':String(v).replace(/[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]/g,'');
 const fmt=v=>v===null||v===undefined?'—':Number(v).toLocaleString('ko-KR');
 const bytes=v=>v==null?'—':Number(v)>=1073741824?(v/1073741824).toFixed(1)+' GiB':Number(v)>=1048576?(v/1048576).toFixed(1)+' MiB':fmt(v)+' B';
 function duration(v){if(v==null)return '—';v=Math.max(0,Math.floor(v));return v>=86400?Math.floor(v/86400)+'일 '+Math.floor(v%86400/3600)+'시간':v>=3600?Math.floor(v/3600)+'시간 '+Math.floor(v%3600/60)+'분':v>=60?Math.floor(v/60)+'분':v+'초';}
 function element(tag,value,cls){const e=document.createElement(tag);if(value!==undefined)e.textContent=text(value);if(cls)e.className=cls;return e;}
 function rows(id,entries){const target=find(id);target.replaceChildren();for(const [label,val] of entries){target.append(element('dt',label),element('dd',text(val)));}}
 function meter(label,value,max){const row=element('div',undefined,'meter-row');row.append(element('span',label),element('strong',value==null||!max?'—':(value/max*100).toFixed(1)+'%'));const bar=element('meter');bar.min=0;bar.max=max||100;bar.value=value||0;bar.setAttribute('aria-label',label);row.append(bar);return row;}
 async function api(path){const r=await fetch(path,{headers:{'X-CSRF-Token':csrf}});if(r.status===401)throw Error('로그인이 만료되었습니다. 다시 로그인하세요.');if(!r.ok)throw Error(await r.text());return r.json();}
 function render(s){
  const now=Date.now()/1000,age=Math.max(0,now-s.collected),rpc=s.rpc||{},host=s.host||{};
  const sample=m=>rpc[m]||{},v=(m,k)=>sample(m).value?.[k];
  for(const [panel,methods] of [['summary',['getblockchaininfo','getnetworkinfo']],['network',['getnetworkinfo','getnettotals','getmempoolinfo','estimatesmartfee']],['blocks',['recentblocks']],['peers',['getpeerinfo']]]){document.querySelector('.panel.'+panel).classList.toggle('stale-data',(age>15&&s.collected>0)||methods.some(m=>sample(m).error&&sample(m).updated>0));}
  const core=sample('getblockchaininfo'),ok=!!core.updated&&!core.error&&age<=15;
  find('live-state').textContent=ok?'● 실시간 · '+Math.floor(age)+'초 전':'○ 연결 확인 필요';find('live-state').classList.toggle('unavailable',!ok);
  find('node-notice').hidden=ok;find('node-notice').textContent=core.updated?'현재 연결이 끊겼습니다. 아래 값은 마지막 수집 데이터입니다.':'Core에 연결하는 중입니다. 초기 시작 상태는 위 안내에서 확인하세요.';
  rows('summary-data',[
   ['버전',v('getnetworkinfo','subversion')],['네트워크',v('getblockchaininfo','chain')],['블록 / 헤더',fmt(v('getblockchaininfo','blocks'))+' / '+fmt(v('getblockchaininfo','headers'))],
   ['검증 진행률',v('getblockchaininfo','verificationprogress')==null?'—':(v('getblockchaininfo','verificationprogress')*100).toFixed(3)+'%'],['초기 동기화 (IBD)',v('getblockchaininfo','initialblockdownload')==null?'대기':v('getblockchaininfo','initialblockdownload')?'진행 중':'완료'],['체인 용량',bytes(v('getblockchaininfo','size_on_disk'))],['기기 가동 시간',duration(host.uptime)]]);
  rows('network-data',[['연결된 피어',fmt(v('getnetworkinfo','connections'))],['들어옴 / 나감',fmt(v('getnetworkinfo','connections_in'))+' / '+fmt(v('getnetworkinfo','connections_out'))],['수신 / 송신',bytes(v('getnettotals','totalbytesrecv'))+' / '+bytes(v('getnettotals','totalbytessent'))],['미확인 거래',fmt(v('getmempoolinfo','size'))+' tx'],['Mempool 크기',bytes(v('getmempoolinfo','bytes'))]]);
  const fee=(m,k)=>v(m,k)==null?'추정 불가':(Number(v(m,k))*100000).toFixed(3);
  rows('fees-data',[['6블록 이내 추정',fee('estimatesmartfee','feerate')],['Mempool 최저',fee('getmempoolinfo','mempoolminfee')],['Relay 최저',fee('getmempoolinfo','minrelaytxfee')]]);
  const blocks=find('blocks-data');blocks.replaceChildren();const list=sample('recentblocks').value||[];
  if(sample('recentblocks').error&&sample('recentblocks').updated>0)blocks.append(element('p','이전 블록 정보 · 현재 tip 확인 불가','hint'));
  for(const b of list){const card=element('article',undefined,'block-row');const heading=element('h4',undefined,'block-heading');const miner=b.miner||{};const name=miner.status==='identified'?miner.name:miner.status==='unavailable'?'조회 불가':miner.status==='ambiguous'?'식별 불확실':'알 수 없음';const pool=element('span',name,'block-miner');pool.title=miner.status==='identified'?'보상 거래의 태그·주소로 추정한 채굴 풀입니다. 실제 채굴자 신원을 보증하지 않습니다.':'블록의 보상 거래에서 채굴 풀을 식별하지 못했습니다.';heading.append(element('span','블록 '+fmt(b.height)),pool);card.append(heading,element('p',fmt(b.nTx)+' transactions · '+duration(now-b.time)+' 전'),element('code',b.hash));blocks.append(card);}
  if(!list.length)blocks.append(element('p','첫 블록 정보를 기다리고 있습니다.','empty'));
  const peers=find('peers-data');peers.replaceChildren();const peersList=sample('getpeerinfo').value||[];
  for(const p of peersList){const row=element('div',undefined,'peer-row');row.append(element('span',p.inbound?'IN':'OUT','direction'),element('code',p.addr),element('small',p.subver));peers.append(row);}
  if(!peersList.length)peers.append(element('p',ok?'현재 연결된 피어가 없습니다.':'Core 연결 후 피어가 표시됩니다.','empty'));
  find('system-meters').replaceChildren(meter('CPU',host.cpu_percent==null?null:Number(host.cpu_percent),100),meter('RAM',host.used_memory_mib,host.total_memory_mib));
  const disk=(host.disks||[]).find(d=>d.mount==='/srv/justverify/data');
  rows('system-data',[['메모리',fmt(host.used_memory_mib)+' / '+fmt(host.total_memory_mib)+' MiB'],['데이터 여유 공간',disk?bytes(disk.available):'—'],['electrs',host.electrs?.state==='UNAVAILABLE'&&v('getblockchaininfo','initialblockdownload')===true?'연결 대기 · Core 초기 동기화 중':host.electrs?.state],['인덱스 높이',fmt(host.electrs?.height)],['Tor',host.tor?.state]]);
 }
 async function refresh(){try{render(await api('/dashboard'));}catch(e){find('live-state').textContent='○ 연결 끊김';find('live-state').classList.add('unavailable');find('node-notice').hidden=false;find('node-notice').textContent=e.message;}}
 function start(){stop();refresh();timer=setInterval(refresh,2000);}
 function stop(){clearInterval(timer);generation++;}
 async function connection(selected='lan'){
  mode=selected;const current=++generation;find('electrum-details').hidden=true;find('electrum-state').textContent='연결 정보를 확인하는 중…';find('qr-save').removeAttribute('href');
  document.querySelectorAll('[data-network]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.network===mode)));
  try{const d=await api('/electrum?network='+mode);if(current!==generation)return;
   const matrix=d.matrix,n=matrix?.length;if(!Array.isArray(matrix)||n<21||n>185||!matrix.every(row=>Array.isArray(row)&&row.length===n&&row.every(x=>typeof x==='boolean')))throw Error('QR 데이터를 확인할 수 없습니다.');
   rows('electrum-data',[['접속 방식',mode==='lan'?'로컬 네트워크':'Tor'],['프로토콜',d.protocol],['TLS / SSL',d.tls?'사용 · 지갑에서 SSL/TLS 선택':'사용 안 함 · Tor 전송'],['포트',d.payload.split(':').at(-1)]]);
   find('electrum-address').value=d.payload;find('electrum-help').textContent=mode==='lan'?'같은 LAN의 지갑에서 SSL/TLS를 선택하고 기기 인증서를 확인하세요.':'지갑에서 Tor를 활성화하거나 Tor SOCKS 프록시를 설정하세요.';
   find('electrum-fingerprint').textContent=d.certificate_sha256?'인증서 SHA256: '+d.certificate_sha256:'';
   const canvas=find('electrum-qr'),scale=8;canvas.width=canvas.height=n*scale;const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#000';matrix.forEach((row,y)=>row.forEach((on,x)=>{if(on)ctx.fillRect(x*scale,y*scale,scale,scale);}));
   find('qr-save').href=canvas.toDataURL('image/png');find('electrum-state').textContent=d.ibd===true?'Core 초기 동기화 중 · electrs와 지갑 연결 준비는 동기화가 끝난 뒤 확인하세요.':d.index_state!=='READY'?'electrs 인덱싱·연결 대기 · 아래 주소는 설정된 주소이며, 아직 지갑 연결 준비가 확인되지 않았습니다.':d.service_active&&d.backend_active?'연결 서비스 실행 중 · 주소 또는 QR 이미지를 사용하세요. 지갑에서 동기화 상태를 확인하세요.':'연결 대기 · 아래는 기기에 설정된 주소입니다. 연결 서비스를 시작해야 사용할 수 있습니다.';find('electrum-details').hidden=false;
  }catch(e){if(current===generation)find('electrum-state').textContent=e.message;}
 }
 return {start,stop,connection};
})();
