/* Explicit Web Speech metadata/event fixtures, not audible/system availability evidence. */
require('./ts_loader.js');
const assert=require('assert/strict'),path=require('node:path');
const map=new Map();global.localStorage={getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v)};
global.window=new EventTarget();global.CustomEvent=class extends Event{constructor(t,o){super(t);this.detail=o?.detail;}};
global.document={hidden:false};global.SpeechSynthesisUtterance=class{constructor(text){this.text=text;}};
const core=require(path.resolve('apps/vehicle-app/src/i18n/core.ts')),voices=require(path.resolve('apps/vehicle-app/src/i18n/voices.ts')),S=require(path.resolve('apps/vehicle-app/src/i18n/systemSpeech.ts'));
const fixture=[{voiceURI:'fixture-en',lang:'en-US',localService:true},{voiceURI:'fixture-de',lang:'de-DE',localService:false}];
let calls=[],behavior='complete';
global.speechSynthesis={getVoices:()=>fixture,cancel:()=>{if(behavior==='throw')throw Error('fixture platform exception');},speak:utterance=>{calls.push(utterance);utterance.onstart?.();if(behavior==='complete')setTimeout(()=>utterance.onend?.(),1);if(behavior==='error')setTimeout(()=>utterance.onerror?.(),1);}};
(async()=>{
 for(const [language,id] of [['en','fixture-en'],['de','fixture-de']]){
  core.setLanguage(language);voices.setVoicePreference(language,{provider:'system',voiceId:id});let started=0;
  assert.equal(await S.systemSpeech('Kapat',new AbortController().signal,()=>true,()=>started++),true);assert.equal(started,1);assert.equal(calls.at(-1).lang,core.LOCALES[language]);assert.equal(calls.at(-1).voice.voiceURI,id);assert.notEqual(calls.at(-1).text,'Kapat');
 }
 const before=calls.length;assert.equal(await S.systemSpeech('private',new AbortController().signal,()=>true,()=>{},true),false);assert.equal(calls.length,before);
 voices.setVoicePreference('de',{provider:'system',voiceId:'fixture-de',onlineConsent:true});behavior='error';assert.equal(await S.systemSpeech('private',new AbortController().signal,()=>true,()=>{},true),false);
 behavior='wait';const controller=new AbortController();const active=S.systemSpeech('Kapat',controller.signal,()=>true);controller.abort();assert.equal(await active,false);
 behavior='throw';assert.equal(await S.systemSpeech('Kapat',new AbortController().signal,()=>true),false);
 behavior='complete';voices.setVoicePreference('de',{provider:'system',voiceId:'missing'});assert.equal(await S.systemSpeech('Kapat',new AbortController().signal,()=>true),false);
 voices.setVoicePreference('de',{provider:'system',voiceId:'fixture-de',gender:'female'});assert.equal(await S.systemSpeech('Kapat',new AbortController().signal,()=>true),false);
 console.log('PASS: selected-locale utterance, actual event completion semantics, explicit online permission, unavailable voice/gender rejection, abort and platform exception cleanup (fixtures).');
})().catch(error=>{console.error(error);process.exitCode=1;});
