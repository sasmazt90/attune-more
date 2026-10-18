import { readHealthRecords,recordDate } from './healthRecords';
import { HEALTH_MODULES } from './healthModules';
/**
 * Attune.more Dynamic Health Selectors
 * Lisans: UNLICENSED
 * 
 * REAL MODE vs DEMO MODE dinamik veri seçicileri.
 * Real modda localStorage ve yerel telemetriden okur; veri yoksa kesinlikle sahte sayı üretmez (empty-state döner).
 * Demo modda ise sunum fikstürlerini sağlar.
 */

import { STORAGE_KEYS, isDemoMode } from './attuneMode';

export interface VisionSummaryData {
  hasData: boolean;
  isDemo: boolean;
  dateTr: string;
  acuitySummary: string;
  contrastSummary: string;
  referralRecommended: boolean;
  rawRecord?: any;
}

export interface SkinSummaryData {
  hasData: boolean;
  isDemo: boolean;
  dateTr: string;
  regionNameTr: string;
  changePct: number;
  changeLabel: string;
  recommendation: string;
  isBaseline: boolean;
  rawRecord?: any;
}

export interface MentalSummaryData {
  hasData: boolean;
  isDemo: boolean;
  dateTr: string;
  primaryTheme: string;
  sessionCount: number;
  sessionCountLabel: string;
  recommendation: string;
}

export interface HealthTimelineItem {
  id: string;
  dateTr: string;
  moduleName: string;
  badgeClass: string;
  description: string;
  isDemo: boolean;
}

export const EMPTY_VISION_SUMMARY: VisionSummaryData = {
  hasData: false, isDemo: false, dateTr: '', acuitySummary: 'Henüz değerlendirme yok',
  contrastSummary: 'Ön değerlendirme bekleniyor', referralRecommended: false
};
export const EMPTY_SKIN_SUMMARY: SkinSummaryData = {
  hasData: false, isDemo: false, dateTr: '', regionNameTr: 'Henüz değerlendirme yok',
  changePct: 0, changeLabel: 'Ölçüm bekleniyor', recommendation: 'Henüz kayıtlı analiz yok', isBaseline: false
};
export const EMPTY_MENTAL_SUMMARY: MentalSummaryData = {
  hasData: false, isDemo: false, dateTr: '', primaryTheme: 'Henüz görüşme yok',
  sessionCount: 0, sessionCountLabel: '0 görüşme', recommendation: 'Asistanla görüşme bekleniyor'
};

export function getVisionSummary(demoMode: boolean = isDemoMode()): VisionSummaryData {
  if (typeof window === 'undefined' && !demoMode) return EMPTY_VISION_SUMMARY;

  if (demoMode) {
    return {
      hasData: true,
      isDemo: true,
      dateTr: '18 Eylül 2026',
      acuitySummary: '20/30 • 20/24',
      contrastSummary: '1.55 LogCS (İzleniyor)',
      referralRecommended: false
    };
  }

  const raw = localStorage.getItem(STORAGE_KEYS.LATEST_VISION);
  if (!raw) {
    return {
      hasData: false,
      isDemo: false,
      dateTr: '',
      acuitySummary: 'Henüz değerlendirme yok',
      contrastSummary: 'Ön değerlendirme bekleniyor',
      referralRecommended: false
    };
  }

  try {
    const parsed = JSON.parse(raw);
    const dateObj = parsed.date ? new Date(parsed.date) : new Date();
    const dateTr = dateObj.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' });
    if (parsed.protocolVersion==='spoken-letter-v1') return {hasData:true,isDemo:false,dateTr,acuitySummary:'Cihaz koşullarında harf tanıma; klinik keskinlik hesaplanmadı',contrastSummary:`${parsed.trials?.filter((t:any)=>t.valid).length||0} geçerli deneme · Boyut bazında harf/yön/birleşik sonuç`,referralRecommended:false,rawRecord:parsed};
    if (['landolt-orientation-continuous-v1','landolt-orientation-guided-v2'].includes(parsed.protocolVersion)) return { hasData:true,isDemo:false,dateTr,acuitySummary:'Görme keskinliği bu protokolle hesaplanmadı',contrastSummary:`${parsed.validTrials || 0} geçerli deneme · ${parsed.notVisible || 0} göremedi`,referralRecommended:false,rawRecord:parsed };
    const right = parsed.acuityRightSnellen || '—';
    const left = parsed.acuityLeftSnellen || '—';
    const acuitySummary = (right === '—' && left === '—') ? '—' : `${right} • ${left}`;
    const contrastVal = parsed.contrastSensitivityLogCS ? `${Number(parsed.contrastSensitivityLogCS).toFixed(2)} LogCS` : 'Ön Değerlendirme';

    return {
      hasData: true,
      isDemo: false,
      dateTr,
      acuitySummary,
      contrastSummary: contrastVal,
      referralRecommended: !!parsed.ophthalmologistReferralRecommended,
      rawRecord: parsed
    };
  } catch {
    return {
      hasData: false,
      isDemo: false,
      dateTr: '',
      acuitySummary: 'Henüz değerlendirme yok',
      contrastSummary: 'Ön değerlendirme bekleniyor',
      referralRecommended: false
    };
  }
}

