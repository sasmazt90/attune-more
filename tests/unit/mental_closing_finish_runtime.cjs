/** Real finish()/cleanup()/speakClosing() closures with a recorded closing-flow fixture: normal and structured paths. */
require('./ts_loader.js');
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const source=fs.readFileSync('apps/vehicle-app/src/utils/useMentalConversation.ts','utf8');
const ast=ts.createSourceFile('mental.ts',source,ts.ScriptTarget.Latest,true),functions={};
(function visit(node){if(ts.isFunctionDeclaration(node)&&node.name)functions[node.name.text]=node.getText(ast);ts.forEachChild(node,visit);})(ast);
const code=ts.transpileModule(['finish','updateContext','speakClosing','cleanup'].map(n=>functions[n]).join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;

let body;
// The real client-side bound check from the bridge module (needs only minimal browser globals to load).
global.window=global.window||new EventTarget();global.document=global.document||Object.assign(new EventTarget(),{hidden:false});
global.localStorage=global.localStorage||{getItem:()=>null,setItem:()=>{}};global.Audio=global.Audio||class{};
const {shortSpokenSummary}=require('../../apps/vehicle-app/src/utils/mentalClosingBridge.ts');
async function scenario(name,{structured=false,outcome='played',analyzeOk=true,bridge=true,failed=false,empty=false,withdraw=false,cancelDuring=false,probeGuard=false,spoken='You talked about work and sleep.',catalog=false,catalogId}={}){
 const events=[],no=()=>{};
 const user={id:'s-1-user',turn:1,sender:'USER',text:'Synthetic non-personal statement.',time:'12:00',completed:true};
 const ai={id:'s-1-ai',turn:1,sender:'AI',text:'Synthetic reply.',time:'12:00',completed:true};
 const r={structured,structuredState:structured?{language:'en',speakerProfile:'female-calm-v1',listenOnly:false}:null,mounted:true,active:true,epoch:4,audioEpoch:0,turn:1,id:'s',startedAt:'2026-11-09',
  transcript:empty?[]:[user,ai],memory:[],memoryThrough:0,busy:false,failed,pendingTurn:null,pendingSpeech:null,controller:null,closing:null,audio:null,recognition:null,restart:null};
 const settings={current:{parked:true,speechConsent:true,cloudConsent:true,voiceEnabled:true}};
 let phase,voiceNotice,summary,flowHooks,neural=0,run,spokenClosing;
 const flow={mode:'technical-preview',selection:'A1-B2-C3',catalog,
  catalogReady:(id,text)=>events.push('catalogReady:'+id+':'+text),
  summaryReady:text=>events.push('summaryReady:'+text),
  summaryUnavailable:()=>events.push('summaryUnavailable'),
  complete:async()=>{events.push('complete');
   if(probeGuard){assert.equal(flowHooks.current(),true,'live during the closing');for(const key of ['parked','speechConsent','cloudConsent','voiceEnabled']){settings.current[key]=false;events.push('guard:'+key+':'+flowHooks.current());settings.current[key]=true;}r.mounted=false;events.push('guard:mounted:'+flowHooks.current());r.mounted=true;}
   if(cancelDuring){r.epoch++;run.cleanup();return 'cancelled';}return outcome;},
  abort:()=>events.push('abort')};
 const deps={runtime:{current:r},settings,historyPermission:{current:false},mentalHistoryAllowed:()=>false,Date,AbortController,setTimeout,clearTimeout,
  abortRecognition:no,stopAudio:()=>{events.push('stopAudio');},timing:stage=>{if(stage.startsWith('closing-'))events.push('t:'+stage);},getLocale:()=> 'en-US',getLanguage:()=> 'en',t:v=>v,
  serviceAllowed:()=>settings.current.speechConsent,spokenText:v=>v.trim(),isDemoMode:()=>false,isMentalSummarySavingAllowed:()=>false,isMentalTranscriptSavingAllowed:()=>false,
  canonicalMentalTheme:v=>v,setPhase:v=>{phase=v;},setNotice:no,setActive:no,setSummary:v=>{summary=v;events.push('setSummary');},setVoiceState:v=>events.push('state:'+v),setVoiceNotice:v=>{voiceNotice=v;},setClosingAudio:v=>events.push('closingAudio:'+v),setSpokenClosing:v=>{spokenClosing=v;events.push('spokenClosing:'+v);},
  API:'fixture',closingTranscript:require('../../apps/vehicle-app/src/utils/mentalSessionClose.ts').closingTranscript,setMessages:no,pendingAudioPlay:{current:null},setAudioNeedsGesture:no,
  readMentalHistory:()=>[],saveMentalHistory:async()=>[],setHistory:no,contextWindowThrough:(m,t)=>t,
  shortSpokenSummary,
  startClosingFlow:hooks=>{events.push('startClosingFlow');flowHooks=hooks;return bridge?flow:null;},
  mentalNeuralSpeech:async(text,signal,current,onPlaying,audioReady,options)=>{neural++;events.push('neural:'+options.speakerProfile+':'+text);return true;},
  fetch:async(url,options)=>{
   assert(url.endsWith('/analyze-session'),'only the summary request');events.push('analyze');
   if(withdraw)settings.current.speechConsent=false;
   events.push('requestSpoken:'+(body=JSON.parse(options.body)).spokenSummary);if('spokenCatalog' in body)events.push('requestCatalog:'+body.spokenCatalog);
   if(!analyzeOk)return {ok:false,json:async()=>({})};
   return {ok:true,json:async()=>({summaryText:'  You described a synthetic situation in detail over several sentences.  ',themes:[],providerType:'LIVE_OPENAI',spokenSummary:structured?'Your short closing.':spoken,...(catalogId!==undefined?{spokenCatalogId:catalogId}:{})})};
  }};
 run=new Function(...Object.keys(deps),code+';return {finish,cleanup};')(...Object.values(deps));
 await run.finish();await run.finish();
 return {events,phase,voiceNotice,summary,neural,flowHooks,r,settings,spokenClosing};
}

(async()=>{
 // Normal (non-structured) conversation: bridge starts before context/summary work; text-ready triggers preparation.
 let s=await scenario('normal-played');
 const order=s.events.filter(e=>!e.startsWith('t:')&&!e.startsWith('state:'));
 assert.deepEqual(order,['stopAudio','startClosingFlow','analyze','requestSpoken:true','summaryReady:You talked about work and sleep.','setSummary','closingAudio:true','complete','closingAudio:false','spokenClosing:true','stopAudio','abort']);
 // Normal path: only the short spokenSummary is spoken; an invalid or missing line never falls back to summaryText.
 for(const bad of [null,'','One sentence here. And a second sentence.','This spoken line is far too long because it keeps going on and on beyond twelve words.']){
  const v=await scenario('normal-invalid-spoken',{spoken:bad,outcome:'no-spoken-summary'});
  assert(v.events.includes('summaryUnavailable'));assert(!v.events.some(e=>e.startsWith('summaryReady')),'no long-text fallback');
  assert.equal(v.voiceNotice,'Özet hazır; kısa sesli özet oluşturulamadı.');assert.equal(v.phase,'completed');assert(v.summary.summaryText.includes('several sentences'));
 }
 assert(s.events.indexOf('t:closing-trigger')<s.events.indexOf('startClosingFlow'));
 assert(s.events.indexOf('startClosingFlow')<s.events.indexOf('t:closing-context-start'),'bridge does not wait for context or summary');
 assert.equal(s.phase,'completed');assert.equal(s.neural,0,'normal path speaks only through the closing flow');assert.equal(s.voiceNotice,undefined);
 assert.equal(s.r.closing,null,'closing slot released');assert.equal(s.flowHooks.language,'en');
 // The closing guard is the dynamic-closing guard: park, consents, voice, service, epoch, language.
 assert.equal(s.flowHooks.current(),true);s.r.epoch++;assert.equal(s.flowHooks.current(),false,'a newer session (epoch) invalidates the old closing');
 s=await scenario('guard',{probeGuard:true});
 assert.deepEqual(s.events.filter(e=>e.startsWith('guard:')),['guard:parked:false','guard:speechConsent:false','guard:cloudConsent:false','guard:voiceEnabled:false','guard:mounted:false']);
 s=await scenario('normal-failed',{outcome:'failed'});assert.equal(s.phase,'completed');assert(s.voiceNotice.includes('Özet hazır'),'text result stays, audio failure is reported');
 s=await scenario('user-stopped-audio',{outcome:'cancelled'});assert.equal(s.phase,'completed','stopping the spoken closing keeps the stored summary');assert.equal(s.voiceNotice,undefined);assert(s.summary);
 assert.equal(s.spokenClosing,true,'a stopped closing also suppresses the separate completion guidance');
 s=await scenario('normal-fallback',{outcome:'fallback'});assert.equal(s.neural,0,'normal fallback = existing text-only closing');assert.equal(s.phase,'completed');
 assert.equal(s.spokenClosing,false,'fallback: nothing spoke, the existing completion guidance stays');
 s=await scenario('structured-fallback',{structured:true,outcome:'fallback'});
 assert.equal(s.neural,1);assert(s.events.includes('neural:female-calm-v1:Your short closing.'),'structured fallback keeps the existing dynamic closing');
 s=await scenario('structured-played',{structured:true});assert(s.events.includes('requestSpoken:undefined'),'structured request unchanged');assert.equal(s.neural,0);assert(s.events.includes('summaryReady:Your short closing.'),'structured speaks its spokenSummary');
 s=await scenario('bridge-off',{bridge:false});assert.equal(s.spokenClosing,undefined,'bridge off: completion guidance unchanged');assert.equal(s.neural,0);assert(s.events.includes('requestSpoken:undefined'),'request unchanged when the bridge is off');assert.equal(s.phase,'completed');assert(!s.events.includes('complete'));
 s=await scenario('bridge-off-structured',{bridge:false,structured:true});assert.equal(s.neural,1,'unchanged structured closing');
 s=await scenario('summary-error',{analyzeOk:false});
 assert(!s.events.some(e=>e.startsWith('summaryReady')));assert(!s.events.includes('complete'));assert(s.events.includes('abort'),'summary failure stops the bridge');assert.equal(s.phase,'error');
 s=await scenario('withdrawn',{withdraw:true});assert(!s.events.some(e=>e.startsWith('summaryReady')));assert(s.events.includes('abort'));assert.equal(s.summary,undefined);
 s=await scenario('failed-session',{failed:true});assert(!s.events.includes('startClosingFlow'),'failed/crisis session: no bridge, no summary');
 s=await scenario('empty',{empty:true});assert(!s.events.includes('startClosingFlow'));
 // Catalog closing: asked for only when the page holds every catalog recording of the language; the checked line's id
 // and text go to the flow (its recording plays there); no id means nothing is spoken; free text is never used instead.
 s=await scenario('catalog-played',{catalog:true,catalogId:'C09',spoken:'You talked about difficulties with sleep.'});
 assert(s.events.includes('requestCatalog:true')&&s.events.includes('requestSpoken:true'));
 assert(s.events.includes('catalogReady:C09:You talked about difficulties with sleep.'));assert(!s.events.some(e=>e.startsWith('summaryReady')));
 assert.equal(s.neural,0);assert.equal(s.phase,'completed');
 s=await scenario('catalog-no-line',{catalog:true,catalogId:null,spoken:null,outcome:'no-spoken-summary'});
 assert(s.events.includes('summaryUnavailable'));assert(!s.events.some(e=>e.startsWith('catalogReady')||e.startsWith('summaryReady')));
 assert.equal(s.voiceNotice,'Özet hazır; kısa sesli özet oluşturulamadı.');
 s=await scenario('catalog-free-text-only',{catalog:true,spoken:'You talked about work and sleep.',outcome:'no-spoken-summary'});
 assert(s.events.includes('summaryUnavailable'),'a free-text line is not spoken on the catalog path');assert(!s.events.some(e=>e.startsWith('summaryReady')));
 s=await scenario('catalog-not-available',{catalog:false});assert(!s.events.some(e=>e.startsWith('requestCatalog')),'request unchanged without the catalog recordings');
 s=await scenario('catalog-structured',{catalog:true,structured:true});assert(!s.events.some(e=>e.startsWith('requestCatalog')));assert(s.events.includes('summaryReady:Your short closing.'));
 s=await scenario('cancel-during',{cancelDuring:true});assert(s.events.filter(e=>e==='abort').length>=1);assert.equal(s.r.closing,null);assert.notEqual(s.phase,'completed');
 console.log('PASS real finish(): bridge starts at the closing trigger before context/summary, preparation starts on validated text, normal and structured paths, fallback keeps existing behaviour, summary failure/consent withdrawal/cancel stop the bridge, failed and empty sessions never start it (fixtures)');
})().catch(error=>{console.error(error);process.exitCode=1;});
