/** Real sendHybrid + race + neural preparation; only network/media/clock are fixtures. */
require('./ts_loader.js');
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const stub=(name,exports)=>{const id=require.resolve(name);require.cache[id]={id,filename:id,loaded:true,exports};};
global.window=new EventTarget();global.document=new EventTarget();document.hidden=false;
global.localStorage={getItem:()=>null};
stub('../../apps/vehicle-app/src/i18n/core.ts',{getLanguage:()=> 'tr',getLocale:()=> 'tr-TR',VOICE_EVENT:'voice'});
stub('../../apps/vehicle-app/src/i18n/locks.ts',{captureWhileLocked:f=>f,languageSwitchLocked:()=>false});
stub('../../apps/vehicle-app/src/utils/playbackMeter.ts',{speechMuted:()=>false});
const {prepareMentalNeuralSpeech}=require('../../apps/vehicle-app/src/utils/mentalNeuralSpeech.ts');
const {chooseHybridTurn}=require('../../apps/vehicle-app/src/utils/mentalHybridRace.ts');
const source=fs.readFileSync('apps/vehicle-app/src/utils/useMentalConversation.ts','utf8');
const ast=ts.createSourceFile('hook.ts',source,ts.ScriptTarget.Latest,true);let hook;
(function visit(n){if(ts.isFunctionDeclaration(n)&&n.name?.text==='sendHybrid')hook=n.getText(ast);ts.forEachChild(n,visit);})(ast);
assert(hook);const code=ts.transpileModule(hook,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
const flush=async()=>{for(let i=0;i<50;i++)await Promise.resolve();};
(async()=>{
 for(const status of [401,403,409,503,'timeout']){
  const refusal=[401,403,409].includes(status),user={id:'user',turn:1,sender:'USER',text:'Yorgunum.',completed:false};
  const r={id:'session',mounted:true,active:true,epoch:1,audioEpoch:0,turn:1,busy:true,transcript:[user],memory:[],structuredState:{language:'tr',speakerProfile:'female-calm-v1',turn:0,asked:[]}};
  const before=structuredClone({transcript:r.transcript,state:r.structuredState,memory:r.memory});
  const settings={current:{parked:true,voiceEnabled:true,cloudConsent:true}}; // Deliberately stale client park state.
  let plays=0,neuralRequests=0,headerReads=0,preparedReady=false,rootSignal,neuralSignal,preparedSignal,now=0,id=0;
  const stages=[],jobs=new Map(),clock={now:()=>now,set:(fn,ms)=>{jobs.set(++id,{at:now+ms,fn});return id;},clear:k=>jobs.delete(k)};
  const advance=async at=>{now=at;for(const[k,j]of [...jobs])if(j.at<=now){jobs.delete(k);j.fn();}await flush();};
  const fetch=async(url,options)=>{
   if(url==='/api/mental-neural-speech'){
    neuralRequests++;neuralSignal=options.signal;
    if(status==='timeout')return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true}));
    // Refusals have no voice/profile/audio headers. Status must be handled first.
    return {status,ok:false,headers:{get:()=>{headerReads++;return null;}}};
   }
   assert.equal(url,'mock/converse');const personal=JSON.parse(options.body).engine==='hybrid-personal-v1';
   return {status:200,ok:true,json:async()=>({reply:personal?'personal':'prepared',providerType:personal?'LIVE_OPENAI':'STRUCTURED_LOCAL',audioAssetIds:['a','b'],structuredState:{...r.structuredState,turn:1,asked:['B01']}})};
  };
  global.fetch=fetch;const no=()=>{};
  const deps={runtime:{current:r},settings,document,localStorage,Date,AbortController,fetch,API:'mock',getLanguage:()=> 'tr',getLocale:()=> 'tr-TR',mentalSpeechEngine:()=> 'chatterbox-v3',speechMuted:()=>false,valid:()=>true,
   stopAudio:()=>{r.audioEpoch++;r.streamCancel?.();},pendingAudioPlay:{current:null},setAudioNeedsGesture:no,setVoiceState:no,setPhase:no,setMessages:no,timing:s=>stages.push(s),spokenText:x=>x,
   append:m=>r.transcript.push(m),resume:()=>{r.busy=false;},cancel:()=>assert.fail('normal unavailable/cancellation must not report failure'),
   prepareMentalNeuralSpeech,
   prepareMentalRecording:async(text,ids,signal)=>{preparedSignal=signal;preparedReady=true;return {play:async()=>{assert(!signal.aborted);plays++;return true;}};},
   chooseHybridTurn:opts=>{rootSignal=opts.signal;return chooseHybridTurn({...opts,clock});}
  };
  const sendHybrid=new Function(...Object.keys(deps),code+';return sendHybrid;')(...Object.values(deps));
  const pending=sendHybrid(user,1,0);await flush();assert(preparedReady);assert.equal(neuralRequests,1);
  if(status==='timeout'){assert.equal(plays,0);await advance(2999);assert.equal(plays,0);await advance(3000);}
  await pending;await advance(4000);
  assert(settings.current.parked);assert(rootSignal.aborted&&preparedSignal.aborted&&neuralSignal.aborted,'both candidates must stop');
  if(refusal){
   assert.equal(plays,0,`${status}: prepared playback must not start`);assert.equal(headerReads,0,'safety status must precede every header check');
   assert.deepEqual({transcript:r.transcript,state:r.structuredState,memory:r.memory},before,'no history/question state advancement');
   assert(!stages.some(s=>s.startsWith('hybrid-selected-')));assert(r.paused);
  }else{assert.equal(plays,1);assert.equal(r.structuredState.turn,1);assert.equal(r.transcript.at(-1).text,'prepared');assert.equal(stages.filter(s=>s==='hybrid-selected-prepared').length,1);}
  assert.equal(jobs.size,0);console.log(`PASS real hybrid neural ${status}: ${refusal?'both arms cancelled; no playback/history/state change':'prepared succeeds'}`);
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
