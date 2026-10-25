'use client';
import {useTranslations} from '../../i18n/LanguageProvider';

import React from 'react';
import { SkinIndicatorValue } from './SkinIndicatorValue';
import { TrendingUp, FileText, Lightbulb, ArrowRight } from 'lucide-react';
import { SkinRegionData } from '../../data/skinDemoFixture';
import { SKIN_TYPE_LABELS, skinTypeLabel } from '../../utils/skinOverview';
import { isCriterionApplicableToRegion } from '../../utils/skinIndicators';
import { PAINT_LABELS, PAINT_REGION_NAMES, paintKey, paintKeyColor, type PaintState } from '../../utils/skinTypePaint';
import { SkinInconclusiveDialog } from './SkinInconclusiveDialog';

interface SkinRegionSummaryProps {
  currentRegion: SkinRegionData;
  onOpenModal: (modal: 'trend' | 'observation' | 'actions') => void;
  onNavigateToCare: () => void;
  selectedCriterion?:string|null;
  onSelectCriterion?:(criterion:string)=>void;
}

export function criterionModelBadge(
  id: string,
  methodVersion?: string | null,
  modelVersion?: string | null,
  regionId?: string
): { code: string; label: string } {
  const m = methodVersion || '';
  if (id === 'acne') {
    if (m.startsWith('appearance-acne-step0-verifier-v5')) {
      return { code: 'local-onnx-acne-v5', label: 'Yerel ONNX: acne-v5-step0-silu + logreg' };
    }
    return { code: 'local-acne-inactive', label: 'Yerel model: acne-v5 (devre dışı)' };
  }
  if (id === 'dry') {
    if (m.startsWith('appearance-native-dry')) {
      return { code: 'local-onnx-dryness-v3', label: 'Yerel ONNX: dryness-calibrated-v3' };
    }
    return { code: 'local-cv-dry', label: 'Yerel Analitik: appearance-cv-6' };
  }
  if (id === 'redness') {
    if (regionId === 'overview' || (modelVersion && modelVersion.includes('ridge'))) {
      return { code: 'local-onnx-degrees-redness', label: 'Yerel ONNX: skin-focused-degrees + LAB a*' };
    }
    return { code: 'local-cv-redness', label: 'Yerel Analitik: LAB a* (appearance-cv-6)' };
  }
  if (id === 'oil') return { code: 'local-cv-oil', label: 'Yerel Analitik: parlama alanı (appearance-cv-6)' };
  if (id === 'lines') return { code: 'local-cv-lines', label: 'Yerel Analitik: sırt iskeleti (appearance-cv-6)' };
  if (id === 'bags') return { code: 'local-cv-bags', label: 'Yerel Analitik: alt kapak konturu (appearance-cv-6)' };
  if (id === 'dark') return { code: 'local-cv-dark', label: 'Yerel Analitik: periorbital renk (appearance-cv-6)' };
  if (id === 'sag') return { code: 'local-cv-sag', label: 'Yerel Analitik: 3B kontur oranı (appearance-cv-6)' };
  if (id === 'tone') return { code: 'local-cv-tone', label: 'Yerel Analitik: kromatik dağılım (appearance-cv-6)' };
  return { code: m || 'local-cv', label: 'Yerel Analitik: appearance-cv-6' };
}

