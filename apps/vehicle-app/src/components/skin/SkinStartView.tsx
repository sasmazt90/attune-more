'use client';

import React from 'react';
import { Eye, Sun, Scan } from 'lucide-react';
import { getRegionData } from '../../data/skinDemoFixture';
import { SkinFacePanel } from './SkinFacePanel';

interface SkinStartViewProps {
  onStart: () => void;
}

export const SkinStartView: React.FC<SkinStartViewProps> = ({ onStart }) => {
  const defaultRegion = getRegionData('forehead');

  return (
    <div className="bg-[#0c1424]/90 border border-slate-800/90 rounded-3xl p-6 md:p-8 shadow-2xl w-full">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Sol Kolon: Büyük Yüz Önizleme + İnce Hizalama Konturu */}
        <div className="lg:col-span-6 flex justify-center">
          <SkinFacePanel
            currentRegion={defaultRegion}
            mode="start"
          />
        </div>

        {/* Sağ Kolon: Sade Başlık, Kılavuz Maddeleri ve Başlat CTA */}
        <div className="lg:col-span-6 space-y-6 max-w-md">
          <div className="space-y-1.5">
            <h1 className="text-3xl font-extrabold text-white tracking-tight">
              Cilt Analizi
            </h1>
            <p className="text-sm text-slate-300 leading-relaxed">
              Gözlüğünüzü çıkarın. Kameraya doğru bakın ve başınızı sabit tutun.
            </p>
          </div>

          {/* 3 Sade Rehber Maddesi */}
          <div className="space-y-3.5 pt-1">
            <div className="flex items-center gap-3 text-sm text-slate-200">
              <div className="w-8 h-8 rounded-full bg-togg-turquoise/15 border border-togg-turquoise/30 flex items-center justify-center text-togg-turquoise shrink-0">
                <Eye className="w-4 h-4" />
              </div>
              <span>Yüz hizasını koruyun</span>
            </div>

            <div className="flex items-center gap-3 text-sm text-slate-200">
              <div className="w-8 h-8 rounded-full bg-togg-turquoise/15 border border-togg-turquoise/30 flex items-center justify-center text-togg-turquoise shrink-0">
                <Sun className="w-4 h-4" />
              </div>
              <span>İyi ışık koşulu sağlayın</span>
            </div>

            <div className="flex items-center gap-3 text-sm text-slate-200">
              <div className="w-8 h-8 rounded-full bg-togg-turquoise/15 border border-togg-turquoise/30 flex items-center justify-center text-togg-turquoise shrink-0">
                <Scan className="w-4 h-4" />
              </div>
              <span>Net görüntü elde edin</span>
            </div>
          </div>

          {/* Parlak Turkuaz CTA Butonu */}
          <div className="pt-2">
            <button
              onClick={onStart}
              className="w-full sm:w-auto px-10 py-3.5 rounded-full bg-[#00d2eb] hover:bg-[#00e5ff] text-slate-950 font-bold text-base shadow-[0_0_25px_rgba(0,210,235,0.4)] hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer uppercase tracking-wider"
            >
              Analizi Başlat
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
