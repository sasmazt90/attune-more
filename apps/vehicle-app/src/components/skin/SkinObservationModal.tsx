'use client';

import { AccessibleDialog } from '../AccessibleDialog';
import React from 'react';
import { FileText, X, AlertCircle } from 'lucide-react';
import { SkinRegionData } from '../../data/skinDemoFixture';

interface SkinObservationModalProps {
  region: SkinRegionData;
  onClose: () => void;
}

export const SkinObservationModal: React.FC<SkinObservationModalProps> = ({ region, onClose }) => {
  return (
    <AccessibleDialog title="Gözlem Notu" onClose={onClose} className="relative w-full max-w-xl bg-[#0B1526] border border-slate-700/80 rounded-2xl p-6 sm:p-7 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-togg-turquoise/10 border border-togg-turquoise/30 flex items-center justify-center text-togg-turquoise">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white tracking-wide">Gözlem Notu</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {region.nameTr} — Optik Analiz Değerlendirmesi
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Pencereyi kapat"
            className="w-11 h-11 shrink-0 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Observation Content Box */}
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-5 space-y-4">
          <div className="flex items-start gap-3.5">
            <div className="w-8 h-8 rounded-full bg-togg-turquoise/20 border border-togg-turquoise/40 flex items-center justify-center text-togg-turquoise shrink-0 mt-0.5">
              <AlertCircle className="w-4 h-4" />
            </div>
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-white leading-snug">
                {region.observation.headline}
              </h4>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                {region.observation.details}
              </p>
            </div>
          </div>
        </div>

        {/* Disclaimer / Guidance */}
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 text-[11px] text-slate-400 leading-normal">
          <span className="font-semibold text-slate-300">Bilgilendirme: </span>
          Bu değerlendirme, araç içi optik sensör verileriyle hesaplanan görsel değişim eğilimidir; tıbbi tanı veya tedavi tavsiyesi teşkil etmez.
        </div>
    </AccessibleDialog>
  );
};
