/** Catalog closing in the page: the bridge plays A, B, C and then the fixed recording of the server-checked catalog line.
 * Real module; a synthetic catalog manifest and synthetic WAV bytes (the committed manifest has no recordings yet);
 * explicit playback and HTTP fixtures; no browser or inference. */
require('./ts_loader.js');
const assert=require('node:assert/strict'),Module=require('node:module'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'../..'),PUBLIC=path.join(ROOT,'apps/vehicle-app/public');
global.window=new EventTarget();global.document=new EventTarget();document.hidden=false;
const store=new Map([['attune.language.v1','tr']]);
global.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)};
global.Audio=class{};
const sha=b=>crypto.createHash('sha256').update(Buffer.from(b)).digest('hex');
const abc=JSON.parse(fs.readFileSync(path.join(PUBLIC,'audio/mental/closing-abc/v1/manifest.json'),'utf8'));
const committed=JSON.parse(fs.readFileSync(path.join(PUBLIC,'audio/mental/closing-catalog/v1/manifest.json'),'utf8'));
const catalog=JSON.parse(fs.readFileSync(path.join(ROOT,'shared/mental/closing-catalog/v1/catalog.json'),'utf8'));

// Synthetic recordings: 99 distinct WAV byte strings, one per language and line, labelled for the playback log.
const bytesOf=new Map(),labels=new Map(abc.entries.map(e=>[e.sha256,e.language+':'+e.variantId]));
const entries=[];
for(const language of ['tr','en','de'])for(const p of catalog.patterns){
 const body=Buffer.alloc(240);body.write('RIFF',0);body.write(('cat:'+language+':'+p.id).padEnd(16),44);
 const audioPath=`/audio/mental/closing-catalog/v1/${language}/female-calm-v1/${language.toUpperCase()}_${p.id}.wav`;
 bytesOf.set(audioPath,body);labels.set(sha(body),'cat:'+language+':'+p.id);
 entries.push({assetId:`closing-catalog/v1/${language}/female-calm-v1/${p.id}`,language,patternId:p.id,exactText:p.text[language],audioPath,
  speakerProfile:'female-calm-v1',sha256:sha(body),bytes:body.length,durationMs:3000,approvalStatus:'technical-preview-awaiting-owner-listening',ownerApprovedAt:null});
}
const synthetic={...committed,approval:{status:'technical-preview-awaiting-owner-listening',ownerApprovedAt:null},entries};

let elements=[],log=[],active=0,maxActive=0,playMs=25,corrupt=null,onStart=null,ttsRequests=0;
const original=Module._load;
Module._load=function(request,parent,...args){
 if(request==='../../public/audio/mental/closing-catalog/v1/manifest.json'&&/mentalClosingBridge\.ts$/.test(parent.filename))return synthetic;
 if(request==='./fixedFileSpeech'&&/mental(ClosingBridge|NeuralSpeech)\.ts$/.test(parent.filename))return {playAudioBytes:(audio,bytes,mime,duration,signal,current,observe)=>new Promise(resolve=>{
  elements.push(audio);
  const label=labels.get(sha(bytes))||'unknown';
  const allowed=()=>!signal.aborted&&current()&&!document.hidden&&!window.attuneOutputMuted;
  if(!allowed()){resolve(false);return;}
  active++;maxActive=Math.max(maxActive,active);log.push('start '+label);observe('playing');onStart?.(label);
  let done=false;
  const poll=setInterval(()=>{if(!allowed())finish(false);},5);
  const finish=ok=>{if(done)return;done=true;clearInterval(poll);clearTimeout(timer);signal.removeEventListener('abort',abort);active--;log.push((ok?'end ':'stop ')+label);if(ok)observe('ended');resolve(ok);};
  const abort=()=>finish(false),timer=setTimeout(()=>finish(allowed()),playMs);
  signal.addEventListener('abort',abort,{once:true});
 })};
 return original.call(this,request,parent,...args);
};
global.fetch=async url=>{
 url=String(url);
 if(url.startsWith('/audio/mental/closing-catalog/')){let b=bytesOf.get(url);if(!b)return new Response('',{status:404});if(corrupt&&url.includes(corrupt)){b=Buffer.from(b);b[60]^=1;}return new Response(b);}
 if(url.startsWith('/audio/'))return new Response(fs.readFileSync(path.join(PUBLIC,url)));
 ttsRequests++;throw Error('no speech generation expected in the catalog closing: '+url);
};
let focus=0;window.addEventListener('attune-stream-focus',e=>{focus+=e.active?1:-1;});
const B=require('../../apps/vehicle-app/src/utils/mentalClosingBridge.ts');
function hooks(extra={}){
 const h={states:[],timings:[],live:true,language:'tr'};
 return Object.assign(h,{current:()=>h.live,audioReady:()=>{},requestGesture:()=>()=>{},state:s=>h.states.push(s),timing:s=>h.timings.push(s)},extra);
}
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const reset=()=>{elements=[];log=[];active=0;maxActive=0;corrupt=null;onStart=null;playMs=25;ttsRequests=0;};
const C=(language,id)=>catalog.patterns.find(p=>p.id===id).text[language];

