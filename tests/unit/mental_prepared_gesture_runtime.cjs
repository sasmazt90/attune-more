/** Actual prepared -> verified fixed -> gesture lifecycle, explicit media fixtures. */
require('./ts_loader.js');const assert=require('assert/strict');
global.window=new EventTarget();global.document=new EventTarget();document.hidden=false;
global.localStorage={getItem:()=>null};global.cancelAnimationFrame=()=>{};
const manifest=require('../../apps/vehicle-app/public/audio/mental/v1/female-calm-v1-manifest.json');
manifest.joinApprovalStatus='approved';manifest.joinSilenceMs=1;
const clip=manifest.entries.find(e=>e.language==='tr'&&e.variantId==='A-V01');
Object.assign(clip,{approvalStatus:'approved',sha256:'a'.repeat(64),bytes:100,durationMs:200});
const fixed=require.resolve('../../apps/vehicle-app/src/i18n/fixedAudio.ts');let verified=0;
require.cache[fixed]={id:fixed,filename:fixed,loaded:true,exports:{verifiedClipBytes:async entry=>{verified++;assert.equal(entry.sha256,clip.sha256);return new ArrayBuffer(100);}}};
class MediaFixture extends EventTarget{
 constructor(){super();this.src='';this.paused=true;this.ended=false;this.duration=.2;this.currentTime=0;this.calls=0;}
 canPlayType(){return 'probably';}pause(){this.paused=true;}load(){}removeAttribute(){this.src='';}getAttribute(){return this.src;}
 play(){this.calls++;return Promise.reject(new DOMException('Explicit native policy fixture','NotAllowedError'));}
}
global.Audio=MediaFixture;
const {playPreparedMental}=require('../../apps/vehicle-app/src/utils/mentalPreparedSpeech.ts');
const settle=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
(async()=>{
 for(const mode of ['play','abort','consent','motion']){
  let live=true,audio,resume,requested=0,cleared=0;const stages=[],focus=[];
  const listener=e=>focus.push(e.active);window.addEventListener('attune-stream-focus',listener);
  const controller=new AbortController();
  const result=playPreparedMental(clip.exactScript,[clip.assetId],controller.signal,()=>live,a=>{audio=a;},stage=>stages.push(stage),play=>{requested++;resume=play;return()=>{cleared++;};});
  await settle();assert.equal(requested,1);assert.deepEqual(stages,['gesture-required']);assert.deepEqual(focus,[true]);
  if(mode==='play'){
   audio.play=()=>{audio.calls++;audio.paused=false;queueMicrotask(()=>audio.dispatchEvent(new Event('playing')));return Promise.resolve();};
   resume();assert.equal(audio.calls,2);await settle();
   audio.currentTime=audio.duration;audio.ended=true;audio.dispatchEvent(new Event('ended'));
   assert.equal(await result,true);assert.deepEqual(stages,['gesture-required','playing','ended']);
  }else{
   if(mode==='abort')controller.abort();else live=false;
   resume();assert.equal(await result,false);assert.equal(audio.calls,1);
  }
  assert.equal(cleared,1);assert.deepEqual(focus,[true,false]);assert(audio.paused);assert.equal(audio.src,'');
  window.removeEventListener('attune-stream-focus',listener);
 }
 assert.equal(verified,4);
 console.log('PASS prepared native gesture recovery and abort/consent/motion cancellation through actual fixed-audio lifecycle; explicit fixtures');
})().catch(e=>{console.error(e);process.exitCode=1;});
