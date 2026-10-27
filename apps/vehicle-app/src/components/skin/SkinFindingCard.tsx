'use client';
import React from 'react';
import { ChevronLeft, ChevronRight, CalendarDays } from 'lucide-react';
import { useTranslations } from '../../i18n/LanguageProvider';
import {
  ACNE_SUBTYPES, FINDING_DEFS, type AcneSubtype, FINDING_VIEW_NAMES, REGION_NAMES, VIEW_REGIONS, countLabel, countUnit, findingColor,
  type FindingViewId, type SkinFinding, type SkinFindingsHistoryEntry, type SkinFindingsResult
} from '../../utils/skinFindings';
import { usesAppearance } from '../../utils/skinRecommendations';
import { compareMeasures, measureOf, scopeOf, type Measure } from '../../utils/skinHistorySummary';
import { SkinDateRangeDialog, inDayRange, type DateRange } from './SkinDateRangeDialog';

/** One finding of a page: title with arrows to the other findings, what it looks like, its score and its history. */
export function SkinFindingCard({ view, items, index, onIndex, history, scanAt, acneType = null, onAcneType, current }: {
  view: FindingViewId; items: SkinFinding[]; index: number; onIndex: (i: number) => void;
  history?: SkinFindingsHistoryEntry[]; scanAt: string;
  /** acne lesion type whose markers alone are drawn on the photo (null = all) */
  acneType?: AcneSubtype | null; onAcneType?: (t: AcneSubtype | null) => void;
  /** this scan's whole findings result (history comparisons need the measured/not measured state of every region) */
  current?: SkinFindingsResult;
}) {
  const { text, language, locale } = useTranslations();
  const f = items[index], n = items.length, color = findingColor(f.id), def = FINDING_DEFS[f.id];
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
      {usesAppearance(f)
        ? <AppearanceValue f={f} color={color} />
        : f.severity !== undefined
        ? <ScoreBar value={f.severity} color={color} label={text('Belirginlik')} scale={[text('Hafif'), text('Orta'), text('Belirgin')]} />
        : f.areaPct !== undefined
          ? <ScoreBar value={f.areaPct} color={color} label={text(f.id === 'melasma' ? 'İşaretli leke kutularının kapladığı alan' : 'Kapladığı alan')} scale={['%0', '%50', '%100'].map(text)} />
          : countLabel(f) !== null
            ? <div className="flex items-baseline justify-center gap-2" data-skin-finding-count={countLabel(f)}>
                <span className="text-4xl font-extrabold tabular-nums text-white">{countLabel(f)}</span>
                <span className="text-base text-slate-400">{countUnit(countLabel(f), def.unit, text)}</span>
              </div>
            : <p className="text-[15px] leading-snug text-slate-400 text-center" data-skin-finding-unmeasured>
                {text('Bu bulgunun değeri bu taramada hesaplanamadı.')}
              </p>}
      {f.toneDiff !== undefined && (
        <p className="text-[15px] text-slate-300 text-center" data-skin-finding-tone={f.toneDiff}>
          {text('Cilt tonunuza göre kırmızılık farkı')}: <strong className="text-white tabular-nums">{f.toneDiff > 0 ? '+' : ''}{language === 'tr' ? f.toneDiff : f.toneDiff.toLocaleString(locale)}</strong>
        </p>
      )}
      {!!f.incomplete?.length && (
        <p className="text-[14px] text-amber-200 text-center" data-skin-finding-incomplete={f.incomplete.join(',')}>
          {text(`Ölçülemeyen bölge: ${f.incomplete.map(r => text(REGION_NAMES[r])).join(', ')}`)}
        </p>
      )}
      {f.subtypes && <AcneTypes f={f} selected={acneType} onSelect={onAcneType} />}
      {current && <History view={view} finding={f} current={current} history={history} scanAt={scanAt} color={color} />}
    </section>
  );
}

/** Collapsible lesion-type breakdown of the acne count (the rows add up to the count shown above). Tapping a type
 * draws only that type's circles on the photo; tapping the same type again draws all of them again. */
