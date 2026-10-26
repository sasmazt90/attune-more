'use client';
import {getLocale} from '../i18n/core';
import {useTranslations} from '../i18n/LanguageProvider';


import { useEffect, useMemo, useState, useId, type ReactNode } from 'react';
import { HEALTH_MODULES, HEALTH_MODULE_IDS, type HealthModule } from '../utils/healthModules';
import { prepareHealthRecords } from '../utils/healthRecords';
import { buildHistorySeries, emptyHistoryRecords, formatHistoryValue, historyTime, moduleOverview, recordsInRange, sessionCountSeries, themeDistribution, type HistoryPoint, type HistoryRecords, type HistorySeries } from '../utils/healthHistorySeries';
import { HealthModuleIcon } from './HealthModuleIcon';
import { AccessibleDialog } from './AccessibleDialog';
import { CardCarousel } from './CardCarousel';
import Link from 'next/link';
import { skinAverages, formatValue } from '../utils/skinHistorySummary';
import { FINDING_DEFS, countUnit } from '../utils/skinFindings';

const datetime = (time: number) => new Date(time).toLocaleString(getLocale(), { dateStyle: 'medium', timeStyle: 'medium' });
const selectClass = 'min-h-11 w-full rounded-xl border border-white/20 bg-slate-950 px-3 text-sm text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-togg-turquoise';
const colors = ['#00c2e7', '#a78bfa', '#34d399', '#fb923c', '#f472b6', '#60a5fa'];

