// Production parser and answer memory; transcripts are fixtures, never live capture.
require('./ts_loader.js');
const assert=require('assert/strict');
const V=require('../../apps/vehicle-app/src/utils/spokenVision.ts');
const {VisionAnswerMemory}=require('../../apps/vehicle-app/src/utils/visionAnswerMemory.ts');
const C=require('../../apps/vehicle-app/src/i18n/core.ts');
const catalog=require('../../shared/localization/messages.json');
const cases=[
 ['en','finish right','F',90],['en','right finish','F',90],['en','finish','F',undefined],
 ['en','repeat left','R',270],['en','pause upright','P',0],['en','resume upside down','R',180],
 ['de','fertig rechts','F',90],['de','rechts fertig','F',90],['de','fertig','F',undefined],
 ['de','beenden aufrecht','B',0],['de','beenden','B',undefined],['de','fortsetzen links','F',270],
 ['de','pausieren kopfüber','P',180],['tr','F sağa','F',90],['tr','Rize baş aşağı','R',180]
];
for(const [language,text,letter,rotation] of cases){
 const answer=V.parseLetterAnswer(text,language);
 assert.equal(answer.command,undefined,text);assert.equal(answer.letter,letter,text);
 assert.equal(answer.rotation,rotation,text);assert.equal(answer.clarify,rotation===undefined?'orientation':undefined,text);
}
for(const [language,phrases] of Object.entries({
 en:{finish:['finish the test','stop the test',' Finish the test! '],pause:['pause'],resume:['resume','continue'],repeat:['repeat'],'not-visible':["I can't see it",'not visible']},
 de:{finish:['Test beenden','den Test beenden',' Test beenden! '],pause:['pausieren','pause'],resume:['fortsetzen','weiter'],repeat:['wiederholen'],'not-visible':['ich sehe es nicht','nicht erkennbar']},
 tr:{finish:['bitir','testi bitir'],pause:['duraklat'],resume:['devam et'],repeat:['tekrar'],'not-visible':['göremiyorum']}
}))for(const [command,texts] of Object.entries(phrases))for(const text of texts)assert.deepEqual(V.parseLetterAnswer(text,language),{command},text);
// Complete command phrases embedded in an answer cannot end/pause a session.
for(const [language,text] of [['en','finish the test right'],['en','finish F right'],['en','finisher right'],['de','Test beenden rechts'],['de','fertig E aufrecht']]){
 const answer=V.parseLetterAnswer(text,language);assert.equal(answer.command,undefined,text);
 if(text.includes('test')||text.includes('Test'))assert(answer.clarify,text);
}
assert.equal(V.parseLetterAnswer('finish finish right','en').letter,'F');
assert.equal(V.parseLetterAnswer('finish or repeat right','en').clarify,'letter');
assert.equal(V.parseLetterAnswer('fertig oder beenden rechts','de').clarify,'letter');
assert.equal(V.parseLetterAnswer('finish right left','en').clarify,'orientation');
assert.equal(V.parseLetterAnswer('bee no finish right','en').letter,'F');
assert.equal(V.parseLetterAnswer('beh nein fertig rechts','de').letter,'F');
// A fragment remains an F answer awaiting orientation, never a cancellation.
const memory=new VisionAnswerMemory(),target={sessionId:'synthetic',eye:'RIGHT',targetId:'one'};
memory.bind(target);memory.append(target,'one','finish',V.parseLetterAnswer('finish','en'),.9);
assert.equal(memory.answer.letter,'F');assert.equal(memory.missing,'orientation');
memory.append(target,'two','right',V.parseLetterAnswer('right','en'),.9);
assert.equal(memory.missing,null);assert.equal(memory.answer.letter,'F');assert.equal(memory.answer.rotation,90);
// Locale changes select the current grammar without changing health/consent bytes.
const values=new Map([['health','unchanged'],['consent','unchanged']]);
global.window=new EventTarget();global.localStorage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,String(v))};
for(const language of ['tr','en','de','en','tr']){
 C.setLanguage(language);const text={tr:'F sağa',en:'finish right',de:'fertig rechts'}[language];
 assert.equal(V.parseLetterAnswer(text,C.getLanguage()).letter,'F');assert.equal(values.get('health'),'unchanged');assert.equal(values.get('consent'),'unchanged');
}
assert.equal(V.parseLetterAnswer('finish right','de').rotation,undefined);
assert.equal(V.parseLetterAnswer('fertig rechts','en').rotation,undefined);
const instructions=Object.values(catalog).find(row=>row.tr.includes('“Tekrar”, “göremiyorum”'));
assert(instructions.en.includes('finish the test'));assert(instructions.de.includes('Test beenden'));
// Execute the component's actual receive/current functions with synthetic frame
// geometry, admission flags and scheduling. Real scoring/memory are retained.
const fs=require('fs'),ts=require('typescript');
const source=ts.createSourceFile('page.tsx',fs.readFileSync('apps/vehicle-app/src/app/vision/SpokenLetterPage.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
const functions=[];function visit(node){if(ts.isFunctionDeclaration(node)&&['receive','current'].includes(node.name?.text))functions.push(node.getText(source));ts.forEachChild(node,visit);}visit(source);assert.equal(functions.length,2);
const compiled=ts.transpileModule(functions.join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
const {VisionFlow}=require('../../apps/vehicle-app/src/utils/visionFlow.ts');
function receiver(language){
 C.setLanguage(language);const session=new V.SpokenLetterSession();session.present();session.letter='F';session.transform=V.legacyTransform('right');session.orientation='right';
 const flow={current:new VisionFlow()};flow.current.start(session.id);flow.current.presentationId=session.presentationId;flow.current.transition('listening');flow.current.setConditions(true);
 const memory=new VisionAnswerMemory();memory.bind({sessionId:session.id,eye:session.eye,targetId:session.trialId});
 const eye={state:'open',ear:.3,method:'synthetic'},closed={...eye,state:'closed'};
 const conditions={observedAt:performance.now(),cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,right:eye,left:closed};
 const r={current:{session,mounted:true,active:true,epoch:1,answerMemory:memory,evidence:{conditions},answerTimer:null,settleAnswer:null,listeningStarted:true}},parked={current:true};
 let permitted=true,cancellations=0,pauses=0,resumes=0;
 const deps={r,flow,parked,getLanguage:C.getLanguage,serviceAllowed:()=>permitted,isCameraAllowed:()=>permitted,isMicrophoneAllowed:()=>permitted,parseLetterAnswer:V.parseLetterAnswer,
  complete:cancelled=>{assert.equal(cancelled,true);cancellations++;},pause:()=>pauses++,resume:()=>resumes++,
  refresh:()=>{},failure:()=>null,measureSymbol:()=>({viewportWidthCssPx:session.sizePx,viewportHeightCssPx:session.sizePx,pathWidthCssPx:session.sizePx*.8,pathHeightCssPx:session.sizePx*.8,strokeWidthCssPx:session.sizePx*.1,measuredAt:performance.now(),method:'dom-svg-css-pixels'}),
  setAnswerNotice:()=>{},answerDescription:V.describeAnswer,inspect:()=>{},prompt:()=>{},stopSpeech:()=>{},setVoice:()=>{},answerTransform:V.answerTransform,respondToVisibleLetter:V.respondToVisibleLetter,stopVoice:()=>{},
  stage:next=>flow.current.transition(next),setTimeout:()=>1,clearTimeout:()=>{},sessionStorage:{getItem:()=>null}};
 const receive=new Function(...Object.keys(deps),compiled+'\nreturn receive;')(...Object.values(deps));
 return {session,flow,memory,parked,deny:()=>{permitted=false;},receive:text=>receive(text,.9,session.presentationId,crypto.randomUUID()),counts:()=>[cancellations,pauses,resumes]};
}
for(const [language,word,direction,finish] of [['tr','F','sağa','testi bitir'],['en','finish','right','finish the test'],['de','fertig','rechts','Test beenden']]){
 let a=receiver(language);a.receive(word);assert.equal(a.session.trials.length,0);assert.equal(a.memory.answer.letter,'F');assert.equal(a.memory.missing,'orientation');assert.deepEqual(a.counts(),[0,0,0]);
 a.receive(direction);assert.equal(a.session.trials.length,1);assert(a.session.trials[0].letterCorrect);assert(a.session.trials[0].combinedCorrect);assert.deepEqual(a.counts(),[0,0,0]);
 a=receiver(language);const before=JSON.stringify(a.session);a.receive(finish);assert.deepEqual(a.counts(),[1,0,0]);assert.equal(JSON.stringify(a.session),before);
 for(const gate of ['consent','motion']){a=receiver(language);if(gate==='consent')a.deny();else a.parked.current=false;const saved=JSON.stringify(a.session);a.receive(word+' '+direction);assert.equal(JSON.stringify(a.session),saved);assert.equal(a.memory.fragmentCount,0);a.receive(finish);assert.deepEqual(a.counts(),[0,0,0]);}
}
console.log('PASS multilingual code words, whole-utterance controls, ambiguity, fragment retention, current-locale grammar and advertised finish phrases (no physical STT)');
