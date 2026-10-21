/** Actual WAV lifecycle, explicit media/time fixtures; no browser/inference claim. */
require('./ts_loader.js');
const assert=require('node:assert/strict');
global.window=new EventTarget();global.document=new EventTarget();document.hidden=false;
global.localStorage={getItem:()=>null};global.cancelAnimationFrame=()=>{};
const timers=[];
global.setInterval=callback=>{const row={callback,active:true};timers.push(row);return row;};
global.setTimeout=(callback,ms)=>{const row={callback,ms,active:true};timers.push(row);return row;};
global.clearTimeout=global.clearInterval=row=>{if(row)row.active=false;};
const {playAudioBytes}=require('../../apps/vehicle-app/src/utils/fixedFileSpeech.ts');
class AudioFixture extends EventTarget {
 constructor(){super();this.src='';this.paused=true;this.ended=false;this.duration=4;this.currentTime=0;this.calls=0;}
 canPlayType(){return 'probably';}pause(){this.paused=true;}load(){}removeAttribute(){this.src='';}getAttribute(){return this.src;}
 play(){this.calls++;return Promise.reject(new DOMException('Explicit media-policy fixture','NotAllowedError'));}
}
const settle=async()=>{await Promise.resolve();await Promise.resolve();};
(async()=>{
 for(const mode of ['play','abort','mute','hidden','consent','motion','language','session','timeout','decode','no-ui']){
  let live=true,resume,cleared=0,requested=0,settled=false;
  window.attuneOutputMuted=false;document.hidden=false;
  const audio=new AudioFixture(),controller=new AbortController(),stages=[];
  if(mode==='decode')audio.play=()=>Promise.reject(new DOMException('Fixture','NotSupportedError'));
  const result=playAudioBytes(audio,new ArrayBuffer(100),'audio/wav',60,controller.signal,()=>live,stage=>stages.push(stage),false,
   mode==='no-ui'?undefined:play=>{requested++;resume=play;return()=>{cleared++;};}).then(value=>{settled=true;return value;});
  await settle();
  if(['decode','no-ui'].includes(mode)){assert.equal(await result,false);assert.equal(requested,0);assert(stages.includes(mode==='decode'?'play-rejected':'gesture-required'));continue;}
  assert.equal(settled,false);assert.equal(requested,1);assert.deepEqual(stages,['gesture-required']);
  if(mode==='play'){
   // The callback must reach native play synchronously inside the real UI action.
   audio.play=()=>{audio.calls++;audio.paused=false;queueMicrotask(()=>audio.dispatchEvent(new Event('playing')));return Promise.resolve();};
   resume();assert.equal(audio.calls,2);await settle();assert.equal(cleared,1);
   audio.currentTime=audio.duration;audio.ended=true;audio.dispatchEvent(new Event('ended'));
   assert.equal(await result,true);assert.deepEqual(stages,['gesture-required','playing','ended']);
  }else{
   if(mode==='abort')controller.abort();
   if(mode==='mute'){window.attuneOutputMuted=true;window.dispatchEvent(new Event('attune-guidance-muted'));}
   if(mode==='hidden'){document.hidden=true;document.dispatchEvent(new Event('visibilitychange'));}
   if(['consent','motion','language','session'].includes(mode))live=false;
   if(mode==='timeout')timers.findLast(t=>t.active&&t.ms===68000).callback();
   // Even a UI callback retained after cancellation cannot start stale output.
   resume();assert.equal(await result,false);assert.equal(audio.calls,1);assert.equal(cleared,1);
  }
  assert(audio.paused);assert.equal(audio.src,'');assert(!timers.some(t=>t.active));
 }
 console.log('PASS 11 gesture/retry, decoding, finite-wait and live cancellation/safety cases (explicit fixtures)');
})().catch(error=>{console.error(error);process.exitCode=1;});
