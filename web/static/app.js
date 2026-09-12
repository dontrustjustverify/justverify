'use strict';
const $=s=>document.querySelector(s),status=$('#status');let ws,term,csrf,setupRequired=false,requiresCode=false;
function size(){if(!term||$('#terminal').hidden)return;const cols=Math.max(30,Math.min(120,Math.floor(($('#terminal').clientWidth)/9)));const rows=innerWidth<700?24:40;term.resize(cols,rows);if(ws?.readyState===1)ws.send(JSON.stringify({cols,rows}));}
async function showAuth(){
  NodeView.stop();SettingsView.stop();DeviceView.stop();$('#maintenance-heading').hidden=true;$('#logout').hidden=true;$('#device-view').hidden=true;$('#overview').hidden=true;$('#electrum-view').hidden=true;$('#terminal').hidden=true;$('#settings-view').hidden=true;$('#welcome').hidden=false;$('#controls').hidden=true;
  try {const r=await fetch('/auth-status');if(!r.ok)throw Error('기기에 연결하지 못했습니다. 새로고침해 주세요.');const data=await r.json();setupRequired=data.setup_required;requiresCode=data.requires_code;
  $('#step').textContent=setupRequired?'처음 시작하기':'다시 오셨군요';$('#title').textContent=setupRequired?'관리자 암호를 정해 주세요':'노드에 로그인';$('#description').textContent=setupRequired?'앞으로 이 노드에 접속할 때 사용할 암호입니다.':'최초 설정 때 만든 관리자 암호를 입력하세요.';
  $('#password-label').textContent=setupRequired?'새 관리자 암호':'관리자 암호';$('#password').autocomplete=setupRequired?'new-password':'current-password';$('#confirm-row').hidden=!setupRequired;$('#confirm').required=setupRequired;$('#code-row').hidden=!(setupRequired&&requiresCode);$('#setup').required=setupRequired&&requiresCode;$('#submit').textContent=setupRequired?'시작하기':'로그인';$('#login').hidden=false;
  } catch(e){status.textContent=e.message;}
}
function terminal(){ $('#logout').hidden=false;DeviceView.loadPreferences();$('#welcome').hidden=true;$('#controls').hidden=false;showPage(1);startNode(); }
async function startNode(){ $('#startup-state').textContent='노드 시작 상태 확인 중…';$('#node-retry').hidden=true;try{const r=await SettingsView.api('/node-start',{});$('#startup-state').textContent=r.started?'노드를 시작했습니다. 네트워크 연결과 블록 동기화가 진행됩니다.':'';}catch(e){$('#startup-state').textContent=e.message;$('#node-retry').hidden=false;} }
$('#node-retry').onclick=startNode;
async function resume(){try{const r=await fetch('/session');if(!r.ok){await showAuth();return;}csrf=(await r.json()).csrf;terminal();}catch(e){status.textContent='기기에 연결할 수 없습니다.';await showAuth();}}
function ensureTerminal(key){
 if(term){size();if(ws?.readyState===1)ws.send(JSON.stringify({input:key}));term.focus();return;}
 term=new Terminal({cols:120,rows:40,fontSize:14,lineHeight:1.15,fontFamily:'Menlo, Consolas, monospace',theme:{background:'#080d10',foreground:'#dbe9e8'},allowProposedApi:false});term.open($('#terminal'));DeviceView.applyTerminalTheme();
 ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/terminal`);ws.binaryType='arraybuffer';ws.onopen=()=>{size();ws.send(JSON.stringify({input:key}));term.focus();};ws.onmessage=e=>term.write(new Uint8Array(e.data));ws.onclose=()=>{term?.dispose();term=null;if(csrf)resume();};term.onData(input=>{if(ws.readyState===1)ws.send(JSON.stringify({input}));});
}
function showPage(n){
 NodeView.stop();SettingsView.stop();DeviceView.stop();$('#device-view').hidden=![6,11].includes(n);$('#overview').hidden=n!==1;$('#electrum-view').hidden=n!==7;$('#terminal').hidden=[1,2,3,6,7,11].includes(n);$('#settings-view').hidden=![2,3].includes(n);document.querySelectorAll('[data-submenu] [data-fkey]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.fkey)===n)));
 $('#maintenance-heading').hidden=![8,9,10].includes(n);
 if([8,9,10].includes(n)){
  $('#maintenance-title').textContent={8:'저장장치 관리',9:'백업 및 복원',10:'Core RPC 상태'}[n];
  $('#maintenance-help').textContent={8:'고급 관리 화면입니다. 정상 작동하는 NVMe는 다시 초기화할 필요가 없습니다.',9:'설정과 연결 정보를 암호화하여 백업하거나 복원합니다. 블록체인 전체와 지갑 개인키는 포함하지 않습니다.',10:'내 Core의 RPC 응답과 마지막 수집 오류를 확인합니다.'}[n];
  $('#maintenance-back').textContent=n===9?'← 설정':'← 문제 해결';$('#maintenance-back').onclick=()=>showPage(n===9?6:11);
 }
 if(n===1)NodeView.start();else if(n===7)NodeView.connection('lan');else if(n===6)DeviceView.open();else if(n===11)DeviceView.troubleshoot();else if(n===2||n===3)SettingsView.open(n===2?'versions':'policy');else ensureTerminal(functionKeys[n]);
}
$('#login').onsubmit=async e=>{
 e.preventDefault();status.textContent='';const password=$('#password').value;
 if(setupRequired&&password!==$('#confirm').value){status.textContent='두 암호가 일치하지 않습니다. 다시 확인해 주세요.';$('#confirm').focus();return;}
 $('#submit').disabled=true;
 try {const body={password};if(setupRequired){body.password_confirm=$('#confirm').value;if(requiresCode)body.setup_token=$('#setup').value;}
 const r=await fetch(setupRequired?'/setup':'/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!r.ok){if(r.status===429)throw Error(`시도가 많아 잠시 제한됐습니다. ${r.headers.get('Retry-After')||300}초 후 다시 시도하세요.`);const message=await r.text();throw Error(message||'로그인하지 못했습니다. 입력을 확인해 주세요.');}
 csrf=(await r.json()).csrf;$('#password').value='';$('#confirm').value='';$('#setup').value='';terminal();
 }catch(e){status.textContent=e.message;}finally{$('#submit').disabled=false;}
};
const functionKeys=['','\x1bOP','\x1bOQ','\x1bOR','\x1bOS','\x1b[15~','\x1b[17~','\x1b[18~','\x1b[19~','\x1b[20~','\x1b[21~'];
document.querySelectorAll('[data-fkey]').forEach(b=>b.onclick=()=>{
 if(b.dataset.group){document.querySelectorAll('[data-submenu]').forEach(n=>n.hidden=n.dataset.submenu!==b.dataset.group);document.querySelectorAll('[data-group]').forEach(n=>n.setAttribute('aria-pressed',String(n===b)));}
 showPage(Number(b.dataset.fkey));
});
document.querySelectorAll('[data-network]').forEach(b=>b.onclick=()=>NodeView.connection(b.dataset.network));
$('#logout').onclick=async()=>{await fetch('/logout',{method:'POST',headers:{'X-CSRF-Token':csrf}});NodeView.stop();SettingsView.stop();ws?.close();csrf=null;showAuth();};addEventListener('resize',size);resume();

// The explorer is a separate LAN service, including when opened by IP.
{const url=new URL(location.href);url.protocol='http:';url.port='3006';url.pathname='/';url.search='';url.hash='';if(url.hostname.endsWith('.onion'))url.hostname='justverify.local';$('#mempool-link').href=url.href;}
