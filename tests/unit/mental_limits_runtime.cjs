/** Production lifecycle boundary tests; synthetic transcripts and mocked services. */
require('./ts_loader.js');
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const source=fs.readFileSync('apps/vehicle-app/src/utils/useMentalConversation.ts','utf8');
const ast=ts.createSourceFile('mental.ts',source,ts.ScriptTarget.Latest,true),functions={};
function walk(n){if(ts.isFunctionDeclaration(n)&&n.name)functions[n.name.text]=n.getText(ast);ts.forEachChild(n,walk);}walk(ast);
const code=ts.transpileModule(['send','finish','updateContext','speakClosing'].map(n=>functions[n]).join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
(async()=>{
 for(const scenario of ['39th-turn','39-turn-cross','100k-cross','94k-soft-close','withdrawn-consent']){
  const no=()=>{};
  const count=scenario==='39th-turn'?76:scenario==='39-turn-cross'?78:64;
  const size=['100k-cross','withdrawn-consent'].includes(scenario)?1500:scenario==='94k-soft-close'?1400:500;
  const rows=Array.from({length:count},(_,i)=>({id:'prior-'+i,turn:Math.floor(i/2)+1,sender:i%2?'AI':'USER',text:String(i).padEnd(size,'x'),time:'12:00',completed:true}));
  const r={structured:true,structuredState:{language:'en',speakerProfile:'female-calm-v1',listenOnly:false},mounted:true,active:true,epoch:1,audioEpoch:0,
           turn:scenario==='39th-turn'?38:scenario==='39-turn-cross'?39:32,id:'boundary',startedAt:'2026-10-27',transcript:[...rows],memory:[],memoryThrough:0,busy:false,failed:false};
  const input=['100k-cross','withdrawn-consent','94k-soft-close'].includes(scenario)?'final user statement '.padEnd(6000,'z'):'This is my final statement';
  let ordinary=0,analysis=0,neural=0,summary,phase,analysed;
  const settings={current:{parked:true,speechConsent:true,cloudConsent:true,voiceEnabled:true}};
  const deps={runtime:{current:r},settings,historyPermission:{current:false},Date,AbortController,setTimeout,clearTimeout,
   valid:e=>r.epoch===e&&r.active,abortRecognition:no,cleanup:no,stopAudio:no,timing:no,getLocale:()=> 'en-US',getLanguage:()=> 'en',t:v=>v,
   serviceAllowed:()=>settings.current.speechConsent,checkCrisisTrigger:()=>({isCrisis:false}),spokenText:v=>v,isDemoMode:()=>false,isMentalSummarySavingAllowed:()=>false,
   canonicalMentalTheme:v=>v,append:m=>r.transcript.push(m),setPhase:v=>phase=v,setNotice:no,setActive:no,setSummary:v=>summary=v,setVoiceState:no,setVoiceNotice:no,
   API:'fixture',speak:async()=>{r.busy=false;},pendingAudioPlay:{current:null},setAudioNeedsGesture:no,
   mentalNeuralSpeech:async(text,signal,current,onPlaying,audioReady,options)=>{neural++;assert(current());assert.equal(options.speakerProfile,'female-calm-v1');return true;},
   fetch:async(url,options)=>{
    const body=JSON.parse(options.body);
    if(url.endsWith('/converse')){ordinary++;assert.equal(body.finishAfterReply,true);return {ok:true,json:async()=>({providerType:'STRUCTURED_LOCAL',reply:'Prepared closing phrase.',sessionAction:'finish',audioAssetIds:['prepared-F01'],structuredState:r.structuredState})};}
    assert(url.endsWith('/analyze-session'));analysis++;analysed=body.messages;
    assert.deepEqual(analysed.slice(0,rows.length).map(m=>m.content),rows.map(m=>m.text));
    assert(analysed.some(m=>m.role==='user'&&m.content===input),'Final utterance must be included verbatim');
    assert(analysed.reduce((n,m)=>n+m.content.length,0)<=120000);
    if(scenario==='withdrawn-consent')settings.current.speechConsent=false;
    return {ok:true,json:async()=>({summaryText:'Complete boundary analysis.',themes:[],providerType:'LIVE_OPENAI',spokenSummary:'Closing summary.'})};
   }};
  const run=new Function(...Object.keys(deps),code+';return {send,finish};')(...Object.values(deps));
  await run.send(input);
  if(ordinary){assert(r.pendingFinish);await run.finish();}
  await run.finish();
  assert.equal(analysis,1);assert.equal(ordinary,['39th-turn','94k-soft-close'].includes(scenario)?1:0);
  assert.equal(neural,scenario==='withdrawn-consent'?0:1);
  assert.deepEqual(r.transcript.slice(0,rows.length),rows,'Earlier transcript must remain unchanged');
  if(scenario!=='withdrawn-consent'){assert(summary);assert.equal(phase,'completed');}else assert.equal(summary,undefined);
 }
 console.log('PASS actual lifecycle at 39-turn/100k boundaries: verbatim final input and earlier transcript preserved, soft closure, one analysis/closing, consent withdrawal gates late results');
})().catch(error=>{console.error(error);process.exitCode=1;});
