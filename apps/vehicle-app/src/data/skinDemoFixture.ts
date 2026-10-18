export type SkinRegionId =
  | 'forehead'
  | 'rightCheek'
  | 'leftCheek'
  | 'nose'
  | 'chin'
  | 'periorbital';

export const REGION_ORDER: SkinRegionId[] = [
  'forehead',
  'rightCheek',
  'leftCheek',
  'nose',
  'chin',
  'periorbital'
];

export interface RegionTrendPoint {
  date: string;
  value: number;
}

export interface MetricItem {
  label: string;
  score: number;
  displayValue: string;
  status: 'amber' | 'cyan' | 'emerald';
}

export interface SkinRegionData {
  indicators?:import('../utils/skinIndicators').SkinIndicator[];
  id: SkinRegionId | 'overview';
  viewTotal?: number;
  skinType?: import('../utils/skinOverview').SkinOverview['skinType'];
  index: number;
  nameTr: string;
  badgeText: string;
  changePct: number;
  isAttentionRequired: boolean;
  metrics: {
    redness: MetricItem;
    luminance: MetricItem;
    texture: MetricItem;
    baselineChange: MetricItem;
  };
  trend: RegionTrendPoint[];
  observation: {
    headline: string;
    details: string;
  };
  actions: Array<{
    icon: 'calendar' | 'shield' | 'care';
    title: string;
    description: string;
    isCareHandoff?: boolean;
  }>;
  // Anatomik SVG path verisi (100x100 normalize koordinat uzayı)
  svgPaths: string[];
  // Gradient merkezi (cx, cy, r)
  gradientCenter: { cx: string; cy: string; r: string };
}

