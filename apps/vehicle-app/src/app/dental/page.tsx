'use client';
import {useLocaleSwitchLock} from '../../i18n/useLocaleSwitchLock';
import {apiFetch as fetch} from '../../utils/localBackend';
import {useTranslations} from '../../i18n/LanguageProvider';

import {HEALTH_START_ACTION,HEALTH_START_SECONDARY} from '../../components/HealthStartCard';
import {HealthPreparation} from '../../components/HealthPreparation';
import {serviceAllowed,useServiceAllowed} from '../../utils/serviceConsent';
import {localBackend} from '../../utils/localBackend';
import { HEALTH_MODULES } from '../../utils/healthModules';
import { useGuidance,qualityGuidance } from '../../utils/audioGuidance';
import {useCallback,useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {careHref} from '../../utils/healthModules';
import {validateDentalFile,UPLOAD_REASONS} from '../../utils/dentalUpload';
import {useVehicle} from '../../context/VehicleContext';
import {InformationButton} from '../../components/InformationButton';
import {RecordHistory} from '../../components/RecordHistory';
import {SkinInference} from '../../utils/skinInference';
import {StablePreviewCrop,SourceMotion,cameraCrop,Crop} from '../../utils/cameraStability';
import {DentalCapture,DENTAL_POSES,DENTAL_GUIDANCE,assessDentalCapture,captureDental} from '../../utils/dentalCapture';
import {DentalCaptureSession} from '../../utils/dentalCaptureSession';
import {saveDentalPhotos,verifyDentalPhotoPixels,DENTAL_PHOTO_PERMISSION} from '../../utils/dentalPhotoHistory';
import {validateDentalResult,validateDentalView,dentalRecordMeasurements,dentalViewMeasured,DENTAL_POSE_LABELS} from '../../utils/dentalResult';
import {DentalResults} from '../../components/dental/DentalResults';
import {DentalJourney} from '../../components/dental/DentalJourney';
import styles from '../../components/dental/dental.module.css';
import {SkipForward,X,RotateCcw,Upload} from 'lucide-react';
import {appendHealthRecord,withRecordsLock} from '../../utils/healthRecords';
import {isCameraAllowed} from '../../utils/attuneMode';
import type {FaceAlignment} from '../../utils/skinAnalyzer';
/** One transient failed frame inside a hold does not restart it; the captured
 * frame itself must pass every gate. Motion/face loss always restart. */
const DENTAL_HOLD_MS=1400,DENTAL_HOLD_GRACE_FRAMES=1,DENTAL_SKIP_AFTER_MS=15000;
export default function DentalPage(){
 const {text:i18nText,node:i18nNode}=useTranslations();
 const {isParked}=useVehicle(),parked=useRef(isParked);parked.current=isParked;
 const consent=useServiceAllowed('dental');
 const [phase,setPhase]=useState<'ready'|'camera'|'analysis'|'result'|'error'>('ready'),[save,setSave]=useState(false),[notice,setNotice]=useState(''),[index,setIndex]=useState(0),[progress,setProgress]=useState(0),[crop,setCrop]=useState<Crop>({x:0,y:0,width:1,height:1}),[ratio,setRatio]=useState(4/3),[result,setResult]=useState<any>(),[shown,setShown]=useState(0);
 const [saveNote,setSaveNote]=useState<{text:string;error:boolean}|null>(null),[uploading,setUploading]=useState(false),[skipAvailable,setSkipAvailable]=useState(false),[skippedPoses,setSkippedPoses]=useState<string[]>([]);
 useLocaleSwitchLock('dental',phase==='camera'||phase==='analysis'||uploading);
 const saving=useRef(false),resultId=useRef(''),saveAllowed=useRef(save);saveAllowed.current=save;
 const [saved,setSaved]=useState(false),[saveBusy,setSaveBusy]=useState(false);
 const fileInput=useRef<HTMLInputElement>(null);
 const voice=useGuidance('dental',isParked);
 useEffect(()=>{if(isParked)voice.phase(phase+':'+index,phase==='camera'?(['dental-front','dental-right','dental-left','dental-bite'] as const)[Math.min(index,3)]:undefined);},[voice,isParked,phase,index]);
 useEffect(()=>{const id=(phase==='camera'&&!notice.endsWith('Kısa süre sabit tutun.'))||phase==='error'?qualityGuidance(notice):undefined;voice.issue(id||'',id);},[voice,notice,phase]);
 const video=useRef<HTMLVideoElement>(null),stream=useRef<MediaStream|undefined>(undefined),inference=useRef<SkinInference|undefined>(undefined),epoch=useRef(0),abort=useRef<AbortController|undefined>(undefined),captures=useRef<readonly DentalCapture[]>([]),session=useRef<DentalCaptureSession|undefined>(undefined),display=useRef(new StablePreviewCrop()),motion=useRef(new SourceMotion()),validSince=useRef(0),lastFrame=useRef(-1),lastFresh=useRef(0),frameTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),misses=useRef(0),poseSince=useRef(0),best=useRef<{sharp:number;alignment:FaceAlignment;canvas:HTMLCanvasElement}|undefined>(undefined);
 const stop=useCallback(()=>{setSaveBusy(false);voice.cancel();session.current?.close();epoch.current++;if(frameTimer.current)clearTimeout(frameTimer.current);stream.current?.getTracks().forEach(track=>track.stop());stream.current=undefined;inference.current?.close();inference.current=undefined;abort.current?.abort();},[voice]);
 const cancel=useCallback(()=>{stop();captures.current=[];resultId.current='';setSaved(false);setSaveNote(null);setResult(undefined);setUploading(false);if(fileInput.current)fileInput.current.value='';setProgress(0);setPhase('ready');setNotice('Geçici fotoğraf ve sonuçlar temizlendi.');},[stop]);
 useEffect(()=>()=>{stop();captures.current=[];},[stop]);
 useEffect(()=>{const changed=()=>{if(stream.current&&!isCameraAllowed()){cancel();setNotice('Kamera izni geri çekildi.');}};window.addEventListener('attune-privacy',changed);window.addEventListener('storage',changed);return()=>{window.removeEventListener('attune-privacy',changed);window.removeEventListener('storage',changed);};},[cancel]);
 useEffect(()=>{if(!isParked&&phase!=='ready'){cancel();setNotice('Diş taraması yalnız PARK durumunda yapılır.');}},[isParked,phase,cancel]);
 /** Each analysis owns the sealed, immutable source list it was started with. */
 const analyze=async(run:number,sources:readonly DentalCapture[])=>{captures.current=sources;
  setPhase('analysis');setNotice('Görünür diş yüzeyleri cihazda analiz ediliyor…');stream.current?.getTracks().forEach(track=>track.stop());inference.current?.close();const controller=new AbortController();abort.current=controller;const timer=setTimeout(()=>controller.abort(),30000);
  try{const response=await fetch(localBackend('/api/local-health/dental'),{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({processingConsent:consent,captures:sources})});if(!response.ok)throw Error('Yerel diş analizi tamamlanamadı.');const value=await response.json();if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;
   validateDentalResult(value,sources as DentalCapture[],true);
   // Views the backend could not measure stay visible as "ölçülemedi"; only a
   // scan without any measured view is an error (never shown as healthy).
   if(!value.views.some(dentalViewMeasured)){setPhase('error');setNotice('Görünümlerin hiçbiri ölçülemedi. Daha iyi ışıkta ve sabit durarak yeniden tarayabilirsiniz.');return;}
   resultId.current=crypto.randomUUID();
   setResult(value);setShown(0);setPhase('result');setNotice('Görünür alan ön değerlendirmesi. Çürük adayları tanı veya şiddet yüzdesi değildir.');
  }catch(error){if(run===epoch.current){setPhase('error');setNotice((error as Error).name==='AbortError'?'Analiz zamanında tamamlanamadı. Geçici fotoğrafları temizleyip yeniden başlayabilirsiniz.':(error as Error).message);}}finally{clearTimeout(timer);}
 };
 const upload=async(file:File)=>{
  if(!consent||!parked.current||!serviceAllowed('dental'))return;stop();const run=epoch.current;captures.current=[];resultId.current='';setSaved(false);setSaveNote(null);setResult(undefined);setUploading(true);setPhase('analysis');setNotice('Fotoğraf yerel olarak açılıyor ve yönü düzeltiliyor…');
  const controller=new AbortController();abort.current=controller;let deadline:ReturnType<typeof setTimeout>|undefined;
  try{
   const photo=await validateDentalFile(file);if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;
   // The same on-device face model anchors a full portrait to its inner mouth.
   // A partial intraoral photo need not contain a face or obtain camera access.
   const bitmap=await createImageBitmap(file,{imageOrientation:'from-image'});
   let photoLandmarks:FaceAlignment['landmarks'];
   try{
    if(bitmap.width*bitmap.height>24000000||Math.max(bitmap.width,bitmap.height)>8192)throw Error(UPLOAD_REASONS.PIXEL_LIMIT);
    const canvas=document.createElement('canvas'),factor=Math.min(1,640/Math.max(bitmap.width,bitmap.height));canvas.width=Math.round(bitmap.width*factor);canvas.height=Math.round(bitmap.height*factor);canvas.getContext('2d')!.drawImage(bitmap,0,0,canvas.width,canvas.height);
    setNotice('Fotoğraftaki ağız konumu cihazda hazırlanıyor…');const detector=new SkinInference();inference.current=detector;try{await detector.initialize();if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;
    const alignment=await detector.assessAlignment(canvas);if((alignment.faceCount||0)>1)throw Error('Fotoğrafta yalnız bir kişinin dişleri görünmeli.');if(alignment.faceDetected)photoLandmarks=alignment.landmarks;}finally{detector.close();if(inference.current===detector)inference.current=undefined;}
   }finally{bitmap.close();}
   if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;
   if(controller.signal.aborted)throw new DOMException('Fotoğraf işlemi zaman aşımına uğradı.','AbortError');
   setNotice('Görünür diş yüzeyleri cihazda analiz ediliyor…');deadline=setTimeout(()=>controller.abort(),30000);
   const response=await fetch(localBackend('/api/local-health/dental-upload'),{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({processingConsent:true,photo,photoLandmarks})});
   const value=await response.json();if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;if(!response.ok)throw Error(UPLOAD_REASONS[value.detail]||'Yerel fotoğraf analizi tamamlanamadı.');
   const view=value.views?.[0];if(value.views?.length!==1||view.sourceType!=='upload'||view.sourceWidth!==value.source?.sourceWidth||view.sourceHeight!==value.source?.sourceHeight||!/^[a-f0-9]{64}$/.test(view.photoId))throw Error('Kaynak fotoğraf eşleşmesi doğrulanamadı.');
   validateDentalView(view,undefined,true);if(!dentalViewMeasured(view))throw Error('Fotoğraf ölçülemedi. Başka bir fotoğraf seçebilirsiniz.');
   const accepted={photo:value.normalizedPhoto,photoId:view.photoId,width:view.sourceWidth,height:view.sourceHeight,pose:view.pose,landmarks:[],conditions:{},sourceType:'upload' as const};await verifyDentalPhotoPixels([accepted]);if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;captures.current=[accepted];resultId.current=crypto.randomUUID();
   delete value.normalizedPhoto;setResult(value);setShown(0);setPhase('result');setNotice('Tek fotoğrafın görünür yüzey sonucu. Çoklu açı doğrulaması yapılmadı.');
  }catch(error){if(run===epoch.current){captures.current=[];setPhase('error');const message=(error as Error).name==='AbortError'?'Fotoğraf analizi zamanında tamamlanmadı. Başka fotoğraf seçebilirsiniz.':(error as Error).message;setNotice(message);if(!qualityGuidance(message))void voice.say('dental-file');}}
  finally{clearTimeout(deadline);if(run===epoch.current&&fileInput.current)fileInput.current.value='';}
 };
 /** Open bite or any reason the front teeth cannot touch: continue with three
  * views; the bite/alignment result is reported as not taken, never as normal.
  * Sealing the session makes a BITE capture still being encoded a no-op. */
 const skipPose=()=>{const scan=session.current;if(phase!=='camera'||!scan||!scan.skipCurrent())return;
  setSkipAvailable(false);setProgress(0);setSkippedPoses([...scan.missing]);validSince.current=0;misses.current=0;best.current=undefined;poseSince.current=performance.now();
  if(scan.sealed){if(frameTimer.current)clearTimeout(frameTimer.current);return;}
  setIndex(scan.step);setNotice(DENTAL_GUIDANCE[scan.nextPose!]);};
 const start=async()=>{
  if(!consent||!isParked||!isCameraAllowed())return;stop();setUploading(false);setSkipAvailable(false);setSkippedPoses([]);captures.current=[];resultId.current='';setSaved(false);setSaveNote(null);setResult(undefined);setIndex(0);setProgress(0);setPhase('camera');setNotice('Kamera ve cihazdaki yüz modeli hazırlanıyor…');const run=epoch.current;const scan=new DentalCaptureSession(sources=>{if(run!==epoch.current||session.current!==scan)return;
    // Every pose skipped: nothing was measured; never present that as a result.
    if(!sources.length){stop();setPhase('error');setNotice('Hiçbir görünüm alınamadı. Daha iyi ışıkta yeniden tarayabilirsiniz.');return;}
    void analyze(run,sources);});session.current=scan;
  try{const media=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1920},height:{ideal:1080}},audio:false});if(run!==epoch.current){media.getTracks().forEach(t=>t.stop());return;}stream.current=media;for(const track of media.getVideoTracks())track.addEventListener('ended',()=>{if(run===epoch.current){stop();setPhase('error');setNotice('Kamera bağlantısı kesildi. Yeniden başlayabilirsiniz.');}},{once:true});inference.current=new SkinInference();await inference.current.initialize();if(run!==epoch.current)return;
   if(!video.current)throw Error('Kamera önizlemesi hazırlanamadı.');video.current.srcObject=media;await video.current.play();setRatio(video.current.videoWidth/video.current.videoHeight);const canvas=document.createElement('canvas'),analysis=document.createElement('canvas');validSince.current=0;misses.current=0;best.current=undefined;poseSince.current=performance.now();lastFrame.current=-1;lastFresh.current=performance.now();display.current=new StablePreviewCrop();motion.current=new SourceMotion();
   const loop=async()=>{if(run!==epoch.current||scan.sealed||!parked.current||!isCameraAllowed()||!video.current)return;const v=video.current,now=performance.now();
    if(v.readyState<2||v.currentTime===lastFrame.current){if(now-lastFresh.current>750){validSince.current=0;setProgress(0);setNotice('Kamera görüntüsü güncel değil.');}frameTimer.current=setTimeout(loop,100);return;}
    lastFrame.current=v.currentTime;lastFresh.current=now;canvas.width=v.videoWidth;canvas.height=v.videoHeight;const ctx=canvas.getContext('2d',{willReadFrequently:true})!;ctx.drawImage(v,0,0);
    const factor=Math.min(1,640/canvas.width);analysis.width=Math.round(canvas.width*factor);analysis.height=Math.round(canvas.height*factor);analysis.getContext('2d')!.drawImage(canvas,0,0,analysis.width,analysis.height);
    let a:FaceAlignment;try{a=await inference.current!.assessAlignment(analysis);}catch{if(run===epoch.current&&!scan.sealed){setPhase('error');setNotice('Yüz modeli yanıt vermedi.');stop();}return;}if(run!==epoch.current||scan.sealed)return;
    const pose=scan.nextPose;if(!pose)return;setCrop(display.current.update(cameraCrop(a.landmarks),performance.now()));const quality=assessDentalCapture(ctx,a,pose),center=a.landmarks?.[1];const moving=center?motion.current.update(center.x,center.y,a.scaleRatio,performance.now()):true;
    const at=performance.now();if(at-poseSince.current>=DENTAL_SKIP_AFTER_MS)setSkipAvailable(true);
    if(quality.valid&&!moving){if(!validSince.current){validSince.current=at;best.current=undefined;}misses.current=0;
     // Keep the sharpest fully valid frame (pixels + its own landmarks) of this hold.
     const sharp=quality.sharp??0;if(!best.current||sharp>best.current.sharp){const copy=best.current?.canvas||document.createElement('canvas');copy.width=canvas.width;copy.height=canvas.height;copy.getContext('2d',{willReadFrequently:true})!.drawImage(canvas,0,0);best.current={sharp,alignment:a,canvas:copy};}
     const held=at-validSince.current;setProgress(Math.min(100,Math.round(held/DENTAL_HOLD_MS*100)));setNotice(DENTAL_GUIDANCE[pose]+' Kısa süre sabit tutun.');
     if(held>=DENTAL_HOLD_MS){const chosen=best.current!;const capture=await captureDental(chosen.canvas,chosen.alignment,pose);
      // The session may have been sealed (skip/cancel) while this frame was encoding:
      // then the capture is discarded and can neither join the sources nor start an analysis.
      if(run!==epoch.current)return;const accepted=scan.accept(capture);if(accepted==='closed')return;
      // Pose skipped while this frame was encoding: drop it and keep guiding the next pose.
      if(accepted==='wrong-pose'){validSince.current=0;best.current=undefined;setProgress(0);frameTimer.current=setTimeout(loop,160);return;}
      validSince.current=0;best.current=undefined;setProgress(0);
      // A frozen/looping source must never fill two poses with one photo.
      if(accepted==='duplicate'){setNotice('Kamera görüntüsü güncel değil.');frameTimer.current=setTimeout(loop,160);return;}
      if(accepted==='complete'){setIndex(4);return;}
      poseSince.current=performance.now();setSkipAvailable(false);setIndex(scan.step);setNotice(DENTAL_GUIDANCE[scan.nextPose!]);}
    }else if(validSince.current&&!moving&&a.faceDetected&&misses.current<DENTAL_HOLD_GRACE_FRAMES){misses.current++;}
    else{validSince.current=0;misses.current=0;best.current=undefined;setProgress(0);setNotice(moving?'Başınızı kısa süre sabit tutun.':quality.reasons[0]);}
    frameTimer.current=setTimeout(loop,160);
   };frameTimer.current=setTimeout(loop,100);
  }catch(error){if(run===epoch.current){stop();setPhase('error');setNotice((error as Error).message||'Kamera açılamadı.');}}
 };
 const saveResult=async()=>{if(!saveAllowed.current||!result||!isParked||saved||saving.current)return;const run=epoch.current,id=resultId.current;if(!id)return;saving.current=true;setSaveBusy(true);setSaveNote(null);try{
  const measurements=dentalRecordMeasurements(result);
  await appendHealthRecord('dental',{id,timestamp:new Date().toISOString(),methodVersion:result.methodVersion,sourceType:result.sourceType||'camera',sourceAssociationVersion:'dental-source-identity-v1',measurements,missingViews:Array.isArray(result.missingViews)?result.missingViews:[],summaryText:'Görünür diş yüzeyleri · çürük adayları, birikim ve dizilim vekilleri; klinik tanı değildir.'},{},()=>run===epoch.current&&parked.current&&saveAllowed.current);
  let photos=false,photoError=false;try{photos=await withRecordsLock(()=>saveDentalPhotos(id,captures.current.map(f=>({...f,landmarks:[],conditions:{}})),()=>run===epoch.current&&parked.current&&saveAllowed.current&&serviceAllowed('dental')));}catch{photoError=true;}
  // Photo storage permitted but nothing stored is a failure, not a numeric-only save.
  if(!photos&&!photoError&&localStorage.getItem(DENTAL_PHOTO_PERMISSION)==='true'&&run===epoch.current)photoError=true;
  if(run===epoch.current){setSaved(true);const text=photoError?'Sayısal sonuç kaydedildi; fotoğraf saklanamadı. Önceki kayıtlar korundu.':photos?'Sayısal sonuç ve izin verilen fotoğraflar yerel geçmişe kaydedildi.':'Yalnız sayısal ölçüm ve aday koordinatları yerel geçmişe kaydedildi.';setNotice(text);setSaveNote({text,error:photoError});}
 }catch(error){if(run===epoch.current){const text=(error as Error).message||'Sonuç kaydedilemedi.';setNotice(text);setSaveNote({text,error:true});}}finally{saving.current=false;if(run===epoch.current)setSaveBusy(false);}};
 const step=phase==='result'?4:Math.min(index,3),photos=captures.current.map(c=>({photo:c.photo,width:c.width,height:c.height}));
 const actionsDisabled=!consent||!isParked;
 return <div className={`space-y-6 mx-auto ${phase==='ready'?'max-w-5xl':'max-w-6xl'}`} data-dental-page><div className="flex items-center gap-3"><h1 className="text-2xl font-bold">{i18nNode(HEALTH_MODULES.dental.name)}</h1><InformationButton title={i18nText("Görünür diş yüzeyleri")}><ul className="list-disc pl-5 space-y-3"><li>{i18nText("Fotoğraf yükleyebilir veya kamerada ön, sağ, sol ve rahat kapanış görünümlerini takip edebilirsiniz.")}</li><li>{i18nText("Ağzınızı zorlamadan ön dişlerinizi gösterin; dişlerinize ışık gelsin. Ağzınıza cisim sokmayın.")}</li><li>{i18nText("Fotoğraftaki işaretler görünür adayları gösterir. Görünmeyen diş yüzeyleri değerlendirilmez.")}</li><li>{i18nText("Birikim görünümü leke, yiyecek ve dolgu ile karışabilir. Dizilim yalnız güvenilir görünen konturlardan hesaplanır.")}</li><li>{i18nText("Fotoğraflar bu oturumda cihazınızda işlenir. Kayıt izni yalnız sayısal sonuç içindir.")}</li></ul></InformationButton></div>
  <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" aria-label={i18nText("Diş fotoğrafı seç")} className="sr-only" disabled={actionsDisabled} onChange={e=>{const file=e.target.files?.[0];if(file)void upload(file);}}/>
  {phase==='ready'?<section className="space-y-5"><HealthPreparation module="dental" actions={<><button className={HEALTH_START_SECONDARY} disabled={actionsDisabled} onClick={()=>fileInput.current?.click()}>{i18nText("Fotoğraf Yükle")}</button><button className={HEALTH_START_ACTION} disabled={actionsDisabled||!isCameraAllowed()} onClick={start}>{i18nText("Diş Taramasını Başlat")}</button></>}/><p role="status" className="text-sm text-slate-400">{i18nNode(notice)}</p></section>
  :<section className={styles.root}>
   {!uploading&&phase!=='error'&&<DentalJourney active={step} skipped={Array.isArray(result?.missingViews)?result.missingViews:skippedPoses}/>}
   {phase==='camera'&&<div className={styles.capture} data-dental-capture>
    <div className={styles.panel}><div className={styles.preview} style={{aspectRatio:ratio*crop.width/crop.height}}><div className="absolute" style={{width:`${100/crop.width}%`,height:`${100/crop.height}%`,left:`${-100*crop.x/crop.width}%`,top:`${-100*crop.y/crop.height}%`}}><video ref={video} muted playsInline autoPlay className="w-full h-full object-fill" data-dental-live-video/></div></div>
     <div className={styles.hold} role="progressbar" aria-label={i18nText('Sabit tutma süresi')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{width:`${progress}%`}}/></div><p className={styles.hint}>{i18nNode(progress>0?'Çekiliyor…':'Başınızı rahat tutun; çekim kendiliğinden yapılır.')}</p></div>
    <div className={styles.panel}><p className={styles.stepCount}>{i18nNode(Math.min(index+1,4))}<small> / 4</small></p><h2>{i18nNode(DENTAL_POSE_LABELS[DENTAL_POSES[Math.min(index,3)]])}</h2><p className={styles.guide}>{i18nNode(DENTAL_GUIDANCE[DENTAL_POSES[Math.min(index,3)]])}</p><p role="status" aria-live="polite">{i18nNode(notice)}</p>
     <div className={styles.actions}>{skipAvailable&&<button type="button" className={styles.secondary} onClick={skipPose} data-dental-skip-pose={DENTAL_POSES[Math.min(index,3)]} {...(index===3?{'data-dental-skip-bite':''}:{})}><SkipForward aria-hidden="true"/>{i18nNode(index===3?'Kapanış görünümünü atla':'Bu görünümü atla')}</button>}<button type="button" className={styles.ghost} onClick={cancel}><X aria-hidden="true"/>{i18nText('İptal et')}</button></div>
     {skipAvailable&&<p className={styles.hint}>{i18nNode(index===3?'Ön dişleriniz birbirine değmiyorsa bu adımı atlayabilirsiniz; dizilim ölçülmez.':'Bu görünüm alınamıyorsa atlayabilirsiniz; sonuçta “alınmadı” olarak gösterilir.')}</p>}</div>
   </div>}
   {phase==='analysis'&&<div className={styles.panel}><p role="status" className={styles.guide}>{i18nNode(notice)}</p><p className="animate-pulse">{i18nText("Yerel analiz sürüyor. İptal edebilirsiniz.")}</p><div className={styles.actions}><button type="button" className={styles.ghost} onClick={cancel}><X aria-hidden="true"/>{i18nText('İptal et')}</button></div></div>}
   {phase==='error'&&<div className={styles.panel}><p role="alert" className={styles.warning}>{i18nNode(notice)}</p><p role="status" className="sr-only">{i18nNode(notice)}</p><div className={styles.actions}><button type="button" className={styles.primary} disabled={actionsDisabled||!isCameraAllowed()} onClick={start}><RotateCcw aria-hidden="true"/>{i18nText('Yeniden tara')}</button><button type="button" className={styles.secondary} disabled={actionsDisabled} onClick={()=>fileInput.current?.click()}><Upload aria-hidden="true"/>{i18nText('Fotoğraf Yükle')}</button><button type="button" className={styles.ghost} onClick={cancel}>{i18nText('Kapat')}</button></div></div>}
   {phase==='result'&&result&&<><p role="status" className="sr-only">{i18nNode(notice)}</p><DentalResults views={result.views} photos={photos} missingViews={result.missingViews||[]} sourceType={result.sourceType} footer={<div className={styles.save}>
    <label><input type="checkbox" checked={save} onChange={e=>setSave(e.target.checked)}/>{i18nText("Sayısal sonucu yerel geçmişime kaydet.")}</label>
    <div className={styles.actions} style={{marginTop:0}}><button type="button" className={styles.primary} disabled={!save||!isParked||saved||saveBusy} onClick={saveResult}>{i18nText("Sonucu kaydet")}</button><Link className={styles.secondary} href={careHref('dental')}>{i18nText("Diş hekimi seçenekleri")}</Link><button type="button" className={styles.ghost} onClick={cancel}>{i18nText('Geçici görüntüleri temizle')}</button></div>
    {saveNote&&<p className={`w-full text-sm ${saveNote.error?styles.warning:''}`} role={saveNote.error?'alert':undefined} data-dental-save-status data-dental-save-error={saveNote.error?'true':undefined}>{i18nNode(saveNote.text)}</p>}
   </div>}/></>}
  </section>}
  <RecordHistory category="dental" parked={isParked}/>
 </div>;
}
