'use client';

import React from 'react';
import { CameraPreparation, type CameraResolution } from '../CameraPreparation';
import { getRegionData } from '../../data/skinDemoFixture';
import { SkinFacePanel } from './SkinFacePanel';

import { FaceAlignment, ImageQuality } from '../../utils/skinAnalyzer';

interface SkinActiveScanProps {
  scanProgress: number;
  videoRef?: React.RefObject<HTMLVideoElement | null>;
  isLiveVideo?: boolean;
  alignment?: FaceAlignment;
  quality?: ImageQuality;
  guidanceText?: string;
  multiAngle?: boolean;
  fresh?: boolean;
  resolution?: CameraResolution;
  preparing?:boolean;
}

export const SkinActiveScan: React.FC<SkinActiveScanProps> = ({
  scanProgress,
  videoRef,
  isLiveVideo = false,
  alignment,
  quality,
  guidanceText,
  multiAngle = false,
  fresh = false,
  resolution,
  preparing=false
}) => {
  const defaultRegion = getRegionData('forehead');

  const analyzing=fresh && !!alignment?.isMediaPipeActive && alignment.faceDetected && alignment.isAligned && !!quality?.isValid && scanProgress>0;

  return (
    <div className="bg-[#0c1424]/90 border border-slate-800/90 rounded-3xl p-6 md:p-8 shadow-2xl w-full">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Sol Kolon: Büyük Yüz + Biyometrik Landmark Konstelasyon Ağı + Tarama Işını */}
        <div className="lg:col-span-6 flex justify-center">
          <SkinFacePanel
            currentRegion={defaultRegion}
            mode="scan"
            scanProgress={scanProgress}
            videoRef={videoRef}
            isLiveVideo={isLiveVideo}
            landmarks={alignment?.landmarks}
          />
        </div>

        {/* Sağ Kolon: Analiz Ediliyor, İlerleme Çubuğu ve 3 Kalite Kontrolü */}
        <div className="lg:col-span-6 space-y-6 max-w-md">
          <div className="space-y-1">
            <h2 className="text-3xl font-extrabold text-white tracking-tight">
              {preparing ? 'Portre Hazırlanıyor' : analyzing ? 'Analiz Ediliyor' : 'Kamera Hazırlığı'}
            </h2>
            <p className="text-sm text-slate-300">
              {guidanceText || 'Lütfen başınızı sabit tutun.'}
            </p>
          </div>

          {/* İlerleme Çubuğu */}
          {!preparing && <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-300 font-medium">
              <span>{analyzing ? 'Geçerli kareler değerlendiriliyor' : 'Uygun konum bekleniyor'}</span>
              <span className="font-mono text-togg-turquoise font-bold">%{scanProgress}</span>
            </div>
            <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
              <div
                className="h-full bg-gradient-to-r from-togg-darkTurquoise via-togg-turquoise to-emerald-400 rounded-full transition-all duration-300 shadow-[0_0_12px_#00e5ff]"
                style={{ width: `${scanProgress}%` }}
              />
            </div>
          </div>}

          <CameraPreparation alignment={alignment} quality={quality} fresh={fresh} resolution={resolution} position={fresh && alignment?.isAligned ? 'Konum hazır' : guidanceText || 'Ölçüm bekleniyor'}/>

        </div>
      </div>
    </div>
  );
};
