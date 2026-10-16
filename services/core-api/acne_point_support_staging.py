"""Offline staging only (not imported by the product; acne stays accepted:false, file:null).

Box-size-independent POINT support filter, an explicit alternative to acne_box_support_staging.principled_accepted_boxes.
Every decision uses only the prediction's centre point and the existing product masks/geometry; box width/height never
influence acceptance or region. No ground-truth or review mask is an input.

Point: px = (x1 + x2) / 2, py = (y1 + y2) / 2 in source px (never moved).
Sampling: analysis pixel (floor((px - x0) * scale), floor((py - y0) * scale)) with the existing origin/scale contract.
Order of checks (first failing check is the reason):
  POINT_NOT_FINITE            px or py not finite
  POINT_OUTSIDE_IMAGE         px < 0 or py < 0 or px >= source width or py >= source height (no clamping)
  POINT_OUTSIDE_SCOPE         analysis pixel outside the analysis raster (= visible-region scope of the capture; no clamping)
  POINT_ON_EXCLUSION          exclusion > 0 at the pixel (eyes, ocular margin, brows, nostrils, mouth, raster edge band)
  POINT_ON_HAIR               hair at the pixel
  POINT_NOT_SKIN_SUPPORT      skin_support (acne_skin) false at the pixel
Region: visible-region envelopes containing the pixel; several -> first in acne_box_support.REGIONS order
(forehead, rightCheek, leftCheek, nose, chin). None -> the existing anatomical distance fallback (same face width,
midline side constraints and 0.15 face-width limit); beyond it -> POINT_UNCERTAIN_REGION.
The redness/contrast rescue of the box filter is NOT used.
"""
import hashlib, math
from typing import Dict, List, Tuple
import cv2
import numpy as np
import acne_box_support

VERSION = 'point-anatomical-support-staging-v1'
REGIONS = acne_box_support.REGIONS


def point_accepted(boxes: List[List[float]], envelopes: Dict[str, np.ndarray], skin_support: np.ndarray, hair: np.ndarray,
                   exclusion: np.ndarray, photo: str, scale: float, origin: Tuple[float, float], visible_regions: List[str] = None,
                   landmarks: List[dict] = None, source_shape: Tuple[int, int] = None) -> Tuple[List[dict], List[dict]]:
    h, w = skin_support.shape; x0, y0 = origin
    src_h, src_w = (float(source_shape[0]), float(source_shape[1])) if source_shape is not None else (h / scale + y0, w / scale + x0)
    regions = [k for k in REGIONS if k in envelopes and (visible_regions is None or k in visible_regions)]
    if landmarks and len(landmarks) > 454:
        face_width = max(10., abs(landmarks[454]['x'] - landmarks[234]['x']) * src_w * scale)
        midline_x = (landmarks[1]['x'] * src_w - x0) * scale
    else:
        pts = np.where(skin_support); face_width = max(10., float(pts[1].max() - pts[1].min()) if len(pts[0]) else float(w)); midline_x = w / 2.
    dist = {}; accepted, rejected = [], []
    for b in boxes:
        bx, by, ex, ey = (float(v) for v in b[:4]); conf = b[4] if len(b) > 4 else None
        px, py = (bx + ex) / 2., (by + ey) / 2.
        rec = dict(point=[px, py], score=conf, box=[bx, by, ex, ey])
        def rej(reason): rejected.append(dict(rec, reason=reason))
        if not (math.isfinite(px) and math.isfinite(py)): rej('POINT_NOT_FINITE'); continue
        if px < 0 or py < 0 or px >= src_w or py >= src_h: rej('POINT_OUTSIDE_IMAGE'); continue
        mx, my = (px - x0) * scale, (py - y0) * scale
        if not (0 <= mx < w and 0 <= my < h): rej('POINT_OUTSIDE_SCOPE'); continue
        cx, cy = int(math.floor(mx)), int(math.floor(my))
        if exclusion[cy, cx]: rej('POINT_ON_EXCLUSION'); continue
        if hair[cy, cx]: rej('POINT_ON_HAIR'); continue
        if not skin_support[cy, cx]: rej('POINT_NOT_SKIN_SUPPORT'); continue
        members = [k for k in regions if envelopes[k][cy, cx]]
        if members: owner, why = members[0], 'POINT_IN_ENVELOPE' + ('' if len(members) == 1 else '(first of ' + ','.join(members) + ')')
        else:
            best, owner = float('inf'), None
            for k in regions:
                if k == 'leftCheek' and cx < midline_x - face_width * .05: continue
                if k == 'rightCheek' and cx > midline_x + face_width * .05: continue
                if k not in dist: dist[k] = cv2.distanceTransform((~envelopes[k]).astype(np.uint8), cv2.DIST_L2, 3)
                d = float(dist[k][cy, cx])
                if d < best: best, owner = d, k
            nd = best / face_width if owner else float('inf')
            if owner is None or nd > .15: rej('POINT_UNCERTAIN_REGION'); continue
            why = f'POINT_DISTANCE_FALLBACK(norm_dist={nd:.3f})'
        accepted.append(dict(rec, region=owner, reason=why, coordinateSpace='source-pixels', localization='detection-point',
                             candidateId=hashlib.sha256(f'{photo}:{px:.3f}:{py:.3f}'.encode()).hexdigest()[:24]))
    return accepted, rejected
