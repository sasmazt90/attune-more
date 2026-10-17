'use client';

import {clearSkinPhotos,SKIN_PHOTO_PERMISSION,SKIN_PHOTO_DELETE_PENDING} from '../../utils/skinPhotoHistory';
import {clearSkinSnapshots} from '../../utils/skinVolatileHistory';
import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {ServiceConsentSettings} from '../../components/ServiceConsentSettings';
import { RECORD_JOURNAL, readHealthRecords, withRecordsLock } from '../../utils/healthRecords';
import { InformationButton } from '../../components/InformationButton';
import {
  ShieldCheck,
  Lock,
  Trash2,
  Camera,
  Mic,
  Database,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ArrowLeft,
  Info
} from 'lucide-react';
import { readMentalHistory } from '../../utils/mentalHistory';
import { STORAGE_KEYS, isDemoMode,SKIN_HOSTED_PROCESSING_PERMISSION,isSkinHostedProcessingAllowed } from '../../utils/attuneMode';
import { localBackend } from '../../utils/localBackend';

  const deriveEffectiveStatus = (
    appAllowed: boolean,
    browserState: 'granted' | 'denied' | 'prompt'
  ): 'GRANTED' | 'DENIED' | 'PROMPT' => {
    if (!appAllowed) {
      return 'DENIED';
    }
    if (browserState === 'granted') {
      return 'GRANTED';
    }
    if (browserState === 'denied') {
      return 'DENIED';
    }
    return 'PROMPT';
  };


