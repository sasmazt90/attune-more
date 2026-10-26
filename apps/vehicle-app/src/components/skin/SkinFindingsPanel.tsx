'use client';
import React from 'react';
import { useTranslations } from '../../i18n/LanguageProvider';
import { ChevronLeft, ChevronRight, Info } from 'lucide-react';
import {
  FINDING_DEFS, FINDING_VIEW_NAMES, UNAVAILABLE_REASON_TEXT, countLabel, countUnit, findingColor, findingsState, inconclusiveFindings, overviewFindings,
  unmeasuredFindings, validFindings, viewFindings, type FindingsState, type OverviewFinding,
  type FindingViewId, type SkinFinding, type SkinFindingId, type SkinFindingsHistoryEntry
} from '../../utils/skinFindings';
import { skinTypeLabel } from '../../utils/skinOverview';
import { SkinFindingCard } from './SkinFindingCard';
import { SkinRecommendationsDialog } from './SkinRecommendationsDialog';
import { SkinInconclusiveFindingsDialog } from './SkinInconclusiveFindingsDialog';
import { SkinUnmeasuredFindingsDialog } from './SkinUnmeasuredFindingsDialog';
import { recommendationBand } from '../../utils/skinRecommendations';

type View = 'overview' | FindingViewId;
interface Props {
  view: View;
  findings?: SkinFinding[];
  /** general.findings of the record: separates "not measured" from "measured, nothing seen" */
  findingsResult?: unknown;
  history?: SkinFindingsHistoryEntry[];
  scanAt: string;
  skinType?: any;
  index: number;
  onIndex: (i: number) => void;
  onGoToView: (view: FindingViewId, finding?: SkinFindingId) => void;
  onNavigateToCare: () => void;
  onRescan?: () => void;
  overviewSel: SkinFindingId | null;
  onOverviewSel: (id: SkinFindingId | null) => void;
}

/** Right column of the result screen: the selected finding's card, the inconclusive note and the two actions. */
export function SkinFindingsPanel({ view, findings, findingsResult, history, scanAt, skinType, index, onIndex, onNavigateToCare, onRescan, overviewSel, onOverviewSel }: Props) {
  const { text } = useTranslations();
  const [recs, setRecs] = React.useState(false);
  const [unclear, setUnclear] = React.useState(false);
  const [unmeasuredOpen, setUnmeasuredOpen] = React.useState(false);
  const state = findingsState(findingsResult);
  const unmeasured = unmeasuredFindings(validFindings(findingsResult) ? findingsResult : undefined, view === 'overview' ? undefined : view);
  const items = view === 'overview' ? [] : viewFindings(findings, view);
  const current = view === 'overview' ? overviewFindings(findings).find(f => f.id === overviewSel) : items[Math.min(index, items.length - 1)];
  const unsure = inconclusiveFindings(findings, view === 'overview' ? undefined : view);
  return (
    <div className="flex flex-col gap-3 w-full" data-skin-findings-panel={view}>
      {view === 'overview'
        ? <Overview findings={findings} state={state} skinType={skinType} selected={overviewSel} onSelect={onOverviewSel} />
        : current
          ? <SkinFindingCard view={view} items={items} index={Math.min(index, items.length - 1)} onIndex={onIndex} history={history} scanAt={scanAt} />
          : <section className="rounded-[26px] bg-[#0f1724] px-6 py-10 text-center flex flex-col gap-2" data-skin-findings-empty={state.kind}>
              <h2 className="text-2xl font-extrabold text-white">{text(FINDING_VIEW_NAMES[view])}</h2>
              {emptyText(state, 'page').map(t => <p key={t} className="text-[17px] text-slate-300">{text(t)}</p>)}
            </section>}

      {unsure.length > 0 && (
        <button type="button" aria-haspopup="dialog" onClick={() => setUnclear(true)} data-skin-findings-inconclusive={unsure.length}
          className="min-h-[52px] rounded-2xl bg-[#1a1f12] hover:bg-[#232914] px-4 flex items-center justify-between gap-3 text-left">
          <span className="flex items-center gap-2.5 text-base font-bold text-[#f5d97a]"><Info aria-hidden="true" className="w-5 h-5" />{text(`${unsure.length} bulgu kesinleştirilemedi`)}</span>
          <span className="flex items-center gap-1.5 text-[15px] font-semibold text-slate-100">{text('Ayrıntılar')}<ChevronRight aria-hidden="true" className="w-5 h-5" /></span>
        </button>
      )}

      {unmeasured.length > 0 && (
        <button type="button" aria-haspopup="dialog" onClick={() => setUnmeasuredOpen(true)} data-skin-findings-unmeasured={unmeasured.length}
          className="min-h-[52px] rounded-2xl bg-[#131d2b] hover:bg-[#1a2533] px-4 flex items-center justify-between gap-3 text-left">
          <span className="flex items-center gap-2.5 text-base font-bold text-slate-200"><Info aria-hidden="true" className="w-5 h-5 text-slate-400" />{text(`${unmeasured.length} bulgu ölçülemedi`)}</span>
          <span className="flex items-center gap-1.5 text-[15px] font-semibold text-slate-100">{text('Ayrıntılar')}<ChevronRight aria-hidden="true" className="w-5 h-5" /></span>
        </button>
      )}

      <div className="flex gap-3" data-skin-actions>
        {current && (
          <button type="button" aria-haspopup="dialog" onClick={() => setRecs(true)} data-skin-open-recommendations
            className="min-h-[60px] flex-1 rounded-[18px] bg-[#0f1724] hover:bg-[#162133] text-lg font-bold text-slate-100 active:scale-[0.99] transition">{text('Öneriler')}</button>
        )}
        <button type="button" onClick={onNavigateToCare}
          className="min-h-[60px] flex-[1.6] rounded-[18px] bg-[#00d2eb] hover:bg-[#00e5ff] text-lg font-extrabold text-slate-950 active:scale-[0.99] transition">{text('Uzman seçenekleri')}</button>
      </div>
      {recs && current && <SkinRecommendationsDialog finding={current} onClose={() => setRecs(false)} onExpert={() => { setRecs(false); onNavigateToCare(); }} />}
      {unmeasuredOpen && <SkinUnmeasuredFindingsDialog items={unmeasured} onClose={() => setUnmeasuredOpen(false)} />}
      {unclear && <SkinInconclusiveFindingsDialog items={unsure} onClose={() => setUnclear(false)} onRescan={onRescan && (() => { setUnclear(false); onRescan(); })} />}
    </div>
  );
}

