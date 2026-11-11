import manifest from '../../public/audio/mental/v1/female-calm-v1-manifest.json';
import {getLanguage} from '../i18n/core';
import {verifiedClipBytes} from '../i18n/fixedAudio';
import {playFixedSpeech,prepareAudioBytes,type PlaybackGestureRequest} from './fixedFileSpeech';

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

/** Only the selected small A+B group is fetched, hash checked and prebuffered, in parallel at T0. */
export async function prepareMentalRecording(text:string,ids:string[],signal:AbortSignal,current:()=>boolean,elements?:HTMLAudioElement[]){
 const language=getLanguage(),clips=ids.map(id=>manifest.entries.find(e=>e.assetId===id));
 if(!ids.length||ids.length>2||manifest.joinApprovalStatus!=='approved'||clips.some(e=>!e||e.language!==language||e.speakerProfile!=='female-calm-v1'||e.approvalStatus!=='approved')||clips.map(e=>e!.exactScript).join(' ')!==text)return null;
 const allowed=()=>!signal.aborted&&current()&&getLanguage()===language;
 const prepared=await Promise.all(clips.map(async (clip,index)=>{
  try{const e=clip!,bytes=await verifiedClipBytes({text:e.exactScript,sourceTextSha256:'',url:e.audioPath,sha256:String(e.sha256),bytes:Number(e.bytes)},signal);
   return allowed()?await prepareAudioBytes(bytes,'audio/wav',Number(e.durationMs)/1000,signal,allowed,elements?.[index]):null;
  }catch{return null;}
 }));
 const cancel=()=>prepared.forEach(p=>p?.cancel());
 if(prepared.some(p=>!p)||!allowed()){cancel();return null;}
 let used=false;
 return {cancel,play:async(audioReady:(audio:HTMLAudioElement)=>void,observe:(stage:string)=>void,requestGesture?:PlaybackGestureRequest)=>{
  if(used)return false;used=true;
  const owner={},focus=(active:boolean)=>{const e=new Event('attune-stream-focus') as Event&{owner:object;active:boolean};e.owner=owner;e.active=active;window.dispatchEvent(e);};focus(true);
  try{for(let i=0;i<prepared.length;i++){
   if(!allowed())return false;const p=prepared[i]!;audioReady(p.audio);
   if(!await p.play(stage=>observe(`prepared-${i}-${stage}`),requestGesture))return false;
   if(i<prepared.length-1&&!await joinPause(manifest.joinSilenceMs,signal,allowed))return false;
  }return allowed();}finally{cancel();focus(false);}
 }};
}
export const hybridConversationEnabled=()=>process.env.NEXT_PUBLIC_MENTAL_CONVERSATION_ENGINE==='hybrid-3s-v1';
