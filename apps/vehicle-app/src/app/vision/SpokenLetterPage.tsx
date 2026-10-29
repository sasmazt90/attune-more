'use client';
import {useLocaleSwitchLock} from '../../i18n/useLocaleSwitchLock';
import {getLanguage,getLocale} from '../../i18n/core';
import {apiFetch as fetch} from '../../utils/localBackend';
import {useTranslations} from '../../i18n/LanguageProvider';

import {HealthStartCard,HEALTH_START_ACTION} from '../../components/HealthStartCard';
import {speechMuted} from '../../utils/playbackMeter';
import {serviceAllowed} from '../../utils/serviceConsent';
import {HEALTH_MODULES} from '../../utils/healthModules';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useVehicle } from '../../context/VehicleContext';
import { AccessibleDialog } from '../../components/AccessibleDialog';
import { InformationButton } from '../../components/InformationButton';
import { RecordHistory } from '../../components/RecordHistory';
import { LetterVisionResult } from '../../components/LetterVisionResult';
import { LetterStimulus } from '../../components/LetterStimulus';
import { CameraPreview } from '../../components/CameraPreparation';
import { VisionInference } from '../../utils/visionInference';
import type { VisionEvidence } from '../../utils/visionTracking';
import { VisionFlow, eyeInstruction } from '../../utils/visionFlow';
import { LETTER_PATHS, LETTER_PROTOCOL, LETTER_METHOD, answerTransform, describeAnswer, LetterResult, RenderedSymbolGeometry, SpokenLetterSession, letterConditionFailure, parseLetterAnswer, respondToVisibleLetter, isLetterInstructionEcho } from '../../utils/spokenVision';
import {VisionJourney} from '../../components/vision/VisionJourney';
import {VISION_ANSWER_SETTLE_MS,visionRecognitionChoice,visionRecognitionConfidence,type VisionComponentConfidence} from '../../utils/visionSpeechTurn';
import {eyeObservation} from '../../utils/visionEyeState';
import { VisionAnswerMemory } from '../../utils/visionAnswerMemory';
import { appendHealthRecord } from '../../utils/healthRecords';
import { isCameraAllowed, isMicrophoneAllowed, isVisionSavingAllowed, isDemoMode } from '../../utils/attuneMode';
import { VisionResponseGate } from '../../utils/visionResponseGate';
import { VISION_FRAME_CLASS } from '../../components/VisionFrame';
import {approvedClip} from '../../i18n/approvedAudio';
import {playFixedSpeech} from '../../utils/fixedFileSpeech';
const TEXT:Record<string,string>={face:'Yüzünüzü kamera görüntüsünde tutun.',framing:'Yüzünüzün tamamını kamera görüntüsünde tutun.',pose:'Başınızı biraz ekrana çevirin; harf alanına bakabilirsiniz.',light:'Açık gözünüzün bulunduğu tarafı aydınlatın.',bright:'Yüzünüzdeki parlamayı azaltın.',blur:'Açık göz çevresinde netlik yetersiz. Kamera netliğini kontrol edin.',preparing:'İki göz açık: başlangıç konumu öğreniliyor.',recede:'Biraz geri çekilin.',approach:'Biraz yaklaşın.','distance-unknown':'Mesafeyi güvenilir izleyemiyorum; yüzünüzü görünür tutun.',camera:'Kamera görüntüsü güncel değil.',eye:'Test edilen göz açık; diğer göz kapalı veya örtülü olmalı.',uncertain:'Göz örtüsünü veya göz açıklığını kontrol edemiyorum.','both-eyes':'İki göz de kapalı veya örtülü. Test edilen gözünüzü açın.','test-eye':'Test edilen gözünüzü açın; diğer gözü kapatın veya örtün.','cover-other':'Diğer gözünüzü kapatın veya örtün.'};
const EYE_TEXT={EYE_OPEN:'açık',EYE_CLOSED:'kapalı',EYE_COVERED_BY_HAND:'elle örtülü',EYE_OCCLUDED_BY_OBJECT:'nesneyle örtülü',EYE_NOT_VISIBLE_OR_UNCERTAIN:'değerlendirilemiyor',FACE_NOT_ALIGNED:'yüz hizası bekleniyor',CAMERA_UNAVAILABLE:'kamera bekleniyor'};
export default function SpokenLetterPage(){
 const {text:i18nText,node:i18nNode}=useTranslations();
 const {isParked,syncStatus}=useVehicle(),parked=useRef(isParked);parked.current=isParked;
 const [,redraw]=useState(0),[ready,setReady]=useState(false),[error,setError]=useState(''),[dialog,setDialog]=useState<string|null>(null),[result,setResult]=useState<LetterResult|null>(null);
 const [evidence,setEvidence]=useState<VisionEvidence|null>(null),[voice,setVoice]=useState<'quiet'|'loading'|'playing'|'listening'|'failed'>('quiet');
 const [answerNotice,setAnswerNotice]=useState('');
 const answerDescription=describeAnswer;
 const video=useRef<HTMLVideoElement>(null),canvas=useRef<HTMLCanvasElement>(null),symbol=useRef<SVGSVGElement>(null),flow=useRef(new VisionFlow());
 const r=useRef({mounted:false,epoch:0,active:false,recognitionFailures:0,pendingPrompt:null as string|null,silenceReminders:new Set<string>(),speechActive:false,starting:false,stream:null as MediaStream|null,engine:null as VisionInference|null,raf:0,timer:null as ReturnType<typeof setInterval>|null,session:null as SpokenLetterSession|null,evidence:null as VisionEvidence|null,recognition:null as any,listeningStarted:false,answerTimer:null as ReturnType<typeof setTimeout>|null,settleAnswer:null as (()=>void)|null,audio:null as HTMLAudioElement|null,controller:null as AbortController|null,cancelSpeech:null as (()=>void)|null,url:null as string|null,restart:null as ReturnType<typeof setTimeout>|null,voiceGeneration:0,voiceTimeout:null as ReturnType<typeof setTimeout>|null,muted:false,modal:false,fault:'',faultSince:0,announcedFault:'',answerMemory:new VisionAnswerMemory(),clarifications:0,saving:false,mainInstructionGiven:false,nextPrompt:0,lastPrompt:'',prompted:new Set<string>(),conditionGate:new VisionResponseGate(),previewPoints:undefined as VisionEvidence['alignment']['landmarks']});
 useLocaleSwitchLock('vision',r.current.active&&flow.current.stage!=='user-paused');
 const actions=useRef({inspect:()=>{},receive:(_text:string,_confidence:number,_id:string,_key:string,_components?:VisionComponentConfidence)=>{},listen:()=>{},stop:()=>{},measure:()=>null as RenderedSymbolGeometry|null,prompt:(_code?:string)=>{},current:(_epoch:number):boolean=>false,canPresent:():boolean=>false,renderError:()=>{},pause:()=>{},silence:()=>{},timing:(_name:string)=>{}});
 const refresh=()=>redraw(v=>v+1);
 const stage=useCallback((next:Parameters<VisionFlow['transition']>[0],reason='')=>{flow.current.transition(next,reason);redraw(v=>v+1);},[]);
 function current(epoch:number){return serviceAllowed('vision')&&r.current.mounted&&r.current.active&&r.current.epoch===epoch&&parked.current&&isCameraAllowed()&&isMicrophoneAllowed();}
 function timing(name:string){window.dispatchEvent(new CustomEvent('attune-vision-speech-timing',{detail:{stage:name,atMs:performance.now(),clock:'browser-performance',presentationId:flow.current.presentationId}}));}
 function abortRecognition(){const a=r.current,old=a.recognition;a.recognition=null;a.listeningStarted=false;a.speechActive=false;if(a.restart)clearTimeout(a.restart);a.restart=null;try{old?.abort();}catch{}}
 function stopSpeech(){const a=r.current;a.voiceGeneration++;if(a.voiceTimeout)clearTimeout(a.voiceTimeout);a.voiceTimeout=null;a.controller?.abort();a.controller=null;a.cancelSpeech?.();a.cancelSpeech=null;if(a.audio){a.audio.onplaying=a.audio.onended=a.audio.onerror=null;a.audio.pause();a.audio.removeAttribute('src');a.audio.load();a.audio=null;}if(a.url)URL.revokeObjectURL(a.url);a.url=null;}
 function stopVoice(){if(r.current.answerTimer)clearTimeout(r.current.answerTimer);r.current.answerTimer=null;r.current.settleAnswer=null;abortRecognition();stopSpeech();if(r.current.mounted)setVoice('quiet');}
 function stop(){const a=r.current;a.epoch++;a.active=false;stopVoice();cancelAnimationFrame(a.raf);if(a.timer)clearInterval(a.timer);a.timer=null;a.stream?.getTracks().forEach(t=>t.stop());a.stream=null;a.engine?.close();a.engine=null;a.session=null;a.evidence=null;a.previewPoints=undefined;if(canvas.current)delete canvas.current.dataset.visionEvidence;a.modal=false;a.pendingPrompt=null;a.silenceReminders.clear();a.answerMemory.clear();a.mainInstructionGiven=false;a.nextPrompt=0;a.lastPrompt='';a.prompted.clear();a.conditionGate=new VisionResponseGate();if(video.current)video.current.srcObject=null;flow.current.reset();if(a.mounted){setAnswerNotice('');setEvidence(null);refresh();}}
 useEffect(()=>{const mute=()=>{if(speechMuted()&&r.current.active){stopSpeech();stage('user-paused','Seslendirme kapalı. Üst çubuktaki hoparlörü açıp devam edin.');abortRecognition();}};window.addEventListener('attune-guidance-muted',mute);return()=>window.removeEventListener('attune-guidance-muted',mute);},[stage]);
 useEffect(()=>{
  let language=getLanguage();
  const changed=()=>{const next=getLanguage(),localeChanged=next!==language;language=next;if(!r.current.active)return;
   if(flow.current.stage!=='user-paused'){actions.current.pause();return;}
   if(localeChanged){abortRecognition();setVoice('quiet');if(!speechMuted()&&!document.hidden)actions.current.listen();}
  };
  window.addEventListener('attune-locale-media-cancel',changed);return()=>window.removeEventListener('attune-locale-media-cancel',changed);
 },[]);
 function measureSymbol():RenderedSymbolGeometry|null{
  const svg=symbol.current,path=svg?.querySelector('path');if(!svg||!path||!flow.current.letterVisible||document.hidden)return null;
  const b=svg.getBoundingClientRect(),p=path.getBoundingClientRect(),style=getComputedStyle(svg),area=svg.parentElement!.getBoundingClientRect(),stroke=Number.parseFloat(getComputedStyle(path).strokeWidth)*b.width/svg.viewBox.baseVal.width;
  if(style.visibility!=='visible'||Number(style.opacity)===0||b.width<=0||b.height<=0||p.width<=0||p.height<=0||b.left<area.left||b.right>area.right+.5||b.top<area.top||b.bottom>area.bottom+.5||b.left<0||b.top<0||b.right>innerWidth+1||b.bottom>innerHeight+1)return null;
  const matrix=path.getScreenCTM();if(!matrix)return null;const length=path.getTotalLength();for(let i=0;i<=8;i++){const point=path.getPointAtLength(length*i/8),screenPoint=new DOMPoint(point.x,point.y).matrixTransform(matrix),hit=document.elementFromPoint(screenPoint.x,screenPoint.y);if(!hit||!svg.contains(hit))return null;}
  return {viewportWidthCssPx:b.width,viewportHeightCssPx:b.height,pathWidthCssPx:p.width,pathHeightCssPx:p.height,strokeWidthCssPx:stroke,measuredAt:performance.now(),method:'dom-svg-css-pixels'};
 }
 async function speak(code:string,onEnded:()=>void){
  const a=r.current,epoch=a.epoch;if(!current(epoch)||a.muted)return;if(speechMuted()){stage('user-paused','Seslendirme kapalı. Üst çubuktaki hoparlörü açıp devam edin.');return;}abortRecognition();stopSpeech();const generation=a.voiceGeneration,token=flow.current.token(),controller=new AbortController();a.controller=controller;
  const valid=()=>current(epoch)&&a.voiceGeneration===generation&&a.controller===controller&&flow.current.matches(token);
  const fail=()=>{if(!valid())return;stopVoice();stage('error','Sesli yönerge kullanılamıyor. Tekrar deneyin.');setVoice('failed');setError('Seçilen dilde yönerge oynatılamadı; yanıt dinlenmedi ve puanlanmadı.');};
  setVoice('loading');a.voiceTimeout=setTimeout(()=>{if(valid()){controller.abort();fail();}},25000);
  try{
   const clip=approvedClip(getLanguage(),'vision','vision:'+code);
   if(!clip)throw Error('APPROVED_VISION_RECORDING_UNAVAILABLE');
   const audio=new Audio();a.audio=audio;audio.dataset.recordingId=clip.recordingId;
   const played=await playFixedSpeech(audio,clip,controller.signal,valid,name=>{if(valid()){timing(name);if(name==='playing')setVoice('playing');}},true);
   if(played&&valid()){stopSpeech();setVoice(a.listeningStarted?'listening':'quiet');onEnded();}else fail();
  }catch{fail();}
 }
 function listen(){
  const a=r.current,s=a.session,epoch=a.epoch,f=flow.current,controlOnly=f.stage==='user-paused';if(!s||!current(epoch)||document.hidden||speechMuted()||!isMicrophoneAllowed()||a.recognition||a.restart||a.controller||a.audio?.paused===false||a.answerTimer||a.settleAnswer||a.muted||a.modal||(!controlOnly&&(!f.canAnswer||failure()||!measureSymbol())))return;
  const SR=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;if(!SR){recognitionFailure('unsupported');return;}
  const recognition=new SR(),recognitionId=crypto.randomUUID(),id=s.presentationId,token=f.token();a.recognition=recognition;recognition.lang=getLocale();recognition.continuous=false;recognition.interimResults=true;recognition.maxAlternatives=3;const finalIndexes=new Set<number>();let accepted=false;
  // Identity callbacks survive a short blink; answer admission remains a
  // separate fresh-frame/stimulus gate. Persistent faults stop this instance.
  const valid=()=>current(epoch)&&isMicrophoneAllowed()&&a.recognition===recognition&&flow.current.matches(token)&&s.presentationId===id;
  recognition.onstart=()=>{if(valid()){if(!controlOnly)s.beginResponse();a.listeningStarted=true;if(a.audio?.paused!==false)setVoice('listening');timing('listening');}else{try{recognition.abort();}catch{}}};
  recognition.onresult=(event:any)=>{
   if(!valid()||accepted)return;
   const finals=[];for(let i=event.resultIndex||0;i<event.results.length;i++){
    const item=event.results[i];if(!item)continue;
    const choices=Array.from({length:Math.min(item.length||1,3)},(_,n)=>({transcript:item[n].transcript,confidence:item[n].confidence}));
    const chosen=visionRecognitionChoice(choices,getLanguage(),{letter:s.letter});if(!chosen||!chosen.transcript.trim()||isLetterInstructionEcho(chosen.transcript,getLanguage()))continue;
    if(!item.isFinal){
     // A meaningful interim cancels obsolete speech and the pending commit,
     // without using an interim transcript as a scored answer.
     if(chosen.parsed.letter||chosen.parsed.rotation!==undefined||chosen.parsed.mirrored!==undefined||chosen.parsed.command){
      a.speechActive=true;if(a.answerTimer)clearTimeout(a.answerTimer);a.answerTimer=null;setVoice('listening');
     }
     continue;
    }
    a.speechActive=false;if(!finalIndexes.has(i)){finalIndexes.add(i);finals.push({...chosen,index:i});}
   }
   if(!finals.length)return;
   const text=finals.map(x=>x.transcript).join(' '),confidence=Math.min(...finals.map(x=>Number.isFinite(x.confidence)?x.confidence:0));
   // A user pause hides the target and ends its answer recognizer. The new
   // generation accepts only the already advertised resume/finish commands;
   // letters, noise and low-confidence controls never enter answer memory.
   if(controlOnly&&(!['resume','finish'].includes(parseLetterAnswer(text,getLanguage()).command||'')||(confidence>0&&confidence<.5)))return;
   accepted=true;s.suspendResponse();a.recognitionFailures=0;timing('asr-final');abortRecognition();setVoice('quiet');
   if(canvas.current)canvas.current.dataset.visionAnswer=JSON.stringify({parsed:parseLetterAnswer(text,getLanguage(),{letter:s.letter}),confidence,atMs:performance.now(),presentationId:id});
   actions.current.receive(text,confidence,id,`${recognitionId}:${finals.map(x=>x.index).join(',')}`,visionRecognitionConfidence(finals));
  };
  recognition.onspeechend=()=>{if(valid())a.speechActive=false;};
  recognition.onerror=(event:any)=>{if(!valid())return;timing('asr-error:'+event.error);if(event.error==='no-speech'){abortRecognition();s.suspendResponse();setVoice('quiet');if(controlOnly)scheduleListening();else actions.current.silence();return;}recognitionFailure(event.error);};
  recognition.onend=()=>{if(!valid())return;a.recognition=null;a.listeningStarted=false;a.speechActive=false;s.suspendResponse();setVoice('quiet');if(!accepted&&!controlOnly)actions.current.silence();else scheduleListening();};
  try{recognition.start();}catch{recognitionFailure('start-failed');}
 }
 function failure(){const a=r.current,s=a.session,c=a.evidence?.conditions||null,v=video.current;if(!c||!v||v.paused||v.ended||v.readyState<2||!a.stream?.getVideoTracks().every(t=>t.readyState==='live')||performance.now()-c.observedAt>750)return 'camera';if(c.blocker)return c.blocker;const gate=s?flow.current.gatedEye(s.eye):null;if(gate){const opened=gate==='RIGHT'?c.right:c.left,other=gate==='RIGHT'?c.left:c.right;if(['closed','covered'].includes(opened.state)&&['closed','covered'].includes(other.state))return 'both-eyes';if(['closed','covered'].includes(opened.state))return 'test-eye';if(opened.state==='open'&&other.state==='open')return 'cover-other';}return letterConditionFailure(c,gate,performance.now());}
 function inspect(){
  const a=r.current,s=a.session,f=flow.current;if(a.active&&s)refresh();if(!a.active||!s||['idle','result','error','user-paused'].includes(f.stage)||a.muted||a.modal)return;
  const problem=failure();f.setConditions(!problem);if(f.stage==='eye-instruction'||(f.stage==='preparing'&&a.controller))return;
  if(problem){
   if(!a.fault)a.faultSince=performance.now();a.fault=problem;
   if(['rendering','prompting','listening'].includes(f.stage)){
    s.suspendResponse();
    // Do not restart a visible letter and its instruction for a short blink.
    // Scoring/STT stop immediately; the persistent fault still hides it below.
    if(performance.now()-a.faultSince>=800){stopVoice();stage('condition-paused',TEXT[problem]||TEXT.uncertain);}
   }else if(f.stage==='condition-paused'){f.reason=TEXT[problem]||TEXT.uncertain;refresh();}
   if(s.presentationId&&performance.now()-a.faultSince>=800&&!a.announcedFault){s.invalidate(problem,a.evidence?.conditions||null,performance.now(),null);f.presentationId='';a.announcedFault=problem;refresh();}return;
  }
  a.fault='';a.faultSince=0;a.announcedFault='';
  if(f.instructionEye!==s.eye){f.eye=s.eye;f.instructionEye=s.eye;stage('eye-instruction',eyeInstruction(s.eye));void speak(s.eye==='RIGHT'?'right':'left',()=>{stage('eye-check',eyeInstruction(s.eye));actions.current.inspect();});return;}
  if(f.stage==='preparing'||f.stage==='eye-check'||f.stage==='condition-paused'){if(!s.presentationId){s.present();if(a.answerMemory.bind({sessionId:s.id,eye:s.eye,targetId:s.trialId})){setAnswerNotice('');a.clarifications=0;a.silenceReminders.clear();}}f.presentationId=s.presentationId;stage('rendering');return;}
  if(f.stage==='listening')actions.current.listen();
 }
 function discardPresentation(reason:string){const a=r.current;a.session?.invalidate(reason,a.evidence?.conditions||null,performance.now(),null);flow.current.presentationId='';}
 function pause(){r.current.session?.suspendResponse();stopVoice();discardPresentation('USER_PAUSED');stage('user-paused','Duraklatıldı. Devam et ile sürdürebilirsiniz.');actions.current.listen();}
 function resume(){const a=r.current;if(!a.session)return;a.recognitionFailures=0;setError('');a.modal=false;setDialog(null);stopVoice();stage('condition-paused','Koşullar kontrol ediliyor.');inspect();}
 async function complete(cancelled=false){
  const a=r.current,s=a.session;if(!s)return;const epoch=a.epoch;s.suspendResponse();stopVoice();stage('user-paused');
  if(cancelled){stop();setDialog('Görev bitirildi. Tamamlanmamış sonuç kaydedilmedi.');return;}
  const value:LetterResult={id:s.id,date:new Date().toISOString(),protocolVersion:LETTER_PROTOCOL,methodVersion:LETTER_METHOD,trials:s.ledger.map(t=>structuredClone(t)),deviceContext:{width:screen.width,height:screen.height,dpr:devicePixelRatio},profileVerification:'unverified',distanceMethod:'relative-head-anchors',physicalScale:null,completed:s.completed};
  let notice='Görev tamamlandı. Saklama tercihi kapalı; geçmişe kayıt eklenmedi.';
  if(isVisionSavingAllowed()&&!isDemoMode()&&!a.saving){a.saving=true;try{await appendHealthRecord('vision',value,{},()=>current(epoch)&&isVisionSavingAllowed());notice='Görev tamamlandı. Sonuç bu cihazdaki geçmişe kaydedildi.';}catch{notice='Görev tamamlandı ancak sonuç kaydedilemedi.';}finally{a.saving=false;}}
  if(a.epoch!==epoch)return;stop();setResult(value);stage('result');setDialog(notice);
 }
 function scheduleListening(){
  const a=r.current;if(a.restart)clearTimeout(a.restart);const epoch=a.epoch,token=flow.current.token();
  a.restart=setTimeout(()=>{a.restart=null;if(current(epoch)&&flow.current.matches(token))actions.current.listen();},350);
 }
 function followUpCode(){
  const memory=r.current.answerMemory;
  const p=memory.answer,hasOrientation=p.rotation!==undefined||p.mirrored!==undefined||!!p.orientation;
  return !p.letter&&!hasOrientation&&!p.ambiguous&&p.clarify!=='reverse'?'repeat':memory.missing||'repeat';
 }
 function silence(){
  const a=r.current,s=a.session;if(!s||!flow.current.canAnswer||failure())return;
  const code=followUpCode(),key=s.trialId+'/'+code;
  if(!a.silenceReminders.has(key)){a.silenceReminders.add(key);setAnswerNotice('Konuşma algılanmadı. Yönergeden sonra yanıtlayın.');prompt(code);}
  else scheduleListening();
 }
 function prompt(code?:string){
  const a=r.current,s=a.session;if(!s||failure()||!measureSymbol())return;
  const initial=!code;
  if(initial){
   if(!a.pendingPrompt&&a.prompted.has(s.trialId)){stage('listening');scheduleListening();return;}
   code=a.pendingPrompt||(a.answerMemory.fragmentCount?followUpCode():a.mainInstructionGiven?'next1':'repeat');a.mainInstructionGiven=true;
  }
  const id=s.presentationId,epoch=a.epoch;
  a.lastPrompt=code!;a.pendingPrompt=code!;s.suspendResponse();abortRecognition();stage('prompting');
  timing('prompt:'+code);
  void speak(code!,()=>{
   if(!current(epoch)||s.presentationId!==id||flow.current.stage!=='prompting')return;
   if(initial)a.prompted.add(s.trialId);a.pendingPrompt=null;
   stage('listening');scheduleListening();
  });
 }
 function receive(text:string,confidence:number,id:string,key:string,componentConfidence?:VisionComponentConfidence){
  const a=r.current,s=a.session;if(!s||!current(a.epoch)||s.presentationId!==id)return;
  const parsed=parseLetterAnswer(text,getLanguage(),{letter:s.letter});
  if(parsed.command&&confidence>0&&confidence<.5)return;
  if(flow.current.stage==='user-paused'){if(parsed.command==='resume')resume();else if(parsed.command==='finish')void complete(true);return;}
  if(!flow.current.canAnswer)return;
  if(parsed.command==='finish'){void complete(true);return;}if(parsed.command==='pause'){pause();return;}if(parsed.command==='resume'){resume();return;}
  const target={sessionId:s.id,eye:s.eye,targetId:s.trialId};
  if(!a.answerMemory.matches(target)||a.answerMemory.processed)return;
  // Store decoded fields before the admission/confidence gate. Showing an
  // understood fragment must not claim information that memory then discards.
  if(!parsed.command){if(!a.answerMemory.append(target,key,text,parsed,confidence,componentConfidence))return;refresh();}
  if(a.answerTimer)clearTimeout(a.answerTimer);a.answerTimer=null;a.settleAnswer=null;
  setVoice('quiet');
  const merged=parsed.command?parsed:a.answerMemory.answer,geometry=measureSymbol(),now=performance.now();
  if(failure()||!geometry||!flow.current.canAnswer){setAnswerNotice(`Algılanan: ${answerDescription(merged)}. Koşullar düzelince bu harf için yeniden yanıt verin.`);s.unscored('CONDITIONS_INVALID_AT_RESPONSE',a.evidence?.conditions||null,now,geometry,parsed);inspect();return;}
  if(parsed.command==='repeat'){a.speechActive=false;prompt(a.lastPrompt||'repeat');return;}
  const unclear=!parsed.command&&(!!a.answerMemory.missing||!!merged.clarify||!merged.letter||!answerTransform(merged));
  if(unclear){
   const code=followUpCode();
   setAnswerNotice(`Algılanan: ${answerDescription(merged)}. ${code==='letter'?'Yalnız harf bekleniyor.':code==='reverse'?'Baş aşağı mı, aynalı mı?':code==='orientation'?'Yalnız yön bekleniyor.':'Yanıtı yeniden söyleyin.'}`);
   const token=flow.current.token(),epoch=a.epoch;
   a.answerTimer=setTimeout(()=>{a.answerTimer=null;if(current(epoch)&&flow.current.matches(token)&&s.presentationId===id&&!failure())prompt(code);},350);
   return;
  }
  const settle=()=>{
   a.answerTimer=null;a.settleAnswer=null;if(!current(epoch)||!flow.current.matches(token)||s.presentationId!==id||a.answerMemory.processed||a.speechActive)return;
   if(failure()||!measureSymbol()){setAnswerNotice('Koşullar değişti. Yanıt puanlanmadı; tekrar yanıtlayın.');return;}
   const before=s.adaptationState;
  if(respondToVisibleLetter(s,merged,a.evidence?.conditions||null,id,measureSymbol)){
   a.answerMemory.markProcessed();
   // Opt-in, local diagnostic for the production score -> size -> DOM audit.
   // No transcript/audio, storage writes or user-facing technical content.
   try{if(sessionStorage.getItem('attune_vision_size_diagnostics')==='1'){
    const t=s.trials[s.trials.length-1];window.dispatchEvent(new CustomEvent('attune-vision-size-diagnostic',{detail:{presentationId:t.presentationId,target:{letter:t.letter,transform:t.transform},parsed:t.answer,letterCorrect:t.letterCorrect,orientationCorrect:t.orientationCorrect,combinedCorrect:t.combinedCorrect,fragmentCount:a.answerMemory.fragmentCount,before,after:s.adaptationState,renderedGeometry:t.renderedGeometry}}));
   }}catch{/* Diagnostics must never interrupt an accepted response. */}
   stopVoice();setAnswerNotice('');flow.current.presentationId='';a.clarifications=0;
   if(s.completed)void complete();else{stage('eye-check');inspect();}
  }
  };
  const token=flow.current.token(),epoch=a.epoch;
  setAnswerNotice('Yanıt alındı. Değerlendiriliyor.');
  a.settleAnswer=settle;
  a.answerTimer=setTimeout(settle,VISION_ANSWER_SETTLE_MS);
 }
 function recognitionFailure(reason:string){
  const a=r.current,s=a.session;if(!s)return;
  if(a.answerTimer)clearTimeout(a.answerTimer);a.answerTimer=null;a.settleAnswer=null;
  abortRecognition();stopSpeech();s.suspendResponse();setVoice('quiet');
  // A bounded retry handles transient transport/audio failures without replaying
  // guidance or converting recognition failure into a wrong vision response.
  if(['network','audio-capture','aborted','start-failed'].includes(reason)&&a.recognitionFailures<2){
   const delay=350*2**a.recognitionFailures++;const epoch=a.epoch,token=flow.current.token();
   setAnswerNotice('Konuşma bağlantısı yeniden kuruluyor. Yanıt puanlanmadı.');
   a.restart=setTimeout(()=>{a.restart=null;if(current(epoch)&&flow.current.matches(token))actions.current.listen();},delay);return;
  }
  discardPresentation('ASR_UNAVAILABLE');stage('error','Konuşma tanıma kullanılamıyor. Mikrofon iznini ve bağlantıyı kontrol edip tekrar deneyin.');setVoice('failed');
  setError(reason==='unsupported'?'Bu tarayıcı sesli yanıtı desteklemiyor. Konuşma tanımayı destekleyen bir tarayıcıda açın.':'Mikrofon veya konuşma hizmeti kullanılamıyor. Yanıt puanlanmadı; tekrar deneyin.');
 }
 actions.current={inspect,receive,listen,stop,pause,silence,measure:measureSymbol,prompt,current,timing,canPresent:()=>!failure(),renderError:()=>{discardPresentation('STIMULUS_NOT_VISIBLE');stage('error','Harf alanı görünür değil. Alanı ekrana getirip tekrar deneyin.');setError('Harf gösterilemedi; yanıt istenmedi veya puanlanmadı.');}};
 const renderStage=flow.current.stage,renderToken=flow.current.token();
 // Require a painted, nonzero, unclipped stimulus before any response prompt.
 useEffect(()=>{if(renderStage!=='rendering')return;const token=renderToken,epoch=r.current.epoch;let cancelled=false,raf=0;const startedAt=performance.now();const verify=()=>{if(cancelled||!actions.current.current(epoch)||!flow.current.matches(token))return;if(actions.current.measure()&&actions.current.canPresent()){actions.current.timing('letter-rendered');actions.current.prompt();}else if(performance.now()-startedAt<2000)raf=requestAnimationFrame(verify);else actions.current.renderError();};raf=requestAnimationFrame(()=>{
  const svg=symbol.current,box=svg?.getBoundingClientRect(),header=document.querySelector<HTMLElement>('[data-cockpit-header]');
  const visibleTop=header&&getComputedStyle(header).position==='sticky'?Math.max(0,header.getBoundingClientRect().bottom):0;
  // A glyph can be inside the viewport but hidden behind the sticky header
  // after using controls. Scroll it into the unobscured area, without scaling.
  if(svg&&box&&(box.top<visibleTop||box.bottom>innerHeight||box.left<0||box.right>innerWidth)){svg.style.scrollMarginTop=`${visibleTop}px`;svg.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'});}
  raf=requestAnimationFrame(verify);
 });return()=>{cancelled=true;cancelAnimationFrame(raf);};},[renderStage,renderToken]);
 useEffect(()=>{const state=r.current;state.mounted=true;setReady(true);const revoke=()=>{if(!isCameraAllowed()||!isMicrophoneAllowed()||!serviceAllowed('vision')){actions.current.stop();setError('Kamera, mikrofon veya hizmet izni kapalı; görev durduruldu.');}};window.addEventListener('storage',revoke);window.addEventListener('attune-privacy',revoke);return()=>{state.mounted=false;actions.current.stop();window.removeEventListener('storage',revoke);window.removeEventListener('attune-privacy',revoke);};},[]);
 useEffect(()=>{const hidden=()=>{if(document.hidden&&r.current.active)actions.current.pause();};document.addEventListener('visibilitychange',hidden);return()=>document.removeEventListener('visibilitychange',hidden);},[]);
 useEffect(()=>{if(!isParked){actions.current.stop();setDialog(null);}},[isParked]);
 useEffect(()=>{if(video.current&&r.current.stream&&video.current.srcObject!==r.current.stream){video.current.srcObject=r.current.stream;void video.current.play().catch(()=>{});}});
 async function start(){
  if(!parked.current||r.current.starting)return;stop();if(canvas.current){delete canvas.current.dataset.visionFailure;delete canvas.current.dataset.visionAnswer;}setAnswerNotice('');setDialog(null);setError('');setResult(null);if(!isCameraAllowed()||!isMicrophoneAllowed()||!serviceAllowed('vision')){setError('Kamera ve mikrofon izinlerini Gizlilik ekranından açın.');return;}
  const a=r.current;a.recognitionFailures=0;a.starting=true;a.active=true;a.muted=false;a.fault='';a.announcedFault='';a.session=new SpokenLetterSession();flow.current.start(a.session.id);refresh();const epoch=a.epoch;
  try{const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:640},height:{ideal:480}},audio:false});if(!current(epoch)){stream.getTracks().forEach(t=>t.stop());return;}a.stream=stream;refresh();
   const engine=new VisionInference();a.engine=engine;await engine.initialize();if(!current(epoch))return;if(!video.current)throw Error('PREVIEW');video.current.srcObject=stream;await video.current.play();void speak('prepare',()=>inspect());
   let last=-1;const analysis=document.createElement('canvas');const inferenceFailure=(error:unknown)=>{if(current(epoch)){if(canvas.current)canvas.current.dataset.visionFailure=JSON.stringify({stage:'frame',message:error instanceof Error?error.message:'UNKNOWN',atMs:performance.now()});stop();setError('Kamera değerlendirmesi kesildi. Görev kaydedilmedi; tekrar deneyebilirsiniz.');}};const loop=async()=>{
    if(!current(epoch))return;const v=video.current,c=canvas.current;if(!v||!c||stream.getVideoTracks().some(t=>t.readyState!=='live'))throw Error('CAMERA_ENDED');
    if(v.readyState>=2&&v.currentTime!==last){last=v.currentTime;const captureSession=flow.current.sessionId,captureEye=a.session?.eye,capturePresentation=a.session?.presentationId;const time=performance.now(),ratio=Math.min(1,640/v.videoWidth);analysis.width=Math.round(v.videoWidth*ratio);analysis.height=Math.round(v.videoHeight*ratio);analysis.getContext('2d',{willReadFrequently:true})!.drawImage(v,0,0,analysis.width,analysis.height);
     const observed=await engine.assess(analysis,time,a.session?flow.current.gatedEye(a.session.eye):null);if(!current(epoch))return;if(flow.current.sessionId!==captureSession||a.session?.eye!==captureEye||a.session?.presentationId!==capturePresentation){a.raf=requestAnimationFrame(()=>void loop().catch(inferenceFailure));return;}observed.conditions.cameraLive=!v.paused&&!v.ended&&stream.getVideoTracks().every(t=>t.readyState==='live');const rawConditions=observed.conditions,gate=a.session?flow.current.gatedEye(a.session.eye):null;
     observed.conditions=a.conditionGate.assess(rawConditions,gate,performance.now())||rawConditions;a.evidence=observed;if(observed.alignment.landmarks)a.previewPoints=observed.alignment.landmarks;setEvidence(observed);
     c.dataset.visionEvidence=JSON.stringify({delegate:observed.delegate,headBox:observed.alignment.box,headPose:{yaw:observed.alignment.yaw,pitch:observed.alignment.pitch,roll:observed.alignment.roll},blurScore:observed.quality.blurScore,conditions:observed.conditions,rawConditions,distanceRatios:observed.distanceRatios,distanceSamples:observed.distanceSamples,inferenceMs:observed.inferenceMs,frameTime:last});inspect();}
    if(current(epoch))a.raf=requestAnimationFrame(()=>void loop().catch(inferenceFailure));};void loop().catch(inferenceFailure);a.timer=setInterval(inspect,200);
  }catch(error){if(current(epoch)){const modelStarted=!!a.engine;if(canvas.current)canvas.current.dataset.visionFailure=JSON.stringify({stage:modelStarted?'model-or-preview':'camera',message:error instanceof Error?error.message:'UNKNOWN',atMs:performance.now()});stop();setError(modelStarted?'Yüz/el modeli veya önizleme başlatılamadı. Bağlantıyı kontrol edip tekrar deneyin.':error instanceof DOMException&&error.name==='NotReadableError'?'Kamera açılamadı; başka kamera kullanımını bitirip yeniden deneyin.':'Kamera görüntüsü alınamadı. Kamera izinlerini ve cihazı kontrol edin.');}}finally{a.starting=false;if(a.mounted)refresh();}
 }
 const lastHeard=r.current.answerMemory.heard;
 const f=flow.current,s=r.current.session,c=evidence?.conditions,fresh=!!c&&performance.now()-c.observedAt<=750,active=r.current.active;
 useEffect(()=>{if(!active)return;const element=document.querySelector<HTMLElement>('[data-vision-stage]'),header=document.querySelector<HTMLElement>('[data-cockpit-header]');if(element){element.style.scrollMarginTop=`${header&&getComputedStyle(header).position==='sticky'?header.getBoundingClientRect().height+8:8}px`;element.scrollIntoView({block:'start',behavior:'instant'});}},[active]);
 const problem=active?failure():null,faceVisible=fresh&&c?.faceCount===1,eyeLine=c?`Sol göz: ${EYE_TEXT[eyeObservation(c,'LEFT',performance.now())]} · Sağ göz: ${EYE_TEXT[eyeObservation(c,'RIGHT',performance.now())]}`:'İki göz açık başlayın';
 const rows=[['Yüz / Kadraj',!fresh?'Ölçüm bekleniyor':c?.blocker==='pose'||c?.blocker==='framing'?TEXT[c.blocker]:c?.faceCount===1?'Yüz izleniyor':'Yüzünüzü görüntüde tutun'],['Işık',!faceVisible?'Ölçüm bekleniyor':c?.qualityValid?'İyi':evidence?.quality.status==='TOO_DARK'?TEXT.light:evidence?.quality.status==='TOO_BRIGHT'?TEXT.bright:'İyi'],['Netlik',!faceVisible?'Ölçüm bekleniyor':c?.qualityValid||(evidence?.quality.blurScore||0)>=4?'İyi':TEXT.blur],['Mesafe / Konum',c?.blocker&&['preparing','recede','approach','distance-unknown'].includes(c.blocker)?TEXT[c.blocker]:c?.distanceState==='stable'?'Başlangıç mesafesi korunuyor':c?.distanceState==='unknown'?'Mesafe ölçümü güvenilir değil':'Başlangıç bekleniyor'],['Göz kontrolü',eyeLine],['Görüntü güncelliği',fresh?'Güncel':'Kamera karesi bekleniyor']];
 const blockLabel=problem&&['eye','uncertain','both-eyes','test-eye','cover-other'].includes(problem)?'Göz':problem==='pose'?'Baş pozu':problem==='blur'?'Netlik':problem==='light'||problem==='bright'?'Işık':problem==='camera'?'Görüntü':problem==='face'||problem==='framing'?'Kadraj':'Mesafe';
 const placeholder=!evidence&&f.stage==='preparing'?'Kamera ve cihazdaki modeller hazırlanıyor…':f.stage==='user-paused'||f.stage==='error'||f.stage==='condition-paused'?f.reason:f.stage==='eye-instruction'?eyeInstruction(s?.eye||'RIGHT'):f.stage==='eye-check'?eyeInstruction(s?.eye||'RIGHT')+(problem&&problem!=='cover-other'?' '+(TEXT[problem]||TEXT.uncertain):''):problem?(problem==='preparing'?'Başlangıç kontrolü sürüyor.':`${blockLabel} kontrolü nedeniyle duraklatıldı.`):'Harf hazırlanıyor…';
 return <div className={`${active?'space-y-3 max-w-full':f.stage==='idle'?'space-y-6 max-w-5xl mx-auto':'space-y-6 max-w-full'} w-full min-w-0`} data-vision-stage={f.stage} data-vision-trial={f.presentationId}>
  <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><h1 className="text-2xl font-bold">{i18nNode(HEALTH_MODULES.vision.name)}</h1><InformationButton title={i18nText("Görme görevi ve hizmet bilgisi")}><p>{i18nText("Bu görev klinik görme keskinliği veya göz numarası ölçmez. Kamera pikselleri ve göz başlangıcı yalnız cihaz belleğinde değerlendirilir. Görüntü aynasızdır; sağ ve sol, kendi anatomik gözünüzdür. Mutlak uzaklık ölçülmez.")}</p></InformationButton></div>{f.stage==='result'&&<button onClick={()=>{setResult(null);setAnswerNotice('');flow.current.reset();refresh();}} className="min-h-11 rounded-xl border border-white/20 px-4">{i18nText("Yeni Analiz")}</button>}</div>
  {!isParked?<p>{i18nNode(syncStatus==='synced'?'Sürüş sırasında görev kapalıdır.':'Araç durumu doğrulanamadı; görev kapalıdır.')}</p>:<>
   {f.stage==='idle'&&<HealthStartCard module="vision" actions={<button onClick={()=>void start()} disabled={!ready||r.current.starting} className={HEALTH_START_ACTION}>{i18nText("Başlat")}</button>}/>}
   {(active||f.stage==='result')&&<VisionJourney phase={f.stage==='result'?'result':f.stage==='preparing'?'prepare':'test'} eye={s?.eye||'LEFT'} completed={s?.trials.length||(f.stage==='result'?24:0)}/>}
   {active&&<section className="grid md:grid-cols-2 gap-4 rounded-2xl bg-cockpit-surface border border-slate-800/90 p-4 md:p-6 w-full min-w-0 max-w-full">
    <div className="order-first md:order-none md:col-span-2 grid md:grid-cols-2 gap-4 min-w-0"><div className="hidden md:block" aria-hidden="true"/><div className="space-y-2 min-w-0">
     <p className="text-center font-semibold">{i18nNode(s?`${s.eye==='RIGHT'?'Sağ':'Sol'} göz · ${s.trials.length%12+1}/12`:'')}</p>
     <p role="status" data-vision-readiness className="min-h-5 text-sm text-togg-turquoise text-center">{i18nNode(voice==='playing'?'Yönerge okunuyor':voice==='loading'?'Yönerge hazırlanıyor':f.stage==='listening'&&r.current.listeningStarted?(f.conditionsValid?'Dinliyor':'Koşul bekleniyor'):f.stage==='listening'?(r.current.answerTimer?'Yanıt işleniyor':'Mikrofon hazırlanıyor'):f.stage==='condition-paused'?'Koşul bekleniyor':'')}</p>
    </div></div>
    <div className="space-y-2 min-w-0"><CameraPreview videoRef={video} landmarks={r.current.previewPoints} vision/><div data-camera-preparation className="space-y-1.5">{rows.map(([label,value])=><div key={label} className="flex flex-wrap justify-between gap-2 px-3 py-1.5 rounded-xl border border-white/10 text-sm"><span>{i18nNode(label)}</span><span className={value==='İyi'||value==='Güncel'?'text-emerald-400':'text-slate-300'}>{i18nNode(value)}</span></div>)}</div><p className="text-sm text-togg-turquoise" data-vision-voice={voice}>{i18nNode(voice==='playing'?'Yönerge okunuyor':voice==='loading'?'Yönerge hazırlanıyor':voice==='listening'?'Dinliyor':'')}</p></div>
    <div className="order-first md:order-none flex flex-col items-center justify-start gap-2 min-w-0 self-start w-full">
     <div data-letter-area className={`${VISION_FRAME_CLASS} flex items-center justify-center p-3`}>
      {f.letterVisible&&s?<LetterStimulus svgRef={symbol} path={LETTER_PATHS[s.letter]} transform={s.transform} sizePx={s.sizePx}/>:<p role="status" data-letter-placeholder className="p-4 text-center text-slate-200">{i18nNode(placeholder)}</p>}
     </div>
     {f.stage==='condition-paused'&&<p role="status" data-vision-condition className="text-sm text-amber-200 text-center">{i18nText("Koşullar düzelince görev otomatik devam eder. Geçersiz deneme puanlanmaz.")}</p>}
     {answerNotice&&<p role="status" data-vision-answer-notice className="text-sm text-slate-200 text-center">{i18nNode(answerNotice)}</p>}
     {lastHeard&&<p className="text-sm text-slate-300 text-center break-words">{i18nText("Duyulan: “")}{lastHeard}”</p>}

     <div className="flex flex-wrap gap-3"><button onClick={()=>void start()} disabled={r.current.starting} className="min-h-11 rounded-xl border border-white/20 px-4">{i18nText("Yeni konumla yeniden başlat")}</button><button onClick={()=>f.stage==='user-paused'?resume():pause()} className="min-h-11 rounded-xl border border-white/20 px-4">{i18nNode(f.stage==='user-paused'?'Devam et':'Duraklat')}</button><button onClick={()=>void complete(true)} className="min-h-11 rounded-xl border border-white/20 px-4">{i18nText("Bitir")}</button>{f.stage==='error'&&<button onClick={resume} className="min-h-11 rounded-xl border border-white/20 px-4">{i18nText("Tekrar dene")}</button>}</div>
     <ul className="w-full max-w-lg list-disc space-y-1 pl-5 text-sm leading-relaxed text-slate-300"><li>{i18nText("Harf ve yönü herhangi bir sırada söyleyebilirsiniz.")}</li><li>{i18nText('Harf adını veya yaygın bir kod sözcüğünü söyleyin; örneğin E, Elma.')}</li><li>{i18nText("Düz, baş aşağı, sağa/sola yatmış, aynalı veya bunların birleşimini söyleyebilirsiniz.")}</li><li>{i18nText("“Tekrar”, “göremiyorum”, “duraklat”, “devam et” ve “bitir” komutlarını kullanabilirsiniz.")}</li></ul>
    </div>
   </section>}
   {error&&<p role="alert" className="text-amber-200">{i18nNode(error)}</p>}
   {f.stage==='result'&&result&&<section className="rounded-2xl border border-white/10 bg-cockpit-surface p-6 space-y-5"><LetterVisionResult result={result}/></section>}
   <RecordHistory category="vision" parked={isParked}/>
  </>}
  <canvas ref={canvas} hidden/>
  {dialog&&<AccessibleDialog title={i18nText("Görme bildirimi")} onClose={()=>{r.current.modal=false;setDialog(null);inspect();}} className="w-full max-w-md rounded-2xl border border-white/20 bg-cockpit-surface p-6 space-y-4"><h2 className="font-bold">{i18nText("Görme bildirimi")}</h2><p>{i18nNode(dialog)}</p><button onClick={()=>{r.current.modal=false;setDialog(null);inspect();}} className="min-h-11 rounded-xl bg-togg-turquoise text-togg-darkBlue px-6">{i18nText("Tamam")}</button></AccessibleDialog>}
 </div>;
}
