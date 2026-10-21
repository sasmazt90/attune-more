/* Real module behavior with explicit platform metadata fixtures; no live voice claims. */
require('./ts_loader.js');
const assert=require('assert/strict'),path=require('path');
const store=new Map([['health-records','PRIVATE äöü ß İı Şş'],['consent','unchanged']]);
global.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v))};
global.window=new EventTarget();global.CustomEvent=class extends Event{constructor(type,options){super(type);this.detail=options?.detail;}};
const load=file=>require(path.resolve('apps/vehicle-app/src',file));
const C=load('i18n/core.ts'),V=load('i18n/voices.ts'),L=load('i18n/locks.ts'),R=load('i18n/render.ts'),P=load('utils/spokenVision.ts');
assert.equal(C.getLanguage(),'tr');
for(const language of C.LANGUAGES){
 C.setLanguage(language);assert.equal(C.getLanguage(),language);assert.equal(C.getLocale(),C.LOCALES[language]);
 assert.equal(store.get('health-records'),'PRIVATE äöü ß İı Şş');assert.equal(store.get('consent'),'unchanged');
 assert.equal(C.t('PRIVATE äöü ß İı Şş',language),'PRIVATE äöü ß İı Şş');
 assert.equal(C.t('Göz Sağlığı',language),language==='en'?'Vision Health':language==='de'?'Augengesundheit':'Göz Sağlığı');
 assert.equal(Number(String(R.localizedNode(12.345,language)).replace(',','.')),12.345);
}
L.setLanguageSwitchLock('vision',true);assert.throws(()=>C.setLanguage('en'),/ASSESSMENT/);assert.throws(()=>V.setVoicePreference('en',{provider:'system'}),/ASSESSMENT/);assert.equal(C.getLanguage(),'de');L.setLanguageSwitchLock('vision',false);
store.set(C.LANGUAGE_KEY,'invalid');assert.equal(C.getLanguage(),'tr');assert.throws(()=>C.setLanguage('fr'),/UNSUPPORTED/);
const voices=[{voiceURI:'real-en',name:'Fixture',lang:'en-US',localService:true},{voiceURI:'real-de',name:'Fixture2',lang:'de-DE',localService:false},{voiceURI:'wrong-region',name:'Fixture3',lang:'en-GB',localService:true}];
assert.equal(V.systemVoiceChoices(voices,'en').length,1);assert.equal(V.systemVoiceChoices(voices,'en')[0].gender,'unknown');
assert.equal(V.selectSystemVoice(voices,'en',{provider:'system',gender:'female'}),undefined);
assert.equal(V.selectSystemVoice(voices,'de',{provider:'system',voiceId:'real-en'}),undefined);
assert.equal(V.selectSystemVoice([], 'de',{provider:'system'}),undefined);
V.setVoicePreference('en',{provider:'local',voiceId:'espeak:en:female',gender:'female'});V.setVoicePreference('de',{provider:'local',voiceId:'espeak:de:male',gender:'male'});assert.equal(V.voicePreference('en').gender,'female');assert.equal(V.voicePreference('de').gender,'male');
for(const [language,sentence,letter,rotation,mirrored] of [['en','P upside down and mirrored','P',180,true],['de','P auf dem Kopf und gespiegelt','P',180,true],['en','F upright','F',0,false],['de','E nach rechts','E',90,false]]){
 const parsed=P.parseLetterAnswer(sentence,language);assert.equal(parsed.letter,letter,sentence);assert.equal(parsed.rotation,rotation,sentence);assert.equal(!!parsed.mirrored,mirrored,sentence);
}
for(const language of ['en','de']){
 for(const [command,text] of Object.entries(language==='en'?{pause:'pause',resume:'resume',finish:'finish the test','not-visible':"I can't see it",repeat:'repeat'}:{pause:'pausieren',resume:'fortsetzen',finish:'Test beenden','not-visible':'ich sehe es nicht',repeat:'wiederholen'}))assert.equal(P.parseLetterAnswer(text,language).command,command,text);
 assert(!P.isLetterInstructionEcho(language==='en'?'P upside down':'P auf dem Kopf',language));
 assert(P.parseLetterAnswer(language==='en'?'E or F upright':'E oder F aufrecht',language).clarify);
}
assert.equal(P.parseLetterAnswer('Pırasanın P’si baş aşağı').letter,'P');
const Manifest=load('app/localized-manifest/route.ts');
for(const language of C.LANGUAGES){const response=Manifest.GET(new Request('http://localhost/localized-manifest?language='+language));assert.equal(response.status,200);assert.equal(response.headers.get('content-language'),C.LOCALES[language]);}
assert.equal(Manifest.GET(new Request('http://localhost/localized-manifest?language=fr')).status,422);
console.log('PASS: persistence, private Unicode preservation, assessment locks, formatting, exact-locale voice metadata/no fallback and multilingual target-independent parser');

const Queue=load('i18n/sessionSpeech.ts');
for(const paused of [false,true]){const state={active:true,paused,pendingSpeech:{text:'old-language reply',crisis:false},transcript:['PRIVATE Straße İı'],progress:{turn:3}};let pauses=0,notices=0;Queue.cancelQueuedSessionSpeech(state,{pause:()=>{pauses++;state.paused=true;},crisis:()=>assert.fail('ordinary reply is not crisis'),notice:()=>notices++});assert.equal(state.pendingSpeech,null);assert.deepEqual(state.transcript,['PRIVATE Straße İı']);assert.deepEqual(state.progress,{turn:3});assert.equal(pauses,paused?0:1);assert.equal(notices,1);}
let crisisCancelled=0;Queue.cancelQueuedSessionSpeech({active:true,paused:true,pendingSpeech:{crisis:true}},{pause:()=>assert.fail('crisis cannot resume normal speech'),crisis:()=>crisisCancelled++,notice:()=>assert.fail('crisis needs the emergency notice')});assert.equal(crisisCancelled,1);

assert.equal(P.parseLetterAnswer('Äpfel aufrecht','de').letter,undefined);assert.equal(P.parseLetterAnswer('Äpfel aufrecht','de').clarify,'letter');assert.equal(P.parseLetterAnswer('Bären aufrecht','de').letter,'B');
