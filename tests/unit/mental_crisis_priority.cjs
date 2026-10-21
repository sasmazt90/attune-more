/* Execute the actual send closure with explicit unavailable-context fixtures.
 * No browser, microphone, provider generation, or physical speech is asserted. */
require('./ts_loader.js');
const assert=require('assert/strict'),fs=require('fs'),vm=require('vm'),ts=require('typescript');
global.window=new EventTarget();global.localStorage={getItem:k=>k==='attune.language.v1'?'de':null};
const C=require('../../apps/vehicle-app/src/i18n/core.ts');
const {checkCrisisTrigger}=require('../../packages/safety/crisisDetector.ts');
const file='apps/vehicle-app/src/utils/useMentalConversation.ts',source=fs.readFileSync(file,'utf8');
const sf=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true);let send;
function walk(n){if(ts.isFunctionDeclaration(n)&&n.name?.text==='send')send=n.getText(sf);ts.forEachChild(n,walk);}walk(sf);assert(send);
const js=ts.transpileModule(send,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
(async()=>{
 for(const crisis of [true,false]){
  const originals=Array.from({length:42},(_,i)=>({id:'retained-'+i,turn:i,sender:i%2?'AI':'USER',text:'Synthetic prior context '+i,completed:true}));
  const r={epoch:1,active:true,paused:false,busy:false,voiceWaiting:false,failed:false,turn:42,id:'synthetic',memoryThrough:0,transcript:structuredClone(originals)};
  let contextCalls=0,speech,phase,notice,network=0;
  const bindings={runtime:{current:r},settings:{current:{parked:true,cloudConsent:false}},valid:epoch=>epoch===r.epoch&&r.active,
   getLocale:()=>C.getLocale(),checkCrisisTrigger,t:C.t,spokenText:v=>v,isDemoMode:()=>true,AbortController,Date,setTimeout,clearTimeout,
   abortRecognition:()=>{},timing:()=>{},append:row=>r.transcript.push(row),setPhase:v=>phase=v,setNotice:v=>notice=v,
   updateContext:async()=>{contextCalls++;throw Error('CONTEXT_UPDATE_FAILED');},
   fetch:async()=>{network++;throw Error('Network forbidden for crisis');},
   speak:async(text,epoch,isCrisis)=>{speech={text,epoch,isCrisis};}};
  vm.createContext(bindings);vm.runInContext(js,bindings);
  await bindings.send(crisis?'Ich fühle mich gerade nicht sicher und brauche dringend Hilfe.':'Ich bin heute müde.');
  assert.deepEqual(r.transcript.slice(0,42),originals);
  if(crisis){assert.equal(contextCalls,0);assert.equal(network,0);assert(speech.isCrisis&&speech.text.includes('112'));assert(!speech.text.includes('Söyledikleriniz'));assert.equal(r.failed,true);}
  else{assert.equal(contextCalls,1);assert.equal(network,0);assert.equal(speech,undefined);assert.equal(phase,'paused');assert.equal(r.paused,true);assert(notice);}
 }
 console.log('PASS actual send closure: local German crisis precedes unavailable context/network; ordinary failed compaction pauses; retained transcript bytes preserved');
})().catch(e=>{console.error(e);process.exitCode=1});
