'use client';
import React from 'react';
import { useTranslations } from '../../i18n/LanguageProvider';
import type { SkinFindingId } from '../../utils/skinFindings';

/** A finding name with an articulated leader line to the spot it refers to (source pixels). */
export type FindingCallout = { key: string; id: SkinFindingId; label: string; sub?: string; color: string; anchor: { x: number; y: number }; active?: boolean };
type Crop = { x: number; y: number; width: number; height: number };
type Box = { w: number; left: number; top: number; pw: number; ph: number };
type Placed = { c: FindingCallout; ax: number; ay: number; x: number; y: number; width: number; path: string };
const MAX_GUTTER = 196, MIN_GUTTER = 104, MIN_PHOTO = 240, LABEL_H = 44, GAP = 6, ROW_COLUMNS = 3;
const LINE = '#e6edf5', HALO = '#070b12';

/** Leader lines and names stay off the face: the photo keeps its own width and labels sit beside it.
 * The gutter narrows with the column. Below a readable gutter the names move under the photo. */
export function gutterWidth(columnWidth: number): number {
  const available = Math.floor((columnWidth - MIN_PHOTO) / 2);
  return available >= MIN_GUTTER ? Math.min(MAX_GUTTER, available) : 0;
}

/** Stack names beside the photo in anchor order, without overlap, so lines do not cross. */
export function stackLabels(wanted: number[], top: number, bottom: number, height = LABEL_H, gap = GAP): number[] {
  const out: number[] = [];
  wanted.forEach((y, i) => out.push(Math.max(top, y - height / 2, i ? out[i - 1] + height + gap : top)));
  for (let i = out.length - 1, limit = bottom - height; i >= 0; i--) {
    if (out[i] > limit) out[i] = Math.max(top + i * (height + gap), limit);
    limit = out[i] - height - gap;
  }
  return out;
}

