import manifest from '../../public/audio/mental/closing-abc/v1/manifest.json';
import female from '../../public/audio/mental/v1/female-calm-v1-manifest.json';
import {getLanguage,type Language} from '../i18n/core';
import {verifiedClipBytes,type FixedClip} from '../i18n/fixedAudio';
import {playAudioBytes,type PlaybackGestureRequest} from './fixedFileSpeech';
import {mentalSpeechEngine,prepareMentalNeuralSpeech,type PreparedNeuralSpeech} from './mentalNeuralSpeech';

/**
 * Closing bridge: three prepared female-calm-v1 recordings (A thanks, B close, C summary preparation) play while
 * the personalised summary and its speech are prepared. Off unless explicitly enabled at build time:
 *  - 'approved': only recordings the owner approved after listening (none are approved yet);
 *  - 'technical-preview': test environments only; also plays recordings that passed technical checks and still
 *    await owner listening. The page labels this mode.
 * Missing, altered, unapproved or mismatched recordings return null and the existing closing behaviour runs.
 */
export type ClosingBridgeMode='off'|'approved'|'technical-preview';
export const CLOSING_PREVIEW_STATUS='technical-preview-awaiting-owner-listening';
export function closingBridgeMode():ClosingBridgeMode{
 const value=process.env.NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE;
 return value==='approved'||value==='technical-preview'?value:'off';
}

type Manifest={speakerProfile:string;referenceSha256:string;generation:Record<string,number>;joinSilenceMs:number;
 approval:{status:string;ownerApprovedAt:string|null};entries:ClosingClip[]};
export type ClosingClip={assetId:string;language:string;group:string;variantId:string;exactText:string;audioPath:string;
 speakerProfile:string;sha256:string;bytes:number;durationMs:number;approvalStatus:string;ownerApprovedAt:string|null};
export type ClosingSelection={language:Language;clips:ClosingClip[];key:string};
const catalog=manifest as unknown as Manifest;
const GROUPS=['A','B','C'] as const;

const sameGeneration=(a:Record<string,number>,b:Record<string,number>)=>
 Object.keys(a).length===Object.keys(b).length&&Object.entries(a).every(([k,v])=>b[k]===v);

/** Five usable recordings per group for this language, or null. Never partial. */
export function closingBridgeClips(language:Language,mode:ClosingBridgeMode=closingBridgeMode(),source:Manifest=catalog):ClosingClip[][]|null{
 if(mode==='off')return null;
 // Same speaker as the dynamic closing: same profile, reference and generation settings.
 if(source.speakerProfile!=='female-calm-v1'||female.speakerProfile!=='female-calm-v1'||source.referenceSha256!==female.conditioningSha256||!sameGeneration(source.generation,female.generation))return null;
 const approved=(clip:ClosingClip)=>clip.approvalStatus==='approved'&&typeof clip.ownerApprovedAt==='string'&&source.approval.status==='approved';
 const usable=(clip:ClosingClip)=>mode==='approved'?approved(clip):approved(clip)||clip.approvalStatus===CLOSING_PREVIEW_STATUS;
 const groups=GROUPS.map(group=>source.entries.filter(clip=>clip.language===language&&clip.group===group));
 const valid=(clip:ClosingClip)=>clip.speakerProfile==='female-calm-v1'&&usable(clip)&&/^[0-9a-f]{64}$/.test(clip.sha256)
  &&clip.bytes>44&&clip.durationMs>0&&clip.audioPath.startsWith('/audio/mental/closing-abc/v1/'+language+'/female-calm-v1/'+clip.group+'/');
 return groups.every(list=>list.length===5&&list.every(valid))?groups:null;
}

// In memory only: avoids repeating the previous combination in this page. No conversation or health data,
// nothing persisted, gone on reload.
const previous=new Map<Language,string>();
const randomIndex=(size:number)=>crypto.getRandomValues(new Uint32Array(1))[0]%size;
/** One A, one B and one C of the same language, chosen once for a closing. */
export function selectClosingBridge(language:Language,groups:ClosingClip[][],random:(size:number)=>number=randomIndex):ClosingSelection{
 const keyOf=(clips:ClosingClip[])=>clips.map(clip=>clip.variantId).join('-');
 let clips=groups.map(list=>list[random(list.length)]);
 for(let attempt=0;attempt<3&&keyOf(clips)===previous.get(language);attempt++)clips=groups.map(list=>list[random(list.length)]);
 if(keyOf(clips)===previous.get(language)){const c=groups[2];clips=[clips[0],clips[1],c[(c.indexOf(clips[2])+1)%c.length]];}
 const key=keyOf(clips);previous.set(language,key);
 return {language,clips,key};
}

