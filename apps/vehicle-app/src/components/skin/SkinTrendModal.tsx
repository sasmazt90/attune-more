'use client';

import { AccessibleDialog } from '../AccessibleDialog';
import React, { useEffect, useMemo, useState } from 'react';
import { TrendingUp, X, Info } from 'lucide-react';
import { SkinRegionData, RegionTrendPoint } from '../../data/skinDemoFixture';
import { isDemoMode } from '../../utils/attuneMode';
import { prepareHealthRecords, type HealthRecord } from '../../utils/healthRecords';
import { buildHistorySeries } from '../../utils/healthHistorySeries';
import { HistoryChart } from '../HealthHistoryOverview';

interface SkinTrendModalProps {
  region: SkinRegionData;
  onClose: () => void;
  analysisId?:string;
  selectedCriterion?:string|null;
}

export const SkinTrendModal: React.FC<SkinTrendModalProps> = ({ region, onClose, analysisId, selectedCriterion }) => {
  const isDemo = isDemoMode();
  const [records,setRecords]=useState<HealthRecord[]>([]),[readError,setReadError]=useState(false);
  const [criterionChoice,setCriterionChoice]=useState(selectedCriterion||''),[seriesChoice,setSeriesChoice]=useState('');
  useEffect(()=>{if(isDemo)return;let current=true,ticket=0;const refresh=()=>{const revision=++ticket;void prepareHealthRecords('skin').then(rows=>{if(current&&revision===ticket){setRecords(rows);setReadError(false);}}).catch(()=>{if(current&&revision===ticket)setReadError(true);});};refresh();window.addEventListener('attune-records',refresh);window.addEventListener('storage',refresh);return()=>{current=false;window.removeEventListener('attune-records',refresh);window.removeEventListener('storage',refresh);};},[isDemo]);
  const liveSeries=useMemo(()=>buildHistorySeries('skin',records).filter(s=>s.region===region.id),[records,region.id]);
  const criteria=[...new Map(liveSeries.map(s=>[s.criterion,{id:s.criterion,label:s.label}])).values()];
  const criterion=criteria.some(c=>c.id===criterionChoice)?criterionChoice:criteria[0]?.id||'';
  const comparable=liveSeries.filter(s=>s.criterion===criterion);
  const selected=comparable.find(s=>s.id===seriesChoice)||comparable.find(s=>s.points.some(p=>p.recordId===analysisId&&p.value!==null))||[...comparable].sort((a,b)=>Math.max(0,...b.points.filter(p=>p.value!==null).map(p=>p.time))-Math.max(0,...a.points.filter(p=>p.value!==null).map(p=>p.time)))[0];

  const trendPoints:RegionTrendPoint[]=useMemo(()=>isDemo?region.trend:[],[isDemo,region.trend]);

  const hasEnoughPoints = trendPoints.length >= 2;

  // Chart dimensions
  const width = 480;
  const height = 180;
  const padX = 50;
  const padY = 30;

  // Y scale: -20% to +40% (total range 60%)
  const minY = Math.min(-20, ...trendPoints.map(point => point.value));
  const maxY = Math.max(40, ...trendPoints.map(point => point.value));
  const getY = (val: number) => {
    const norm = (val - minY) / (maxY - minY);
    return height - padY - norm * (height - 2 * padY);
  };

  const getX = (index: number) => {
    if (trendPoints.length <= 1) return width / 2;
    return padX + (index / (trendPoints.length - 1)) * (width - 2 * padX);
  };

  const pointsStr = hasEnoughPoints
    ? trendPoints.map((p, i) => `${getX(i)},${getY(p.value)}`).join(' ')
    : '';

  const areaStr = hasEnoughPoints
    ? `${pointsStr} ${getX(trendPoints.length - 1)},${height - padY} ${getX(0)},${height - padY}`
    : '';

  if(!isDemo)return <AccessibleDialog title="Zaman İçinde Değişim" onClose={onClose} className="relative w-full max-w-xl bg-[#0B1526] border border-slate-700/80 rounded-2xl p-6 sm:p-7 shadow-2xl space-y-6">
    <div className="flex items-start justify-between gap-3"><div className="flex items-center gap-3"><div className="w-10 h-10 shrink-0 rounded-xl bg-togg-turquoise/10 border border-togg-turquoise/30 flex items-center justify-center text-togg-turquoise"><TrendingUp className="w-5 h-5"/></div><div><h3 className="text-lg font-bold text-white tracking-wide">Zaman İçinde Değişim</h3><p className="text-xs text-slate-400 mt-0.5">{region.nameTr}</p></div></div><button onClick={onClose} aria-label="Pencereyi kapat" className="w-11 h-11 shrink-0 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800/80"><X className="w-5 h-5"/></button></div>
    <div className="grid gap-3 sm:grid-cols-2">{criteria.length>0&&<label className="space-y-1 text-xs text-slate-400">Ölçüm<select value={criterion} onChange={e=>{setCriterionChoice(e.target.value);setSeriesChoice('');}} className="min-h-11 w-full min-w-0 rounded-xl border border-white/20 bg-slate-950 px-3 text-sm text-white">{criteria.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></label>}{comparable.length>1&&<label className="space-y-1 text-xs text-slate-400">Karşılaştırılabilir seri<select value={selected?.id||''} onChange={e=>setSeriesChoice(e.target.value)} className="min-h-11 w-full min-w-0 rounded-xl border border-white/20 bg-slate-950 px-3 text-sm text-white">{comparable.map((s,i)=><option key={s.id} value={s.id}>Seri {i+1} · {new Date(s.points.find(p=>p.value!==null)?.time||s.points[0].time).toLocaleDateString('tr-TR')}</option>)}</select></label>}</div>
    <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-4 sm:p-5 min-h-[200px]">{readError?<p role="alert" className="py-8 text-center text-sm text-amber-200">Kayıtlar açılamadı; mevcut veriler korunuyor.</p>:selected?<HistoryChart key={JSON.stringify([selected.id,selected.points])} series={selected} kind="line"/>:<p className="py-8 text-center text-sm text-slate-400">Bu görünüm için kayıtlı karşılaştırılabilir ölçüm yok.</p>}</div>
    <details className="text-xs text-slate-400"><summary className="cursor-pointer">Kayıtların karşılaştırılması hakkında bilgi</summary><p className="mt-2">Yalnız kayıtlı ölçümler gösterilir. Farklı yöntemler ve birimler ayrı serilerde tutulur; eksik ölçümler çizgiyi keser.</p></details>
  </AccessibleDialog>;

  return (
    <AccessibleDialog title="Zaman İçinde Değişim" onClose={onClose} className="relative w-full max-w-xl bg-[#0B1526] border border-slate-700/80 rounded-2xl p-6 sm:p-7 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-togg-turquoise/10 border border-togg-turquoise/30 flex items-center justify-center text-togg-turquoise">
              <TrendingUp className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white tracking-wide">Zaman İçinde Değişim</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {region.nameTr} bölgesindeki görsel değişim {isDemo ? '(Demo Geçmiş)' : '(Gerçek Ölçümler)'}
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

        {/* Chart Container */}
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-4 sm:p-5 relative min-h-[200px] flex items-center justify-center">
          {hasEnoughPoints ? (
            <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible">
              <defs>
                <linearGradient id="trendAreaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#F59E0B" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#F59E0B" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Y Guide Lines and Labels */}
              {[maxY, maxY / 2, 0, minY].map((level) => {
                const y = getY(level);
                return (
                  <g key={level}>
                    <line
                      x1={padX - 10}
                      y1={y}
                      x2={width - padX + 10}
                      y2={y}
                      stroke="rgba(148, 163, 184, 0.15)"
                      strokeDasharray={level === 0 ? 'none' : '3 3'}
                      strokeWidth={level === 0 ? '1.2' : '0.8'}
                    />
                    <text
                      x={padX - 16}
                      y={y + 4}
                      textAnchor="end"
                      className="text-[10px] fill-slate-500 font-mono"
                    >
                      {level > 0 ? `+${level}%` : `${level}%`}
                    </text>
                  </g>
                );
              })}

              {/* Area Fill */}
              <polygon points={areaStr} fill="url(#trendAreaGradient)" />

              {/* Trend Polyline */}
              <polyline
                points={pointsStr}
                fill="none"
                stroke="#F59E0B"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Data Points */}
              {trendPoints.map((p, i) => {
                const cx = getX(i);
                const cy = getY(p.value);
                const isLast = i === trendPoints.length - 1;

                return (
                  <g key={i}>
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isLast ? '5' : '4'}
                      fill="#F59E0B"
                      stroke="#0B1526"
                      strokeWidth="2"
                    />
                    {/* Badge on latest or above */}
                    {isLast ? (
                      <g transform={`translate(${cx - 20}, ${cy - 28})`}>
                        <rect
                          width="40"
                          height="20"
                          rx="6"
                          fill="#F59E0B"
                          className="shadow-md"
                        />
                        <text
                          x="20"
                          y="14"
                          textAnchor="middle"
                          className="text-[11px] font-bold fill-slate-950 font-mono"
                        >
                          {p.value > 0 ? `+${p.value}%` : `${p.value}%`}
                        </text>
                      </g>
                    ) : (
                      <text
                        x={cx}
                        y={cy - 10}
                        textAnchor="middle"
                        className="text-[10px] font-mono fill-slate-300 font-semibold"
                      >
                        {p.value > 0 ? `+${p.value}%` : `${p.value}%`}
                      </text>
                    )}
                    {/* X Axis Date Label */}
                    <text
                      x={cx}
                      y={height - 8}
                      textAnchor="middle"
                      className="text-[11px] fill-slate-400 font-medium"
                    >
                      {p.date}
                    </text>
                  </g>
                );
              })}
            </svg>
          ) : (
            <div className="py-8 text-center space-y-2">
              <Info className="w-7 h-7 text-slate-500 mx-auto" />
              <p className="text-xs text-slate-300 font-medium">
                Henüz yeterli geçmiş ölçüm yok.
              </p>
              <p className="text-[11px] text-slate-500 max-w-xs mx-auto">
                Zaman içindeki görsel değişim grafiğini görüntüleyebilmek için en az 2 karşılaştırılabilir takip taraması gereklidir.
              </p>
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="flex items-center justify-between text-xs text-slate-400 border-t border-slate-800/80 pt-4">
          <span>{isDemo ? 'Referans baz: 17 Eylül 2026' : 'İlk Ölçüm: Referans Baz Çizgisi'}</span>
          <span className="text-amber-400 font-medium">İzleme sıklığı: Periyodik</span>
        </div>
    </AccessibleDialog>
  );
};
