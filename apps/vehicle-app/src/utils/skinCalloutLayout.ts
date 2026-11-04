/** Places finding labels on the photo. Presentation only: anchors come from measured results and are never moved.
 * All values are CSS pixels relative to the photo's top-left corner. */
export type CalloutRect = { x: number; y: number; w: number; h: number };
export type CalloutItem = {
  key: string;
  /** the measured spot on the face */
  ax: number; ay: number;
  /** touch target of the label */
  w: number; h: number;
  /** drawn label height, centred in the touch target */
  visualH: number;
};
export type PlacedCallout = CalloutRect & { key: string; ax: number; ay: number; endX: number; endY: number; path: string; length: number };
export type CalloutLayout = { placed: PlacedCallout[]; fits: boolean };
export type CalloutOptions = {
  width: number; height: number;
  /** eyes, brows, nose and mouth: labels avoid them */
  keepOut?: CalloutRect[];
  /** the face, softly avoided */
  face?: CalloutRect | null;
  margin?: number;
};

const OFFSETS = [0, -16, 16, -32, 32, -52, 52, -76, 76];
const RADII = [14, 22, 32, 44, 58, 74, 92, 112, 134];

const overlap = (a: CalloutRect, b: CalloutRect) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
const inside = (x: number, y: number, r: CalloutRect, pad = 0) => x >= r.x - pad && x <= r.x + r.w + pad && y >= r.y - pad && y <= r.y + r.h + pad;
type Segment = [number, number, number, number];
function crosses([a, b, c, d]: Segment, [e, f, g, h]: Segment): boolean {
  const side = (px: number, py: number, qx: number, qy: number, rx: number, ry: number) => (qx - px) * (ry - py) - (qy - py) * (rx - px);
  const s1 = side(a, b, c, d, e, f), s2 = side(a, b, c, d, g, h), s3 = side(e, f, g, h, a, b), s4 = side(e, f, g, h, c, d);
  return s1 * s2 < 0 && s3 * s4 < 0;
}
function hitsRect(seg: Segment, r: CalloutRect): boolean {
  for (let t = 0; t <= 1; t += .1) if (inside(seg[0] + (seg[2] - seg[0]) * t, seg[1] + (seg[3] - seg[1]) * t, r)) return true;
  return false;
}

/** Where the line meets the label: the near side, or the top or bottom when the label sits over the spot. */
function attach(item: CalloutItem, r: CalloutRect): { x: number; y: number; horizontal: boolean } {
  const inset = Math.max(0, (r.h - item.visualH) / 2), cy = r.y + r.h / 2;
  if (r.x >= item.ax) return { x: r.x, y: cy, horizontal: true };
  if (r.x + r.w <= item.ax) return { x: r.x + r.w, y: cy, horizontal: true };
  const x = Math.max(r.x + 14, Math.min(r.x + r.w - 14, item.ax));
  return r.y >= item.ay ? { x, y: r.y + inset, horizontal: false } : { x, y: r.y + r.h - inset, horizontal: false };
}

type Option = { rect: CalloutRect; end: { x: number; y: number; horizontal: boolean }; seg: Segment; length: number; base: number };

