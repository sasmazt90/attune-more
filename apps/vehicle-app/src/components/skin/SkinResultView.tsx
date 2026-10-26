'use client';
import { useTranslations } from '../../i18n/LanguageProvider';

import React from 'react';
import { SkinRegionData } from '../../data/skinDemoFixture';
import { SkinSnapshot } from '../../utils/skinSnapshot';
import { SkinFacePanel } from './SkinFacePanel';
import { SkinFindingsPanel } from './SkinFindingsPanel';
import {
  FINDING_ANCHOR, FINDING_DEFS, anchorPoint, FINDING_VIEW_NAMES, FINDING_VIEW_ORDER, findingColor, isFindingView, overviewFindings, seenCount, viewFindings,
  type FindingViewId, type SkinFinding, type SkinFindingId, type SkinFindingsHistoryEntry
} from '../../utils/skinFindings';
import type { FindingCallout } from './SkinFindingCallouts';

type View = 'overview' | FindingViewId;
interface SkinResultViewProps {
  currentRegion: SkinRegionData;
  snapshot?: SkinSnapshot;
  findings?: SkinFinding[];
  /** earlier scans with findings, for the history chart */
  findingsHistory?: SkinFindingsHistoryEntry[];
  /** time of this scan (ISO) */
  scanAt?: string;
  onSelectView?: (view: View) => void;
  onRescan?: () => void;
  onPrev: () => void;
  onNext: () => void;
  onOpenModal?: (modal: 'trend' | 'observation' | 'actions') => void;
  onNavigateToCare: () => void;
  videoRef?: React.RefObject<HTMLVideoElement | null>;
  isLiveVideo?: boolean;
  isBaseline?: boolean;
  comparisonUnavailable?: boolean;
  comparisonReasons?: ('legacy-quality-missing' | 'capture-conditions-incompatible')[];
  baselineTimestamp?: string;
  baselineId?: string;
  comparisonScope?: 'single-front-v1' | 'three-angle-v2';
}

/** Pages a finding was seen on, with the finding as merged on that page. */
const FINDING_VIEWS_OF = (all: SkinFinding[] | undefined, id: SkinFindingId) =>
  (overviewFindings(all).find(f => f.id === id)?.views || []).map(v => ({ v, f: viewFindings(all, v).find(x => x.id === id)! }));