const fixed=(clip:ClosingClip):FixedClip=>({text:clip.exactText,sourceTextSha256:'',url:clip.audioPath,bytes:clip.bytes,sha256:clip.sha256,mimeType:'audio/wav',durationSeconds:clip.durationMs/1000});

function joinPause(ms:number,signal:AbortSignal,live:()=>boolean):Promise<boolean>{
 return new Promise(resolve=>{
  if(signal.aborted||!live()){resolve(false);return;}
  const done=(ok:boolean)=>{clearTimeout(timer);signal.removeEventListener('abort',abort);resolve(ok);};
  const abort=()=>done(false),timer=setTimeout(()=>done(live()),Math.min(300,Math.max(0,ms)));
  signal.addEventListener('abort',abort,{once:true});
 });
}

/** A, B, C in order, each only after the previous one ended, on one reused media element when given. */
export async function playClosingBridge(selection:ClosingSelection,bytes:ArrayBuffer[],signal:AbortSignal,live:()=>boolean,audioReady:(audio:HTMLAudioElement)=>void,observe:(stage:string)=>void,requestGesture?:PlaybackGestureRequest,element?:HTMLAudioElement):Promise<boolean>{
 for(let index=0;index<selection.clips.length;index++){
  if(!live())return false;
  const clip=selection.clips[index],audio=element??new Audio();audioReady(audio);
  const played=await playAudioBytes(audio,bytes[index],'audio/wav',clip.durationMs/1000,signal,live,stage=>observe(clip.group+'-'+stage),false,requestGesture);
  if(!played)return false;
  if(index<selection.clips.length-1&&!await joinPause(catalog.joinSilenceMs,signal,live))return false;
 }
 return live();
}

/**
 * The normal path speaks the analysis' short spokenSummary, never the longer written summaryText. The server
 * validates the full contract (language, address, grounding, no repeated bridge phrases); this mirrors the
 * length/sentence bounds as a second guard. Nothing is shortened: an invalid line is simply not spoken.
 */