export function getSkinSummary(demoMode: boolean = isDemoMode()): SkinSummaryData {
  if (typeof window === 'undefined' && !demoMode) return EMPTY_SKIN_SUMMARY;

  if (demoMode) {
    return {
      hasData: true,
      isDemo: true,
      dateTr: '21 Eylül 2026',
      regionNameTr: 'Sağ Yanak',
      changePct: 22,
      changeLabel: '+%22 Değişim',
      recommendation: 'Uzman görüşü önerildi',
      isBaseline: false
    };
  }

  const raw = localStorage.getItem(STORAGE_KEYS.LATEST_SKIN);
  if (!raw) {
    return {
      hasData: false,
      isDemo: false,
      dateTr: '',
      regionNameTr: 'Henüz değerlendirme yok',
      changePct: 0,
      changeLabel: 'Ölçüm bekleniyor',
      recommendation: 'Henüz kayıtlı analiz yok',
      isBaseline: false
    };
  }

  try {
    const parsed = JSON.parse(raw);
    const dateObj = parsed.timestamp ? new Date(parsed.timestamp) : new Date();
    const dateTr = dateObj.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' });
    const isBaseline = !!parsed.isBaseline;
    const regionNameTr = parsed.highestChangeRegion || (isBaseline ? 'Referans Tarama' : 'Tüm Bölgeler');
    const changePct = Number(parsed.highestChangePct || 0);
    const changeLabel = parsed.analysisMode==='instant-appearance-v2'?'Mevcut görünüm analizi':parsed.comparisonUnavailable ? 'Karşılaştırılamadı' : isBaseline
      ? 'Referans Kaydedildi'
      : `Kızarıklık piksel göstergesi: ${changePct > 0 ? '+' : ''}${changePct}%`;

    return {
      hasData: true,
      isDemo: false,
      dateTr,
      regionNameTr,
      changePct,
      changeLabel,
      recommendation: parsed.analysisMode==='instant-appearance-v2'?'Bölge ve kriter sonuçlarını inceleyin':parsed.referenceDeleted ? 'Yeni referans taraması gerekiyor' : parsed.comparisonUnavailable ? 'Uyumlu ışık/netlik/poz koşullarında yeniden deneyin' : isBaseline ? 'Sonraki uygun taramayla karşılaştırılacak' : parsed.referralSuggested ? 'Uzman görüşü önerildi' : 'Referans bandında',
      isBaseline,
      rawRecord: parsed
    };
  } catch {
    return {
      hasData: false,
      isDemo: false,
      dateTr: '',
      regionNameTr: 'Henüz değerlendirme yok',
      changePct: 0,
      changeLabel: 'Ölçüm bekleniyor',
      recommendation: 'Henüz kayıtlı analiz yok',
      isBaseline: false
    };
  }
}

export function getMentalSummary(demoMode: boolean = isDemoMode()): MentalSummaryData {
  if (demoMode) {
    return {
      hasData: true,
      isDemo: true,
      dateTr: '19 Eylül 2026',
      primaryTheme: 'Uyku düzensizliği',
      sessionCount: 4,
      sessionCountLabel: '4 görüşme',
      recommendation: 'Rahatlatıcı kabin ortamı önerildi'
    };
  }

  // Real Mode: check stored mental sessions count or latest summary
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem(STORAGE_KEYS.LATEST_MENTAL);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        return {
          hasData: true,
          isDemo: false,
          dateTr: parsed.dateTr || 'Bugün',
          primaryTheme: parsed.primaryTheme || 'Genel İyi Oluş',
          sessionCount: parsed.sessionCount || 1,
          sessionCountLabel: `${parsed.sessionCount || 1} görüşme`,
          recommendation: parsed.recommendation || 'Takip önerildi'
        };
      } catch {}
    }
  }

  return {
    hasData: false,
    isDemo: false,
    dateTr: '',
    primaryTheme: 'Henüz görüşme yok',
    sessionCount: 0,
    sessionCountLabel: '0 görüşme',
    recommendation: 'Asistanla görüşme bekleniyor'
  };
}

