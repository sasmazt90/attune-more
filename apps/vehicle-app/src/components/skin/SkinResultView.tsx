'use client';

import React from 'react';
import { SkinRegionData } from '../../data/skinDemoFixture';
import { SkinSnapshot } from '../../utils/skinSnapshot';
import { InformationButton } from '../InformationButton';
import { SkinFacePanel } from './SkinFacePanel';
import { SkinRegionSummary } from './SkinRegionSummary';

interface SkinResultViewProps {
  currentRegion: SkinRegionData;
  snapshot?: SkinSnapshot;
  onPrev: () => void;
  onNext: () => void;
  onOpenModal: (modal: 'trend' | 'observation' | 'actions') => void;
  onNavigateToCare: () => void;
  videoRef?: React.RefObject<HTMLVideoElement | null>;
  isLiveVideo?: boolean;
  isBaseline?: boolean;
  comparisonUnavailable?: boolean;
  comparisonReasons?: ('legacy-quality-missing'|'capture-conditions-incompatible')[];
  baselineTimestamp?: string;
  baselineId?: string;
  comparisonScope?: 'single-front-v1' | 'three-angle-v2';
}

export const SkinResultView: React.FC<SkinResultViewProps> = ({
  currentRegion, snapshot,
  onPrev,
  onNext,
  onOpenModal,
  onNavigateToCare,
  videoRef,
  isLiveVideo = false,
  isBaseline, comparisonUnavailable, comparisonReasons, baselineTimestamp, baselineId, comparisonScope = 'single-front-v1'
}) => {
  const [selection,setSelection]=React.useState<{region:string;criterion:string}|null>(null);
  React.useEffect(()=>setSelection(null),[currentRegion.id,snapshot?.photoId]);
  const selectedCriterion=selection?.region===currentRegion.id?selection.criterion:null;
  const selectCriterion=(criterion:string)=>setSelection(selectedCriterion===criterion?null:{region:currentRegion.id,criterion});
  return (
    <div className="bg-[#0c1424]/90 border border-slate-800/90 rounded-3xl p-5 sm:p-7 shadow-2xl space-y-5 w-full">
      {/* Üst Bilgi Satırı: Başlık, Dinamik Özet Cümlesi, Yasal Rozet */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/70 pb-4">
        <div className="space-y-1">
          <h1 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">
            Cilt Analizi Tamamlandı
          </h1>
          <p className="text-xs sm:text-sm text-slate-300">
            {currentRegion.indicators ? 'Bölge ve kriter seçerek fotoğrafınızdaki görünümü inceleyin.' : isBaseline ? 'Referans oluşturuldu; sonraki uygun taramalar bununla karşılaştırılacak.' :
              comparisonUnavailable ? 'Karşılaştırılamadı. Referansınız korundu.' :
              `${currentRegion.nameTr}: kızarıklık piksel göstergesinde referansa göre ${currentRegion.changePct > 0 ? '+' : ''}${currentRegion.changePct}% değişim.`}
          </p>
          <InformationButton title="Referans ve görüntü"><ul className="list-disc pl-5 space-y-3 text-base leading-relaxed">
            <li>Skorlar fotoğraftaki görünümün 0–100 ölçeğindeki göstergeleridir; hastalık olasılığı veya klinik şiddet yüzdesi değildir.</li>
            <li>Işık, gölge, sakal ve görüntü netliği değerlendirmeyi etkileyebilir. Yeterli görüntü alınamayan değerler — ile gösterilir.</li>
            <li>Parlama, pullanma ve sivilce adayları fotoğraftaki görünüm üzerinden değerlendirilir.</li>
            <li>Renkli alanlar seçtiğiniz bölge ve kriterin görüntüdeki dağılımını gösterir.</li>
            <li>T-bölgesi alın ve burunu kapsar.</li>
            <li>Kontur göstergelerinde görüntüde izlenen katlanma ve sınır çizgileri gösterilir.</li>
          </ul></InformationButton>
        </div>

        <div>
          <span className="text-[11px] bg-slate-900/80 border border-slate-700/80 text-slate-400 px-3 py-1 rounded-full font-medium whitespace-nowrap">
            Ön değerlendirme • Tanı değildir
          </span>
        </div>
      </div>

      {/* İKİ KOLON ANA DÜZEN (FIRST VIEWPORT ONLY - NO PAGE SCROLL) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start" data-skin-result-layout>
        {/* SOL KOLON (~45%): Yüz Portresi + Karusel Okları + Organik Maske Vurgusu + İndikatör */}
        <div className="lg:col-span-5 min-w-0 flex flex-col items-center">
          <SkinFacePanel
            currentRegion={currentRegion}
            snapshot={snapshot}
            mode="result"
            onPrev={onPrev}
            onNext={onNext}
            videoRef={videoRef}
            isLiveVideo={isLiveVideo}
            selectedCriterion={selectedCriterion}
          />
        </div>

        {/* SAĞ KOLON (~55%): Bölge Başlığı + 4 Metrik Çubuğu + 3 İkincil Buton + Ana CTA */}
        <div className="lg:col-span-7 min-w-0">
          <SkinRegionSummary
            currentRegion={currentRegion}
            onOpenModal={onOpenModal}
            onNavigateToCare={onNavigateToCare}
            selectedCriterion={selectedCriterion}
            onSelectCriterion={selectCriterion}
          />
        </div>
      </div>
    </div>
  );
};
