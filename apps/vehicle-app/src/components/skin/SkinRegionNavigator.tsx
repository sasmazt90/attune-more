'use client';

import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { SkinRegionData, REGION_ORDER } from '../../data/skinDemoFixture';

interface SkinRegionNavigatorProps {
  currentRegion: SkinRegionData;
  onPrev: () => void;
  onNext: () => void;
  total?: number;
}

export const SkinRegionNavigator: React.FC<SkinRegionNavigatorProps> = ({
  currentRegion,
  onPrev,
  onNext, total = currentRegion.viewTotal || REGION_ORDER.length
}) => {
  return (
    <div className="flex items-center justify-center gap-5 select-none mt-4" data-skin-navigation>
      <button onClick={onPrev} aria-label="Önceki Bölge" className="min-w-11 min-h-11 rounded-full border border-togg-turquoise/50 text-togg-turquoise flex items-center justify-center"><ChevronLeft className="w-5 h-5"/></button>
      <span className="text-xs font-mono text-slate-400">{currentRegion.index} / {total}</span>
      <button onClick={onNext} aria-label="Sonraki Bölge" className="min-w-11 min-h-11 rounded-full border border-togg-turquoise/50 text-togg-turquoise flex items-center justify-center"><ChevronRight className="w-5 h-5"/></button>
    </div>
  );
};

export const NavigationArrows: React.FC<{
  onPrev: () => void;
  onNext: () => void;
}> = ({ onPrev, onNext }) => {
  return (
    <>
      {/* Sol Ok Butonu (<) */}
      <button
        onClick={onPrev}
        aria-label="Önceki Bölge"
        className="absolute left-2.5 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-slate-950/80 border border-togg-turquoise/50 text-togg-turquoise flex items-center justify-center hover:bg-slate-900 hover:border-togg-turquoise hover:scale-105 active:scale-95 transition-all shadow-lg cursor-pointer z-20"
      >
        <ChevronLeft className="w-5 h-5" />
      </button>

      {/* Sağ Ok Butonu (>) */}
      <button
        onClick={onNext}
        aria-label="Sonraki Bölge"
        className="absolute right-2.5 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-slate-950/80 border border-togg-turquoise/50 text-togg-turquoise flex items-center justify-center hover:bg-slate-900 hover:border-togg-turquoise hover:scale-105 active:scale-95 transition-all shadow-lg cursor-pointer z-20"
      >
        <ChevronRight className="w-5 h-5" />
      </button>
    </>
  );
};
