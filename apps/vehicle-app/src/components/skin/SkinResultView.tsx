'use client';
import { useTranslations } from '../../i18n/LanguageProvider';

import React from 'react';
import { SkinRegionData } from '../../data/skinDemoFixture';
import { SkinSnapshot } from '../../utils/skinSnapshot';
import { SkinFacePanel } from './SkinFacePanel';
import { SkinFindingsPanel } from './SkinFindingsPanel';
import {HealthResultNavigation} from '../HealthResultNavigation';
import {sourceBoundCallouts,findingSnapshot,type SkinCaptureIdentities,type SkinSourceFrames} from '../../utils/skinCalloutModel';
import {
  FINDING_VIEW_NAMES, FINDING_VIEW_ORDER, isFindingView, seenCount, viewFindings,
  type AcneSubtype, type FindingViewId, type SkinFinding, type SkinFindingId, type SkinFindingsHistoryEntry
} from '../../utils/skinFindings';

type View = 'overview' | FindingViewId;
interface SkinResultViewProps {
  currentRegion: SkinRegionData;
  snapshot?: SkinSnapshot;
  snapshots?: SkinSourceFrames;
  captures?: SkinCaptureIdentities;
  findings?: SkinFinding[];
  /** general.findings of the record (status / unavailable list) */
  findingsResult?: unknown;
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

/** Result screen ("face map"): page tabs, the photo with labels pointing at each finding, and the finding card. */
export const SkinResultView: React.FC<SkinResultViewProps> = ({ currentRegion, snapshot: defaultSnapshot, snapshots, captures, findings, findingsResult, findingsHistory, scanAt, onSelectView, onRescan, onPrev, onNext, onNavigateToCare, videoRef, isLiveVideo = false }) => {
  const { text, locale } = useTranslations();
  const view: View = isFindingView(currentRegion.id) ? currentRegion.id : 'overview';
  const at = React.useMemo(() => scanAt || new Date().toISOString(), [scanAt]);
  const items = view === 'overview' ? [] : viewFindings(findings, view);
  const [index, setIndex] = React.useState(0);
  /** Overview: null = skin-type map on the photo, else the finding shown on the whole face */
  const [overviewSel, setOverviewSel] = React.useState<SkinFindingId | null>(null);
  const [sourceKey,setSourceKey]=React.useState<string|null>(null);
  const pending = React.useRef<SkinFindingId | null>(null);
  /** acne lesion type drawn alone on the photo (null = every acne circle) */
  const [acneType, setAcneType] = React.useState<AcneSubtype | null>(null);
  React.useEffect(() => { setAcneType(null); }, [view, index]);
  React.useEffect(() => {
    const i = pending.current ? items.findIndex(f => f.id === pending.current) : 0;
    setIndex(Math.max(0, i)); pending.current = null; setOverviewSel(null);setSourceKey(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);
  const goTo = (target: View, finding?: SkinFindingId) => {
    if (target === view) { if (finding) setIndex(Math.max(0, items.findIndex(f => f.id === finding))); return; }
    pending.current = finding || null; onSelectView?.(target);
  };
  const selected = view === 'overview' ? overviewSel : items[Math.min(index, items.length - 1)]?.id || null;
  const snapshot=findingSnapshot(findings,view,selected,snapshots,captures,defaultSnapshot,sourceKey);
  const callouts=sourceBoundCallouts(findings,snapshot,captures,view,selected);
  const selectFinding=(key:string)=>{const item=callouts.find(c=>c.key===key);if(!item)return;setSourceKey(key);if(view==='overview')setOverviewSel(item.id);else setIndex(Math.max(0,items.findIndex(f=>f.id===item.id)));};
  const when = new Date(at);
  return (
    <div className="w-full flex flex-col gap-5 short:gap-2" data-skin-result>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-4">
          <h1 className="text-[30px] short:text-2xl font-extrabold tracking-tight text-white">{text('Cilt analizi')}</h1>
          <span className="text-base text-slate-400">{when.toLocaleDateString(locale, { day: 'numeric', month: 'long' })} · {when.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
        <span className="text-[15px] text-slate-300 px-[18px] py-2.5 rounded-full bg-[#0f1724] whitespace-nowrap">{text('Ön değerlendirme · Tanı değildir')}</span>
      </div>

      <nav aria-label={text('Bölgeler')} className="max-w-full overflow-x-auto self-start" data-skin-region-tabs>
        <div className="flex gap-1.5 p-1.5 short:p-1 rounded-[22px] short:rounded-2xl bg-[#0d1520] min-w-max">
          {FINDING_VIEW_ORDER.map(id => {
            const active = id === view, n = id === 'overview' ? 0 : seenCount(findings, id);
            return (
              <button key={id} type="button" aria-current={active ? 'page' : undefined} onClick={() => goTo(id)} data-skin-region-tab={id}
                className={`min-h-[52px] short:min-h-[44px] px-5 short:px-3 rounded-2xl text-[17px] short:text-sm flex items-center gap-2 transition ${active ? 'bg-[#1a2a3c] text-white font-bold' : 'text-slate-300 font-semibold hover:bg-white/[0.05]'}`}>
                {text(id === 'overview' ? 'Genel bakış' : FINDING_VIEW_NAMES[id])}
                {n > 0 && <span className={`min-w-6 h-6 px-1.5 rounded-full text-xs font-bold flex items-center justify-center ${active ? 'bg-[#00d2eb] text-slate-950' : 'bg-white/10 text-white'}`}>{n}</span>}
              </button>
            );
          })}
        </div>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-2 short:grid-cols-2 gap-6 short:gap-3 xl:gap-10 items-start" data-skin-result-layout>
        <div className="min-w-0 flex flex-col items-center">
          <SkinFacePanel currentRegion={currentRegion} snapshot={snapshot} mode="result" videoRef={videoRef} isLiveVideo={isLiveVideo}
            findings={findings} selectedFinding={selected} callouts={callouts} onSelectFinding={selectFinding}
            markerType={selected === 'acne' ? acneType : null} />
        </div>
        <div className="min-w-0 flex flex-col gap-3">
          <HealthResultNavigation title={view==='overview'?'Genel bakış':FINDING_VIEW_NAMES[view]} previousLabel="Önceki bölge" nextLabel="Sonraki bölge" onPrevious={onPrev} onNext={onNext} index={FINDING_VIEW_ORDER.indexOf(view)} total={FINDING_VIEW_ORDER.length}/>
          <SkinFindingsPanel key={view} view={view} findings={findings} findingsResult={findingsResult} history={findingsHistory} scanAt={at} skinType={currentRegion.skinType}
            index={Math.min(index, Math.max(0, items.length - 1))} onIndex={i=>{setIndex(i);setSourceKey(null);}} onGoToView={(v, f) => goTo(v, f)}
            overviewSel={overviewSel} onOverviewSel={id=>{setOverviewSel(id);setSourceKey(null);}} acneType={acneType} onAcneType={setAcneType}
            onNavigateToCare={onNavigateToCare} onRescan={onRescan} />
        </div>
      </div>
    </div>
  );
};
