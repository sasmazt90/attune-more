// Execute the actual component effect/recognition functions with an explicit OS fixture.
// No real camera, microphone, recognition provider or health records are used.
require('./ts_loader.js');const ts=require('typescript'),fs=require('fs'),assert=require('assert/strict');
const text=fs.readFileSync('apps/vehicle-app/src/app/vision/SpokenLetterPage.tsx','utf8'),source=ts.createSourceFile('page.tsx',text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);let effect;const functions={};
function visit(node){if(ts.isFunctionDeclaration(node)&&['abortRecognition','listen','current'].includes(node.name?.text))functions[node.name.text]=node.getText(source);if(ts.isCallExpression(node)&&node.expression.getText(source)==='useEffect'&&node.arguments[0]?.getText(source).includes("window.addEventListener('attune-locale-media-cancel'"))effect=node.arguments[0].getText(source);ts.forEachChild(node,visit);}visit(source);assert(effect&&Object.keys(functions).length===3);
const compiled=ts.transpileModule(Object.values(functions).join('\n')+'\nconst effect='+effect+';', {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
global.window=new EventTarget();global.document={hidden:false};const values=new Map([['health','unchanged'],['consent','unchanged']]);global.localStorage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,String(v))};
const C=require('../../apps/vehicle-app/src/i18n/core.ts'),V=require('../../apps/vehicle-app/src/utils/spokenVision.ts'),{VisionFlow}=require('../../apps/vehicle-app/src/utils/visionFlow.ts');
let permitted=true,receives=[],pauses=0,voiceStates=[];const instances=[];class Recognition{constructor(){instances.push(this);}start(){this.onstart?.();}abort(){this.aborted=true;this.onend?.();}}
window.SpeechRecognition=Recognition;C.setLanguage('en');const session=new V.SpokenLetterSession();session.present(1000);const flow={current:new VisionFlow()};flow.current.start('synthetic');flow.current.transition('user-paused');const r={current:{mounted:true,active:true,epoch:3,session,recognition:null,listeningStarted:false,restart:null,audio:null,muted:false,modal:false}},parked={current:true},actions={current:{pause:()=>pauses++,receive:(...a)=>receives.push(a)}};
const deps={r,flow,parked,actions,window,getLanguage:C.getLanguage,getLocale:C.getLocale,speechMuted:()=>window.attuneOutputMuted===true,serviceAllowed:()=>permitted,isCameraAllowed:()=>permitted,isMicrophoneAllowed:()=>permitted,canvas:{current:null},setVoice:value=>voiceStates.push(value),timing:()=>{},failure:()=>assert.fail('Paused control cannot demand camera inference'),measureSymbol:()=>assert.fail('Paused control cannot demand a stimulus'),stage:()=>assert.fail('Unexpected error'),setError:()=>assert.fail('Unexpected error'),setAnswerNotice:()=>{},discardPresentation:()=>{},visionRecognitionChoice:require('../../apps/vehicle-app/src/utils/visionSpeechTurn.ts').visionRecognitionChoice,parseLetterAnswer:V.parseLetterAnswer,isLetterInstructionEcho:V.isLetterInstructionEcho};
const names=Object.keys(deps);const controller=new Function(...names,compiled+'\nreturn {effect,listen,abortRecognition};')(...names.map(k=>deps[k]));actions.current.listen=controller.listen;
const cleanup=controller.effect();controller.listen();const old=instances[0];assert.equal(old.lang,'en-US');const saved=JSON.stringify(session);
C.setLanguage('de');assert(old.aborted);assert.equal(instances.length,2);const fresh=instances.at(-1);assert.equal(fresh.lang,'de-DE');assert.equal(JSON.stringify(session),saved);assert.equal(flow.current.stage,'user-paused');assert.equal(r.current.restart,null);assert.deepEqual(voiceStates.slice(-2),['quiet','listening']);
function result(word,index=0){const row=[{transcript:word,confidence:.9}];row.isFinal=true;const results=[];results[index]=row;return {resultIndex:index,results};}
old.onresult(result('resume'));assert.equal(receives.length,0);fresh.onresult(result('fortsetzen'));assert.equal(receives.length,1);assert.equal(receives[0][0],'fortsetzen');
// In a paused session an F/B code word must never cancel the assessment;
// only the advertised explicit finish phrase can enter the receive path.
for(const [i,word] of ['fertig','beenden','fertig rechts'].entries())fresh.onresult(result(word,i+1));assert.equal(receives.length,1);
fresh.onresult(result('Test beenden',4));assert.equal(receives.length,2);
window.dispatchEvent(new Event('attune-locale-media-cancel'));assert.equal(instances.length,2); // Voice-only event must not reopen the microphone.
window.attuneOutputMuted=true;C.setLanguage('tr');assert(fresh.aborted);assert.equal(instances.length,2);assert.equal(voiceStates.at(-1),'quiet');window.attuneOutputMuted=false;
document.hidden=true;C.setLanguage('en');assert.equal(instances.length,2);document.hidden=false;permitted=false;C.setLanguage('de');assert.equal(instances.length,2);permitted=true;parked.current=false;C.setLanguage('tr');assert.equal(instances.length,2);parked.current=true;
flow.current.transition('eye-check');C.setLanguage('tr');assert.equal(pauses,1);r.current.active=false;C.setLanguage('en');assert.equal(instances.length,2);cleanup();C.setLanguage('de');assert.equal(instances.length,2);
assert.equal(JSON.stringify(session),saved);assert.equal(values.get('health'),'unchanged');assert.equal(values.get('consent'),'unchanged');console.log('PASS actual component source: paused EN -> DE recognizer identity/locale, new-language control acceptance, stale-event rejection, mute/permission/motion/inactive guards, no session/data reset and listener cleanup (OS fixtures only)');
// Exercise the current grammar after every TR/EN/DE paused locale transition.
r.current.active=true;flow.current.transition('user-paused');C.setLanguage('en');const cleanup2=controller.effect();controller.listen();
for(const [language,locale,word,finish] of [['en','en-US','finish','finish the test'],['tr','tr-TR','F','testi bitir'],['de','de-DE','fertig','Test beenden']]){
 const previous=instances.at(-1);C.setLanguage(language);const live=instances.at(-1);assert.equal(live.lang,locale);
 const count=receives.length;live.onresult(result(word));assert.equal(receives.length,count);
 live.onresult(result(finish,1));assert.equal(receives.length,count+1);assert.equal(receives.at(-1)[0],finish);
 const low=result(finish,2);low.results[2][0].confidence=.2;live.onresult(low);assert.equal(receives.length,count+1);
 if(previous!==live){previous.onresult(result(finish,3));assert.equal(receives.length,count+1);assert(previous.aborted);}
 assert.equal(JSON.stringify(session),saved);
}
cleanup2();controller.abortRecognition();assert.equal(values.get('health'),'unchanged');assert.equal(values.get('consent'),'unchanged');
console.log('PASS TR/EN/DE paused locale transitions: explicit finish accepted, code words/low-confidence/stale finals rejected, progress preserved (OS fixtures only)');
