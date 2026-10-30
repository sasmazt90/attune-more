/** Execute real lifecycle closures with labelled prepared-audio/provider fixtures. */
require('./ts_loader.js');
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const source=fs.readFileSync('apps/vehicle-app/src/utils/useMentalConversation.ts','utf8');
const ast=ts.createSourceFile('mental.ts',source,ts.ScriptTarget.Latest,true),functions={};
function visit(node){if(ts.isFunctionDeclaration(node)&&node.name)functions[node.name.text]=node.getText(ast);ts.forEachChild(node,visit);}visit(ast);
const names=['send','speak','finish','updateContext','speakClosing'];
const code=ts.transpileModule(names.map(n=>functions[n]).join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
(async()=>{
 for(const scenario of ['success','failure','throw','late','muted','crisis-limit','pending-limit']){
  const closingWorks=scenario==='success',crisisLimit=scenario==='crisis-limit';
  const r={structured:true,structuredState:null,mounted:true,active:true,epoch:1,audioEpoch:0,turn:crisisLimit||scenario==='pending-limit'?39:0,id:'synthetic',startedAt:'2026-10-27',transcript:[],memory:[],memoryThrough:0,busy:false,failed:false};
  let analyses=0,turnCalls=0,neural=0,prepared=0,summary,phase,voiceNotice;
  const no=()=>{};
  const deps={runtime:{current:r},settings:{current:{voiceEnabled:true,speechConsent:true,cloudConsent:true,parked:true}},historyPermission:{current:false},mentalHistoryAllowed:()=>false,
   valid:e=>r.active&&r.epoch===e,serviceAllowed:()=>true,getLanguage:()=> 'en',getLocale:()=> 'en-US',t:x=>x,
   Date,AbortController,setTimeout,clearTimeout,
   abortRecognition:no,cleanup:no,stopAudio:()=>{r.audioEpoch++;r.audio=null;},canonicalMentalTheme:x=>x,timing:no,setVoiceNotice:v=>voiceNotice=v,setVoiceState:no,setPhase:v=>phase=v,setNotice:no,setActive:no,setSummary:v=>summary=v,
   append:m=>r.transcript.push(m),checkCrisisTrigger:()=>({isCrisis:crisisLimit,emergencyResponseTr:'112 emergency'}),spokenText:x=>x,isDemoMode:()=>false,isMentalSummarySavingAllowed:()=>false,
   API:'mock',resume:()=>{r.busy=false;},cancel:()=>{r.active=false;},mentalSpeechEngine:()=> 'chatterbox-v3',approvedMentalTemplate:()=>null,
   playPreparedMental:async(text,ids)=>{prepared++;assert.equal(text,'Okay. What happened?');assert.deepEqual(ids,['prepared-A','prepared-B']);return true;},
   mentalNeuralSpeech:async(text,signal,current,onPlaying,audioReady,options)=>{neural++;assert(current());assert.equal(options.speakerProfile,'female-calm-v1');assert.equal(text,'Your own concise closing summary.');if(scenario==='throw')throw Error('Fixture audio unavailable');if(scenario==='late'){r.epoch++;r.audio='new-session-audio';}return closingWorks;},
   pendingAudioPlay:{current:null},setAudioNeedsGesture:no,
   fetch:async(url,options)=>{
    const body=JSON.parse(options.body);
    if(url.endsWith('/converse')){turnCalls++;assert.equal(body.engine,'structured-v1');assert.deepEqual(body.history,[]);return {ok:true,json:async()=>({reply:'Okay. What happened?',providerType:'STRUCTURED_LOCAL',structuredState:{language:'en',speakerProfile:'female-calm-v1',listenOnly:false},audioAssetIds:['prepared-A','prepared-B']})};}
    assert(url.endsWith('/analyze-session'),'No compaction/rewrite/other network requests');analyses++;
    assert.equal(body.messages.length,2);assert.equal(body.historyConsent,false);assert.deepEqual(body.priorSessions,[]);
    return {ok:true,json:async()=>({summaryText:'You described your own situation.',themes:[],providerType:'LIVE_OPENAI',spokenSummary:'Your own concise closing summary.',recommendations:[],relatedSessionIds:[],recurringThemes:[]})};
   },
  };
  const run=new Function(...Object.keys(deps),code+';return {send,finish};')(...Object.values(deps));
  const text='This is my synthetic personal situation';
  const pending=scenario==='pending-limit'?{user:{id:'synthetic-39-user',turn:39,sender:'USER',text,time:'12:00',completed:false},prior:[]}:undefined;
  if(pending)r.transcript.push(pending.user);
  await run.send(text,pending);
  if(crisisLimit){assert(r.failed);assert(r.transcript.some(m=>m.isCrisis&&m.text.includes('112')));assert.equal(analyses+neural+turnCalls,0);continue;}
  assert.equal(turnCalls,1);assert.equal(neural,0);assert.equal(prepared,1);assert.equal(analyses,0);
  if(scenario==='muted')deps.settings.current.voiceEnabled=false;
  await run.finish();await run.finish();
  assert.equal(analyses,1);assert.equal(neural,scenario==='muted'?0:1);assert(summary.summaryText);
  if(scenario!=='late')assert.equal(phase,'completed');
  if(scenario==='late')assert.equal(r.audio,'new-session-audio');
  if(['failure','throw'].includes(scenario))assert(voiceNotice.includes('Özet hazır'));
 }
 console.log('PASS real structured send/speech/finish closures: zero ordinary generation, one analysis and one same-speaker closure, duplicate finish ignored, visible result survives audio failure');
})().catch(error=>{console.error(error);process.exitCode=1;});
