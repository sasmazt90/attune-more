"""Offline staging only; selected from frozen AG d90ff954.
Thresholds were exposed to Scope B; no independent acceptance claim.
Not connected to production configuration.
"""

import math
import hashlib
from typing import Dict, List, Tuple
import cv2
import numpy as np
import acne_box_support

VERSION = 'source-box-anatomical-principled-staging-v1'
REGIONS = acne_box_support.REGIONS


def principled_accepted_boxes(
    boxes: List[List[float]],
    envelopes: Dict[str, np.ndarray],
    skin_support: np.ndarray,
    hair: np.ndarray,
    exclusion: np.ndarray,
    photo: str,
    scale: float,
    origin: Tuple[int, int],
    visible_regions: List[str] = None,
    landmarks: List[dict] = None,
    source_shape: Tuple[int, int] = None,
    bgr: np.ndarray = None,
    max_hair_area_frac: float = 0.25,
    min_skin_support_frac: float = 0.50,
    min_rel_erythema: float = 0.045,
    min_contrast_diff: float = 18.0
) -> Tuple[Dict[str, List[dict]], List[dict]]:
    """Principled anatomical support filter for staging evaluation."""
    assigned = {k: [] for k in envelopes}
    rejected = []
    h, w = skin_support.shape
    x0, y0 = origin
    candidate_regions = [k for k in REGIONS if k in envelopes and (visible_regions is None or k in visible_regions)]
    source_w = float(source_shape[1]) if source_shape is not None and len(source_shape) >= 2 else (float(w / scale + x0) if scale > 0 else float(w))

    if landmarks and len(landmarks) > 454 and isinstance(landmarks[454], dict) and isinstance(landmarks[234], dict):
        source_face_width = abs(landmarks[454]['x'] - landmarks[234]['x']) * source_w
        face_width = max(10.0, float(source_face_width * scale))
    else:
        skin_pts = np.where(skin_support)
        face_width = float(skin_pts[1].max() - skin_pts[1].min()) if len(skin_pts[0]) > 0 else float(w)
        face_width = max(10.0, face_width)

    if landmarks and len(landmarks) >= 2 and isinstance(landmarks[1], dict) and 'x' in landmarks[1]:
        source_midline_x = float(landmarks[1]['x'] * source_w)
        midline_x = float((source_midline_x - x0) * scale)
    else:
        midline_x = float(w / 2)

    dist_maps = {}
    for bx, by, ex, ey, confidence in boxes:
        a = max(0, int((bx - x0) * scale))
        b = max(0, int((by - y0) * scale))
        c = min(w, int(math.ceil((ex - x0) * scale)))
        d = min(h, int(math.ceil((ey - y0) * scale)))

        if c <= a or d <= b:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='OUTSIDE_SOURCE_SUPPORT'))
            continue

        cx = min(w - 1, max(0, int(((bx + ex) / 2.0 - x0) * scale)))
        cy = min(h - 1, max(0, int(((by + ey) / 2.0 - y0) * scale)))

        box_excl = float((exclusion[b:d, a:c] > 0).mean())
        box_hair = float((hair[b:d, a:c] > 0).mean())
        box_skin = float(skin_support[b:d, a:c].mean())

        # Anatomical hole exclusion (eyes, nostrils, mouth)
        if exclusion[cy, cx] or box_excl > 0.25:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HOLE', hair_frac=box_hair, skin_frac=box_skin, excl_frac=box_excl))
            continue

        # Dense hair / beard rejection
        if box_hair > max_hair_area_frac:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HAIR_DENSE', hair_frac=box_hair, skin_frac=box_skin))
            continue

        # Center hair / pore check with principled contrast and erythema validation
        if hair[cy, cx] or not skin_support[cy, cx]:
            if box_skin >= min_skin_support_frac and box_hair <= max_hair_area_frac and bgr is not None:
                img_a = max(0, int(round(bx)))
                img_b = max(0, int(round(by)))
                img_c = min(bgr.shape[1], int(round(ex)))
                img_d = min(bgr.shape[0], int(round(ey)))
                if img_c <= img_a or img_d <= img_b:
                    rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='OUTSIDE_SOURCE_SUPPORT'))
                    continue

                patch = bgr[img_b:img_d, img_a:img_c].astype(np.float32)
                pad = 8
                pa = max(0, img_a - pad)
                pb = max(0, img_b - pad)
                pc = min(bgr.shape[1], img_c + pad)
                pd = min(bgr.shape[0], img_d + pad)
                ctx = bgr[pb:pd, pa:pc].astype(np.float32)

                p_ery = (patch[:, :, 2] - patch[:, :, 1]) / (patch[:, :, 2] + patch[:, :, 1] + 1e-5)
                c_ery = (ctx[:, :, 2] - ctx[:, :, 1]) / (ctx[:, :, 2] + ctx[:, :, 1] + 1e-5)
                rel_e = float(p_ery.mean() - c_ery.mean())
                c_diff = float(ctx.mean() - patch.mean())

                is_real_lesion = (rel_e >= min_rel_erythema) or (c_diff >= min_contrast_diff and rel_e >= 0.035)
                if not is_real_lesion:
                    rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HAIR_OR_NOT_SKIN', rel_erythema=round(rel_e, 4), contrast_diff=round(c_diff, 2)))
                    continue
            else:
                rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HAIR_OR_NOT_SKIN', hair_frac=box_hair, skin_frac=box_skin))
                continue

        # Insufficient skin support
        if box_skin < min_skin_support_frac:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='INSUFFICIENT_SKIN_SUPPORT', skin_frac=box_skin))
            continue

        # Regional assignment via envelope overlap or distance transform
        reg_overlaps = [(float((envelopes[k] & skin_support)[b:d, a:c].mean()), k) for k in candidate_regions]
        reg_overlaps.sort(reverse=True)

        if reg_overlaps and reg_overlaps[0][0] >= 0.15:
            owner = reg_overlaps[0][1]
            assign_reason = 'ENVELOPE_OVERLAP'
        else:
            best_dist = float('inf')
            best_candidate = None
            for k in candidate_regions:
                if k == 'leftCheek' and cx < midline_x - face_width * 0.05:
                    continue
                if k == 'rightCheek' and cx > midline_x + face_width * 0.05:
                    continue
                if k not in dist_maps:
                    dist_maps[k] = cv2.distanceTransform((~envelopes[k]).astype(np.uint8), cv2.DIST_L2, 3)
                d_val = float(dist_maps[k][cy, cx])
                if d_val < best_dist:
                    best_dist = d_val
                    best_candidate = k

            norm_dist = best_dist / face_width if best_candidate else float('inf')
            if best_candidate is not None and norm_dist <= 0.15:
                owner = best_candidate
                assign_reason = f'ANATOMICAL_DISTANCE_FALLBACK(norm_dist={norm_dist:.3f})'
            else:
                rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='UNCERTAIN_ANATOMICAL_REGION', norm_dist=round(norm_dist, 4) if best_candidate else None))
                continue

        cand_id = hashlib.sha256(f'{photo}:{bx:.3f}:{by:.3f}:{ex:.3f}:{ey:.3f}'.encode()).hexdigest()[:24]
        assigned[owner].append(dict(
            x=bx, y=by, width=ex - bx, height=ey - by,
            confidence=confidence, region=owner,
            assignmentReason=assign_reason, candidateId=cand_id,
            coordinateSpace='source-pixels', localization='detection-box'
        ))

    return assigned, rejected
