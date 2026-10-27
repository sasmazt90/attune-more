'use client';
import { X } from 'lucide-react';
import { useTranslations } from '../../i18n/LanguageProvider';
import { AccessibleDialog } from '../AccessibleDialog';
import { FINDING_DEFS, UNAVAILABLE_REASON_TEXT, type SkinFindingId } from '../../utils/skinFindings';

/** Findings that were not measured in this scan, each with its reason (no model, not validated, poses missing).
 * Nothing here is a result: these findings are neither "seen" nor "not seen". */
export function SkinUnmeasuredFindingsDialog({ items, onClose }: { items: { id: SkinFindingId; reason: string }[]; onClose: () => void }) {
  const { text } = useTranslations();
  const title = text(`${items.length} bulgu ölçülemedi`);
  return (
    <AccessibleDialog title={title} onClose={onClose} className="w-full max-w-[680px] max-h-[92vh] overflow-y-auto rounded-[28px] bg-[#0f1724] px-7 py-6 flex flex-col gap-4 shadow-2xl">
      <div className="flex items-start justify-between gap-4" data-skin-unmeasured-findings={items.length}>
        <h2 className="text-[26px] leading-tight font-extrabold tracking-tight text-white">{title}</h2>
        <button type="button" aria-label={text('Kapat')} onClick={onClose} className="w-[52px] h-[52px] shrink-0 rounded-2xl bg-[#1a2533] flex items-center justify-center text-slate-100"><X aria-hidden="true" className="w-5 h-5" /></button>
      </div>
      <p className="text-[15px] leading-snug text-slate-400">{text('Bu bulgular bu taramada değerlendirilmedi; görülmedi anlamına gelmez.')}</p>
      <ul className="flex flex-col gap-2.5">
        {items.map(u => (
          <li key={u.id} className="rounded-[18px] bg-[#131d2b] px-[18px] py-4 flex flex-col gap-1.5" data-skin-unmeasured-item={u.id} data-reason={u.reason}>
            <span className="text-[17px] font-bold text-white">{text(FINDING_DEFS[u.id].label)}</span>
            <span className="text-[15px] leading-snug text-slate-300">{text(UNAVAILABLE_REASON_TEXT[u.reason] || 'Bu bulgu bu taramada ölçülemedi.')}</span>
          </li>
        ))}
      </ul>
    </AccessibleDialog>
  );
}
