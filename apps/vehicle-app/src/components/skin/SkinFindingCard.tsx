'use client';
import React from 'react';
import { ChevronLeft, ChevronRight, CalendarDays } from 'lucide-react';
import { useTranslations } from '../../i18n/LanguageProvider';
import {
  FINDING_DEFS, FINDING_VIEW_NAMES, COUNT_RANGE_LABEL, findingColor, viewFindings,
  type FindingViewId, type SkinFinding, type SkinFindingsHistoryEntry
} from '../../utils/skinFindings';
import { findingScore } from '../../utils/skinRecommendations';
import { SkinDateRangeDialog, inDayRange, type DateRange } from './SkinDateRangeDialog';

/** One finding of a page: title with arrows to the other findings, what it looks like, its score and its history. */
export function SkinFindingCard({ view, items, index, onIndex, history, scanAt }: {
  view: FindingViewId; items: SkinFinding[]; index: number; onIndex: (i: number) => void;
  history?: SkinFindingsHistoryEntry[]; scanAt: string;
}) {
  const { text } = useTranslations();
  const f = items[index], n = items.length, color = findingColor(f.id), def = FINDING_DEFS[f.id];
  const score = findingScore(f);
  const step = (d: number) => onIndex((index + d + n) % n);
  const arrow = (d: number) => (
    <button type="button" onClick={() => step(d)} disabled={n < 2} aria-label={text(d < 0 ? 'Önceki bulgu' : 'Sonraki bulgu')}
      className="w-[52px] h-[52px] shrink-0 rounded-2xl bg-[#1a2533] flex items-center justify-center text-slate-100 hover:bg-[#223043] active:scale-95 transition disabled:opacity-30 disabled:pointer-events-none">
      {d < 0 ? <ChevronLeft aria-hidden="true" className="w-6 h-6" /> : <ChevronRight aria-hidden="true" className="w-6 h-6" />}
    </button>
  );
  return (
    <section className="rounded-[26px] bg-[#0f1724] px-5 pt-5 pb-6 flex flex-col gap-5" data-skin-finding-card={f.id} aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        {arrow(-1)}
        <div className="min-w-0 flex flex-col items-center gap-1 text-center">
          <span className="text-[13px] font-bold tracking-[0.08em] uppercase" style={{ color }} data-skin-finding-kicker>
            {text(FINDING_VIEW_NAMES[view])} · {index + 1} / {n}
          </span>
          <h2 className="text-[28px] leading-tight font-extrabold tracking-tight text-white">{text(def.label)}</h2>
        </div>
        {arrow(1)}
      </div>
      <p className="text-[17px] leading-snug text-slate-300 text-center">{text(def.info)}</p>
      {f.severity !== undefined
        ? <ScoreBar value={f.severity} color={color} label={text('Belirginlik')} scale={[text('Hafif'), text('Orta'), text('Belirgin')]} />
        : f.areaPct !== undefined
          ? <ScoreBar value={f.areaPct} color={color} label={text('Kapladığı alan')} scale={['%0', '%50', '%100'].map(text)} />
          : def.kind === 'count' && f.countRange
            ? <div className="flex items-baseline justify-center gap-2" data-skin-finding-count={f.countRange}>
                <span className="text-4xl font-extrabold tabular-nums text-white">{COUNT_RANGE_LABEL[f.countRange] || f.countRange}</span>
                <span className="text-base text-slate-400">{text(def.unit || '')}</span>
              </div>
            : <p className="text-[15px] leading-snug text-slate-400 text-center" data-skin-finding-unmeasured>
                {text('Bu taramada görüldü. Belirginlik, alan ve sayı bu sürümde ölçülmüyor.')}
              </p>}
      {score !== undefined && <History view={view} finding={f} history={history} scanAt={scanAt} color={color} />}
    </section>
  );
}

function ScoreBar({ value, color, label, scale }: { value: number; color: string; label: string; scale: string[] }) {
  const { text } = useTranslations();
  const v = Math.round(Math.max(0, Math.min(100, value)));
  // keep the number inside the card at the ends of the bar
  const shift = v < 6 ? '0%' : v > 94 ? '-100%' : '-50%';
  return (
    <div className="flex flex-col gap-1.5" data-skin-finding-score={v}>
      <span className="text-[15px] font-semibold text-slate-400">{label}</span>
      <div className="relative h-8">
        <span className="absolute bottom-0 whitespace-nowrap text-xl font-extrabold text-white tabular-nums" style={{ left: `${v}%`, transform: `translateX(${shift})` }}>{text(`%${v}`)}</span>
      </div>
      <div className="relative h-2.5 rounded-full bg-[#1a2533]" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={v} aria-label={label}>
        <div className="h-full rounded-full" style={{ width: `${v}%`, background: color }} />
        <div className="absolute top-1/2 w-[18px] h-[18px] rounded-full bg-white border-4 -translate-x-1/2 -translate-y-1/2" style={{ left: `${v}%`, borderColor: color }} />
      </div>
      <div className="flex justify-between pt-1 text-[13px] text-slate-500">{scale.map(s => <span key={s}>{s}</span>)}</div>
    </div>
  );
}

