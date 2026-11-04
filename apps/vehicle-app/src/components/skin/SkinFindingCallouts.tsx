'use client';
import React from 'react';
import { useTranslations } from '../../i18n/LanguageProvider';
import type { SkinFindingId } from '../../utils/skinFindings';
import { placeCallouts, type CalloutRect } from '../../utils/skinCalloutLayout';

/** A finding name joined by a short line to the spot it refers to (source pixels). */
export type FindingCallout = { key: string; id: SkinFindingId; label: string; sub?: string; color: string; anchor: { x: number; y: number }; active?: boolean };
type Crop = { x: number; y: number; width: number; height: number };
type Box = { w: number; left: number; top: number; pw: number; ph: number };
type Size = { w: number; h: number; visualH: number; lines: number };
// 48 px is the vehicle stylesheet's minimum for a control.
const TARGET = 48, MIN_PHOTO = 220, MAX_LINES = 2, LINE = '#e6edf5', HALO = '#070b12';
/** Label width limits follow the photo, so a German or Turkish name wraps instead of covering the face. */
export const labelWidthLimit = (photoWidth: number) => Math.max(104, Math.min(190, Math.round(photoWidth * .46)));
const toPhoto = (r: CalloutRect, crop: Crop, box: Box): CalloutRect => ({ x: (r.x - crop.x) / crop.width * box.pw, y: (r.y - crop.y) / crop.height * box.ph, w: r.w / crop.width * box.pw, h: r.h / crop.height * box.ph });

/** The dot and the name. The same markup is measured and shown, so the measured size is the real size. */
function Pill({ color, label, sub, on, width }: { color: string; label: string; sub?: string; on: boolean; width?: number }) {
  return (
    <span data-skin-callout-pill className={`inline-flex items-center gap-1.5 rounded-[14px] border px-2.5 py-1 text-[13px] leading-[1.2] text-white text-left shadow-md ${on ? 'font-bold' : 'font-semibold'}`}
      style={{ borderColor: color, background: 'rgba(10,18,32,.92)', ...(width ? { width } : {}) }}>
      <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
      <span data-skin-callout-text className="min-w-0 [overflow-wrap:anywhere]">{label}{sub && <span className="ml-1.5 text-slate-300 tabular-nums">{sub}</span>}</span>
    </span>
  );
}

