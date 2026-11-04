/** Runs the actual conversation hook on a small hook host: real state machine and storage, deterministic provider and recognizer. */
require('./ts_loader.js');
const assert=require('assert/strict'),Module=require('module'),path=require('path');
const host={slots:[],index:0,effects:[],dirty:false};
const react={
 useState(initial){const k=host.index++;if(!(k in host.slots))host.slots[k]=typeof initial==='function'?initial():initial;return [host.slots[k],v=>{const next=typeof v==='function'?v(host.slots[k]):v;if(next!==host.slots[k]){host.slots[k]=next;host.dirty=true;}}];},
 useRef(value){const k=host.index++;if(!(k in host.slots))host.slots[k]={current:value};return host.slots[k];},
 useCallback:f=>f,useMemo:f=>f(),
 useEffect(effect,deps){const k=host.index++,old=host.slots[k];if(old&&deps&&deps.every((d,n)=>d===old.deps[n]))return;host.slots[k]={deps,cleanup:old?.cleanup};host.effects.push(()=>{old?.cleanup?.();host.slots[k].cleanup=effect();});},
 useSyncExternalStore:(_subscribe,read)=>read(),
};
const load=Module._load;
Module._load=function(request,...rest){
 if(request==='react')return react;
 if(request==='@packages/safety/crisisDetector')return {checkCrisisTrigger:()=>({isCrisis:false})};
 return load.call(this,request,...rest);
};
const store=new Map();
global.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k),key:i=>[...store.keys()][i]??null,get length(){return store.size;}};
global.window=new EventTarget();window.attuneOutputMuted=true;window.localStorage=global.localStorage;
global.document=Object.assign(new EventTarget(),{hidden:false,documentElement:{lang:'en'},cookie:''});
Object.defineProperty(global,'navigator',{value:{language:'en-US',locks:{request:(_name,operation)=>operation()}},configurable:true});
const utterances=[];
class Recognition{start(){this.timer=setTimeout(()=>{this.onstart?.();this.timer=setTimeout(()=>{const text=utterances.shift();if(text){this.onresult?.({resultIndex:0,results:[Object.assign([{transcript:text,confidence:.9}],{isFinal:true})]});}else this.onerror?.({error:'no-speech'});this.onend?.();},5);},1);}abort(){clearTimeout(this.timer);}stop(){clearTimeout(this.timer);}}
window.SpeechRecognition=Recognition;
const provider={analyze:[],converse:[],mode:'success',deferred:null};
const json=(status,body)=>({ok:status<400,status,json:async()=>body,text:async()=>JSON.stringify(body)});
global.fetch=async(url,options={})=>{
 const route=String(url);
 if(route.includes('/provider-status'))return json(200,{apiKeyConfigured:true,providerName:'Mocked'});
 if(route.includes('/compact-context'))return json(200,{memory:[],method:'extractive-user-quotes-v1'});
 if(route.includes('/analyze-session')){provider.analyze.push(JSON.parse(options.body));return json(200,{providerType:'LIVE_OPENAI',summaryText:'A completed reflection.',themes:['Odaklanma'],moodTrend:'RELAXED'});}
 if(route.includes('/converse')){
  provider.converse.push(JSON.parse(options.body));
  if(provider.mode==='fail')return json(503,{detail:'CONVERSE_PROVIDER_UNAVAILABLE'});
  if(provider.mode==='defer')return new Promise(resolve=>{provider.deferred=()=>resolve(json(200,{reply:'A late reply.',isCrisis:false,providerType:'LIVE_OPENAI'}));});
  return json(200,{reply:'A completed reply.',isCrisis:false,providerType:'LIVE_OPENAI'});
 }
 throw Error('Unexpected request '+route);
};
const utils=path.resolve('apps/vehicle-app/src/utils');
const consent=require(path.join(utils,'serviceConsent.ts'));
const {STORAGE_KEYS}=require(path.join(utils,'attuneMode.ts'));
const {useMentalConversation}=require(path.join(utils,'useMentalConversation.ts'));
const {closingTranscript}=require(path.join(utils,'mentalSessionClose.ts'));
const settle=(ms=20)=>new Promise(ok=>setTimeout(ok,ms));
let hook;
function render(){for(let i=0;i<20;i++){host.dirty=false;host.index=0;hook=useMentalConversation(true);const effects=host.effects.splice(0);for(const effect of effects)effect();if(!host.dirty&&!effects.length)return;}}
const records=()=>JSON.parse(localStorage.getItem(STORAGE_KEYS.MENTAL_HISTORY)||'[]');
async function until(what,test){for(let i=0;i<400;i++){render();if(test())return;await settle(10);}throw Error('Timed out waiting for '+what);}
async function start(){provider.mode='success';hook.start();await until('listening',()=>hook.phase==='listening');}
async function turn(text,count){utterances.push(text);await until('reply '+text,()=>hook.messages.filter(m=>m.sender==='AI').length===count&&hook.phase==='listening');}
async function pending(text){provider.mode='defer';utterances.push(text);await until('pending reply',()=>hook.phase==='preparing'&&provider.deferred);}

