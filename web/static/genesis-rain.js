'use strict';
// Mainnet genesis block: header plus the original coinbase transaction (285 bytes).
const GenesisRain=(()=>{
 const hex='0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c0101000000010000000000000000000000000000000000000000000000000000000000000000ffffffff4d04ffff001d0104455468652054696d65732030332f4a616e2f32303039204368616e63656c6c6f72206f6e206272696e6b206f66207365636f6e64206261696c6f757420666f722062616e6b73ffffffff0100f2052a01000000434104678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5fac00000000';
 const defaults=Object.freeze({enabled:false,brightness:40,speed:160,density:140});
 const ranges={brightness:[3,100],speed:[15,400],density:[30,300]};
 function normalize(value){
  if(!value||typeof value!=='object'||typeof value.enabled!=='boolean')return {...defaults};
  const result={enabled:value.enabled};
  for(const [key,[low,high]] of Object.entries(ranges)){
   if(!Number.isInteger(value[key])||value[key]<low||value[key]>high)return {...defaults};
   result[key]=value[key];
  }
  return result;
 }
 let settings={...defaults},canvas,ctx,width=0,height=0,streams=[],raf=0,last=0,accent='',head='',frozen=false;
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 function halt(){cancelAnimationFrame(raf);raf=0;last=0;}
 function palette(){const css=getComputedStyle(document.documentElement);accent=css.getPropertyValue('--accent').trim();head=css.getPropertyValue('--text').trim();}
 function resize(){
  if(!canvas)return;
  width=innerWidth;height=innerHeight;
  const scale=Math.min(devicePixelRatio||1,1.5,Math.sqrt(3000000/Math.max(1,width*height)));
  canvas.width=Math.max(1,Math.round(width*scale));canvas.height=Math.max(1,Math.round(height*scale));ctx.setTransform(scale,0,0,scale,0,0);
  const step=Math.max((width<550?24:26)/(settings.density/100),width/160);
  streams=[];
  for(let x=8;x<width;x+=step)streams.push({x:Math.round(x+Math.random()*5),y:Math.random()*(height+360)-180,length:8+Math.floor(Math.random()*20),speed:26+Math.random()*48,offset:Math.floor(Math.random()*hex.length)});
 }
 function draw(seconds){
  ctx.clearRect(0,0,width,height);ctx.font=`${width<550?12:14}px ui-monospace, SFMono-Regular, monospace`;ctx.textAlign='center';
  const opacity=settings.brightness/100;
  for(const stream of streams){
   stream.y+=seconds*stream.speed*settings.speed/100;
   if(stream.y-stream.length*18>height){stream.y=-18;stream.offset=(stream.offset+37)%hex.length;}
   for(let j=stream.length-1;j>=0;j--){
    const y=stream.y-j*18;if(y<0||y>height+18)continue;
    const index=((stream.offset+Math.floor(stream.y/18)-j)%hex.length+hex.length)%hex.length;
    ctx.globalAlpha=j===0?Math.min(.7,opacity*1.9):opacity*Math.pow(1-j/stream.length,1.6);ctx.fillStyle=j===0?head:accent;ctx.fillText(hex[index],stream.x,y);
   }
  }
  ctx.globalAlpha=1;
 }
 function animate(now){
  raf=0;if(!settings.enabled||document.hidden||frozen||reduced.matches)return;
  if(!last)last=now;const delta=now-last;
  if(delta>=1000/24){draw(Math.min(delta/1000,.1));last=now;}
  raf=requestAnimationFrame(animate);
 }
 function resume(){halt();if(!settings.enabled||!ctx||document.hidden||frozen)return;draw(0);if(!reduced.matches)raf=requestAnimationFrame(animate);}
 function apply(value){
  const next=normalize(value),wasEnabled=settings.enabled,densityChanged=settings.density!==next.density;settings=next;
  if(!settings.enabled){halt();if(canvas){canvas.hidden=true;canvas.width=canvas.height=1;streams=[];}document.body.removeAttribute('data-rain');return;}
  if(!canvas){canvas=document.createElement('canvas');canvas.id='genesis-rain';canvas.setAttribute('aria-hidden','true');document.body.prepend(canvas);ctx=canvas.getContext('2d');}
  if(!ctx)return;
  canvas.hidden=false;document.body.dataset.rain='on';palette();
  if(!wasEnabled||densityChanged||!streams.length)resize();
  resume();
 }
 addEventListener('resize',()=>{if(settings.enabled&&ctx){resize();resume();}},{passive:true});
 document.addEventListener('visibilitychange',resume);reduced.addEventListener('change',resume);
 document.addEventListener('freeze',()=>{frozen=true;halt();});document.addEventListener('resume',()=>{frozen=false;resume();});
 addEventListener('pagehide',halt);addEventListener('pageshow',resume);
 return {defaults,normalize,apply};
})();
