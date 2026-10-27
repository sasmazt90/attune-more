'use client';
import React from 'react';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useTranslations } from '../../i18n/LanguageProvider';
import { AccessibleDialog } from '../AccessibleDialog';

export type DateRange = { from: Date; to: Date };
const WEEKDAYS: Record<string, string[]> = { tr: ['Pt', 'Sa', 'Ça', 'Pe', 'Cu', 'Ct', 'Pz'], en: ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'], de: ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'] };
const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const same = (a: Date, b: Date) => day(a).getTime() === day(b).getTime();
/** Whole local days: from 00:00 of the first day to the end of the last day (no hours of the previous day). */
export function inDayRange(at: string | Date, range: DateRange): boolean {
  const t = new Date(at).getTime(), start = day(range.from).getTime();
  const end = new Date(range.to.getFullYear(), range.to.getMonth(), range.to.getDate() + 1).getTime();
  return t >= start && t < end;
}
/** Two taps choose a range: the first starts a new range, the second ends it (an earlier day swaps the ends). */
export function nextRange(from: Date, to: Date | null, d: Date): { from: Date; to: Date | null } {
  if (to) return { from: d, to: null };
  return d < from ? { from: d, to: from } : { from, to: d };
}

/** Date range for the history chart: quick presets and a month calendar (dots mark scan days). */
export function SkinDateRangeDialog({ scans, value, onApply, onClose }: { scans: string[]; value: DateRange; onApply: (r: DateRange) => void; onClose: () => void }) {
  const { text, locale, language } = useTranslations();
  const today = day(new Date());
  const [from, setFrom] = React.useState(day(value.from));
  const [to, setTo] = React.useState<Date | null>(day(value.to));
  const [month, setMonth] = React.useState(new Date(value.to.getFullYear(), value.to.getMonth(), 1));
  const scanDays = scans.map(s => day(new Date(s)));
  const preset = (days: number | null) => {
    const f = days === null ? (scanDays[0] || today) : new Date(today.getTime() - days * 86400000);
    setFrom(day(f)); setTo(today); setMonth(new Date(today.getFullYear(), today.getMonth(), 1));
  };
  const pick = (d: Date) => {
    const r = nextRange(from, to, d); setFrom(r.from); setTo(r.to);
  };
  const first = (month.getDay() + 6) % 7, count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells: (Date | null)[] = [...Array(first).fill(null), ...Array.from({ length: count }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1))];
  while (cells.length % 7) cells.push(null);
  const weekdays = WEEKDAYS[language] || WEEKDAYS.tr;
  const fmt = (d: Date) => d.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' });
  const presets: [string, number | null][] = [['Son 30 gün', 30], ['Son 3 ay', 91], ['Son 6 ay', 182], ['Tümü', null]];
  return (
    <AccessibleDialog title={text('Tarih aralığı')} onClose={onClose} className="w-full max-w-[460px] rounded-[28px] bg-[#0f1724] p-6 flex flex-col gap-4 shadow-2xl">
      <div className="flex items-start justify-between gap-3" data-skin-date-range>
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-extrabold text-white">{text('Tarih aralığı')}</h2>
          <span className="text-[15px] text-slate-400">{fmt(from)} – {to ? fmt(to) : '…'}</span>
        </div>
        <button type="button" aria-label={text('Kapat')} onClick={onClose} className="w-[52px] h-[52px] shrink-0 rounded-2xl bg-[#1a2533] flex items-center justify-center text-slate-100"><X aria-hidden="true" className="w-5 h-5" /></button>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {presets.map(([label, days]) => (
          <button key={label} type="button" onClick={() => preset(days)} className="min-h-11 rounded-xl bg-[#1a2533] hover:bg-[#223043] px-2 text-sm font-semibold text-slate-100">{text(label)}</button>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <button type="button" aria-label={text('Önceki ay')} onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} className="w-12 h-12 rounded-xl bg-[#1a2533] flex items-center justify-center text-slate-100"><ChevronLeft aria-hidden="true" className="w-5 h-5" /></button>
        <span className="text-lg font-bold text-white capitalize">{month.toLocaleDateString(locale, { month: 'long', year: 'numeric' })}</span>
        <button type="button" aria-label={text('Sonraki ay')} onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} className="w-12 h-12 rounded-xl bg-[#1a2533] flex items-center justify-center text-slate-100"><ChevronRight aria-hidden="true" className="w-5 h-5" /></button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center">
        {weekdays.map((w, i) => <span key={i} className="text-xs font-semibold text-slate-500 pb-1 capitalize">{w}</span>)}
        {cells.map((d, i) => {
          if (!d) return <span key={i} />;
          const end = to || from, inRange = d >= from && d <= end, edge = same(d, from) || (to && same(d, to)), scan = scanDays.some(s => same(s, d));
          return (
            <button key={i} type="button" onClick={() => pick(d)} disabled={d > today} aria-pressed={!!edge}
              className={`relative h-11 rounded-xl text-[15px] tabular-nums transition disabled:opacity-25 ${edge ? 'bg-[#00d2eb] text-slate-950 font-bold' : inRange ? 'bg-[#00d2eb]/[0.08] text-white' : 'text-slate-200 hover:bg-white/10'}`}>
              {d.getDate()}
              {scan && <span aria-hidden="true" className={`absolute bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full ${edge ? 'bg-slate-950' : 'bg-[#a78bfa]'}`} />}
            </button>
          );
        })}
      </div>
      <p className="flex items-center gap-2 text-sm text-slate-400"><span aria-hidden="true" className="w-1.5 h-1.5 rounded-full bg-[#a78bfa]" />{text('Tarama yapılan günler')}</p>
      <button type="button" onClick={() => onApply({ from, to: to || from })} className="min-h-[60px] rounded-2xl bg-[#00d2eb] hover:bg-[#00e5ff] text-slate-950 text-lg font-extrabold">{text('Uygula')}</button>
    </AccessibleDialog>
  );
}
