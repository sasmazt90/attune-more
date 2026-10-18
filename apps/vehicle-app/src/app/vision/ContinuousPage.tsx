'use client';
import { HEALTH_MODULES } from '../../utils/healthModules';
import { useEffect, useRef, useState } from 'react';
import { useVehicle } from '../../context/VehicleContext';
import { InformationButton } from '../../components/InformationButton';
import { ContinuousSelector } from '../../components/ContinuousSelector';
import { RecordHistory } from '../../components/RecordHistory';
import { SkinInference } from '../../utils/skinInference';
import { SkinAnalyzer } from '../../utils/skinAnalyzer';
import { ContinuousVisionResult, OrientationResult } from '../../components/ContinuousVisionResult';
import { appendHealthRecord } from '../../utils/healthRecords';
import { isCameraAllowed, isVisionSavingAllowed, isDemoMode } from '../../utils/attuneMode';
import { CALIBRATION_KEY, CONTINUOUS_VISION_PROTOCOL, ContinuousVisionSession, eyeInstruction, summarizeContinuousTrials, ScreenCalibration, calibrationMatches, screenContext, randomAngle, conditionFailure, VisionConditions } from '../../utils/continuousVision';

export default function VisionPage() {
  const { isParked,syncStatus }=useVehicle();
  const [mode,setMode]=useState<'idle'|'prepare'|'practice'|'eye-ready'|'test'|'result'>('idle');
  const [calibration,setCalibration]=useState<ScreenCalibration|null>(null),[calibrationValid,setCalibrationValid]=useState(false);
  const [cardWidth,setCardWidth]=useState(240),[calibrating,setCalibrating]=useState(false);
  const [cameraLive,setCameraLive]=useState(false),[modelActive,setModelActive]=useState(false);
  const [notice,setNotice]=useState(''),[conditions,setConditions]=useState<VisionConditions|null>(null);
  const [angle,setAngle]=useState(0),[target,setTarget]=useState(0),[interacted,setInteracted]=useState(false),[practiceCount,setPracticeCount]=useState(0);
  const [session,setSession]=useState<ContinuousVisionSession|null>(null),[result,setResult]=useState<OrientationResult|null>(null);
  const [revision,setRevision]=useState(0),[preparedPractice,setPreparedPractice]=useState(false),[saveStatus,setSaveStatus]=useState('');
  const video=useRef<HTMLVideoElement>(null),canvas=useRef<HTMLCanvasElement>(null);
  const runtime=useRef({mounted:false,epoch:0,stream:null as MediaStream|null,engine:null as SkinInference|null,raf:0,baseline:null as number|null,stableSince:0,conditions:null as VisionConditions|null,submitting:false,session:null as ContinuousVisionSession|null,paused:false,saving:false});
  const parked=useRef(isParked);parked.current=isParked;
  function stop() {
    const r=runtime.current;r.epoch++;cancelAnimationFrame(r.raf);r.stream?.getTracks().forEach(track=>track.stop());r.stream=null;r.engine?.close();r.engine=null;r.baseline=null;r.stableSince=0;r.conditions=null;r.submitting=false;r.session=null;r.paused=false;
    if(video.current)video.current.srcObject=null;
    if(r.mounted){setCameraLive(false);setModelActive(false);setConditions(null);setInteracted(false);}
  }
  useEffect(()=>{
    const activeRuntime=runtime.current; activeRuntime.mounted=true;
    const verify=()=>{try{const saved=JSON.parse(localStorage.getItem(CALIBRATION_KEY)||'null');setCalibration(saved);setCalibrationValid(calibrationMatches(saved,screenContext()));}catch{setCalibration(null);setCalibrationValid(false);}};
    const privacy=()=>{verify();if(!isCameraAllowed()){stop();setMode('idle');setNotice('Kamera tercihi kapalı. Ölçüm başlatılamaz.');}};
    verify();window.addEventListener('resize',verify);window.visualViewport?.addEventListener('resize',verify);window.addEventListener('storage',privacy);window.addEventListener('attune-privacy',privacy);
    return()=>{activeRuntime.mounted=false;stop();window.removeEventListener('resize',verify);window.visualViewport?.removeEventListener('resize',verify);window.removeEventListener('storage',privacy);window.removeEventListener('attune-privacy',privacy);};
  },[]);
  const [observedClock,setObservedClock]=useState(0);
  useEffect(()=>{if(!cameraLive)return;const timer=setInterval(()=>setObservedClock(performance.now()),200);return()=>clearInterval(timer);},[cameraLive]);
  useEffect(()=>{if(!isParked){stop();setMode('idle');setNotice('');}},[isParked]);
  useEffect(()=>{if(video.current&&runtime.current.stream){video.current.srcObject=runtime.current.stream;void video.current.play().catch(()=>{});}},[mode,cameraLive]);
  async function prepare() {
    if(!parked.current)return;
    stop();setNotice('');setResult(null);setSaveStatus('');setPreparedPractice(false);setMode('prepare');
    if(!isCameraAllowed()){setNotice('Kamera izni Gizlilik tercihlerinde kapalı.');return;}
    const r=runtime.current,epoch=r.epoch;
    const current=()=>r.mounted&&r.epoch===epoch&&parked.current&&isCameraAllowed();
    try {
      const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:640},height:{ideal:480}},audio:false});
      if(!current()){stream.getTracks().forEach(t=>t.stop());return;}
      r.stream=stream;setCameraLive(true);
      const engine=new SkinInference();r.engine=engine;await engine.initialize();if(!current())return;setModelActive(true);
      if(!video.current)throw new Error('Preview');video.current.srcObject=stream;await video.current.play();
      let last=-1;
      const loop=async()=>{
        if(!current())return;
        const v=video.current,c=canvas.current;
        if(!v||!c||stream.getVideoTracks().some(t=>t.readyState==='ended')){setNotice('Kamera bağlantısı kesildi. Ölçüm durduruldu.');stop();return;}
        if(v.readyState>=2&&v.currentTime!==last){
          last=v.currentTime;c.width=v.videoWidth;c.height=v.videoHeight;const ctx=c.getContext('2d',{willReadFrequently:true});
          if(ctx){
            ctx.drawImage(v,0,0,c.width,c.height);const capturedAt=performance.now();
            const a=await engine.assessAlignment(c);if(!current())return;
            const q=SkinAnalyzer.checkQuality(ctx,c.width,c.height,a.faceDetected,a.box);
            const positioned=a.isMediaPipeActive&&a.faceCount===1&&a.isAligned&&Math.abs(a.roll)<=.15&&q.isValid&&!!a.box&&a.box.x>=0&&a.box.y>=0&&a.box.x+a.box.width<=c.width&&a.box.y+a.box.height<=c.height;
            if(positioned){if(!r.stableSince)r.stableSince=capturedAt;if(!r.baseline&&capturedAt-r.stableSince>=1000)r.baseline=a.scaleRatio;}else r.stableSince=0;
            const observed:VisionConditions={observedAt:capturedAt,modelActive:a.isMediaPipeActive,cameraLive:true,faceCount:a.faceCount??0,qualityValid:q.isValid,positionValid:positioned&&capturedAt-r.stableSince>=1000,relativeScaleChange:r.baseline?(a.scaleRatio-r.baseline)/r.baseline:null,eye:r.session?.eye||'RIGHT',eyeEvidence:'unsupported'};
            r.conditions=observed;setConditions(observed);
          }
        }
        if(current())r.raf=requestAnimationFrame(()=>void loop().catch(()=>{if(current()){setNotice('Yüz değerlendirmesi kesildi. Ölçüm durduruldu.');stop();}}));
      };
      void loop().catch(()=>{if(current()){setNotice('Yüz değerlendirmesi kullanılamıyor.');stop();}});
    } catch {if(current()){stop();setNotice('Kamera veya yüz modeli başlatılamadı. Tarayıcı iznini ve bağlantınızı kontrol edin.');}}
  }
  function saveCalibration() {
    if(!parked.current)return;
    const saved:ScreenCalibration={version:1,method:'manual-card',pixelsPerMm:cardWidth/85.6,context:screenContext(),calibratedAt:new Date().toISOString()};
    try{localStorage.setItem(CALIBRATION_KEY,JSON.stringify(saved));setCalibration(saved);setCalibrationValid(true);setCalibrating(false);setNotice('Manuel ölçek kaydedildi. Kart eşleştirmesi cihaz tarafından ölçülmedi.');}catch{setNotice('Ekran ölçeği saklanamadı.');}
  }
  function cameraReady() {return parked.current&&isCameraAllowed()&&calibrationMatches(calibration,screenContext())&&!conditionFailure(runtime.current.conditions,performance.now());}
  function practice(prepared=false) {if(!parked.current||(prepared&&!cameraReady()))return;setPreparedPractice(prepared);setTarget(randomAngle());setAngle(randomAngle());setInteracted(false);setPracticeCount(0);setMode('practice');setNotice('Alıştırma sonuçları kaydedilmez.');}
  function beginSession() {if(!cameraReady()||practiceCount<3)return;const next=new ContinuousVisionSession();runtime.current.session=next;setSession(next);setMode('eye-ready');setNotice('');}
  function beginEye() {const r=runtime.current;if(!cameraReady()||!r.session||r.conditions?.eye!==r.session.eye)return;r.session.present();r.paused=false;setTarget(r.session.targetAngle);setAngle(randomAngle());setInteracted(false);setMode('test');setNotice('');}
  async function saveResult(value:OrientationResult) {
    const r=runtime.current;if(r.saving||!parked.current||!isVisionSavingAllowed()||isDemoMode())return;
    const epoch=r.epoch;r.saving=true;setSaveStatus('Kaydediliyor…');
    try{await appendHealthRecord('vision',value,{},()=>r.mounted&&r.epoch===epoch&&parked.current&&isVisionSavingAllowed()&&!isDemoMode());if(r.mounted)setSaveStatus('Sonuç bu cihazdaki geçmişe kaydedildi.');}
    catch{if(r.mounted)setSaveStatus('Sonuç kaydedilemedi. Açık izin ve cihaz depolamasını kontrol edin.');}
    finally{r.saving=false;}
  }
  function answer(notVisible=false) {
    const r=runtime.current;
    if(!parked.current||r.submitting||(!notVisible&&!interacted))return;
    if(mode==='practice'){r.submitting=true;setPracticeCount(n=>n+1);setTarget(randomAngle());setAngle(randomAngle());setInteracted(false);requestAnimationFrame(()=>{r.submitting=false;});return;}
    const t=r.session;if(mode!=='test'||!t||t.presentationId!==presentationId||r.paused||!cameraReady()||!r.conditions)return;
    if(!t.respond(notVisible?null:angle,interacted,r.conditions,performance.now()))return;
    setInteracted(false);setRevision(n=>n+1);
    if(t.completed){
      const value:OrientationResult={id:crypto.randomUUID(),date:new Date().toISOString(),protocolVersion:CONTINUOUS_VISION_PROTOCOL,trials:t.trials.map(v=>({...v,conditions:{...v.conditions}})),...summarizeContinuousTrials(t.trials),invalidPresentations:t.invalidPresentations,screenCalibration:calibration,distanceMethod:'relative-face-scale-only',eyeOcclusionVerification:'not-camera-verified-user-instruction'};
      stop();setResult(value);setMode('result');setNotice('');setSaveStatus('Sonuç saklanmadı. Kayıt için Gizlilik’te açık saklama tercihi gerekir.');void saveResult(value);
    }else if(t.eye!==r.conditions.eye){r.stableSince=0;r.conditions=null;setConditions(null);setMode('eye-ready');}
    else{t.present();setTarget(t.targetAngle);setAngle(randomAngle());}
    requestAnimationFrame(()=>{r.submitting=false;});
  }
  // The interval forces stale checks, but its previous tick must never be
  // compared to a newer captured frame as if that frame were in the future.
  const blocked=conditionFailure(conditions,typeof performance==='undefined'?observedClock:Math.max(observedClock,performance.now()));
  const gate=blocked||(!calibrationValid?'Ekran ölçeğini manuel olarak hazırlayın.':null);
  useEffect(()=>{const r=runtime.current,t=r.session;if(mode!=='test'||!t)return;if(gate){if(!r.paused){t.invalidate();r.paused=true;setInteracted(false);setRevision(n=>n+1);}}else if(r.paused){t.present();r.paused=false;setTarget(t.targetAngle);setAngle(randomAngle());setInteracted(false);setRevision(n=>n+1);}},[gate,mode]);
  const presentationId=session?.presentationId||0;
  const contrast=mode==='test'&&session?session.contrast:1;
  const size=mode==='test'&&session&&calibration?session.stimulusSizeMm*calibration.pixelsPerMm:calibrationValid&&calibration?2*calibration.pixelsPerMm:96;
  const responseLocked=!isParked || !(mode==='practice'||mode==='test') || (mode==='test'&&(!!gate||runtime.current.paused));
  return <div className="space-y-6" data-vision-mode={mode} data-vision-revision={revision}>
    <div className="flex items-center justify-between gap-3"><h1 className="text-2xl font-bold">{HEALTH_MODULES.vision.name}</h1><InformationButton title="Görme kontrolü hakkında"><p>Tek okla Landolt boşluğunun yönünü eşleştirirsiniz. Yeni görev açısal performans içindir; klinik keskinlik, Snellen, logMAR veya risk eşiği hesaplamaz. Eski dört yönlü kayıtlar kendi protokolünde korunur.</p><p>Kamera tek yüz, görüntü kalitesi, baş konumu ve başlangıca göre yüz ölçeği değişimini izler. Kesin santimetre veya tam göz örtülmesini doğrulamaz. Göz örtülmesi kullanıcı yönergesidir; kamera doğrulaması olarak kaydedilmez. Örtme yüz/model takibini bozarsa deneme duraklar. Klinik sonuç üretilmez.</p><p>Windows demosu gerçek araç ekranına veya sensörlerine bağlı değildir. Önizleme aynalanmaz; göz adları kişinin anatomik sağı ve soludur. Kamera kareleri yalnız bellekte işlenir.</p></InformationButton></div>
    {!isParked&&<p role="alert" className="text-amber-200">{syncStatus==='synced'?'Sürüş sırasında kontrol kapalıdır. Park durumunu bekleyin.':'Araç park durumu doğrulanamıyor. Kontrol kapalıdır.'}</p>}
    {notice&&<p role="status" className="text-sm text-amber-200">{notice}</p>}
    {mode==='idle'&&<section className="rounded-2xl border border-white/10 bg-cockpit-surface p-6 space-y-4"><h2 className="text-xl font-bold">Boşluğun yönünü eşleştirin</h2><p className="text-sm text-amber-200">Yön hizalama ön değerlendirmesi klinik keskinlik testi değildir. Göz örtülmesi ve mutlak mesafe kamera tarafından doğrulanmaz.</p><p className="text-slate-300">Oku halka üzerinde sürükleyin, sonra Yanıtla’ya dokunun.</p><div className="flex flex-wrap gap-3"><button className="min-h-11 rounded-xl bg-togg-turquoise text-togg-darkBlue px-5 font-bold disabled:opacity-40" disabled={!isParked} onClick={()=>void prepare()}>Hazırlığı Başlat</button><button className="min-h-11 px-4 rounded-xl border border-white/20 disabled:opacity-40" disabled={!isParked} onClick={()=>practice()}>Kısa Alıştırma</button></div></section>}
    {mode==='prepare'&&<section className="grid md:grid-cols-2 gap-6 rounded-2xl border border-white/10 bg-cockpit-surface p-6">
      <div className="space-y-3"><video ref={video} muted playsInline autoPlay className="w-full max-h-64 bg-slate-950 rounded-xl object-contain" aria-label="Aynasız canlı kamera önizlemesi"/><p className="text-sm">Kamera: {cameraLive?'açık':'kapalı'} · Yüz değerlendirmesi: {modelActive?'çalışıyor':'bekleniyor'}</p><p className="text-sm text-amber-200" role="status">{blocked}</p></div>
      <div className="space-y-4"><h2 className="font-bold text-xl">Tek hazırlık</h2><div className="flex justify-between gap-2"><p>Ekran ölçeği: {calibrationValid?'manuel ölçek kayıtlı':'kalibrasyon gerekiyor'}</p><InformationButton title="Manuel ekran ölçeği"><p>Gerçek araç profili bulunmuyor. Standart 85,6 mm kartın yalnız kenarını ekrandaki çizgiyle fiziksel olarak eşleştirin. CSS milimetresi veya varsayılan genişlik ölçüm sayılmaz. Kart üzerindeki bilgileri kameraya göstermeyin.</p><p>Zoom, ekran çözünürlüğü veya piksel ölçeği değişirse kalibrasyon kullanılmaz. Aynı çözünürlüklü başka fiziksel ekrana geçiş otomatik algılanamayabilir; ekranı değiştirdiğinizde yeniden kalibre edin. Pencere genişliği tek başına fiziksel piksel ölçeğini değiştirmez.</p></InformationButton></div>
      <button className="min-h-11 px-4 rounded-xl border border-white/20" onClick={()=>setCalibrating(v=>!v)}>{calibrationValid?'Ekran ölçeğini yeniden ayarla':'Ekran ölçeğini ayarla'}</button>
      {calibrating&&<div className="space-y-3"><p className="text-sm">Çizgiyi kartın uzun kenarıyla eşleştirin.</p><div className="overflow-x-auto py-3"><div data-calibration-line className="h-2 bg-togg-turquoise" style={{width:cardWidth}}/></div><input aria-label="Kart kenarının ekrandaki genişliği" type="range" min="80" max="500" step=".1" value={cardWidth} onChange={e=>setCardWidth(Number(e.target.value))} className="w-full min-h-11"/><button className="min-h-11 px-4 rounded-xl bg-togg-turquoise text-togg-darkBlue" onClick={saveCalibration}>Manuel eşleştirmeyi kaydet</button></div>}
      <p className="text-sm text-slate-300">Mutlak mesafe ölçülmüyor. Kamera başlangıç konumuna göre değişimi izler.</p><p className="text-sm text-amber-200">Denemelerde hangi gözü örtmeniz gerektiği gösterilecek. Gözünüze baskı uygulamayın; yönerge kamera doğrulaması değildir.</p><button disabled={!!gate||!isParked} onClick={()=>practice(true)} className="min-h-11 px-4 rounded-xl border border-white/20 disabled:opacity-40">Alıştırma ve denemelere geç</button><button className="min-h-11 px-4 rounded-xl border border-white/20" onClick={()=>practice()}>Alıştırmayla devam et</button></div>
    </section>}
    {mode==='eye-ready'&&session&&<section className="rounded-2xl bg-cockpit-surface p-5 space-y-4"><h2 className="text-xl font-bold">{session.eye==='RIGHT'?'Sağ göz':session.eye==='LEFT'?'Sol göz':'İki göz / kontrast'}</h2><p className="text-lg">{eyeInstruction(session.eye)}</p><p className="text-sm text-amber-200">Örtülme kamera tarafından doğrulanmaz. Bu yönergeyle devam edeceksiniz.</p><button className="min-h-11 px-4 rounded-xl border border-white/20 disabled:opacity-40" disabled={!!gate||!isParked} onClick={beginEye}>Bu koşulda denemeleri başlat</button></section>}
    {(mode==='practice'||mode==='test')&&<section className="rounded-2xl border border-white/10 bg-cockpit-surface p-5 space-y-5"><h2 className="text-lg font-bold">{mode==='practice'?'Alıştırma · sonuç kaydedilmez':'Ön değerlendirme · '+((session?.trials.length||0)+1)+'/24'}</h2><p className="text-sm text-slate-300">{mode==='test'&&session?eyeInstruction(session.eye):'Oku boşluğa yöneltin. Sürüklemek yanıt göndermez.'}</p><div className="grid md:grid-cols-2 gap-6 items-center">
      <div className="min-h-60 flex items-center justify-center rounded-xl bg-white overflow-auto" data-optotype-area><svg data-continuous-optotype width={size} height={size} viewBox="0 0 100 100" className="shrink-0" aria-label="Landolt halkası"><g transform={`rotate(${target} 50 50)`}><circle cx="50" cy="50" r="40" fill="none" stroke={contrast===1?'#111':`rgb(${Math.round(255*(1-contrast))},${Math.round(255*(1-contrast))},${Math.round(255*(1-contrast))})`} strokeWidth="20"/><rect x="50" y="40" width="50" height="20" fill="white"/></g></svg></div>
      <div className="flex flex-col items-center gap-4"><ContinuousSelector angle={angle} disabled={responseLocked} onChange={value=>{setAngle(value);setInteracted(true);}}/><button disabled={responseLocked||!interacted} onClick={()=>answer()} className="min-h-11 w-full max-w-64 px-5 rounded-xl bg-togg-turquoise text-togg-darkBlue font-bold disabled:bg-slate-800 disabled:text-slate-400">Yanıtla</button><button disabled={responseLocked} onClick={()=>answer(true)} className="min-h-11 px-4 rounded-xl border border-white/20 disabled:opacity-40">BOŞLUĞU GÖREMİYORUM</button></div>
    </div>{mode==='practice'&&<p className="text-sm">{practiceCount} alıştırma yanıtı · {calibrationValid?'Manuel ölçek kullanılıyor.':'Bu alıştırma fiziksel ölçekte değildir.'}</p>}{preparedPractice&&mode==='practice'&&<button className="min-h-11 px-4 rounded-xl border border-white/20 disabled:opacity-40" disabled={practiceCount<3||!!gate||!isParked} onClick={beginSession}>Sağ göz denemelerine geç</button>}{cameraLive&&<div className="flex flex-wrap items-center gap-3"><video ref={video} autoPlay muted playsInline className="w-40 rounded-xl object-contain"/><p className="max-w-md text-sm text-amber-200">{gate || 'Kamera ve başlangıca göre konum uygun. Göz örtülmesi doğrulanmadı.'}</p></div>}</section>}
    {mode==='eye-ready'&&cameraLive&&<div className="flex flex-wrap gap-3 items-center"><video ref={video} autoPlay muted playsInline className="w-40 rounded-xl object-contain"/><p role="status" className="text-sm text-amber-200">{gate || 'Kamera ve başlangıca göre konum uygun. Göz örtülmesi doğrulanmadı.'}</p></div>}
    {mode==='result'&&result&&<section className="rounded-2xl border border-white/10 bg-cockpit-surface p-5 space-y-4"><ContinuousVisionResult result={result}/><p role="status" className="text-sm text-amber-200">{saveStatus}</p>{!saveStatus.startsWith('Sonuç bu cihazdaki')&&<button className="min-h-11 px-4 rounded-xl border border-white/20 disabled:opacity-40" onClick={()=>void saveResult(result)} disabled={!isParked||runtime.current.saving||!isVisionSavingAllowed()}>Sonucu Kaydet</button>}</section>}
    {mode!=='idle'&&<button className="min-h-11 px-4 rounded-xl border border-white/20" onClick={()=>{stop();setMode('idle');setNotice(mode==='result'?'Ön değerlendirme kapatıldı.':'Kontrol kapatıldı. Tamamlanmayan denemeler kaydedilmedi.');}}>Kontrolü Bitir</button>}
    <canvas ref={canvas} hidden/>
    <RecordHistory category="vision" parked={isParked}/>
  </div>;
}