function History({ view, finding, history, scanAt, color }: { view: FindingViewId; finding: SkinFinding; history?: SkinFindingsHistoryEntry[]; scanAt: string; color: string }) {
  const { text, locale } = useTranslations();
  const all = React.useMemo(() => {
    const rows = (history || []).flatMap(h => {
      const m = viewFindings(h.findings, view).find(x => x.id === finding.id), v = m && findingScore(m);
      return v === undefined ? [] : [{ at: h.at, v }];
    });
    const now = findingScore(finding);
    if (now !== undefined && !rows.some(r => r.at === scanAt)) rows.push({ at: scanAt, v: now });
    return rows.sort((a, b) => a.at.localeCompare(b.at));
  }, [history, view, finding, scanAt]);
  const [range, setRange] = React.useState<DateRange | null>(null);
  const [picker, setPicker] = React.useState(false);
  const first = all.length ? new Date(all[0].at) : new Date(scanAt), last = new Date(scanAt);
  const from = range?.from || first, to = range?.to || last;
  const pts = all.filter(p => inDayRange(p.at, { from, to }));
  const fmt = (d: Date, year = false) => d.toLocaleDateString(locale, { day: 'numeric', month: 'short', ...(year ? { year: 'numeric' } : {}) });
  const W = 504, H = 160, X0 = 40, X1 = 480, Y0 = 10, Y1 = 132;
  const x = (i: number) => (pts.length < 2 ? (X0 + X1) / 2 : X0 + (X1 - X0) * i / (pts.length - 1));
  const y = (v: number) => Y1 - (Y1 - Y0) * Math.max(0, Math.min(100, v)) / 100;
  const labelEvery = Math.max(1, Math.ceil(pts.length / 6));
  return (
    <div className="flex flex-col gap-2" data-skin-finding-history={pts.length}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-[15px] font-semibold text-slate-400">{text('Geçmiş')}</span>
        <button type="button" aria-haspopup="dialog" onClick={() => setPicker(true)} data-skin-history-range
          className="min-h-11 rounded-xl bg-[#1a2533] hover:bg-[#223043] px-3 flex items-center gap-2 text-sm font-semibold text-slate-100">
          <CalendarDays aria-hidden="true" className="w-4 h-4 text-slate-300" />{fmt(from)} – {fmt(to, true)}
        </button>
      </div>
      {pts.length < 2
        ? <p className="rounded-2xl bg-[#131d2b] px-4 py-5 text-[15px] leading-snug text-slate-400 text-center" data-skin-history-empty>
            {text(all.length < 2 ? 'Geçmiş grafiği bir sonraki taramanızdan sonra burada görünür.' : 'Seçilen tarih aralığında yeterli tarama yok.')}
          </p>
        : <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
            aria-label={text('Belirginlik geçmişi') + ': ' + pts.map(p => `${fmt(new Date(p.at))} %${Math.round(p.v)}`).join(', ')}>
            {[100, 50, 0].map(v => (
              <g key={v}>
                <line x1={X0} x2={W - 8} y1={y(v)} y2={y(v)} stroke={v ? '#1a2533' : '#26313f'} />
                <text x={X0 - 8} y={y(v) + 4} textAnchor="end" fontSize="12" fill="#7d8898">{v}</text>
              </g>
            ))}
            <polyline points={pts.map((p, i) => `${x(i)},${y(p.v)}`).join(' ')} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
            {pts.map((p, i) => (
              <g key={p.at}>
                <circle cx={x(i)} cy={y(p.v)} r={i === pts.length - 1 ? 5.5 : 4} fill={i === pts.length - 1 ? color : '#0f1724'} stroke={color} strokeWidth="2.5" />
                {(i % labelEvery === 0 || i === pts.length - 1) && <text x={x(i)} y={H - 6} textAnchor={pts.length > 1 && i === 0 ? 'start' : pts.length > 1 && i === pts.length - 1 ? 'end' : 'middle'} dx={pts.length > 1 && i === 0 ? -6 : pts.length > 1 && i === pts.length - 1 ? 6 : 0} fontSize="12" fill="#7d8898">{fmt(new Date(p.at))}</text>}
              </g>
            ))}
          </svg>}
      {picker && <SkinDateRangeDialog scans={all.map(p => p.at)} value={{ from, to }} onClose={() => setPicker(false)} onApply={r => { setRange(r); setPicker(false); }} />}
    </div>
  );
}
