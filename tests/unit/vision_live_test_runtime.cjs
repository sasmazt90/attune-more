require('./ts_loader.js');
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const V=require('../../apps/vehicle-app/src/utils/spokenVision.ts');
const {VisionAnswerMemory}=require('../../apps/vehicle-app/src/utils/visionAnswerMemory.ts');
const {VisionFlow}=require('../../apps/vehicle-app/src/utils/visionFlow.ts');
const C=require('../../apps/vehicle-app/src/utils/visionCoverage.ts');
const {visionRecognitionChoice,VISION_ANSWER_SETTLE_MS}=require('../../apps/vehicle-app/src/utils/visionSpeechTurn.ts');
const matrix={tr:[],en:[],de:[]};
function check(language,text,expected,context={letter:'E'}){
 const actual=V.parseLetterAnswer(text,language,context);
 for(const [field,value] of Object.entries(expected))assert.deepEqual(actual[field],value,`${language}: ${text} -> ${JSON.stringify(actual)}`);
 matrix[language].push({text,expected,actual,pass:true});
}
for(const text of ['E','E harfi','Elma','Edirne','Bence E'])check('tr',text,{letter:'E',clarify:'orientation'});
for(const text of ['E sola dönük','E sol yana devrik','E sol yana devrilmiş','E sola devrik','E sola devrilmiş','E sola yatmış','E saat yönünün tersinde doksan derece','E doksan derece sola'])check('tr',text,{letter:'E',rotation:270,clarify:undefined});
for(const text of ['E sağa yatmış','E sağ yana devrilmiş','E saat yönünde 90 derece','E doksan derece sağa','E aşaa bakıyor','E aşağı dönük'])check('tr',text,{letter:'E',rotation:90,clarify:undefined});
for(const text of ['E düz','E normal','E standart','E doğru yönde'])check('tr',text,{letter:'E',rotation:0});
for(const text of ['E baş aşağı','E 180 derece dönmüş'])check('tr',text,{letter:'E',rotation:180});
for(const text of ['E aynalı','E ayna görüntüsü','E ayna yansıması','E simetrik'])check('tr',text,{letter:'E',mirrored:true});
check('tr','E hem baş aşağı hem aynalı',{letter:'E',rotation:180,mirrored:true});
check('tr','E dikey aynalı',{letter:'E',rotation:180,mirrored:true});
check('tr','E ama ters',{letter:'E',clarify:'reverse'});check('tr','E ters ve simetrik',{clarify:'reverse'});
check('tr','P değil E düz',{letter:'E',rotation:0});check('tr',"Pırasanın P'si sola yatmış",{letter:'P',rotation:270});
check('tr','E değil',{letter:undefined,clarify:'letter'});check('tr','patates düz',{letter:undefined,clarify:'letter'});
check('tr','E yukarı bakıyor',{rotation:270});check('tr','F aşağı bakıyor',{clarify:'orientation'},{letter:'F'});
for(const text of ['E','ee','Echo','elephant','I think the letter is E'])check('en',text,{letter:'E',clarify:'orientation'});
for(const text of ['E turned right','E tilted to the right','E ninety degrees clockwise','E clockwise 90 degrees'])check('en',text,{letter:'E',rotation:90});
for(const text of ['E counterclockwise ninety degrees','E anticlockwise','E ninety degrees counterclockwise','E leaning left'])check('en',text,{letter:'E',rotation:270});
for(const text of ['E upside down','E one hundred and eighty degrees clockwise','E half a turn'])check('en',text,{letter:'E',rotation:180});
for(const text of ['E mirrored','E mirror image','E horizontally reflected','E flipped horizontally'])check('en',text,{letter:'E',mirrored:true});
check('en','E vertically mirrored',{letter:'E',rotation:180,mirrored:true});check('en','E upside down and mirrored',{letter:'E',rotation:180,mirrored:true});
check('en','E not mirrored upright',{letter:'E',rotation:0,mirrored:false});check('en','P no E upright',{letter:'E',rotation:0});
check('en','E facing down',{rotation:90});check('en','E pointing up',{rotation:270});
check('en','E as in elephant upright',{letter:'E',rotation:0});check('en','E as in banana upright',{clarify:'letter'});
check('en','E reverse',{clarify:'reverse'});check('en','not E',{letter:undefined,clarify:'letter'});check('en','engineering upright',{letter:undefined,clarify:'letter'});
for(const text of ['E','eh','Emil','Essen','Elefant','ich denke der Buchstabe ist E'])check('de',text,{letter:'E',clarify:'orientation'});
for(const text of ['E nach rechts','E im Uhrzeigersinn neunzig Grad','E neunzig Grad im Uhrzeigersinn'])check('de',text,{letter:'E',rotation:90});
for(const text of ['E nach links','E gegen den Uhrzeigersinn neunzig Grad','E neunzig Grad gegen den Uhrzeigersinn'])check('de',text,{letter:'E',rotation:270});
for(const text of ['E auf dem Kopf','E kopfüber','E um hundertachtzig Grad gedreht'])check('de',text,{letter:'E',rotation:180});
for(const text of ['E gespiegelt','E spiegelverkehrt','E Spiegelbild'])check('de',text,{letter:'E',mirrored:true});
check('de','E vertikal gespiegelt',{letter:'E',rotation:180,mirrored:true});check('de','E kopfüber und gespiegelt',{rotation:180,mirrored:true});
check('de','E nicht gespiegelt aufrecht',{rotation:0,mirrored:false});check('de','P nein E aufrecht',{letter:'E',rotation:0});
check('de','nicht P sondern E aufrecht',{letter:'E',rotation:0});check('de','E wie Elefant aufrecht',{letter:'E',rotation:0});
check('de','E wie Banane aufrecht',{clarify:'letter'});check('de','E zeigt nach unten',{rotation:90});check('de','E schaut nach oben',{rotation:270});
check('de','E umgekehrt',{clarify:'reverse'});check('de','Äpfel aufrecht',{letter:undefined,clarify:'letter'});check('de','Straße aufrecht',{letter:undefined,clarify:'letter'});
// Wrong directions/letters remain wrong after interpretation. Exercise actual D4 geometry.
for(const language of ['tr','en','de']){
 const text={tr:'F sola yatmış',en:'F counterclockwise',de:'F nach links'}[language],answer=V.parseLetterAnswer(text,language,{letter:'E'});
 const score=V.scoreLetterTrial({valid:true,letter:'E',orientation:'right',transform:V.legacyTransform('right'),answer:{letter:answer.letter,transform:V.answerTransform(answer)},notVisible:false});
 assert.equal(score.letterCorrect,false);assert.equal(score.orientationCorrect,false);
}
for(const letter of Object.keys(V.LETTER_PATHS))for(const rotation of [0,90,180,270])for(const mirrored of [false,true]){
 const transform={rotation,mirrored,mirrorAxis:'x',order:'mirror-then-rotate'};
 assert(V.equivalentTransform(letter,transform,transform));
 if(letter!=='A'&&letter!=='E')assert(!V.equivalentTransform(letter,transform,{...transform,mirrored:!mirrored}));
}
assert.equal(visionRecognitionChoice([{transcript:'E right',confidence:.9},{transcript:'E left',confidence:.87}],'en',{letter:'E'}).confidence,.3);
assert.equal(visionRecognitionChoice([{transcript:'E right',confidence:.9},{transcript:'Echo clockwise',confidence:.87}],'en',{letter:'E'}).confidence,.9);
// Both anatomical eyes: confirmation never overrides camera/face/open-eye failures.
let coverageChecks=0;for(const eye of ['RIGHT','LEFT']){
 const open={state:'open',ear:.3,method:'fixture'},uncertain={...open,state:'uncertain'};
 const c={observedAt:1000,cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,distancePolicy:'head-anchors-hysteresis-v1',distanceState:'stable',right:eye==='RIGHT'?open:uncertain,left:eye==='LEFT'?open:uncertain};
 for(const kind of ['closed','hand','object']){
  const confirmation={testEye:eye,coveredEye:eye==='RIGHT'?'LEFT':'RIGHT',kind,confirmedAt:1000,source:'user-confirmed'};
  const effective=C.withCoverageConfirmation(c,eye,confirmation,1100);
  assert.equal(V.letterConditionFailure(effective,eye,1100),null);assert.equal((eye==='RIGHT'?effective.left:effective.right).state,'uncertain');coverageChecks++;
  for(const change of [{cameraLive:false},{faceCount:0},{qualityValid:false},{positionValid:false},{relativeScaleChange:null},{observedAt:0},{[eye==='RIGHT'?'right':'left']:{state:'closed'}},{[eye==='RIGHT'?'left':'right']:{state:'open'}}]){
   const invalid=C.withCoverageConfirmation({...c,...change},eye,confirmation,1100);assert(V.letterConditionFailure(invalid,eye,1100));assert(!invalid.coverageConfirmation);coverageChecks++;
  }
  assert(!C.withCoverageConfirmation(c,eye==='RIGHT'?'LEFT':'RIGHT',confirmation,1100).coverageConfirmation);coverageChecks++;
  assert(!C.withCoverageConfirmation({...c,observedAt:62000},eye,confirmation,62000).coverageConfirmation);coverageChecks++;
 }
 assert.equal(C.eyeObservation({...c,right:{state:'covered',occlusionKind:'hand'}},'RIGHT',1100),'EYE_COVERED_BY_HAND');
 assert.equal(C.eyeObservation({...c,left:{state:'covered',occlusionKind:'object'}},'LEFT',1100),'EYE_OCCLUDED_BY_OBJECT');
}
// Execute production receive/current with virtual time: no tests reimplement scoring.
const source=ts.createSourceFile('page.tsx',fs.readFileSync('apps/vehicle-app/src/app/vision/SpokenLetterPage.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),functions=[];
function visit(n){if(ts.isFunctionDeclaration(n)&&['receive','current'].includes(n.name?.text))functions.push(n.getText(source));ts.forEachChild(n,visit);}visit(source);
const compiled=ts.transpileModule(functions.join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
function harness(){
 let now=1000,next=0,permitted=true,problem=null;const timers=new Map(),session=new V.SpokenLetterSession();session.present(now);session.letter='F';session.transform=V.legacyTransform('right');session.orientation='right';
 const flow={current:new VisionFlow()};flow.current.start(session.id);flow.current.presentationId=session.presentationId;flow.current.transition('listening');flow.current.setConditions(true);
 const memory=new VisionAnswerMemory();memory.bind({sessionId:session.id,eye:session.eye,targetId:session.trialId});
 const c={observedAt:now,cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,right:{state:'open'},left:{state:'closed'}};
 const r={current:{session,mounted:true,active:true,epoch:1,inputMode:'speech',answerMemory:memory,evidence:{conditions:c},answerTimer:null,settleAnswer:null,listeningStarted:true,clarified:new Set(),speechActive:false}};
 const geometry=()=>({viewportWidthCssPx:120,viewportHeightCssPx:120,pathWidthCssPx:80,pathHeightCssPx:80,strokeWidthCssPx:10,measuredAt:now,method:'dom-svg-css-pixels'});
 const deps={r,flow,parked:{current:true},getLanguage:()=> 'en',serviceAllowed:()=>permitted,isCameraAllowed:()=>permitted,isMicrophoneAllowed:()=>permitted,parseLetterAnswer:V.parseLetterAnswer,
 complete:()=>{},pause:()=>{},resume:()=>{},refresh:()=>{},failure:()=>problem,measureSymbol:geometry,setAnswerNotice:()=>{},answerDescription:V.describeAnswer,inspect:()=>{},prompt:()=>{},stopSpeech:()=>{},setVoice:()=>{},answerTransform:V.answerTransform,
 respondToVisibleLetter:(s,a,c,id,m)=>V.respondToVisibleLetter(s,a,c,id,m,()=>now),stopVoice:()=>{},stage:next=>flow.current.transition(next),VISION_ANSWER_SETTLE_MS,setTimeout:(fn,ms)=>{timers.set(++next,{fn,at:now+ms});return next;},clearTimeout:id=>timers.delete(id),sessionStorage:{getItem:()=>null}};
 const receive=new Function(...Object.keys(deps),compiled+'\nreturn receive;')(...Object.values(deps));
 return {session,r,flow,memory,receive:(text,key=crypto.randomUUID(),confidence=.9)=>receive(text,confidence,session.presentationId,key),advance(ms){now+=ms;c.observedAt=now;for(const [id,t]of [...timers])if(t.at<=now){timers.delete(id);t.fn();}},deny(){permitted=false;},fault(){problem='eye';},next(){flow.current.presentationId='changed';flow.current.transition('rendering');},buttons(answer){receive('',1,session.presentationId,crypto.randomUUID(),answer);}};
}
let h=harness();h.receive('P right');assert.equal(h.session.trials.length,0);h.advance(400);h.receive('P no F');h.advance(749);assert.equal(h.session.trials.length,0);h.advance(1);assert.equal(h.session.trials.length,1);assert(h.session.trials[0].combinedCorrect);
h=harness();h.receive('F right','same');h.advance(500);h.receive('F right','same');h.advance(250);assert.equal(h.session.trials.length,1);
for(const action of ['deny','fault','next']){h=harness();h.receive('F right');h[action]();h.advance(800);assert.equal(h.session.trials.length,0,action);}
h=harness();h.receive('F right');h.r.current.speechActive=true;h.advance(800);assert.equal(h.session.trials.length,0);h.r.current.speechActive=false;h.receive('F left');h.advance(800);assert.equal(h.session.trials.length,1);assert.equal(h.session.trials[0].orientationCorrect,false);
h=harness();h.receive('F',undefined,.3);h.receive('right');h.advance(800);assert.equal(h.session.trials.length,0);h.receive('F');h.advance(800);assert.equal(h.session.trials.length,1);
h=harness();h.buttons({letter:'F',rotation:90,mirrored:false});assert.equal(h.session.trials.length,1);assert.equal(h.session.trials[0].inputMethod,'buttons');
const output={kind:'deterministic transcript, coverage and production-controller tests; no physical ASR/camera claim',languages:Object.fromEntries(Object.entries(matrix).map(([l,v])=>[l,{passed:v.length,cases:v}])),coverageChecks,controller:'passed',transformMatrix:'6 letters x 8 transforms passed'};
if(process.env.VISION_EVIDENCE_PATH)fs.writeFileSync(process.env.VISION_EVIDENCE_PATH,JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({languages:Object.fromEntries(Object.entries(matrix).map(([l,v])=>[l,v.length])),coverageChecks,controller:'PASS',transformMatrix:'PASS'}));
