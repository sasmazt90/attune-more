'use client';

import {useTranslations} from '../../i18n/LanguageProvider';
import type { SkinIndicator } from '../../utils/skinIndicators';
import { appearanceColor, skinDisplayKind, SKIN_DISPLAY_DIRECTION } from '../../utils/skinPresentation';
import { ResultValue } from '../ResultValue';

export function SkinIndicatorValue({ indicator, bar = true }: { indicator: SkinIndicator; bar?: boolean }) {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const kind = skinDisplayKind(indicator), baseline = indicator.appearance?.limitationCode === 'REFERENCE_CREATED';
  const limitation = indicator.appearance?.limitationCode || indicator.measurement?.unavailableReason;
  const value = indicator.score;
  if (value === null || !Number.isFinite(value) || baseline) {
    if (limitation && ['CAPTURE_QUALITY', 'GLARE_OR_EXPOSURE', 'INSUFFICIENT_SUPPORT', 'INSUFFICIENT_VALID_PIXELS', 'INCOMPLETE_CHEEKS_UNVERIFIED'].includes(limitation)) {
      return <span className="text-sm font-semibold text-amber-300/80">{i18nText("Ölçülemedi")}</span>;
    }
    return <span className="text-xl font-bold text-slate-300">—</span>;
  }
  if (kind !== 'percent') return <ResultValue value={kind === 'contour' ? value * 1000 : value} unit={kind === 'contour' ? '× 10⁻³ kontur oranı' : kind === 'count' ? 'aday' : indicator.unit} />;
  const percent = Math.max(0, Math.min(100, value)), direction = SKIN_DISPLAY_DIRECTION[indicator.id] || 'neutral';
  const gradient = direction === 'positive' ? 'linear-gradient(to right,#f84b55 0%,#fb923c 50%,#34d399 100%)' : 'linear-gradient(to right,#34d399 0%,#fb923c 50%,#f84b55 100%)';
  return <div className="space-y-3" data-skin-percentage>
    <ResultValue value={value} format="percent" color={appearanceColor(percent, direction)} />
    {bar && <div className="h-2 rounded-full bg-slate-800 overflow-hidden" role="meter" aria-label={i18nText(indicator.label)} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-valuetext={i18nText(`${Math.round(percent)}%`)}>
      <div className="h-full rounded-full" style={{ width: `${percent}%`, backgroundImage: gradient, backgroundSize: `${percent ? 10000 / percent : 100}% 100%`, backgroundRepeat: 'no-repeat' }} />
    </div>}
  </div>;
}
