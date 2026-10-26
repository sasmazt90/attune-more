'use client';
import {useLocaleSwitchLock} from '../../i18n/useLocaleSwitchLock';
import {useTranslations} from '../../i18n/LanguageProvider';

import {serviceAllowed} from '../../utils/serviceConsent';
import {careHref} from '../../utils/healthModules';
import { useGuidance,qualityGuidance,skinNeutralGuidance } from '../../utils/audioGuidance';
import { lowerFaceExpressionReason } from '../../utils/skinExpression';
import {SkinEyewearCheck,SkinEyewearGate,SKIN_CAPTURE_POLICY,type EyewearStatus} from '../../utils/skinEyewear';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { validFindings } from '../../utils/skinFindings';
import { useRouter } from 'next/navigation';
import { useVehicle } from '../../context/VehicleContext';
import {
  SkinAnalyzer,
  FaceAlignment,
  ImageQuality,
  RegionMetrics,
  SkinAnalysisResult,
  detectCameraMirrored
} from '../../utils/skinAnalyzer';
import {
  SkinRegionId,
  REGION_ORDER,
  SKIN_REGIONS,
  SkinRegionData,
  getRegionData,
  buildSkinRegionViewModel
} from '../../data/skinDemoFixture';
import { isDemoMode, STORAGE_KEYS, isCameraAllowed,isSkinHostedProcessingAllowed } from '../../utils/attuneMode';
import { appendHealthRecord,withRecordsLock } from '../../utils/healthRecords';
import {saveSkinPhotos} from '../../utils/skinPhotoHistory';
import { rememberSkinSnapshots } from '../../utils/skinVolatileHistory';
import { InformationButton } from '../../components/InformationButton';
import { SkinInference } from '../../utils/skinInference';
import { SKIN_ANGLES, ANGLE_LABELS, AngleCapture, SkinAngle, MultiAngleReference, matchesSkinAngle, angleGuidance, captureSkinAngle, compareMultiAngle, fuseMultiAngleSkinOverview } from '../../utils/skinMultiAngle';
import { SkinSnapshot, snapshotRawSkinFrame as snapshotSkinFrame, snapshotAngleForRegion, assertCompleteFace } from '../../utils/skinSnapshot';
import { measureSkinIndicators, SKIN_SIGN_CONTRACT, validSkinIndicators } from '../../utils/skinIndicators';
import {skinTemporalSupport} from '../../utils/skinTemporalSupport';
import { analyzeAppearance,attachAppearance } from '../../utils/appearanceMeasurements';
import { buildSkinViewModel, skinViewOrder, overviewFromResponse, validSkinOverview, type SkinViewId } from '../../utils/skinOverview';
import { SkinLocalAnalysis } from '../../utils/skinLocalMaps';
import { SkinStartView } from '../../components/skin/SkinStartView';
import { SkinActiveScan } from '../../components/skin/SkinActiveScan';
import type { CameraResolution } from '../../components/CameraPreparation';
import { SkinResultView } from '../../components/skin/SkinResultView';
import { SkinTrendModal } from '../../components/skin/SkinTrendModal';
import { SkinObservationModal } from '../../components/skin/SkinObservationModal';
import { SkinActionsModal } from '../../components/skin/SkinActionsModal';
import { AlertTriangle, RefreshCw, ShieldAlert } from 'lucide-react';

