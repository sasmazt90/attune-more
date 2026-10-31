/** Exercise the actual recognizer's lifecycle; provider/media are deterministic mocks. */
require('./ts_loader.js');const assert=require('assert/strict');
global.window=new EventTarget();const store=new Map();global.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v))};
const S=require('../../apps/vehicle-app/src/utils/serviceConsent.ts');
const R=require('../../apps/vehicle-app/src/utils/speechRecognition.ts');
const native=function Native(){};window.SpeechRecognition=native;
assert.equal(R.speechRecognitionConstructor('mental'),native,'native remains the default');
process.env.NEXT_PUBLIC_ATTUNE_SPEECH_PROVIDER='openai';
// Reload the consent module exactly as a separate deployment build would.
delete require.cache[require.resolve('../../apps/vehicle-app/src/utils/serviceConsent.ts')];
delete require.cache[require.resolve('../../apps/vehicle-app/src/utils/speechRecognition.ts')];
const C=require('../../apps/vehicle-app/src/utils/serviceConsent.ts'),{CloudSpeechRecognition}=require('../../apps/vehicle-app/src/utils/speechRecognition.ts');
assert.throws(()=>C.setServiceConsent('mental',['recognition','conversation','speech-output-v2']),/EXPLICIT/);
const grant=()=>C.setServiceConsent('mental',C.SERVICE_REQUIREMENTS.mental.map(x=>x[0]));grant();
const pending=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
let source,stops=0,fetchCalls=0;const media=()=>({getTracks:()=>[{stop:()=>stops++}]});
Object.defineProperty(global,'navigator',{value:{mediaDevices:{getUserMedia:()=>source.promise}},configurable:true});
global.AudioContext=class{resume(){return Promise.resolve();}close(){return Promise.resolve();}createAnalyser(){return {fftSize:1024,getFloatTimeDomainData:a=>a.fill(.1)};}createMediaStreamSource(){return {connect(){}};}};
global.MediaRecorder=class{static isTypeSupported(){return true;}state='inactive';constructor(){global.lastRecorder=this;}start(){this.state='recording';}stop(){this.state='inactive';this.ondataavailable({data:new Blob([new Uint8Array(200)])});queueMicrotask(()=>this.onstop());}};
const settle=()=>new Promise(r=>setTimeout(r,10));
(async()=>{
 source=pending();let r=new CloudSpeechRecognition('mental');let results=0;r.onresult=()=>results++;r.start();r.abort();source.resolve(media());await settle();assert.equal(stops,1);assert.equal(results,0);
 source=pending();r=new CloudSpeechRecognition('mental');r.start();C.setServiceConsent('mental',null);source.resolve(media());await settle();assert.equal(stops,2);assert.equal(results,0);assert.throws(()=>r.start(),/PERMISSION/);grant();
 const response=pending();global.fetch=()=>{fetchCalls++;return response.promise;};
 source=pending();r=new CloudSpeechRecognition('mental');r.onresult=()=>results++;r.start();source.resolve(media());await new Promise(x=>setTimeout(x,260));r.stop();await settle();assert.equal(fetchCalls,1);r.abort();response.resolve({ok:true,json:async()=>({text:'late sensitive transcript'})});await settle();assert.equal(results,0,'abort rejects late provider result');
 source=pending();global.fetch=async()=>({ok:true,json:async()=>({text:'actual returned transcript'})});r=new CloudSpeechRecognition('mental');let output;r.onresult=e=>output=e.results[0];r.start();source.resolve(media());await new Promise(x=>setTimeout(x,260));r.stop();await settle();assert.equal(output[0].transcript,'actual returned transcript');assert.equal(output[0].confidence,0);assert.equal(output.isFinal,true);
 console.log('PASS native default, renewed cloud consent, permission revocation, pending capture cleanup, abort rejects late reply, final provider transcript and unknown confidence');
})().catch(e=>{console.error(e);process.exitCode=1;});
