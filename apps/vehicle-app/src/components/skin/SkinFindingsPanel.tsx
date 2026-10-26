'use client';
import React from 'react';
import { useTranslations } from '../../i18n/LanguageProvider';
import { ChevronRight, Info } from 'lucide-react';
import {
  FINDING_DEFS, FINDING_VIEWS, FINDING_VIEW_NAMES, findingColor, inconclusiveFindings, seenCount, viewFindings,
  type FindingViewId, type SkinFinding, type SkinFindingId, type SkinFindingsHistoryEntry
} from '../../utils/skinFindings';
import { PAINT_LABELS, PAINT_REGION_NAMES, paintKey, paintKeyColor, type PaintState } from '../../utils/skinTypePaint';
import { skinTypeLabel } from '../../utils/skinOverview';
import { SkinFindingCard } from './SkinFindingCard';
import { SkinRecommendationsDialog } from './SkinRecommendationsDialog';
import { SkinInconclusiveFindingsDialog } from './SkinInconclusiveFindingsDialog';
import { SkinInconclusiveDialog } from './SkinInconclusiveDialog';

type View = 'overview' | FindingViewId;
interface Props {
  view: View;
  findings?: SkinFinding[];
  history?: SkinFindingsHistoryEntry[];
  scanAt: string;
  skinType?: any;
  index: number;
  onIndex: (i: number) => void;
  onGoToView: (view: FindingViewId, finding?: SkinFindingId) => void;
  onNavigateToCare: () => void;
  onRescan?: () => void;
}

