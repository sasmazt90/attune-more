'use client';
import React from 'react';
import Link from 'next/link';
import { ChevronRight, Info } from 'lucide-react';
import { useTranslations } from '../../i18n/LanguageProvider';
import { FINDING_DEFS, UNAVAILABLE_REASON_TEXT, countUnit, findingColor, validFindings } from '../../utils/skinFindings';
import { compareRecords, formatValue, skinTypeLabel, type Change, type Measure, type SkinRecord } from '../../utils/skinHistorySummary';

const WHY: Record<string, string> = {
  DIFFERENT_MEASURE: 'farklı ölçü türü', DIFFERENT_METHOD: 'farklı yöntem sürümü', NO_EXACT_COUNT: 'kesin sayı yok',
  PARTIAL_REGIONS: 'bölgelerin bir kısmı ölçülemedi', NO_VALUE: 'değer yok',
};

/** Sağlık Geçmişim → one skin analysis: findings seen now or in the scan just before, compared only when the two values
 * are exact, of the same kind and from the same method (skinHistorySummary.compareRecords). */
export function SkinRecordComparison({ record, previous, careHref }: { record: SkinRecord; previous?: SkinRecord; careHref?: string }) {
  const { text, locale } = useTranslations();
  const [open, setOpen] = React.useState(false);
  const rows = compareRecords(record, previous);
  const res = record.general?.findings;
  const unavailable = validFindings(res) ? res.unavailable || [] : [];
  const type = skinTypeLabel(record), prevType = previous ? skinTypeLabel(previous) : null;
  const when = (t?: string) => (t ? new Date(t).toLocaleString(locale, { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
  const unit = (id: keyof typeof FINDING_DEFS, m: Measure) =>
    m.kind === 'count' ? countUnit(formatValue(m, locale), FINDING_DEFS[id].unit, text) : m.kind === 'appearance' ? text('görünüm skoru') : m.kind === 'area' ? text('alan') : '';
  const nowCell = (id: keyof typeof FINDING_DEFS, m: Measure) => {
    if (m.state === 'seen') return <><strong className="text-[17px] text-white">{formatValue(m, locale)}</strong>{m.value !== undefined && unit(id, m) && <span className="text-[13px] text-slate-400"> {unit(id, m)}</span>}</>;
    if (m.state === 'notSeen') return <span className="text-slate-400">—</span>;
    return <span className="text-[14px] font-semibold text-amber-200">{text(m.state === 'inconclusive' ? 'Kesinleştirilemedi' : 'Ölçülemedi')}</span>;
  };
  const prevText = (c: Change) => (c.previous && c.previous.state === 'seen' ? <span className="text-[13px] font-medium text-slate-400"> · {text(`önceki ${formatValue(c.previous, locale)}`)}</span> : null);
  const change = (c: Change, m: Measure) => {
    const n = c.delta !== undefined ? new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(c.delta) : '';
    switch (c.kind) {
      case 'up': case 'down':
        if (m.kind === 'appearance') return <span className={c.kind === 'up' ? 'text-rose-400' : 'text-emerald-400'}>{text(c.kind === 'up' ? `Görünüm skoru ${n} puan arttı.` : `Görünüm skoru ${n} puan azaldı.`)}</span>;
        return <><span className={c.kind === 'up' ? 'text-rose-400' : 'text-emerald-400'}>{c.kind === 'up' ? '↑' : '↓'} {m.kind === 'count' ? n : text(`${n} puan`)}</span>{prevText(c)}</>;
      case 'same': return <><span className="text-slate-400">= {text('aynı')}</span>{prevText(c)}</>;
      case 'new': return <><span className="text-slate-100">{text('Yeni')}</span><span className="text-[13px] font-medium text-slate-400"> · {text('önceki taramada görülmedi')}</span></>;
      case 'gone': return <><span className="text-emerald-400">{text('Görülmedi')}</span>{prevText(c)}</>;
      case 'unknownNow': return <><span className="text-slate-500">—</span>{prevText(c)}</>;
      case 'noPrevious': return <span className="text-[13px] font-medium text-slate-400">{text('önceki taramada ölçülemedi')}</span>;
      case 'incomparable': return <><span className="text-[13px] font-medium text-slate-400">{text('karşılaştırılamaz')} · {text(WHY[c.why || ''] || 'değer yok')}</span>{prevText(c)}</>;
      default: return <span className="text-slate-500">—</span>;
    }
  };
  const grid = 'grid grid-cols-[14px_minmax(0,1fr)_minmax(110px,auto)_minmax(170px,auto)] items-center gap-x-4 px-4';
  return (
    <div className="space-y-4" data-skin-record-comparison={record.id}>
      <p className="text-sm text-slate-400" data-skin-compare-with={previous ? 'previous' : 'none'}>
        {previous ? text(`Karşılaştırma: bir önceki tarama (${when(previous.timestamp)})`) : text('İlk tarama: karşılaştırılacak önceki tarama yok.')}
      </p>
      {type && <p className="inline-flex flex-wrap items-center gap-2 rounded-full bg-[#131d2b] px-4 py-2 text-sm text-slate-300">
        {text('Cilt tipi')}: <strong className="text-white">{text(type)}</strong>{previous && prevType && <span className="text-slate-400">({text(`önceki: ${prevType}`)})</span>}
      </p>}
      <div className="rounded-2xl bg-[#0f1724] py-1" role="table" aria-label={text('Bulgular')}>
        <div className={`${grid} py-2.5 text-[13px] text-slate-400`} role="row">
          <span aria-hidden="true" /><span role="columnheader">{text('Bulgu')}</span>
          <span role="columnheader" className="text-right">{text('Son tarama')}</span>
          <span role="columnheader" className="text-right">{text('Önceki taramaya göre')}</span>
        </div>
        {rows.map(r => (
          <div key={r.id} role="row" data-skin-compare-row={r.id} data-skin-compare-change={r.change.kind} data-skin-compare-now={r.now.state}
            className={`${grid} border-t border-white/[0.06] py-3 ${r.now.state !== 'seen' ? 'opacity-70' : ''}`}>
            <span className="h-3 w-3 rounded-full" style={{ background: r.now.state === 'seen' ? findingColor(r.id) : '#94a3b8' }} aria-hidden="true" />
            <span role="cell" className="min-w-0"><span className="block text-[16px] font-bold text-white">{text(r.label)}</span>
              {!!r.views.length && <span className="block text-[13px] text-slate-400">{r.views.map(v => text(v)).join(', ')}</span>}</span>
            <span role="cell" className="whitespace-nowrap text-right tabular-nums">{nowCell(r.id, r.now)}</span>
            <span role="cell" className="whitespace-nowrap text-right text-[15px] font-bold tabular-nums">{change(r.change, r.now)}</span>
          </div>
        ))}
        {!rows.length && <p className="border-t border-white/[0.06] px-4 py-4 text-sm text-slate-400" data-skin-compare-empty>{text(validFindings(res) && res.status !== 'unavailable' && res.findings.some(f => f.status === 'notSeen') && !res.findings.some(f => f.status === 'inconclusive') ? 'Bu taramada görülen bulgu yok.' : 'Bu taramada bulgular ölçülemedi.')}</p>}
      </div>
      {!!unavailable.length && (
        <div className="rounded-2xl bg-[#0f1724]">
          <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex min-h-[52px] w-full items-center justify-between gap-3 px-4 text-[15px] font-semibold text-slate-200">
            <span className="flex items-center gap-2.5"><Info aria-hidden="true" className="h-5 w-5 text-slate-400" />{text(`${unavailable.length} bulgu ölçülemedi`)}</span>
            <span className="flex items-center gap-1 text-slate-300">{text('Ayrıntılar')}<ChevronRight aria-hidden="true" className={`h-5 w-5 transition-transform ${open ? 'rotate-90' : ''}`} /></span>
          </button>
          {open && <ul className="space-y-1.5 px-4 pb-3 text-sm">{unavailable.map(u => (
            <li key={u.id} className="flex flex-wrap justify-between gap-x-4"><span className="text-slate-200">{text(FINDING_DEFS[u.id].label)}</span><span className="text-slate-400">{text(UNAVAILABLE_REASON_TEXT[u.reason] || UNAVAILABLE_REASON_TEXT.MODEL_NOT_AVAILABLE || u.reason)}</span></li>
          ))}</ul>}
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        {careHref && <Link href={careHref} className="flex min-h-[52px] flex-1 items-center justify-center rounded-2xl bg-[#162130] px-5 text-base font-bold text-slate-100 hover:bg-[#1d2a3c]">{text('Uzman seçenekleri')}</Link>}
        <Link href={`/skin?view=record&id=${encodeURIComponent(record.id)}`} data-skin-open-result
          className="flex min-h-[52px] flex-[1.4] items-center justify-center rounded-2xl bg-[#00d2eb] px-5 text-base font-bold text-slate-950 hover:bg-[#22dcf0]">
          {text('Sonuç ekranında aç')}<ChevronRight aria-hidden="true" className="ml-1 h-5 w-5" />
        </Link>
      </div>
    </div>
  );
}
