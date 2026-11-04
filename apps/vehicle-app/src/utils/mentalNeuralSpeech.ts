import {getLanguage,getLocale,VOICE_EVENT} from '../i18n/core';
import {captureWhileLocked,languageSwitchLocked} from '../i18n/locks';
import {playAudioBytes,type PlaybackGestureRequest} from './fixedFileSpeech';
import {speechMuted} from './playbackMeter';
import limits from '../../../../shared/localization/neural-tts-limits.json';
export const MENTAL_ENGINE_KEY='attune.mental-speech-engine.v1';
export type MentalSpeechEngine='chatterbox-v3'|'browser-system';
function storedEngine():MentalSpeechEngine{
 try{return localStorage.getItem(MENTAL_ENGINE_KEY)==='browser-system'?'browser-system':'chatterbox-v3';}catch{return 'chatterbox-v3';}
}
export const mentalSpeechEngine=captureWhileLocked(storedEngine);
export function setMentalSpeechEngine(engine:MentalSpeechEngine){
 if(languageSwitchLocked())throw Error('ASSESSMENT_IN_PROGRESS');
 if(!['chatterbox-v3','browser-system'].includes(engine))throw Error('UNSUPPORTED_ENGINE');
 localStorage.setItem(MENTAL_ENGINE_KEY,engine);
 if(localStorage.getItem(MENTAL_ENGINE_KEY)!==engine)throw Error('VOICE_PREFERENCE_WRITE_FAILED');
 window.dispatchEvent(new Event(VOICE_EVENT));window.dispatchEvent(new Event('attune-locale-media-cancel'));
}
/**
 * Speech takes about 2.6 s per second of audio on the host, with no gain from more threads or a second worker, so a
 * whole reply waits about 16 s. The first sentence is ready in about 9 s and plays while the rest is generated. The
 * reply ends at the same time, with a pause between the two parts instead of a longer wait before the first.
 */
const FIRST_PART_MIN_WORDS=6;
const words=(text:string)=>text.trim().split(/\s+/).filter(Boolean).length;
export function speechParts(text:string):string[]{
 const sentences=text.trim().split(/(?<=[.!?…]["'”’)]?)\s+/).filter(Boolean);
 let at=1,first=sentences[0]||'';
 while(at<sentences.length&&words(first)<FIRST_PART_MIN_WORDS)first+=' '+sentences[at++];
 const rest=sentences.slice(at).join(' ');
 return rest?[first,rest]:[text];
}
/** Dynamic response text only. Authentication is handled by the same-origin server. */
export async function mentalNeuralSpeech(text:string,signal:AbortSignal,current:()=>boolean,onPlaying:()=>void,audioReady:(audio:HTMLAudioElement)=>void,options:{requestGesture?:PlaybackGestureRequest;observe?:(stage:string)=>void;speakerProfile?:'official-default'|'female-calm-v1'}={}):Promise<boolean>{
 const language=getLanguage(),locale=getLocale(),controller=new AbortController();
 const permitted=()=>{try{return !signal.aborted&&!controller.signal.aborted&&current()&&!speechMuted()&&!document.hidden&&getLanguage()===language&&mentalSpeechEngine()==='chatterbox-v3'&&Number(localStorage.getItem('attune_hearing_audio_focus')||0)<=Date.now();}catch{return false;}};
 const check=()=>{if(!permitted())controller.abort();},cancel=()=>controller.abort();
 if(!permitted())return false;
 signal.addEventListener('abort',cancel,{once:true});
 for(const event of ['attune-locale-media-cancel','attune-guidance-muted','attune-guidance-cancel'])window.addEventListener(event,cancel);
 document.addEventListener('visibilitychange',check);
 const timer=setInterval(check,100);let deadline=setTimeout(cancel,limits.generationMilliseconds);
 // Claim focus during generation too, preventing fixed guidance overlap.
 const owner={},focus=(active:boolean)=>{const event=new Event('attune-stream-focus') as Event&{owner:object;active:boolean};event.owner=owner;event.active=active;window.dispatchEvent(event);};
 focus(true);
 // Null means this part cannot be played, for whatever reason. It never rejects, because the next part is generated
 // while this one plays and nothing is waiting on it yet.
 const generate=async(part:string):Promise<ArrayBuffer|null>=>{
  try{
   const response=await fetch('/api/mental-neural-speech',{method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',body:JSON.stringify({text:part,language,speechConsent:true,...(options.speakerProfile?{speakerProfile:options.speakerProfile}:{})}),signal:controller.signal});
   if(options.speakerProfile&&response.headers.get('x-tts-speaker-profile')!==options.speakerProfile)return null;
   if(!response.ok||!permitted()||response.headers.get('content-type')?.split(';')[0]!=='audio/wav'||response.headers.get('x-tts-source')!=='chatterbox-multilingual-v3'||response.headers.get('x-tts-locale')!==locale)return null;
   const reader=response.body?.getReader();if(!reader)return null;const chunks:Uint8Array[]=[];let size=0;
   while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>8*1024*1024){await reader.cancel();return null;}chunks.push(value);}
   if(size<=44||!permitted())return null;
   const bytes=new Uint8Array(size);let at=0;for(const chunk of chunks){bytes.set(chunk,at);at+=chunk.length;}
   return bytes.buffer;
  }catch{return null;}
 };
 try{
  const parts=speechParts(text);
  let pending=generate(parts[0]);
  for(let index=0;index<parts.length;index++){
   const bytes=await pending;
   if(!bytes||!permitted())return false;
   // A part's generation budget ends here; playback has its own bounded deadline.
   // Keep live mute/consent/locale/session/motion and abort observation active.
   clearTimeout(deadline);
   if(index+1<parts.length){deadline=setTimeout(cancel,limits.generationMilliseconds);pending=generate(parts[index+1]);}
   options.observe?.('response-ready');
   const audio=new Audio();audioReady(audio);
   const played=await playAudioBytes(audio,bytes,'audio/wav',limits.audioSeconds,controller.signal,permitted,stage=>{options.observe?.(stage);if(stage==='playing'&&index===0)onPlaying();},false,options.requestGesture);
   if(!played)return false;
  }
  return true;
 }catch{return false;}
 finally{controller.abort();clearInterval(timer);clearTimeout(deadline);signal.removeEventListener('abort',cancel);for(const event of ['attune-locale-media-cancel','attune-guidance-muted','attune-guidance-cancel'])window.removeEventListener(event,cancel);document.removeEventListener('visibilitychange',check);focus(false);}
}
