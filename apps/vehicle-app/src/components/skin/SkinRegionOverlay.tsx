'use client';
import {useTranslations} from '../../i18n/LanguageProvider';


import React from 'react';
import { SkinRegionData } from '../../data/skinDemoFixture';

interface SkinRegionOverlayProps {
  region: SkinRegionData;
  mode?: 'result' | 'scan' | 'start';
  scanProgress?: number;
}

export const SkinRegionOverlay: React.FC<SkinRegionOverlayProps> = ({
  region,
  mode = 'result',
  scanProgress = 75
}) => {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const isAmber = region.isAttentionRequired;
  const primaryColor = isAmber ? '#F59E0B' : '#00e5ff';
  const secondaryColor = isAmber ? '#D97706' : '#00b4d8';

  return (
    <svg
      viewBox="0 0 100 100"
      className="absolute inset-0 w-full h-full pointer-events-none"
      preserveAspectRatio="none"
    >
      <defs>
        {/* Anatomik Gauss Feathering Filtresi - userSpaceOnUse ile 100x100 viewBox'ta cilde pürüzsüzce erir */}
        <filter
          id="anatomicalFeather"
          filterUnits="userSpaceOnUse"
          x="0"
          y="0"
          width="100"
          height="100"
        >
          <feGaussianBlur
            in="SourceGraphic"
            stdDeviation={region.id === 'periorbital' ? '1.6' : '2.0'}
          />
        </filter>

        {/* Eterik İnce Rim Yumuşatma Filtresi - userSpaceOnUse ile 0.7 birim blur */}
        <filter
          id="softRimFeather"
          filterUnits="userSpaceOnUse"
          x="0"
          y="0"
          width="100"
          height="100"
        >
          <feGaussianBlur in="SourceGraphic" stdDeviation="0.7" />
        </filter>

        {/* Scan Modu Lazer Işıma Filtresi */}
        <filter id="laserGlow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="1.0" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        {/* Bölgeye Özel Radial Gradient */}
        <radialGradient
          id="opticalRegionGradient"
          cx={region.gradientCenter?.cx || '50%'}
          cy={region.gradientCenter?.cy || '50%'}
          r={region.gradientCenter?.r || '50%'}
        >
          <stop offset="0%" stopColor={primaryColor} stopOpacity={isAmber ? '0.45' : '0.38'} />
          <stop offset="55%" stopColor={primaryColor} stopOpacity={isAmber ? '0.25' : '0.22'} />
          <stop offset="85%" stopColor={secondaryColor} stopOpacity={isAmber ? '0.08' : '0.06'} />
          <stop offset="100%" stopColor={secondaryColor} stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* ========================================================== */}
      {/* 1. START MODU: HİZALAMA OVALİ & DİKEY EKSEN                  */}
      {/* ========================================================== */}
      {mode === 'start' && (
        <g>
          {/* İnce Turkuaz Hizalama Çerçevesi */}
          <ellipse
            cx="50"
            cy="44"
            rx="27"
            ry="33"
            fill="none"
            stroke="#00e5ff"
            strokeWidth="1.0"
            strokeOpacity="0.70"
            strokeDasharray="2 1.5"
            filter="url(#laserGlow)"
          />
          {/* Dikey Merkez Kılavuz Çizgisi */}
          <line
            x1="50"
            y1="11"
            x2="50"
            y2="77"
            stroke="#00e5ff"
            strokeWidth="0.8"
            strokeOpacity="0.45"
          />
        </g>
      )}

      {/* ========================================================== */}
      {/* 2. SCAN MODU: BİYOMETRİK MESH + LAZER SCAN ÇİZGİSİ          */}
      {/* ========================================================== */}
      {mode === 'scan' && (
        <g>
          {/* İnce Landmark Konstelasyon Ağı */}
          <g stroke="#00e5ff" strokeWidth="0.28" opacity="0.45" strokeDasharray="1 1">
            <line x1="33" y1="24" x2="42" y2="22" />
            <line x1="42" y1="22" x2="50" y2="21" />
            <line x1="50" y1="21" x2="58" y2="22" />
            <line x1="58" y1="22" x2="67" y2="24" />
            <line x1="50" y1="21" x2="50" y2="46" />
            <line x1="36" y1="33" x2="45" y2="34" />
            <line x1="45" y1="34" x2="50" y2="36" />
            <line x1="50" y1="36" x2="55" y2="34" />
            <line x1="55" y1="34" x2="64" y2="33" />
            <line x1="35" y1="44" x2="44" y2="45" />
            <line x1="44" y1="45" x2="50" y2="47" />
            <line x1="50" y1="47" x2="56" y2="45" />
            <line x1="56" y1="45" x2="65" y2="44" />
            <line x1="42" y1="62" x2="50" y2="63" />
            <line x1="50" y1="63" x2="58" y2="62" />
          </g>

          {/* Düğümler */}
          <circle cx="50" cy="21" r="0.75" fill="#00e5ff" opacity="0.9" />
          <circle cx="42" cy="22" r="0.65" fill="#00e5ff" opacity="0.8" />
          <circle cx="58" cy="22" r="0.65" fill="#00e5ff" opacity="0.8" />
          <circle cx="36" cy="33" r="0.65" fill="#00e5ff" opacity="0.8" />
          <circle cx="64" cy="33" r="0.65" fill="#00e5ff" opacity="0.8" />
          <circle cx="50" cy="36" r="0.75" fill="#00e5ff" opacity="0.9" />
          <circle cx="35" cy="44" r="0.65" fill="#00e5ff" opacity="0.8" />
          <circle cx="65" cy="44" r="0.65" fill="#00e5ff" opacity="0.8" />
          <circle cx="50" cy="47" r="0.75" fill="#00e5ff" opacity="0.9" />
          <circle cx="50" cy="63" r="0.75" fill="#00e5ff" opacity="0.9" />

          {/* Animasyonlu Lazer Tarama Işını */}
          <line
            x1="0"
            y1={scanProgress < 100 ? 20 + (scanProgress * 0.5) : 50}
            x2="100"
            y2={scanProgress < 100 ? 20 + (scanProgress * 0.5) : 50}
            stroke="#00e5ff"
            strokeWidth="1.2"
            strokeOpacity="0.9"
            filter="url(#laserGlow)"
          />
        </g>
      )}

      {/* ========================================================== */}
      {/* 3. RESULT MODU: OPTİK DERMATOLOJİK FEATHERED OVERLAY (v3)   */}
      {/* ========================================================== */}
      {mode === 'result' && (
        <g className="transition-opacity duration-300 ease-out">
          {region.svgPaths.map((pathData, idx) => (
            <g key={idx}>
              {/* Katman 1: Ana Anatomik Gauss Feathering (stdDev 1.6-2.0) */}
              <path
                d={pathData}
                fill="url(#opticalRegionGradient)"
                stroke="none"
                filter="url(#anatomicalFeather)"
              />

              {/* Katman 2: Yumuşak Bulanıklaştırılmış Eterik Rim (0.5px, %28-32 Opaklık, stdDev 0.7) */}
              <path
                d={pathData}
                fill="none"
                stroke={primaryColor}
                strokeWidth="0.5"
                strokeOpacity={isAmber ? '0.32' : '0.28'}
                strokeLinejoin="round"
                strokeLinecap="round"
                filter="url(#softRimFeather)"
              />
            </g>
          ))}
        </g>
      )}

      {/* Köşe Vizör Parantezleri [   ] */}
      <g stroke="#00e5ff" strokeWidth="1.2" strokeOpacity="0.8" fill="none">
        <path d="M 6 12 L 6 6 L 12 6" />
        <path d="M 88 6 L 94 6 L 94 12" />
        <path d="M 6 88 L 6 94 L 12 94" />
        <path d="M 88 94 L 94 94 L 94 88" />
      </g>
    </svg>
  );
};
