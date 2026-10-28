// Actual paused locale effect/recognizer functions. Capture-free OS fixtures.
require('./ts_loader.js');const ts=require('typescript'),fs=require('fs'),assert=require('assert/strict');
const source=ts.createSourceFile('page.tsx',fs.readFileSync('apps/vehicle-app/src/app/vision/SpokenLetterPage.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),functions={};let effect;
function visit(n){if(ts.isFunctionDeclaration(n)&&['abortRecognition','listen','current'].includes(n.name?.text))functions[n.name.text]=n.getText(source);if(ts.isCallExpression(n)&&n.expression.getText(source)==='useEffect'&&n.arguments[0]?.getText(source).includes("window.addEventListener('attune-locale-media-cancel'"))effect=n.arguments[0].getText(source);ts.forEachChild(n,visit);}visit(source);
const compiled=ts.transpileModule(Object.values(functions).join('\n')+'\nconst effect='+effect+';',{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
global.window=new EventTarget();global.document={hidden:false};const values=new Map([['health','unchanged'],['consent','unchanged']]);global.localStorage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,String(v))};
const C=require('../../apps/vehicle-app/src/i18n/core.ts'),V=require('../../apps/vehicle-app/src/utils/spokenVision.ts'),{VisionFlow}=require('../../apps/vehicle-app/src/utils/visionFlow.ts');
const instances=[],received=[];let permitted=true,pauses=0;
class Recognition{constructor(){instances.push(this);}start(){this.onstart?.();}abort(){this.aborted=true;this.onend?.();}}
window.SpeechRecognition=Recognition;const session=new V.SpokenLetterSession();session.present(1000);const saved=JSON.stringify(session),flow={current:new VisionFlow()};flow.current.start(session.id);flow.current.transition('user-paused');
const r={current:{mounted:true,active:true,epoch:3,session,recognition:null,listeningStarted:false,restart:null,audio:null,controller:null,answerTimer:null,settleAnswer:null,muted:false,modal:false}},parked={current:true},actions={current:{pause:()=>pauses++,receive:(...args)=>received.push(args),silence:()=>assert.fail('Paused turn must not issue answer guidance')}};
const deps={r,flow,parked,actions,window,getLanguage:C.getLanguage,getLocale:C.getLocale,speechMuted:()=>window.attuneOutputMuted===true,serviceAllowed:()=>permitted,isCameraAllowed:()=>permitted,isMicrophoneAllowed:()=>permitted,canvas:{current:null},setVoice:()=>{},timing:()=>{},failure:()=>assert.fail('Paused control cannot demand camera inference'),measureSymbol:()=>assert.fail('Paused control cannot demand a stimulus'),stage:()=>assert.fail('Unexpected error'),setError:()=>assert.fail('Unexpected error'),setAnswerNotice:()=>{},discardPresentation:()=>{},parseLetterAnswer:V.parseLetterAnswer,isLetterInstructionEcho:V.isLetterInstructionEcho,visionRecognitionChoice:require('../../apps/vehicle-app/src/utils/visionSpeechTurn.ts').visionRecognitionChoice,recognitionFailure:()=>assert.fail('Unexpected failure'),scheduleListening:()=>{}};
const controller=new Function(...Object.keys(deps),compiled+'\nreturn {effect,listen,abortRecognition};')(...Object.values(deps));actions.current.listen=controller.listen;
function result(text,index=0,confidence=.9){const row=[{transcript:text,confidence}];row.isFinal=true;const results=[];results[index]=row;return {resultIndex:index,results};}
C.setLanguage('en');const cleanup=controller.effect();controller.listen();let previous=instances.at(-1);
for(const [language,locale,word,finish] of [['de','de-DE','fertig','Test beenden'],['tr','tr-TR','F','testi bitir'],['en','en-US','finish','finish the test']]){
 C.setLanguage(language);const live=instances.at(-1);assert.equal(live.lang,locale);assert(previous.aborted);assert.equal(live.continuous,false);
 const before=received.length;previous.onresult(result(finish));assert.equal(received.length,before);
 live.onresult(result(word));live.onresult(result(finish,1,.2));assert.equal(received.length,before);
 live.onresult(result(finish,2));assert.equal(received.length,before+1);assert(live.aborted);assert.equal(r.current.recognition,null);live.onresult(result(finish,3));assert.equal(received.length,before+1);
 controller.listen();previous=instances.at(-1);assert.equal(JSON.stringify(session),saved);
}
const count=instances.length;window.dispatchEvent(new Event('attune-locale-media-cancel'));assert.equal(instances.length,count);
controller.abortRecognition();for(const gate of ['muted','hidden','permission','motion']){
 window.attuneOutputMuted=gate==='muted';document.hidden=gate==='hidden';permitted=gate!=='permission';parked.current=gate!=='motion';controller.listen();assert.equal(instances.length,count);
}
window.attuneOutputMuted=false;document.hidden=false;permitted=true;parked.current=true;flow.current.transition('eye-check');C.setLanguage('de');assert.equal(pauses,1);
cleanup();r.current.active=false;assert.equal(values.get('health'),'unchanged');assert.equal(values.get('consent'),'unchanged');
console.log('PASS actual paused TR/EN/DE turn recognizers: locale/identity, single acceptance, low-confidence rejection, mute/permission/motion guards and cleanup');
