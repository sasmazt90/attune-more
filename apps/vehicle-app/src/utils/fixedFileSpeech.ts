import {verifiedClipBytes,type FixedClip} from '../i18n/fixedAudio';
import {observeAppPlayback,speechMuted} from './playbackMeter';

/** Original AAC/M4A playback, independent of MP3-only streaming. No transcoding. */
export async function playFixedSpeech(audio:HTMLAudioElement,clip:FixedClip,signal:AbortSignal,current:()=>boolean,observe:(stage:string)=>void=()=>{},ownsFocus=false):Promise<boolean>{
 const allowed=()=>{try{return !signal.aborted&&current()&&!document.hidden&&!speechMuted()&&Number(localStorage.getItem('attune_hearing_audio_focus')||0)<=Date.now();}catch{return false;}};
 if(!allowed())return false;
 const bytes=await verifiedClipBytes(clip,signal);if(!allowed())return false;
 const mime=clip.mimeType||'audio/mpeg';
 if(!audio.canPlayType(mime))throw Error('APPROVED_AUDIO_FORMAT_UNAVAILABLE');
 const url=URL.createObjectURL(new Blob([bytes],{type:mime}));
 return new Promise(resolve=>{
  let done=false,started=false;
  const owner={};
  const focus=(active:boolean)=>{if(!ownsFocus)return;const e=new Event('attune-stream-focus') as Event & {owner:object;active:boolean};e.owner=owner;e.active=active;window.dispatchEvent(e);};
  const unmeter=observeAppPlayback(audio);
  const finish=(played:boolean)=>{if(done)return;done=true;clearInterval(timer);clearTimeout(deadline);signal.removeEventListener('abort',cancel);document.removeEventListener('visibilitychange',visibility);window.removeEventListener('attune-guidance-muted',visibility);audio.removeEventListener('playing',playing);audio.removeEventListener('ended',ended);audio.removeEventListener('error',cancel);audio.pause();audio.removeAttribute('src');audio.load();unmeter();focus(false);URL.revokeObjectURL(url);resolve(played);};
  const cancel=()=>finish(false),visibility=()=>{if(!allowed())cancel();};
  const playing=()=>{if(!allowed()){cancel();return;}started=true;observe('playing');};
  const ended=()=>{const complete=started&&allowed()&&audio.ended&&Number.isFinite(audio.duration)&&audio.currentTime+.1>=audio.duration;if(complete)observe('ended');finish(complete);};
  const timer=setInterval(visibility,100),deadline=setTimeout(cancel,Math.max(30000,((clip.durationSeconds||20)+8)*1000));
  signal.addEventListener('abort',cancel,{once:true});document.addEventListener('visibilitychange',visibility);window.addEventListener('attune-guidance-muted',visibility);
  audio.addEventListener('playing',playing);audio.addEventListener('ended',ended);audio.addEventListener('error',cancel);
  focus(true);audio.preload='auto';audio.src=url;
  if(!allowed()){cancel();return;}
  try{void audio.play().catch(cancel);}catch{cancel();}
 });
}
