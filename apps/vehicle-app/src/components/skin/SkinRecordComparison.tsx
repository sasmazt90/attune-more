'use client';
import React from 'react';
import Link from 'next/link';
import { ChevronRight, Info } from 'lucide-react';
import { useTranslations } from '../../i18n/LanguageProvider';
import { FINDING_DEFS, UNAVAILABLE_REASON_TEXT, countUnit, findingColor, validFindings } from '../../utils/skinFindings';
import { compareWithPrevious, formatMetric, skinTypeLabel, type Change, type FindingRow } from '../../utils/skinHistorySummary';

type SkinRecord = Parameters<typeof compareWithPrevious>[0];

/** Sağlık Geçmişim → one skin analysis: every seen finding with its value, compared with the scan just before it. */
export function SkinRecordComparison({ record, previous, careHref }: { record: SkinRecord & { id: string }; previous?: SkinRecord & { timestamp?: string }; careHref?: string }) {
  const { text, locale } = useTranslations();
  const [open, setOpen] = React.useState(false);
  const { rows, gone } = compareWithPrevious(record, previous, locale);
  const res = record.general?.findings;
  const unavailable = validFindings(res) ? res.unavailable || [] : [];
  const type = skinTypeLabel(record), prevType = previous ? skinTypeLabel(previous) : null;
  const when = (t?: string) => (t ? new Date(t).toLocaleString(locale, { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '');
  const value = (r: FindingRow) => formatMetric(r, locale);
  const unit = (r: FindingRow) => (r.kind === 'count' ? countUnit(formatMetric(r, locale), FINDING_DEFS[r.id].unit, text) : r.kind === 'area' ? text('alan') : '');
  const change = (c: Change, kind?: string) => {
    const n = c.delta !== undefined ? new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(c.delta) : '';
    const was = c.previous ? <span className="text-[13px] font-medium text-slate-400"> · {text(`önceki ${c.previous}`)}</span> : null;
    switch (c.kind) {
      case 'up': return <><span className="text-rose-400">↑ {kind === 'count' ? n : text(`${n} puan`)}</span>{was}</>;
      case 'down': return <><span className="text-emerald-400">↓ {kind === 'count' ? n : text(`${n} puan`)}</span>{was}</>;
      case 'same': return <><span className="text-slate-400">= {text('aynı')}</span>{was}</>;
      case 'new': return <><span className="text-slate-100">{text('Yeni')}</span><span className="text-[13px] font-medium text-slate-400"> · {text('önceki taramada yoktu')}</span></>;
      case 'gone': return <><span className="text-emerald-400">{text('Görülmedi')}</span>{was}</>;
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
        {[...rows, ...gone].map(r => (
          <div key={r.id} role="row" data-skin-compare-row={r.id} data-skin-compare-change={r.change.kind}
            className={`${grid} border-t border-white/[0.06] py-3 ${r.change.kind === 'gone' ? 'opacity-60' : ''}`}>
            <span className="h-3 w-3 rounded-full" style={{ background: r.change.kind === 'gone' ? '#94a3b8' : findingColor(r.id) }} aria-hidden="true" />
            <span role="cell" className="min-w-0"><span className="block text-[16px] font-bold text-white">{text(r.label)}</span>
              {!!r.views.length && <span className="block text-[13px] text-slate-400">{r.views.map(v => text(v)).join(', ')}</span>}</span>
            <span role="cell" className="whitespace-nowrap text-right tabular-nums"><strong className="text-[17px] text-white">{value(r)}</strong>
              {r.metric !== undefined && unit(r) && <span className="text-[13px] text-slate-400"> {unit(r)}</span>}</span>
            <span role="cell" className="whitespace-nowrap text-right text-[15px] font-bold tabular-nums">{change(r.change, r.kind)}</span>
          </div>
        ))}
        {!rows.length && !gone.length && <p className="border-t border-white/[0.06] px-4 py-4 text-sm text-slate-400">{text('Bu taramada görülen bulgu yok.')}</p>}
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
