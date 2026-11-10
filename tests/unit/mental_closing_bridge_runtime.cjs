/** Closing A/B/C bridge: real module, real manifest/WAV bytes, explicit playback and HTTP fixtures; no browser or inference. */
require('./ts_loader.js');
const assert=require('node:assert/strict'),Module=require('node:module'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'../..'),PUBLIC=path.join(ROOT,'apps/vehicle-app/public');
global.window=new EventTarget();global.document=new EventTarget();document.hidden=false;
const store=new Map([['attune.language.v1','tr']]);
global.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)};
global.Audio=class{};
const manifest=JSON.parse(fs.readFileSync(path.join(PUBLIC,'audio/mental/closing-abc/v1/manifest.json'),'utf8'));
const sha=b=>crypto.createHash('sha256').update(Buffer.from(b)).digest('hex');
const labels=new Map(manifest.entries.map(e=>[e.sha256,e.language+':'+e.variantId]));

// Playback fixture: one active output at a time is asserted; every start/end is logged with a label.
let log=[],active=0,maxActive=0,playMs=25,failLabel=null,onStart=null;
const original=Module._load;
Module._load=function(request,parent,...args){
 if(request==='./fixedFileSpeech'&&/mental(ClosingBridge|NeuralSpeech)\.ts$/.test(parent.filename))return {playAudioBytes:(audio,bytes,mime,duration,signal,current,observe)=>new Promise(resolve=>{
  const label=labels.get(sha(bytes))||'tts:'+Buffer.from(bytes).toString('utf8',44,60).trim();
  // Mirrors the real guard: session, mute and visibility end output.
  const allowed=()=>!signal.aborted&&current()&&!document.hidden&&!window.attuneOutputMuted;
  if(!allowed()){resolve(false);return;}
  active++;maxActive=Math.max(maxActive,active);log.push('start '+label);observe('playing');onStart?.(label);
  let done=false;
  const poll=setInterval(()=>{if(!allowed())finish(false);},5);
  const finish=ok=>{if(done)return;done=true;clearInterval(poll);clearTimeout(timer);signal.removeEventListener('abort',abort);active--;log.push((ok?'end ':'stop ')+label);if(ok)observe('ended');resolve(ok);};
  const abort=()=>finish(false),timer=setTimeout(()=>finish(allowed()&&label!==failLabel),playMs);
  signal.addEventListener('abort',abort,{once:true});
 })};
 return original.call(this,request,parent,...args);
};
// HTTP fixture: static clips come from the real public files; speech requests answer after a chosen delay.
let ttsDelay=0,ttsRequests=[],corrupt=null;
const wav=text=>{const body=Buffer.alloc(200);body.write('RIFF',0);body.write(text.padEnd(16).slice(0,16),44);return body;};
global.fetch=async(url,init={})=>{
 if(String(url).startsWith('/audio/')){
  let bytes=fs.readFileSync(path.join(PUBLIC,String(url)));
  if(corrupt&&String(url).includes(corrupt)){bytes=Buffer.from(bytes);bytes[100]^=1;}
  return new Response(bytes);
 }
 assert.equal(url,'/api/mental-neural-speech');
 const body=JSON.parse(init.body);ttsRequests.push({text:body.text,at:log.length,profile:body.speakerProfile});
 assert.equal(body.speakerProfile,'female-calm-v1');
 await new Promise((resolve,reject)=>{const t=setTimeout(resolve,ttsDelay);init.signal?.addEventListener('abort',()=>{clearTimeout(t);reject(Error('aborted'));},{once:true});});
 return new Response(wav(body.text.split(' ')[0]),{headers:{'Content-Type':'audio/wav','X-TTS-Source':'chatterbox-multilingual-v3','X-TTS-Locale':'tr-TR','X-TTS-Speaker-Profile':'female-calm-v1'}});
};
let focus=0;window.addEventListener('attune-stream-focus',e=>{focus+=e.active?1:-1;});
const B=require('../../apps/vehicle-app/src/utils/mentalClosingBridge.ts');

function hooks(extra={}){
 const h={states:[],timings:[],live:true,language:'tr'};
 return Object.assign(h,{current:()=>h.live,audioReady:()=>{},requestGesture:()=>()=>{},state:s=>h.states.push(s),timing:s=>h.timings.push(s)},extra);
}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const reset=()=>{log=[];active=0;maxActive=0;ttsRequests=[];failLabel=null;corrupt=null;onStart=null;ttsDelay=0;playMs=25;};

