import {verifiedClipBytes,type FixedClip} from '../i18n/fixedAudio';
import {observeAppPlayback,speechMuted} from './playbackMeter';

/** Present a real user action; return its synchronous UI cleanup. */
export type PlaybackGestureRequest=(play:()=>void)=>()=>void;

/** Original AAC/M4A playback, independent of MP3-only streaming. No transcoding. */
export async function playFixedSpeech(audio:HTMLAudioElement,clip:FixedClip,signal:AbortSignal,current:()=>boolean,observe:(stage:string)=>void=()=>{},ownsFocus=false,requestGesture?:PlaybackGestureRequest):Promise<boolean>{
 const allowed=()=>{try{return !signal.aborted&&current()&&!document.hidden&&!speechMuted()&&Number(localStorage.getItem('attune_hearing_audio_focus')||0)<=Date.now();}catch{return false;}};
 if(!allowed())return false;
 const bytes=await verifiedClipBytes(clip,signal);if(!allowed())return false;
 return playAudioBytes(audio,bytes,clip.mimeType||'audio/mpeg',clip.durationSeconds||20,signal,current,observe,ownsFocus,requestGesture);
}

/** Shared output lifecycle for original clips and newly generated PCM WAV. */
export async function playAudioBytes(audio:HTMLAudioElement,bytes:ArrayBuffer,mime:string,durationSeconds:number,signal:AbortSignal,current:()=>boolean,observe:(stage:string)=>void=()=>{},ownsFocus=false,requestGesture?:PlaybackGestureRequest):Promise<boolean>{
 const allowed=()=>{try{return !signal.aborted&&current()&&!document.hidden&&!speechMuted()&&Number(localStorage.getItem('attune_hearing_audio_focus')||0)<=Date.now();}catch{return false;}};
 if(!allowed())return false;
 if(!audio.canPlayType(mime))throw Error('AUDIO_FORMAT_UNAVAILABLE');
 const url=URL.createObjectURL(new Blob([bytes],{type:mime}));
 return new Promise(resolve=>{
  let done=false,started=false,clearGesture:(()=>void)|undefined;
  const dismissGesture=()=>{clearGesture?.();clearGesture=undefined;};
  const owner={};
  const focus=(active:boolean)=>{if(!ownsFocus)return;const e=new Event('attune-stream-focus') as Event & {owner:object;active:boolean};e.owner=owner;e.active=active;window.dispatchEvent(e);};
  const unmeter=observeAppPlayback(audio);
  const finish=(played:boolean)=>{if(done)return;done=true;dismissGesture();clearInterval(timer);clearTimeout(deadline);signal.removeEventListener('abort',cancel);document.removeEventListener('visibilitychange',visibility);window.removeEventListener('attune-guidance-muted',visibility);audio.removeEventListener('playing',playing);audio.removeEventListener('ended',ended);audio.removeEventListener('error',cancel);audio.pause();audio.removeAttribute('src');audio.load();unmeter();focus(false);URL.revokeObjectURL(url);resolve(played);};
  const cancel=()=>finish(false),visibility=()=>{if(!allowed())cancel();};
  const playing=()=>{if(!allowed()){cancel();return;}dismissGesture();started=true;observe('playing');};
  const ended=()=>{const complete=started&&allowed()&&audio.ended&&Number.isFinite(audio.duration)&&audio.currentTime+.1>=audio.duration;if(complete)observe('ended');finish(complete);};
  const timer=setInterval(visibility,100),deadline=setTimeout(cancel,Math.max(30000,(durationSeconds+8)*1000));
  signal.addEventListener('abort',cancel,{once:true});document.addEventListener('visibilitychange',visibility);window.addEventListener('attune-guidance-muted',visibility);
  audio.addEventListener('playing',playing);audio.addEventListener('ended',ended);audio.addEventListener('error',cancel);
  focus(true);audio.preload='auto';audio.src=url;
  if(!allowed()){cancel();return;}
  const rejected=(error:unknown)=>{
   if(done)return;
   if(!allowed()){cancel();return;}
   if(error instanceof DOMException&&error.name==='NotAllowedError'){
    observe('gesture-required');
    if(requestGesture){if(!clearGesture)clearGesture=requestGesture(attempt);return;}
   }else observe('play-rejected');
   cancel();
  };
  // Called synchronously by the visible button after a blocked autoplay. Keep
  // the same bytes, finite deadline and all live guards; never bypass policy.
  function attempt(){if(done)return;if(!allowed()){cancel();return;}try{void audio.play().catch(rejected);}catch(error){rejected(error);}}
  attempt();
 });
}
