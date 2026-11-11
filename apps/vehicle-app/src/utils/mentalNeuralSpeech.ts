import {getLanguage,getLocale,VOICE_EVENT} from '../i18n/core';
import {captureWhileLocked,languageSwitchLocked} from '../i18n/locks';
import {playAudioBytes,prepareAudioBytes,type PlayableAudio,type PlaybackGestureRequest} from './fixedFileSpeech';
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
export type NeuralSpeechOptions={requestGesture?:PlaybackGestureRequest;observe?:(stage:string)=>void;speakerProfile?:'official-default'|'female-calm-v1';wholeReply?:boolean;preparedElement?:HTMLAudioElement;onSafetyRefusal?:()=>void};
/** Speech whose generation has started but whose playback is a separate, single step. */
export type PreparedNeuralSpeech={
 /** First part ready; wholeReply requires the entire reply decoded/prebuffered. Never rejects. */
 firstReady:Promise<boolean>;
 /** Plays every part in order; a later part keeps generating while an earlier one plays. Only the first call plays.
  * An element passed in is reused for every part (keeps an Android WebView gesture unlock); otherwise each part gets a new one. */
 play:(onPlaying:()=>void,audioReady:(audio:HTMLAudioElement)=>void,requestGesture?:PlaybackGestureRequest,element?:HTMLAudioElement)=>Promise<boolean>;
 /** Stops generation and playback and releases listeners/focus. Idempotent. */
 cancel:()=>void;
};
/** Dynamic response text only. Authentication is handled by the same-origin server. */
export async function mentalNeuralSpeech(text:string,signal:AbortSignal,current:()=>boolean,onPlaying:()=>void,audioReady:(audio:HTMLAudioElement)=>void,options:NeuralSpeechOptions={}):Promise<boolean>{
 return prepareMentalNeuralSpeech(text,signal,current,options).play(onPlaying,audioReady,options.requestGesture);
}
/**
 * Start generating now and play later. Used where earlier output (for example a prepared recording) is still
 * playing: generation overlaps it, playback never does. Playback has the same guards as mentalNeuralSpeech.
 */
export function prepareMentalNeuralSpeech(text:string,signal:AbortSignal,current:()=>boolean,options:NeuralSpeechOptions={}):PreparedNeuralSpeech{
 const language=getLanguage(),locale=getLocale(),controller=new AbortController();
 const permitted=()=>{try{return !signal.aborted&&!controller.signal.aborted&&current()&&!speechMuted()&&!document.hidden&&getLanguage()===language&&mentalSpeechEngine()==='chatterbox-v3'&&Number(localStorage.getItem('attune_hearing_audio_focus')||0)<=Date.now();}catch{return false;}};
 const check=()=>{if(!permitted())controller.abort();},cancel=()=>controller.abort();
 if(!permitted())return {firstReady:Promise.resolve(false),play:async()=>false,cancel:()=>{}};
 signal.addEventListener('abort',cancel,{once:true});
 for(const event of ['attune-locale-media-cancel','attune-guidance-muted','attune-guidance-cancel'])window.addEventListener(event,cancel);
 document.addEventListener('visibilitychange',check);
 const timer=setInterval(check,100);let deadline=setTimeout(cancel,limits.generationMilliseconds);
 // Claim focus during generation too, preventing fixed guidance overlap.
 const owner={},focus=(active:boolean)=>{const event=new Event('attune-stream-focus') as Event&{owner:object;active:boolean};event.owner=owner;event.active=active;window.dispatchEvent(event);};
 focus(true);
 let released=false,played=false,whole:PlayableAudio|null=null;
 const release=()=>{if(released)return;released=true;controller.abort();whole?.cancel();clearInterval(timer);clearTimeout(deadline);signal.removeEventListener('abort',cancel);for(const event of ['attune-locale-media-cancel','attune-guidance-muted','attune-guidance-cancel'])window.removeEventListener(event,cancel);document.removeEventListener('visibilitychange',check);focus(false);};
 // Null means this part cannot be played, for whatever reason. It never rejects, because the next part is generated
 // while this one plays and nothing is waiting on it yet.
 const generate=async(part:string,index:number):Promise<ArrayBuffer|null>=>{
  try{
   options.observe?.('segment-request-'+index);
   const response=await fetch('/api/mental-neural-speech',{method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',body:JSON.stringify({text:part,language,speechConsent:true,...(options.speakerProfile?{speakerProfile:options.speakerProfile}:{})}),signal:controller.signal});
   // Safety/auth refusals invalidate the shared turn before any audio/profile header validation.
   if([401,403,409].includes(response.status)){release();options.onSafetyRefusal?.();return null;}
   if(options.speakerProfile&&response.headers.get('x-tts-speaker-profile')!==options.speakerProfile)return null;
   if(!response.ok||!permitted()||response.headers.get('content-type')?.split(';')[0]!=='audio/wav'||response.headers.get('x-tts-source')!=='chatterbox-multilingual-v3'||response.headers.get('x-tts-locale')!==locale)return null;
   options.observe?.('segment-headers-'+index);
   const reader=response.body?.getReader();if(!reader)return null;const chunks:Uint8Array[]=[];let size=0;
   while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>8*1024*1024){await reader.cancel();return null;}chunks.push(value);}
   if(size<=44||!permitted())return null;
   options.observe?.('segment-ready-'+index);
   const bytes=new Uint8Array(size);let at=0;for(const chunk of chunks){bytes.set(chunk,at);at+=chunk.length;}
   return bytes.buffer;
  }catch{return null;}
 };
 const parts=options.wholeReply?[text]:speechParts(text),results:Promise<ArrayBuffer|null>[]=[];
 // One part generates at a time. A part starts as soon as the previous one is ready, so the next part is
 // generated while the current one plays (or while it waits to be played).
 const start=(index:number)=>{
  results[index]=generate(parts[index],index).then(bytes=>{
   if(!bytes||!permitted())return null;
   // A part's generation budget ends here; playback has its own bounded deadline.
   // Keep live mute/consent/locale/session/motion and abort observation active.
   clearTimeout(deadline);
   if(index+1<parts.length){deadline=setTimeout(cancel,limits.generationMilliseconds);start(index+1);}
   return bytes;
  });
 };
 start(0);
 const firstReady=results[0].then(async bytes=>{if(!bytes||!permitted())return false;if(!options.wholeReply)return true;whole=await prepareAudioBytes(bytes,'audio/wav',limits.audioSeconds,controller.signal,permitted,options.preparedElement);return !!whole&&permitted();});
 const play=async(onPlaying:()=>void,audioReady:(audio:HTMLAudioElement)=>void,requestGesture?:PlaybackGestureRequest,element?:HTMLAudioElement)=>{
  if(played||released)return false;
  played=true;
  try{
   if(options.wholeReply){if(!await firstReady||!whole||!permitted())return false;audioReady(whole.audio);return await whole.play(stage=>{options.observe?.(stage);if(stage==='playing')onPlaying();},requestGesture);}
   for(let index=0;index<parts.length;index++){
    const bytes=await results[index];
    if(!bytes||!permitted())return false;
    options.observe?.('response-ready');
    const audio=element??new Audio();audioReady(audio);
    const done=await playAudioBytes(audio,bytes,'audio/wav',limits.audioSeconds,controller.signal,permitted,stage=>{options.observe?.(stage);if(stage==='playing'&&index===0)onPlaying();},false,requestGesture);
    if(!done)return false;
   }
   return true;
  }catch{return false;}
  finally{release();}
 };
 return {firstReady,play,cancel:release};
}
