/** Real hook closures, injected clock/network/media. No AWS, model or real latency claims. */
require('./ts_loader.js');const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const realRace=require('../../apps/vehicle-app/src/utils/mentalHybridRace.ts').chooseHybridTurn;
const source=fs.readFileSync('apps/vehicle-app/src/utils/useMentalConversation.ts','utf8'),ast=ts.createSourceFile('hook.ts',source,ts.ScriptTarget.Latest,true),functions={};
(function visit(n){if(ts.isFunctionDeclaration(n)&&n.name)functions[n.name.text]=n.getText(ast);ts.forEachChild(n,visit);})(ast);
const code=ts.transpileModule(['send','sendHybrid','finish','updateContext','speakClosing'].map(n=>functions[n]).join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
(async()=>{let count=0;
 for(const scenario of ['prepared-three-turns','personal','cancel','consent','drive','finish-control','server-safety-refusal']){
  const r={hybrid:true,structured:false,structuredState:{language:'tr',speakerProfile:'female-calm-v1',turn:0,asked:[]},mounted:true,active:true,epoch:1,audioEpoch:0,turn:0,id:'synthetic',transcript:[],memory:[],memoryThrough:0,busy:false,failed:false};
  let phase,summary,plays=0,personalPlays=0,pendingJobs=0,catalog=0,analysis=0,requestStates=[],lateResolvers=[],notices=[];const no=()=>{};
  const deps={performance,Date,AbortController,setTimeout,clearTimeout,document:{hidden:false},localStorage:{getItem:()=>null},runtime:{current:r},settings:{current:{parked:true,voiceEnabled:true,speechConsent:true,cloudConsent:true}},
   valid:e=>r.active&&r.epoch===e,serviceAllowed:()=>true,speechMuted:()=>false,mentalSpeechEngine:()=> 'chatterbox-v3',getLanguage:()=> 'tr',getLocale:()=> 'tr-TR',t:x=>x,
   abortRecognition:no,stopAudio:()=>{r.audioEpoch++;r.streamCancel?.();r.streamCancel=null;},cleanup:()=>{r.controller?.abort();},timing:no,setVoiceNotice:no,setVoiceState:no,setPhase:x=>phase=x,setNotice:x=>notices.push(x),setActive:no,setMessages:no,setAudioNeedsGesture:no,pendingAudioPlay:{current:null},
   append:m=>r.transcript.push(m),checkCrisisTrigger:()=>({isCrisis:false}),spokenText:x=>x,isDemoMode:()=>false,resume:()=>{r.busy=false;r.voiceWaiting=false;},cancel:()=>{r.active=false;r.failed=true;},API:'mock',
   closingTranscript:require('../../apps/vehicle-app/src/utils/mentalSessionClose.ts').closingTranscript,canonicalMentalTheme:x=>x,isMentalSummarySavingAllowed:()=>false,setSummary:x=>summary=x,
   startClosingFlow:()=>({catalog:true,catalogReady:(id)=>{assert.equal(id,'C09');catalog++;},complete:async()=> 'complete',abort:no}),setClosingAudio:no,setSpokenClosing:no,
   prepareMentalRecording:async(text,ids,signal)=>({play:async(audio,observe)=>{assert(!signal.aborted);assert(text.startsWith('prepared'));plays++;observe('prepared-0-playing');return true;}}),
   prepareMentalNeuralSpeech:(text,signal)=>{pendingJobs++;let resolve;const firstReady=scenario==='personal'?Promise.resolve(true):new Promise(ok=>{resolve=ok;lateResolvers.push(ok);});const cancel=()=>{pendingJobs--;resolve?.(false);};signal.addEventListener('abort',cancel,{once:true});return {firstReady,cancel:()=>{},play:async()=>{personalPlays++;return !signal.aborted;}};},
   chooseHybridTurn:async opts=>{
    let now=opts.receivedAt,id=0;const jobs=new Map();const clock={now:()=>now,set:(fn,ms)=>{jobs.set(++id,{at:now+ms,fn});return id;},clear:k=>jobs.delete(k)};
    const result=realRace({...opts,clock});for(let n=0;n<35;n++)await Promise.resolve();
    if(['cancel','consent','drive'].includes(scenario)){r.epoch++;r.controller.abort();}
    now=opts.receivedAt+3000;for(const [k,j] of [...jobs])if(j.at<=now){jobs.delete(k);j.fn();}return result;
   },
   fetch:async(url,options)=>{
    const b=JSON.parse(options.body);
    if(url.endsWith('/converse')){if(scenario==='server-safety-refusal'&&b.engine==='hybrid-personal-v1')return {ok:false,status:409};requestStates.push(b.structuredState);assert(b.history.every(m=>!m.content.includes('discarded')));const personal=b.engine==='hybrid-personal-v1',n=b.structuredState.turn+1;
     return {ok:true,json:async()=>({reply:(personal?'discarded-personal':'prepared')+' '+n,providerType:personal?'LIVE_OPENAI':'STRUCTURED_LOCAL',structuredState:{...b.structuredState,turn:n,asked:[...b.structuredState.asked,'B'+n]},audioAssetIds:['a','b'],...(scenario==='finish-control'?{sessionAction:'finish'}:{})})};}
    assert(url.endsWith('/analyze-session'));analysis++;assert.equal(b.engine,undefined);assert.equal(b.spokenCatalog,true);assert.equal(b.spokenSummary,true);assert(b.messages.every(m=>!m.content.includes('discarded')));
    return {ok:true,json:async()=>({summaryText:'Actual selected conversation.',themes:[],providerType:'LIVE_OPENAI',spokenCatalogId:'C09',spokenSummary:'Sleep was discussed.'})};
   },
  };
  if(scenario==='personal')deps.fetch=async()=>({ok:true,json:async()=>({reply:'personal selected',providerType:'LIVE_OPENAI',structuredState:{language:'tr',speakerProfile:'female-calm-v1',turn:1},audioAssetIds:[]})});
  const run=new Function(...Object.keys(deps),code+';return {send,finish};')(...Object.values(deps));
  const turns=scenario==='prepared-three-turns'?3:1;for(let n=0;n<turns;n++)await run.send('synthetic user '+n);
  for(const resolve of lateResolvers)resolve(true);for(let n=0;n<10;n++)await Promise.resolve();
  if(scenario==='prepared-three-turns'){assert.equal(plays,3);assert.equal(personalPlays,0);assert.equal(pendingJobs,0);assert.equal(r.transcript.length,6);assert.equal(r.structuredState.turn,3);assert.deepEqual(r.structuredState.asked,['B1','B2','B3']);assert.deepEqual(requestStates.map(s=>s.turn),[0,0,1,1,2,2]);await run.finish();assert.equal(analysis,1);assert.equal(catalog,1);assert(summary);}
  else if(scenario==='personal'){assert.equal(personalPlays,1);assert.equal(plays,0);assert.equal(r.transcript.at(-1).text,'personal selected');}
  else if(scenario==='finish-control'){assert.equal(plays+personalPlays,0);assert.equal(r.transcript.filter(m=>m.sender==='AI').length,0);assert.equal(catalog,1);}
  else{assert.equal(plays+personalPlays,0);assert.equal(r.transcript.filter(m=>m.sender==='AI').length,0);assert.equal(r.structuredState.turn,0);}
  assert(!r.failed);count++;
 }
 console.log(`PASS ${count} real hook scenarios: three repeated prepared turns commit only heard context/state, no accumulated TTS, personal winner, cancellation, catalog closing and no F01 duplicate`);
})().catch(e=>{console.error(e);process.exitCode=1;});
