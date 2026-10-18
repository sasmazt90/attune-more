'use client';
import { HEALTH_MODULES,HEALTH_MODULE_IDS } from '../../utils/healthModules';

import React, { useState, useEffect } from 'react';
import { HealthHistoryOverview } from '../../components/HealthHistoryOverview';
import { RecordHistory } from '../../components/RecordHistory';
import { InformationButton } from '../../components/InformationButton';
import { readHealthRecords } from '../../utils/healthRecords';
import { AccessibleDialog } from '../../components/AccessibleDialog';
import { useVehicle } from '../../context/VehicleContext';
import { mockInitialHealthProfile } from '@packages/health-profile/mockData';
import {
  Download,
  FileText,
} from 'lucide-react';
import { buildShareSections, printHealthSummary, ShareSelection,ShareSection,measuredShareSection } from '../../utils/healthShare';
import { isDemoMode } from '../../utils/attuneMode';
import {
  getVisionSummary,
  EMPTY_VISION_SUMMARY,
  EMPTY_SKIN_SUMMARY,
  EMPTY_MENTAL_SUMMARY,
  getSkinSummary,
  getMentalSummary,
  VisionSummaryData,
  SkinSummaryData,
  MentalSummaryData
} from '../../utils/healthSelectors';

export default function ProfilePage() {

  const { isParked } = useVehicle();
  const profile = mockInitialHealthProfile;
  const [showShareModal, setShowShareModal] = useState<boolean>(false);

  const [selection, setSelection] = useState<ShareSelection>({ vision: false, skin: false, mental: false,dental:false,hearing:false });
  const [shareError, setShareError] = useState<string | null>(null);

  const [isDemo, setIsDemo] = useState<boolean>(false);
  const [vision, setVision] = useState<VisionSummaryData>(EMPTY_VISION_SUMMARY);
  const [skin, setSkin] = useState<SkinSummaryData>(EMPTY_SKIN_SUMMARY);
  const [mental, setMental] = useState<MentalSummaryData>(EMPTY_MENTAL_SUMMARY);
  const [dental,setDental]=useState<ShareSection|null>(null),[hearing,setHearing]=useState<ShareSection|null>(null);

  useEffect(() => {
    const refresh = () => {
      const demo = isDemoMode(); setIsDemo(demo);
      try { if (!demo) for (const category of ['vision', 'skin', 'mental', 'dental', 'hearing'] as const) readHealthRecords(category); }
      catch { setShareError('Kayıtlar doğrulanamadı; veri değiştirilmedi.'); }
      try{setDental(measuredShareSection('dental'));setHearing(measuredShareSection('hearing'));}catch{setDental(null);setHearing(null);}
      setVision(getVisionSummary(demo)); setSkin(getSkinSummary(demo)); setMental(getMentalSummary(demo));
    };
    refresh(); window.addEventListener('attune-records', refresh); window.addEventListener('storage', refresh);
    return () => { window.removeEventListener('attune-records', refresh); window.removeEventListener('storage', refresh); };
  }, []);

  return (
    <div className="space-y-6">
      {/* 1. SCREEN 09: ÜST PROFİL KARTI VE BİRİNCİL AKSIYONLAR (FIRST VIEWPORT) */}
      <section className="bg-gradient-to-br from-cockpit-surface via-[#071322] to-cockpit-bg border border-white/10 rounded-2xl p-6 md:p-7 shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-togg-darkBlue/90 border border-togg-turquoise/40 flex items-center justify-center text-togg-turquoise font-extrabold text-xl shadow-[0_0_15px_rgba(0,194,231,0.2)]">
            {isDemo ? 'AY' : 'Siz'}
          </div>
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl md:text-2xl font-extrabold text-white">Sağlık Geçmişim</h1><InformationButton title="Sağlık geçmişi"><p>Sonuçlar bu tarayıcı profilinde saklanır. Silme yalnız seçtiğiniz uygulama kaydını kaldırır; dış sağlayıcının geçmiş isteklerini silmez. Paylaşımda yalnız seçtiğiniz kategoriler yazdırılır.</p></InformationButton>
              <span className="text-slate-500">•</span>
              <span className="text-slate-300 font-medium text-sm">{isDemo ? profile.user.displayName + ' (örnek kimlik)' : 'Yerel kullanıcı'}</span>
              {isDemo && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-950/80 border border-togg-turquoise/30 text-togg-turquoise lowercase font-mono">
                  demo veri
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400">
              {isDemo ? 'Örnek profil • ' : ''}Yerel veri koruma
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => setShowShareModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-togg-darkBlue/70 hover:bg-togg-darkBlue text-togg-turquoise border border-togg-darkTurquoise/60 text-xs font-bold transition-all shadow-md min-h-touch"
          >
            <FileText className="w-4 h-4" />
            <span>Hekimle Paylaşılabilir Özet</span>
          </button>


        </div>
      </section>

      <HealthHistoryOverview />

      {!isDemo && <section className="bg-cockpit-surface border border-white/10 rounded-2xl p-5 space-y-7">
        <RecordHistory parked={isParked} />
      </section>}

      {/* PAYLAŞILABİLİR ÖZET MODALI */}
      {showShareModal && (
        <AccessibleDialog title="Hekim Paylaşım Özeti" onClose={() => setShowShareModal(false)} className="bg-cockpit-surface border border-togg-turquoise/40 rounded-2xl p-6 md:p-8 max-w-lg w-full space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2 text-togg-turquoise font-bold">
                <FileText className="w-5 h-5" />
                <span>Hekim Paylaşım Özeti (Klinik Dışı Değişim Raporu)</span>
              </div>
              <button
                onClick={() => setShowShareModal(false)}
                aria-label="Pencereyi kapat"
                className="w-11 shrink-0 text-slate-400 hover:text-white text-xs"
              >
                ✕
              </button>
            </div>

            <fieldset className="space-y-2 text-sm">
              <legend>Rapora dahil edilecek sonuçları seçin</legend>
              {HEALTH_MODULE_IDS.map(key => {
                const available = key==='dental'?Boolean(dental):key==='hearing'?Boolean(hearing):{vision,skin,mental}[key].hasData;
                const label = HEALTH_MODULES[key].name;
                return <label key={key} className="flex items-center gap-2">
                  <input type="checkbox" checked={Boolean(selection[key])} disabled={!available || !isParked}
                    onChange={e => setSelection(previous => ({ ...previous, [key]: e.target.checked }))} />
                  {label}{!available && ' — kayıt bulunmuyor'}
                </label>;
              })}
            </fieldset>
            <div data-share-preview className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3 text-xs">
              <p>{isDemo ? 'Demo rapor — örnek kullanıcı' : 'Yerel kullanıcı — kimlik doğrulanmadı'}</p>
              {buildShareSections(selection, vision, skin, mental,dental,hearing).map(section => <section key={section.title}>
                <strong>{section.title}</strong><p>{section.text}</p><p>{section.dateTr}</p>
              </section>)}
              {!buildShareSections(selection, vision, skin, mental,dental,hearing).length && <p>En az bir mevcut sonucu seçin.</p>}
            </div>
            <p className="text-xs text-slate-400">Klinik tanı değildir. Seçtiğiniz bilgiler bu cihazın yazdırma penceresine aktarılır; hekime otomatik gönderilmez. PDF kaydetme hedefini bu pencerede siz seçersiniz.</p>
            {shareError && <p role="alert">{shareError}</p>}
            <p id="share-print-status" role="status" className="text-xs text-slate-300">
              {!isParked ? 'Yazdırma yalnız PARK durumunda kullanılabilir.' : buildShareSections(selection, vision, skin, mental,dental,hearing).length === 0 ? 'Yazdırmak için en az bir kayıtlı sonucu seçin.' : 'Yalnız seçtiğiniz kategoriler yazdırılır.'}
            </p>
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowShareModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-semibold"
              >
                Kapat
              </button>
              <button
                disabled={!isParked || buildShareSections(selection, vision, skin, mental,dental,hearing).length === 0}
                aria-describedby="share-print-status"
                onClick={() => {
                  setShareError(null);
                  try {
                    printHealthSummary(buildShareSections(selection, vision, skin, mental,dental,hearing), isDemo);
                  } catch {
                    setShareError('Yazdırma penceresi açılamadı. Rapor indirilmedi veya gönderilmedi.');
                  }
                }}
                className="flex items-center gap-2 px-5 py-2.5 bg-togg-turquoise enabled:hover:bg-[#33D0EE] text-togg-darkBlue rounded-xl text-xs font-bold shadow-md disabled:bg-slate-800 disabled:text-slate-400 disabled:[box-shadow:none] disabled:cursor-not-allowed"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Yazdır / PDF olarak kaydet</span>
              </button>
            </div>
        </AccessibleDialog>
      )}
    </div>
  );
}
