'use client';
import { X } from 'lucide-react';
import { useTranslations } from '../../i18n/LanguageProvider';
import { AccessibleDialog } from '../AccessibleDialog';
import { FINDING_DEFS, FINDING_VIEW_NAMES, type FindingViewId, type SkinFinding } from '../../utils/skinFindings';

/** Measured capture causes (regional_skin_v3.capture_causes), same wording as the skin-type dialog. */
const REASON: Record<string, string> = {
  LIGHTING: 'Işık, gölge veya parlaklık yeterince dengeli olmamış olabilir.',
  ANGLE: 'Kamera açısı bölgenin tamamının görüntülenmesini engellemiş olabilir.',
  COVER: 'Sakal veya kırışıklık çizgileri bölgenin büyük kısmını kaplamış olabilir.',
};
const ADVICE: Record<string, string> = {
  LIGHTING: 'Yüzünüzün eşit şekilde aydınlatıldığından emin olun.',
  ANGLE: 'Yüzünüzün kameraya dönük olduğundan emin olun.',
  'LIGHTING+ANGLE': 'Yüzünüzün eşit şekilde aydınlatıldığından ve kameraya dönük olduğundan emin olun.',
};
const causesOf = (f: SkinFinding) => (f.causes?.length ? f.causes : ['LIGHTING', 'ANGLE']).filter(c => c in REASON);

/** Findings that could not be confirmed: where, the likely reason, what to change, and a rescan button. */
export function SkinInconclusiveFindingsDialog({ items, onClose, onRescan }: {
  items: (SkinFinding & { view: FindingViewId })[]; onClose: () => void; onRescan?: () => void;
}) {
  const { text } = useTranslations();
  const all = new Set(items.flatMap(causesOf));
  const key = ['LIGHTING', 'ANGLE'].filter(c => all.has(c)).join('+');
  const title = text(`${items.length} bulgu kesinleştirilemedi`);
  return (
    <AccessibleDialog title={title} onClose={onClose} className="w-full max-w-[680px] max-h-[92vh] overflow-y-auto rounded-[28px] bg-[#0f1724] px-7 py-6 flex flex-col gap-4 shadow-2xl">
      <div className="flex items-start justify-between gap-4" data-skin-inconclusive-findings={items.length}>
        <h2 className="text-[26px] leading-tight font-extrabold tracking-tight text-white">{title}</h2>
        <button type="button" aria-label={text('Kapat')} onClick={onClose} className="w-[52px] h-[52px] shrink-0 rounded-2xl bg-[#1a2533] flex items-center justify-center text-slate-100"><X aria-hidden="true" className="w-5 h-5" /></button>
      </div>
      <ul className="flex flex-col gap-2.5">
        {items.map(f => (
          <li key={f.view + f.id} className="rounded-[18px] bg-[#131d2b] px-[18px] py-4 flex flex-col gap-1.5" data-skin-inconclusive-item={f.id}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-[17px] font-bold text-white">{text(FINDING_DEFS[f.id].label)}</span>
              <span className="text-sm text-slate-400 whitespace-nowrap">{text(FINDING_VIEW_NAMES[f.view])}</span>
            </div>
            {causesOf(f).map(c => <span key={c} className="text-[15px] leading-snug text-slate-300">{text(REASON[c])}</span>)}
          </li>
        ))}
      </ul>
      {key && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-bold tracking-[0.08em] uppercase text-slate-400">{text('Tekrar taramadan önce')}</span>
          <span className="text-[15px] leading-snug text-slate-300">{text(ADVICE[key])}</span>
        </div>
      )}
      {onRescan && <button type="button" onClick={onRescan} className="min-h-[60px] rounded-2xl bg-[#00d2eb] hover:bg-[#00e5ff] text-slate-950 text-lg font-extrabold">{text('Tekrar tara')}</button>}
    </AccessibleDialog>
  );
}