function options(item: CalloutItem, all: CalloutItem[], o: Required<Pick<CalloutOptions, 'width' | 'height' | 'margin'>> & CalloutOptions): Option[] {
  const { width: W, height: H, margin: m } = o;
  const scale = Math.max(.75, Math.min(1.25, Math.min(W, H) / 380));
  const faceX = o.face ? o.face.x + o.face.w / 2 : W / 2;
  const seen = new Set<string>(), out: Option[] = [];
  const add = (x: number, y: number) => {
    const rect = { x: Math.max(m, Math.min(W - m - item.w, x)), y: Math.max(m, Math.min(H - m - item.h, y)), w: item.w, h: item.h };
    const id = `${Math.round(rect.x)},${Math.round(rect.y)}`;
    if (seen.has(id) || inside(item.ax, item.ay, rect, 3)) return;
    seen.add(id);
    const end = attach(item, rect), seg: Segment = [item.ax, item.ay, end.x, end.y];
    const length = Math.hypot(end.x - item.ax, end.y - item.ay);
    let base = length;
    for (const k of o.keepOut || []) {
      base += overlap(rect, k) / (rect.w * rect.h) * 700;
      for (let t = .1; t < 1; t += .2) if (inside(item.ax + (end.x - item.ax) * t, item.ay + (end.y - item.ay) * t, k)) base += 10;
    }
    if (o.face) base += overlap(rect, o.face) / (rect.w * rect.h) * 46;
    // Other findings' spots stay visible.
    for (const other of all) if (other !== item && inside(other.ax, other.ay, rect, 5)) base += 320;
    // Labels sit on the same side of the face as their spot, so lines do not reach across it.
    if ((rect.x + rect.w / 2 - faceX) * (item.ax - faceX) < 0) base += 44;
    out.push({ rect, end, seg, length, base });
  };
  for (const raw of RADII) {
    const r = raw * scale;
    for (const d of OFFSETS) {
      add(item.ax + r, item.ay - item.h / 2 + d);
      add(item.ax - r - item.w, item.ay - item.h / 2 + d);
      add(item.ax - item.w / 2 + d, item.ay - r - item.h);
      add(item.ax - item.w / 2 + d, item.ay + r);
    }
  }
  return out.sort((a, b) => a.base - b.base);
}

function cost(option: Option, others: Option[]): number {
  let total = option.base;
  for (const other of others) {
    if (overlap(option.rect, other.rect) > 0) return Infinity;
    if (crosses(option.seg, other.seg)) total += 260;
    if (hitsRect(option.seg, other.rect) || hitsRect(other.seg, option.rect)) total += 260;
  }
  return total;
}

/** Labels near their spots, inside the photo, without touching each other. `fits` is false when that is not possible
 * within short lines, and the caller then lists the names under the photo instead of crowding the face. */
export function placeCallouts(items: CalloutItem[], settings: CalloutOptions): CalloutLayout {
  const o = { margin: 6, ...settings };
  if (!items.length) return { placed: [], fits: true };
  if (items.some(i => i.w > o.width - 2 * o.margin || i.h > o.height - 2 * o.margin)) return { placed: [], fits: false };
  const order = [...items].sort((a, b) => b.w * b.h - a.w * a.h || a.key.localeCompare(b.key));
  const choices = new Map(order.map(item => [item, options(item, items, o)]));
  const chosen = new Map<CalloutItem, Option>();
  const best = (item: CalloutItem) => {
    const others = [...chosen].filter(([other]) => other !== item).map(([, option]) => option);
    let winner: Option | null = null, score = Infinity;
    for (const option of choices.get(item)!) {
      if (option.base >= score) break; // sorted: nothing later can be cheaper
      const value = cost(option, others);
      if (value < score) { score = value; winner = option; }
    }
    return { winner, score };
  };
  for (const item of order) {
    const { winner } = best(item);
    if (!winner) return { placed: [], fits: false };
    chosen.set(item, winner);
  }
  // Earlier labels were placed without knowing about later ones, so give each another look.
  for (let round = 0; round < 3; round++) {
    let moved = false;
    for (const item of order) {
      const current = chosen.get(item)!, others = [...chosen].filter(([other]) => other !== item).map(([, option]) => option);
      const { winner, score } = best(item);
      if (winner && winner !== current && score < cost(current, others) - .5) { chosen.set(item, winner); moved = true; }
    }
    if (!moved) break;
  }
  const limit = Math.max(96, .4 * Math.max(o.width, o.height));
  const placed = items.map(item => {
    const { rect, end, length } = chosen.get(item)!;
    const c = end.horizontal ? { x: item.ax + (end.x - item.ax) * .62, y: end.y } : { x: end.x, y: item.ay + (end.y - item.ay) * .62 };
    const round = (v: number) => Math.round(v * 10) / 10;
    return { key: item.key, ...rect, ax: item.ax, ay: item.ay, endX: round(end.x), endY: round(end.y), length: round(length), path: `M${round(item.ax)} ${round(item.ay)}Q${round(c.x)} ${round(c.y)} ${round(end.x)} ${round(end.y)}` };
  });
  return { placed, fits: placed.every(p => p.length <= limit) };
}