export function shortSpokenSummary(value:unknown):string|null{
 if(typeof value!=='string')return null;
 const text=value.normalize('NFC').replace(/\s+/g,' ').trim();
 if(!text||text.length>100||text.split(' ').length>12||/[.!?…]["'”’)]?\s+\S/.test(text))return null;
 return text;
}

export type ClosingState='closingBridge'|'closingSummaryPending'|'closingSpeechPending'|'speaking';
export type ClosingHooks={
 language:Language;
 /** Same guard as the dynamic closing: session epoch, park, consents, voice, service. */
 current:()=>boolean;
 audioReady:(audio:HTMLAudioElement)=>void;
 requestGesture:PlaybackGestureRequest;
 state:(state:ClosingState)=>void;
 timing:(stage:string)=>void;
};
export type ClosingOutcome='played'|'failed'|'cancelled'|'fallback'|'no-spoken-summary';
export type ClosingFlow={
 mode:ClosingBridgeMode;selection:string;
 /** The summary passed every existing check: start preparing its speech now. Only the first call counts. */
 summaryReady:(text:string)=>void;
 /** The analysis produced no usable short spoken summary: after C the closing ends without dynamic speech. */
 summaryUnavailable:()=>void;
 /** After the bridge ends, play the prepared summary. 'fallback': the bridge never started. Only the first call runs. */
 complete:()=>Promise<ClosingOutcome>;
 /** Stops recordings, generation and playback; releases focus. Idempotent. */
 abort:()=>void;
};

/**
 * Starts the bridge at once. Returns null (existing behaviour) when off, unusable, or not the neural female path.
 * Ownership: one controller and one focus owner cover the bridge, the wait and the summary; only one recording or
 * summary part plays at a time; nothing is replayed to fill a wait.
 */
export function startClosingFlow(hooks:ClosingHooks):ClosingFlow|null{
 const mode=closingBridgeMode(),groups=closingBridgeClips(hooks.language,mode);
 if(!groups||mentalSpeechEngine()!=='chatterbox-v3'||getLanguage()!==hooks.language||!hooks.current())return null;
 const selection=selectClosingBridge(hooks.language,groups);
 const controller=new AbortController(),signal=controller.signal;
 const live=()=>!signal.aborted&&hooks.current()&&getLanguage()===hooks.language;
 const owner={},focus=(active:boolean)=>{const event=new Event('attune-stream-focus') as Event&{owner:object;active:boolean};event.owner=owner;event.active=active;window.dispatchEvent(event);};
 focus(true);
 // Created inside the user's Finish tap and reused for every recording and summary part: Android WebView requires a
 // user gesture per new media element (setMediaPlaybackRequiresUserGesture); the unlock stays with this element.
 const element=new Audio();
 let released=false,unavailable=false,text:string|null=null,speech:PreparedNeuralSpeech|null=null,speechReady=false,completion:Promise<ClosingOutcome>|null=null;
 const abort=()=>{if(released)return;released=true;controller.abort();speech?.cancel();focus(false);};
 hooks.timing('closing-bridge-selected');
 let verified:(ok:boolean)=>void=()=>{};
 const assets=new Promise<boolean>(resolve=>{verified=resolve;});
 const bridge=(async():Promise<'played'|'failed'|'cancelled'|'unavailable'>=>{
  let bytes:ArrayBuffer[];
  try{bytes=await Promise.all(selection.clips.map(clip=>verifiedClipBytes(fixed(clip),signal)));}
  catch{verified(false);return live()?'unavailable':'cancelled';}
  verified(live());
  if(!live())return 'cancelled';
  hooks.timing('closing-bridge-verified');hooks.state('closingBridge');
  const played=await playClosingBridge(selection,bytes,signal,live,hooks.audioReady,stage=>hooks.timing('closing-'+stage),hooks.requestGesture,element);
  if(!played)return live()?'failed':'cancelled';
  hooks.timing('closing-bridge-ended');
  // Honest state while waiting; no recording is repeated to cover it.
  if(text===null&&!unavailable)hooks.state('closingSummaryPending');else if(text!==null&&!speechReady)hooks.state('closingSpeechPending');
  return 'played';
 })();
 const summaryReady=(value:string)=>{
  if(text!==null||unavailable||released)return;
  text=value;hooks.timing('closing-summary-text-ready');
  void assets.then(ok=>{
   if(!ok||!live()||speech)return;
   speech=prepareMentalNeuralSpeech(value,signal,live,{speakerProfile:'female-calm-v1',observe:stage=>hooks.timing('closing-summary-'+stage)});
   void speech.firstReady.then(ready=>{speechReady=ready;hooks.timing(ready?'closing-summary-first-ready':'closing-summary-first-failed');});
  });
 };
 const complete=()=>completion??=(async():Promise<ClosingOutcome>=>{
  try{
   const result=await bridge;
   if(result==='unavailable')return 'fallback';
   if(result==='played'&&text===null&&unavailable)return live()?'no-spoken-summary':'cancelled';
   if(result!=='played'||text===null)return result==='cancelled'||!live()?'cancelled':'failed';
   await assets;await Promise.resolve();
   if(!speech)return live()?'failed':'cancelled';
   if(!speechReady)hooks.state('closingSpeechPending');
   else if(!await joinPause(catalog.joinSilenceMs,signal,live))return live()?'failed':'cancelled';
   const played=await speech.play(()=>{hooks.state('speaking');hooks.timing('closing-summary-audio-start');},hooks.audioReady,hooks.requestGesture,element);
   if(played)hooks.timing('closing-summary-complete');
   return played?'played':live()?'failed':'cancelled';
  }finally{abort();}
 })();
 const summaryUnavailable=()=>{if(text!==null||released)return;unavailable=true;hooks.timing('closing-summary-no-spoken-line');};
 return {mode,selection:selection.key,summaryReady,summaryUnavailable,complete,abort};
}
