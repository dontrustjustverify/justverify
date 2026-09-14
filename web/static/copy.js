'use strict';
// Clipboard writes only happen after an explicit click. HTTP LAN browsers also
// get a selected-text fallback when the secure Clipboard API is unavailable.
const CopyAddress=(()=>{
 function wrap(input){
  const box=document.createElement('div');box.className='address-field';
  const button=document.createElement('button');button.type='button';button.className='copy-button';button.title='주소 복사';button.setAttribute('aria-label','주소 복사');
  button.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="7" width="12" height="14" rx="2"/><path d="M9 3h10a2 2 0 0 1 2 2v12"/></svg>';
  const message=document.createElement('span');message.className='copy-feedback';message.setAttribute('role','status');
  let reset;
  button.onclick=async()=>{
   clearTimeout(reset);let copied=false;const value=input.value;
   if(!value)return;
   if(window.isSecureContext&&navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(value);copied=true;}catch{}}
   if(!copied){
    const field=document.createElement('textarea');field.value=value;field.readOnly=true;field.style.cssText='position:fixed;left:-9999px;top:0';document.body.append(field);
    const focused=document.activeElement;field.focus();field.select();field.setSelectionRange(0,value.length);
    try{copied=document.execCommand('copy');}catch{}finally{field.remove();focused?.focus({preventScroll:true});}
   }
   message.textContent=copied?'복사됨':'자동 복사가 지원되지 않습니다. 선택된 주소를 복사하세요.';
   if(!copied){input.focus();input.select();input.setSelectionRange(0,value.length);}
   box.classList.toggle('copied',copied);reset=setTimeout(()=>{message.textContent='';box.classList.remove('copied');},copied?2500:8000);
  };
  box.append(input,button,message);return box;
 }
 function enhance(input){if(input&&!input.closest('.address-field')){const marker=document.createTextNode('');input.before(marker);marker.replaceWith(wrap(input));}}
 return {wrap,enhance};
})();