/** Empty state: "measured, nothing seen" only when the findings were actually measured. */
function emptyText(state: FindingsState, where: 'page' | 'overview'): string[] {
  if (state.kind === 'missing') return ['Bu kayıtta bulgu analizi yok; bulgular ölçülmedi.'];
  if (state.kind === 'unavailable') return ['Bulgular bu taramada ölçülemedi.', ...(UNAVAILABLE_REASON_TEXT[state.reason] ? [UNAVAILABLE_REASON_TEXT[state.reason]] : [])];
  return [where === 'page' ? 'Ölçülen bulgular bu bölgede görülmedi.' : 'Ölçülen bulgular bu taramada görülmedi.'];
}

function Overview({ findings, state, skinType, selected, onSelect }: {
  findings?: SkinFinding[]; state: FindingsState; skinType?: any; selected: SkinFindingId | null; onSelect: (id: SkinFindingId | null) => void;
}) {
  const { text } = useTranslations();
  const typeName = skinTypeLabel(skinType);
  const all = overviewFindings(findings);
  const PAGE = 4, pages = Math.max(1, Math.ceil(all.length / PAGE));
  const [page, setPage] = React.useState(0);
  const shown = all.slice(page * PAGE, page * PAGE + PAGE);
  // the header arrows slide the findings grid, four cards at a time
  const arrow = (d: number) => (
    <button type="button" onClick={() => setPage((page + d + pages) % pages)} disabled={pages < 2} aria-label={text(d < 0 ? 'Önceki bulgular' : 'Sonraki bulgular')}
      className="w-[52px] h-[52px] shrink-0 rounded-2xl bg-[#1a2533] flex items-center justify-center text-slate-100 hover:bg-[#223043] active:scale-95 transition disabled:opacity-30 disabled:pointer-events-none">
      {d < 0 ? <ChevronLeft aria-hidden="true" className="w-6 h-6" /> : <ChevronRight aria-hidden="true" className="w-6 h-6" />}
    </button>
  );
  return (
    <section className="rounded-[26px] bg-[#0f1724] px-5 pt-4 pb-5 flex flex-col gap-3" data-skin-overview>
      <div className="flex items-center justify-between gap-3">
        {arrow(-1)}
        <div className="min-w-0 flex flex-col items-center gap-1 text-center">
          {pages > 1 && <span className="text-[13px] font-bold tracking-[0.08em] text-[#00d2eb] tabular-nums" data-skin-overview-page>{page + 1} / {pages}</span>}
          <h2 className="text-[28px] leading-tight font-extrabold tracking-tight text-white">{text('Genel bakış')}</h2>
        </div>
        {arrow(1)}
      </div>
      {typeName && (
        <button type="button" aria-pressed={selected === null} onClick={() => onSelect(null)} data-skin-type-card
          className={`min-h-[56px] rounded-2xl border-2 px-4 py-2 flex items-center justify-between gap-3 text-left transition ${selected === null ? 'border-[#00d2eb] bg-[#00d2eb]/10' : 'border-transparent bg-[#131d2b] hover:bg-[#1a2533]'}`}>
          <span className="text-[15px] font-semibold text-slate-400">{text('Cilt tipi')}</span>
          <strong className="text-lg font-bold text-white">{text(typeName)}</strong>
        </button>
      )}
      <div className="flex flex-col gap-2.5" data-skin-overview-findings={all.length} data-skin-findings-state={state.kind}>
        <div className="flex items-center justify-between gap-3">
          <span className="text-[15px] font-semibold text-slate-400">{text('Bulgular')}</span>
        </div>
        {all.length === 0
          ? <div className="rounded-[18px] bg-[#131d2b] px-4 py-6 text-center text-[17px] text-slate-300 flex flex-col gap-1" data-skin-findings-empty={state.kind}>{emptyText(state, 'overview').map(t => <p key={t}>{text(t)}</p>)}</div>
          : <div className="grid grid-cols-2 gap-2.5">
              {shown.map(f => <OverviewFindingCard key={f.id} f={f} on={selected === f.id} onClick={() => onSelect(selected === f.id ? null : f.id)} />)}
            </div>}
      </div>
    </section>
  );
}

