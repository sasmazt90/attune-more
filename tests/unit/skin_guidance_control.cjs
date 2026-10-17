// Actual hook scheduling with virtual timers/fake audio; no browser or speech.
require('./ts_loader.js');
const assert=require('assert/strict'),fs=require('fs'),Module=require('module');
const nativeLoad=Module._load,nativeTimeout=setTimeout,nativeClear=clearTimeout;
let now=0,next=1,plays=0,pauses=0;const timers=new Map(),cleanup=[],refs=[];
global.window=new EventTarget();global.location={pathname:'/skin'};
global.CustomEvent??=class extends Event{constructor(t,o){super(t);this.detail=o?.detail}};
global.localStorage={getItem:()=>null};
global.requestAnimationFrame=()=>0;global.cancelAnimationFrame=()=>{};
global.setTimeout=(fn,ms)=>{const id=next++;timers.set(id,{fn,at:now+ms});return id};global.clearTimeout=id=>timers.delete(id);
Module._load=function(name,parent,...rest){if(name==='react'&&parent.filename.endsWith('audioGuidance.ts'))return {useId:()=>':controlled',useRef:v=>{const r={current:v};refs.push(r);return r},useMemo:fn=>fn(),useEffect:fn=>cleanup.push(fn())};return nativeLoad.call(this,name,parent,...rest)};
let lastAudio;global.Audio=class extends EventTarget{constructor(){super();this.dataset={};lastAudio=this}async play(){plays++}pause(){pauses++}removeAttribute(){}load(){}};
global.URL.createObjectURL=()=> 'blob:controlled-no-media';global.URL.revokeObjectURL=()=>{};
global.fetch=async url=>{const b=fs.readFileSync('apps/vehicle-app/public'+url);return {ok:true,arrayBuffer:async()=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)}};
async function step(ms){now+=ms;for(const [id,t] of [...timers])if(t.at<=now){timers.delete(id);t.fn()}await new Promise(r=>nativeTimeout(r,25))}
(async()=>{
 const G=require('../../apps/vehicle-app/src/utils/audioGuidance.ts'),api=G.useGuidance('skin',true);
 try{
  api.issue('pose-front','skin-front');await step(899);assert.equal(plays,0);await step(1);assert.equal(plays,1);lastAudio.onended();
  for(let i=0;i<5;i++)api.issue('pose-front','skin-front');await step(5000);assert.equal(plays,1);
  api.issue('');await step(1200);api.issue('pose-front','skin-front');await step(900);assert.equal(plays,2);
  G.muteGuidance(true);assert(pauses>0);api.issue('pose-left','skin-left');await step(900);assert.equal(plays,2);
  G.muteGuidance(false);api.cancel();api.issue('pose-right','skin-right');api.cancel();await step(1000);assert.equal(plays,2);
  refs[0].current=false;api.issue('disabled','skin-front');await step(900);assert.equal(plays,2);api.cancel();refs[0].current=true;
  location.pathname='/privacy';api.issue('outside-health','skin-front');await step(900);assert.equal(plays,2);
  assert.equal(G.skinNeutralGuidance(),undefined); // Failed clip is not faked/admitted.
 }finally{api.cancel();for(const f of cleanup)if(typeof f==='function')f();Module._load=nativeLoad;global.setTimeout=nativeTimeout;global.clearTimeout=nativeClear}
 assert.equal(timers.size,0);console.log('PASS 900ms stability / once per issue / 1200ms recovery / mute / cancel / disabled / route boundary / no fake neutral clip');
})().catch(e=>{console.error(e);process.exitCode=1});
