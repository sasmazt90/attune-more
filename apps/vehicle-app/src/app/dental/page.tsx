'use client';
import {HealthPreparation} from '../../components/HealthPreparation';
import {serviceAllowed,useServiceAllowed} from '../../utils/serviceConsent';
import {localBackend} from '../../utils/localBackend';
import { HEALTH_MODULES } from '../../utils/healthModules';
import { useGuidance,qualityGuidance } from '../../utils/audioGuidance';
import {useCallback,useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {careHref} from '../../utils/healthModules';
import {validateDentalFile,UPLOAD_REASONS} from '../../utils/dentalUpload';
import {ResultValue} from '../../components/ResultValue';
import {useVehicle} from '../../context/VehicleContext';
import {InformationButton} from '../../components/InformationButton';
import {RecordHistory} from '../../components/RecordHistory';
import {SkinInference} from '../../utils/skinInference';
import {StablePreviewCrop,SourceMotion,cameraCrop,Crop} from '../../utils/cameraStability';
import {DentalCapture,DENTAL_POSES,DENTAL_GUIDANCE,assessDentalCapture,captureDental} from '../../utils/dentalCapture';
import {appendHealthRecord} from '../../utils/healthRecords';
import {isCameraAllowed} from '../../utils/attuneMode';
import type {FaceAlignment} from '../../utils/skinAnalyzer';
const button='min-h-11 px-5 py-3 rounded-xl border border-sky-400/25 bg-slate-900 disabled:opacity-40';
export default function DentalPage(){
 const {isParked}=useVehicle(),parked=useRef(isParked);parked.current=isParked;
 const consent=useServiceAllowed('dental');
 const [phase,setPhase]=useState<'ready'|'camera'|'analysis'|'result'|'error'>('ready'),[save,setSave]=useState(false),[notice,setNotice]=useState(''),[index,setIndex]=useState(0),[progress,setProgress]=useState(0),[crop,setCrop]=useState<Crop>({x:0,y:0,width:1,height:1}),[ratio,setRatio]=useState(4/3),[result,setResult]=useState<any>(),[shown,setShown]=useState(0);
 const [uploading,setUploading]=useState(false);
 const fileInput=useRef<HTMLInputElement>(null);
 const voice=useGuidance('dental',isParked);
 useEffect(()=>{if(isParked)voice.phase(phase+':'+index,phase==='camera'?(['dental-front','dental-right','dental-left','dental-bite'] as const)[Math.min(index,3)]:undefined);},[voice,isParked,phase,index]);
 useEffect(()=>{const id=(phase==='camera'&&!notice.endsWith('Kısa süre sabit tutun.'))||phase==='error'?qualityGuidance(notice):undefined;voice.issue(id||'',id);},[voice,notice,phase]);
 const video=useRef<HTMLVideoElement>(null),stream=useRef<MediaStream|undefined>(undefined),inference=useRef<SkinInference|undefined>(undefined),epoch=useRef(0),abort=useRef<AbortController|undefined>(undefined),captures=useRef<DentalCapture[]>([]),display=useRef(new StablePreviewCrop()),motion=useRef(new SourceMotion()),validSince=useRef(0),lastFrame=useRef(-1),lastFresh=useRef(0),frameTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
 const stop=useCallback(()=>{voice.cancel();epoch.current++;if(frameTimer.current)clearTimeout(frameTimer.current);stream.current?.getTracks().forEach(track=>track.stop());stream.current=undefined;inference.current?.close();inference.current=undefined;abort.current?.abort();},[voice]);
 const cancel=useCallback(()=>{stop();captures.current=[];setResult(undefined);setUploading(false);if(fileInput.current)fileInput.current.value='';setProgress(0);setPhase('ready');setNotice('Geçici fotoğraf ve sonuçlar temizlendi.');},[stop]);
 useEffect(()=>()=>{stop();captures.current=[];},[stop]);
 useEffect(()=>{const changed=()=>{if(stream.current&&!isCameraAllowed()){cancel();setNotice('Kamera izni geri çekildi.');}};window.addEventListener('attune-privacy',changed);window.addEventListener('storage',changed);return()=>{window.removeEventListener('attune-privacy',changed);window.removeEventListener('storage',changed);};},[cancel]);
 useEffect(()=>{if(!isParked&&phase!=='ready'){cancel();setNotice('Diş taraması yalnız PARK durumunda yapılır.');}},[isParked,phase,cancel]);
 const analyze=async(run:number)=>{
  setPhase('analysis');setNotice('Görünür diş yüzeyleri cihazda analiz ediliyor…');stream.current?.getTracks().forEach(track=>track.stop());inference.current?.close();abort.current=new AbortController();const timer=setTimeout(()=>abort.current?.abort(),30000);
  try{const response=await fetch(localBackend('/api/local-health/dental'),{method:'POST',headers:{'Content-Type':'application/json'},signal:abort.current.signal,body:JSON.stringify({processingConsent:consent,captures:captures.current})});if(!response.ok)throw Error('Yerel diş analizi tamamlanamadı.');const value=await response.json();if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;
   if(value.views.length!==captures.current.length||value.views.some((v:any,i:number)=>v.photoId!==captures.current[i].photoId))throw Error('Kaynak fotoğraf eşleşmesi doğrulanamadı.');
   setResult(value);setShown(0);setPhase('result');setNotice('Görünür alan ön değerlendirmesi. Çürük adayları tanı veya şiddet yüzdesi değildir.');
  }catch(error){if(run===epoch.current){setPhase('error');setNotice((error as Error).name==='AbortError'?'Analiz zamanında tamamlanamadı. Geçici fotoğrafları temizleyip yeniden başlayabilirsiniz.':(error as Error).message);}}finally{clearTimeout(timer);}
 };
 const upload=async(file:File)=>{
  if(!consent||!parked.current||!serviceAllowed('dental'))return;stop();const run=epoch.current;captures.current=[];setResult(undefined);setUploading(true);setPhase('analysis');setNotice('Fotoğraf yerel olarak açılıyor ve yönü düzeltiliyor…');
  abort.current=new AbortController();let deadline:ReturnType<typeof setTimeout>|undefined;
  try{
   const photo=await validateDentalFile(file);if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;
   // The same on-device face model anchors a full portrait to its inner mouth.
   // A partial intraoral photo need not contain a face or obtain camera access.
   const bitmap=await createImageBitmap(file,{imageOrientation:'from-image'});
   let photoLandmarks:FaceAlignment['landmarks'];
   try{
    if(bitmap.width*bitmap.height>24000000||Math.max(bitmap.width,bitmap.height)>8192)throw Error(UPLOAD_REASONS.PIXEL_LIMIT);
    const canvas=document.createElement('canvas'),factor=Math.min(1,640/Math.max(bitmap.width,bitmap.height));canvas.width=Math.round(bitmap.width*factor);canvas.height=Math.round(bitmap.height*factor);canvas.getContext('2d')!.drawImage(bitmap,0,0,canvas.width,canvas.height);
    setNotice('Fotoğraftaki ağız konumu cihazda hazırlanıyor…');inference.current=new SkinInference();await inference.current.initialize();if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;
    const alignment=await inference.current.assessAlignment(canvas);if((alignment.faceCount||0)>1)throw Error('Fotoğrafta yalnız bir kişinin dişleri görünmeli.');if(alignment.faceDetected)photoLandmarks=alignment.landmarks;
   }finally{bitmap.close();inference.current?.close();inference.current=undefined;}
   if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;
   if(abort.current.signal.aborted)throw new DOMException('Fotoğraf işlemi zaman aşımına uğradı.','AbortError');
   setNotice('Görünür diş yüzeyleri cihazda analiz ediliyor…');deadline=setTimeout(()=>abort.current?.abort(),30000);
   const response=await fetch(localBackend('/api/local-health/dental-upload'),{method:'POST',headers:{'Content-Type':'application/json'},signal:abort.current.signal,body:JSON.stringify({processingConsent:true,photo,photoLandmarks})});
   const value=await response.json();if(run!==epoch.current||!parked.current||!serviceAllowed('dental'))return;if(!response.ok)throw Error(UPLOAD_REASONS[value.detail]||'Yerel fotoğraf analizi tamamlanamadı.');
   const view=value.views?.[0];if(value.views?.length!==1||view.sourceType!=='upload'||view.sourceWidth!==value.source?.sourceWidth||view.sourceHeight!==value.source?.sourceHeight||!/^[a-f0-9]{64}$/.test(view.photoId))throw Error('Kaynak fotoğraf eşleşmesi doğrulanamadı.');
   captures.current=[{photo:value.normalizedPhoto,photoId:view.photoId,width:view.sourceWidth,height:view.sourceHeight,pose:view.pose,landmarks:[],conditions:{},sourceType:'upload'}];
   delete value.normalizedPhoto;setResult(value);setShown(0);setPhase('result');setNotice('Tek fotoğrafın görünür yüzey sonucu. Çoklu açı doğrulaması yapılmadı.');
  }catch(error){if(run===epoch.current){captures.current=[];setPhase('error');const message=(error as Error).name==='AbortError'?'Fotoğraf analizi zamanında tamamlanmadı. Başka fotoğraf seçebilirsiniz.':(error as Error).message;setNotice(message);if(!qualityGuidance(message))void voice.say('dental-file');}}
  finally{clearTimeout(deadline);if(run===epoch.current&&fileInput.current)fileInput.current.value='';}
 };
 const start=async()=>{
  if(!consent||!isParked||!isCameraAllowed())return;stop();setUploading(false);captures.current=[];setResult(undefined);setIndex(0);setProgress(0);setPhase('camera');setNotice('Kamera ve cihazdaki yüz modeli hazırlanıyor…');const run=epoch.current;
  try{const media=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1920},height:{ideal:1080}},audio:false});if(run!==epoch.current){media.getTracks().forEach(t=>t.stop());return;}stream.current=media;inference.current=new SkinInference();await inference.current.initialize();if(run!==epoch.current)return;
   if(!video.current)throw Error('Kamera önizlemesi hazırlanamadı.');video.current.srcObject=media;await video.current.play();setRatio(video.current.videoWidth/video.current.videoHeight);const canvas=document.createElement('canvas'),analysis=document.createElement('canvas');validSince.current=0;lastFrame.current=-1;lastFresh.current=performance.now();display.current=new StablePreviewCrop();motion.current=new SourceMotion();
   const loop=async()=>{if(run!==epoch.current||!parked.current||!isCameraAllowed()||!video.current)return;const v=video.current,now=performance.now();
    if(v.readyState<2||v.currentTime===lastFrame.current){if(now-lastFresh.current>750){validSince.current=0;setProgress(0);setNotice('Kamera görüntüsü güncel değil.');}frameTimer.current=setTimeout(loop,100);return;}
    lastFrame.current=v.currentTime;lastFresh.current=now;canvas.width=v.videoWidth;canvas.height=v.videoHeight;const ctx=canvas.getContext('2d',{willReadFrequently:true})!;ctx.drawImage(v,0,0);
    const factor=Math.min(1,640/canvas.width);analysis.width=Math.round(canvas.width*factor);analysis.height=Math.round(canvas.height*factor);analysis.getContext('2d')!.drawImage(canvas,0,0,analysis.width,analysis.height);
    let a:FaceAlignment;try{a=await inference.current!.assessAlignment(analysis);}catch{if(run===epoch.current){setPhase('error');setNotice('Yüz modeli yanıt vermedi.');stop();}return;}if(run!==epoch.current)return;
    const pose=DENTAL_POSES[captures.current.length];setCrop(display.current.update(cameraCrop(a.landmarks),performance.now()));const quality=assessDentalCapture(ctx,a,pose),center=a.landmarks?.[1];const moving=center?motion.current.update(center.x,center.y,a.scaleRatio,performance.now()):true;
    if(quality.valid&&!moving){if(!validSince.current)validSince.current=performance.now();const held=performance.now()-validSince.current;setProgress(Math.min(100,Math.round(held/14)));setNotice(DENTAL_GUIDANCE[pose]+' Kısa süre sabit tutun.');
     if(held>=1400){const capture=await captureDental(canvas,a,pose);if(run!==epoch.current)return;captures.current.push(capture);validSince.current=0;setProgress(0);setIndex(captures.current.length);if(captures.current.length===4){await analyze(run);return;}setNotice(DENTAL_GUIDANCE[DENTAL_POSES[captures.current.length]]);}
    }else{validSince.current=0;setProgress(0);setNotice(moving?'Başınızı kısa süre sabit tutun.':quality.reasons[0]);}
    frameTimer.current=setTimeout(loop,160);
   };frameTimer.current=setTimeout(loop,100);
  }catch(error){if(run===epoch.current){stop();setPhase('error');setNotice((error as Error).message||'Kamera açılamadı.');}}
 };
 const saveResult=async()=>{if(!save||!result||!isParked)return;try{
  // No source pixels, thumbnails, local maps or photos enter persistent records.
  const measurements=result.views.map((view:any)=>({pose:view.pose,quality:view.quality,caries:view.caries,accumulation:view.accumulation,alignment:view.alignment}));
  await appendHealthRecord('dental',{id:crypto.randomUUID(),timestamp:new Date().toISOString(),methodVersion:result.methodVersion,sourceType:result.sourceType||'camera',measurements,summaryText:'Görünür diş yüzeyleri · çürük adayları, birikim ve dizilim vekilleri; klinik tanı değildir.'},{},()=>parked.current&&save);setNotice('Yalnız sayısal ölçüm ve aday koordinatları yerel geçmişe kaydedildi.');
 }catch(error){setNotice((error as Error).message);}};
 const view=result?.views[shown],photo=captures.current[shown];
 return <div className="space-y-6 max-w-6xl mx-auto" data-dental-page><div className="flex items-center gap-3"><h1 className="text-2xl font-bold">{HEALTH_MODULES.dental.name}</h1><InformationButton title="Görünür diş yüzeyleri"><ul className="list-disc pl-5 space-y-3"><li>Fotoğraf yükleyebilir veya kamerada ön, sağ, sol ve rahat kapanış görünümlerini takip edebilirsiniz.</li><li>Ağzınızı zorlamadan ön dişlerinizi gösterin; dişlerinize ışık gelsin. Ağzınıza cisim sokmayın.</li><li>Fotoğraftaki işaretler görünür adayları gösterir. Görünmeyen diş yüzeyleri değerlendirilmez.</li><li>Birikim görünümü leke, yiyecek ve dolgu ile karışabilir. Dizilim yalnız güvenilir görünen konturlardan hesaplanır.</li><li>Fotoğraflar bu oturumda cihazınızda işlenir. Kayıt izni yalnız sayısal sonuç içindir.</li></ul></InformationButton></div>
  <section className="border border-white/10 bg-cockpit-surface rounded-2xl p-5 md:p-7 space-y-5">{phase==='ready'&&<HealthPreparation module="dental"/>}
   <p role="status">{notice}</p>
   {(phase==='ready'||uploading)&&<><div className="flex flex-wrap gap-3 items-center"><input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" aria-label="Diş fotoğrafı seç" className="sr-only" disabled={!consent||!isParked} onChange={e=>{const file=e.target.files?.[0];if(file)void upload(file);}}/><button className={button} disabled={!consent||!isParked} onClick={()=>fileInput.current?.click()}>Fotoğraf Yükle</button><button className={button} disabled={!consent||!isParked||!isCameraAllowed()} onClick={start}>Diş Taramasını Başlat</button></div></>}
   {phase==='camera'&&<div className="space-y-4"><p>{Math.min(index+1,4)} / 4 · {DENTAL_GUIDANCE[DENTAL_POSES[Math.min(index,3)]]}</p><div className="relative rounded-2xl overflow-hidden mx-auto w-full max-w-xl" style={{aspectRatio:ratio*crop.width/crop.height}}><div className="absolute" style={{width:`${100/crop.width}%`,height:`${100/crop.height}%`,left:`${-100*crop.x/crop.width}%`,top:`${-100*crop.y/crop.height}%`}}><video ref={video} muted playsInline autoPlay className="w-full h-full object-fill" data-dental-live-video/></div></div><p>{progress>0?'Çekiliyor…':'Dişlerinizi gösterin; başınızı rahat tutun.'}</p></div>}
   {phase==='analysis'&&<p className="animate-pulse">Yerel analiz sürüyor. İptal edebilirsiniz.</p>}
   {phase==='error'&&<p role="alert" className="text-amber-200">{notice}</p>}
   {phase==='result'&&view&&photo&&<div className="grid lg:grid-cols-2 gap-6 items-start" data-dental-result><div className="space-y-4"><svg viewBox={`0 0 ${photo.width} ${photo.height}`} role="img" aria-label="Gerçek diş fotoğrafı ve görünür adaylar" className="rounded-2xl w-full"><image href={photo.photo} width={photo.width} height={photo.height}/>{view.caries?.candidates?.map((c:any,i:number)=><rect key={i} x={c.bounds.x} y={c.bounds.y} width={c.bounds.width} height={c.bounds.height} fill="none" stroke="#fda4af" strokeWidth={photo.width/300}/>)}{view.accumulation?.quality==='valid'&&view.accumulation.candidates.map((c:any,i:number)=><path key={i} d={c.points.map((p:number[],j:number)=>`${j?'L':'M'}${p[0]} ${p[1]}`).join(' ')+'Z'} fill="#36e4f1" fillOpacity=".25" stroke="#36e4f1"/>)}{view.alignment?.contours?.map((c:any,i:number)=><path key={i} d={c.points.map((p:number[],j:number)=>`${j?'L':'M'}${p[0]} ${p[1]}`).join(' ')+'Z'} fill="none" stroke="#c4b5fd" strokeWidth={photo.width/600}/>)}</svg><div className="flex gap-3 justify-center"><button className={button} onClick={()=>setShown(v=>(v+captures.current.length-1)%captures.current.length)}>Önceki</button><span className="py-3">{shown+1} / {captures.current.length}</span><button className={button} onClick={()=>setShown(v=>(v+1)%captures.current.length)}>Sonraki</button></div></div><div className="space-y-4"><h2 className="text-xl font-bold">Görünür yüzeyler · {photo.pose==='BITE'?'Kapanış görünümü':photo.pose==='FRONT'?'Ön':photo.pose==='RIGHT'?'Anatomik sağ':'Anatomik sol'}</h2><div className="border border-white/10 rounded-2xl p-4"><h3>Çürük adayı</h3><p>{view.caries?.value===null||!view.caries?'Bu görüntü/model için sonuç üretilemedi.':`${view.caries.value} görünür aday`}</p><InformationButton title="Görünür adaylar"><p>İşaretler yalnız fotoğrafta görünen yüzeylere aittir. Aday görülmemesi, görünmeyen yüzeylerin değerlendirilmiş olduğu anlamına gelmez.</p></InformationButton></div><div className="border border-white/10 rounded-2xl p-4"><h3>Birikim görünümü</h3><ResultValue value={view.accumulation?.value??null} status={view.accumulation?.value===null?'Yeterli sınır görünümü yok.':undefined} unit="% görünür sınır alanında aday"/></div><div className="border border-white/10 rounded-2xl p-4"><h3>Görünür ön diş dizilimi</h3>{view.alignment?.rows?Object.entries(view.alignment.rows).map(([which,v]:[string,any])=><p key={which}>{which==='upper'?'Üst':'Alt'} sıra: {v.value===null?'Konturlar güvenilir ayrılamadı.':`${Math.round(v.value)}° yön dağılımı · ${v.contourCount} kontur`}</p>):<p>Bu fotoğrafta diş konturları güvenilir ayrılamadı.</p>}</div></div></div>}
   {phase==='result'&&<><label className="flex gap-3"><input type="checkbox" checked={save} onChange={e=>setSave(e.target.checked)}/>Sayısal sonucu yerel geçmişime kaydet.</label><div className="flex flex-wrap gap-3"><button className={button} disabled={!save||!isParked} onClick={saveResult}>Sonucu kaydet</button><Link className={button} href={careHref('dental')}>Diş hekimi seçenekleri</Link></div></>}
   {phase!=='ready'&&<button className={button} onClick={cancel}>{phase==='result'?'Geçici görüntüleri temizle':'İptal et'}</button>}
  </section><RecordHistory category="dental" parked={isParked}/>
 </div>;
}