(async()=>{
 // The pure rule, including a failed turn that is not the pending one.
 const m=(id,completed)=>({id,completed});
 assert.deepEqual(closingTranscript([m('u1',true),m('a1',true),m('u2',false)],'u2',false),{completed:[m('u1',true),m('a1',true)],discardedPending:true,failed:false});
 assert.equal(closingTranscript([m('u1',false),m('err',false)],undefined,true).failed,true);
 assert.equal(closingTranscript([m('u1',true),m('err',false)],undefined,false).failed,true,'an unfinished message without a pending turn is a failed turn');
 assert.equal(closingTranscript([],undefined,false).discardedPending,false);

 consent.setServiceConsent('mental',consent.SERVICE_REQUIREMENTS.mental.map(x=>x[0]));
 render();await until('hook ready',()=>hook.serviceConsent===true);

 // Later reply pending: completed exchange saved once, unfinished one gone, late reply ignored.
 await start();await turn('First completed turn.',1);await pending('Unanswered turn.');
 await hook.finish();await hook.finish();await until('completed',()=>hook.phase==='completed');
 assert.equal(provider.analyze.length,1,'exactly one summary request');
 assert.deepEqual(provider.analyze[0].messages,[{role:'user',content:'First completed turn.'},{role:'assistant',content:'A completed reply.'}]);
 assert.ok(!JSON.stringify(provider.analyze[0]).includes('Unanswered turn.'));
 assert.equal(records().length,1);
 assert.equal(records()[0].completed,true);assert.equal(records()[0].consented,true);
 assert.equal(records()[0].transcript,undefined,'raw transcript stays off without its own consent');
 assert.deepEqual(hook.messages.map(x=>x.text),['First completed turn.','A completed reply.']);
 assert.equal(hook.notice,'Tamamlanan görüşme turlarının özeti kaydedildi; yanıtı beklenen son mesaj dahil edilmedi.');
 provider.deferred();provider.deferred=null;await settle(40);render();
 assert.deepEqual(hook.messages.map(x=>x.text),['First completed turn.','A completed reply.'],'late reply cannot reach the session');
 assert.equal(records().length,1);assert.equal(provider.analyze.length,1);assert.equal(hook.phase,'completed');

 // Transcript consent keeps its own gate and never stores the discarded turn.
 localStorage.setItem(STORAGE_KEYS.PRIVACY_MENTAL_TRANSCRIPT_ALLOWED,'true');
 await start();await turn('Stored turn.',1);await pending('Never stored.');
 await hook.finish();await until('completed',()=>hook.phase==='completed'&&records().length===2);
 assert.deepEqual(records()[1].transcript.map(x=>x.text),['Stored turn.','A completed reply.']);
 localStorage.removeItem(STORAGE_KEYS.PRIVACY_MENTAL_TRANSCRIPT_ALLOWED);
 provider.deferred();provider.deferred=null;await settle(40);render();assert.equal(records().length,2);

 // Only a pending first turn: nothing completed, nothing to summarise.
 const summaries=provider.analyze.length;
 await start();await pending('Only a pending first turn.');
 await hook.finish();await until('empty end',()=>hook.phase==='completed');
 assert.equal(records().length,2);assert.equal(provider.analyze.length,summaries);assert.deepEqual(hook.messages,[]);
 provider.deferred();provider.deferred=null;await settle(40);render();assert.equal(records().length,2);

 // Paused with the reply pending: the turn is still unanswered, so the same rule applies.
 await start();await turn('Completed before pause.',1);await pending('Pending while paused.');
 hook.pause();render();assert.equal(hook.phase,'paused');
 await hook.finish();await until('paused end',()=>hook.phase==='completed'&&records().length===3);
 assert.ok(!JSON.stringify(provider.analyze.at(-1)).includes('Pending while paused.'));
 provider.deferred();provider.deferred=null;await settle(40);render();

 // A provider failure stays a failed session: an error, and no record.
 await start();await turn('Completed before failure.',1);provider.mode='fail';utterances.push('This reply fails.');
 await until('error',()=>hook.phase==='error');
 await hook.finish();render();
 assert.equal(hook.phase,'error');assert.equal(records().length,3);
 console.log('PASS pending reply cancelled, completed exchanges summarised and saved once, late reply ignored, transcript consent separate, empty and failed sessions unsaved');
 process.exit(0);
})().catch(error=>{console.error(error);process.exit(1);});
