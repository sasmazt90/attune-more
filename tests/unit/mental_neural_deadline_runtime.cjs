/** Actual proxy/client control flow, virtual deadlines, explicitly synthetic audio. */
const {NextRequest}=require('next/server');
require('./ts_loader.js');
const assert=require('node:assert/strict'),Module=require('node:module');
const limits=require('../../shared/localization/neural-tts-limits.json');
global.window=new EventTarget();global.document=new EventTarget();document.hidden=false;
const store=new Map([['attune.language.v1','en']]);
global.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v))};
global.Audio=class{};
const timers=new Set();
global.setTimeout=(callback,ms)=>{const row={callback,ms,active:true};timers.add(row);return row;};
global.clearTimeout=row=>{if(row)row.active=false;};
global.setInterval=callback=>({callback});global.clearInterval=()=>{};
let mode='success',checks=0;
const original=Module._load;
Module._load=function(request,parent,...args){
 if(request==='./fixedFileSpeech'&&parent.filename.endsWith('mentalNeuralSpeech.ts'))return {playAudioBytes:async(audio,bytes,mime,duration,signal,current)=>{
  checks++;assert.equal(duration,60);assert.equal(signal.aborted,false);
  assert(![...timers].some(t=>t.active&&t.ms===limits.generationMilliseconds),'generation timer must end before playback');
  if(mode==='mute'){window.attuneOutputMuted=true;window.dispatchEvent(new Event('attune-guidance-muted'));}
  if(mode==='cancel')window.dispatchEvent(new Event('attune-guidance-cancel'));
  if(mode==='language')window.dispatchEvent(new Event('attune-locale-media-cancel'));
  return current()&&!signal.aborted;
 }};
 return original.call(this,request,parent,...args);
};
const client=require('../../apps/vehicle-app/src/utils/mentalNeuralSpeech.ts');
const audio=()=>new Response(new Uint8Array(100),{headers:{'Content-Type':'audio/wav','X-TTS-Source':'chatterbox-multilingual-v3','X-TTS-Locale':'en-US'}});
const active=ms=>[...timers].findLast(t=>t.active&&t.ms===ms);
(async()=>{
 for(mode of ['success','mute','cancel','language']){
  window.attuneOutputMuted=false;
  global.fetch=async()=>{assert(active(limits.generationMilliseconds));return audio();};
  assert.equal(await client.mentalNeuralSpeech('Explicit synthetic deadline fixture',new AbortController().signal,()=>true,()=>{},()=>{}),mode==='success');
 }
 window.attuneOutputMuted=false;
 global.fetch=async(url,init)=>{active(limits.generationMilliseconds).callback();assert(init.signal.aborted);throw Error('aborted');};
 assert.equal(await client.mentalNeuralSpeech('No model inference',new AbortController().signal,()=>true,()=>{},()=>{}),false);
 assert.equal(checks,4);assert(![...timers].some(t=>t.active));
 const transport=require.resolve('../../apps/vehicle-app/src/utils/mentalLocalTransport.ts');
 require.cache[transport]={id:transport,filename:transport,loaded:true,exports:{mentalLocalTransport:(url,init)=>global.fetch(url,init)}};
 const {POST}=require('../../apps/vehicle-app/src/app/api/mental-neural-speech/route.ts');
 process.env.ATTUNE_MENTAL_TTS_TOKEN='noncredential-fixture-'.repeat(3);
 const request=signal=>new NextRequest('http://localhost:3360/api/mental-neural-speech',{method:'POST',signal,headers:{Host:'localhost:3360',Origin:'http://localhost:3360','Content-Type':'application/json'},body:JSON.stringify({text:'No inference fixture',language:'en',speechConsent:true})});
 for(const terminal of ['success','deadline','abort']){
  const controller=new AbortController();
  global.fetch=async(url,init)=>{
   assert(active(limits.proxyMilliseconds));
   if(terminal==='deadline')active(limits.proxyMilliseconds).callback();
   if(terminal==='abort')controller.abort();
   if(init.signal.aborted)throw Error('aborted');
   return audio();
  };
  const response=await POST(request(controller.signal));
  assert.equal(response.status,terminal==='success'?200:504);
  assert(![...timers].some(t=>t.active));
 }
 assert(limits.workerSeconds*1000<limits.proxyMilliseconds&&limits.proxyMilliseconds<limits.generationMilliseconds);
 console.log('PASS bounded proxy/client deadlines, generation-to-playback handoff and live mute/cancel/locale observation (virtual time and synthetic audio; no inference)');
})().catch(error=>{console.error(error);process.exitCode=1;});
