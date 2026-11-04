import {isMicrophoneAllowed} from './attuneMode';
import {serviceAllowed} from './serviceConsent';
import {cloudSpeechEnabled} from './speechProvider';
import {localBackend} from './localBackend';

type Service='vision'|'mental';
// Sentences in the Mental reference clips are up to 950 ms apart, so a 900 ms silence limit cut people off mid-thought.
// 1500 ms leaves room for that, and adds little beside about 16 s of speech generation. A Vision answer is one short
// word, so it keeps the quick limit. Waiting for speech to begin stays at 15 s for both.
const LISTENING:Record<Service,{silenceMs:number;longestMs:number;deadlineMs:number}>={
 vision:{silenceMs:900,longestMs:15000,deadlineMs:40000},
 mental:{silenceMs:1500,longestMs:60000,deadlineMs:90000},
};
const NO_SPEECH_MS=15000;
/** Bounded real microphone capture. No transcript fixtures or score overrides. */
export class CloudSpeechRecognition {
 lang='tr-TR';continuous=false;interimResults=false;maxAlternatives=1;
 onstart:(()=>void)|null=null;onend:(()=>void)|null=null;onspeechend:(()=>void)|null=null;
 onerror:((event:{error:string})=>void)|null=null;
 onresult:((event:{resultIndex:number;results:any[]})=>void)|null=null;
 private epoch=0;private active=false;private controller:AbortController|null=null;
 private stream:MediaStream|null=null;private recorder:MediaRecorder|null=null;
 private context:AudioContext|null=null;private interval:ReturnType<typeof setInterval>|null=null;
 private deadline:ReturnType<typeof setTimeout>|null=null;private heard=false;
 constructor(private service:Service){}
 private allowed=()=>isMicrophoneAllowed()&&serviceAllowed(this.service);
 private valid=(epoch:number)=>this.active&&this.epoch===epoch&&this.allowed();
 private privacy=()=>{if(!this.allowed())this.abort();};
 private release(){
  if(this.interval)clearInterval(this.interval);this.interval=null;
  if(this.deadline)clearTimeout(this.deadline);this.deadline=null;
  if(this.recorder?.state==='recording')this.recorder.stop();this.recorder=null;
  this.stream?.getTracks().forEach(track=>track.stop());this.stream=null;
  void this.context?.close().catch(()=>{});this.context=null;
  window.removeEventListener('attune-privacy',this.privacy);
  window.removeEventListener('attune-service-consent',this.privacy);
 }
 abort(){this.active=false;this.epoch++;this.controller?.abort();this.controller=null;this.release();}
 stop(){if(this.recorder?.state==='recording')this.recorder.stop();}
 start(){
  if(this.active)throw Error('RECOGNITION_ALREADY_STARTED');
  if(!this.allowed())throw Error('SPEECH_PERMISSION_REQUIRED');
  this.active=true;this.heard=false;const epoch=++this.epoch;this.controller=new AbortController();
  window.addEventListener('attune-privacy',this.privacy);window.addEventListener('attune-service-consent',this.privacy);
  this.deadline=setTimeout(()=>this.fail(epoch,'network'),LISTENING[this.service].deadlineMs);
  void this.capture(epoch);
 }
 private end(epoch:number){if(!this.valid(epoch))return;this.active=false;this.release();this.onend?.();}
 private fail(epoch:number,error:string){if(!this.valid(epoch))return;this.onerror?.({error});this.end(epoch);}
 private async capture(epoch:number){
  try{
   const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
   if(!this.valid(epoch)){stream.getTracks().forEach(t=>t.stop());return;}
   this.stream=stream;const context=new AudioContext();this.context=context;await context.resume();
   if(!this.valid(epoch))return;
   const analyser=context.createAnalyser();analyser.fftSize=1024;context.createMediaStreamSource(stream).connect(analyser);
   const mime=['audio/webm;codecs=opus','audio/webm'].find(type=>MediaRecorder.isTypeSupported(type));
   if(!mime){this.fail(epoch,'audio-capture');return;}
   const recorder=new MediaRecorder(stream,{mimeType:mime,audioBitsPerSecond:64000});this.recorder=recorder;
   const chunks:Blob[]=[];let bytes=0;recorder.ondataavailable=e=>{if(e.data.size){bytes+=e.data.size;chunks.push(e.data);if(bytes>2000000)this.fail(epoch,'audio-capture');}};
   recorder.onerror=()=>this.fail(epoch,'audio-capture');
   recorder.onstop=()=>{if(this.valid(epoch))void this.submit(epoch,new Blob(chunks,{type:mime}));};
   const samples=new Float32Array(analyser.fftSize);let started=performance.now(),lastVoice=started,voicedFrames=0;
   recorder.start(200);this.onstart?.();
   if(!this.valid(epoch))return;
   this.interval=setInterval(()=>{
    if(!this.valid(epoch)){this.abort();return;}
    analyser.getFloatTimeDomainData(samples);const rms=Math.sqrt(samples.reduce((sum,x)=>sum+x*x,0)/samples.length),now=performance.now();
    if(rms>.012){voicedFrames++;lastVoice=now;if(voicedFrames>=4)this.heard=true;}
    const limits=LISTENING[this.service];
    if((this.heard&&now-lastVoice>limits.silenceMs)||now-started>(this.heard?limits.longestMs:NO_SPEECH_MS)){if(this.interval)clearInterval(this.interval);this.interval=null;this.onspeechend?.();this.stop();}
   },50);
  }catch(e){this.fail(epoch,e instanceof DOMException&&e.name==='NotAllowedError'?'not-allowed':'audio-capture');}
 }
 private async submit(epoch:number,blob:Blob){
  this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;
  void this.context?.close().catch(()=>{});this.context=null;
  if(!this.heard){this.fail(epoch,'no-speech');return;}
  try{
   const data=new Uint8Array(await blob.arrayBuffer());let binary='';for(let i=0;i<data.length;i+=8192)binary+=String.fromCharCode(...data.subarray(i,i+8192));
   if(!this.valid(epoch))return;
   const response=await fetch(localBackend('/api/speech/transcribe'),{method:'POST',headers:{'Content-Type':'application/json'},signal:this.controller!.signal,body:JSON.stringify({audio:btoa(binary),consent:true,service:this.service,language:this.lang.split('-')[0]})});
   if(!this.valid(epoch))return;
   if(!response.ok){this.fail(epoch,response.status===403?'not-allowed':response.status===422?'no-speech':'network');return;}
   const result=await response.json();if(!this.valid(epoch))return;
   if(typeof result.text!=='string'||!result.text.trim()){this.fail(epoch,'no-speech');return;}
   // Zero denotes unavailable confidence, as for native recognizers without it.
   const item=Object.assign([{transcript:result.text,confidence:0}],{isFinal:true});
   this.onresult?.({resultIndex:0,results:[item]});this.end(epoch);
  }catch{this.fail(epoch,'network');}
 }
}
export function speechRecognitionConstructor(service:Service):any {
 if(cloudSpeechEnabled())return class extends CloudSpeechRecognition{constructor(){super(service);}};
 return (window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;
}