export default function PrivacyPage() {
  const [cameraAppAllowed, setCameraAppAllowed] = useState<boolean>(true);
  const [micAppAllowed, setMicAppAllowed] = useState<boolean>(true);
  const [browserCameraState, setBrowserCameraState] = useState<'granted' | 'denied' | 'prompt'>('prompt');
  const [browserMicState, setBrowserMicState] = useState<'granted' | 'denied' | 'prompt'>('prompt');
  const [cameraStatus, setCameraStatus] = useState<'GRANTED' | 'DENIED' | 'PROMPT'>('PROMPT');
  const [micStatus, setMicStatus] = useState<'GRANTED' | 'DENIED' | 'PROMPT'>('PROMPT');
  const [saveTranscript, setSaveTranscript] = useState(false);
  const [saveSkin,setSaveSkin]=useState(false);
  const [hostedSkin,setHostedSkin]=useState(false);
  const [saveSkinPhotos,setSaveSkinPhotos]=useState(false);
  const [photoBusy,setPhotoBusy]=useState(false);
  const [saveHearing,setSaveHearing]=useState(true);
  const [saveVision, setSaveVision] = useState(false);
  const [saveMentalSummaries, setSaveMentalSummaries] = useState<boolean>(true);
  const [dataStats, setDataStats] = useState<{
    visionCount: number;
    skinCount: number;
    mentalCount: number;
    dentalCount: number;
    hearingCount: number;
  }>({ visionCount: 0, skinCount: 0, mentalCount: 0, dentalCount: 0, hearingCount: 0 });

  const [wipeStatus, setWipeStatus] = useState<'IDLE' | 'CONFIRM' | 'WIPING' | 'SUCCESS' | 'PARTIAL' | 'FAILED'>('IDLE');
  const [wipeResult, setWipeResult] = useState<{ local: boolean; backend: boolean } | null>(null);
  const [storageUnavailable, setStorageUnavailable] = useState(false);

  const checkStatus = useCallback(() => {
    try {
    if (typeof window !== 'undefined') {
      // 1. Uygulama içi izin tercihi (App preference)
      const camPref = localStorage.getItem(STORAGE_KEYS.PRIVACY_CAMERA_ALLOWED);
      const camAllowed = camPref === null ? true : camPref === 'true';
      setCameraAppAllowed(camAllowed);

      const micPref = localStorage.getItem(STORAGE_KEYS.PRIVACY_MIC_ALLOWED);
      const micAllowed = micPref === null ? true : micPref === 'true';
      setMicAppAllowed(micAllowed);

      // 2. Tarayıcı izin sorgusu - App preference var diye atlanmaz
      if (navigator.permissions && navigator.permissions.query) {
        navigator.permissions
          .query({ name: 'camera' as any })
          .then((p) => {
            const bState = (p.state as 'granted' | 'denied' | 'prompt') || 'prompt';
            setBrowserCameraState(bState);
            setCameraStatus(deriveEffectiveStatus(camAllowed, bState));
          })
          .catch(() => {
            setCameraStatus(deriveEffectiveStatus(camAllowed, 'prompt'));
          });

        navigator.permissions
          .query({ name: 'microphone' as any })
          .then((p) => {
            const bState = (p.state as 'granted' | 'denied' | 'prompt') || 'prompt';
            setBrowserMicState(bState);
            setMicStatus(deriveEffectiveStatus(micAllowed, bState));
          })
          .catch(() => {
            setMicStatus(deriveEffectiveStatus(micAllowed, 'prompt'));
          });
      } else {
        setCameraStatus(deriveEffectiveStatus(camAllowed, 'prompt'));
        setMicStatus(deriveEffectiveStatus(micAllowed, 'prompt'));
      }

      setSaveTranscript(localStorage.getItem(STORAGE_KEYS.PRIVACY_MENTAL_TRANSCRIPT_ALLOWED) === 'true');
      setSaveSkin(localStorage.getItem('attune_privacy_skin_save_allowed')==='true');
      setHostedSkin(isSkinHostedProcessingAllowed());
      setSaveSkinPhotos(localStorage.getItem(SKIN_PHOTO_PERMISSION)==='true');
      setSaveHearing(localStorage.getItem('attune_privacy_hearing_save_allowed')!=='false');
      setSaveVision(localStorage.getItem(STORAGE_KEYS.PRIVACY_VISION_SAVE_ALLOWED) === 'true');
      const mentalPref = localStorage.getItem(STORAGE_KEYS.PRIVACY_MENTAL_SAVE_ALLOWED);
      if (mentalPref !== null) {
        setSaveMentalSummaries(mentalPref === 'true');
      }

      // 3. Gerçek Veri Sayımları (Demo vs Real)
      if (isDemoMode()) {
        setDataStats({ visionCount: 1, skinCount: 2, mentalCount: 2, dentalCount: 0, hearingCount: 0 });
      } else {
        const vCount = readHealthRecords('vision').length;

        let skinHist: any[] = [];
        try {
          const rawHist = localStorage.getItem(STORAGE_KEYS.SKIN_HISTORY);
          if (rawHist) skinHist = JSON.parse(rawHist);
        } catch {}

        const sCount = skinHist.length > 0
          ? skinHist.length
          : (localStorage.getItem(STORAGE_KEYS.LATEST_SKIN) ? 1 : (localStorage.getItem(STORAGE_KEYS.SKIN_BASELINE) ? 1 : 0));

        const mentalHistory = readMentalHistory();
        const mCount = mentalHistory.length || (localStorage.getItem(STORAGE_KEYS.LATEST_MENTAL) ? 1 : 0);

        setDataStats({ visionCount: vCount, skinCount: sCount, mentalCount: mCount, dentalCount: readHealthRecords('dental').length, hearingCount: readHealthRecords('hearing').length });
        setStorageUnavailable(false);
      }
    }
    } catch {
      setStorageUnavailable(true);
    }  }, []);

  useEffect(() => {
    checkStatus(); window.addEventListener('attune-records', checkStatus); window.addEventListener('storage', checkStatus);
    return () => { window.removeEventListener('attune-records', checkStatus); window.removeEventListener('storage', checkStatus); };
  }, [checkStatus]);

  const handleToggleMentalSaving = (val: boolean) => {
    try {
      localStorage.setItem(STORAGE_KEYS.PRIVACY_MENTAL_SAVE_ALLOWED, String(val));
      setSaveMentalSummaries(val);
      window.dispatchEvent(new Event('attune-privacy'));
    } catch { setStorageUnavailable(true); }
  };

  const handleToggleCamera = () => {
    const next = !cameraAppAllowed;
    try {
      localStorage.setItem(STORAGE_KEYS.PRIVACY_CAMERA_ALLOWED, String(next));
      setCameraAppAllowed(next);
      setCameraStatus(deriveEffectiveStatus(next, browserCameraState));
      window.dispatchEvent(new Event('attune-privacy'));
    } catch { setStorageUnavailable(true); }
  };

  const handleToggleMic = () => {
    const next = !micAppAllowed;
    try {
      localStorage.setItem(STORAGE_KEYS.PRIVACY_MIC_ALLOWED, String(next));
      setMicAppAllowed(next);
      setMicStatus(deriveEffectiveStatus(next, browserMicState));
      window.dispatchEvent(new Event('attune-privacy'));
    } catch { setStorageUnavailable(true); }
  };

  const handleWipeAllData = async () => {
    setWipeStatus('WIPING');
    let local = true;
    const healthKeys = [SKIN_PHOTO_DELETE_PENDING,'attune_skin_appearance_reference_v1','attune_skin_appearance_single_reference_v1',RECORD_JOURNAL, 'attune_dental_history_v1', 'attune_dental_latest_v1', 'attune_hearing_history_v1', 'attune_hearing_latest_v1', 'attune_skin_geometry_reference_v1', STORAGE_KEYS.SKIN_SIGNS_BASELINE, STORAGE_KEYS.SKIN_SINGLE_SIGNS_BASELINE, 'togg_health_vision_history', STORAGE_KEYS.LATEST_VISION, STORAGE_KEYS.LATEST_SKIN,
      STORAGE_KEYS.SKIN_BASELINE, STORAGE_KEYS.SKIN_BASELINE_META, STORAGE_KEYS.SKIN_MULTI_BASELINE, STORAGE_KEYS.SKIN_REMINDER, STORAGE_KEYS.SKIN_HISTORY, STORAGE_KEYS.LATEST_MENTAL, STORAGE_KEYS.MENTAL_HISTORY,
      STORAGE_KEYS.REFERRAL_CONTEXT, STORAGE_KEYS.DEMO_SKIN_RESULT, STORAGE_KEYS.DEMO_REFERRAL];
    try { await withRecordsLock(async () => {
    await clearSkinPhotos();clearSkinSnapshots();
    for (const key of healthKeys) {
      try {
        localStorage.removeItem(key);
        if (localStorage.getItem(key) !== null) local = false;
      } catch {
        local = false;
      }
    }
    } ); } catch { local = false; }
    window.dispatchEvent(new Event('attune-records'));
    window.dispatchEvent(new Event('attune-reminder'));
    let backend = false;
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(localBackend('/api/privacy/wipe'), { method: 'POST', signal: controller.signal });
      if (!response.ok) throw new Error('Silme isteği başarısız');
      const verification = await fetch(localBackend('/api/mental/sessions'), { cache: 'no-store', signal: controller.signal });
      if (!verification.ok) throw new Error('Silme doğrulanamadı');
      const remaining = await verification.json();
      backend = Array.isArray(remaining) && remaining.length === 0;
    } catch {
      backend = false;
    } finally {
      clearTimeout(deadline);
    }
    if (local) setDataStats({ visionCount: 0, skinCount: 0, mentalCount: 0, dentalCount: 0, hearingCount: 0 });
    setWipeResult({ local, backend });
    setWipeStatus(local && backend ? 'SUCCESS' : local || backend ? 'PARTIAL' : 'FAILED');
  };

  return (
    <div className="space-y-6">
<ServiceConsentSettings />
      {storageUnavailable && <p role="alert" className="text-sm text-amber-200">Tarayıcı depolamasına erişilemiyor; kayıtların durumu doğrulanamıyor.</p>}
      {/* 1. SCREEN 10: ÜST BAŞLIK VE AÇIKLAMA (FIRST VIEWPORT) */}
      <section className="bg-gradient-to-br from-cockpit-surface via-[#071322] to-cockpit-bg border border-white/10 rounded-2xl p-6 md:p-7 shadow-2xl space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-togg-turquoise/10 border border-togg-turquoise/30 text-togg-turquoise text-[11px] font-semibold tracking-wider uppercase">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Yerel Gizlilik ve Veri Güvenliği</span>
            </div>

            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              Verileriniz sizin kontrolünüzde.
            </h1>

            <p className="text-sm text-slate-300">
              Kullanım tercihlerinizi ve kayıtlarınızı yönetin.
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs bg-slate-950/80 px-4 py-2 rounded-xl border border-white/10 text-slate-300 shrink-0 self-start md:self-auto">
            <Lock className="w-3.5 h-3.5 text-togg-turquoise" />
            <span>Cihazda Depolama: <strong>Aktif</strong></span>
          </div>
        </div>
      </section>

      {/* 2. ÜÇ BÜYÜK TERCİH KAROSU (3 LARGE PREFERENCE TILES) */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Karo 1: KAMERA */}
        <div className="bg-cockpit-surface border border-white/10 rounded-2xl p-6 flex flex-col justify-between hover:border-white/20 transition-all shadow-xl space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-3 bg-togg-darkBlue/80 border border-togg-darkTurquoise/50 text-togg-turquoise rounded-xl">
                <Camera className="w-6 h-6" />
              </div>
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-bold ${
                  cameraStatus === 'GRANTED'
                    ? 'bg-emerald-950/70 text-emerald-400 border border-emerald-800/70'
                    : cameraStatus === 'DENIED'
                    ? 'bg-rose-950/70 text-rose-400 border border-rose-800/70'
                    : 'bg-amber-950/70 text-amber-400 border border-amber-800/70'
                }`}
              >
                {cameraStatus === 'GRANTED' ? 'Açık' : cameraStatus === 'DENIED' ? 'Kapalı' : 'Sorulacak'}
              </span>
            </div>

            <div>
              <div className="flex items-center justify-between gap-3"><h2 className="text-base font-bold text-white">Kabin Kamerası</h2><InformationButton title="Kabin Kamerası"><p>Kamera yalnız görme ve cilt kontrolleri için kullanılır. Ham görüntü saklanmaz. Bu tercih tarayıcı/cihaz izni değildir; Başlat eyleminde gerçek izin istenir. Bilinçli olarak kapattığınız tercih korunur.</p></InformationButton></div>
            </div>
          </div>

          <div className="pt-3 border-t border-white/5 flex items-center justify-between">
            <span className="text-[11px] text-slate-400">Uygulama İzni</span>
            <button
              onClick={handleToggleCamera}
              className="text-xs font-semibold text-togg-turquoise hover:underline"
            >
              {cameraAppAllowed ? 'Erişimi Kapat' : 'İzin Ver'}
            </button>
          </div>
        </div>

        {/* Karo 2: MİKROFON */}
        <div className="bg-cockpit-surface border border-white/10 rounded-2xl p-6 flex flex-col justify-between hover:border-white/20 transition-all shadow-xl space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-3 bg-togg-darkBlue/80 border border-togg-darkTurquoise/50 text-togg-turquoise rounded-xl">
                <Mic className="w-6 h-6" />
              </div>
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-bold ${
                  micStatus === 'GRANTED'
                    ? 'bg-emerald-950/70 text-emerald-400 border border-emerald-800/70'
                    : micStatus === 'DENIED'
                    ? 'bg-rose-950/70 text-rose-400 border border-rose-800/70'
                    : 'bg-amber-950/70 text-amber-400 border border-amber-800/70'
                }`}
              >
                {micStatus === 'GRANTED' ? 'Açık' : micStatus === 'DENIED' ? 'Kapalı' : 'Sorulacak'}
              </span>
            </div>

            <div>
              <div className="flex items-center justify-between gap-3"><h2 className="text-base font-bold text-white">Kabin Mikrofonu</h2><InformationButton title="Kabin Mikrofonu"><p>Mikrofon yalnız görüşmeyi başlattığınızda kullanılır. Tarayıcı/cihaz izni ayrıca gerekir; bu tercih onu onaylamaz. Konuşma tanıma hizmeti sesi buluta aktarabilir. Aktarım Ruh Sağlığı ekranındaki hizmet onayına bağlıdır. Ham ses uygulamada saklanmaz.</p></InformationButton></div>
            </div>
          </div>

          <div className="pt-3 border-t border-white/5 flex items-center justify-between">
            <span className="text-[11px] text-slate-400">Uygulama İzni</span>
            <button
              onClick={handleToggleMic}
              className="text-xs font-semibold text-togg-turquoise hover:underline"
            >
              {micAppAllowed ? 'Erişimi Kapat' : 'İzin Ver'}
            </button>
          </div>
        </div>

        {/* Karo 3: SEANS HAFIZASI */}
        <div className="bg-cockpit-surface border border-white/10 rounded-2xl p-6 flex flex-col justify-between hover:border-white/20 transition-all shadow-xl space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-3 bg-togg-darkBlue/80 border border-togg-darkTurquoise/50 text-togg-turquoise rounded-xl">
                <Database className="w-6 h-6" />
              </div>
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-bold ${
                  saveMentalSummaries
                    ? 'bg-emerald-950/70 text-emerald-400 border border-emerald-800/70'
                    : 'bg-slate-900 text-slate-400 border border-slate-800'
                }`}
              >
                {saveMentalSummaries ? 'Açık' : 'Kapalı'}
              </span>
            </div>

            <div>
              <div className="flex items-center justify-between gap-3"><h2 className="text-base font-bold text-white">Seans Hafızası</h2><InformationButton title="Seans Hafızası"><p>Tamamlanan görüşmenin kısa özeti, temaları, duygu eğilimi ve tarihi bu cihazda saklanır. Ham ses saklanmaz. Tam konuşma dökümü için aşağıdaki ayrı, varsayılan kapalı tercih gerekir. Kapatmak önceki kayıtları silmez. Görüşme başlatmak için saklama izni zorunlu değildir.</p></InformationButton></div>
            </div>
          </div>

          <div className="pt-3 border-t border-white/5 flex items-center justify-between">
            <span className="text-[11px] text-slate-400">Yerel Saklama</span>
            <button
              onClick={() => handleToggleMentalSaving(!saveMentalSummaries)}
              className="text-xs font-semibold text-togg-turquoise hover:underline"
            >
              {saveMentalSummaries ? 'Devre Dışı Bırak' : 'Etkinleştir'}
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-white/10 bg-cockpit-surface p-6 space-y-3">
        <div className="flex items-center justify-between gap-3"><h2 className="font-bold">Konuşma dökümü</h2><InformationButton title="Konuşma dökümü saklama"><p>Varsayılan kapalıdır. Açarsanız, ayrıca özet saklama tercihiniz açıkken tamamlanmış görüşmenin kullanıcı/asistan metinleri ve gerçek mesaj zamanları bu tarayıcıda aynı oturum kaydına eklenir. Ham mikrofon sesi saklanmaz. Bu tercih yeni bir backend veya dış sağlayıcı döküm kaydı oluşturmaz.</p><p>Görüşme hizmet onayı kapsamındaki yanıt/özet metin aktarımı ayrıdır. Yerel Sil eylemi dökümü ve özeti birlikte temizler; sağlayıcının tarihsel saklama veya silme durumunu doğrulamaz. Tercihi kapatmak eski kayıtları otomatik silmez.</p></InformationButton></div>
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={saveTranscript} aria-label="Tam konuşma dökümünü bu cihazda sakla" onChange={e=>{try{localStorage.setItem(STORAGE_KEYS.PRIVACY_MENTAL_TRANSCRIPT_ALLOWED,String(e.target.checked));setSaveTranscript(e.target.checked);window.dispatchEvent(new Event('attune-privacy'));}catch{setStorageUnavailable(true);}}}/>Tam konuşma dökümünü bu cihazda sakla</label>
        <p className="text-xs text-slate-400">Fotoğraf saklama tercihi aşağıda Cilt Sağlığı için ayrıca yönetilir.</p>
        <div className="flex items-center justify-between gap-3"><h2 className="font-bold">Görme ön değerlendirmesi</h2><InformationButton title="Yön hizalama sonucu saklama"><p>Varsayılan kapalıdır. Açarsanız tamamlanan yön hizalama denemeleri, görünürlük yanıtları, açı hataları, tarih ve hazırlık/doğrulama sınırları yalnız bu tarayıcıdaki geçmişe kaydedilir. Kamera karesi veya klinik keskinlik kaydı oluşturulmaz. Kapatmak eski kayıtları silmez; Sil ile tek kayıt kaldırılabilir.</p></InformationButton></div>
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={saveVision} aria-label="Yön hizalama sonuçlarını bu cihazda sakla" onChange={e=>{try{localStorage.setItem(STORAGE_KEYS.PRIVACY_VISION_SAVE_ALLOWED,String(e.target.checked));setSaveVision(e.target.checked);window.dispatchEvent(new Event('attune-privacy'));}catch{setStorageUnavailable(true);}}}/>Yön hizalama sonuçlarını bu cihazda sakla</label>
      </section>

      <section className="rounded-2xl border border-white/10 bg-cockpit-surface p-6 space-y-3">
        <h2 className="font-bold">Cilt görünümü ve kişisel referans</h2>
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={saveSkinPhotos} disabled={photoBusy} onChange={async e=>{const enabled=e.target.checked;setPhotoBusy(true);try{await withRecordsLock(async()=>{localStorage.setItem(SKIN_PHOTO_PERMISSION,String(enabled));setSaveSkinPhotos(enabled);window.dispatchEvent(new Event('attune-privacy'));if(!enabled){clearSkinSnapshots();await clearSkinPhotos();}});setSaveSkinPhotos(enabled);window.dispatchEvent(new Event('attune-privacy'));}catch{setStorageUnavailable(true);setSaveSkinPhotos(localStorage.getItem(SKIN_PHOTO_PERMISSION)==='true');}finally{setPhotoBusy(false);}}}/>Yeni cilt kayıtlarının fotoğraflarını bu cihazda sakla</label>
        <p className="text-xs text-slate-400">Varsayılan kapalıdır. Sayısal kayıt izni de açıksa yeni taramaların fotoğraf ve seçilebilir görüntü katmanları uygulama yeniden açıldığında korunur. Kapatınca saklanan cilt fotoğrafları silinir; sayısal kayıtlar kalır. En fazla 128 MB saklanır; dolunca eski kayıtlar silinmez, yeni fotoğraf kaydedilemez.</p>
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={saveSkin} onChange={e=>{try{localStorage.setItem('attune_privacy_skin_save_allowed',String(e.target.checked));setSaveSkin(e.target.checked);window.dispatchEvent(new Event('attune-privacy'));}catch{setStorageUnavailable(true);}}}/>Cilt ölçümlerini ve kişisel sayısal referansı bu tarayıcıda sakla</label>
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={hostedSkin} onChange={e=>{try{localStorage.setItem(SKIN_HOSTED_PROCESSING_PERMISSION,String(e.target.checked));setHostedSkin(e.target.checked);window.dispatchEvent(new Event('attune-privacy'));}catch{setStorageUnavailable(true);}}}/>Cilt tipi için yüz fotoğrafımın Roboflow tarafından işlenmesine izin ver</label>
        <p className="text-xs text-slate-400">Varsayılan kapalıdır; çekim izninden ayrıdır. Fotoğraf saklama tercihi aşağıda ayrıca yönetilir. Diş sonuçlarında ayrıca Kaydet onayı verilir. Kapatmak eski kayıtları silmez; kayıt Sil veya Tüm Yerel Verileri Sil ile kaldırılır.</p>
      </section>

      <section className="rounded-2xl border border-white/10 bg-cockpit-surface p-6 space-y-3"><h2 className="font-bold">İşitme Sağlığı sonuçları</h2><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={saveHearing} onChange={e=>{try{localStorage.setItem('attune_privacy_hearing_save_allowed',String(e.target.checked));setSaveHearing(e.target.checked);window.dispatchEvent(new Event('attune-privacy'));}catch{setStorageUnavailable(true);}}}/>Tamamlanan sayısal işitme sonuçlarını bu cihazda sakla</label></section>

      {/* 3. BELOW FOLD: YEREL VERİ YÖNETİMİ VE SİLME */}
      <section className="bg-cockpit-surface border border-white/10 rounded-2xl p-6 md:p-7 shadow-xl space-y-5">
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="space-y-0.5">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Database className="w-4 h-4 text-togg-turquoise" />
              <span>Kayıtlı Yerel Sağlık Verileri</span>
            </h2>
            <p className="text-xs text-slate-400">
              Bu cihazda yerel olarak tutulan test ve seans özetleri.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 text-center">
          <div className="bg-slate-950/70 border border-slate-800 p-4 rounded-xl">
            <div className="text-xs text-slate-400">Görme Kayıtları</div>
            <div className="text-2xl font-bold text-togg-turquoise mt-1 font-mono">{storageUnavailable ? '—' : dataStats.visionCount}</div>
          </div>
          <div className="bg-slate-950/70 border border-slate-800 p-4 rounded-xl">
            <div className="text-xs text-slate-400">Cilt Taramaları</div>
            <div className="text-2xl font-bold text-togg-turquoise mt-1 font-mono">{storageUnavailable ? '—' : dataStats.skinCount}</div>
          </div>
          <div className="bg-slate-950/70 border border-slate-800 p-4 rounded-xl">
            <div className="text-xs text-slate-400">Görüşme Özetleri</div>
            <div className="text-2xl font-bold text-togg-turquoise mt-1 font-mono">{storageUnavailable ? '—' : dataStats.mentalCount}</div>
          </div>
            {(['dental','hearing'] as const).map(category => <div key={category} className="bg-slate-950/70 border border-slate-800 p-4 rounded-xl"><div className="text-xs text-slate-400">{category === 'dental' ? 'Diş Kayıtları' : 'İşitme Kayıtları'}</div><div className="text-2xl font-bold text-togg-turquoise mt-1 font-mono">{storageUnavailable ? '—' : category === 'dental' ? dataStats.dentalCount : dataStats.hearingCount}</div></div>)}
        </div>

        {/* TÜM YEREL VERİLERİ SİL BUTONU */}
        <div className="pt-2">
          {wipeStatus === 'IDLE' && (
            <button
              onClick={() => setWipeStatus('CONFIRM')}
              className="flex items-center gap-2 px-5 py-3 rounded-xl bg-rose-950/50 hover:bg-rose-900/70 text-rose-300 border border-rose-800/80 text-xs font-bold transition-all min-h-touch"
            >
              <Trash2 className="w-4 h-4" />
              <span>TÜM YEREL VERİLERİ SİL</span>
            </button>
          )}

          {wipeStatus === 'CONFIRM' && (
            <div className="bg-rose-950/40 border border-rose-700/80 rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-2 text-rose-300 font-bold text-xs">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <span>Bu işlem yerel bellekteki tüm kayıtları kalıcı olarak temizler!</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Beş sağlık modülünün yerel kayıtları ve eski kişisel cilt referansları silinecektir.
              </p>
              <div className="flex gap-3 pt-1">
                <button
                  onClick={handleWipeAllData}
                  className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow"
                >
                  Evet, Tüm Verileri Sil
                </button>
                <button
                  onClick={() => setWipeStatus('IDLE')}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs"
                >
                  Vazgeç
                </button>
              </div>
            </div>
          )}

          {wipeStatus === 'WIPING' && <p role="status" className="text-xs text-slate-300">Veriler siliniyor ve doğrulanıyor…</p>}
          {wipeResult && ['SUCCESS', 'PARTIAL', 'FAILED'].includes(wipeStatus) && (
            <div role="status" className="p-4 rounded-xl border border-slate-700 space-y-2 text-xs text-slate-200">
              <p>{wipeResult.local ? 'Tarayıcıdaki sağlık kayıtları silindi.' : 'Tarayıcıdaki sağlık kayıtlarının tamamı silinemedi.'}</p>
              <p>{wipeResult.backend ? 'Yerel sunucudaki seans özetlerinin silindiği doğrulandı.' : 'Yerel sunucudaki seans özetlerinin silindiği doğrulanamadı; kayıtlar hâlâ mevcut olabilir.'}</p>
              {wipeStatus !== 'SUCCESS' && <p className="text-amber-200">{wipeStatus === 'PARTIAL' ? 'Silme işlemi kısmen tamamlandı.' : 'Silme işlemi tamamlanamadı.'}</p>}
              <button onClick={handleWipeAllData} className="underline">Yeniden Dene</button>
            </div>
          )}
          {wipeStatus === 'SUCCESS' && (
            <div className="bg-emerald-950/40 border border-emerald-700/80 rounded-xl p-4 text-emerald-300 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Tüm yerel veriler başarıyla temizlendi.</span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