export function HistoryChart({ series, kind }: { series: HistorySeries; kind: 'line' | 'bar' }) {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const [active, setActive] = useState<HistoryPoint | null>(null);
  const tooltipId = useId();
  const points = series.points, valid = points.filter(p => p.value !== null);
  if (!valid.length) return <p className="py-12 text-center text-sm text-slate-400">{i18nText("Seçilen aralıkta karşılaştırılabilir ölçüm yok.")}</p>;
  const left = 66, right = 736, top = 22, bottom = 208;
  const t0 = points[0].time, t1 = points[points.length - 1].time;
  const low = Math.min(0, ...valid.map(p => p.value!)), high = series.unit === '%' ? Math.max(100, ...valid.map(p => p.value!)) : Math.max(1, ...valid.map(p => p.value!));
  const x = (time: number) => t1 === t0 ? (left + right) / 2 : left + (time - t0) / (t1 - t0) * (right - left);
  const y = (value: number) => bottom - (value - low) / (high - low) * (bottom - top);
  const paths: string[] = []; let segment = '';
  for (const p of points) {
    if (p.value === null) { if (segment) paths.push(segment); segment = ''; }
    else segment += `${segment ? ' L' : 'M'}${x(p.time)},${y(p.value)}`;
  }
  if (segment) paths.push(segment);
  const gaps = points.length - valid.length, last = valid[valid.length - 1];
  return <div className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2 text-sm"><p>{i18nText("Son ölçüm: ")}<strong>{i18nNode(formatHistoryValue(last.value!, series.unit))}</strong></p><p className="text-slate-400">{i18nNode(valid.length)}{i18nText(" ölçüm")}{i18nNode(gaps ? ` · ${gaps} ölçüm boşluğu` : '')}{i18nNode(valid.length === 1 ? ' · tek nokta' : '')}</p></div>
    <div className="relative">
    <svg viewBox="0 0 760 246" className="w-full min-w-0" role="group" aria-label={i18nText(`${series.label}, ${series.regionLabel}, zaman grafiği`)}>
      {[0, .5, 1].map(f => { const v = low + (high - low) * f; return <g key={f}><line x1={left} x2={right} y1={y(v)} y2={y(v)} stroke="#334155" strokeDasharray="3 4"/><text x={left - 8} y={y(v) + 4} textAnchor="end" fill="#94a3b8" fontSize="12">{i18nNode(new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 1 }).format(v))}</text></g>; })}
      <text x={left} y="237" fill="#94a3b8" fontSize="12">{i18nNode(new Date(t0).toLocaleDateString(getLocale()))}</text><text x={right} y="237" textAnchor="end" fill="#94a3b8" fontSize="12">{i18nNode(new Date(t1).toLocaleDateString(getLocale()))}</text>
      {kind === 'line' && paths.map((d, i) => <path key={i} d={d} fill="none" stroke="#00c2e7" strokeWidth="2.5"/>)}
      {points.map(p => p.value === null ? <g key={p.id}><line x1={x(p.time) - 3} x2={x(p.time) + 3} y1={bottom - 3} y2={bottom + 3} stroke="#94a3b8"/><line x1={x(p.time) - 3} x2={x(p.time) + 3} y1={bottom + 3} y2={bottom - 3} stroke="#94a3b8"/></g> : <g key={p.id}>
        {kind === 'bar' && <rect x={x(p.time) - Math.min(14, 230 / valid.length)} y={Math.min(y(0), y(p.value))} width={Math.min(28, 460 / valid.length)} height={Math.max(1, Math.abs(y(0) - y(p.value)))} fill="#00c2e7" opacity=".65" rx="3"/>}
        <circle cx={x(p.time)} cy={y(p.value)} r={active?.id === p.id ? 7 : 5} fill="#00c2e7" stroke="#0b1320" strokeWidth="2" tabIndex={0} role="button" aria-describedby={active?.id === p.id ? tooltipId : undefined} aria-label={i18nText(`${datetime(p.time)} · ${series.label} · ${series.regionLabel} · ${formatHistoryValue(p.value, series.unit)}`)} onMouseEnter={() => setActive(p)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(p)} onBlur={() => setActive(null)} onClick={() => setActive(p)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActive(p); } if (e.key === 'Escape') setActive(null); }}/>
      </g>)}
    </svg>
    {active && <div id={tooltipId} role="tooltip" className="pointer-events-none absolute left-3 right-3 top-3 z-10 max-w-md rounded-xl border border-togg-turquoise/40 bg-slate-950/95 p-3 text-sm shadow-xl">
      <p className="text-slate-400">{i18nNode(datetime(active.time))}</p><p>{i18nNode(series.label)}{i18nNode(series.regionLabel && ` · ${series.regionLabel}`)}: <strong>{i18nNode(formatHistoryValue(active.value!, series.unit))}</strong></p>
    </div>}
    </div>
    <p className="text-xs text-slate-400">{i18nText("Ayrıntı için bir noktaya dokunun veya klavyeyle odaklanın.")}{i18nNode(valid.length === 1 && ' Tek ölçüm değişim eğilimi göstermez.')}</p>
  </div>;
}

