// Explicit Web Speech voice/event fixtures; never claimed as audible synthesis.
require('./ts_loader.js');const assert=require('assert/strict');
const store=new Map([['health','unchanged synthetic sentinel'],['consent','unchanged']]);global.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v))};global.window=new EventTarget();global.document=new EventTarget();document.hidden=false;global.SpeechSynthesisUtterance=class{constructor(text){this.text=text;}};global.fetch=()=>assert.fail('No external or consumer endpoint permitted');
const core=require('../../apps/vehicle-app/src/i18n/core.ts'),M=require('../../apps/vehicle-app/src/i18n/mentalVoices.ts'),S=require('../../apps/vehicle-app/src/i18n/systemSpeech.ts');
const voice=(voiceURI,lang,localService=false,name=voiceURI)=>({voiceURI,lang,localService,name});
let inventory=[],mode='complete',last,cancelCount=0;
global.speechSynthesis=new EventTarget();Object.assign(speechSynthesis,{getVoices:()=>inventory,cancel:()=>{cancelCount++},speak:u=>{last=u;if(mode!=='end-only')u.onstart?.();if(['complete','end-only'].includes(mode))setTimeout(()=>u.onend?.(),1);if(mode==='error')setTimeout(()=>u.onerror?.(),1);}});
(async()=>{
 for(const [language,id,locale] of [['tr','tr-TR-EmelNeural','tr-TR'],['en','en-GB-AdaMultilingualNeural','en-GB'],['de','de-DE-KatjaNeural','de-DE']]){
  core.setLanguage(language);inventory=[voice('unknown',locale,true,'Some female voice'),voice('male',locale,true,'Microsoft Stefan - German (Germany)'),voice(id,locale)];assert.equal(M.mentalSystemVoices(inventory,language).length,1);assert.equal(M.selectMentalSystemVoice(inventory,language,{}),undefined);
  M.setMentalVoicePreference(language,{onlineConsent:true});const text={tr:'Bu değişken yanıtın kimliği ',en:'This variable response has identifier ',de:'Diese variable Antwort hat die Kennung '}[language]+crypto.randomUUID();let starts=0;
  assert(await S.mentalSystemSpeech(text,new AbortController().signal,()=>true,()=>starts++));assert.equal(starts,1);assert.equal(last.text,text);assert.equal(last.lang,locale);assert.equal(last.voice.voiceURI,id);assert.equal(store.get('health'),'unchanged synthetic sentinel');assert.equal(store.get('consent'),'unchanged');
  assert.equal(M.selectMentalSystemVoice(inventory,language,{voiceId:'gone',onlineConsent:true}),undefined);
 }
 // Actual browser aliases require exact manufacturer identity + matching locale.
 assert(M.mentalVoiceIdentity(voice('runtime-uri','de-DE',true,'Microsoft Hedda - German (Germany)')));
 assert(!M.mentalVoiceIdentity(voice('runtime-uri','en-US',true,'Microsoft Hedda - German (Germany)')));
 assert.equal(M.selectMentalSystemVoice([voice('zira','en-US',true,'Microsoft Zira - English (United States)'),voice('en-US-AriaNeural','en-US')],'en',{onlineConsent:true}).voiceURI,'en-US-AriaNeural');
 assert(!M.mentalVoiceIdentity(voice('unknown','de-DE',true,'My Katja clone')));
 core.setLanguage('de');inventory=[voice('de-DE-KatjaNeural','de-DE')];M.setMentalVoicePreference('de',{onlineConsent:true});
 for(const fault of ['abort','mute','hidden','locale','hearing','motion-or-consent','online-revoked','error','end-only']){
  M.setMentalVoicePreference('de',{onlineConsent:true});mode=['error','end-only'].includes(fault)?fault:'wait';const controller=new AbortController();let current=true;const task=S.mentalSystemSpeech('Nicht vorgegebener synthetischer Text '+crypto.randomUUID(),controller.signal,()=>current);await new Promise(r=>setTimeout(r,2));
  if(fault==='abort')controller.abort();if(fault==='mute'){window.attuneOutputMuted=true;window.dispatchEvent(new Event('attune-guidance-muted'));}if(fault==='hidden'){document.hidden=true;document.dispatchEvent(new Event('visibilitychange'));}if(fault==='locale')core.setLanguage('en');if(fault==='hearing'){store.set('attune_hearing_audio_focus',String(Date.now()+5000));window.dispatchEvent(new Event('attune-audio-focus'));}if(fault==='motion-or-consent')current=false;if(fault==='online-revoked')store.set(M.MENTAL_VOICE_KEY,JSON.stringify({de:{onlineConsent:false}}));
  assert.equal(await task,false,fault);window.attuneOutputMuted=false;document.hidden=false;store.delete('attune_hearing_audio_focus');core.setLanguage('de');
 }
 M.setMentalVoicePreference('de',{onlineConsent:true});mode='complete';inventory=[];const pending=S.mentalSystemSpeech('Late voice discovery',new AbortController().signal,()=>true);setTimeout(()=>{inventory=[voice('de-DE-KatjaNeural','de-DE')];speechSynthesis.dispatchEvent(new Event('voiceschanged'));},2);assert(await pending);
 inventory=[];const controller=new AbortController();const pendingEmpty=S.mentalSystemSpeech('No voice',controller.signal,()=>true);controller.abort();assert.equal(await pendingEmpty,false);assert(cancelCount>0);
 console.log('PASS dynamic arbitrary text unchanged / 3 languages and documented female identities / no unregistered or other-language fallback / online opt-in / late discovery / start+end required / mute, abort, hidden, locale, hearing focus, permission+motion invalidation (fixtures only; no live TTS PASS)');
})().catch(e=>{console.error(e);process.exitCode=1});