export function getHealthTimeline(demoMode: boolean = isDemoMode()): HealthTimelineItem[] {
  if (demoMode) {
    return [
      {
        id: 'demo-skin',
        dateTr: '21 Eylül 2026',
        moduleName: HEALTH_MODULES.skin.name,
        badgeClass: 'bg-emerald-950/60 text-emerald-400 border-emerald-800/60',
        description: 'Sağ yanak bölgesinde baz çizgiye göre +%22 doku varyansı ve kızarıklık eğilimi kaydedildi. Uzman yönlendirme önerisi Care Agent\'a iletildi.',
        isDemo: true
      },
      {
        id: 'demo-mental',
        dateTr: '19 Eylül 2026',
        moduleName: HEALTH_MODULES.mental.name,
        badgeClass: 'bg-indigo-950/60 text-indigo-400 border-indigo-800/60',
        description: 'Akşam dönüş yolunda uyku düzensizliği ve yorgunluk teması öne çıktı. Seans hafızası güncellenerek rahatlatıcı kabin rehberliği sağlandı.',
        isDemo: true
      },
      {
        id: 'demo-vision',
        dateTr: '18 Eylül 2026',
        moduleName: HEALTH_MODULES.vision.name,
        badgeClass: 'bg-cyan-950/60 text-togg-turquoise border-cyan-800/60',
        description: 'Kontrast hassasiyetinde baz çizgiye göre hafif değişim eğilimi (1.55 LogCS) izlendi. Keskinlik 20/30 seviyesinde sabit kaldı.',
        isDemo: true
      }
    ];
  }

  const items: HealthTimelineItem[] = [];

  const skin = getSkinSummary(false);
  if (skin.hasData && skin.rawRecord) {
    items.push({
      id: `real-skin-${skin.rawRecord.id || '1'}`,
      dateTr: skin.dateTr,
      moduleName: HEALTH_MODULES.skin.name,
      badgeClass: 'bg-emerald-950/60 text-emerald-400 border-emerald-800/60',
      description: skin.rawRecord.clinicalNoteTr || `${skin.regionNameTr} bölgesinde ${skin.changeLabel} kaydedildi.`,
      isDemo: false
    });
  }

  const vision = getVisionSummary(false);
  if (vision.hasData && vision.rawRecord) {
    items.push({
      id: `real-vision-${vision.rawRecord.id || '1'}`,
      dateTr: vision.dateTr,
      moduleName: HEALTH_MODULES.vision.name,
      badgeClass: 'bg-cyan-950/60 text-togg-turquoise border-cyan-800/60',
      description: ['landolt-orientation-guided-v2','spoken-letter-v1'].includes(vision.rawRecord.protocolVersion) ? `Cihaz koşullarında görev · ${vision.contrastSummary}. ${vision.acuitySummary}.` : `Görme keskinliği ${vision.acuitySummary}. Kontrast hassasiyeti ${vision.contrastSummary}.`,
      isDemo: false
    });
  }

  const mental = getMentalSummary(false);
  if (mental.hasData) {
    items.push({
      id: 'real-mental',
      dateTr: mental.dateTr,
      moduleName: HEALTH_MODULES.mental.name,
      badgeClass: 'bg-indigo-950/60 text-indigo-400 border-indigo-800/60',
      description: `Öne çıkan tema: ${mental.primaryTheme}. Toplam ${mental.sessionCountLabel}.`,
      isDemo: false
    });
  }

  for(const category of ['dental','hearing'] as const){
    try {const records=readHealthRecords(category);for(const row of records.slice(-1))items.push({id:`real-${category}-${row.id}`,dateTr:recordDate(row),moduleName:HEALTH_MODULES[category].name,badgeClass:'bg-cyan-950/60 text-togg-turquoise border-cyan-800/60',description:row.summaryText||'Yerel ön değerlendirme',isDemo:false});}catch{}
  }
  return items;
}
