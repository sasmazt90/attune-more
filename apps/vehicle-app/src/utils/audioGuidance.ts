'use client';
import {setSpeechMuted} from './playbackMeter';
import {getLanguage} from '../i18n/core';
import {approvedClip} from '../i18n/approvedAudio';
import {playFixedSpeech} from './fixedFileSpeech';
import {useEffect,useId,useMemo,useRef} from 'react';
import manifest from '../../public/audio/guidance/manifest.json';
import {HEALTH_MODULE_IDS,HEALTH_MODULES,type HealthModule} from './healthModules';
export type GuidanceId=keyof typeof manifest.entries;
export const skinNeutralGuidance=():GuidanceId|undefined=>approvedClip(getLanguage(),'skin','guidance:skin-neutral')?'skin-neutral':undefined;
type Job={owner:string;id:GuidanceId;language:ReturnType<typeof getLanguage>;module:HealthModule;controller:AbortController;audio?:HTMLAudioElement;resolve:(played:boolean)=>void;finished:boolean};
let current:Job|undefined,pending:Job|undefined,muted=false;
const completed=new Set<string>();
const streams=new Set<object>();
const activeModule=()=>HEALTH_MODULE_IDS.find(id=>location.pathname===HEALTH_MODULES[id].route||location.pathname.startsWith(HEALTH_MODULES[id].route+'/'));
const token=(owner:string,id:GuidanceId)=>owner+':'+getLanguage()+':'+activeModule()+':'+id;
const hearingOwns=()=>Number(localStorage.getItem('attune_hearing_audio_focus')||0)>Date.now();
const healthRoute=()=>typeof window!=='undefined'&&!!activeModule();
const permitted=(id:GuidanceId)=>healthRoute()&&!document.hidden&&!/^(cockpit|profile|care|record)-/.test(id);
function unavailable(job:Job){if(!job.controller.signal.aborted)window.dispatchEvent(new CustomEvent('attune-voice-unavailable',{detail:{locale:job.language}}));dispose(job);}
function healthInteraction(event:Event){return event.isTrusted&&healthRoute()&&!(event.target instanceof Element&&event.target.closest('[data-cockpit-header], [data-record-history], [data-health-history], a[href]'));}
function dispose(job:Job,played=false){if(job.finished)return;job.finished=true;job.controller.abort();if(played)completed.add(job.owner+':'+job.language+':'+job.module+':'+job.id);if(current===job)current=undefined;if(pending===job)pending=undefined;job.resolve(played);}
export function cancelGuidance(owner?:string){for(const job of [current,pending])if(job&&(!owner||job.owner===owner))dispose(job);}
export function muteGuidance(value:boolean){muted=value;setSpeechMuted(value);if(value)cancelGuidance();window.dispatchEvent(new CustomEvent('attune-guidance-muted',{detail:value}));}
export function speakGuidance(owner:string,id:GuidanceId,repeat=false):Promise<boolean>{
 const targetModule=activeModule();
 if(!targetModule||!permitted(id)||muted||streams.size||hearingOwns())return Promise.resolve(false);
 if(!repeat&&completed.has(token(owner,id)))return Promise.resolve(true);
 if(current?.owner===owner&&current.id===id)return Promise.resolve(false);
 cancelGuidance();
 return new Promise(resolve=>{const job:Job={owner,id,language:getLanguage(),module:targetModule,controller:new AbortController(),resolve,finished:false};current=job;void load(job);});
}
async function load(job:Job){
 try{
  const clip=approvedClip(job.language,job.module,'guidance:'+job.id);
  if(!clip)throw Error('APPROVED_MODULE_RECORDING_UNAVAILABLE');
  const valid=()=>!job.finished&&current===job&&getLanguage()===job.language&&activeModule()===job.module&&permitted(job.id)&&!muted&&!streams.size&&!hearingOwns();
  const audio=new Audio();job.audio=audio;audio.dataset.guidanceId=job.id;audio.dataset.guidanceSource='user-approved-recordings';audio.dataset.recordingId=clip.recordingId;
  const played=await playFixedSpeech(audio,clip,job.controller.signal,valid,event=>window.dispatchEvent(new CustomEvent('attune-guidance-event',{detail:{id:job.id,event,source:'user-approved-recordings',recordingId:clip.recordingId,voice:clip.voice,locale:clip.applicationLocale}})));
  if(!played&&!job.controller.signal.aborted&&valid())unavailable(job);else dispose(job,played);
 }catch{unavailable(job);}
}
if(typeof window!=='undefined'){
 window.addEventListener('attune-stream-focus',event=>{const e=event as Event & {owner:object;active:boolean};if(e.active){streams.add(e.owner);cancelGuidance();}else streams.delete(e.owner);});
 for(const event of ['attune-guidance-cancel','attune-locale-media-cancel','popstate','pagehide'])window.addEventListener(event,()=>cancelGuidance());
 document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelGuidance();});
 window.addEventListener('attune-audio-focus',()=>{if(hearingOwns())cancelGuidance();});
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
 if(/birleştir/i.test(text))return 'dental-bite';
 if(/dil|dudak|diş.*gör|ağzınızı/i.test(text))return 'dental-teeth';return undefined;
}