/** Result screen ("face map"): page tabs, the photo with labels pointing at each finding, and the finding card. */
export const SkinResultView: React.FC<SkinResultViewProps> = ({ currentRegion, snapshot, findings, findingsHistory, scanAt, onSelectView, onRescan, onNavigateToCare, videoRef, isLiveVideo = false }) => {
  const { text, locale } = useTranslations();
  const view: View = isFindingView(currentRegion.id) ? currentRegion.id : 'overview';
  const at = React.useMemo(() => scanAt || new Date().toISOString(), [scanAt]);
  const items = view === 'overview' ? [] : viewFindings(findings, view);
  const [index, setIndex] = React.useState(0);
  /** Overview: null = skin-type map on the photo, else the finding shown on the whole face */
  const [overviewSel, setOverviewSel] = React.useState<SkinFindingId | null>(null);
  const pending = React.useRef<SkinFindingId | null>(null);
  React.useEffect(() => {
    const i = pending.current ? items.findIndex(f => f.id === pending.current) : 0;
    setIndex(Math.max(0, i)); pending.current = null; setOverviewSel(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);
  const goTo = (target: View, finding?: SkinFindingId) => {
    if (target === view) { if (finding) setIndex(Math.max(0, items.findIndex(f => f.id === finding))); return; }
    pending.current = finding || null; onSelectView?.(target);
  };
  const selected = view === 'overview' ? overviewSel : items[Math.min(index, items.length - 1)]?.id || null;
  const lm = snapshot?.landmarks;
  const anchorOf = (f: SkinFinding, v: FindingViewId) => {
    if (!snapshot || !lm) return null;
    const marker = f.markers?.[0] && (!f.pose || f.pose === snapshot.angle) ? f.markers[0] : null;
    const a = FINDING_ANCHOR[f.id][v];
    return marker ? { x: marker.x, y: marker.y } : a !== undefined ? anchorPoint(a, lm, snapshot.width, snapshot.height) : null;
  };
  const valueLabel = (f: SkinFinding) => {
    const v = f.severity ?? f.areaPct;
    return v !== undefined ? `%${Math.round(v)}` : undefined;
  };
  const ready = !!snapshot && !!lm && lm.length >= 468;
  // Page: one label per finding. Overview with a finding chosen: one label per page it was seen on (tap = open that page).
  const callouts: FindingCallout[] = !ready ? [] : view !== 'overview'
    ? items.flatMap(f => { const anchor = anchorOf(f, view); return anchor ? [{ key: f.id, id: f.id, label: FINDING_DEFS[f.id].label, color: findingColor(f.id), anchor }] : []; })
    : overviewSel ? FINDING_VIEWS_OF(findings, overviewSel).flatMap(({ v, f }) => {
        const anchor = anchorOf(f, v);
        return anchor ? [{ key: v, id: f.id, label: FINDING_VIEW_NAMES[v], sub: valueLabel(f), color: findingColor(f.id), anchor, active: true }] : [];
      }) : [];
  const onCallout = (key: string) => {
    if (view === 'overview') { if (isFindingView(key) && overviewSel) goTo(key, overviewSel); }
    else goTo(view, key as SkinFindingId);
  };
  const when = new Date(at);
  return (
    <div className="w-full flex flex-col gap-5" data-skin-result>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-4">
          <h1 className="text-[30px] font-extrabold tracking-tight text-white">{text('Cilt analizi')}</h1>
          <span className="text-base text-slate-400">{when.toLocaleDateString(locale, { day: 'numeric', month: 'long' })} · {when.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
        <span className="text-[15px] text-slate-300 px-[18px] py-2.5 rounded-full bg-[#0f1724] whitespace-nowrap">{text('Ön değerlendirme · Tanı değildir')}</span>
      </div>

      <nav aria-label={text('Bölgeler')} className="max-w-full overflow-x-auto self-start" data-skin-region-tabs>
        <div className="flex gap-1.5 p-1.5 rounded-[22px] bg-[#0d1520] min-w-max">
          {FINDING_VIEW_ORDER.map(id => {
            const active = id === view, n = id === 'overview' ? 0 : seenCount(findings, id);
            return (
              <button key={id} type="button" aria-current={active ? 'page' : undefined} onClick={() => goTo(id)} data-skin-region-tab={id}
                className={`min-h-[52px] px-5 rounded-2xl text-[17px] flex items-center gap-2 transition ${active ? 'bg-[#1a2a3c] text-white font-bold' : 'text-slate-300 font-semibold hover:bg-white/[0.05]'}`}>
                {text(id === 'overview' ? 'Genel bakış' : FINDING_VIEW_NAMES[id])}
                {n > 0 && <span className={`min-w-6 h-6 px-1.5 rounded-full text-xs font-bold flex items-center justify-center ${active ? 'bg-[#00d2eb] text-slate-950' : 'bg-white/10 text-white'}`}>{n}</span>}
              </button>
            );
          })}
        </div>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)] gap-6 xl:gap-10 items-start" data-skin-result-layout>
        <div className="min-w-0 flex flex-col items-center">
          <SkinFacePanel currentRegion={currentRegion} snapshot={snapshot} mode="result" videoRef={videoRef} isLiveVideo={isLiveVideo}
            findings={findings} selectedFinding={selected} callouts={callouts} onSelectFinding={onCallout} />
        </div>
        <div className="min-w-0">
          <SkinFindingsPanel view={view} findings={findings} history={findingsHistory} scanAt={at} skinType={currentRegion.skinType}
            index={Math.min(index, Math.max(0, items.length - 1))} onIndex={setIndex} onGoToView={(v, f) => goTo(v, f)}
            overviewSel={overviewSel} onOverviewSel={setOverviewSel}
            onNavigateToCare={onNavigateToCare} onRescan={onRescan} />
        </div>
      </div>
    </div>
  );
};
