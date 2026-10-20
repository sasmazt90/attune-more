'use client';
import {observeAppPlayback,setSpeechMuted} from './playbackMeter';
import {getLanguage} from '../i18n/core';
import {voicePreference} from '../i18n/voices';
import {systemSpeech} from '../i18n/systemSpeech';
import {apiFetch,localBackend} from './localBackend';
import {recordedProfile,verifiedClipBytes} from '../i18n/fixedAudio';
import {useEffect,useId,useMemo,useRef} from 'react';
import manifest from '../../public/audio/guidance/manifest.json';
import {HEALTH_MODULE_IDS,HEALTH_MODULES} from './healthModules';
import {admittedSkinNeutral} from './skinNeutralAsset';
type Entry={text:string;voice:string;rate:string;pitch:string;url:string;sha256:string;textVersion:string};
export type GuidanceId=keyof typeof manifest.entries;
/** No placeholder/different voice: capture gating is activated only once the
 * fixed neutral clip has actually been admitted to the content-addressed bank. */
export const skinNeutralGuidance=():GuidanceId|undefined=>admittedSkinNeutral((manifest.entries as Record<string,unknown>)['skin-neutral'],manifest.version)?'skin-neutral' as GuidanceId:undefined;
type Job={owner:string;id:GuidanceId;language:ReturnType<typeof getLanguage>;controller:AbortController;audio?:HTMLAudioElement;url?:string;resolve:(played:boolean)=>void;finished:boolean;unmeter?:()=>void};
let current:Job|undefined,pending:Job|undefined,muted=false;
const completed=new Set<string>();
const streams=new Set<object>();
const token=(owner:string,id:GuidanceId)=>owner+':'+getLanguage()+':'+id;
const hearingOwns=()=>Number(localStorage.getItem('attune_hearing_audio_focus')||0)>Date.now();
const healthRoute=()=>typeof window!=='undefined'&&HEALTH_MODULE_IDS.some(id=>location.pathname===HEALTH_MODULES[id].route||location.pathname.startsWith(HEALTH_MODULES[id].route+'/'));
const permitted=(id:GuidanceId)=>healthRoute()&&!/^(cockpit|profile|care|record)-/.test(id);
function unavailable(job:Job){if(!job.controller.signal.aborted)window.dispatchEvent(new CustomEvent('attune-voice-unavailable',{detail:{locale:job.language}}));dispose(job);}
function healthInteraction(event:Event){return event.isTrusted&&healthRoute()&&!(event.target instanceof Element&&event.target.closest('[data-cockpit-header], [data-record-history], [data-health-history], a[href]'));}
function dispose(job:Job,played=false){if(job.finished)return;job.finished=true;job.unmeter?.();job.controller.abort();job.audio?.pause();if(job.audio){job.audio.removeAttribute('src');job.audio.load();}if(job.url)URL.revokeObjectURL(job.url);if(played)completed.add(job.owner+':'+job.language+':'+job.id);if(current===job)current=undefined;if(pending===job)pending=undefined;job.resolve(played);}
export function cancelGuidance(owner?:string){for(const job of [current,pending])if(job&&(!owner||job.owner===owner))dispose(job);}
export function muteGuidance(value:boolean){muted=value;setSpeechMuted(value);if(value)cancelGuidance();window.dispatchEvent(new CustomEvent('attune-guidance-muted',{detail:value}));}
export function speakGuidance(owner:string,id:GuidanceId,repeat=false):Promise<boolean>{
 if(!permitted(id)||muted||streams.size||hearingOwns())return Promise.resolve(false);
 if(!repeat&&completed.has(token(owner,id)))return Promise.resolve(true);
 if(current?.owner===owner&&current.id===id)return Promise.resolve(false);
 cancelGuidance();
 return new Promise(resolve=>{const job:Job={owner,id,language:getLanguage(),controller:new AbortController(),resolve,finished:false};current=job;void load(job);});
}
async function load(job:Job){
 try{
  const e=manifest.entries[job.id] as Entry;
  const preference=voicePreference();
  if(getLanguage()!=='tr'||preference.provider!=='approved'){
   const valid=()=>!job.finished&&current===job&&permitted(job.id)&&!muted&&!streams.size&&!hearingOwns();
   if(preference.provider==='system'){
    const played=await systemSpeech(e.text,job.controller.signal,valid,()=>window.dispatchEvent(new CustomEvent('attune-guidance-event',{detail:{id:job.id,event:'playing',source:'system-synthesis'}})));
    if(played)window.dispatchEvent(new CustomEvent('attune-guidance-event',{detail:{id:job.id,event:'ended',source:'system-synthesis'}}));
    else if(!job.controller.signal.aborted&&valid())window.dispatchEvent(new CustomEvent('attune-voice-unavailable',{detail:{locale:job.language}}));
    return dispose(job,played);
   }
   if(preference.provider==='local'){
    const profile=recordedProfile(getLanguage(),preference.gender==='female'?'female':'male');
    const clip=profile&&profile.id===preference.voiceId?profile.guidance[job.id]:undefined;
    if(!clip)throw Error('LOCALIZED_RECORDING_UNAVAILABLE');
    const bytes=await verifiedClipBytes(clip,job.controller.signal);if(!valid())return dispose(job);
    job.url=URL.createObjectURL(new Blob([bytes],{type:'audio/mpeg'}));job.audio=new Audio(job.url);job.audio.dataset.guidanceId=job.id;job.audio.dataset.guidanceSource='new-local-synthesis';job.unmeter=observeAppPlayback(job.audio);
    job.audio.onended=()=>{window.dispatchEvent(new CustomEvent('attune-guidance-event',{detail:{id:job.id,event:'ended',source:'new-local-synthesis'}}));dispose(job,true);};job.audio.onerror=()=>unavailable(job);
    return await play(job);
   }
   if(preference.provider!=='edge'||!preference.voiceId)return dispose(job);
   const response=await apiFetch(localBackend('/api/guidance/speech'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:job.id,voiceId:preference.voiceId,cloudConsent:true}),signal:job.controller.signal});
   if(!response.ok)throw Error('LOCALIZED_GUIDANCE_UNAVAILABLE');const bytes=await response.arrayBuffer();
   if(!valid()||bytes.byteLength>8*1024*1024)return dispose(job);
   job.url=URL.createObjectURL(new Blob([bytes],{type:'audio/mpeg'}));job.audio=new Audio(job.url);job.audio.dataset.guidanceId=job.id;job.audio.dataset.guidanceSource='edge-synthesis';job.unmeter=observeAppPlayback(job.audio);
   job.audio.onended=()=>{window.dispatchEvent(new CustomEvent('attune-guidance-event',{detail:{id:job.id,event:'ended',source:'edge-synthesis'}}));dispose(job,true);};job.audio.onerror=()=>unavailable(job);
   return await play(job);
  }
  const expected=job.id.startsWith('mental-')?'tr-TR-EmelNeural':'tr-TR-AhmetNeural';
  if(manifest.version!=='guidance-20261009-v1'||e.textVersion!==manifest.version||e.voice!==expected||e.rate!=='-10%'||e.pitch!=='-10Hz')throw Error('GUIDANCE_CONTRACT');
  const response=await fetch(e.url,{signal:job.controller.signal});if(!response.ok)throw Error('GUIDANCE_LOAD');const bytes=await response.arrayBuffer();
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');
  if(digest!==e.sha256)throw Error('GUIDANCE_HASH');
  if(job.finished||current!==job||!permitted(job.id)||muted||streams.size||hearingOwns())return dispose(job);
  job.url=URL.createObjectURL(new Blob([bytes],{type:'audio/mpeg'}));job.audio=new Audio(job.url);job.audio.dataset.guidanceId=job.id;job.unmeter=observeAppPlayback(job.audio);
  job.audio.onended=()=>{window.dispatchEvent(new CustomEvent('attune-guidance-event',{detail:{id:job.id,event:'ended'}}));dispose(job,true);};
  job.audio.onerror=()=>unavailable(job);
  await play(job);
 }catch{unavailable(job);}
}
async function play(job:Job){
 if(job.finished||current!==job||!permitted(job.id)||muted||streams.size||hearingOwns())return dispose(job);
 try{await job.audio!.play();pending=undefined;window.dispatchEvent(new CustomEvent('attune-guidance-event',{detail:{id:job.id,event:'playing'}}));}
 catch(error){if(job.finished)return;if((error as DOMException).name==='NotAllowedError'){pending=job;window.dispatchEvent(new CustomEvent('attune-guidance-event',{detail:{id:job.id,event:'interaction-required'}}));}else dispose(job);}
}
if(typeof window!=='undefined'){
 window.addEventListener('attune-stream-focus',event=>{const e=event as Event & {owner:object;active:boolean};if(e.active){streams.add(e.owner);cancelGuidance();}else streams.delete(e.owner);});
 window.addEventListener('attune-guidance-cancel',()=>cancelGuidance());
 window.addEventListener('attune-audio-focus',()=>{if(hearingOwns())cancelGuidance();});
 const retry=(e:Event)=>{if(!healthInteraction(e)){if(e.isTrusted)cancelGuidance();return;}if(pending)void play(pending);};
 window.addEventListener('pointerdown',retry,{capture:true});window.addEventListener('keydown',retry,{capture:true});
}
/** One session per mounted route. Issues must be stable 900ms and resolve 1200ms before repeating. */
export function useGuidance(owner:string,enabled=true){
 const key=owner+useId();const available=useRef(enabled);available.current=enabled;
 const api=useMemo(()=>{
  let phaseKey='',phaseId:GuidanceId|undefined,issueKey='',issuePlayed='',timer:ReturnType<typeof setTimeout>|undefined,clearTimer:ReturnType<typeof setTimeout>|undefined,generation=0;
  let failed:{id:GuidanceId;issue?:string;generation:number}|undefined;
  let attempting=false;
  const attempt=async(id:GuidanceId,issue?:string)=>{
   if(attempting||!available.current)return false;
   const run=generation;attempting=true;failed=undefined;
   const played=await speakGuidance(key,id,true);
   if(run===generation){attempting=false;if(played){if(issue===issueKey)issuePlayed=issue||'';}else if(available.current&&permitted(id))failed={id,issue,generation:run};}
   return played;
  };
  const reset=()=>{generation++;attempting=false;failed=undefined;cancelGuidance(key);};
  return {
   say:(id:GuidanceId,repeat=true)=>available.current?speakGuidance(key,id,repeat):Promise.resolve(false),
   phase:(phase:string,id?:GuidanceId)=>{if(phase===phaseKey)return;phaseKey=phase;phaseId=id;issueKey='';issuePlayed='';if(timer)clearTimeout(timer);if(clearTimer){clearTimeout(clearTimer);clearTimer=undefined;}reset();if(id&&available.current)void attempt(id);},
   issue:(code:string,id?:GuidanceId)=>{if(code&&code===issueKey){if(clearTimer){clearTimeout(clearTimer);clearTimer=undefined;}return;}if(!code&&clearTimer)return;if(timer)clearTimeout(timer);if(clearTimer)clearTimeout(clearTimer);if(!code){clearTimer=setTimeout(()=>{clearTimer=undefined;if(issueKey)reset();issueKey='';issuePlayed='';},1200);return;}if(code===issuePlayed)return;reset();issueKey=code;timer=setTimeout(()=>{timer=undefined;if(issueKey===code&&id&&available.current)void attempt(id,code);},900);},
   repeat:()=>{reset();return phaseId?attempt(phaseId):Promise.resolve(false);},
   retryFailed:(event:Event)=>{if(healthInteraction(event)&&failed&&failed.generation===generation&&!muted&&!streams.size&&!hearingOwns())void attempt(failed.id,failed.issue);},
   cancel:()=>{if(timer)clearTimeout(timer);if(clearTimer)clearTimeout(clearTimer);reset();},
  };
 },[key]);
 useEffect(()=>{if(!enabled)api.cancel();return()=>api.cancel();},[api,enabled]);
 useEffect(()=>{window.addEventListener('pointerdown',api.retryFailed);window.addEventListener('keydown',api.retryFailed);return()=>{window.removeEventListener('pointerdown',api.retryFailed);window.removeEventListener('keydown',api.retryFailed);};},[api]);
 return api;
}
export function qualityGuidance(text:string):GuidanceId|undefined{
 if(/ayrıntı|yaklaş|detay/i.test(text))return 'quality-near';if(/uzak|kadraj|alın ve çene/i.test(text))return 'quality-far';
 if(/ışık|parla|yansı/i.test(text))return 'quality-light';if(/net|sabit|hareket/i.test(text))return 'quality-blur';if(/yüz.*algı|yüz.*gör/i.test(text))return 'quality-face';
 if(/dil|dudak|diş.*gör|ağzınızı/i.test(text))return 'dental-teeth';return undefined;
}
