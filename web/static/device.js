'use strict';
const DeviceView=(()=>{
 let prefs={theme:'teal',language:'auto',name:'justverify'},data,timer,busy=false;
 const root=()=>document.querySelector('#device-view');
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const api=async body=>{const response=await fetch('/device-settings',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)});if(!response.ok){if(response.status===401){const session=await fetch('/session');if(!session.ok)await showAuth();}throw Error(await response.text());}return response.json();};
 const button=(label,fn,cls='subtle')=>{const b=el('button',label,cls);b.type='button';b.onclick=fn;return b;};
 const colors={teal:'#50D4C7',amber:'#FFB000',green:'#00FF00',ice:'#F0FFF8'};
 const names={teal:'Teal',amber:'Amber',green:'Green',ice:'Ice'};
 function applyTerminalTheme(){try{if(typeof term!=='undefined'&&term){const css=getComputedStyle(document.documentElement),c=colors[prefs.theme],text=css.getPropertyValue('--text').trim(),muted=css.getPropertyValue('--muted').trim();term.options.theme={background:'#080d10',foreground:text,cyan:c,brightCyan:c,green:c,brightGreen:c,white:text,brightWhite:text,brightBlack:muted};}}catch{}}
 function apply(value){prefs=value;document.documentElement.dataset.theme=prefs.theme;I18n.set(prefs.language);const link=document.querySelector('#mempool-link');if(link){const url=new URL(link.href);const language=I18n.resolve(prefs.language);url.pathname='/'+(language==='en'?'en-US':language)+'/';link.href=url.href;}applyTerminalTheme();try{localStorage.setItem('jv-appearance',JSON.stringify({theme:prefs.theme,language:prefs.language}));}catch{}}
 try{const p=JSON.parse(localStorage.getItem('jv-appearance'));if(p&&colors[p.theme]&&['auto','ko','en','ja'].includes(p.language))prefs={...prefs,...p};}catch{}
 apply(prefs);
 addEventListener('languagechange',()=>{if(prefs.language==='auto')apply(prefs);});
 async function loadPreferences(){try{data=await api({action:'state'});apply(data.preferences);}catch{}}
 function stop(){clearInterval(timer);timer=null;}
 function message(text){const n=document.querySelector('#device-message');if(n)n.textContent=text;}
 async function run(fn){if(busy)return;busy=true;root().inert=true;try{await fn();}catch(e){message(e.message);}finally{busy=false;root().inert=false;}}
 async function open(){stop();root().replaceChildren(el('p','JUSTVERIFY','eyebrow'),el('h2','설정'),el('p','연결 중','hint'));try{data=await api({action:'state'});apply(data.preferences);render();timer=setInterval(refresh,10000);}catch(e){root().replaceChildren(el('p',e.message,'notice'));}}
 async function refresh(){if(busy)return;try{const d=await api({action:'state'});data.device=d.device;facts();}catch{message('기기 상태를 갱신하지 못했습니다.');}}
 function facts(){const target=document.querySelector('#device-facts');if(!target)return;target.replaceChildren();const d=data.device;const up=d.uptime_seconds;const duration=up===undefined?'—':`${Math.floor(up/86400)}d ${Math.floor(up%86400/3600)}h ${Math.floor(up%3600/60)}m`;
  for(const [label,value] of [['디바이스',d.model||'확인 불가'],['JustVerify OS',d.os_version||'버전 정보 없음'],['로컬 IP',d.local_ip?.join(' · ')||'—'],['Uptime',duration]]){const dd=el('dd');if(label==='로컬 IP'&&d.local_ip?.length){for(const ip of d.local_ip){const input=el('input');input.readOnly=true;input.value=ip;input.setAttribute('aria-label','로컬 IP');dd.append(CopyAddress.wrap(input));}}else dd.textContent=value;target.append(el('dt',label),dd);}}
 function row(title,description,controls){const r=el('div',undefined,'device-row');const label=el('div');label.append(el('h3',title));if(description)label.append(el('p',description,'hint'));const c=el('div',undefined,'device-options');c.append(...controls);r.append(label,c);return r;}
 function render(){const r=root();r.replaceChildren(el('p','JUSTVERIFY','eyebrow'),el('h2','설정'));const msg=el('p','','hint');msg.id='device-message';msg.role='status';msg.setAttribute('aria-live','polite');r.append(msg);
  const device=el('section',undefined,'device-summary panel');const info=el('div');info.append(el('h3',prefs.name+' · JustVerify'));const dl=el('dl');dl.id='device-facts';info.append(dl);const power=el('div',undefined,'device-power');power.append(button('재시작',()=>reviewPower('reboot')),button('시스템 종료',()=>reviewPower('shutdown'),'subtle danger'));device.append(info,power);r.append(device);facts();
  const settings=el('section',undefined,'device-list panel');settings.append(row('계정명, 패스워드 변경',prefs.name,[button('계정명 변경',()=>account('name')),button('패스워드 변경',()=>account('password'))]));
  const swatches=el('div',undefined,'swatches');for(const [key,color] of Object.entries(colors)){const b=button(names[key],()=>run(async()=>{const result=await api({action:'preferences',theme:key,language:prefs.language});apply(result.preferences);render();message('저장되었습니다.');}),'swatch');b.dataset.color=key;b.style.setProperty('--swatch',color);b.setAttribute('aria-pressed',String(prefs.theme===key));b.title=color;swatches.append(b);}
  settings.append(row('글자색 선택','글자, 테두리와 버튼에 함께 적용됩니다.',[swatches]));
  const select=el('select');select.id='language-choice';select.setAttribute('aria-labelledby','language-settings-label');for(const [value,label] of [['auto','자동 (브라우저 언어)'],['ko','한국어'],['en','English'],['ja','日本語']]){const o=el('option',label);o.value=value;select.append(o);}select.value=prefs.language;
  select.onchange=()=>run(async()=>{const result=await api({action:'preferences',theme:prefs.theme,language:select.value});apply(result.preferences);render();message('저장되었습니다.');});const languageRow=row('Language/언어설정/言語設定','',[select]);const languageLabel=languageRow.querySelector('h3');languageLabel.id='language-settings-label';languageLabel.setAttribute('translate','no');settings.append(languageRow);
  const remote=data.remote_web;const toggle=button(remote.running?'켜짐':'꺼짐',()=>reviewTor(!remote.running),'toggle');toggle.id='remote-web-toggle';toggle.setAttribute('role','switch');toggle.setAttribute('aria-checked',String(remote.running));settings.append(row('Remote Tor access','Tor Browser로 외부에서 관리 화면에 접속합니다.',[toggle]));
  if(remote.running&&remote.url){const link=el('input');link.readOnly=true;link.value=remote.url;link.setAttribute('aria-label','Tor 관리 화면 주소');const help=el('p','Tor Browser에서 이 주소를 열고 관리자 암호로 로그인하세요.','hint');settings.append(CopyAddress.wrap(link),help);}
  if(remote.needs_recovery)settings.append(el('p','Tor 설정이 저장값과 다릅니다. 토글을 다시 적용하세요.','notice'));
  r.append(settings);const maintenance=el('section',undefined,'device-list panel');
  maintenance.append(row('백업 및 복원','설정과 연결 정보를 암호화하여 보관합니다.',[button('열기 →',()=>showPage(9))]),row('문제 해결','노드 연결 상태와 고급 저장장치 관리를 확인합니다.',[button('열기 →',()=>showPage(11))]));r.append(maintenance);
  const modal=el('dialog');modal.id='device-dialog';r.append(modal);
 }
 function troubleshoot(){stop();const r=root();r.replaceChildren(button('← 설정',()=>showPage(6)),el('h2','문제 해결'));
  const items=el('section',undefined,'device-list panel');items.append(row('Core RPC 상태','내 Core의 RPC 응답과 마지막 수집 오류를 확인합니다.',[button('확인 →',()=>showPage(10))]));
  const advanced=el('details',undefined,'advanced-storage');advanced.append(el('summary','고급 · 저장장치 관리'),el('p','NVMe는 첫 부팅 때 자동으로 준비됩니다. 설치 중단 복구나 별도 데이터 디스크를 관리할 때만 사용하세요.','hint'),button('저장장치 관리 열기',()=>showPage(8)));items.append(advanced);r.append(items);
 }
 function dialog(title){const d=document.querySelector('#device-dialog');d.replaceChildren(el('h2',title));const form=el('form');const note=el('p','','hint');note.role='status';form.append(note);d.append(form);const cancel=button('취소',()=>d.close());d.showModal();return {d,form,note,cancel};}
 function field(form,label,id,type='text',value=''){const l=el('label',label);l.htmlFor=id;const input=el('input');input.id=id;input.type=type;input.required=true;input.value=value;if(type==='password'){input.minLength=12;input.maxLength=256;input.autocomplete=id==='current-password'?'current-password':'new-password';}else{input.maxLength=40;input.autocomplete='nickname';}form.append(l,input);return input;}
 function account(kind){const {d,form,note,cancel}=dialog(kind==='name'?'계정명 변경':'패스워드 변경');let name,current,password,confirm;
  if(kind==='name')name=field(form,'새 계정명','account-name','text',prefs.name);
  else{form.append(el('p','웹 관리자 암호를 변경합니다. SSH 암호는 별개입니다. 변경 후 모든 브라우저에서 다시 로그인합니다.','hint'));current=field(form,'현재 암호','current-password','password');password=field(form,'새 암호 (12자 이상)','new-password','password');confirm=field(form,'새 암호 확인','confirm-password','password');}
  const save=el('button','저장');save.type='submit';const actions=el('div',undefined,'dialog-actions');actions.append(cancel,save);form.append(actions);
  form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{const body=kind==='name'?{action:'name',name:name.value.trim()}:{action:'password',current_password:current.value,password:password.value,password_confirm:confirm.value};const result=await api(body);if(result.reauthenticate){csrf=null;ws?.close();d.close();await showAuth();status.textContent=I18n.text('암호가 변경되었습니다. 새 암호로 로그인하세요.');}else{apply(result.preferences);render();message('저장되었습니다.');}}catch(e){note.textContent=e.message;}finally{save.disabled=false;}};
 }
 async function reviewPower(operation){await run(async()=>{const plan=await api({action:'power_preview',operation});confirmChange(plan,operation==='reboot'?'기기를 재시작할까요?':'기기를 종료할까요?',operation==='reboot'?'Core와 electrs를 안전하게 종료한 뒤 재부팅합니다. 잠시 후 다시 접속하세요.':'Core와 electrs를 안전하게 종료합니다. 다시 켜려면 기기의 전원을 조작해야 합니다.');});}
 async function reviewTor(enabled){await run(async()=>{const plan=await api({action:'tor_preview',enabled});confirmChange(plan,enabled?'Tor 원격 접속 켜기':'Tor 원격 접속 끄기',enabled?'관리자 암호를 아는 사용자가 Tor Browser로 접속할 수 있습니다.':'Tor 브라우저 연결이 종료됩니다. 로컬 네트워크에서 계속 접속할 수 있습니다.');});}
 function confirmChange(plan,title,description){const {d,form,note,cancel}=dialog(title);form.append(el('p',description,'hint'));const pass=field(form,'현재 암호','current-password','password');const save=el('button','적용');save.type='submit';const actions=el('div',undefined,'dialog-actions');actions.append(cancel,save);form.append(actions);
  form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{const result=await api({action:'apply',token:plan.token,password:pass.value});pass.value='';d.close();if(result.queued){stop();message(result.queued==='reboot'?'재시작 중입니다. 잠시 후 새로고침하세요.':'시스템 종료 중입니다. 기기가 완전히 꺼진 뒤 전원을 분리하세요.');}else{data.remote_web=result;render();message('저장되었습니다.');}}catch(e){note.textContent=e.message;save.disabled=false;}};
 }
 return {open,stop,loadPreferences,applyTerminalTheme,troubleshoot};
})();