function ThemeChart({ distribution, kind }: { distribution: ReturnType<typeof themeDistribution>; kind: 'donut' | 'bar' }) {
 const {text:i18nText,node:i18nNode}=useTranslations();
  if (!distribution.total) return <p className="py-12 text-center text-sm text-slate-400">{i18nText("Bu aralıkta kayıtlı tema yok.")}</p>;
  let offset = 0;
  return <div className="grid items-center gap-6 sm:grid-cols-2">
    {kind === 'donut' && <svg viewBox="0 0 240 240" className="mx-auto w-full max-w-64" role="img" aria-label={i18nText("Ruh Sağlığı tema dağılımı")}>
      {distribution.rows.map((row, index) => { const length = row.count / distribution.total * 100, start = offset; offset += length; return <circle key={row.label} cx="120" cy="120" r="86" fill="none" stroke={colors[index % colors.length]} strokeWidth="32" pathLength="100" strokeDasharray={`${length} ${100 - length}`} strokeDashoffset={-start} transform="rotate(-90 120 120)"><title>{i18nNode(row.label)}: {i18nNode(row.percent)}% · {i18nNode(row.count)}{i18nText(" katkı")}</title></circle>; })}
      <text x="120" y="119" textAnchor="middle" fill="white" fontSize="24">{i18nNode(distribution.total)}</text><text x="120" y="142" textAnchor="middle" fill="#94a3b8" fontSize="12">{i18nText("tema katkısı")}</text>
    </svg>}
    <ul className={`space-y-4 ${kind === 'bar' ? 'sm:col-span-2' : ''}`}>{distribution.rows.map((row, index) => <li key={row.label}><div className="flex items-start justify-between gap-3 text-sm"><span className="flex min-w-0 items-start gap-2"><span className="mt-1 h-3 w-3 shrink-0 rounded-full" style={{ background: colors[index % colors.length] }}/>{i18nNode(row.label)}</span><strong className="shrink-0">{i18nNode(row.percent)}%</strong></div><p className="pl-5 text-xs text-slate-400">{i18nNode(row.count)}{i18nText(" görüşme katkısı / ")}{i18nNode(distribution.total)}{i18nText(" tema katkısı")}</p>{kind === 'bar' && <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full" style={{ width: `${row.count / distribution.total * 100}%`, background: colors[index % colors.length] }}/></div>}</li>)}</ul>
  </div>;
}

function AnalysisPanel({ module, records }: { module: HealthModule; records: HistoryRecords[HealthModule] }) {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const [range, setRange] = useState('all'), [criterionChoice, setCriterion] = useState(''), [regionChoice, setRegion] = useState(''), [sourceChoice, setSource] = useState(''), [methodChoice, setMethod] = useState(''), [chart, setChart] = useState('line');
  const ranged = useMemo(() => recordsInRange(records, range === 'all' ? null : Number(range)), [records, range]);
  const allSeries = useMemo(() => buildHistorySeries(module, ranged), [module, ranged]);
  const criteria = module === 'mental' ? [{ id: 'sessions', label: 'Kayıtlı görüşme sayısı' }, { id: 'themes', label: 'Tema dağılımı' }] : [...new Map(allSeries.map(s => [s.criterion, { id: s.criterion, label: s.label }])).values()];
  const criterion = criteria.some(c => c.id === criterionChoice) ? criterionChoice : criteria.find(c => c.id === 'combined')?.id || criteria[0]?.id || '';
  const scoped = allSeries.filter(s => s.criterion === criterion);
  const regions = [...new Map(scoped.map(s => [s.region, s.regionLabel])).entries()];
  const region = regions.some(([id]) => id === regionChoice) ? regionChoice : regions[0]?.[0] || '';
  const regionSeries = scoped.filter(s => s.region === region);
  const sources = [...new Set(regionSeries.map(s => s.source).filter(Boolean))];
  const source = sources.includes(sourceChoice) ? sourceChoice : sources[0] || '';
  const comparable = regionSeries.filter(s => !source || s.source === source);
  const selected = comparable.find(s => s.id === methodChoice) || comparable[0];
  const themes = module === 'mental' && criterion === 'themes';
  const kind = themes ? chart === 'bar' ? 'bar' : 'donut' : chart === 'bar' ? 'bar' : 'line';
  const series = module === 'mental' && !themes ? sessionCountSeries(ranged) : selected;
  const distribution = useMemo(() => themeDistribution(ranged), [ranged]);
  const hasRangeRecords = ranged.some(r => historyTime(r) !== null);
  return <section id="health-history-analysis" className="rounded-2xl border border-white/10 bg-cockpit-surface p-5 space-y-5" aria-label={i18nText(`${HEALTH_MODULES[module].name} zaman içinde değişim`)}>
    <div className="flex flex-wrap items-center gap-3"><h2 className="text-lg font-bold">{i18nNode(HEALTH_MODULES[module].name)}</h2><details className="relative shrink-0"><summary tabIndex={0} aria-label={i18nText("Kayıtların karşılaştırılması hakkında bilgi")} className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-full border border-white/20 text-togg-turquoise focus-visible:outline focus-visible:outline-2 focus-visible:outline-togg-turquoise"><span aria-hidden="true">ⓘ</span></summary><div className="absolute left-0 top-full z-20 mt-2 w-72 max-w-[calc(100vw-4rem)] rounded-xl border border-white/20 bg-slate-950 p-4 text-sm text-slate-300 shadow-xl space-y-3"><p>{i18nText("Yalnız kayıtlı ölçümler gösterilir. Eksik ölçümler çizgiyi keser; tek nokta eğilim göstermez. Farklı yöntem, birim, cihaz ve protokoller ayrı serilerde tutulur.")}</p>{module === 'skin' && <p>{i18nText("0–100 değerleri görünüm indeksidir; klinik şiddet veya hastalık olasılığı değildir. Kişisel referans farkı ayrı ölçümdür.")}</p>}{module === 'hearing' && <p>{i18nText("Dijital dBFS peak ile dB SNR ayrı ölçümlerdir; klinik dB HL değildir. Cihaz, kulaklık ve hazırlık koşulları karşılaştırmayı sınırlar.")}</p>}{module === 'mental' && <p>{i18nText("Her tema bir görüşmeden en fazla bir katkı alır. Dağılımın paydası tüm tema katkılarıdır; tema kaydı olmayan görüşmelere kategori atanmaz.")}</p>}{module === 'dental' && <p>{i18nText("Çürük adayları doğrulanmış hastalık değildir. Görünüm kaynağı, model ve eşik uyumu karşılaştırmayı sınırlar.")}</p>}{module === 'vision' && <p>{i18nText("Harf/yön doğruluğunun paydası geçerli denemelerdir. Göz ve gerçek render boyutu ayrı tutulur; klinik görme keskinliği türetilmez.")}</p>}</div></details><p className="w-full text-sm text-slate-400">{i18nText("Zaman içinde değişim")}</p></div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <label className="space-y-1 text-xs text-slate-400">{i18nText("Tarih aralığı")}<select className={selectClass} value={range} onChange={e => setRange(e.target.value)}><option value="7">{i18nText("Son 7 gün")}</option><option value="30">{i18nText("Son 30 gün")}</option><option value="all">{i18nText("Tümü")}</option></select></label>
      {criteria.length > 0 && <label className="space-y-1 text-xs text-slate-400">{i18nText("Ölçüm")}<select className={selectClass} value={criterion} onChange={e => { setCriterion(e.target.value); setRegion(''); setMethod(''); }} >{criteria.map(c => <option key={c.id} value={c.id}>{i18nNode(c.label)}</option>)}</select></label>}
      {regions.length > 0 && <label className="space-y-1 text-xs text-slate-400">{i18nNode(module === 'vision' ? 'Göz' : module === 'hearing' ? 'Kulak / frekans' : module === 'dental' ? 'Görünüm / sıra' : 'Bölge')}<select className={selectClass} value={region} onChange={e => { setRegion(e.target.value); setMethod(''); }}>{regions.map(([id, label]) => <option key={id} value={id}>{i18nNode(label)}</option>)}</select></label>}
      {sources.length > 1 && <label className="space-y-1 text-xs text-slate-400">{i18nText("Fotoğraf kaynağı")}<select className={selectClass} value={source} onChange={e => { setSource(e.target.value); setMethod(''); }}>{sources.map(s => <option key={s}>{i18nNode(s)}</option>)}</select></label>}
      {comparable.length > 1 && <label className="space-y-1 text-xs text-slate-400 sm:col-span-2">{i18nText("Karşılaştırılabilir seri")}<select className={selectClass} value={selected?.id || ''} onChange={e => setMethod(e.target.value)}>{comparable.map((s, index) => <option key={s.id} value={s.id}>{i18nText("Seri ")}{i18nNode(index + 1)} · {i18nNode(new Date(s.points.find(p => p.value !== null)?.time || s.points[0].time).toLocaleDateString(getLocale()))}</option>)}</select></label>}
      {(series || themes) && <label className="space-y-1 text-xs text-slate-400">{i18nText("Grafik")}<select className={selectClass} value={kind} onChange={e => setChart(e.target.value)}>{themes ? <option value="donut">{i18nText("Tema halkası")}</option> : <option value="line">{i18nText("Çizgi")}</option>}<option value="bar">{i18nText("Çubuk")}</option></select></label>}
    </div>
    {!hasRangeRecords ? <p className="py-12 text-center text-sm text-slate-400">{i18nNode(records.length ? 'Seçilen tarih aralığında kayıt yok.' : 'Henüz kayıt yok.')}</p> : themes ? <ThemeChart distribution={distribution} kind={kind === 'bar' ? 'bar' : 'donut'}/> : series ? <HistoryChart key={JSON.stringify([series.id, series.points, kind])} series={series} kind={kind === 'bar' ? 'bar' : 'line'}/> : <p className="py-12 text-center text-sm text-slate-400">{i18nText("Kayıtlarda grafik için desteklenen sayısal ölçüm yok.")}</p>}
  </section>;
}

export function HealthHistoryOverview({ showStartActions = false, parked = true, extraCard }: { showStartActions?: boolean; parked?: boolean; extraCard?: ReactNode }) {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const [records, setRecords] = useState<HistoryRecords>(emptyHistoryRecords), [module, setModule] = useState<HealthModule | null>(null), [error, setError] = useState(false);
  useEffect(() => {
    let version = 0, disposed = false;
    const refresh = async () => { const current = ++version; const results = await Promise.allSettled(HEALTH_MODULE_IDS.map(id => prepareHealthRecords(id))); if (disposed || current !== version) return; const next = emptyHistoryRecords(); results.forEach((r, i) => { if (r.status === 'fulfilled') next[HEALTH_MODULE_IDS[i]] = r.value; }); setError(results.some(r => r.status === 'rejected')); setRecords(next); };
    void refresh(); window.addEventListener('attune-records', refresh); window.addEventListener('storage', refresh);
    return () => { disposed = true; version++; window.removeEventListener('attune-records', refresh); window.removeEventListener('storage', refresh); };
  }, []);
  const skinAvg = useMemo(() => skinAverages(records.skin as any), [records.skin]);
  const cards: { id: string; content: ReactNode }[] = HEALTH_MODULE_IDS.map(id => {
    const overview = moduleOverview(id, records[id]), selected = module === id;
    return { id, content: <article className={`flex w-full flex-col rounded-2xl border bg-cockpit-surface transition-colors ${selected ? 'border-togg-turquoise' : 'border-white/10 hover:border-white/30'}`}>
      <button type="button" aria-haspopup="dialog" aria-expanded={selected} onClick={() => setModule(id)} className="flex min-h-44 w-full flex-1 flex-col items-start rounded-2xl p-4 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-togg-turquoise" data-health-module={id}>
        <span className="flex min-w-0 items-start gap-2 text-sm font-bold text-togg-turquoise"><span className="shrink-0 pt-0.5"><HealthModuleIcon module={id}/></span><span>{i18nNode(HEALTH_MODULES[id].name)}</span></span>
        {id === 'skin' && skinAvg ? <SkinAverages avg={skinAvg} /> : <>
        <span className="mt-3 flex-1 text-sm leading-relaxed text-slate-300">{i18nNode(overview.text)}</span><span className="mt-3 text-xs text-slate-400">{i18nNode(overview.date !== null ? new Date(overview.date).toLocaleDateString(getLocale()) : overview.count ? 'Tarih kaydedilmemiş' : 'Kayıt yok')}</span></>}
      </button>
      {showStartActions && <div className="mx-4 mb-4 border-t border-white/10 pt-3">{parked || id === 'mental' ? <Link href={HEALTH_MODULES[id].route} className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-togg-turquoise px-3 text-xs font-semibold text-togg-darkBlue focus-visible:outline focus-visible:outline-2 focus-visible:outline-white">{i18nNode(!parked ? 'Görüşmeyi görüntüle' : id === 'mental' ? 'Görüşmeyi başlat' : 'Kontrolü aç')}</Link> : <p className="py-3 text-center text-xs text-slate-500">{i18nText("Park halinde açılır")}</p>}</div>}
    </article> };
  });
  if (extraCard) cards.push({ id: 'care', content: <>{i18nNode(extraCard)}</> });
  return <div data-health-history className="min-w-0">
    <CardCarousel label="Sağlık modülleri" items={cards}/>
    {error && <p role="alert" className="mt-3 text-sm text-amber-300">{i18nText("Bazı kayıtlar okunamadı; mevcut veriler değiştirilmedi.")}</p>}
    {module && <AccessibleDialog title={i18nText(`${HEALTH_MODULES[module].name} geçmiş grafikleri`)} onClose={() => setModule(null)} className="w-full max-w-4xl rounded-2xl border border-white/20 bg-cockpit-surface p-4 space-y-3">
      <div data-health-history className="space-y-3">
        <div className="flex items-center justify-between gap-3"><label className="min-w-0 text-xs text-slate-400">{i18nText("Sağlık modülü")}<select className={selectClass} value={module} onChange={e => setModule(e.target.value as HealthModule)}>{HEALTH_MODULE_IDS.map(id => <option key={id} value={id}>{i18nNode(HEALTH_MODULES[id].name)}</option>)}</select></label><button type="button" aria-label={i18nText("Grafik penceresini kapat")} onClick={() => setModule(null)} className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-white/20 text-slate-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-togg-turquoise">✕</button></div>
        <AnalysisPanel key={module} module={module} records={records[module]}/>
      </div>
    </AccessibleDialog>}
  </div>;
}

/** Skin card: average of the last scans with measured findings (counts over every scan that measured them,
 * scores over the scans where the finding was seen), the most frequent skin type, and the scan count. */
function SkinAverages({ avg }: { avg: NonNullable<ReturnType<typeof skinAverages>> }) {
  const { text, locale } = useTranslations();
  return <span className="mt-2 flex w-full flex-1 flex-col gap-1.5 text-sm" data-skin-averages={avg.scans}>
    <span className="text-xs text-slate-400">{text(`Son ${avg.scans} taramanın ortalaması`)}</span>
    {avg.skinType && <span className="flex justify-between gap-3 text-slate-300"><span>{text('Cilt tipi')}</span><strong className="text-white">{text(avg.skinType)}</strong></span>}
    {avg.rows.filter(r => r.value !== undefined).slice(0, 3).map(r => <span key={r.id} className="flex justify-between gap-3 text-slate-300" data-skin-average={r.id} data-skin-average-used={r.used}>
      <span className="truncate">{text(r.label)}{r.used < avg.scans && <span className="text-xs text-slate-500"> {text(`(${r.used} tarama)`)}</span>}</span>
      <strong className="whitespace-nowrap tabular-nums text-white">{formatValue(r, locale)}{r.kind === 'count' && <> {countUnit(formatValue(r, locale), FINDING_DEFS[r.id].unit, text)}</>}{r.kind === 'appearance' && <span className="text-xs font-normal text-slate-400"> {text('görünüm skoru')}</span>}</strong></span>)}
    {!avg.rows.some(r => r.value !== undefined) && <span className="text-slate-300">{text('Bu taramalarda karşılaştırılabilir bulgu değeri yok.')}</span>}
    <span className="mt-auto pt-2 text-xs text-slate-400">{text(`${avg.scans} tarama · son ${new Date(avg.latest).toLocaleDateString(getLocale())}`)}</span>
  </span>;
}
