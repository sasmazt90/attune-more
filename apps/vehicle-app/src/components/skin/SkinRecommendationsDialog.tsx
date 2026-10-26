'use client';
import { X } from 'lucide-react';
import { useTranslations } from '../../i18n/LanguageProvider';
import { AccessibleDialog } from '../AccessibleDialog';
import { FINDING_DEFS, findingColor, type SkinFinding } from '../../utils/skinFindings';
import { REC_NOTES, recommendationBand } from '../../utils/skinRecommendations';

/** Ingredients and routine for the finding's current score band. Ingredient names only, no brands, no diagnosis. */
export function SkinRecommendationsDialog({ finding, onClose, onExpert }: { finding: SkinFinding; onClose: () => void; onExpert: () => void }) {
  const { text } = useTranslations();
  const def = FINDING_DEFS[finding.id], color = findingColor(finding.id);
  const { band } = recommendationBand(finding);
  const range = band.range ? (def.kind === 'count' ? `${band.range} ${text(def.unit || '')}` : band.range) : '';
  const note = REC_NOTES[finding.id];
  const routine = ([['Sabah', band.morning], ['Akşam', band.evening], ['Kullanım', band.usage], ['Alışkanlık', band.habit]] as [string, string | undefined][])
    .filter((r): r is [string, string] => !!r[1]);
  const title = text(def.label);
  return (
    <AccessibleDialog title={title} onClose={onClose} className="w-full max-w-[720px] max-h-[92vh] overflow-y-auto rounded-[28px] bg-[#0f1724] p-7 flex flex-col gap-5 shadow-2xl">
      <div className="flex items-start justify-between gap-4" data-skin-recommendations={finding.id} data-band={band.range}>
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-bold tracking-[0.08em] uppercase" style={{ color }}>
            {text('Öneriler')}{range && <> · {text(range)}</>}
          </span>
          <h2 className="text-[28px] leading-tight font-extrabold tracking-tight text-white">{title}</h2>
        </div>
        <button type="button" aria-label={text('Kapat')} onClick={onClose} className="w-[52px] h-[52px] shrink-0 rounded-2xl bg-[#1a2533] flex items-center justify-center text-slate-100"><X aria-hidden="true" className="w-5 h-5" /></button>
      </div>
      {note && <p className="text-[15px] leading-relaxed text-slate-300">{text(note)}</p>}
      {band.ingredients.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <span className="text-[15px] font-semibold text-slate-400">{text('Tercih edebileceğiniz içerikler')}</span>
          <ul className="flex flex-wrap gap-2" data-skin-rec-ingredients>
            {band.ingredients.map(i => <li key={i} className="text-base font-semibold text-[#e8e2ff] bg-[#221d3d] px-4 py-2 rounded-full">{text(i)}</li>)}
          </ul>
        </div>
      )}
      <div className={`grid gap-3 ${routine.length >= 3 ? 'sm:grid-cols-3' : routine.length === 2 ? 'sm:grid-cols-2' : ''}`}>
        {routine.map(([label, value]) => (
          <div key={label} className="rounded-[18px] bg-[#131d2b] p-4 flex flex-col gap-1.5">
            <span className="text-sm font-bold text-white">{text(label)}</span>
            <span className="text-[15px] leading-snug text-slate-300">{text(value)}</span>
          </div>
        ))}
      </div>
      <p className="text-sm leading-relaxed text-slate-500">{text('Öneriler fotoğraftaki görünüme dayanır ve tanı değildir. Şikâyetiniz sürerse bir uzmana danışın.')}</p>
      <button type="button" onClick={onExpert} className="min-h-[60px] rounded-2xl bg-[#00d2eb] hover:bg-[#00e5ff] text-slate-950 text-lg font-extrabold">{text('Uzman seçenekleri')}</button>
    </AccessibleDialog>
  );
}