export const SKIN_REGIONS: Record<SkinRegionId, SkinRegionData> = {
  forehead: {
    id: 'forehead',
    index: 1,
    nameTr: 'Alın',
    badgeText: '+4%',
    changePct: 4,
    isAttentionRequired: false,
    metrics: {
      redness: {
        label: 'Kızarıklık Eğilimi',
        score: 32,
        displayValue: 'Stabil',
        status: 'cyan'
      },
      luminance: {
        label: 'Ton / Parlaklık',
        score: 68,
        displayValue: 'Yüksek parlaklık',
        status: 'cyan'
      },
      texture: {
        label: 'Eski piksel doku farkı',
        score: 22,
        displayValue: 'Stabil',
        status: 'cyan'
      },
      baselineChange: {
        label: 'Referansa Göre Değişim',
        score: 35,
        displayValue: 'Stabil (+4%)',
        status: 'emerald'
      }
    },
    trend: [
      { date: '17 Eyl', value: 2 },
      { date: '19 Eyl', value: 3 },
      { date: '21 Eyl', value: 4 }
    ],
    observation: {
      headline: 'Alın bölgesinde homojen ton ve dengeli doku dağılımı korunuyor.',
      details: 'Önceki taramaya kıyasla belirgin bir doku veya kızarıklık sapması saptanmadı. Genel görünüm fizyolojik sınırlar içerisindedir.'
    },
    actions: [
      {
        icon: 'calendar',
        title: 'Düzenli takip taraması yapın',
        description: '4 hafta sonra yeniden tarama önerilir.'
      },
      {
        icon: 'shield',
        title: 'Cilt bariyerini destekleyin',
        description: 'Günlük cilt bakımınızı ve koruyucu rutininizi sürdürün.'
      },
      {
        icon: 'care',
        title: 'Uzman görüşü alabilirsiniz',
        description: 'Detaylı değerlendirme için Care Agent ile ilerleyin.',
        isCareHandoff: true
      }
    ],
    // Doğal alın anatomisi: Kaşların 15px üstünden başlayan, kaş kavisi boyunca yükselen, şakaklarda ve saç çizgisi altında yumuşakça sönen anatomik kubbe
    svgPaths: [
      'M 29 27.5 C 36 26.5, 43 26.0, 50 26.0 C 57 26.0, 64 26.5, 71 27.5 C 69.5 21.8, 62 17.2, 50 17.2 C 38 17.2, 30.5 21.8, 29 27.5 Z'
    ],
    gradientCenter: { cx: '50%', cy: '22.5%', r: '26%' }
  },
  rightCheek: {
    id: 'rightCheek',
    index: 2,
    nameTr: 'Sağ Yanak',
    badgeText: '+22%',
    changePct: 22,
    isAttentionRequired: true,
    metrics: {
      redness: {
        label: 'Kızarıklık Eğilimi',
        score: 64,
        displayValue: 'Yüksek (+22%)',
        status: 'amber'
      },
      luminance: {
        label: 'Ton / Parlaklık',
        score: 52,
        displayValue: 'Stabil',
        status: 'cyan'
      },
      texture: {
        label: 'Eski piksel doku farkı',
        score: 48,
        displayValue: 'Hafif Artış',
        status: 'cyan'
      },
      baselineChange: {
        label: 'Referansa Göre Değişim',
        score: 58,
        displayValue: 'Takip Önerilir (+22%)',
        status: 'amber'
      }
    },
    trend: [
      { date: '17 Eyl', value: 6 },
      { date: '19 Eyl', value: 14 },
      { date: '21 Eyl', value: 22 }
    ],
    observation: {
      headline: 'Sağ yanak bölgesinde referans taramaya göre izlemeye değer bir görsel değişim gözlendi.',
      details: 'Bu bölgede kızarıklık eğiliminde hafif artış, doku varyansında ise sınırlı bir değişim tespit edildi. Genel cilt görünümü stabil seyrediyor.'
    },
    actions: [
      {
        icon: 'calendar',
        title: 'Düzenli takip taraması yapın',
        description: '4 hafta sonra yeniden tarama önerilir.'
      },
      {
        icon: 'shield',
        title: 'Cilt bariyerini destekleyin',
        description: 'Günlük cilt bakımınızı ve koruyucu rutininizi sürdürün.'
      },
      {
        icon: 'care',
        title: 'Uzman görüşü alabilirsiniz',
        description: 'Detaylı değerlendirme için Care Agent ile ilerleyin.',
        isCareHandoff: true
      }
    ],
    // Doğal elmacık kemiği anatomisi: infraorbital alan altından başlayan, zygomatik kemiği izleyen, nazolabiyal katlantı ve ağız köşesi üstünde soft fade olan asimetrik organik maske
    svgPaths: [
      'M 29.5 41.8 C 33.5 42.2, 37.5 42.5, 41.0 43.5 C 42.8 47.0, 42.2 51.8, 39.5 55.5 C 37.0 58.0, 33.0 58.2, 29.5 56.8 C 26.0 54.8, 25.0 50.0, 25.8 45.5 C 26.6 43.5, 28.0 42.2, 29.5 41.8 Z'
    ],
    gradientCenter: { cx: '33%', cy: '49%', r: '24%' }
  },
  leftCheek: {
    id: 'leftCheek',
    index: 3,
    nameTr: 'Sol Yanak',
    badgeText: '-3%',
    changePct: -3,
    isAttentionRequired: false,
    metrics: {
      redness: {
        label: 'Kızarıklık Eğilimi',
        score: 35,
        displayValue: 'Stabil',
        status: 'cyan'
      },
      luminance: {
        label: 'Ton / Parlaklık',
        score: 64,
        displayValue: 'Yüksek parlaklık',
        status: 'cyan'
      },
      texture: {
        label: 'Eski piksel doku farkı',
        score: 22,
        displayValue: 'Stabil',
        status: 'cyan'
      },
      baselineChange: {
        label: 'Referansa Göre Değişim',
        score: 28,
        displayValue: 'Stabil (-3%)',
        status: 'emerald'
      }
    },
    trend: [
      { date: '17 Eyl', value: 0 },
      { date: '19 Eyl', value: -1 },
      { date: '21 Eyl', value: -3 }
    ],
    observation: {
      headline: 'Sol yanak dokusu ve renk dağılımı referans baz değerlerle tam uyumludur.',
      details: 'Eritem veya doku düzensizliği saptanmadı. Cilt bariyeri dengeli seyretmektedir.'
    },
    actions: [
      {
        icon: 'calendar',
        title: 'Düzenli takip taraması yapın',
        description: '4 hafta sonra yeniden tarama önerilir.'
      },
      {
        icon: 'shield',
        title: 'Cilt bariyerini koruyun',
        description: 'Rutin cilt bakımınızı sürdürün.'
      },
      {
        icon: 'care',
        title: 'Uzman görüşü alabilirsiniz',
        description: 'Detaylı değerlendirme için Care Agent ile ilerleyin.',
        isCareHandoff: true
      }
    ],
    // Sol yanak simetrik anatomik karşılığı
    svgPaths: [
      'M 70.5 41.8 C 66.5 42.2, 62.5 42.5, 59.0 43.5 C 57.2 47.0, 57.8 51.8, 60.5 55.5 C 63.0 58.0, 67.0 58.2, 70.5 56.8 C 74.0 54.8, 75.0 50.0, 74.2 45.5 C 73.4 43.5, 72.0 42.2, 70.5 41.8 Z'
    ],
    gradientCenter: { cx: '67%', cy: '49%', r: '24%' }
  },
  nose: {
    id: 'nose',
    index: 4,
    nameTr: 'Burun',
    badgeText: '+6%',
    changePct: 6,
    isAttentionRequired: false,
    metrics: {
      redness: {
        label: 'Kızarıklık Eğilimi',
        score: 40,
        displayValue: 'Stabil (+6%)',
        status: 'cyan'
      },
      luminance: {
        label: 'Ton / Parlaklık',
        score: 60,
        displayValue: 'Yüksek parlaklık',
        status: 'cyan'
      },
      texture: {
        label: 'Eski piksel doku farkı',
        score: 26,
        displayValue: 'Stabil',
        status: 'cyan'
      },
      baselineChange: {
        label: 'Referansa Göre Değişim',
        score: 38,
        displayValue: 'Stabil (+6%)',
        status: 'emerald'
      }
    },
    trend: [
      { date: '17 Eyl', value: 3 },
      { date: '19 Eyl', value: 5 },
      { date: '21 Eyl', value: 6 }
    ],
    observation: {
      headline: 'Burun çevresinde hafif sebase parlaklık ve minimal ton değişimi gözlendi.',
      details: 'T-bölgesi için olağan fizyolojik sınırlar dahilindedir. Özel bir müdahale gerektirmemektedir.'
    },
    actions: [
      {
        icon: 'calendar',
        title: 'Düzenli takip taraması yapın',
        description: '4 hafta sonra yeniden tarama önerilir.'
      },
      {
        icon: 'shield',
        title: 'T-bölgesi arındırıcı bakım',
        description: 'Cildinizi arındırıcı ve dengeleyici nazik bakım uygulayın.'
      },
      {
        icon: 'care',
        title: 'Uzman görüşü alabilirsiniz',
        description: 'Detaylı değerlendirme için Care Agent ile ilerleyin.',
        isCareHandoff: true
      }
    ],
    svgPaths: [
      'M 47.5 37 C 49 36, 51 36, 52.5 37 C 53 41, 53.5 45, 55 48.5 C 54 52.5, 51.5 53.5, 50 53.5 C 48.5 53.5, 46 52.5, 45 48.5 C 46.5 45, 47 41, 47.5 37 Z'
    ],
    gradientCenter: { cx: '50%', cy: '46%', r: '20%' }
  },
  chin: {
    id: 'chin',
    index: 5,
    nameTr: 'Çene',
    badgeText: '+2%',
    changePct: 2,
    isAttentionRequired: false,
    metrics: {
      redness: {
        label: 'Kızarıklık Eğilimi',
        score: 28,
        displayValue: 'Stabil',
        status: 'emerald'
      },
      luminance: {
        label: 'Ton / Parlaklık',
        score: 65,
        displayValue: 'Yüksek parlaklık',
        status: 'cyan'
      },
      texture: {
        label: 'Eski piksel doku farkı',
        score: 16,
        displayValue: 'Stabil',
        status: 'cyan'
      },
      baselineChange: {
        label: 'Referansa Göre Değişim',
        score: 24,
        displayValue: 'Stabil (+2%)',
        status: 'emerald'
      }
    },
    trend: [
      { date: '17 Eyl', value: 1 },
      { date: '19 Eyl', value: 1 },
      { date: '21 Eyl', value: 2 }
    ],
    observation: {
      headline: 'Çene bölgesinde doku homojenitesi yüksek ve tahriş izi bulunmuyor.',
      details: 'Baz çizgi ölçümleriyle tam örtüşmektedir. Yüzey pürüzsüzlüğü korunmaktadır.'
    },
    actions: [
      {
        icon: 'calendar',
        title: 'Düzenli takip taraması yapın',
        description: '4 hafta sonra yeniden tarama önerilir.'
      },
      {
        icon: 'shield',
        title: 'Cilt bariyerini koruyun',
        description: 'Rutin cilt bakımınızı sürdürün.'
      },
      {
        icon: 'care',
        title: 'Uzman görüşü alabilirsiniz',
        description: 'Detaylı değerlendirme için Care Agent ile ilerleyin.',
        isCareHandoff: true
      }
    ],
    svgPaths: [
      'M 43.5 64 C 47 63, 53 63, 56.5 64 C 58 68, 55.5 73, 50 73 C 44.5 73, 42 68, 43.5 64 Z'
    ],
    gradientCenter: { cx: '50%', cy: '68%', r: '20%' }
  },
  periorbital: {
    id: 'periorbital',
    index: 6,
    nameTr: 'Göz Çevresi',
    badgeText: '+8%',
    changePct: 8,
    isAttentionRequired: false,
    metrics: {
      redness: {
        label: 'Kızarıklık Eğilimi',
        score: 30,
        displayValue: 'Stabil',
        status: 'cyan'
      },
      luminance: {
        label: 'Ton / Parlaklık',
        score: 54,
        displayValue: 'Stabil',
        status: 'cyan'
      },
      texture: {
        label: 'Eski piksel doku farkı',
        score: 34,
        displayValue: 'Hafif Artış',
        status: 'cyan'
      },
      baselineChange: {
        label: 'Referansa Göre Değişim',
        score: 42,
        displayValue: 'İzleniyor (+8%)',
        status: 'emerald'
      }
    },
    trend: [
      { date: '17 Eyl', value: 4 },
      { date: '19 Eyl', value: 6 },
      { date: '21 Eyl', value: 8 }
    ],
    observation: {
      headline: 'Göz çevresinde referansa göre hafif ton ve doku varyasyonu gözlendi.',
      details: 'Uzun sürüş veya yorgunluğa bağlı sınırlı bir ton değişimi mevcuttur. Düzenli mola ve dinlenme önerilir.'
    },
    actions: [
      {
        icon: 'calendar',
        title: 'Düzenli takip taraması yapın',
        description: '4 hafta sonra yeniden tarama önerilir.'
      },
      {
        icon: 'shield',
        title: 'Göz çevresi dinlendirici mola',
        description: 'Uzun sürüşlerde düzenli mola vererek gözlerinizi dinlendirin.'
      },
      {
        icon: 'care',
        title: 'Uzman görüşü alabilirsiniz',
        description: 'Detaylı değerlendirme için Care Agent ile ilerleyin.',
        isCareHandoff: true
      }
    ],
    // Doğal periorbital anatomi: İki göz için alt orbital rim ve göz altı çukuru (tear trough) boyunca uzanan yumuşak geçişli iki hilal maske; göz küresi, iris ve sklera tamamen açık
    svgPaths: [
      // Sağ göz altı (Görüntünün solu)
      'M 28.5 40.8 C 32.5 41.8, 37.5 41.8, 42.0 41.0 C 41.0 45.5, 35.5 46.5, 30.5 45.0 C 29.0 44.0, 28.0 42.5, 28.5 40.8 Z',
      // Sol göz altı (Görüntünün sağı)
      'M 58.0 41.0 C 62.5 41.8, 67.5 41.8, 71.5 40.8 C 72.0 42.5, 71.0 44.0, 69.5 45.0 C 64.5 46.5, 59.0 45.5, 58.0 41.0 Z'
    ],
    gradientCenter: { cx: '50%', cy: '43.8%', r: '28%' }
  }
};