(async()=>{
 // 1. Gate: off by default; approved-only finds nothing approved yet; preview needs complete, matching groups.
 delete process.env.NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE;
 assert.equal(B.closingBridgeMode(),'off');assert.equal(B.startClosingFlow(hooks()),null);
 for(const language of ['tr','en','de']){
  assert.equal(B.closingBridgeClips(language,'approved'),null,'unapproved recordings never play in approved mode');
  const groups=B.closingBridgeClips(language,'technical-preview');
  assert.deepEqual(groups.map(g=>g.map(c=>c.variantId)),['A','B','C'].map(g=>[1,2,3,4,5].map(i=>g+i)));
  assert(groups.flat().every(c=>c.language===language&&c.speakerProfile==='female-calm-v1'));
 }
 assert.equal(manifest.entries.length,45);
 const variant=(change)=>{const copy=JSON.parse(JSON.stringify(manifest));change(copy);return B.closingBridgeClips('en','technical-preview',copy);};
 assert.equal(variant(m=>m.entries.splice(m.entries.findIndex(e=>e.language==='en'&&e.group==='B'),1)),null,'missing recording');
 assert.equal(variant(m=>{m.referenceSha256='0'.repeat(64);}),null,'other reference');
 assert.equal(variant(m=>{m.generation={...m.generation,temperature:.5};}),null,'other settings');
 assert.equal(variant(m=>{m.speakerProfile='official-default';}),null,'other profile');
 assert.equal(variant(m=>{m.entries.find(e=>e.language==='en').approvalStatus='rejected';}),null,'unapproved status');
 assert.equal(variant(m=>{m.entries.find(e=>e.language==='en').sha256='x';}),null,'malformed hash');
 assert.equal(variant(m=>{m.entries.find(e=>e.language==='en').audioPath='https://drive.google.com/file/d/x/view';}),null,'no external/Drive URLs');
 const approvedCopy=JSON.parse(JSON.stringify(manifest));approvedCopy.approval={status:'approved',ownerApprovedAt:'2026-11-10T00:00:00Z'};approvedCopy.entries.forEach(e=>{e.approvalStatus='approved';e.ownerApprovedAt='2026-11-10T00:00:00Z';});
 assert(B.closingBridgeClips('en','approved',approvedCopy),'owner approval would enable approved mode');

 // 2. Selection: one per group, same language, never the previous combination; all 125 reachable.
 const groups=B.closingBridgeClips('de','technical-preview');
 let previous=null;const seen=new Set();
 for(let i=0;i<4000;i++){const s=B.selectClosingBridge('de',groups);assert.deepEqual(s.clips.map(c=>c.group),['A','B','C']);assert(s.clips.every(c=>c.language==='de'));assert.notEqual(s.key,previous);previous=s.key;seen.add(s.key);}
 assert.equal(seen.size,125);
 const zero=()=>0,first=B.selectClosingBridge('en',B.closingBridgeClips('en','technical-preview'),zero),second=B.selectClosingBridge('en',B.closingBridgeClips('en','technical-preview'),zero);
 assert.notEqual(first.key,second.key,'deterministic escape from a repeat');

 process.env.NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE='technical-preview';
 // 3. Main path: A→B→C once, summary request starts during A, speech generated before C ends, no overlap, next part prefetched.
 reset();ttsDelay=10;playMs=60;
 let h=hooks();const flow=B.startClosingFlow(h);assert(flow);
 assert.equal(B.startClosingFlow(hooks({live:false,current:()=>false})),null,'precondition guard');
 // The closing flow started; the summary text arrives while A plays.
 onStart=label=>{if(label.endsWith(':'+flow.selection.split('-')[0]))flow.summaryReady('Birinci cümle burada altı kelimeden oluşuyor. İkinci cümle de burada.');};
 const outcome=await Promise.all([flow.complete(),flow.complete()]);
 assert.deepEqual(outcome,['played','played'],'second complete() returns the same single run');
 const starts=log.filter(l=>l.startsWith('start'));
 assert.deepEqual(starts.map(l=>l.split(':')[1]).slice(0,3),flow.selection.split('-'));
 assert(starts.slice(0,3).every(l=>l.startsWith('start tr:')),'same language');
 assert.equal(starts.filter(l=>!l.includes('tts')).length,3,'each recording plays exactly once');
 assert.equal(maxActive,1,'never two outputs at once');
 assert.equal(ttsRequests.length,2,'two parts, each requested once');
 const cEnd=log.findIndex(l=>l.startsWith('end tr:C'));
 assert(ttsRequests[0].at<=cEnd&&ttsRequests[1].at<=cEnd,'both parts generated during the bridge (next part prefetch kept)');
 assert(log.findIndex(l=>l.includes('start tts'))>cEnd,'summary plays only after C ended');
 assert(h.timings.includes('closing-summary-first-ready')&&h.timings.indexOf('closing-summary-first-ready')<h.timings.indexOf('closing-bridge-ended'));
 assert.equal(h.states.at(-1),'speaking');assert.equal(focus,0,'focus released');

 // 4. Slow speech: honest pending state after C, no recording replayed to fill the wait.
 reset();ttsDelay=400;playMs=20;h=hooks();
 let f=B.startClosingFlow(h);f.summaryReady('Kısa ama altı kelimelik bir özet cümlesi.');
 assert.equal(await f.complete(),'played');
 assert(h.states.includes('closingSpeechPending'));assert.equal(log.filter(l=>l.startsWith('start tr:')).length,3);
 assert(log.findIndex(l=>l.startsWith('start tts'))>log.findIndex(l=>l.startsWith('end tr:C')));

 // 5. Summary text later than the bridge: pending summary state, then speech.
 reset();playMs=10;h=hooks();f=B.startClosingFlow(h);
 await wait(450);assert(h.states.includes('closingSummaryPending'));
 f.summaryReady('Geç gelen özet metni burada altı kelime.');assert.equal(await f.complete(),'played');

 // 6. Cancellation during A: recordings and pending speech stop; a late answer never plays.
 reset();ttsDelay=200;playMs=80;h=hooks();f=B.startClosingFlow(h);f.summaryReady('İptal edilecek özet metni altı kelime burada.');
 await wait(40);f.abort();const before=log.length;
 assert.equal(await f.complete(),'cancelled');await wait(300);
 assert(!log.slice(before).some(l=>l.startsWith('start')),'nothing starts after cancel');assert.equal(focus,0);

 // 7. Session invalidation (park/consent/epoch) and mute/hidden stop output without new selection.
 for(const guard of ['session','muted','hidden']){
  reset();playMs=60;h=hooks();f=B.startClosingFlow(h);f.summaryReady('Durdurulacak özet metni altı kelimeden oluşur.');
  await wait(30);
  if(guard==='session')h.live=false;
  if(guard==='muted')window.attuneOutputMuted=true;
  if(guard==='hidden')document.hidden=true;
  const result=await f.complete();window.attuneOutputMuted=false;document.hidden=false;
  assert.notEqual(result,'played');assert(!log.some(l=>l.includes('start tts')),guard+': no summary after stop');
 }

 // 8. Language change: the bridge stops and nothing else plays.
 reset();playMs=60;h=hooks();f=B.startClosingFlow(h);f.summaryReady('Dil değişince durması gereken özet metni.');
 await wait(30);store.set('attune.language.v1','en');window.dispatchEvent(new Event('attune-locale-media-cancel'));
 assert.notEqual(await f.complete(),'played');store.set('attune.language.v1','tr');

 // 9. Altered recording: verified before anything plays; fallback without any audio or speech request.
 reset();corrupt='/B/';h=hooks();f=B.startClosingFlow(h);f.summaryReady('Bozuk kayıt nedeniyle geri dönüş metni.');
 assert.equal(await f.complete(),'fallback');assert.equal(log.length,0);assert.equal(ttsRequests.length,0);

 // 10. Playback failure of B: later output never starts; result is reported as failed.
 reset();playMs=20;h=hooks();f=B.startClosingFlow(h);failLabel='tr:'+f.selection.split('-')[1];f.summaryReady('Oynatma hatasında sesli özet çalınmaz.');
 assert.equal(await f.complete(),'failed');assert(!log.some(l=>l.includes('start tts')));assert(!log.some(l=>l.startsWith('start tr:C')));

 // 11. Neural engine not selected: no bridge (existing behaviour), nothing played.
 store.set('attune.mental-speech-engine.v1','browser-system');assert.equal(B.startClosingFlow(hooks()),null);store.delete('attune.mental-speech-engine.v1');
 assert.equal(focus,0);
 console.log('PASS closing A/B/C bridge: gated by mode/profile/hash/approval, one selection per closing without repeats (125 reachable), A→B→C without overlap, summary speech prepared during the bridge with next-part prefetch, honest waits, cancel/session/mute/hidden/language stops, altered/failed assets fall back (fixtures; no browser/inference)');
})().catch(error=>{console.error(error);process.exitCode=1;});
