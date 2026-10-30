import manifest from '../../public/audio/mental/v1/female-calm-v1-manifest.json';
import {getLanguage} from '../i18n/core';
import {playFixedSpeech,type PlaybackGestureRequest} from './fixedFileSpeech';

export type StructuredState={language:string;speakerProfile:'female-calm-v1';listenOnly:boolean;turn:number;seed?:number;selections?:string[]}&Record<string,unknown>;
export const structuredConversationEnabled=()=>process.env.NEXT_PUBLIC_MENTAL_CONVERSATION_ENGINE==='structured-v1';

/** Exact approved scripts/bytes only. Missing assets never trigger synthesis. */
export async function playPreparedMental(text:string,ids:string[],signal:AbortSignal,current:()=>boolean,audioReady:(audio:HTMLAudioElement)=>void,observe:(stage:string)=>void,requestGesture?:PlaybackGestureRequest){
 const language=getLanguage();
 const allowed=()=>current()&&getLanguage()===language&&!signal.aborted;
 const clips=ids.map(id=>manifest.entries.find(e=>e.assetId===id));
 if(!ids.length||clips.some(e=>!e||e.language!==language||e.speakerProfile!=='female-calm-v1'||e.approvalStatus!=='approved'||!e.sha256||!e.bytes||!e.durationMs)||clips.map(e=>e!.exactScript).join(' ')!==text||manifest.joinApprovalStatus!=='approved')return false;
 // Hold focus for the complete utterance, including the calibrated join.
 const owner={},focus=(active:boolean)=>{const event=new Event('attune-stream-focus') as Event&{owner:object;active:boolean};event.owner=owner;event.active=active;window.dispatchEvent(event);};
 focus(true);
 try{
  for(let i=0;i<clips.length;i++){
   if(!allowed())return false;
   const clip=clips[i]!,audio=new Audio();audioReady(audio);
   const played=await playFixedSpeech(audio,{text:clip.exactScript,sourceTextSha256:'',url:clip.audioPath,sha256:String(clip.sha256),bytes:Number(clip.bytes),mimeType:'audio/wav',durationSeconds:Number(clip.durationMs)/1000},signal,allowed,observe,false,requestGesture);
   if(!played)return false;
   if(i<clips.length-1&&!await joinPause(manifest.joinSilenceMs,signal,allowed))return false;
  }
  return allowed();
 }finally{focus(false);}
}

function joinPause(ms:number,signal:AbortSignal,current:()=>boolean):Promise<boolean>{
 return new Promise(resolve=>{
  if(signal.aborted||!current()){resolve(false);return;}
  const done=(ok:boolean)=>{clearTimeout(timer);signal.removeEventListener('abort',abort);resolve(ok);};
  const abort=()=>done(false),timer=setTimeout(()=>done(current()),Math.min(300,Math.max(0,ms)));
  signal.addEventListener('abort',abort,{once:true});
 });
}