export const getRegionData = (id: SkinRegionId): SkinRegionData => {
  return SKIN_REGIONS[id] || SKIN_REGIONS.forehead;
};

export const getRegionByIndex = (index: number): SkinRegionData => {
  const safeIndex = ((index % REGION_ORDER.length) + REGION_ORDER.length) % REGION_ORDER.length;
  const id = REGION_ORDER[safeIndex];
  return SKIN_REGIONS[id];
};

/**
 * Real Mode analiz sonucunu veya Demo Mode fikstürünü UI view modeline dönüştürür.
 * Görsel SVG geometrisi ve layout config korunur; metrikler Real Mode'da gerçek SkinAnalysisResult'tan gelir.
 */
export function buildSkinRegionViewModel(
  regionId: SkinRegionId,
  analysisResult: any | null,
  isDemo: boolean = false
): SkinRegionData {
  const base = getRegionData(regionId);
  if(analysisResult?.schemaVersion===3)return {...base,nameTr:regionId==='nose'?'T-Bölgesi':base.nameTr,indicators:analysisResult.indicators?.[regionId]||[],badgeText:analysisResult.isBaseline?'Yeni ölçüm referansı':'Yeni değerlendirme',trend:[],changePct:0,isAttentionRequired:false,observation:{headline:`${regionId==='nose'?'T-Bölgesi':base.nameTr} — görsel değerlendirme`,details:analysisResult.indicators?.[regionId]?.some((row:import('../utils/skinIndicators').SkinIndicator)=>row.appearance)?'Kabul edilen gerçek fotoğrafta mevcut görüntünün bölgesel görünüm adayları hesaplandı. Bunlar tanı, cilt nemi veya klinik şiddet değildir. Kalite yetersizse o ölçüm gösterilmez.':'Renk indeksleri yalnız kabul edilmiş fotoğrafta ölçülür. Boş göstergeler için doğrulanmış yöntem yoktur. Eski parlaklık/doku skorları bu başlıklara dönüştürülmez.'}};
  if (isDemo) {
    return base;
  }

  // REAL MODE: Analiz sonucu yoksa veya bölge verisi eksikse kesinlikle demo sayılarına düşülmez
  if (!analysisResult || !analysisResult.regions || !analysisResult.regions[regionId]) {
    return {
      ...base,
      changePct: 0,
      badgeText: '—',
      isAttentionRequired: false,
      metrics: {
        redness: {
          label: 'Kızarıklık Eğilimi',
          score: 0,
          displayValue: '—',
          status: 'cyan'
        },
        luminance: {
          label: 'Ton / Parlaklık',
          score: 0,
          displayValue: '—',
          status: 'cyan'
        },
        texture: {
          label: 'Eski piksel doku farkı',
          score: 0,
          displayValue: '—',
          status: 'cyan'
        },
        baselineChange: {
          label: 'Referansa Göre Değişim',
          score: 0,
          displayValue: '—',
          status: 'emerald'
        }
      },
      trend: [],
      observation: {
        headline: 'Analiz verisi bulunamadı',
        details: 'Bu bölge için henüz gerçek zamanlı analiz sonucu mevcut değil.'
      }
    };
  }

  const real = analysisResult.regions[regionId];
  const changePct = typeof real.changeFromBaselinePct === 'number' ? real.changeFromBaselinePct : 0;
  const isAttentionRequired = Math.abs(changePct) >= 20;

  const rednessScore = typeof real.rednessScore === 'number' ? real.rednessScore : 0;
  const rednessStatus: 'amber' | 'cyan' | 'emerald' = rednessScore > 50 ? 'amber' : 'cyan';
  const rednessDisplay = rednessScore > 50 ? 'Yüksek' : rednessScore > 35 ? 'Orta' : 'Düşük';

  const lumScore = typeof real.luminanceScore === 'number' ? real.luminanceScore : 0;
  const lumDisplay = lumScore > 60 ? 'Yüksek parlaklık' : lumScore < 40 ? 'Düşük' : 'Dengeli';

  const textScore = typeof real.textureVariance === 'number' ? real.textureVariance : 0;
  const textStatus: 'amber' | 'cyan' | 'emerald' = textScore > 40 ? 'amber' : 'cyan';
  const textDisplay = textScore > 40 ? 'Belirgin piksel farkı' : textScore > 20 ? 'Orta piksel farkı' : 'Az piksel farkı';

  const comparable = !analysisResult.isBaseline && !analysisResult.comparisonUnavailable && typeof real.changeFromBaselinePct === 'number';
  const deltaDisplay = !comparable ? (analysisResult.isBaseline ? 'İlk tarama' : 'Karşılaştırılamadı') : `${changePct > 0 ? '+' : ''}${changePct}%`;
  const deltaStatus: 'amber' | 'cyan' | 'emerald' = isAttentionRequired ? 'amber' : 'emerald';

  return {
    ...base,
    changePct,
    badgeText: deltaDisplay,
    isAttentionRequired,
    metrics: {
      redness: {
        ...base.metrics.redness,
        score: Math.round(rednessScore),
        displayValue: rednessDisplay,
        status: rednessStatus
      },
      luminance: {
        ...base.metrics.luminance,
        score: Math.round(lumScore),
        displayValue: lumDisplay,
        status: 'cyan'
      },
      texture: {
        ...base.metrics.texture,
        score: Math.round(textScore),
        displayValue: textDisplay,
        status: textStatus
      },
      baselineChange: {
        ...base.metrics.baselineChange,
        score: Math.min(100, Math.abs(changePct) * 3),
        displayValue: deltaDisplay,
        status: deltaStatus
      }
    },
    observation: {
      headline: `${base.nameTr} — ${deltaDisplay}`,
      details: !comparable ? `${base.nameTr}: ${deltaDisplay}. İlk geçerli taramanızın sayısal metrikleri referanstır; bu sonuç tanı değildir.` :
        `${base.nameTr} bölgesinin kızarıklık piksel göstergesinde ${changePct > 0 ? '+' : ''}${changePct}% fark ölçüldü. Işık ve poz bu göstergeleri etkileyebilir; klinik değişim veya tanı değildir.`
    }
  };
}

