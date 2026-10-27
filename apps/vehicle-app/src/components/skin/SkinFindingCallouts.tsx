'use client';
import React from 'react';
import { useTranslations } from '../../i18n/LanguageProvider';
import type { SkinFindingId } from '../../utils/skinFindings';

/** A label beside the photo with a leader line to the spot it refers to (source pixels). */
export type FindingCallout = { key: string; id: SkinFindingId; label: string; sub?: string; color: string; anchor: { x: number; y: number }; active?: boolean };
type Crop = { x: number; y: number; width: number; height: number };
const GUTTER = 196, PILL_H = 52, GAP = 12, MIN_PHOTO = 360;

/** When the photo column has room for both gutters and a readable photo (>= MIN_PHOTO px): labels in the gutters left
 * and right of the photo with leader lines. Otherwise (narrow screens, or a narrow photo column): the same labels as a
 * row of buttons under the photo, so the gutters never squeeze the photo. Tapping a label selects that finding. */
export function SkinFindingCallouts({ callouts, crop, photoRef, active, onSelect, children }: {
  callouts?: FindingCallout[]; crop?: Crop; photoRef: React.RefObject<HTMLDivElement | null>; active: SkinFindingId | null;
  onSelect?: (key: string) => void; children: React.ReactNode;
}) {
  const { text } = useTranslations();
  const wrap = React.useRef<HTMLDivElement>(null);
  const [box, setBox] = React.useState<{ w: number; left: number; top: number; pw: number; ph: number } | null>(null);
  const [wide, setWide] = React.useState(false);
  React.useEffect(() => {
    const measure = () => {
      const w = wrap.current, p = photoRef.current;
      setWide(window.matchMedia('(min-width: 1280px)').matches);
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

  const list = callouts || [];
  if (!list.length) return <>{children}</>;
  // gutters only when the whole column (w) leaves at least MIN_PHOTO px for the photo between them
  const gutter = wide && !!box && box.w >= 2 * GUTTER + MIN_PHOTO;
  const pill = (c: FindingCallout, style?: React.CSSProperties, extra = '') => {
    const on = c.active ?? c.id === active;
    return (
      <button key={c.key} type="button" aria-pressed={on} onClick={() => onSelect?.(c.key)} data-skin-callout={c.key} style={{ ...style, borderColor: on ? c.color : 'transparent', background: on ? `${c.color}26` : '#121b28' }}
        className={`min-h-[52px] rounded-full border-2 px-4 flex items-center gap-2.5 text-left text-[15px] leading-tight transition active:scale-[0.98] ${on ? 'text-white font-bold' : 'text-slate-200 font-semibold hover:bg-white/10'} ${c.sub ? 'whitespace-nowrap' : ''} ${extra}`}>
        <span aria-hidden="true" className="w-2.5 h-2.5 shrink-0 rounded-full" style={{ background: c.color, boxShadow: on ? `0 0 10px ${c.color}` : undefined }} />
        <span>{text(c.label)}{c.sub && <span className="ml-1.5 font-semibold text-slate-300 tabular-nums">{text(c.sub)}</span>}</span>
      </button>
    );
  };

  // Gutter layout: project anchors into wrapper pixels, split by side, stack labels without overlap.
  let placed: { c: FindingCallout; ax: number; ay: number; left: boolean; y: number }[] = [];
  if (gutter && box && crop) {
    const pts = list.map(c => ({ c, ax: box.left + (c.anchor.x - crop.x) / crop.width * box.pw, ay: box.top + (c.anchor.y - crop.y) / crop.height * box.ph }));
    const sides = [pts.filter(p => p.ax < box.left + box.pw / 2), pts.filter(p => p.ax >= box.left + box.pw / 2)];
    // keep both sides balanced when one side would crowd
    while (Math.abs(sides[0].length - sides[1].length) > 2) {
      const [from, to] = sides[0].length > sides[1].length ? [sides[0], sides[1]] : [sides[1], sides[0]];
      from.sort((a, b) => Math.abs(a.ax - box.left - box.pw / 2) - Math.abs(b.ax - box.left - box.pw / 2));
      to.push(from.shift()!);
    }
    placed = sides.flatMap((side, i) => {
      const sorted = [...side].sort((a, b) => a.ay - b.ay);
      let y = -Infinity;
      const ys = sorted.map(p => (y = Math.max(p.ay - PILL_H / 2, y + PILL_H + GAP)));
      const over = ys.length ? ys[ys.length - 1] + PILL_H - (box.top + box.ph) : 0;
      return sorted.map((p, j) => ({ ...p, left: i === 0, y: Math.max(box.top, ys[j] - Math.max(0, over)) }));
    });
  }
  return (
    <div className="w-full flex flex-col items-center gap-3" data-skin-callouts>
      <div ref={wrap} className="relative w-full flex justify-center" style={gutter ? { paddingLeft: GUTTER, paddingRight: GUTTER } : undefined} data-skin-callout-layout={gutter ? 'gutter' : 'row'}>
        {children}
        {gutter && box && placed.length > 0 && <>
          <svg aria-hidden="true" className="absolute inset-0 w-full h-full pointer-events-none overflow-visible">
            {placed.map(p => {
              const on = p.c.active ?? p.c.id === active, cy = p.y + PILL_H / 2;
              const ex = p.left ? GUTTER - 8 : box.w - GUTTER + 8, elbow = p.left ? Math.min(p.ax - 18, ex + 40) : Math.max(p.ax + 18, ex - 40);
              return (
                <g key={p.c.key} opacity={on ? 1 : 0.6}>
                  <polyline points={`${p.ax},${p.ay} ${elbow},${cy} ${ex},${cy}`} fill="none" stroke={p.c.color} strokeWidth={on ? 2.5 : 2} strokeLinejoin="round" />
                  <circle cx={p.ax} cy={p.ay} r={on ? 6 : 5} fill={p.c.color} stroke="#070b12" strokeWidth="1.5" />
                </g>
              );
            })}
          </svg>
          {placed.map(p => pill(p.c, { position: 'absolute', top: p.y, ...(p.left ? { right: box.w - GUTTER + 8 } : { left: box.w - GUTTER + 8 }), ...(p.c.sub ? {} : { maxWidth: GUTTER - 16 }) }))}
        </>}
      </div>
      {!gutter && <div className="flex flex-wrap justify-center gap-2" data-skin-callout-row>{list.map(c => pill(c))}</div>}
    </div>
  );
}