/** Small card of the overview grid: name and a bar for the score, area or count. */
function OverviewFindingCard({ f, on, onClick }: { f: OverviewFinding; on: boolean; onClick: () => void }) {
  const { text } = useTranslations();
  const color = findingColor(f.id), def = FINDING_DEFS[f.id];
  const score = f.severity ?? f.areaPct;
  let width: number | null = null, value: string;
  if (score !== undefined) { width = Math.round(score); value = text(`%${width}`); }
  else if (countLabel(f) !== null) {
    const b = recommendationBand(f); width = b ? Math.round((b.index + 1) / b.total * 100) : null;
    value = `${countLabel(f)} ${countUnit(countLabel(f), def.unit, text)}`.trim();
  } else value = f.views.map(v => text(FINDING_VIEW_NAMES[v])).join(', ');  // no score: where it was seen
  // the value sits above the filled end of the bar (kept inside the card at both ends)
  const shift = width === null ? '0%' : width < 12 ? '0%' : width > 88 ? '-100%' : '-50%';
  return (
    <button type="button" aria-pressed={on} onClick={onClick} data-skin-overview-finding={f.id}
      className="min-h-[96px] rounded-2xl border-2 px-4 pt-3 pb-3.5 flex flex-col justify-between gap-1.5 text-left transition active:scale-[0.99]"
      style={{ borderColor: on ? color : 'transparent', background: on ? `${color}1a` : '#131d2b' }}>
      <span className="flex items-center gap-2 min-w-0">
        <span aria-hidden="true" className="w-2.5 h-2.5 shrink-0 rounded-full" style={{ background: color }} />
        <span className="text-base font-bold leading-tight text-white truncate">{text(def.label)}</span>
      </span>
      {width !== null
        ? <span className="block">
            <span className="relative block h-6">
              <span className="absolute bottom-0 whitespace-nowrap text-base font-extrabold text-white tabular-nums" style={{ left: `${Math.max(4, width)}%`, transform: `translateX(${shift})` }}>{value}</span>
            </span>
            <span className="mt-0.5 block h-2 rounded-full bg-[#1a2533]" aria-hidden="true">
              <span className="block h-full rounded-full" style={{ width: `${Math.max(4, width)}%`, background: color }} />
            </span>
          </span>
        : <span className="text-sm font-semibold text-slate-400 truncate">{value}</span>}
    </button>
  );
}