export default function SkinPage() {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const resultPersisted=useRef(false);
  const storageAllowed=()=>serviceAllowed('skin')&&localStorage.getItem('attune_privacy_skin_save_allowed')==='true';
  const temporalSupport=useRef<ReturnType<typeof skinTemporalSupport>[]>([]);
  const localAnalysis=useRef<SkinLocalAnalysis|null>(null);
  const addLocalMaps=async(snapshot:SkinSnapshot,ctx:CanvasRenderingContext2D,valid:boolean,current:()=>boolean,expected?:string,indicators?:import('../../utils/skinIndicators').SkinIndicators,conditions?:Record<string,number>)=>{
    localAnalysis.current??=new SkinLocalAnalysis();
    try {const result=await localAnalysis.current.analyze(snapshot,ctx.getImageData(0,0,snapshot.width,snapshot.height).data,valid,current,expected);if(current()){snapshot.photoId=result.photoId;snapshot.localMaps=result.maps;snapshot.localAnalysis={loadMs:result.loadMs,analysisMs:result.analysisMs,allocatedBytes:result.allocatedBytes};}} catch {/* Optional local layer failure never fabricates a map or discards numerical capture. */}
    if(indicators&&conditions&&snapshot.landmarks){
      if(!snapshot.photoId){const digest=await crypto.subtle.digest('SHA-256',ctx.getImageData(0,0,snapshot.width,snapshot.height).data);snapshot.photoId=Array.from(new Uint8Array(digest)).map(v=>v.toString(16).padStart(2,'0')).join('');}
      const result=await analyzeAppearance(snapshot,valid,conditions,temporalSupport.current,current);
      if(current()){attachAppearance(indicators,result);snapshot.experimentalAcneV5=result.acneRuntime?.status==='measured';snapshot.general=overviewFromResponse(result);snapshot.localMaps=result.maps;snapshot.contoursMeasured=result.contours;snapshot.acneCandidates=Object.fromEntries(Object.entries(result.measurements).map(([region,rows])=>[region,rows.find(v=>v.id==='acne'&&v.value!==null)?.components.bounds||[]]));
        snapshot.acneCandidates.overview=[...new Map(Object.values(snapshot.acneCandidates).flat().map((box:any)=>[box.candidateId||`${box.x}:${box.y}:${box.width}:${box.height}`,box])).values()];}
    }
  };
  useEffect(()=>()=>{localAnalysis.current?.cancel();},[]);
  const router = useRouter();
  const { isParked, state } = useVehicle();

  const [scanState, setScanState] = useState<'READY' | 'CAMERA_ACTIVE' | 'COMPLETED' | 'ERROR'>('READY');
  useLocaleSwitchLock('skin',scanState==='CAMERA_ACTIVE');
  const activeScanRef=useRef(false);activeScanRef.current=scanState==='CAMERA_ACTIVE';
  const hostedConsentRef=useRef(isSkinHostedProcessingAllowed());
  const [preparationPhase,setPreparationPhase]=useState<string|null>(null);
  const [preparationSeconds,setPreparationSeconds]=useState(0);
  useEffect(()=>{if(!preparationPhase || scanState!=='CAMERA_ACTIVE'){setPreparationSeconds(0);if(scanState!=='CAMERA_ACTIVE')setPreparationPhase(null);return;}setPreparationSeconds(0);const started=performance.now();const timer=setInterval(()=>setPreparationSeconds(Math.floor((performance.now()-started)/1000)),1000);return()=>clearInterval(timer);},[preparationPhase,scanState]);
  const [photoNotice,setPhotoNotice]=useState('');
  const persistPhotos=async(id:string,frames:Partial<Record<SkinAngle,SkinSnapshot>>,isCurrent:()=>boolean)=>{if(!isCurrent())return;setPhotoNotice('');try{await withRecordsLock(()=>saveSkinPhotos(id,frames,isCurrent));}catch{if(isCurrent())setPhotoNotice('Cilt fotoğrafı kaydedilemedi. Sayısal sonuçlar korunuyor.');}};
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [scanProgress, setScanProgress] = useState<number>(0);
  const [multiAngle, setMultiAngle] = useState(true);
  const [angleIndex, setAngleIndex] = useState(0);
  const [completedAngles, setCompletedAngles] = useState<SkinAngle[]>([]);
  const angleRuntime = useRef({ enabled: true, index: 0, captures: {} as Partial<Record<SkinAngle, AngleCapture>> });
  const [selectedRegionId, setSelectedRegionId] = useState<SkinViewId>('forehead');
  const [activeModal, setActiveModal] = useState<'trend' | 'observation' | 'actions' | null>(null);

  // Video & Canvas referansları (MediaPipe kamera ve analiz motoru)
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [cameraFresh,setCameraFresh]=useState(false);
  const [cameraResolution,setCameraResolution]=useState<CameraResolution>();
  useEffect(()=>{
    if(!mediaStream || scanState!=='CAMERA_ACTIVE'){setCameraFresh(false);return;}
    let lastTime=-1,lastChange=0;
    const timer=setInterval(()=>{const video=videoRef.current,now=performance.now();if(video && video.readyState>=2 && video.currentTime!==lastTime){lastTime=video.currentTime;lastChange=now;}setCameraFresh(lastChange>0 && now-lastChange<750);},150);
    return()=>clearInterval(timer);
  },[mediaStream,scanState]);
  const [isMediaPipeLoaded, setIsMediaPipeLoaded] = useState<boolean>(false);
  const isMediaPipeLoadedRef = useRef<boolean>(false);
  const inferenceRef = useRef<SkinInference | null>(null);
  const initializationFailedRef = useRef(false);
  const [initializationEpoch, setInitializationEpoch] = useState(0);
  const demoTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [isLiveVideo, setIsLiveVideo] = useState<boolean>(false);

  // Hizalama ve kalite telemetrisi
  const [alignment, setAlignment] = useState<FaceAlignment>({
    faceDetected: false,
    isMediaPipeActive: false,
    yaw: 0,
    pitch: 0,
    roll: 0,
    scaleRatio: 0,
    isAligned: false,
    guidanceTextTr: 'Kamera hazırlanıyor...'
  });
  const [quality, setQuality] = useState<ImageQuality>({
    isValid: false,
    avgLuminance: 0,
    blurScore: 0,
    status: 'NO_FACE'
  });
  const [guidanceText, setGuidanceText] = useState<string>('Lütfen başınızı sabit tutun.');
  const [eyewearStatus,setEyewearStatus]=useState<EyewearStatus|'PENDING'>('PENDING');
  const voice=useGuidance('skin',isParked);
  const [lowerFaceIssue,setLowerFaceIssue]=useState<string>();
  const introPendingRef=useRef(false);
  const [introPending,setIntroPending]=useState(false);
  useEffect(()=>{
    const ended=(event:Event)=>{const detail=(event as CustomEvent<{id:string;event:string}>).detail;if(detail?.event==='ended'&&['skin-front','skin-right','skin-left'].includes(detail.id)){introPendingRef.current=false;setIntroPending(false);}};
    window.addEventListener('attune-guidance-event',ended);return()=>window.removeEventListener('attune-guidance-event',ended);
  },[]);
  useEffect(()=>{
    const id=isParked&&scanState==='CAMERA_ACTIVE'?(['skin-front','skin-right','skin-left'] as const)[angleIndex]:undefined;
    // The same render's initial quality text must not cancel the phase clip
    // before its fetch/play starts. Keep all visual capture gates independent.
    introPendingRef.current=!!id;setIntroPending(!!id);
    if(isParked)voice.phase(scanState+':'+angleIndex,id);
  },[voice,isParked,scanState,angleIndex]);
  useEffect(()=>{const active=scanState==='CAMERA_ACTIVE'&&serviceAllowed('skin')&&isCameraAllowed()&&!introPendingRef.current&&!preparationPhase&&!quality.status.startsWith('EYEWEAR');const id=active?(lowerFaceIssue?(lowerFaceIssue.startsWith('POSE_')?(['skin-front','skin-right','skin-left'] as const)[angleIndex]:skinNeutralGuidance()):!guidanceText.startsWith('Hizalama uygun')?qualityGuidance(guidanceText):undefined):undefined;voice.issue(id?lowerFaceIssue||id:'',id);},[voice,guidanceText,scanState,preparationPhase,quality.status,introPending,lowerFaceIssue,angleIndex]);

  const snapshotFrames = useRef<Partial<Record<SkinAngle, SkinSnapshot>>>({});
  const snapshotRecord = useRef<string | null>(null);
  const [snapshots, setSnapshots] = useState<Partial<Record<SkinAngle, SkinSnapshot>>>({});
  const [analysisResult, setAnalysisResult] = useState<SkinAnalysisResult | null>(null);

  // Real-time döngü referansları
  const consecutiveValidFramesRef = useRef<number>(0);
  const mountedRef = useRef(true);
  const acquisitionRef = useRef(0);
  const persistingRef = useRef(false);
  const parkedRef = useRef(isParked);
  parkedRef.current = isParked;

  // URL parametresi ile durum ve test yönetimi
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const stateParam = params.get('state');
    const resultParam = params.get('result');
    const regionParam = params.get('region');
    const modalParam = params.get('modal');

    if (stateParam === 'ready') {
      setScanState('READY');
    } else if (stateParam === 'active') {
      setScanState('CAMERA_ACTIVE');
      setScanProgress(75);
    } else if (stateParam === 'completed' || resultParam === 'true') {
      setScanState('COMPLETED');
    }

    if (regionParam) {
      const match = REGION_ORDER.find(
        (id, idx) => id.toLowerCase() === regionParam.toLowerCase() || String(idx + 1) === regionParam
      );
      if (match) setSelectedRegionId(match);
    }

    if (modalParam === 'trend') setActiveModal('trend');
    else if (modalParam === 'observation') setActiveModal('observation');
    else if (modalParam === 'actions') setActiveModal('actions');
  }, []);

  // MediaPipe FaceLandmarker'ı başlat
  useEffect(() => {
    if (isDemoMode()) return;
    initializationFailedRef.current = false;
    isMediaPipeLoadedRef.current = false;
    setIsMediaPipeLoaded(false);
    let isMounted = true;
    let engine: SkinInference;
    try {
      engine = new SkinInference();
      inferenceRef.current = engine;
      engine.onPhase = phase => { if (mountedRef.current && activeScanRef.current) {setPreparationPhase(phase);setGuidanceText(phase === 'MODEL' ? 'Yerel portre modeli hazırlanıyor… İptal edebilirsiniz.' : phase === 'INFERENCE' ? 'Kabul edilen fotoğrafın arka planı ayrılıyor…' : 'Saç ve cilt sınırları kaynak piksellerinden iyileştiriliyor…');} };
    } catch {
      initializationFailedRef.current = true;
      return;
    }
    engine.initialize().then(() => {
      if (isMounted) {
        isMediaPipeLoadedRef.current = true;
        setIsMediaPipeLoaded(true);
      }
    }).catch(() => {
      if (isMounted) {
        initializationFailedRef.current = true;
        setErrorMessage('Cilt analiz motoru başlatılamadı. Lütfen bağlantınızı kontrol edip tekrar deneyin.');
        setScanState(previous => previous === 'CAMERA_ACTIVE' ? 'ERROR' : previous);
      }
    });
    return () => {
      isMounted = false;
      engine.close();
      inferenceRef.current = null;
    };
  }, [initializationEpoch]);

  // Invalidate late camera acquisition on exit. The scan effect owns live RAF/stream cleanup.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      snapshotFrames.current = {}; snapshotRecord.current = null;
      acquisitionRef.current += 1;
      if (demoTimerRef.current) {
        clearInterval(demoTimerRef.current);
      }
    };
  }, []);

  // Cancel pending acquisition/demo work when driving or privacy permission is revoked.
  useEffect(() => {
    const revoke = () => {
      const changed=hostedConsentRef.current!==isSkinHostedProcessingAllowed();hostedConsentRef.current=isSkinHostedProcessingAllowed();
      if (!parkedRef.current || !isCameraAllowed() || changed&&activeScanRef.current) {
        voice.cancel();setLowerFaceIssue(undefined);
        acquisitionRef.current += 1;
        snapshotFrames.current = {}; snapshotRecord.current = null; setSnapshots({});
        if (demoTimerRef.current) clearInterval(demoTimerRef.current);
        setScanState('READY');
        setMediaStream(null);
        setIsLiveVideo(false);
      }
    };
    revoke();
    window.addEventListener('storage', revoke);
    window.addEventListener('attune-privacy', revoke);
    return () => {
      window.removeEventListener('storage', revoke);
      window.removeEventListener('attune-privacy', revoke);
    };
  }, [isParked, voice]);

  useEffect(() => {
    const refresh = () => {
      if (scanState !== 'COMPLETED' || isDemoMode() || !resultPersisted.current) return;
      try {
        const latest = JSON.parse(localStorage.getItem(STORAGE_KEYS.LATEST_SKIN) || 'null');
        if (latest?.id !== snapshotRecord.current) { snapshotFrames.current = {}; snapshotRecord.current = null; setSnapshots({}); }
        if (latest?.regions) setAnalysisResult(latest);
        else { setAnalysisResult(null); setScanState('READY'); }
      } catch { setErrorMessage('Kayıt durumu doğrulanamadı.'); setScanState('ERROR'); }
    };
    window.addEventListener('storage', refresh); window.addEventListener('attune-records', refresh);
    return () => { window.removeEventListener('storage', refresh); window.removeEventListener('attune-records', refresh); };
  }, [scanState]);

  useEffect(() => {
    if (isParked && typeof window !== 'undefined' && window.location.search.includes('view=latest')) {
      try {
        const stored = localStorage.getItem(STORAGE_KEYS.LATEST_SKIN);
        const frames = (window as any).__attuneInitialSnapshots;
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed && parsed.regions) {
            if (frames) {
              snapshotFrames.current = frames;
              snapshotRecord.current = parsed.id;
              setSnapshots(frames);
            }
            setSelectedRegionId(parsed.general ? 'overview' : 'forehead');
            setAnalysisResult(parsed);
            setScanState('COMPLETED');
          }
        }
      } catch {}
    }
  }, [isParked]);

  // Real modda COMPLETED durumu doğrulaması: Kayıtlı gerçek analiz yoksa COMPLETED state'e izin verilmez
  useEffect(() => {
    if (scanState === 'COMPLETED' && !isDemoMode() && !analysisResult) {
      try {
        const stored = localStorage.getItem(STORAGE_KEYS.LATEST_SKIN);
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed && parsed.regions) {
            setAnalysisResult(parsed);
            return;
          }
        }
      } catch {}
      setErrorMessage('Kayıtlı gerçek analiz sonucu bulunamadı. Lütfen yeni bir tarama yapın.');
      setScanState('ERROR');
    }
  }, [scanState, analysisResult]);

  // Functional selection reads the latest region; handlers stay stable until results change.
  const handlePrevRegion = useCallback(() => {
    const order = skinViewOrder(analysisResult);
    setSelectedRegionId(current => order[(order.indexOf(current) - 1 + order.length) % order.length]);
  }, [analysisResult]);
  const handleNextRegion = useCallback(() => {
    const order = skinViewOrder(analysisResult);
    setSelectedRegionId(current => order[(order.indexOf(current) + 1) % order.length]);
  }, [analysisResult]);

  // Klavye ile döngüsel bölge navigasyonu ve modal kontrolü
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (activeModal !== null) {
        if (e.key === 'Escape') setActiveModal(null);
        return;
      }
      if (scanState !== 'COMPLETED') return;

      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        handlePrevRegion();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        handleNextRegion();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [scanState, activeModal, handlePrevRegion, handleNextRegion]);

  // Demo modda kamera olmadan sentetik portreyle doğrudan deterministik tarama
  const startSyntheticDemoScan = () => {
    if (demoTimerRef.current) {
      clearInterval(demoTimerRef.current);
      demoTimerRef.current = null;
    }
    setScanProgress(0);
    setGuidanceText('Demo portre taranıyor...');
    let currentProg = 5;
    demoTimerRef.current = setInterval(() => {
      currentProg += 5;
      if (currentProg >= 100) {
        if (demoTimerRef.current) {
          clearInterval(demoTimerRef.current);
          demoTimerRef.current = null;
        }
        setScanProgress(100);
        finishScan(true);
      } else {
        setScanProgress(currentProg);
      }
    }, 80);
  };

  // Taramayı başarıyla tamamlama fonksiyonu
  const finishScan = async (
    isDemo: boolean = false,
    finalAlignment?: FaceAlignment,
    finalQuality?: ImageQuality
  ) => {
    if (persistingRef.current) return;
    persistingRef.current = true;
    const acquisition = acquisitionRef.current;
    const validCapture = () => serviceAllowed('skin') && mountedRef.current && parkedRef.current && acquisitionRef.current === acquisition && isCameraAllowed();
    try {
    if (demoTimerRef.current) {
      clearInterval(demoTimerRef.current);
      demoTimerRef.current = null;
    }

    if (isDemo) {
      // DEMO MODE: Fikstür verisini kullanır, gerçek kullanıcı anahtarını bozmaz.
      // Demo metrikleri her zaman fikstürden geldiğinden usedMediaPipe her zaman false'tur.
      const demoResult: SkinAnalysisResult = {
        id: `demo-skin-${Date.now()}`,
        timestamp: new Date().toISOString(),
        quality: { isValid: true, avgLuminance: 120, blurScore: 8.5, status: 'OPTIMAL' },
        regions: getDefaultEngineRegions(),
        highestChangeRegion: 'Sağ Yanak',
        highestChangePct: 22,
        referralSuggested: true,
        isBaseline: false,
        clinicalNoteTr: 'Sağ yanak bölgesinde baz çizgi referansına göre %22 görsel değişim gözlendi.',
        usedMediaPipe: false
      };

      try {
        localStorage.setItem(STORAGE_KEYS.DEMO_SKIN_RESULT, JSON.stringify(demoResult));
      } catch {}

      setAnalysisResult(demoResult);
      setSelectedRegionId('forehead');
      setScanState('COMPLETED');
      return;
    }

    // REAL MODE: Yalnızca MediaPipe aktifse ve doğrulanmışsa hesaplar
    const alignToUse = finalAlignment || alignment;
    const qualToUse = finalQuality || quality;
    const isMPLoaded = isMediaPipeLoadedRef.current || isMediaPipeLoaded;

    const canvas = canvasRef.current;
    if (!canvas || !isMPLoaded || !alignToUse.isMediaPipeActive) {
      setErrorMessage(
        'Cilt analiz motoru kullanılamıyor. Lütfen kamera iznini ve bağlantınızı kontrol edip tekrar deneyin.'
      );
      setScanState('ERROR');
      return;
    }

    if (!qualToUse.isValid || !alignToUse.isAligned || !alignToUse.faceDetected) {
      setErrorMessage('Yüz, poz veya görüntü kalitesi geçerli değil; tarama kaydedilmedi.');
      setScanState('ERROR');
      return;
    }

    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) {
      setErrorMessage('Tuval grafik bağlamı başlatılamadı. Lütfen sayfayı yenileyip tekrar deneyin.');
      setScanState('ERROR');
      return;
    }

    let regionMetrics: Record<string, RegionMetrics>;
    try {
      regionMetrics = SkinAnalyzer.analyzeRegions(ctx, canvas.width, canvas.height, alignToUse);
    } catch (err: any) {
      console.warn('MediaPipe ROI analizi başarısız:', err);
      setErrorMessage(
        'Yüz ROI anatomik bölgeleri tespit edilemedi. Lütfen doğrudan kameraya bakın ve ışığı artırın.'
      );
      setScanState('ERROR');
      return;
    }

    try { assertCompleteFace(alignToUse, canvas.width, canvas.height); } catch { setErrorMessage('Alın ve çenenin tamamı kadrajda olmalı. İlgili pozu yeniden alın.'); setScanState('ERROR'); return; }
    setGuidanceText('Yerel görünüm ölçümleri hazırlanıyor; iptal edebilirsiniz.');
    setPreparationPhase(null);
    if (!validCapture()) return;
    const acceptedSnapshot = snapshotSkinFrame(canvas, alignToUse, 'FRONT');
    const indicators=measureSkinIndicators(ctx,acceptedSnapshot,qualToUse);
    try{
      await addLocalMaps(acceptedSnapshot,ctx,qualToUse.isValid,validCapture,undefined,indicators,{yaw:alignToUse.yaw,pitch:alignToUse.pitch,roll:alignToUse.roll,scaleRatio:alignToUse.scaleRatio,avgLuminance:qualToUse.avgLuminance,blurScore:qualToUse.blurScore});
    }catch(error){
      if(!validCapture())return;
      setErrorMessage(error instanceof Error?error.message:'Yerel görünüm analizi tamamlanamadı.');setScanState('ERROR');return;
    }
    if(!validCapture())return;

    const capturePose = { yaw: alignToUse.yaw, pitch: alignToUse.pitch, roll: alignToUse.roll, scaleRatio: alignToUse.scaleRatio };
    // Legacy metrics remain available to old records; they do not drive V3 claims.
    const comparison = SkinAnalyzer.compareWithBaseline(regionMetrics, null, 20.0);

    const finalResult: SkinAnalysisResult = {
      schemaVersion:3,indicatorContract:SKIN_SIGN_CONTRACT,indicators,
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      quality: qualToUse,
      regions: comparison.comparedRegions,
      highestChangeRegion: '',
      highestChangePct: 0,
      referralSuggested: false,
      isBaseline: false, analysisMode: 'instant-appearance-v2',
      clinicalNoteTr: 'Mevcut taramanın bölgesel görünüm vekilleri; hastalık veya kalibre klinik şiddet değildir.',
      comparisonUnavailable: false,
      comparisonScope: 'single-front-v1', capturePose,
      comparisonReasons: [],
      usedMediaPipe: true
    };

    finalResult.analysisId=finalResult.id;
    finalResult.general=acceptedSnapshot.general ? {...acceptedSnapshot.general,analysisId:finalResult.id} : undefined;
    finalResult.captures={FRONT:{captureId:acceptedSnapshot.photoId!,pose:"FRONT",sourceWidth:acceptedSnapshot.width,sourceHeight:acceptedSnapshot.height}};
    // Current-session measurements never read/write personal reference keys.
    if (validSkinIndicators(indicators) && validSkinOverview(finalResult.general,finalResult.id) && SkinAnalyzer.canPersistResult(finalResult)) {
      try {
        resultPersisted.current=storageAllowed();
        if(resultPersisted.current)await appendHealthRecord('skin', finalResult, {}, () => validCapture() && storageAllowed());
        if (!validCapture()) return;
      } catch (e) {
        setErrorMessage('Tarama metrikleri hesaplandı ancak kayıt tamamlanamadı. Geçmiş kaydı oluşturulduğu doğrulanamadı.');
        setScanState('ERROR');
        return;
      }
    } else {
      setErrorMessage('MediaPipe doğrulaması olmadan sağlık telemetrisi kaydedilemez.');
      setScanState('ERROR');
      return;
    }

    const snapshot = acceptedSnapshot;
    snapshotFrames.current = { FRONT: snapshot }; rememberSkinSnapshots(finalResult.id,{FRONT:snapshot}); await persistPhotos(finalResult.id,{FRONT:snapshot},validCapture); if(!validCapture())return; setSelectedRegionId(finalResult.general ? 'overview' : 'forehead'); snapshotRecord.current = finalResult.id; setSnapshots({ FRONT: snapshot });
    setMediaStream(null); setIsLiveVideo(false);
    setAnalysisResult(finalResult);
    // En yüksek değişimin olduğu bölgeye odaklan veya varsayılan sağ yanak
    setScanState('COMPLETED');
    } catch {
      if (validCapture()) {
        setErrorMessage('Yerel görünüm analizi tamamlanamadı.');
        setScanState('ERROR');
      }
    } finally { persistingRef.current = false; }
  };

  // Real-time video işleme döngüsü (requestAnimationFrame)
  const finishMultiScan = async (captures: Record<SkinAngle, AngleCapture>) => {
    if (persistingRef.current) return;
    persistingRef.current = true;
    const acquisition = acquisitionRef.current;
    const validCapture = () => serviceAllowed('skin') && mountedRef.current && parkedRef.current && acquisitionRef.current === acquisition && isCameraAllowed();
    const current: MultiAngleReference = { id: crypto.randomUUID(), timestamp: new Date().toISOString(), schemaVersion: 2, scope: 'three-angle-v2', captures };
    try {
      const comparison = compareMultiAngle(current, null);
      const indicators=Object.assign({},captures.FRONT.indicators,captures.RIGHT.indicators,captures.LEFT.indicators);
      const finalResult: SkinAnalysisResult = {
        schemaVersion:3,indicatorContract:SKIN_SIGN_CONTRACT,indicators,
        id: current.id, timestamp: current.timestamp, quality: captures.FRONT.quality, regions: comparison.regions,
        usedMediaPipe: true, isBaseline: false, analysisMode: 'instant-appearance-v2', highestChangeRegion: '',
        highestChangePct: 0, referralSuggested: false,
        comparisonScope: 'three-angle-v2', capturePose: captures.FRONT.pose,
        comparisonUnavailable: false, comparisonReasons: [],
        clinicalNoteTr: 'Mevcut taramanın bölgesel renk ve görünüm vekilleri. Hastalık tanısı veya kalibre edilmiş klinik şiddet değildir; eski ölçümler yeni yönteme dönüştürülmez.'
      };
      finalResult.analysisId=finalResult.id;
      finalResult.captures=Object.fromEntries(Object.entries(snapshotFrames.current).map(([pose,frame])=>[pose,{captureId:frame.photoId!,pose,sourceWidth:frame.width,sourceHeight:frame.height}]));
      const fusedGeneral=fuseMultiAngleSkinOverview(snapshotFrames.current.FRONT?.general,indicators,finalResult.captures);
      finalResult.general=fusedGeneral ? {...fusedGeneral,analysisId:finalResult.id} : undefined;
      for (const frame of Object.values(snapshotFrames.current)) {
        if (frame && finalResult.general) frame.general = finalResult.general;
      }
      if (!validSkinIndicators(indicators) || !validSkinOverview(finalResult.general,finalResult.id) || !SkinAnalyzer.canPersistResult(finalResult)) throw new Error('Invalid metrics');
      // Numeric history never contains pixels; photo retention has separate consent.
      resultPersisted.current=storageAllowed();
      if(resultPersisted.current)await appendHealthRecord('skin', finalResult, {}, () => validCapture() && storageAllowed());
      if (!validCapture()) return;
      rememberSkinSnapshots(finalResult.id,snapshotFrames.current); await persistPhotos(finalResult.id,snapshotFrames.current,validCapture); if(!validCapture())return; setSelectedRegionId(finalResult.general ? 'overview' : 'forehead'); snapshotRecord.current = finalResult.id; setSnapshots({ ...snapshotFrames.current });
      setMediaStream(null); setIsLiveVideo(false);
      setAnalysisResult(finalResult); setScanProgress(100); setScanState('COMPLETED');
    } catch {
      if (!validCapture()) return;
      setErrorMessage('Üç açılı ölçüm veya geçmiş kaydı doğrulanamadı.'); setScanState('ERROR');
    } finally { persistingRef.current = false; }
  };
  const finishMultiRef = useRef(finishMultiScan);
  finishMultiRef.current = finishMultiScan;
  const finishRef = useRef(finishScan);
  finishRef.current = finishScan;
  useEffect(() => {
    if (!(mediaStream && videoRef.current && scanState === 'CAMERA_ACTIVE') || !isParked) return;
    const video = videoRef.current;
    videoRef.current.srcObject = mediaStream;
    let cancelled = false;
    let frameId: number | null = null;
    let lastVideoTime = -1;
    const finishScan = (...args: Parameters<typeof finishRef.current>) => finishRef.current(...args);
    void video.play().catch(() => {
      if (!cancelled) {
        setErrorMessage('Video oynatma başlatılamadı. Lütfen tekrar deneyin.');
        setScanState('ERROR');
      }
    });
    const schedule = () => {
      frameId = requestAnimationFrame(loop);
    };
    consecutiveValidFramesRef.current = 0;
    setScanProgress(0);

    const isDemo = isDemoMode();

    // Match the working 640-wide acquisition scale without degrading the
    // accepted native photo or using any display crop/zoom in measurement.
    const analysisCanvas=document.createElement('canvas');
    const eyewearCheck=new SkinEyewearCheck(),eyewearGate=new SkinEyewearGate();
    setEyewearStatus('PENDING');
    const loop = async () => {
      if (cancelled) return;
      if (!isCameraAllowed() || !parkedRef.current || mediaStream.getVideoTracks().every(t => t.readyState === 'ended')) {
        setErrorMessage('Kamera kapatıldı. İzinleri kontrol edip yeniden deneyin.');
        setScanState('ERROR');
        return;
      }
      if (!videoRef.current || !canvasRef.current) {
        if (isDemo) {
          // Demo modda video elementi hazır değilse de deterministic ilerleme sağlanır
          consecutiveValidFramesRef.current += 1;
          const progress = Math.min(100, Math.round((consecutiveValidFramesRef.current / 30) * 100));
          setScanProgress(progress);
          if (progress >= 100) {
            finishScan(true);
            return;
          }
        }
        schedule();
        return;
      }

      const video = videoRef.current;
      const canvas = canvasRef.current;

      if (video.readyState >= 2 && video.videoWidth > 0 && video.currentTime !== lastVideoTime) {
        lastVideoTime = video.currentTime;
        if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
        }

        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

          // Gerçek hizalama ve kalite değerlendirmesi
          if (!isMediaPipeLoadedRef.current || !inferenceRef.current) {
            setGuidanceText('Cilt analiz motoru hazırlanıyor...');
            schedule();
            return;
          }
          let curAlign: FaceAlignment;
          try {
            const ratio=Math.min(1,640/canvas.width);
            const w=Math.round(canvas.width*ratio),h=Math.round(canvas.height*ratio);
            if(analysisCanvas.width!==w || analysisCanvas.height!==h){analysisCanvas.width=w;analysisCanvas.height=h;}
            const analysisCtx=analysisCanvas.getContext('2d',{willReadFrequently:true});
            if(!analysisCtx)throw Error('CAMERA_ANALYSIS_CANVAS');
            analysisCtx.drawImage(canvas,0,0,w,h);
            curAlign = await inferenceRef.current.assessAlignment(analysisCanvas);
            curAlign.cameraMirrored = detectCameraMirrored(video, ctx, curAlign.faceTransform);
          } catch {
            if (!cancelled) {
              setErrorMessage('Cilt analiz motoru yanıt vermiyor. Lütfen yeniden deneyin.');
              setScanState('ERROR');
            }
            return;
          }
          // Driving/privacy/unmount may cancel while a real frame is being inferred.
          if (cancelled || !parkedRef.current || !isCameraAllowed()) return;
          const analysisCtx=analysisCanvas.getContext('2d',{willReadFrequently:true})!;
          let curQual = SkinAnalyzer.checkQuality(analysisCtx, analysisCanvas.width, analysisCanvas.height, curAlign.faceDetected, curAlign.box);
          if(!isDemo&&curQual.avgLuminance>=40&&curQual.avgLuminance<=220&&curAlign.faceDetected&&curAlign.isMediaPipeActive){
            try{
              const status=await eyewearCheck.assess(canvas,curAlign,()=>!cancelled&&parkedRef.current&&isCameraAllowed());
              if(cancelled||!parkedRef.current||!isCameraAllowed())return;
              setEyewearStatus(status);
              const stable=curQual.isValid&&eyewearGate.observe(status,performance.now());
              if(!curQual.isValid)eyewearGate.reset();
              if(status!=='CLEAR'||curQual.isValid&&!stable)curQual={...curQual,isValid:false,status:status==='EYEWEAR_PRESENT'?'EYEWEAR':status==='CLEAR'?'EYEWEAR_PENDING':'EYEWEAR_UNCERTAIN',warningMessageTr:status==='EYEWEAR_PRESENT'?'Cilt analizi için gözlüğünüzü çıkarın':status==='CLEAR'?'Göz çevreniz doğrulanıyor; kısa süre sabit durun.':'Göz çevrenizi net gösterin; kısa süre sabit durun.'};
            }catch{
              if(cancelled)return;
              eyewearGate.reset();setEyewearStatus('UNCERTAIN');
              curQual={...curQual,isValid:false,status:'EYEWEAR_UNCERTAIN',warningMessageTr:'Göz çevresi doğrulanamadı. Kameraya doğru bakın ve yeniden deneyin.'};
            }
          }else if(!isDemo){eyewearGate.reset();setEyewearStatus('PENDING');}
          // Landmarks stay normalized to the complete decoded source. Only
          // pixel-space bounds must return to native coordinates for capture ROI.
          if(curAlign.box){const sx=canvas.width/analysisCanvas.width,sy=canvas.height/analysisCanvas.height;curAlign={...curAlign,box:{x:curAlign.box.x*sx,y:curAlign.box.y*sy,width:curAlign.box.width*sx,height:curAlign.box.height*sy}};}

          setAlignment(curAlign);
          setQuality(curQual);

          if (isDemo) {
            // DEMO MOD: Zamanlayıcı bazlı yumuşak ilerleme
            consecutiveValidFramesRef.current += 1;
            const progress = Math.min(100, Math.round((consecutiveValidFramesRef.current / 18) * 100));
            setScanProgress(progress);
            if (progress >= 100) {
              finishScan(true);
              return;
            }
          } else {
            // REAL MOD: Gerçek MediaPipe + Yüz Tespiti + Hizalama + Kalite Doğrulaması
            const isMPLoaded = isMediaPipeLoadedRef.current;
            const captureState = angleRuntime.current;
            const target = SKIN_ANGLES[captureState.index];
            const aligned = captureState.enabled ? matchesSkinAngle(curAlign, target) : curAlign.isAligned;
            // Never strand capture behind an unavailable spoken instruction.
            // Backend still marks unsupported lower-face measurements null.
            const expressionIssue=skinNeutralGuidance()?lowerFaceExpressionReason(curAlign,canvas.width,canvas.height):undefined;
            setLowerFaceIssue(curQual.isValid&&curAlign.faceDetected?(!aligned?'POSE_'+target:expressionIssue):undefined);
            const isValid =
              isMPLoaded &&
              curAlign.faceDetected &&
              curAlign.isMediaPipeActive &&
              aligned &&
              !expressionIssue &&
              curQual.isValid;

            if (isValid) {
              if(curAlign.landmarks){temporalSupport.current.push(skinTemporalSupport(ctx,curAlign.landmarks));temporalSupport.current=temporalSupport.current.slice(-6);}
              consecutiveValidFramesRef.current += 1;
              const progress = Math.min(100, Math.round((consecutiveValidFramesRef.current / 15) * 100));
              setScanProgress(captureState.enabled ? Math.round((captureState.index * 100 + progress) / 3) : progress);
              setGuidanceText('Hizalama uygun. Lütfen sabit durun...');

              if (progress >= 100) {
                if (captureState.enabled) {
                  try {
                    assertCompleteFace(curAlign, canvas.width, canvas.height);
                    const capture = await captureSkinAngle(ctx, curAlign, curQual, target, captureState.captures);
                    if (cancelled || !parkedRef.current || !isCameraAllowed()) return;
                    setGuidanceText('Yerel görünüm ölçümleri hazırlanıyor; iptal edebilirsiniz.');
                    setPreparationPhase(null);
                    if (cancelled || !parkedRef.current || !isCameraAllowed()) return;
                    const snapshot = snapshotSkinFrame(canvas, curAlign, target);
                    capture.indicators=measureSkinIndicators(ctx,snapshot,curQual);
                    await addLocalMaps(snapshot,ctx,curQual.isValid,()=>!cancelled&&parkedRef.current&&isCameraAllowed(),capture.frameToken,capture.indicators,{...capture.pose,avgLuminance:curQual.avgLuminance,blurScore:curQual.blurScore});
                    if(cancelled||!parkedRef.current||!isCameraAllowed())return;
                    if(target==='FRONT'){delete capture.indicators.rightCheek;delete capture.indicators.leftCheek;}
                    if (target === 'FRONT') snapshot.rois = snapshot.rois.filter(r => !['rightCheek','leftCheek'].includes(r.id));
                    snapshotFrames.current[target] = snapshot;
                    captureState.captures[target] = capture;
                    setCompletedAngles([...SKIN_ANGLES.slice(0, captureState.index + 1)]);
                    if (captureState.index === 2) { finishMultiRef.current(captureState.captures as Record<SkinAngle, AngleCapture>); return; }
                    temporalSupport.current=[];captureState.index++; setAngleIndex(captureState.index); consecutiveValidFramesRef.current = 0;
                  } catch (error) {
                    if (cancelled || !parkedRef.current || !isCameraAllowed()) return;
                    if(error instanceof Error&&error.message==='Yerel görünüm analizi tamamlanamadı.'){setErrorMessage(error.message);setScanState('ERROR');return;}
                    consecutiveValidFramesRef.current = 0;
                    setScanProgress(Math.round(captureState.index * 100 / 3));
                    setGuidanceText(error instanceof Error && error.message === 'INCOMPLETE_HEAD_FRAME' ? 'Alın ve çeneniz kadrajda kalacak şekilde biraz geriye gidin; bu poz yeniden alınacak.' : 'Bu poz güvenilir ölçülemedi veya önceki kareyle aynı. İstenen açıyı yeniden deneyin.');
                  }
                  schedule(); return;
                }
                finishScan(false, curAlign, curQual);
                return;
              }
            } else {
              // Koşullar bozulursa ilerlemeyi durdur veya geriye al
              consecutiveValidFramesRef.current = captureState.enabled || expressionIssue || curQual.status.startsWith('EYEWEAR') ? 0 : Math.max(0, consecutiveValidFramesRef.current - 1);
              if (curQual.status.startsWith('EYEWEAR')) {
                setGuidanceText(curQual.warningMessageTr || 'Göz çevrenizi net gösterin.');
              } else if (!curAlign.faceDetected) {
                setGuidanceText('Yüz algılanamadı. Kameranın karşısına geçin.');
              } else if (!aligned) {
                setGuidanceText(captureState.enabled ? angleGuidance(curAlign, target) : curAlign.guidanceTextTr || 'Yüzünüzü kılavuz alana ortalayın.');
              } else if (!curQual.isValid) {
                setGuidanceText(curQual.warningMessageTr || 'Ortam aydınlatmasını kontrol edin.');
              }
            }
          }
        }
      }

      schedule();
    };

    schedule();
    return () => {
      eyewearCheck.cancel();eyewearGate.reset();
      cancelled = true; localAnalysis.current?.cancel();
      if (frameId !== null) cancelAnimationFrame(frameId);
      video.srcObject = null;
      mediaStream.getTracks().forEach(track => track.stop());
    };
  }, [mediaStream, scanState, isParked]);

  // Kamerayı başlat ve taramaya geç
  const startCamera = async () => {
    if (!isParked || scanState === 'CAMERA_ACTIVE') return;
    const acquisition = ++acquisitionRef.current;
    setErrorMessage(null);
    snapshotFrames.current = {}; snapshotRecord.current = null; setSnapshots({});
    angleRuntime.current = { enabled: multiAngle, index: 0, captures: {} };
    setAngleIndex(0); setCompletedAngles([]);

    // 1. Gizlilik Tercihi Kontrolü
    if (!isCameraAllowed()) {
      setErrorMessage(
        'Kabin kamerası kullanım izni Gizlilik ayarlarında kapalıdır. Lütfen Gizlilik & İzinler sayfasından kamerayı açın.'
      );
      setScanState('ERROR');
      return;
    }

    const isDemo = isDemoMode();

    // 2. Real Modda MediaPipe kontrolü
    if (!isDemo && !isMediaPipeLoaded && initializationFailedRef.current) {
      setErrorMessage(
        'Cilt analiz motoru kullanılamıyor. Lütfen kamera iznini ve bağlantınızı kontrol edip tekrar deneyin.'
      );
      setScanState('ERROR');
      return;
    }

    setScanState('CAMERA_ACTIVE');
    setScanProgress(0);

    if (isDemo) {
      setIsLiveVideo(false);
      startSyntheticDemoScan();
      return;
    }

    try {
      const videoConstraints:MediaTrackConstraints & {resizeMode:ConstrainDOMString}={width:{ideal:1920},height:{ideal:1080},resizeMode:{ideal:'none'},facingMode:'user'};
      const stream = await navigator.mediaDevices.getUserMedia({
        video: videoConstraints
      });
      if (!mountedRef.current || acquisition !== acquisitionRef.current || !parkedRef.current || !isCameraAllowed()) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      setMediaStream(stream);
      const track=stream.getVideoTracks()[0],settings=track.getSettings(),capabilities=track.getCapabilities?.();
      setCameraResolution({width:settings.width||0,height:settings.height||0,maxWidth:capabilities?.width?.max,maxHeight:capabilities?.height?.max});
      setIsLiveVideo(true);
    } catch (err: any) {
      if (!mountedRef.current || acquisition !== acquisitionRef.current) return;
      console.warn('Kamera erişimi sağlanamadı:', err);
      if (isDemo) {
        // Demo modda kamera erişilemezse videoRef beklemeksizin sentetik taramayı tamamlar
        setIsLiveVideo(false);
        startSyntheticDemoScan();
      } else {
        setIsLiveVideo(false);
        setErrorMessage(
          'Kamera erişimi sağlanamadı. Lütfen kamera izinlerinizi kontrol edip tekrar deneyin.'
        );
        setScanState('ERROR');
      }
    }
  };

  const getDefaultEngineRegions = (): Record<string, RegionMetrics> => ({
    forehead: { id: 'forehead', nameTr: 'Alın', rednessScore: 32, luminanceScore: 68, textureVariance: 22, changeFromBaselinePct: 4 },
    rightCheek: { id: 'rightCheek', nameTr: 'Sağ Profil', rednessScore: 64, luminanceScore: 52, textureVariance: 48, changeFromBaselinePct: 22 },
    leftCheek: { id: 'leftCheek', nameTr: 'Sol Profil', rednessScore: 35, luminanceScore: 64, textureVariance: 22, changeFromBaselinePct: -3 },
    nose: { id: 'nose', nameTr: 'Burun', rednessScore: 40, luminanceScore: 60, textureVariance: 26, changeFromBaselinePct: 6 },
    chin: { id: 'chin', nameTr: 'Çene', rednessScore: 28, luminanceScore: 65, textureVariance: 16, changeFromBaselinePct: 2 },
    periorbital: { id: 'periorbital', nameTr: 'Göz Çevresi', rednessScore: 30, luminanceScore: 54, textureVariance: 34, changeFromBaselinePct: 8 }
  });

  // Care modülüne yönlendirme (Dermatoloji el sıkışması)
  // Earlier scans with validated findings (numeric only, no photos) for the history chart of each finding.
  const findingsHistory = React.useMemo(() => {
    if (isDemoMode() || typeof window === 'undefined') return [];
    try {
      const rows = JSON.parse(localStorage.getItem(STORAGE_KEYS.SKIN_HISTORY) || '[]');
      return (Array.isArray(rows) ? rows : []).filter((r: any) => r?.id !== analysisResult?.id && typeof r?.timestamp === 'string' && validFindings(r?.general?.findings))
        .map((r: any) => ({ at: r.timestamp, findings: r.general.findings.findings }));
    } catch { return []; }
  }, [analysisResult?.id]);

  const handleNavigateToCare = () => {
    const isDemo = isDemoMode();
    const currentRegion = buildSkinViewModel(selectedRegionId, analysisResult, isDemo);
    const referralContext = {
      sourceModule: 'SKIN',
      specialty: 'Dermatoloji',
      reasonSummary: currentRegion.observation.details,
      timestamp: new Date().toISOString(),
      metricsSummary: {
        region: currentRegion.nameTr,
        changePct: currentRegion.changePct,
        usedMediaPipe: analysisResult?.usedMediaPipe === true
      },
      isDemo
    };
    try {
      if (isDemo) {
        localStorage.setItem(STORAGE_KEYS.DEMO_REFERRAL, JSON.stringify(referralContext));
      } else {
        localStorage.setItem(STORAGE_KEYS.REFERRAL_CONTEXT, JSON.stringify(referralContext));
      }
    } catch (e) {}
    router.push(careHref('skin'));
  };

  // Sürüş emniyeti kilidi
  if (!isParked) {
    return (
      <div className="bg-gradient-to-b from-slate-900/90 to-[#0B1526]/90 border border-amber-500/50 rounded-3xl p-10 text-center max-w-xl mx-auto my-12 space-y-6 shadow-[0_0_50px_rgba(245,158,11,0.15)] backdrop-blur-xl">
        <div className="w-20 h-20 bg-amber-500/15 border border-amber-500/40 text-amber-400 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
          <AlertTriangle className="w-10 h-10 animate-pulse" />
        </div>
        <div className="space-y-2">
          <span className="text-[11px] font-mono uppercase tracking-widest text-amber-400 font-bold px-3 py-1 bg-amber-500/10 rounded-full border border-amber-500/20">{i18nText("Sürüş Emniyeti Devrede • ")}{i18nNode(state.currentSpeed)}{i18nText(" km/s ")}</span>
          <h1 className="text-2xl font-extrabold text-white">{i18nText("Cilt Sağlığı Kilitlendi")}</h1>
          <p className="text-sm text-slate-300 leading-relaxed max-w-md mx-auto">{i18nText("Cilt analizi kamera odaklanması ve yüz hizalaması gerektirdiğinden, sürüş güvenliğiniz için araç hareket halindeyken kullanılamaz. ")}</p>
        </div>
        <div className="p-3.5 bg-slate-950/80 rounded-xl border border-slate-800 text-xs text-slate-300 flex items-center justify-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span>{i18nText("Lütfen aracı güvenli bir alanda ")}<strong>{i18nText("Park (P)")}</strong>{i18nText(" moduna alın.")}</span>
        </div>
      </div>
    );
  }

  const currentRegionData: SkinRegionData = buildSkinViewModel(
    selectedRegionId,
    analysisResult,
    isDemoMode()
  );

  return (
    <div className="space-y-4 max-w-5xl mx-auto select-none">
      {/* Gizli kanvas (MediaPipe piksel analizi) */}
      <canvas ref={canvasRef} className="hidden" data-skin-capture-policy={SKIN_CAPTURE_POLICY} data-skin-eyewear-state={eyewearStatus} data-mediapipe-ready={isMediaPipeLoaded} data-mediapipe-active={alignment.isMediaPipeActive} data-face-detected={alignment.faceDetected} data-landmark-count={alignment.landmarks?.length || 0} data-quality-status={quality.status} data-yaw={alignment.yaw} data-angle={SKIN_ANGLES[angleIndex]} data-completed-angles={completedAngles.join(',')} />
      {scanState === 'READY' && errorMessage && <p role="alert" className="text-amber-200">{i18nNode(errorMessage)}</p>}

      {/* ============================================================ */}
      {/* HATA DURUMU: MediaPipe / Kamera / İzin Eksikliği             */}
      {/* ============================================================ */}
      {scanState === 'ERROR' && (
        <div className="bg-[#0c1424]/90 border border-amber-500/40 rounded-3xl p-8 md:p-10 shadow-2xl max-w-xl mx-auto text-center space-y-6">
          <div className="w-16 h-16 bg-amber-500/10 border border-amber-500/30 text-amber-400 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
            <AlertTriangle className="w-8 h-8" />
          </div>
          <div className="space-y-2">
            <span className="text-[11px] font-mono uppercase tracking-widest text-amber-400 font-bold px-3 py-1 bg-amber-500/10 rounded-full border border-amber-500/20">{i18nText("Analiz Motoru Bildirimi ")}</span>
            <h2 className="text-2xl font-extrabold text-white">{i18nText("Cilt Sağlığı Başlatılamadı")}</h2>
            <p className="text-sm text-slate-300 leading-relaxed max-w-md mx-auto">
              {i18nNode(errorMessage || 'Cilt analiz motoru kullanılamıyor. Lütfen kamera iznini ve bağlantınızı kontrol edip tekrar deneyin.')}
            </p>
          </div>
          <div className="pt-2 flex justify-center gap-3">
            <button
              onClick={() => {
                setErrorMessage(null);
                if (initializationFailedRef.current) setInitializationEpoch(epoch => epoch + 1);
                setScanState('READY');
              }}
              className="px-6 py-2.5 rounded-xl bg-togg-turquoise text-togg-darkBlue font-bold text-xs hover:bg-[#33D0EE] transition-all shadow-md"
            >{i18nText("Tekrar Dene ")}</button>
            <button
              onClick={() => router.push('/privacy')}
              className="px-5 py-2.5 rounded-xl bg-slate-900 text-slate-300 border border-slate-700 font-medium text-xs hover:bg-slate-800 transition-all"
            >{i18nText("Gizlilik & İzinler ")}</button>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* SCREEN 1: SKIN START VIEW (REFERANS 1 & 2)                  */}
      {/* ============================================================ */}
      {scanState === 'READY' && (
        <><div className="flex items-center justify-between gap-3 mb-3"><InformationButton title={i18nText("Cilt taraması")}><p>{i18nText("Yüz noktaları ve bölgesel görünüm bu cihazda işlenir; sonuçta kamera kapanır. Cilt tipi için Gizlilik & İzinler alanında ayrıca izin verirseniz yüz fotoğrafınızın ilgili kısmı Roboflow tarafından işlenir; internet gerekir. Sayısal kayıt ve fotoğraf saklama tercihleri ayrıdır. Fotoğraf saklama kapalıysa görüntü yalnız açık oturumda kalır. Fotoğrafı saklanmamış eski kayıtlar sayısal olarak gösterilir. Sonuç klinik tanı değildir.")}</p><label className="flex min-h-11 items-center gap-3"><input type="checkbox" aria-label={i18nText("Üç açılı tarama")} checked={multiAngle} onChange={e => setMultiAngle(e.target.checked)} />{i18nText("Ön, sağ ve sol pozlarda tara. Kapalıyken yalnız ön poz kullanılır.")}</label></InformationButton></div><SkinStartView onStart={startCamera} /></>
      )}

      {/* ============================================================ */}
      {/* SCREEN 2: SKIN ACTIVE SCAN (REFERANS 1)                     */}
      {/* ============================================================ */}
      {scanState === 'CAMERA_ACTIVE' && (
        <>
        {!isDemoMode() && <div data-angle-progress className="flex flex-wrap items-center gap-3"><p>{i18nNode(multiAngle ? `Aşama ${angleIndex + 1}/3: ${ANGLE_LABELS[SKIN_ANGLES[angleIndex]]}` : 'Ön poz')}</p><InformationButton title={i18nText("Kamera ve pozlar")}><p>{i18nText("Önizleme aynasızdır. Yönler anatomik sağ ve solunuzdur. Ön pozdan alın, burun, çene ve göz çevresi; yan pozdan görünen yanak ölçülür. Tamamlanan pozlar: ")}{i18nNode(completedAngles.map(a=>ANGLE_LABELS[a]).join(', ') || 'henüz yok')}{i18nText(". Ekrandaki büyütme yalnız görüntüleme içindir; kalite ham kamera karesinden ölçülür.")}</p></InformationButton><button onClick={() => { void voice.repeat();consecutiveValidFramesRef.current = 0; setScanProgress(Math.round(angleIndex * 100 / 3)); setGuidanceText('İstenen pozu yeniden deneyin.'); }} className="text-sm underline">{i18nText("Bu açıyı tekrar dene")}</button><button onClick={() => { acquisitionRef.current++; activeScanRef.current=false; setPreparationPhase(null); setScanState('READY'); setMediaStream(null); }} className="text-sm underline">{i18nText("Taramayı İptal Et")}</button></div>}
        {preparationPhase && <div role="status" data-portrait-preparation={preparationPhase} className="flex items-center gap-3 py-3 text-sm text-togg-turquoise"><span aria-hidden="true" className="h-5 w-5 rounded-full border-2 border-current border-r-transparent animate-spin"/><span>{i18nNode(guidanceText)}{i18nText(" Bu aşamada geçen süre: ")}{i18nNode(preparationSeconds)}{i18nText(" sn.")}</span></div>}
        <SkinActiveScan
          preparing={!!preparationPhase}
          scanProgress={scanProgress}
          videoRef={videoRef}
          isLiveVideo={isLiveVideo}
          alignment={multiAngle && !isDemoMode() ? { ...alignment, isAligned: matchesSkinAngle(alignment, SKIN_ANGLES[angleIndex]) } : alignment}
          quality={quality}
          fresh={cameraFresh}
          resolution={cameraResolution}
          guidanceText={guidanceText}
          multiAngle={multiAngle && !isDemoMode()}
        />
        </>
      )}

      {/* ============================================================ */}
      {/* SCREEN 3: SKIN RESULT VIEW (REFERANS 1, 2, 3, 4)            */}
      {/* ============================================================ */}
      {scanState === 'COMPLETED' && (isDemoMode() || !!analysisResult) && (
        <>

        {photoNotice&&<p role="status" className="text-sm text-amber-200">{i18nNode(photoNotice)}</p>}
        <SkinResultView
          currentRegion={currentRegionData}
          snapshot={snapshots[snapshotAngleForRegion(selectedRegionId, analysisResult?.comparisonScope === 'three-angle-v2')]}
          findings={(analysisResult as any)?.general?.findings?.findings}
          findingsHistory={findingsHistory}
          scanAt={(analysisResult as any)?.timestamp}
          onRescan={() => { setMediaStream(null); setIsLiveVideo(false); setScanState('READY'); }}
          onSelectView={(view) => setSelectedRegionId(view as SkinViewId)}
          onPrev={handlePrevRegion}
          onNext={handleNextRegion}
          onOpenModal={(modal) => setActiveModal(modal)}
          onNavigateToCare={handleNavigateToCare}
          videoRef={videoRef}
          isLiveVideo={false}
          isBaseline={analysisResult?.isBaseline}
          comparisonUnavailable={analysisResult?.comparisonUnavailable}
           comparisonReasons={analysisResult?.comparisonReasons}
          baselineTimestamp={analysisResult?.baselineTimestamp}
          baselineId={analysisResult?.baselineId}
          comparisonScope={analysisResult?.comparisonScope === 'three-angle-v2' ? 'three-angle-v2' : 'single-front-v1'}
        />
        {Object.values(snapshots).some(s=>s?.visualError) && <button onClick={()=>{setMediaStream(null);setIsLiveVideo(false);setScanState('READY');}} className="min-h-11 border border-white/20 rounded-xl px-4">{i18nText("Görüntü için yeni tarama")}</button>}
        </>
      )}

      {/* ============================================================ */}
      {/* SCREEN 4, 5, 6: MODALLAR (Zaman İçinde / Gözlem / Aksiyon)  */}
      {/* ============================================================ */}
      {activeModal === 'trend' && (
        <SkinTrendModal
          region={currentRegionData}
          analysisId={analysisResult?.id}
          onClose={() => setActiveModal(null)}
        />
      )}

      {activeModal === 'observation' && (
        <SkinObservationModal
          region={currentRegionData}
          onClose={() => setActiveModal(null)}
        />
      )}

      {activeModal === 'actions' && (
        <SkinActionsModal
          region={currentRegionData}
          onClose={() => setActiveModal(null)}
          onNavigateToCare={handleNavigateToCare}
        />
      )}
    </div>
  );
}
