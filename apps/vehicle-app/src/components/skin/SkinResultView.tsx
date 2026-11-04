'use client';
import { useTranslations } from '../../i18n/LanguageProvider';

import React from 'react';
import { SkinRegionData } from '../../data/skinDemoFixture';
import { SkinSnapshot } from '../../utils/skinSnapshot';
import { SkinFacePanel } from './SkinFacePanel';
import { SkinFindingsPanel } from './SkinFindingsPanel';
import {HealthPhotoNavigation} from '../HealthResultNavigation';
import {sourceBoundCallouts,findingLayers,findingSnapshot,unlocatedFindings,type SkinCaptureIdentities,type SkinSourceFrames} from '../../utils/skinCalloutModel';
import {
  FINDING_DEFS, FINDING_VIEW_NAMES, FINDING_VIEW_ORDER, isFindingView, seenCount, viewFindings,
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
  /** this scan's result was not stored, because saving is off */
  notSaved?: boolean;
}

/** Result screen ("face map"): page tabs, the photo with labels pointing at each finding, and the finding card. */
export const SkinResultView: React.FC<SkinResultViewProps> = ({ currentRegion, snapshot: defaultSnapshot, snapshots, captures, findings, findingsResult, findingsHistory, scanAt, onSelectView, onRescan, onPrev, onNext, onNavigateToCare, videoRef, isLiveVideo = false, notSaved = false }) => {
  const { text, locale } = useTranslations();
  const view: View = isFindingView(currentRegion.id) ? currentRegion.id : 'overview';
  const at = React.useMemo(() => scanAt || new Date().toISOString(), [scanAt]);
  const items = view === 'overview' ? [] : viewFindings(findings, view);
  const [index, setIndex] = React.useState(0);
  /** Overview: null = every located finding on the photo, else only this finding */
  const [overviewSel, setOverviewSel] = React.useState<SkinFindingId | null>(null);
  /** A page: the same choice. The card still shows one finding at a time. */
  const [pageSel, setPageSel] = React.useState<SkinFindingId | null>(null);
  /** The skin-type map replaces the findings while the skin-type row is on. */
  const [skinMap, setSkinMap] = React.useState(false);
  const [sourceKey,setSourceKey]=React.useState<string|null>(null);
  const pending = React.useRef<SkinFindingId | null>(null);
  /** acne lesion type drawn alone on the photo (null = every acne circle) */
  const [acneType, setAcneType] = React.useState<AcneSubtype | null>(null);
  React.useEffect(() => { setAcneType(null); }, [view, index]);
  React.useEffect(() => {
    const i = pending.current ? items.findIndex(f => f.id === pending.current) : 0;
    // A selection belongs to its view, so changing view never carries one over.
    setIndex(Math.max(0, i)); setPageSel(pending.current); pending.current = null; setOverviewSel(null);setSourceKey(null);setSkinMap(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);
  const goTo = (target: View, finding?: SkinFindingId) => {
    if (target === view) { if (finding) { setIndex(Math.max(0, items.findIndex(f => f.id === finding))); setPageSel(finding); } return; }
    pending.current = finding || null; onSelectView?.(target);
  };
  const selected = view === 'overview' ? overviewSel : pageSel;
  const snapshot=findingSnapshot(findings,view,selected,snapshots,captures,defaultSnapshot,sourceKey);
  const showMap=skinMap&&!selected;
  const callouts=showMap?[]:sourceBoundCallouts(findings,snapshot,captures,view,selected);
  // With nothing to draw, the photo keeps the regional skin-type map.
  const mapShown=!selected&&(showMap||!findingLayers(findings,snapshot,view,null).length);
  const unlocated=showMap?[]:unlocatedFindings(findings,snapshot,view,selected);
  const choose=(id:SkinFindingId|null)=>{if(view==='overview')setOverviewSel(id);else setPageSel(id);setSkinMap(false);};
  /** Tapping the selected finding again brings every finding back. */
  const selectFinding=(key:string)=>{const item=callouts.find(c=>c.key===key);if(!item)return;if(item.id===selected){choose(null);setSourceKey(null);return;}setSourceKey(key);choose(item.id);if(view!=='overview')setIndex(Math.max(0,items.findIndex(f=>f.id===item.id)));};
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

      {notSaved && <p role="status" data-skin-not-saved className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-4 py-2 text-sm text-amber-100">{text('Sonuç saklanmadı. Kayıt için Gizlilik’te açık saklama tercihi gerekir.')}</p>}

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
          <HealthPhotoNavigation previousLabel="Önceki bölge" nextLabel="Sonraki bölge" onPrevious={onPrev} onNext={onNext}>
            <SkinFacePanel currentRegion={currentRegion} snapshot={snapshot} mode="result" videoRef={videoRef} isLiveVideo={isLiveVideo}
              findings={findings} selectedFinding={selected} showAllFindings={!showMap} callouts={callouts} onSelectFinding={selectFinding}
              markerType={selected === 'acne' ? acneType : null} />
          </HealthPhotoNavigation>
          {snapshot && unlocated.length > 0 && <p data-skin-unlocated={unlocated.join(' ')} className="mt-2 max-w-full text-center text-sm text-slate-400">{text('Bu fotoğrafta işaretli değil; değerleri kartlarda:')} {unlocated.map(id => text(FINDING_DEFS[id].label)).join(', ')}</p>}
        </div>
        <div className="min-w-0 flex flex-col gap-3">
          <SkinFindingsPanel key={view} view={view} findings={findings} findingsResult={findingsResult} history={findingsHistory} scanAt={at} skinType={currentRegion.skinType}
            index={Math.min(index, Math.max(0, items.length - 1))} onIndex={i=>{setIndex(i);setSourceKey(null);setPageSel(items[i]?.id||null);setSkinMap(false);}} onGoToView={(v, f) => goTo(v, f)}
            overviewSel={overviewSel} onOverviewSel={id=>{setOverviewSel(id);setSourceKey(null);setSkinMap(false);}} acneType={acneType} onAcneType={t=>{setAcneType(t);if(t&&view!=='overview')setPageSel(items[Math.min(index,items.length-1)]?.id||null);}}
            pageSel={pageSel} onPageSel={id=>{setPageSel(id);setSourceKey(null);setSkinMap(false);}} skinMapShown={mapShown} onSkinMap={()=>{setSkinMap(!mapShown);setOverviewSel(null);setSourceKey(null);}}
            onNavigateToCare={onNavigateToCare} onRescan={onRescan} />
        </div>
      </div>
    </div>
  );
};