/** Right column of the result screen: the selected finding's card, the inconclusive note and the two actions. */
export function SkinFindingsPanel({ view, findings, history, scanAt, skinType, index, onIndex, onGoToView, onNavigateToCare, onRescan }: Props) {
  const { text } = useTranslations();
  const [recs, setRecs] = React.useState(false);
  const [unclear, setUnclear] = React.useState(false);
  const items = view === 'overview' ? [] : viewFindings(findings, view);
  const current = items[Math.min(index, items.length - 1)];
  const unsure = inconclusiveFindings(findings, view === 'overview' ? undefined : view);
  return (
    <div className="flex flex-col gap-3 w-full" data-skin-findings-panel={view}>
      {view === 'overview'
        ? <Overview findings={findings} skinType={skinType} onGoToView={onGoToView} />
        : current
          ? <SkinFindingCard view={view} items={items} index={Math.min(index, items.length - 1)} onIndex={onIndex} history={history} scanAt={scanAt} />
          : <section className="rounded-[26px] bg-[#0f1724] px-6 py-10 text-center flex flex-col gap-2" data-skin-findings-empty>
              <h2 className="text-2xl font-extrabold text-white">{text(FINDING_VIEW_NAMES[view])}</h2>
              <p className="text-[17px] text-slate-300">{text('Bu taramada bu bölgede öne çıkan bir bulgu yok.')}</p>
            </section>}

      {unsure.length > 0 && (
        <button type="button" aria-haspopup="dialog" onClick={() => setUnclear(true)} data-skin-findings-inconclusive={unsure.length}
          className="min-h-[52px] rounded-2xl bg-[#1a1f12] hover:bg-[#232914] px-4 flex items-center justify-between gap-3 text-left">
          <span className="flex items-center gap-2.5 text-base font-bold text-[#f5d97a]"><Info aria-hidden="true" className="w-5 h-5" />{text(`${unsure.length} bulgu kesinleştirilemedi`)}</span>
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
      {unclear && <SkinInconclusiveFindingsDialog items={unsure} onClose={() => setUnclear(false)} onRescan={onRescan && (() => { setUnclear(false); onRescan(); })} />}
    </div>
  );
}

function Overview({ findings, skinType, onGoToView }: { findings?: SkinFinding[]; skinType?: any; onGoToView: (view: FindingViewId, finding?: SkinFindingId) => void }) {
  const { text } = useTranslations();
  const [unmeasured, setUnmeasured] = React.useState<{ regionId: string; causes?: string[] | null } | null>(null);
  const regional = skinType?.decisionTrace?.regions as Record<string, any> | undefined;
  const typeName = skinTypeLabel(skinType);
  const total = seenCount(findings);
  return (
    <section className="rounded-[26px] bg-[#0f1724] p-5 flex flex-col gap-5" data-skin-overview>
      {(typeName || regional) && (
        <div className="flex flex-col gap-3" data-skin-type>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[15px] font-semibold text-slate-400">{text('Cilt tipi')}</span>
            {typeName && <strong className="text-2xl font-extrabold text-white">{text(typeName)}</strong>}
          </div>
          {regional && (
            <ul className="flex flex-wrap gap-2" data-skin-type-regions>
              {(['forehead', 'nose', 'chin', 'rightCheek', 'leftCheek'] as const).filter(id => regional[id]).map(id => {
                const e = regional[id]; const st: PaintState = ['oily', 'dry', 'normal'].includes(e.state) ? e.state : 'unmeasured';
                const sens = st !== 'unmeasured' && e.sensitive === true, color = paintKeyColor(paintKey(st, sens));
                const body = <><span aria-hidden="true" className="w-2.5 h-2.5 rounded-full" style={{ background: color }} /><span className="text-slate-400">{text(PAINT_REGION_NAMES[id])}</span><span className="text-white font-semibold">{text(PAINT_LABELS[st]) + (sens ? ' · ' + text('Hassas') : '')}</span></>;
                return (
                  <li key={id} data-skin-type-region-row={id} data-state={st}>
                    {st === 'unmeasured'
                      ? <button type="button" onClick={() => setUnmeasured({ regionId: id, causes: e.causes })} className="min-h-11 inline-flex items-center gap-2 rounded-full border border-dashed border-slate-500/70 px-3.5 text-sm">{body}<Info aria-hidden="true" className="w-4 h-4 text-togg-turquoise" /></button>
                      : <span className="min-h-11 inline-flex items-center gap-2 rounded-full bg-[#131d2b] px-3.5 text-sm">{body}</span>}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
      <div className="flex flex-col gap-2" data-skin-findings-by-view>
        <span className="text-[15px] font-semibold text-slate-400">{total ? text(`Bu taramada ${total} bulgu görüldü`) : text('Bu taramada öne çıkan bir bulgu yok')}</span>
        {FINDING_VIEWS.map(v => {
          const seen = viewFindings(findings, v);
          return (
            <button key={v} type="button" onClick={() => onGoToView(v)} data-skin-findings-view={v}
              className="min-h-[60px] rounded-[18px] bg-[#131d2b] hover:bg-[#1a2533] active:scale-[0.995] transition px-4 py-2.5 flex items-center gap-3 text-left">
              <span className="w-40 shrink-0 text-[17px] font-bold text-white">{text(FINDING_VIEW_NAMES[v])}</span>
              <span className="flex-1 flex flex-wrap gap-1.5">
                {seen.length === 0 && <span className="text-[15px] text-slate-500">{text('Öne çıkan bulgu yok')}</span>}
                {seen.map(f => (
                  <span key={f.id} className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-semibold" style={{ background: `${findingColor(f.id)}1f`, color: findingColor(f.id) }}>
                    <span aria-hidden="true" className="w-1.5 h-1.5 rounded-full" style={{ background: findingColor(f.id) }} />{text(FINDING_DEFS[f.id].label)}
                  </span>
                ))}
              </span>
              <ChevronRight aria-hidden="true" className="w-5 h-5 shrink-0 text-slate-400" />
            </button>
          );
        })}
      </div>
      {unmeasured && <SkinInconclusiveDialog regionId={unmeasured.regionId} causes={unmeasured.causes} onClose={() => setUnmeasured(null)} />}
    </section>
  );
}
