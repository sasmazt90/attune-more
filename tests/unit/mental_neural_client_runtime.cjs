/** Execute actual dynamic transport/playback with explicit audio/HTTP fixtures. */
require('./ts_loader.js');const assert=require('assert/strict'),Module=require('module');
global.window=new EventTarget();global.document=new EventTarget();document.hidden=false;const store=new Map([['attune.language.v1','en']]);global.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v))};
let fetchCalls=0,playCalls=0,ready=0,focus=0,playing=0,capture=0,mode='success';
window.addEventListener('attune-stream-focus',e=>{focus+=e.active?1:-1;});
const original=Module._load;Module._load=function(request,parent,...args){
 if(request==='./fixedFileSpeech'&&parent.filename.endsWith('mentalNeuralSpeech.ts'))return {playAudioBytes:async(audio,bytes,mime,duration,signal,current,observe)=>{playCalls++;assert.equal(mime,'audio/wav');assert.equal(bytes.byteLength,100);if(!current()||signal.aborted)return false;observe('playing');return true;}};
 return original.call(this,request,parent,...args);
};global.Audio=class{};
const C=require('../../apps/vehicle-app/src/i18n/core.ts'),N=require('../../apps/vehicle-app/src/utils/mentalNeuralSpeech.ts');
const raw='A genuinely new nonpersonal response 1287 İı Straße.';
global.fetch=async(url,init)=>{fetchCalls++;assert.equal(url,'/api/mental-neural-speech');assert.deepEqual(JSON.parse(init.body),{text:raw,language:'en',speechConsent:true});assert(!('Authorization' in init.headers));if(mode==='locale')C.setLanguage('de');if(mode==='abort')window.dispatchEvent(new Event('attune-guidance-cancel'));return new Response(new Uint8Array(100),{status:mode==='unavailable'?503:200,headers:{'Content-Type':'audio/wav','X-TTS-Source':'chatterbox-multilingual-v3','X-TTS-Locale':mode==='wrongLocale'?'tr-TR':'en-US'}});};
(async()=>{
 assert.equal(N.mentalSpeechEngine(),'chatterbox-v3');
 for(const variant of ['success','locale','abort','unavailable','wrongLocale']){mode=variant;C.setLanguage('en');const before=playCalls;assert.equal(await N.mentalNeuralSpeech(raw,new AbortController().signal,()=>true,()=>playing++,()=>ready++),variant==='success');assert.equal(focus,0);assert.equal(playCalls-before,variant==='success'?1:0);}
 for(const guard of ['muted','hidden','focus','invalid','signal']){window.attuneOutputMuted=guard==='muted';document.hidden=guard==='hidden';store.set('attune_hearing_audio_focus',guard==='focus'?String(Date.now()+10000):'0');const c=new AbortController();if(guard==='signal')c.abort();const before=fetchCalls;assert.equal(await N.mentalNeuralSpeech(raw,c.signal,()=>guard!=='invalid',()=>{},()=>{}),false);assert.equal(fetchCalls,before);}
 window.attuneOutputMuted=false;document.hidden=false;store.delete('attune_hearing_audio_focus');N.setMentalSpeechEngine('browser-system');const before=fetchCalls;assert.equal(await N.mentalNeuralSpeech(raw,new AbortController().signal,()=>true,()=>{},()=>{}),false);assert.equal(fetchCalls,before);assert.equal(playing,1);assert.equal(ready,1);assert.equal(capture,0);console.log('PASS raw dynamic text transport, backend default/separate explicit fallback, language/source guards, cancellation/mute/background/Hearing focus and balanced audio ownership (HTTP/playback fixtures only)');
})().catch(e=>{console.error(e);process.exitCode=1});