export function SkinFindingCallouts({ callouts, crop, photoRef, active, onSelect, keepOut, face, children }: {
  callouts?: FindingCallout[]; crop?: Crop; photoRef: React.RefObject<HTMLDivElement | null>; active: SkinFindingId | null;
  onSelect?: (key: string) => void; keepOut?: CalloutRect[]; face?: CalloutRect | null; children: React.ReactNode;
}) {
  const { text } = useTranslations();
  const wrap = React.useRef<HTMLDivElement>(null), ruler = React.useRef<HTMLDivElement>(null);
  const [box, setBox] = React.useState<Box | null>(null);
  const [sizes, setSizes] = React.useState<Record<string, Size>>({});
  const list = React.useMemo(() => (callouts || []).filter(c => !crop || (c.anchor.x >= crop.x && c.anchor.x <= crop.x + crop.width && c.anchor.y >= crop.y && c.anchor.y <= crop.y + crop.height)), [callouts, crop]);
  const labels = list.map(c => `${c.key}=${text(c.label)}${c.sub ? ' ' + text(c.sub) : ''}`).join('|');

  React.useEffect(() => {
    const measure = () => {
      const w = wrap.current, p = photoRef.current;
      if (!w || !p) return;
      const a = w.getBoundingClientRect(), b = p.getBoundingClientRect();
      setBox(old => {
        const next = { w: a.width, left: b.left - a.left, top: b.top - a.top, pw: b.width, ph: b.height };
        return old && Object.keys(next).every(k => Math.abs(old[k as keyof Box] - next[k as keyof Box]) < .5) ? old : next;
      });
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (wrap.current) ro.observe(wrap.current);
    if (photoRef.current) ro.observe(photoRef.current);
    window.addEventListener('resize', measure);
    return () => { ro.disconnect(); window.removeEventListener('resize', measure); };
  }, [photoRef, list.length]);

  const limit = box ? labelWidthLimit(box.pw) : 0;
  // Sizes come from the rendered text, so every language gets its own width and the layout runs again when it changes.
  React.useEffect(() => {
    const host = ruler.current;
    if (!host || !limit) return;
    const measure = () => {
      const next: Record<string, Size> = {};
      host.querySelectorAll<HTMLElement>('[data-skin-callout-ruler]').forEach(row => {
        const pill = row.firstElementChild as HTMLElement;
        const name = pill.querySelector<HTMLElement>('[data-skin-callout-text]')!;
        const lineHeight = parseFloat(getComputedStyle(name).lineHeight) || 16;
        const linesOf = () => Math.round(name.getBoundingClientRect().height / lineHeight);
        pill.style.width = ''; pill.style.whiteSpace = 'nowrap';
        const natural = Math.ceil(pill.getBoundingClientRect().width);
        pill.style.whiteSpace = '';
        // Two balanced lines read better than one long line and one short word.
        let width = natural <= limit ? natural : Math.min(limit, Math.ceil(natural * .62));
        pill.style.width = `${width}px`;
        while (linesOf() > MAX_LINES && width < limit) { width = Math.min(limit, width + 12); pill.style.width = `${width}px`; }
        next[row.dataset.skinCalloutRuler!] = { w: Math.max(TARGET, width), h: Math.max(TARGET, Math.ceil(pill.getBoundingClientRect().height)), visualH: Math.ceil(pill.getBoundingClientRect().height), lines: linesOf() };
        pill.style.width = '';
      });
      setSizes(next);
    };
    measure();
    // A web font arriving late changes the width of the text, so its size is read again.
    let live = true;
    void document.fonts?.ready.then(() => { if (live) measure(); });
    const fonts = () => measure();
    document.fonts?.addEventListener?.('loadingdone', fonts);
    return () => { live = false; document.fonts?.removeEventListener?.('loadingdone', fonts); };
  }, [labels, limit]);

  const layout = React.useMemo(() => {
    if (!box || !crop || !list.length || !list.every(c => sizes[c.key])) return null;
    const anchors = list.map(c => ({ c, ax: (c.anchor.x - crop.x) / crop.width * box.pw, ay: (c.anchor.y - crop.y) / crop.height * box.ph }));
    if (box.pw < MIN_PHOTO || list.some(c => sizes[c.key].lines > MAX_LINES)) return { anchors, placed: null };
    const result = placeCallouts(anchors.map(({ c, ax, ay }) => ({ key: c.key, ax, ay, w: sizes[c.key].w, h: sizes[c.key].h, visualH: sizes[c.key].visualH })), {
      width: box.pw, height: box.ph, keepOut: (keepOut || []).map(r => toPhoto(r, crop, box)), face: face ? toPhoto(face, crop, box) : null,
    });
    return { anchors, placed: result.fits ? result.placed : null };
  }, [box, crop, list, sizes, keepOut, face]);

  if (!list.length) return <>{children}</>;
  const mode = !layout ? 'pending' : layout.placed ? 'photo' : 'list';
  const pressed = (c: FindingCallout) => c.active ?? c.id === active;
  const button = 'flex items-center justify-center rounded-[14px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-white';
  return (
    <div className="w-full flex flex-col items-center" data-skin-callouts>
      <div ref={wrap} className="relative w-full flex justify-center" data-skin-callout-layout={mode}>
        {children}
        {/* Hidden copies are what the label sizes are read from. */}
        <div ref={ruler} aria-hidden="true" className="absolute left-0 top-0 invisible pointer-events-none" style={{ width: limit || 190 }}>
          {list.map(c => <div key={c.key} data-skin-callout-ruler={c.key} style={{ width: 'max-content', maxWidth: 'none', height: 0, overflow: 'hidden' }}><Pill color={c.color} label={text(c.label)} sub={c.sub && text(c.sub)} on={pressed(c)} /></div>)}
        </div>
        {box && layout && <>
          <svg aria-hidden="true" className="absolute pointer-events-none overflow-visible" style={{ left: box.left, top: box.top, width: box.pw, height: box.ph }} data-skin-callout-connectors>
            {layout.anchors.map(({ c, ax, ay }) => {
              const on = pressed(c), p = layout.placed?.find(x => x.key === c.key);
              return <g key={c.key} data-skin-callout-line={c.key}>
                {p && <path d={p.path} fill="none" stroke={HALO} strokeOpacity=".55" strokeWidth="3" strokeLinecap="round" />}
                {p && <path d={p.path} fill="none" stroke={LINE} strokeWidth={on ? 1.5 : 1.25} strokeLinecap="round" data-skin-callout-path={c.key} />}
                <circle cx={ax} cy={ay} r={on ? 4.5 : 3.5} fill={HALO} fillOpacity=".35" stroke={layout.placed ? LINE : c.color} strokeWidth="1.5" data-skin-callout-ring={c.key} />
              </g>;
            })}
          </svg>
          {layout.placed?.map(p => {
            const c = list.find(x => x.key === p.key)!, size = sizes[c.key];
            return <button key={p.key} type="button" aria-pressed={pressed(c)} onClick={() => onSelect?.(c.key)} data-skin-callout={c.key} data-skin-callout-finding={c.id} data-skin-callout-anchor={`${c.anchor.x},${c.anchor.y}`} data-skin-callout-lines={size.lines}
              className={`absolute ${button}`} style={{ left: box.left + p.x, top: box.top + p.y, width: p.w, height: p.h }}>
              <Pill color={c.color} label={text(c.label)} sub={c.sub && text(c.sub)} on={pressed(c)} width={Math.max(0, size.w)} />
            </button>;
          })}
        </>}
      </div>
      {mode === 'list' && (
        <ul className="mt-2 flex w-full flex-wrap justify-center gap-x-1.5" data-skin-callout-list>
          {list.map(c => <li key={c.key} className="max-w-full"><button type="button" aria-pressed={pressed(c)} onClick={() => onSelect?.(c.key)} data-skin-callout={c.key} data-skin-callout-finding={c.id} data-skin-callout-anchor={`${c.anchor.x},${c.anchor.y}`}
            className={`min-h-[48px] min-w-[48px] max-w-full ${button}`}><Pill color={c.color} label={text(c.label)} sub={c.sub && text(c.sub)} on={pressed(c)} /></button></li>)}
        </ul>
      )}
    </div>
  );
}