export function SkinFindingCallouts({ callouts, crop, photoRef, active, onSelect, children }: {
  callouts?: FindingCallout[]; crop?: Crop; photoRef: React.RefObject<HTMLDivElement | null>; active: SkinFindingId | null;
  onSelect?: (key: string) => void; children: React.ReactNode;
}) {
  const { text } = useTranslations();
  const wrap = React.useRef<HTMLDivElement>(null);
  const [box, setBox] = React.useState<Box | null>(null);
  React.useEffect(() => {
    const measure = () => {
      const w = wrap.current, p = photoRef.current;
      if (!w || !p) return;
      const a = w.getBoundingClientRect(), b = p.getBoundingClientRect();
      setBox({ w: a.width, left: b.left - a.left, top: b.top - a.top, pw: b.width, ph: b.height });
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (wrap.current) ro.observe(wrap.current);
    if (photoRef.current) ro.observe(photoRef.current);
    window.addEventListener('resize', measure);
    return () => { ro.disconnect(); window.removeEventListener('resize', measure); };
  }, [photoRef, callouts?.length]);

  const list = (callouts || []).filter(c => !crop || (c.anchor.x >= crop.x && c.anchor.x <= crop.x + crop.width && c.anchor.y >= crop.y && c.anchor.y <= crop.y + crop.height));
  if (!list.length) return <>{children}</>;
  const gutter = box ? gutterWidth(box.w) : 0;

  let placed: Placed[] = [], extraBottom = 0;
  if (box && crop) {
    const pts = list.map(c => ({ c, ax: box.left + (c.anchor.x - crop.x) / crop.width * box.pw, ay: box.top + (c.anchor.y - crop.y) / crop.height * box.ph }));
    const photoBottom = box.top + box.ph;
    if (gutter) {
      const center = box.left + box.pw / 2;
      const sides = [pts.filter(p => p.ax < center), pts.filter(p => p.ax >= center)];
      while (Math.abs(sides[0].length - sides[1].length) > 2) {
        const [from, to] = sides[0].length > sides[1].length ? [sides[0], sides[1]] : [sides[1], sides[0]];
        from.sort((a, b) => Math.abs(a.ax - center) - Math.abs(b.ax - center));
        to.push(from.shift()!);
      }
      placed = sides.flatMap((side, i) => {
        const sorted = [...side].sort((a, b) => a.ay - b.ay);
        const ys = stackLabels(sorted.map(p => p.ay), box.top, Math.max(photoBottom, box.top + sorted.length * (LABEL_H + GAP)));
        return sorted.map((p, j) => {
          const left = i === 0, cy = ys[j] + LABEL_H / 2;
          const end = left ? box.left - 6 : box.left + box.pw + 6;
          const x = left ? end - (gutter - 12) : end;
          const elbow = left ? Math.min(p.ax - 12, end + 18) : Math.max(p.ax + 12, end - 18);
          return { c: p.c, ax: p.ax, ay: p.ay, x, y: ys[j], width: gutter - 12, path: `${p.ax},${p.ay} ${elbow},${cy} ${end},${cy}` };
        });
      });
      extraBottom = Math.max(0, ...placed.map(p => p.y + LABEL_H - photoBottom));
    } else {
      // Narrow column: names under the photo, in anchor order, each still joined to its spot.
      const sorted = [...pts].sort((a, b) => a.ax - b.ax);
      const columns = Math.min(ROW_COLUMNS, sorted.length), width = box.w / columns;
      placed = sorted.map((p, i) => {
        const row = Math.floor(i / columns), x = (i % columns) * width, y = photoBottom + 14 + row * (LABEL_H + GAP), lx = x + width / 2;
        const elbow = photoBottom + 7;
        return { c: p.c, ax: p.ax, ay: p.ay, x, y, width, path: `${p.ax},${p.ay} ${p.ax},${elbow} ${lx},${elbow} ${lx},${y}` };
      });
      extraBottom = 14 + Math.ceil(sorted.length / columns) * (LABEL_H + GAP);
    }
  }
  return (
    <div className="w-full flex flex-col items-center" data-skin-callouts>
      <div ref={wrap} className="relative w-full flex justify-center" style={{ ...(gutter ? { paddingLeft: gutter, paddingRight: gutter } : {}), paddingBottom: extraBottom }} data-skin-callout-layout={gutter ? 'gutter' : 'row'}>
        {children}
        {box && placed.length > 0 && <>
          <svg aria-hidden="true" className="absolute inset-0 w-full h-full pointer-events-none overflow-visible" data-skin-callout-connectors>
            {placed.map(p => {
              const on = p.c.active ?? p.c.id === active;
              return <g key={p.c.key} opacity={on || active === null ? 1 : .7} data-skin-callout-line={p.c.key}>
                <polyline points={p.path} fill="none" stroke={HALO} strokeOpacity=".55" strokeWidth={on ? 3.5 : 3} strokeLinejoin="round" />
                <polyline points={p.path} fill="none" stroke={LINE} strokeWidth={on ? 1.75 : 1.25} strokeLinejoin="round" />
                <circle cx={p.ax} cy={p.ay} r={on ? 4 : 3} fill="none" stroke={LINE} strokeWidth="1.5" />
              </g>;
            })}
          </svg>
          {placed.map(p => {
            const on = p.c.active ?? p.c.id === active;
            return <button key={p.c.key} type="button" aria-pressed={on} onClick={() => onSelect?.(p.c.key)} data-skin-callout={p.c.key}
              style={{ position: 'absolute', top: p.y, left: p.x, width: p.width, minHeight: LABEL_H }}
              className={`px-1.5 flex items-center text-sm leading-tight break-words transition ${gutter && p.x < box.left ? 'justify-end text-right' : gutter ? 'justify-start text-left' : 'justify-center text-center'} ${on ? 'text-white font-bold underline underline-offset-4' : 'text-slate-200 font-medium'}`}>
              <span className="min-w-0">{text(p.c.label)}{p.c.sub && <span className="ml-1.5 text-slate-300 tabular-nums">{text(p.c.sub)}</span>}</span>
            </button>;
          })}
        </>}
      </div>
    </div>
  );
}
