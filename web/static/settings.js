'use strict';
const SettingsView=(()=>{
 const el=id=>document.getElementById(id);let generation=0,kind,state,values={},selection,preview,busy=false,poll;
 const labels={listen:'들어오는 연결',onlynet:'나가는 연결',proxy:'Clearnet 연결에 Tor 사용',blocksonly:'블록만 수신',persistmempool:'재시작 후 Mempool 유지',maxmempool:'Mempool 메모리 상한',mempoolexpiry:'거래 보관 시간',minrelaytxfee:'최소 전파 수수료',incrementalrelayfee:'거래 교체 추가 수수료',dustrelayfee:'Dust 기준 수수료',dbcache:'데이터베이스 캐시',maxconnections:'최대 피어 수',maxuploadtarget:'하루 업로드 한도',datacarrier:'데이터 출력 전파',datacarriersize:'데이터 출력 크기',txindex:'전체 거래 인덱스',blockfilterindex:'블록 필터 인덱스',peerblockfilters:'피어에 블록 필터 제공',peerbloomfilters:'피어 Bloom 필터',rest:'로컬 REST API',permitbaremultisig:'Bare multisig 전파',privatebroadcast:'비공개 거래 브로드캐스트',asmap:'내장 ASMAP 사용',bantime:'피어 차단 시간',timeout:'연결 시간 제한',peertimeout:'피어 응답 대기',maxreceivebuffer:'수신 버퍼',maxsendbuffer:'송신 버퍼'};
 function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
 async function api(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)});if(!r.ok){if(r.status===401)showAuth();throw Error(await r.text());}return r.json();}
 function message(text){el('settings-status').textContent=text;}
 function clearReview(){preview=null;el('settings-review').hidden=true;}
 function changed(){clearReview();message('변경한 값은 아직 적용되지 않았습니다. 변경 내용 확인 후 저장하세요.');}
 function stop(){generation++;clearTimeout(poll);}
 async function open(which){stop();kind=which;const g=generation;el('settings-view').hidden=false;el('settings-content').replaceChildren();clearReview();el('settings-title').textContent=which==='policy'?'Mempool · 네트워크 설정':'버전 변경';message('현재 설정을 불러오는 중…');busy=false;
  try{const s=await api('/'+which,{method:'state'});if(g!==generation)return;state=s;values={...(s.requested||{})};selection=s.active?{version:s.active.instance.core_version,network:s.active.instance.network,watch_only:!!s.active.instance.watch_only}:null;render();message(s.active_error||'');}catch(e){if(g===generation)message(e.message);}
 }
 function button(text,action,cls){const b=node('button',text,cls);b.type='button';b.onclick=action;return b;}
 function toggle(text,on,action){const b=button(text,()=>action(b.getAttribute('aria-checked')!=='true'),'toggle');b.setAttribute('role','switch');b.setAttribute('aria-checked',String(on));return b;}
 function render(){el('settings-content').replaceChildren();if(kind==='policy')policy();else versions();const recovery=state.transaction||state.transition;if(recovery?.needs_recovery){message('이전 변경이 중단되었습니다. 복구 상태를 확인하세요.');el('settings-content').append(button('중단된 변경 복구',()=>operation(async()=>{await api('/'+kind,{method:'recover'});await open(kind);})));}}
 function defaultValue(e){if(e.type==='decimal'){const match=String(e.default).match(/^(\d+)(?:\.(\d+))?$/);if(!match)return '';const raw=BigInt(match[1]+(match[2]||''));const power=(match[2]||'').length-5;if(power<=0)return String(raw*10n**BigInt(-power));const s=String(raw).padStart(power+1,'0');return (s.slice(0,-power)+'.'+s.slice(-power)).replace(/\.?0+$/,'');}return String(e.default??'');}
 function policy(){
  const host=el('settings-content');host.append(node('p',`Bitcoin Core ${state.version} · ${state.network} · 저장하면 Core와 관련 서비스를 재시작합니다.`,'hint'));
  const nav=node('div',undefined,'network-switch');const fields=node('div');host.append(nav,fields);
  const groups={network:'네트워크',mempool:'Mempool · 수수료',resources:'자원 · 인덱스',advanced:'고급'};
  const net=new Set(['listen','onlynet','proxy','maxconnections','maxuploadtarget','maxsendbuffer','maxreceivebuffer','timeout','peertimeout','bantime']);
  const resource=new Set(['dbcache','txindex','blockfilterindex','peerblockfilters','peerbloomfilters','rest','txospenderindex','asmap']);
  let tab='network';
  function rows(){fields.replaceChildren();nav.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===tab)));
   const order=['listen','onlynet','proxy'];const priority=key=>order.includes(key)?order.indexOf(key):99;const sorted=[...state.entries].sort((a,b)=>priority(a.key)-priority(b.key));for(const e of sorted){const group=net.has(e.key)?'network':resource.has(e.key)?'resources':e.advanced?'advanced':'mempool';if(group!==tab)continue;
    const row=node('section',undefined,'setting-row'),info=node('div'),controls=node('div',undefined,'setting-control');row.append(info,controls);fields.append(row);
    info.append(node('h4',labels[e.key]||e.key),node('code',e.key));const help={listen:'다른 노드가 이 노드로 연결할 수 있는 경로입니다. RPC 접근 설정과는 별개입니다.',onlynet:'자동으로 연결할 목적지 네트워크를 선택합니다. 들어오는 연결과 수동으로 추가한 피어에는 적용되지 않습니다.',proxy:'켜면 일반 인터넷의 노드에도 Tor를 경유해 연결합니다. onion 연결은 이 토글과 관계없이 Tor를 사용합니다.'};if(help[e.key])info.append(node('p',help[e.key],'hint'));const details=node('details');details.append(node('summary','Core 옵션 설명'),node('p',e.description,'hint'));info.append(details);
    const supported=e.editable!==false&&!e.ignored_or_wallet_only&&e.source_registration_present===true&&!(e.key==='blockversion'&&state.network!=='regtest');
    const current=values[e.key],fallback=defaultValue(e);let display=current??fallback;
    const note=node('p',`기본값: ${e.default??'N/A'} ${e.type==='decimal'?'BTC/kvB':e.unit||''} · ${current===undefined?'기본값 사용':'지정값: '+current+(e.type==='decimal'?' sat/vB':'')}`,'hint');info.append(node('p',`저장된 요청값: ${state.requested[e.key]??'기본값 사용'}`,'hint'),note);
    if(e.range&&e.range.min!==undefined)info.append(node('p',`입력 범위: ${e.range.min} ~ ${e.range.max}`,'hint'));
    const save=v=>{values[e.key]=v;changed();rows();};
    if(!supported){controls.append(node('span','이 버전·네트워크에서는 변경 불가','hint'));continue;}
    if(['boolean','tor_proxy'].includes(e.type)){controls.append(toggle(labels[e.key]||e.key,String(display).startsWith('1'),on=>save(on?'1':'0')));}
    else if(['incoming_set','network_set'].includes(e.type)){
     const incoming=e.type==='incoming_set';const options=incoming?[['clearnet','Clearnet'],['tor','Tor']]:[['ipv4','Clearnet IPv4'],['ipv6','Clearnet IPv6'],['onion','Tor']];
     if(current===undefined)display=incoming?(state.network==='regtest'?'tor':'clearnet,tor'):'ipv4,ipv6,onion';
     const selected=new Set(display.split(','));for(const [key,label] of options)controls.append(toggle(label,selected.has(key),on=>{if(on)selected.add(key);else selected.delete(key);if(!incoming&&!selected.size){message('나가는 연결은 하나 이상 선택하세요.');return;}save([...selected].sort().join(',')||'none');}));
    }else{
     const input=node('input');input.type='text';input.inputMode=e.type==='decimal'?'decimal':'numeric';input.value=current??'';input.placeholder=fallback;input.setAttribute('aria-label',labels[e.key]||e.key);input.autocomplete='off';input.oninput=()=>{if(input.value.trim())values[e.key]=input.value.trim();else delete values[e.key];changed();note.textContent=`기본값: ${e.default} · ${input.value?'지정값: '+input.value:'기본값 사용'}`;};controls.append(input,node('small',e.type==='decimal'?'sat/vB':e.unit||''));
    }
    controls.append(button('기본값으로',()=>{delete values[e.key];changed();rows();},'subtle'));
   }
  }
  for(const [key,label] of Object.entries(groups)){const b=button(label,()=>{tab=key;rows();});b.dataset.tab=key;nav.append(b);}rows();
  host.append(button('변경 내용 확인',()=>operation(async()=>{preview=await api('/policy',{method:'preview',values});review(preview.plan.changes,preview.plan.warning);}),'primary-action'));
 }
 function versions(){
  const host=el('settings-content'),active=state.active?.instance;host.append(node('p',active?`현재 실행: Bitcoin Core ${active.core_version} · ${active.network}`:'최초 노드 시작을 준비하고 있습니다.','hint'));
  const all=node('input');all.type='checkbox';all.id='all-versions';const label=node('label','이전 패치 버전까지 보기','inline-check');label.prepend(all);host.append(label);
  const cards=node('div',undefined,'version-grid');host.append(cards);const detail=node('div',undefined,'version-detail');host.append(detail);
  if(!selection){const last=state.releases.filter(r=>r.downloaded).at(-1);if(last)selection={version:last.version,network:'main',watch_only:false};}
  function choose(){detail.replaceChildren();clearReview();const release=state.releases.find(r=>r.version===selection?.version);if(!release)return;
   cards.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.version===selection.version)));
   const network=node('select');network.setAttribute('aria-label','Bitcoin 네트워크');for(const n of release.networks){const option=node('option',({main:'Mainnet',test:'Testnet3',testnet4:'Testnet4',signet:'Signet',regtest:'Regtest'})[n]||n);option.value=n;network.append(option);}if(!release.networks.includes(selection.network))selection.network='main';network.value=selection.network;network.onchange=()=>{selection.network=network.value;changed();choose();};
   const notes=node('a','공식 릴리스 안내');notes.href=release.release_notes;notes.target='_blank';notes.rel='noopener noreferrer';detail.append(notes);detail.append(node('h4',`선택한 버전: ${release.version}`),node('label','Bitcoin 네트워크'),network,node('p','버전별 데이터와 electrs 인덱스를 별도로 유지합니다. 새 버전·네트워크에서는 다시 동기화할 수 있습니다. 기존 데이터는 보존됩니다.','hint'));
   detail.append(toggle('RPC 지갑 연동용 watch-only 모드',selection.watch_only,on=>{selection.watch_only=on;changed();choose();}));
   if(!release.downloaded){detail.append(button('검증된 바이너리 다운로드',()=>operation(async()=>{await api('/versions',{method:'download',version:selection.version});message('다운로드·서명 검증 진행 중…');watchDownload();})));}
   else if(active&&selection.version===active.core_version&&selection.network===active.network&&selection.watch_only===!!active.watch_only)detail.append(node('p','현재 사용 중인 버전과 모드입니다.','hint'));else detail.append(button('이 버전으로 변경 내용 확인',()=>operation(async()=>{preview=await api('/versions',{method:'preview',...selection});review([`Bitcoin Core ${preview.preview.target.instance.core_version} · ${preview.preview.target.instance.network}`,preview.preview.explanation],['Core와 관련 서비스를 재시작합니다. 동기화와 electrs 준비 상태는 현황에서 별도로 확인합니다.']);}),'primary-action'));
  }
  function list(){cards.replaceChildren();const major=new Map();for(const r of state.releases)major.set(r.version.split('.')[0],r);const entries=all.checked?state.releases:[...major.values()];for(const r of [...entries].reverse()){const b=button('',()=>{selection={version:r.version,network:selection?.network||'main',watch_only:selection?.watch_only||false};choose();message(`Bitcoin Core ${r.version} 선택됨 · 아래에서 변경 내용을 확인하세요.`);},'version-card');b.dataset.version=r.version;b.append(node('strong','Bitcoin Core '+r.version),node('small',(active?.core_version===r.version?'현재 사용 · ':'')+(r.downloaded?'다운로드됨':'다운로드 필요')),node('small',r.support_status?.includes('EOL')?'공식 유지보수 지원 종료':'공식 안정 릴리스'));b.disabled=r.availability!=='OFFICIAL_BINARY_VERIFIED';cards.append(b);}choose();}all.onchange=list;list();
  if(['downloading','installing'].includes(state.download?.phase)){host.append(node('p','바이너리 다운로드·서명 검증 진행 중…','hint'));watchDownload();}
 }
 async function watchDownload(){const g=generation;poll=setTimeout(async()=>{try{const s=await api('/versions',{method:'state'});if(g!==generation)return;state=s;if(s.releases.some(r=>r.version===selection.version&&r.downloaded)){render();message('다운로드·검증 완료. 변경 내용을 확인하세요.');}else if(['failed','interrupted'].includes(s.download?.phase)){message('다운로드가 완료되지 않았습니다. 다시 다운로드를 선택하세요.');}else{message('다운로드·서명 검증 진행 중…');watchDownload();}}catch(e){if(g===generation)message(e.message);}},3000);}
 async function operation(fn){if(busy)return;busy=true;const g=generation;el('controls').inert=true;el('settings-content').inert=true;el('settings-review').inert=true;message('검증·서비스 응답을 기다리는 중…');try{await fn();}catch(e){if(g===generation)message(e.message);}finally{busy=false;el('controls').inert=false;el('settings-content').inert=false;el('settings-review').inert=false;}}
 function review(changes,warnings){const box=el('settings-review');box.replaceChildren(node('h3','적용 전 확인'));const list=node('ul');for(const line of [...changes,...warnings])list.append(node('li',line));box.append(list);box.append(button('저장하고 적용',()=>operation(async()=>{await api('/'+kind,{method:'apply',token:preview.token});await open(kind);message('설정 저장·서비스 재시작·상태 확인을 마쳤습니다.');})),button('취소',()=>{clearReview();message('적용하지 않았습니다.');},'subtle'));box.hidden=false;box.scrollIntoView({block:'nearest'});message('변경 내용을 확인하세요. 아직 저장되지 않았습니다.');}
 return {open,stop,api};
})();
