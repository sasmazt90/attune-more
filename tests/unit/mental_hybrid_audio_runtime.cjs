/** Real prebuffer lifecycle with simulated media readiness; no physical playback measurement. */
require('./ts_loader.js');const assert=require('assert/strict');
global.window=new EventTarget();global.document=new EventTarget();document.hidden=false;global.localStorage={getItem:()=>null};
let audios=[],plays=0,revoked=0;global.URL={createObjectURL:()=> 'blob:test',revokeObjectURL:()=>revoked++};
class Audio extends EventTarget{duration=2;readyState=0;currentTime=0;ended=false;constructor(){super();audios.push(this);}canPlayType(){return 'probably';}load(){}pause(){}removeAttribute(){this.src='';}play(){plays++;this.dispatchEvent(new Event('playing'));this.ended=true;this.currentTime=this.duration;queueMicrotask(()=>this.dispatchEvent(new Event('ended')));return Promise.resolve();}}
global.Audio=Audio;
const meter=require.resolve('../../apps/vehicle-app/src/utils/playbackMeter.ts');require.cache[meter]={id:meter,filename:meter,loaded:true,exports:{speechMuted:()=>false,observeAppPlayback:()=>()=>{}}};
const {prepareAudioBytes}=require('../../apps/vehicle-app/src/utils/fixedFileSpeech.ts');
(async()=>{
 const c=new AbortController();let ready=false;const p=prepareAudioBytes(new ArrayBuffer(100),'audio/wav',2,c.signal,()=>true).then(x=>{ready=true;return x;});await Promise.resolve();assert(!ready);assert.equal(plays,0);
 audios[0].dispatchEvent(new Event('loadedmetadata'));await Promise.resolve();assert(!ready,'headers/metadata/URL are insufficient');
 audios[0].readyState=4;audios[0].dispatchEvent(new Event('canplaythrough'));const playable=await p;assert(playable);assert.equal(plays,0);assert(await playable.play(()=>{}));assert.equal(plays,1);assert.equal(await playable.play(()=>{}),false);
 const c2=new AbortController();const p2=prepareAudioBytes(new ArrayBuffer(100),'audio/wav',2,c2.signal,()=>true);c2.abort();assert.equal(await p2,null);audios[1].readyState=4;audios[1].dispatchEvent(new Event('canplaythrough'));assert.equal(plays,1);
 const c3=new AbortController();const p3=prepareAudioBytes(new ArrayBuffer(100),'audio/wav',2,c3.signal,()=>true);audios[2].readyState=4;audios[2].duration=NaN;audios[2].dispatchEvent(new Event('canplaythrough'));assert.equal(await p3,null);assert(revoked>=3);
 console.log('PASS 3 media readiness scenarios: whole playable data required, cancellation releases URLs/no late play, corrupt duration rejected');
})().catch(e=>{console.error(e);process.exitCode=1;});
