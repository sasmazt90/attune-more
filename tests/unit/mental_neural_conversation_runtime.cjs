/** Execute actual Mental speak closure; labelled providers, no speech/inference. */
require('./ts_loader.js');const ts=require('typescript'),fs=require('fs'),assert=require('assert/strict');
const text=fs.readFileSync('apps/vehicle-app/src/utils/useMentalConversation.ts','utf8'),ast=ts.createSourceFile('conversation.ts',text,ts.ScriptTarget.Latest,true);let speak;
function visit(n){if(ts.isFunctionDeclaration(n)&&n.name?.text==='speak')speak=n.getText(ast);ts.forEachChild(n,visit);}visit(ast);assert(speak);
const code=ts.transpileModule(speak,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText;
(async()=>{
 for(const scenario of ['backend','browser','failed','crisis']){
  const r={active:true,epoch:1,audioEpoch:0,pendingSpeech:null},settings={current:{speechConsent:true,voiceEnabled:true}};let neural=0,system=0,resumed=0,notice;
  const deps={runtime:{current:r},settings,valid:e=>e===r.epoch&&r.active,AbortController,setTimeout,clearTimeout,
   setVoiceNotice:()=>{},setVoiceState:()=>{},setPhase:()=>{},setActive:()=>{},getLanguage:()=> 'de',t:s=>s,timing:()=>{},
   approvedMentalTemplate:()=>null,abortRecognition:()=>{},stopAudio:()=>{r.audioEpoch++;},resume:()=>resumed++,cancel:why=>{notice=why;r.active=false;},
   mentalSpeechEngine:()=>scenario==='browser'?'browser-system':'chatterbox-v3',
   mentalNeuralSpeech:async value=>{neural++;assert.equal(value,'Neue dynamische Antwort 1287.');return scenario!=='failed';},
   mentalSystemSpeech:async value=>{system++;assert.equal(value,'Neue dynamische Antwort 1287.');return true;}};
  const run=new Function(...Object.keys(deps),code+';return speak;')(...Object.values(deps));await run('Neue dynamische Antwort 1287.',1,scenario==='crisis');
  if(scenario==='crisis'){assert.equal(neural+system,0);assert(notice.includes('112'));assert.equal(resumed,0);}
  if(scenario==='backend'){assert.equal(neural,1);assert.equal(system,0);assert.equal(resumed,1);assert.equal(r.pendingSpeech,null);}
  if(scenario==='browser'){assert.equal(neural,0);assert.equal(system,1);assert.equal(resumed,1);}
  if(scenario==='failed'){assert.equal(neural,1);assert.equal(system,0);assert(notice);assert.equal(resumed,0);}
 }
 console.log('PASS actual Mental speech closure: arbitrary replies select backend/explicit browser only, failure has no automatic fallback, crisis retains 112 without optional synthesis');
})().catch(e=>{console.error(e);process.exitCode=1});