export const SkinRegionSummary: React.FC<SkinRegionSummaryProps> = ({
  currentRegion,
  onOpenModal,
  onNavigateToCare,selectedCriterion,onSelectCriterion
}) => {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const [inconclusive, setInconclusive] = React.useState<{ regionId: string; reason?: string | null } | null>(null);
  const regional = (currentRegion.skinType as any)?.decisionTrace?.regions as Record<string, any> | undefined;
  const { metrics } = currentRegion;
  const visibleIndicators = React.useMemo(
    () => currentRegion.indicators?.filter(ind => isCriterionApplicableToRegion(ind.id, currentRegion.id)),
    [currentRegion.indicators, currentRegion.id]
  );

  const skinTypeDisplay = skinTypeLabel(currentRegion.skinType as any)
    ? skinTypeLabel(currentRegion.skinType as any)!
    : (currentRegion.skinType as any)?.displayValue
      ? i18nText((currentRegion.skinType as any).displayValue)
      : currentRegion.skinType?.limitationCode === 'INCOMPLETE_CHEEKS_UNVERIFIED'
        ? i18nText('Belirsiz (Yanak verisi eksik)')
        : currentRegion.skinType?.limitationCode === 'INCOMPLETE_TZONE_UNVERIFIED'
          ? i18nText('Belirsiz (T-bölgesi verisi eksik)')
          : currentRegion.skinType?.limitationCode === 'INTERMEDIATE_BAND_UNDETERMINED'
            ? i18nText('Belirlenemedi (Ara sinyal bandı)')
            : currentRegion.skinType?.limitationCode === 'NEGATIVE_EVIDENCE_METHOD_NOT_ACCEPTED'
              ? i18nText('Değerlendirilmedi')
              : currentRegion.skinType?.limitationCode === 'MIXED_REGIONAL_PATTERN_UNDETERMINED'
                ? i18nText('Karışık desen (Belirlenemedi)')
                : '—';

  return (
    <div className="space-y-5 w-full">
      {/* Bölge Başlığı ve Rozet */}
      <div className="space-y-3.5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-white tracking-wide">
            {i18nNode(currentRegion.nameTr)}
          </h3>
        </div>

        {currentRegion.id === 'overview' && (
          <div className="rounded-2xl border border-sky-400/15 bg-slate-900/60 p-4 space-y-1.5" data-skin-type data-skin-type-limitation={currentRegion.skinType?.limitationCode || undefined}>
            <div className="flex flex-wrap justify-between gap-2">
              <span className="text-sm text-slate-300">{i18nText("Cilt tipi")}</span>
              <strong className="text-base text-white">{i18nNode(skinTypeDisplay)}</strong>
            </div>
            {regional && (
              <ul className="pt-2 space-y-1" data-skin-type-regions>
                {(['forehead', 'nose', 'chin', 'rightCheek', 'leftCheek'] as const).filter(id => regional[id]).map(id => {
                  const e = regional[id]; const st: PaintState = ['oily', 'dry', 'normal'].includes(e.state) ? e.state : 'unmeasured';
                  const sens = st !== 'unmeasured' && e.sensitive === true; const color = paintKeyColor(paintKey(st, sens));
                  const label = i18nText(PAINT_LABELS[st]) + (sens ? ' · ' + i18nText('Hassas') : '');
                  return (
                    <li key={id} className="flex items-center justify-between gap-2 text-sm" data-skin-type-region-row={id} data-state={st}>
                      <span className="flex items-center gap-2 text-slate-300"><span aria-hidden="true" className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: color }} />{i18nNode(PAINT_REGION_NAMES[id])}</span>
                      {st === 'unmeasured'
                        ? <button type="button" onClick={() => setInconclusive({ regionId: id, reason: e.reason })} aria-haspopup="dialog" className="inline-flex min-h-11 items-center gap-2 text-slate-300 underline-offset-2 hover:underline">
                            {label}<span aria-hidden="true" className="inline-flex w-6 h-6 items-center justify-center rounded-full border border-white/20 text-togg-turquoise">ⓘ</span>
                          </button>
                        : <span className="text-white">{label}</span>}
                    </li>
                  );
                })}
              </ul>
            )}
            {inconclusive && <SkinInconclusiveDialog regionId={inconclusive.regionId} reason={inconclusive.reason} onClose={() => setInconclusive(null)} />}
            <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400 font-mono" data-skin-type-model={currentRegion.skinType?.methodVersion || 'local-vit+regional-v3'}>
              <span>{i18nText(regional ? "Bölgesel cilt haritası (yerel model)" : "Bölgesel Kural + Yerel ONNX (local-vit-dima806)")}</span>
              <span>{i18nText("Model/vekil tahmini · Klinik tanı değildir")}</span>
            </div>
          </div>
        )}
        {/* Current source measurements only. */}
        {visibleIndicators ? <div className="space-y-4" data-skin-indicators>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {visibleIndicators.map(indicator=>{
              const geometry=indicator.appearance?.type==='longitudinal_measurement';
              const delta=indicator.referenceDelta===undefined?undefined:Math.round(indicator.referenceDelta*(geometry?1000:1));
              const modelBadge = criterionModelBadge(
                indicator.id,
                indicator.appearance?.methodVersion || indicator.measurement?.methodVersion || indicator.method,
                indicator.appearance?.modelVersion,
                currentRegion.id
              );
              return <div key={indicator.id} data-skin-indicator={indicator.id} data-criterion-model={modelBadge.code} role={onSelectCriterion?'button':undefined} tabIndex={onSelectCriterion?0:undefined} aria-pressed={onSelectCriterion?selectedCriterion===indicator.id:undefined} onClick={()=>onSelectCriterion?.(indicator.id)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onSelectCriterion?.(indicator.id);}}} className={`rounded-2xl border bg-slate-900/60 p-4 space-y-3 ${selectedCriterion===indicator.id?'border-togg-turquoise ring-1 ring-togg-turquoise/40':'border-sky-400/15'}`}>
                <div className="space-y-1">
                  <div className="text-sm text-slate-300">{i18nNode(indicator.label)}</div>
                  <div className="text-[11px] text-slate-400 font-mono" data-criterion-model-label>{i18nText(modelBadge.label)}</div>
                </div>
                <SkinIndicatorValue indicator={indicator}/>
                {delta!==undefined&&<p className="text-xs text-sky-300">{i18nText("Referansa göre ")}{i18nNode(delta>0?'+':'')}{i18nNode(delta)} {i18nNode(geometry?'× 10⁻³ kontur farkı':indicator.unit)}</p>}
              </div>;
            })}
          </div>
        </div> : <div className="space-y-2.5">
          {/* 1. Kızarıklık Eğilimi */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-medium">
              <span className="text-slate-300">{i18nNode(metrics.redness.label)}</span>
              <span
                className={`font-mono font-bold ${
                  metrics.redness.status === 'amber'
                    ? 'text-amber-400'
                    : 'text-slate-300'
                }`}
              >
                {i18nNode(metrics.redness.displayValue)}
              </span>
            </div>
            <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  metrics.redness.status === 'amber'
                    ? 'bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.5)]'
                    : 'bg-togg-turquoise'
                }`}
                style={{ width: `${metrics.redness.score}%` }}
              />
            </div>
          </div>

          {/* 2. Ton / Parlaklık */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-medium">
              <span className="text-slate-300">{i18nNode(metrics.luminance.label)}</span>
              <span className="text-sky-400 font-semibold font-mono">
                {i18nNode(metrics.luminance.displayValue)}
              </span>
            </div>
            <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
              <div
                className="h-full bg-sky-400 rounded-full transition-all duration-300"
                style={{ width: `${metrics.luminance.score}%` }}
              />
            </div>
          </div>

          {/* 3. Doku Değişimi */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-medium">
              <span className="text-slate-300">{i18nNode(metrics.texture.label)}</span>
              <span className="text-togg-turquoise font-semibold font-mono">
                {i18nNode(metrics.texture.displayValue)}
              </span>
            </div>
            <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
              <div
                className="h-full bg-togg-turquoise rounded-full transition-all duration-300 shadow-[0_0_8px_rgba(0,229,255,0.4)]"
                style={{ width: `${metrics.texture.score}%` }}
              />
            </div>
          </div>

          {/* 4. Referansa Göre Değişim */}
          {/^[-+]?\d/.test(metrics.baselineChange.displayValue) && <div className="space-y-1">
            <div className="flex justify-between text-xs font-medium">
              <span className="text-slate-300">{i18nNode(metrics.baselineChange.label)}</span>
              <span
                className={`font-semibold font-mono ${
                  metrics.baselineChange.status === 'amber'
                    ? 'text-amber-400 font-bold'
                    : 'text-slate-300'
                }`}
              >
                {i18nNode(metrics.baselineChange.displayValue)}
              </span>
            </div>
            <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  metrics.baselineChange.status === 'amber'
                    ? 'bg-amber-400'
                    : 'bg-sky-400'
                }`}
                style={{ width: `${metrics.baselineChange.score}%` }}
              />
            </div>
          </div>}
        </div>}
      </div>

      {/* 3 İkincil Eylem Butonu */}
      <div className="grid grid-cols-3 gap-3 pt-1">
        <button
          onClick={() => onOpenModal('trend')}
          className="bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 hover:border-slate-700 text-slate-200 rounded-2xl p-3 flex flex-col items-center justify-center text-center gap-1.5 transition-all hover:scale-[1.02] active:scale-[0.98] group cursor-pointer"
        >
          <div className="w-8 h-8 rounded-xl bg-togg-turquoise/10 border border-togg-turquoise/20 flex items-center justify-center text-togg-turquoise group-hover:scale-110 transition-transform">
            <TrendingUp className="w-4 h-4" />
          </div>
          <span className="text-xs font-medium text-slate-300 group-hover:text-white leading-tight">{i18nText("Zaman İçinde")}<br />{i18nText("Değişim ")}</span>
        </button>

        <button
          onClick={() => onOpenModal('observation')}
          className="bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 hover:border-slate-700 text-slate-200 rounded-2xl p-3 flex flex-col items-center justify-center text-center gap-1.5 transition-all hover:scale-[1.02] active:scale-[0.98] group cursor-pointer"
        >
          <div className="w-8 h-8 rounded-xl bg-togg-turquoise/10 border border-togg-turquoise/20 flex items-center justify-center text-togg-turquoise group-hover:scale-110 transition-transform">
            <FileText className="w-4 h-4" />
          </div>
          <span className="text-xs font-medium text-slate-300 group-hover:text-white leading-tight">{i18nText("Gözlem Notu ")}</span>
        </button>

        <button
          onClick={() => onOpenModal('actions')}
          className="bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 hover:border-slate-700 text-slate-200 rounded-2xl p-3 flex flex-col items-center justify-center text-center gap-1.5 transition-all hover:scale-[1.02] active:scale-[0.98] group cursor-pointer"
        >
          <div className="w-8 h-8 rounded-xl bg-togg-turquoise/10 border border-togg-turquoise/20 flex items-center justify-center text-togg-turquoise group-hover:scale-110 transition-transform">
            <Lightbulb className="w-4 h-4" />
          </div>
          <span className="text-xs font-medium text-slate-300 group-hover:text-white leading-tight">{i18nText("Önerilen")}<br />{i18nText("Aksiyonlar ")}</span>
        </button>
      </div>

      {/* Büyük Turkuaz Ana CTA Butonu */}
      <div className="pt-1">
        <button
          onClick={onNavigateToCare}
          className="w-full flex items-center justify-center gap-2 py-3.5 px-6 rounded-full bg-[#00d2eb] hover:bg-[#00e5ff] text-slate-950 font-bold text-sm tracking-wide shadow-[0_0_25px_rgba(0,210,235,0.35)] hover:brightness-105 active:scale-[0.99] transition-all cursor-pointer"
        >
          <span>{i18nText("Uzman Seçeneklerini Gör")}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
