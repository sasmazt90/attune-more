/* Actual routing/playback modules with explicit media-event fault fixtures.
 * This is not physical audio, browser codec, or live provider evidence. */
require('./ts_loader.js');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
global.window=new EventTarget();global.document=new EventTarget();document.hidden=false;
global.CustomEvent=class extends Event{constructor(t,o){super(t);this.detail=o?.detail;}};
const storage=new Map([['health-records','unchanged Straße İı'],['consent','unchanged']]);
global.localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,String(v))};
global.requestAnimationFrame=()=>0;global.cancelAnimationFrame=()=>{};
const C=require('../../apps/vehicle-app/src/i18n/core.ts');
const A=require('../../apps/vehicle-app/src/i18n/approvedAudio.ts');
const {playFixedSpeech}=require('../../apps/vehicle-app/src/utils/fixedFileSpeech.ts');
const {verifiedClipBytes}=require('../../apps/vehicle-app/src/i18n/fixedAudio.ts');
let fault='',lastBlob,liveURLs=0;
global.URL.createObjectURL=b=>{lastBlob=b;liveURLs++;return 'blob:fixture'};
global.URL.revokeObjectURL=()=>liveURLs--;
global.fetch=async url=>{const b=fs.readFileSync(path.join('apps/vehicle-app/public',url));return {ok:fault!=='missing',arrayBuffer:async()=>fault==='hash'?new Uint8Array(b.length).buffer:fault==='size'?new ArrayBuffer(1):b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)}};
class AudioFixture extends EventTarget{
 constructor(){super();this.dataset={};this.duration=1;this.currentTime=0;this.ended=false;this.paused=true;}
 canPlayType(){return 'probably';}play(){this.paused=false;this.dispatchEvent(new Event('playing'));return Promise.resolve();}
 pause(){this.paused=true;}removeAttribute(){}load(){}
 complete(){this.ended=true;this.currentTime=1;this.dispatchEvent(new Event('ended'));}
}
const tick=()=>new Promise(r=>setTimeout(r,10));
(async()=>{
 const modules={skin:'Skin Health',mental:'Mental Health',vision:'Vision Health',dental:'Dental Health',hearing:'Hearing Health'};
 const profiles={tr:{skin:'emel',mental:'emel',vision:'ahmet',dental:'ahmet',hearing:'ahmet'},en:{skin:'ada',mental:'ada',vision:'andrew',dental:'andrew',hearing:'andrew'},de:{skin:'katja',mental:'katja',vision:'stefan',dental:'stefan',hearing:'stefan'}};
 for(const m of A.approvedAudio.activeGuidanceMappings){const module=Object.keys(modules).find(k=>modules[k]===m.module);const clip=A.approvedClip(m.language,module,m.eventId);assert.equal(clip.recordingId,m.recordingId);assert.equal(clip.voiceProfile,profiles[m.language][module]);assert.equal(clip.mimeType,'audio/mp4');}
 assert.equal(A.approvedAudio.activeGuidanceMappings.length,129);
 for(const language of C.LANGUAGES){
  C.setLanguage(language);assert.equal(storage.get('health-records'),'unchanged Straße İı');assert.equal(storage.get('consent'),'unchanged');
  for(const module of Object.keys(modules)){assert.equal(A.approvedClip(language,module,'guidance:cockpit-entry'),undefined);assert.equal(A.approvedClip(language,module,'hearing-digit:0'),undefined);assert.equal(A.approvedClip(language,module,'dynamic:mental'),undefined);}
  for(const event of ['quality-blur','quality-face','quality-far','quality-light','quality-near']){
   const skin=A.approvedClip(language,'skin','guidance:'+event),dental=A.approvedClip(language,'dental','guidance:'+event);assert.equal(skin.gender,'female');assert.equal(dental.gender,'male');assert.notEqual(skin.recordingId,dental.recordingId);
  }
  const mappings=A.approvedAudio.activeGuidanceMappings.filter(m=>m.language===language&&m.eventId.startsWith('mental-template:'));
  for(const m of mappings){const clip=A.approvedClip(language,'mental',m.eventId);assert.equal(A.approvedMentalTemplate(language,clip.exactScript).recordingId,clip.recordingId);assert.equal(A.approvedMentalTemplate(language,clip.exactScript+' altered'),undefined);}
  assert.equal(A.approvedMentalTemplate(language,'Arbitrary AI response, not a finite template'),undefined);
 }
 assert.equal(A.mentalVoiceContract('en').providerVoiceId,'en-GB-AdaMultilingualNeural');assert.equal(A.mentalVoiceContract('en').applicationLocale,'en-US');assert.equal(A.mentalVoiceContract('de').providerVoiceId,null);
 const clip=A.approvedClip('en','mental','guidance:mental-entry');
 for(const [f,error] of [['missing','UNAVAILABLE'],['size','SIZE'],['hash','HASH']]){fault=f;await assert.rejects(verifiedClipBytes(clip,new AbortController().signal),new RegExp(error));}fault='';
 let audio=new AudioFixture(),controller=new AbortController();let task=playFixedSpeech(audio,clip,controller.signal,()=>true);await tick();assert.equal(lastBlob.type,'audio/mp4');audio.complete();assert.equal(await task,true);assert.equal(liveURLs,0);
 for(const mode of ['abort','hidden','mute','early-end','generation']){
  let current=true;audio=new AudioFixture();controller=new AbortController();task=playFixedSpeech(audio,clip,controller.signal,()=>current);await tick();
  if(mode==='abort')controller.abort();if(mode==='hidden'){document.hidden=true;document.dispatchEvent(new Event('visibilitychange'));}if(mode==='mute'){window.attuneOutputMuted=true;window.dispatchEvent(new Event('attune-guidance-muted'));}if(mode==='early-end')audio.dispatchEvent(new Event('ended'));if(mode==='generation')current=false;
  assert.equal(await task,false,mode);assert.equal(audio.paused,true);assert.equal(liveURLs,0);document.hidden=false;window.attuneOutputMuted=false;
 }
 global.AudioContext=class extends EventTarget{constructor(){super();this.state='running';}close(){return Promise.resolve();}};
 const {HearingAudio}=require('../../apps/vehicle-app/src/utils/hearingAudio.ts');
 const nativeFetch=global.fetch;let bankFetches=0;global.fetch=(...args)=>{bankFetches++;return nativeFetch(...args);};
 for(const language of ['en','de']){C.setLanguage(language);const engine=new HearingAudio(()=>{});await assert.rejects(engine.loadBank(new AbortController().signal),/akustik/);assert.equal(bankFetches,0);engine.close();}
 console.log('PASS 129 mappings / 15 module-language assignments / shared voice separation / exact templates only / 3-locale storage preservation / MIME / missing-size-hash faults / actual-handler cancellation, mute, hidden, generation and completion fixtures');
})().catch(e=>{console.error(e);process.exitCode=1});
