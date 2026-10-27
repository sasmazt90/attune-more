import raw from '../../public/audio/localized/manifest.json';
import type {Language} from './core';
export type FixedClip={text:string;sourceTextSha256:string;url:string;bytes:number;sha256:string;mimeType?:'audio/mp4'|'audio/mpeg'|'audio/wav';durationSeconds?:number};
export type LocalAudioProfile={id:string;name:string;locale:string;gender:'male'|'female';provider:'local';local:true;guidance:Record<string,FixedClip>;vision:Record<string,FixedClip>};
type AudioMap={version:string;source:string;auditoryAcceptance:'pending';voices:Record<'en'|'de',Record<'male'|'female',LocalAudioProfile>>;hearing:Record<'en'|'de',{url:string;bytes:number;sha256:string}>};
export const localizedAudio=raw as unknown as AudioMap;
export function recordedProfile(language:Language,gender:'male'|'female'='male'){
 return language==='tr'?undefined:localizedAudio.voices[language]?.[gender];
}
export async function verifiedClipBytes(clip:FixedClip,signal:AbortSignal){
 const controller=new AbortController(),abort=()=>controller.abort();
 if(signal.aborted)controller.abort();else signal.addEventListener('abort',abort,{once:true});
 const deadline=setTimeout(abort,15000);
 try{
  if(controller.signal.aborted)throw Error('LOCALIZED_RECORDING_CANCELLED');
  const response=await fetch(clip.url,{signal:controller.signal});if(!response.ok)throw Error('LOCALIZED_RECORDING_UNAVAILABLE');
  const bytes=await response.arrayBuffer();if(bytes.byteLength!==clip.bytes)throw Error('LOCALIZED_RECORDING_SIZE');
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');
  if(hash!==clip.sha256)throw Error('LOCALIZED_RECORDING_HASH');
  if(controller.signal.aborted)throw Error('LOCALIZED_RECORDING_CANCELLED');
  return bytes;
 }finally{clearTimeout(deadline);signal.removeEventListener('abort',abort);}
}