function AcneTypes({ f, selected, onSelect }: { f: SkinFinding; selected: AcneSubtype | null; onSelect?: (t: AcneSubtype | null) => void }) {
  const { text } = useTranslations();
  const [open, setOpen] = React.useState(false);
  return (
    <div className="rounded-2xl bg-[#131d2b]" data-skin-acne-subtypes={open ? 'open' : 'closed'} data-skin-acne-selected={selected || 'all'}>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
        className="w-full min-h-[48px] px-4 flex items-center justify-between gap-3 text-[15px] font-semibold text-slate-100">
        {text('Akne türleri')}
        <ChevronRight aria-hidden="true" className={`w-5 h-5 transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>
      {open && (
        <ul className="flex flex-col gap-1 px-2 pb-2">
          {ACNE_SUBTYPES.map(({ id, label }) => {
            const n = f.subtypes![id] || 0, active = selected === id;
            return (
              <li key={id} data-skin-acne-subtype={id}>
                <button type="button" disabled={!n || !onSelect} aria-pressed={active} onClick={() => onSelect?.(active ? null : id)}
                  className={`w-full min-h-[44px] px-2 rounded-xl flex items-center justify-between gap-3 text-[15px] text-left transition ${active ? 'bg-[#00d2eb]/15 ring-1 ring-[#00d2eb]' : 'hover:bg-white/[0.05]'} disabled:hover:bg-transparent disabled:cursor-default`}>
                  <span className={active ? 'text-white font-semibold' : n ? 'text-slate-300' : 'text-slate-500'}>{text(label)}</span>
                  <span className={`font-bold tabular-nums ${n ? 'text-white' : 'text-slate-500'}`}>{n}{id === 'unspecified' && f.countAtLeast ? '+' : ''}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** Görünüm skoru of a red-appearance finding (appearance-v1): the bar is the score; the raw affected area and colour
 * intensity are shown separately; a shared regional mask is said so; no score is invented when it is missing. */
function AppearanceValue({ f, color }: { f: SkinFinding; color: string }) {
  const { text, locale } = useTranslations();
  const a = f.appearance, nf = (v: number, d = 1) => new Intl.NumberFormat(locale, { maximumFractionDigits: d }).format(v);
  const pct = (v: number) => (locale.startsWith('tr') ? `%${nf(v)}` : locale.startsWith('de') ? `${nf(v)}\u00a0%` : `${nf(v)}%`);
  if (!a) return (
    <div className="flex flex-col gap-1 text-center" data-skin-appearance-unavailable={f.appearanceUnavailable || 'MISSING'}>
      <p className="text-[15px] leading-snug text-slate-400">{text('Görünüm skoru bu taramada hesaplanamadı.')}</p>
      {f.appearanceUnavailable === 'AFFECTED_MASK_NOT_AVAILABLE' && <p className="text-[13px] text-slate-500">{text('Bu bulgu için etkilenen cilt alanını piksel düzeyinde ayıran bir ölçüm yok.')}</p>}
    </div>
  );
  return (
    <div className="flex flex-col gap-2" data-skin-appearance={a.score}>
      <ScoreBar value={a.score} color={color} label={text('Görünüm skoru')} scale={['0', '50', '100']} plain />
      <p className="text-[14px] text-slate-300 text-center" data-skin-appearance-raw>
        {text('Etkilenen alan')}: <strong className="text-white tabular-nums">{pct(a.areaPct)}</strong> · {text('Renk yoğunluğu')}: <strong className="text-white tabular-nums">+{nf(a.intensity)}</strong>
      </p>
      {!!f.appearanceSharedWith?.length && <p className="text-[13px] text-slate-500 text-center" data-skin-appearance-shared={f.appearanceSharedWith.join(',')}>
        {text(`Aynı bölgesel kızarıklık ölçümü: ${f.appearanceSharedWith.map(id => text(FINDING_DEFS[id].label)).join(', ')}`)}
      </p>}
    </div>
  );
}

function ScoreBar({ value, color, label, scale, plain = false }: { value: number; color: string; label: string; scale: string[]; plain?: boolean }) {
  const { text } = useTranslations();
  const v = Math.round(Math.max(0, Math.min(100, value)));
  // keep the number inside the card at the ends of the bar
  const shift = v < 6 ? '0%' : v > 94 ? '-100%' : '-50%';
  return (
    <div className="flex flex-col gap-1.5" data-skin-finding-score={v}>
      <span className="text-[15px] font-semibold text-slate-400">{label}</span>
      <div className="relative h-8">
        <span className="absolute bottom-0 whitespace-nowrap text-xl font-extrabold text-white tabular-nums" style={{ left: `${v}%`, transform: `translateX(${shift})` }}>{plain ? v : text(`%${v}`)}</span>
      </div>
      <div className="relative h-2.5 rounded-full bg-[#1a2533]" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={v} aria-label={label}>
        <div className="h-full rounded-full" style={{ width: `${v}%`, background: color }} />
        <div className="absolute top-1/2 w-[18px] h-[18px] rounded-full bg-white border-4 -translate-x-1/2 -translate-y-1/2" style={{ left: `${v}%`, borderColor: color }} />
      </div>
      <div className="flex justify-between pt-1 text-[13px] text-slate-500">{scale.map(s => <span key={s}>{s}</span>)}</div>
    </div>
  );
}

/** History of the finding on this page: only values of the same kind and method version as this scan's exact value
 * (a measured absence counts as 0 for counts only; unknown scans are gaps, never 0). */
function History({ view, finding, current, history, scanAt, color }: { view: FindingViewId; finding: SkinFinding; current: SkinFindingsResult; history?: SkinFindingsHistoryEntry[]; scanAt: string; color: string }) {
  const { text, locale } = useTranslations();
  const entries = React.useMemo(() => (history || []).map(h => ({ at: h.at, res: { version: h.version || 'unknown', status: h.status, findings: h.findings, unavailable: h.unavailable } as SkinFindingsResult })), [history]);
  const scope = React.useMemo(() => scopeOf(finding.id, [current, ...entries.map(e => e.res)], VIEW_REGIONS[view]), [finding.id, current, entries, view]);
  const now: Measure = React.useMemo(() => measureOf(current, finding.id, scope), [current, finding.id, scope]);
  const all = React.useMemo(() => {
    if (!now.exact || now.value === undefined) return [];
    const rows = entries.flatMap(e => {
      const m = measureOf(e.res, finding.id, scope), c = compareMeasures(now, m);
      const v = ['up', 'down', 'same'].includes(c.kind) ? m.value : c.kind === 'new' && now.kind === 'count' ? 0 : undefined;
      return v === undefined || e.at === scanAt ? [] : [{ at: e.at, v }];
    });
    rows.push({ at: scanAt, v: now.value });
    return rows.sort((a, b) => a.at.localeCompare(b.at));
  }, [entries, finding.id, scope, now, scanAt]);
  const before = all.length > 1 ? all[all.length - 2] : undefined;
  const delta = before && now.kind === 'appearance' ? Math.round((now.value as number) - before.v) : undefined;
  const [range, setRange] = React.useState<DateRange | null>(null);
  const [picker, setPicker] = React.useState(false);
  const first = all.length ? new Date(all[0].at) : new Date(scanAt), last = new Date(scanAt);
  const from = range?.from || first, to = range?.to || last;
  const pts = all.filter(p => inDayRange(p.at, { from, to }));
  const fmt = (d: Date, year = false) => d.toLocaleDateString(locale, { day: 'numeric', month: 'short', ...(year ? { year: 'numeric' } : {}) });
  const W = 504, H = 160, X0 = 40, X1 = 480, Y0 = 10, Y1 = 132;
  const x = (i: number) => (pts.length < 2 ? (X0 + X1) / 2 : X0 + (X1 - X0) * i / (pts.length - 1));
  // counts: axis 0..(largest count rounded up to 10); scores: 0..100
  const isCount = now.kind === 'count', top = isCount ? Math.max(10, Math.ceil(Math.max(...all.map(p => p.v), 1) / 10) * 10) : 100;
  const y = (v: number) => Y1 - (Y1 - Y0) * Math.max(0, Math.min(top, v)) / top;
  const labelEvery = Math.max(1, Math.ceil(pts.length / 6));
  if (now.value === undefined) return null;   // no value in this scan: nothing to chart
  return (
    <div className="flex flex-col gap-2" data-skin-finding-history={pts.length}>
      {delta !== undefined && <p className="text-[15px] font-semibold text-slate-200" data-skin-appearance-change={delta}>
        {text(delta === 0 ? 'Görünüm skoru değişmedi.' : delta < 0 ? `Görünüm skoru ${-delta} puan azaldı.` : `Görünüm skoru ${delta} puan arttı.`)}
      </p>}
      <div className="flex items-center justify-between gap-3">
        <span className="text-[15px] font-semibold text-slate-400">{text('Geçmiş')}</span>
        <button type="button" aria-haspopup="dialog" onClick={() => setPicker(true)} data-skin-history-range
          className="min-h-11 rounded-xl bg-[#1a2533] hover:bg-[#223043] px-3 flex items-center gap-2 text-sm font-semibold text-slate-100">
          <CalendarDays aria-hidden="true" className="w-4 h-4 text-slate-300" />{fmt(from)} – {fmt(to, true)}
        </button>
      </div>
      {pts.length < 2
        ? <p className="rounded-2xl bg-[#131d2b] px-4 py-5 text-[15px] leading-snug text-slate-400 text-center" data-skin-history-empty>
            {text(!now.exact ? 'Bu taramanın değeri önceki taramalarla karşılaştırılamıyor.' : all.length < 2 ? 'Geçmiş grafiği bir sonraki taramanızdan sonra burada görünür.' : 'Seçilen tarih aralığında yeterli tarama yok.')}
          </p>
        : <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
            aria-label={text(isCount ? 'Sayı geçmişi' : now.kind === 'appearance' ? 'Görünüm skoru geçmişi' : 'Belirginlik geçmişi') + ': ' + pts.map(p => `${fmt(new Date(p.at))} ${isCount || now.kind === 'appearance' ? Math.round(p.v) : text(`%${Math.round(p.v)}`)}`).join(', ')}>
            {[top, top / 2, 0].map(v => (
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
