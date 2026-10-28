// Execute production controller functions with virtual time and explicit Audio/ASR adapters.
// Real native media and browser UI are checked separately by vision_conversation.py.
require('./ts_loader.js');const ts=require('typescript'),fs=require('fs'),assert=require('assert/strict');
const V=require('../../apps/vehicle-app/src/utils/spokenVision.ts'),{VisionAnswerMemory}=require('../../apps/vehicle-app/src/utils/visionAnswerMemory.ts'),{VisionFlow}=require('../../apps/vehicle-app/src/utils/visionFlow.ts');
const {visionRecognitionChoice,visionRecognitionConfidence,VISION_ANSWER_SETTLE_MS}=require('../../apps/vehicle-app/src/utils/visionSpeechTurn.ts');
const src=ts.createSourceFile('page.tsx',fs.readFileSync('apps/vehicle-app/src/app/vision/SpokenLetterPage.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),functions=[];
const names=['prompt','receive','listen','silence','scheduleListening','followUpCode','speak','current','abortRecognition','stopVoice','stopSpeech'];
function visit(n){if(ts.isFunctionDeclaration(n)&&names.includes(n.name?.text))functions.push(n.getText(src));ts.forEachChild(n,visit);}visit(src);assert.equal(functions.length,names.length);
const compiled=ts.transpileModule(functions.join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
const flush=async()=>{await Promise.resolve();await Promise.resolve();};
function harness(language='tr',rotation=90){
 let now=1000,timerId=0,voice='',fault=null;const timers=new Map(),records=[],audios=[],recognizers=[],events=[];
 const session=new V.SpokenLetterSession();session.present(now);session.letter='E';session.transform=V.legacyTransform(({0:'upright',90:'right',180:'down',270:'left'})[rotation]);session.orientation=({0:'upright',90:'right',180:'down',270:'left'})[rotation];
 const memory=new VisionAnswerMemory();memory.bind({sessionId:session.id,eye:session.eye,targetId:session.trialId});
 const flow={current:new VisionFlow()};flow.current.start(session.id);flow.current.instructionEye='RIGHT';flow.current.presentationId=session.presentationId;flow.current.transition('rendering');flow.current.setConditions(true);
 const conditions={observedAt:now,cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,right:{state:'open'},left:{state:'closed'}};
 const r={current:{mounted:true,active:true,epoch:1,session,evidence:{conditions},answerMemory:memory,recognition:null,restart:null,controller:null,audio:null,answerTimer:null,settleAnswer:null,voiceGeneration:0,voiceTimeout:null,prompted:new Set(),silenceReminders:new Set(),mainInstructionGiven:false,pendingPrompt:null,recognitionFailures:0,speechActive:false}};
 const a=r.current,actions={current:{}},window={};
 class Recognition{
  constructor(){recognizers.push(this);}
  start(){assert.equal(a.controller,null,'Microphone started with an output controller');assert(audios.every(x=>x.paused),'Microphone overlapped output');this.onstart?.();}
  abort(){this.aborted=true;this.onend?.();}
  emit(text,confidence=.9){this.onresult?.({resultIndex:0,results:[Object.assign([{transcript:text,confidence}],{isFinal:true})]});}
 }
 window.SpeechRecognition=Recognition;
 class Audio{constructor(){this.dataset={};this.paused=true;audios.push(this);}pause(){this.paused=true;}load(){}removeAttribute(){}}
 const geometry=()=>({viewportWidthCssPx:120,viewportHeightCssPx:120,pathWidthCssPx:80,pathHeightCssPx:80,strokeWidthCssPx:10,measuredAt:now,method:'dom-svg-css-pixels'});
 const deps={r,flow,actions,window,document:{hidden:false},parked:{current:true},getLanguage:()=>language,getLocale:()=>({tr:'tr-TR',en:'en-US',de:'de-DE'})[language],serviceAllowed:()=>true,isCameraAllowed:()=>true,isMicrophoneAllowed:()=>true,speechMuted:()=>false,
 inspect:()=>{},stage:next=>flow.current.transition(next),refresh:()=>{},setVoice:v=>voice=v,setError:message=>assert.fail(message),setAnswerNotice:()=>{},timing:s=>events.push(s),failure:()=>fault,measureSymbol:geometry,
 approvedClip:(_l,_m,code)=>({recordingId:code}),Audio,AbortController,URL,performance:{now:()=>now},canvas:{current:null},
 playFixedSpeech:(audio,clip,signal,current,observe)=>new Promise(resolve=>{assert.equal(a.recognition,null,'Output started with an active microphone');audio.paused=false;observe('playing');const rec={code:clip.recordingId.split(':')[1],audio,finish:()=>{audio.paused=true;observe('ended');resolve(current());}};records.push(rec);signal.addEventListener('abort',()=>{audio.paused=true;resolve(false);},{once:true});}),
 parseLetterAnswer:V.parseLetterAnswer,isLetterInstructionEcho:V.isLetterInstructionEcho,visionRecognitionChoice,visionRecognitionConfidence,VISION_ANSWER_SETTLE_MS,answerTransform:V.answerTransform,answerDescription:V.describeAnswer,
 respondToVisibleLetter:(s,p,c,id,measure)=>V.respondToVisibleLetter(s,p,c,id,measure,()=>now),sessionStorage:{getItem:()=>null},setTimeout:(fn,ms)=>{timers.set(++timerId,{fn,at:now+ms});return timerId;},clearTimeout:id=>timers.delete(id),complete:()=>{},pause:()=>{},resume:()=>{},recognitionFailure:()=>assert.fail('Unexpected recognition failure')};
 const controller=new Function(...Object.keys(deps),compiled+'\nreturn {prompt,receive,listen,silence,stopVoice};')(...Object.values(deps));Object.assign(actions.current,controller,{inspect:()=>{}});
 const advance=async ms=>{now+=ms;conditions.observedAt=now;for(const [id,t]of [...timers])if(t.at<=now){timers.delete(id);t.fn();}await flush();};
 return {r,flow,session,memory,records,recognizers,events,controller,advance,async listenAfterOutput(){records.at(-1).finish();await flush();assert.equal(a.recognition,null);await advance(349);assert.equal(a.recognition,null);await advance(1);assert(a.recognition);},emit:(text,c=.9)=>a.recognition.emit(text,c),last:()=>records.at(-1)?.code,async start(){controller.prompt();assert.equal(flow.current.stage,'prompting');controller.listen();assert.equal(recognizers.length,0);await this.listenAfterOutput();},async answer(text,c=.9){this.emit(text,c);await advance(350);},async finish(text){this.emit(text);await advance(VISION_ANSWER_SETTLE_MS);assert.equal(session.trials.length,1);assert(session.trials[0].combinedCorrect);},fault(v){fault=v;}};
}
(async()=>{
 const results={};for(const language of ['tr','en','de']){
  const letter={tr:'Edirne',en:'Echo',de:'Emil'}[language],direction={tr:'saat yönünde doksan derece',en:'clockwise ninety degrees',de:'im Uhrzeigersinn neunzig Grad'}[language],both=letter+' '+direction;let h;
  h=harness(language);await h.start();await h.answer(letter);assert.equal(h.last(),'orientation');assert.equal(h.memory.answer.letter,'E');assert.equal(h.session.trials.length,0);await h.listenAfterOutput();await h.finish(direction);
  h=harness(language,180);await h.start();await h.answer(letter);await h.listenAfterOutput();await h.finish(({tr:'baş aşağı',en:'upside down',de:'auf dem Kopf'})[language]);
  h=harness(language);await h.start();await h.answer(direction);assert.equal(h.last(),'letter');assert.equal(h.memory.answer.rotation,90);await h.listenAfterOutput();await h.finish(letter);
  h=harness(language);await h.start();await h.finish(both);assert.equal(h.records.length,1);
  h=harness(language);await h.start();await h.answer('blablabla');assert.equal(h.last(),'repeat');assert.equal(h.session.trials.length,0);await h.listenAfterOutput();await h.finish(both);
  h=harness(language);await h.start();await h.answer(letter);await h.listenAfterOutput();await h.answer('blablabla');assert.equal(h.memory.answer.letter,'E');assert.equal(h.last(),'orientation');await h.listenAfterOutput();await h.finish(direction);
  h=harness(language);await h.start();await h.answer(letter,.3);await h.listenAfterOutput();await h.answer(direction);assert.equal(h.last(),'letter');assert.equal(h.memory.confidence.letter,.3);assert.equal(h.memory.confidence.orientation,.9);await h.listenAfterOutput();await h.finish(letter);
  h=harness(language);await h.start();await h.answer(direction,.3);await h.listenAfterOutput();await h.answer(letter);assert.equal(h.last(),'orientation');assert.equal(h.memory.confidence.letter,.9);assert.equal(h.memory.confidence.orientation,.3);await h.listenAfterOutput();await h.finish(direction);
  h=harness(language);await h.start();await h.answer(({tr:'E veya F ',en:'E or F ',de:'E oder F '})[language]+direction);assert.equal(h.last(),'letter');assert.equal(h.memory.answer.rotation,90);await h.listenAfterOutput();await h.finish(letter);
  h=harness(language);await h.start();await h.answer(letter+' '+({tr:'sağa sola',en:'right left',de:'rechts links'})[language]);assert.equal(h.last(),'orientation');assert.equal(h.memory.answer.letter,'E');await h.listenAfterOutput();await h.finish(direction);
  h=harness(language);await h.start();await h.answer('B');await h.listenAfterOutput();await h.answer(({tr:'B değil E',en:'B no E',de:'B nein E'})[language]);assert.equal(h.memory.answer.letter,'E');assert.equal(h.last(),'orientation');await h.listenAfterOutput();await h.finish(direction);
  h=harness(language,270);await h.start();await h.answer(direction);await h.listenAfterOutput();await h.answer(({tr:'sağa değil sola',en:'right no left',de:'rechts nein links'})[language]);assert.equal(h.memory.answer.rotation,270);assert.equal(h.last(),'letter');await h.listenAfterOutput();await h.finish(letter);
  h=harness(language);await h.start();const old=h.r.current.recognition;old.onerror({error:'no-speech'});old.onend();assert.equal(h.last(),'repeat');await h.listenAfterOutput();const count=h.records.length;const silent=h.r.current.recognition;silent.onerror({error:'no-speech'});await h.advance(350);assert.equal(h.records.length,count);assert(h.r.current.recognition);await h.finish(both);
  h=harness(language);await h.start();const stale=h.r.current.recognition;await h.answer(letter);stale.emit(direction);assert.equal(h.memory.answer.rotation,undefined);h.controller.stopVoice();h.flow.current.transition('user-paused');h.records.at(-1).finish();await flush();await h.advance(1000);assert.equal(h.r.current.recognition,null);assert.equal(h.session.trials.length,0);
  h=harness(language);await h.start();const rec=h.r.current.recognition;const segments=[Object.assign([{transcript:letter,confidence:.3}],{isFinal:true}),Object.assign([{transcript:direction,confidence:.95}],{isFinal:true})];rec.onresult({resultIndex:0,results:segments});await h.advance(350);assert.equal(h.last(),'letter');assert.equal(h.memory.confidence.letter,.3);assert.equal(h.memory.confidence.orientation,.95);await h.listenAfterOutput();await h.finish(letter);
  results[language]={status:'PASS',scenarios:15,scope:'production controller with virtual Audio/ASR/time; not physical media validation'};
 }
 console.log(JSON.stringify(results));
})().catch(error=>{console.error(error);process.exitCode=1;});
