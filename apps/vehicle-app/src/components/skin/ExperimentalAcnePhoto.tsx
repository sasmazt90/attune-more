'use client';
import React,{useEffect,useRef,useState} from 'react';
import {useVehicle} from '../../context/VehicleContext';
import {LOCAL_API_BASE} from '../../utils/previewLocalApi';
import {SkinInference} from '../../utils/skinInference';
import {SkinAnalyzer} from '../../utils/skinAnalyzer';
import {SkinEyewearCheck} from '../../utils/skinEyewear';
import {matchesSkinAngle,angleGuidance,type SkinAngle} from '../../utils/skinMultiAngle';
import {snapshotRawSkinFrame,type SkinSnapshot} from '../../utils/skinSnapshot';
import {expressionObservation} from '../../utils/skinExpression';
import {getRegionData,REGION_ORDER,type SkinRegionData} from '../../data/skinDemoFixture';
import {SkinFacePanel} from './SkinFacePanel';

type Result={experimental:true;status:'ok';requestId:string;photoId:string;sourceWidth:number;sourceHeight:number;candidateCount:number;acneCandidates:NonNullable<SkinSnapshot['acneCandidates']>;model:{verifierSHA256:string;onnxSHA256:string};timing:{modelLoadMs:number;totalAnalysisMs:number};tileCount:number};
const modelHash='0d7bf03ca4d9898ef1b2e78c6d54d61be6aff580329b20b78a9232f79cfd43bb';
const regions:SkinRegionData[]=[{...getRegionData('forehead'),id:'overview',nameTr:'Genel Bakış'},...REGION_ORDER.map(id=>getRegionData(id))];
const messages:Record<string,string>={SKIN_EYEWEAR_PRESENT:'Cilt analizi için gözlüğünüzü çıkarın.',SKIN_EYEWEAR_CHECK_UNCERTAIN:'Göz çevresi doğrulanamadı. Gözlüksüz, net bir fotoğraf seçin.',EXPERIMENTAL_ACNE_V5_MODEL_UNAVAILABLE:'Deneysel yerel model yüklenemedi. Aday sonucu oluşturulmadı.',EXPERIMENTAL_ACNE_V5_DISABLED:'Deneysel mod backend üzerinde kapalı.',NATIVE_TILE_BUDGET_EXCEEDED:'Bu fotoğraf yerel analiz kapsamını aşıyor. Sonuç oluşturulmadı.',EXPERIMENTAL_CAPTURE_QUALITY_FAILED:'Fotoğraf kalitesi analize uygun değil.',EXPERIMENTAL_CAPTURE_POSE_FAILED:'Fotoğraf seçilen poza uygun değil.',LOCAL_ANALYSIS_TIMEOUT:'Yerel analiz zaman sınırına ulaştı. Sonuç oluşturulmadı.',CANCELLED:'Analiz iptal edildi.'};
export function ExperimentalAcnePhoto(){
 const {isParked}=useVehicle();const parked=useRef(isParked);parked.current=isParked;
 const [file,setFile]=useState<File>();const [pose,setPose]=useState<SkinAngle>('FRONT');const [consent,setConsent]=useState(false);const allowed=useRef(consent);allowed.current=consent;
 const [config,setConfig]=useState<'loading'|'available'|'unavailable'>('loading');const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');const [result,setResult]=useState<Result>();const [snapshot,setSnapshot]=useState<SkinSnapshot>();const [region,setRegion]=useState('overview');const [visibleMs,setVisibleMs]=useState<number>();
 const engine=useRef<SkinInference|undefined>(undefined);const glasses=useRef<SkinEyewearCheck|undefined>(undefined);const controller=useRef<AbortController|undefined>(undefined);const epoch=useRef(0);const mounted=useRef(true);const started=useRef(0);
 const cancel=()=>{epoch.current++;controller.current?.abort();glasses.current?.cancel();setBusy(false);setResult(undefined);setSnapshot(undefined);setVisibleMs(undefined);setNotice('Analiz iptal edildi.');};
 useEffect(()=>{const requestEpoch=epoch;mounted.current=true;const c=new AbortController();fetch(`${LOCAL_API_BASE}/api/local-health/skin/acne-v5-config`,{signal:c.signal,cache:'no-store'}).then(r=>r.json()).then(v=>{if(mounted.current)setConfig(v.enabled&&v.status==='available'&&v.verifierSHA256===modelHash?'available':'unavailable');}).catch(()=>{if(mounted.current)setConfig('unavailable');});return()=>{mounted.current=false;requestEpoch.current++;c.abort();controller.current?.abort();glasses.current?.cancel();engine.current?.close();};},[]);
 useEffect(()=>{if(!isParked||!consent){epoch.current++;controller.current?.abort();glasses.current?.cancel();setBusy(false);setResult(undefined);setSnapshot(undefined);setVisibleMs(undefined);}},[isParked,consent]);
 useEffect(()=>{if(!result)return;const ticket=epoch.current;let b=0;const a=requestAnimationFrame(()=>{b=requestAnimationFrame(()=>{if(epoch.current===ticket&&mounted.current)setVisibleMs(performance.now()-started.current);});});return()=>{cancelAnimationFrame(a);cancelAnimationFrame(b);};},[result]);
 const analyze=async()=>{
  if(!file||!consent||!isParked||config!=='available'||busy)return;
  const ticket=++epoch.current;const current=()=>mounted.current&&ticket===epoch.current&&parked.current&&allowed.current;
  const abort=new AbortController();controller.current=abort;const timeout=setTimeout(()=>{abort.abort();glasses.current?.cancel();},45000);started.current=performance.now();setBusy(true);setResult(undefined);setSnapshot(undefined);setVisibleMs(undefined);setNotice('Fotoğraf ve yüz koşulları kontrol ediliyor...');
  try{
   if(file.size>25_000_000)throw Error('Fotoğraf dosyası çok büyük.');
   const image=await createImageBitmap(file,{imageOrientation:'from-image'});const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
   if(canvas.width<16||canvas.height<16||canvas.width>4096||canvas.height>4096||canvas.width*canvas.height>8_400_000){image.close();throw Error('Fotoğraf boyutu yerel analiz kapsamını aşıyor.');}
   const ctx=canvas.getContext('2d',{willReadFrequently:true});if(!ctx){image.close();throw Error('Fotoğraf hazırlanamadı.');}ctx.drawImage(image,0,0);image.close();
   engine.current??=new SkinInference();await engine.current.initialize();if(!current())return;if(abort.signal.aborted)throw Error('LOCAL_ANALYSIS_TIMEOUT');
   // Same <=640-wide analysis canvas and actual product quality/pose gates;
   // original source pixels remain native for snapshot, crops and detector.
   const ratio=Math.min(1,640/canvas.width),analysis=document.createElement('canvas');analysis.width=Math.round(canvas.width*ratio);analysis.height=Math.round(canvas.height*ratio);const qctx=analysis.getContext('2d',{willReadFrequently:true});if(!qctx)throw Error('Kalite kontrolü başlatılamadı.');qctx.drawImage(canvas,0,0,analysis.width,analysis.height);
   let alignment=await engine.current.assessAlignment(analysis);if(!current())return;if(abort.signal.aborted)throw Error('LOCAL_ANALYSIS_TIMEOUT');
   if(!alignment.isMediaPipeActive||alignment.faceCount!==1||!alignment.faceDetected)throw Error('Fotoğrafta tam ve tek bir yüz algılanmalı.');
   const quality=SkinAnalyzer.checkQuality(qctx,analysis.width,analysis.height,alignment.faceDetected,alignment.box);
   if(!quality.isValid)throw Error(quality.warningMessageTr||'Fotoğraf kalitesi analize uygun değil.');
   if(!matchesSkinAngle(alignment,pose))throw Error(angleGuidance(alignment,pose));
   glasses.current??=new SkinEyewearCheck();const eyewear=await glasses.current.assess(canvas,alignment,current);if(!current())return;
   if(eyewear!=='CLEAR')throw Error(eyewear==='EYEWEAR_PRESENT'?messages.SKIN_EYEWEAR_PRESENT:messages.SKIN_EYEWEAR_CHECK_UNCERTAIN);
   if(alignment.box)alignment={...alignment,box:{x:alignment.box.x/ratio,y:alignment.box.y/ratio,width:alignment.box.width/ratio,height:alignment.box.height/ratio}};
   const frame=snapshotRawSkinFrame(canvas,alignment,pose);frame.experimentalAcneV5=true;
   const hash=await crypto.subtle.digest('SHA-256',ctx.getImageData(0,0,canvas.width,canvas.height).data);frame.photoId=Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,'0')).join('');
   const requestId=crypto.randomUUID();setNotice('Deneysel sivilce adayları yerel cihazda hesaplanıyor...');
   const response=await fetch(`${LOCAL_API_BASE}/api/local-health/skin`,{method:'POST',headers:{'Content-Type':'application/json'},signal:abort.signal,body:JSON.stringify({experimentalAcneV5:true,processingConsent:true,hostedProcessingConsent:false,requestId,photo:frame.dataUrl,photoId:frame.photoId,pose,landmarks:frame.landmarks,meshes:frame.meshes,exclusions:frame.exclusions,expressionObservation:expressionObservation(frame.expressionScores,frame.photoId),qualityValid:quality.isValid,conditions:{yaw:alignment.yaw,pitch:alignment.pitch,roll:alignment.roll,scaleRatio:alignment.scaleRatio,avgLuminance:quality.avgLuminance,blurScore:quality.blurScore},temporal:[],capturePreflight:{engine:'browser-mediapipe',faceCount:alignment.faceCount,quality}})});
   const value=await response.json();if(!current())return;
   if(!response.ok)throw Error(messages[value.detail]||'Deneysel yerel analiz tamamlanamadı. Sonuç oluşturulmadı.');
   const v=value as Result;if(v.experimental!==true||v.status!=='ok'||v.requestId!==requestId||v.photoId!==frame.photoId||v.sourceWidth!==frame.width||v.sourceHeight!==frame.height||v.model.verifierSHA256!==modelHash||v.candidateCount!==v.acneCandidates.overview.length)throw Error('Sonuç fotoğraf veya model kimliğiyle eşleşmedi.');
   frame.acneCandidates=v.acneCandidates;setRegion('overview');setSnapshot(frame);setResult(v);setNotice('');
  }catch(error){if(current()){setResult(undefined);setSnapshot(undefined);setNotice(abort.signal.aborted?'Yerel analiz iptal edildi veya zaman sınırına ulaştı; sonuç oluşturulmadı.':error instanceof Error?error.message:'Fotoğraf analizi tamamlanamadı.');}}
  finally{clearTimeout(timeout);if(controller.current===abort)controller.current=undefined;if(current())setBusy(false);}
 };
 const selected=regions.find(r=>r.id===region)||regions[0];
 return <section data-acne-v5-preview className="bg-[#0c1424]/90 border border-slate-800/90 rounded-3xl p-6 md:p-8 w-full max-w-6xl mx-auto my-6">
  <header className="mb-6"><p className="text-togg-turquoise text-sm font-bold">Cilt Sağlığı · Yerel önizleme</p><h1 className="text-3xl font-extrabold text-white mt-2">Deneysel sivilce adayları</h1><p className="text-sm text-slate-300 mt-3">Gözlüksüz, net ve tek yüz içeren bir fotoğraf seçin. Sonuç tanı veya şiddet ölçümü değildir ve geçmişe kaydedilmez.</p></header>
  <div className="grid lg:grid-cols-2 gap-8 items-start">
   <div className="space-y-5">
    <label className="block text-sm text-slate-200">Fotoğraf seç<input aria-label="Fotoğraf seç" type="file" accept="image/png,image/jpeg,image/webp" className="block mt-2 w-full text-sm" onChange={e=>{cancel();setNotice('');setFile(e.target.files?.[0]);}}/></label>
    <label className="block text-sm text-slate-200">Fotoğrafın pozu<select aria-label="Fotoğrafın pozu" value={pose} onChange={e=>{cancel();setNotice('');setPose(e.target.value as SkinAngle);}} className="block mt-2 p-3 rounded-xl bg-slate-900 border border-slate-700"><option value="FRONT">Ön</option><option value="RIGHT">Anatomik sağ</option><option value="LEFT">Anatomik sol</option></select></label>
    <label className="flex items-start gap-3 text-sm text-slate-200"><input aria-label="Yerel fotoğraf işlemeye izin ver" type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)} className="mt-1"/>Seçtiğim fotoğrafın yalnız bu cihazda işlenmesine izin veriyorum. Fotoğraf dış servise gönderilmez.</label>
    {config==='loading'&&<p role="status">Yerel önizleme denetleniyor...</p>}{config==='unavailable'&&<p role="alert" className="text-amber-200">Deneysel mod kapalı veya yerel model kullanılamıyor. Analiz sonucu oluşturulmadı.</p>}{!isParked&&<p role="status" className="text-amber-200">Araç park durumu doğrulanmalı.</p>}
    <div className="flex gap-3"><button disabled={!file||!consent||!isParked||busy||config!=='available'} onClick={()=>void analyze()} className="rounded-full bg-togg-turquoise text-slate-950 px-7 py-3 font-bold disabled:opacity-40">Fotoğrafı analiz et</button>{busy&&<button onClick={cancel} className="border border-slate-600 rounded-full px-5 py-3">İptal</button>}</div>
    {notice&&<p role={busy?'status':'alert'} className="text-sm text-amber-100" data-acne-preview-status>{notice}</p>}
    {result&&<div data-acne-preview-result data-request-id={result.requestId} data-photo-id={result.photoId} data-model-hash={result.model.verifierSHA256} data-visible-ms={visibleMs} className="rounded-2xl border border-togg-turquoise/30 p-5"><p className="font-bold text-xl text-white">{result.candidateCount} sivilce adayı</p><p className="text-sm text-slate-300 mt-2">{result.candidateCount?'Noktalar kabul edilen deneysel adayları gösterir.':'Bu denemede kabul edilen sivilce adayı bulunmadı; bu bir sağlıklılık kararı değildir.'}</p><p className="text-xs text-amber-200 mt-3">Deneysel sonuç · geçmişe kaydedilmedi</p></div>}
   </div>
   <div>{snapshot&&result?<><div className="flex flex-wrap gap-2 mb-4">{regions.map(r=><button key={r.id} disabled={r.id!=='overview'&&!snapshot.meshes[r.id]} onClick={()=>setRegion(r.id)} className={`px-3 py-2 rounded-lg text-xs border disabled:opacity-30 ${region===r.id?'border-togg-turquoise text-togg-turquoise':'border-slate-700 text-slate-300'}`}>{r.nameTr}</button>)}</div><SkinFacePanel currentRegion={selected} snapshot={snapshot} mode="result" selectedCriterion="acne"/></>:<div className="min-h-80 rounded-2xl border border-slate-800 flex items-center justify-center text-slate-400 p-8 text-center">Fotoğrafınız ve aday noktaları burada görünür.</div>}</div>
  </div>
 </section>;
}
