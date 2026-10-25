/** Presentation-only outlines for the regional skin-type paint on the result
 * photo. Smooth, landmark-following shapes (never boxes or mesh triangles).
 * Indices are MediaPipe FaceMesh landmarks in the unmirrored accepted frame;
 * a [a,b,t] entry is the point a + t·(b − a). Measurement ROIs are unchanged. */
export type PaintPoint = number | [number, number, number];
export type PaintRegionId = 'forehead' | 'nose' | 'rightCheek' | 'leftCheek' | 'chin' | 'periorbital';
export type PaintState = 'oily' | 'dry' | 'normal' | 'unmeasured';

const FOREHEAD_TOP: Record<number, number> = { 21: .35, 54: .7, 103: .9, 67: 1, 109: 1, 10: 1, 338: 1, 297: 1, 332: .9, 284: .7, 251: .35 };
export const PAINT_OUTLINES: Record<PaintRegionId, PaintPoint[][]> = {
  forehead: [[21, 54, 103, 67, 109, 10, 338, 297, 332, 284, 251, 301, 293, 334, 296, 336, 9, 107, 66, 105, 63, 71]],
  nose: [[9, 336, 285, 417, 465, 412, 343, 437, 420, 429, 358, 327, 326, 2, 97, 98, 129, 209, 198, 217, 114, 188, 245, 193, 55, 107]],
  rightCheek: [[143, 127, 234, 93, 132, 58, 172, 136, 150, 169, 210, 202, 57, 186, 92, 165, 203, 129, 209, 198, 217, 114, 188, 245, 128, 121, 120, 119, 118, 117, 111]],
  leftCheek: [[372, 356, 454, 323, 361, 288, 397, 365, 379, 394, 430, 422, 287, 410, 322, 391, 423, 358, 429, 420, 437, 343, 412, 465, 357, 350, 349, 348, 347, 346, 340]],
  chin: [[57, [43, 204, .45], [106, 194, .45], [182, 201, .45], [83, 200, .3], [18, 200, .45], [313, 200, .3], [406, 421, .45], [335, 418, .45], [273, 424, .45], 287, 430, 394, 379, 378, 400, 377, 152, 148, 176, 149, 150, 169, 210]],
  // Two closed rings; the eye openings are cut out with evenodd fill.
  periorbital: [
    [143, 111, 117, 118, 119, 120, 121, 128, 245, 193, 55, 65, 52, 53, 46, 124, 35],
    [33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7],
    [372, 340, 346, 347, 348, 349, 350, 357, 465, 417, 285, 295, 282, 283, 276, 353, 265],
    [263, 466, 388, 387, 386, 385, 384, 398, 362, 382, 381, 380, 374, 373, 390, 249]
  ]
};
export const PAINT_COLORS: Record<PaintState, string> = { oily: '#22c55e', dry: '#3b82f6', normal: '#facc15', unmeasured: '#94a3b8' };
export const SENSITIVE_COLOR = '#ec4899';

type P = { x: number; y: number };
function resolve(lm: P[], p: PaintPoint): P {
  if (typeof p === 'number') return lm[p];
  const [a, b, t] = p; return { x: lm[a].x + (lm[b].x - lm[a].x) * t, y: lm[a].y + (lm[b].y - lm[a].y) * t };
}
/** Closed Catmull-Rom spline converted to cubic Béziers: soft, organic edges. */
function smoothClosed(pts: P[]): string {
  const n = pts.length; if (n < 3) return '';
  let d = `M${pts[0].x.toFixed(1)} ${pts[0].y.toFixed(1)}`;
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
    const c1 = { x: p1.x + (p2.x - p0.x) / 6, y: p1.y + (p2.y - p0.y) / 6 }, c2 = { x: p2.x - (p3.x - p1.x) / 6, y: p2.y - (p3.y - p1.y) / 6 };
    d += `C${c1.x.toFixed(1)} ${c1.y.toFixed(1)} ${c2.x.toFixed(1)} ${c2.y.toFixed(1)} ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return d + 'Z';
}
/** Source-pixel SVG path for one region; null if landmarks are missing. */
export function paintPath(region: PaintRegionId, landmarks: { x: number; y: number }[] | undefined, width: number, height: number): string | null {
  if (!landmarks || landmarks.length < 468) return null;
  const lm = landmarks.map(p => ({ x: p.x * width, y: p.y * height }));
  const up = { x: (lm[10].x - lm[9].x) * .42, y: (lm[10].y - lm[9].y) * .42 };
  return PAINT_OUTLINES[region].map(ring => smoothClosed(ring.map(p => {
    const q = resolve(lm, p);
    const k = region === 'forehead' && typeof p === 'number' ? FOREHEAD_TOP[p] || 0 : 0;
    return k ? { x: q.x + up.x * k, y: q.y + up.y * k } : q;
  }))).join('');
}
/** Approximate face width in source pixels, used to scale blur and textures. */
export function faceWidthPx(landmarks: { x: number }[] | undefined, width: number): number {
  if (!landmarks || landmarks.length < 468) return width / 3;
  return Math.abs(landmarks[454].x - landmarks[234].x) * width;
}

/** Landmark used to place the small region tag, plus a face-width-relative offset. */
export const PAINT_TAG_ANCHOR: Record<Exclude<PaintRegionId,'periorbital'>, { index: number; dx: number; dy: number }> = {
  forehead: { index: 10, dx: 0, dy: -0.02 }, nose: { index: 4, dx: 0, dy: 0.05 },
  rightCheek: { index: 205, dx: -0.12, dy: 0 }, leftCheek: { index: 425, dx: 0.12, dy: 0 }, chin: { index: 152, dx: 0, dy: 0.05 }
};
export const PAINT_LABELS: Record<PaintState, string> = { oily: 'Yağlı', dry: 'Kuru', normal: 'Normal görünüm', unmeasured: 'Ölçüm notu' };
/** Centroid of a region outline (source pixels) — used to inset the sensitivity ring. */
export function paintCentroid(region: PaintRegionId, landmarks: { x: number; y: number }[], width: number, height: number): { x: number; y: number } {
  const ring = PAINT_OUTLINES[region][0].map(p => resolve(landmarks.map(q => ({ x: q.x * width, y: q.y * height })), p));
  return { x: ring.reduce((a, p) => a + p.x, 0) / ring.length, y: ring.reduce((a, p) => a + p.y, 0) / ring.length };
}