(async()=>{
 // 1. Availability. The committed manifest: no recording yet (catalog off, request unchanged), or whole languages of 33
 // technical previews (usable only in technical-preview mode, never in approved mode).
 for(const language of ['tr','en','de']){
  const count=committed.entries.filter(e=>e.language===language).length;
  assert([0,33].includes(count),language);
  const clips=B.closingCatalogClips(language,'technical-preview',committed);
  assert.equal(clips===null?0:Object.keys(clips).length,count,language);
  assert.equal(B.closingCatalogClips(language,'approved',committed),null,'no owner approval yet');
 }
 assert.equal(Object.keys(B.closingCatalogClips('tr','technical-preview',synthetic)).length,33);
 assert.equal(B.closingCatalogClips('tr','off',synthetic),null);
 assert.equal(B.closingCatalogClips('tr','approved',synthetic),null,'technical previews never play in approved mode');
 const variant=change=>{const copy=JSON.parse(JSON.stringify(synthetic));change(copy);return B.closingCatalogClips('en','technical-preview',copy);};
 assert.equal(variant(m=>{m.entries=m.entries.filter(e=>!(e.language==='en'&&e.patternId==='C17'));}),null,'never a subset of the 33 lines');
 assert.equal(variant(m=>{m.entries.find(e=>e.language==='en').audioPath='/audio/mental/closing-abc/v1/en/x.wav';}),null);
 assert.equal(variant(m=>{m.referenceSha256='0'.repeat(64);}),null,'other reference voice');
 assert.equal(variant(m=>{m.generation={...m.generation,temperature:0.9};}),null,'other generation settings');
 assert.equal(variant(m=>{m.entries.find(e=>e.language==='en').approvalStatus='draft';}),null);
 assert(variant(m=>{m.entries.filter(e=>e.language!=='en').forEach(e=>{e.sha256='bad';});}),'another language does not affect this one');

 process.env.NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE='technical-preview';
 // 2. Main path: the checked line arrives during A; A→B→C, then the line's own recording; no speech generation.
 reset();playMs=40;let h=hooks();let f=B.startClosingFlow(h);assert(f&&f.catalog);
 onStart=label=>{if(label==='tr:'+f.selection.split('-')[0])f.catalogReady('C09',C('tr','C09'));};
 assert.equal(await f.complete(),'played');
 assert.deepEqual(log.filter(l=>l.startsWith('start')).map(l=>l.slice(6)),[...f.selection.split('-').map(v=>'tr:'+v),'cat:tr:C09']);
 assert.equal(maxActive,1);assert.equal(ttsRequests,0);assert.equal(new Set(elements).size,1,'one media element for A, B, C and the catalog line');
 for(const stage of ['closing-summary-text-ready','closing-summary-first-ready','closing-summary-audio-start','closing-summary-playing','closing-summary-ended','closing-summary-complete'])assert(h.timings.includes(stage),stage);
 assert(h.timings.indexOf('closing-summary-audio-start')>h.timings.indexOf('closing-C-ended'));
 assert.equal(focus,0);

 // 3. A line that is not the recording's exact text, an unknown id or no id: nothing is spoken, no generation.
 for(const [id,text] of [['C09',C('tr','C08')],['C99','x'],['__proto__','x'],[null,C('tr','C09')],['C09',C('en','C09')]]){
  reset();playMs=10;h=hooks();f=B.startClosingFlow(h);f.catalogReady(id,text);
  assert.equal(await f.complete(),'no-spoken-summary',String(id));
  assert(!log.some(l=>l.includes('cat:')));assert.equal(ttsRequests,0);
  assert(h.timings.includes('closing-summary-catalog-mismatch'));
 }

 // 4. Driving, consent or epoch change (session guard) during C: C stops and the catalog line never starts.
 reset();playMs=60;h=hooks();f=B.startClosingFlow(h);f.catalogReady('C02',C('tr','C02'));
 onStart=label=>{if(label==='tr:'+f.selection.split('-')[2])setTimeout(()=>{h.live=false;},10);};
 assert.equal(await f.complete(),'cancelled');await wait(200);
 assert(!log.some(l=>l.includes('cat:')),'no catalog line after the stop');assert.equal(focus,0);

 // 5. The line arrives only after the stop (late analysis answer): ignored, nothing plays.
 reset();playMs=30;h=hooks();f=B.startClosingFlow(h);
 onStart=label=>{if(label==='tr:'+f.selection.split('-')[2])f.abort();};
 const done=f.complete();await wait(120);f.catalogReady('C02',C('tr','C02'));
 assert.equal(await done,'cancelled');await wait(100);assert(!log.some(l=>l.includes('cat:')));

 // 6. Altered recording of the chosen line: refused before playing; the bridge itself still played.
 reset();playMs=10;corrupt='TR_C11';h=hooks();f=B.startClosingFlow(h);f.catalogReady('C11',C('tr','C11'));
 assert.equal(await f.complete(),'failed');assert(!log.some(l=>l.includes('cat:')));
 assert(h.timings.includes('closing-summary-first-failed'));

 // 7. Mute and hidden page during C stop the closing; the line does not start.
 for(const guard of ['muted','hidden']){
  reset();playMs=50;h=hooks();f=B.startClosingFlow(h);f.catalogReady('C30',C('tr','C30'));
  onStart=label=>{if(label==='tr:'+f.selection.split('-')[2])setTimeout(()=>{if(guard==='muted')window.attuneOutputMuted=true;else document.hidden=true;},5);};
  assert.notEqual(await f.complete(),'played');window.attuneOutputMuted=false;document.hidden=false;
  assert(!log.some(l=>l.includes('cat:')),guard);
 }

 // 8. The free-text line of the earlier path is not accepted as a catalog line; after one call, later calls are ignored.
 reset();playMs=10;h=hooks();f=B.startClosingFlow(h);f.catalogReady('C09',C('tr','C09'));f.catalogReady('C30',C('tr','C30'));f.summaryReady('Başka bir serbest metin altı kelime burada.');
 assert.equal(await f.complete(),'played');assert.deepEqual(log.filter(l=>l.startsWith('start cat:')),['start cat:tr:C09']);
 assert.equal(focus,0);
 console.log('PASS catalog closing: 33-line gate per language (profile, settings, paths, approval), A→B→C then the checked line\'s own recording on the same element, no speech generation, exact-text match required, stops on session/mute/hidden, late lines ignored, altered recording refused (fixtures; no browser/inference)');
})().catch(error=>{console.error(error);process.exitCode=1;});
