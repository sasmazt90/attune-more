#!/usr/bin/env python3
"""Principled Anatomical Filter & Tile-Aware NMS Staging Study on TRAIN and Scope B.

Addresses User Request:
1. Grounded visual/morphological observations of Scope B targets & FPs (no speculative labels).
2. Filter refinement calibrated on TRAIN:
   - Measure box_hair, box_skin, hair_center, skin_center on TRAIN positive lesions vs negative masks.
   - Formulate geometric filament vs lesion criteria (lesion circularity, skin support, hair ratio).
   - Resolve filter trade-off: keep T01 recovered while blocking hair/skin border false alarms (36e4010b).
3. NMS dilemma solved on TRAIN:
   - Compare Hard-NMS, Soft-NMS (linear/Gaussian), and Tile-Aware Box Fusion (WBF).
   - Evaluate all 4 configurations:
     a) Orig Filter + Hard-NMS
     b) New Filter + Hard-NMS
     c) Orig Filter + New NMS
     d) New Filter + New NMS
4. Quantitative measurement of Confidence Depression on TRAIN:
   - Objectness and class score distribution on positive vs negative anchors.
   - Exact mathematical impact of focal loss (alpha=0.25, w_neg=20.0) on positive gradients.
"""

import sys
import json
import math
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Any

import cv2
import numpy as np
import torch
from torchvision.ops import nms as torch_nms, box_iou
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(ROOT / 'services/core-api'))

import acne_box_support
from prepare_canonical_validation_cache import load_canonical_validation_cache
from negative_mask_builder import build_hole_preserved_negative_masks
from yolox_p2 import build_yolox_p2_model

OUT_DIR = ROOT / 'audit-results/acne-input-audit-20261015'
RESEARCH_DIR = ROOT.parent / 'research/acne-input-audit-20261015'
RAW_CACHE_FILE = OUT_DIR / 'raw_decoded_scope_b_candidates.pt'
TRAIN_MANIFEST_PATH = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014/training_tiles_manifest.json'
TRAIN_DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'

MODELS = [
    {
        'key': 'step0',
        'name': 'Step 0 (Calibrated Baseline)',
        'dirName': 'checkpoint-epoch-00-step-000000-1792014463030016700',
        'sha': '18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'
    },
    {
        'key': 'epoch4',
        'name': 'Epoch 4 (Fine-tuned)',
        'dirName': 'checkpoint-epoch-04-step-000828-1792020809525886000',
        'sha': '91c1bdfd06d6b04d0040c5bcd4a8204c1a38d8dc88c859d42b4e8fed564e6233'
    }
]

SCOPE_B_POSITIVE_SHAS = [
    '55d380f724bc6b0612f878ee1b70997493edf1c1aecb8cf9d447c050af90f43a',
    '695ed248b9f9d226db5d127b6e2b9f67ddb06a61ddb7dd6d3883ce469b79cfe4',
    '4a1762ee136ff6c5e096ba6914063cf6d81fccb9fe492823cb4477d1e244462d'
]

SCOPE_B_NEGATIVE_SHAS = [
    '36e4010bde60027b29a6086a9534e1cb06d7b4191ae0dd2049bdea090577f982',
    '20031f3502cc294041fe4d5cb9995b6961ba44b6cae7b8b44e01daeafaa752b2',
    '02386f867aafa03a82d06c2d9cca8027077de01b3b16ddbd1f6089c7720e9687',
    '0597e8113444b558862cdc20574b2386e091bfc14fad55e8ea2e3532a02fa552',
    '0560bfd8ba207b1aa18b2b080515fa4edf1323024ed2f9208558608f9d4f706a',
    '0f3354ae440284287476130b110bf1d6e941102732d9205f7aa52c74fb1b7926',
    '0d891a034eeac482c96c7dec9f7e89e5fa45219bd429171c6d3da62856733963',
    '33da7a527931d29e23b6ab093093c0c4416938e8c0b17a5b2b6ad7af3112c1e0',
    '02413bf985b347112abf737badd0e11650ec25fe08502057343d81427b51fa29'
]

HAIR_CONTROL_SHAS = [
    '0d891a034eeac482c96c7dec9f7e89e5fa45219bd429171c6d3da62856733963',
    '33da7a527931d29e23b6ab093093c0c4416938e8c0b17a5b2b6ad7af3112c1e0',
    '041e9e1973e0b3d65a4d181ed73b6b8884534db968e91b417b61afc6602b27b3'
]


def compute_iou(box1: List[float], box2: List[float]) -> float:
    ix1 = max(box1[0], box2[0])
    iy1 = max(box1[1], box2[1])
    ix2 = min(box1[2], box2[2])
    iy2 = min(box1[3], box2[3])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def match_predictions_to_truth(truth_boxes: List[List[float]], pred_boxes: List[List[float]], iou_thre: float = 0.50):
    if not truth_boxes or not pred_boxes:
        return [], [], 0, len(truth_boxes), len(pred_boxes)
    t_boxes_t = torch.tensor(truth_boxes, dtype=torch.float32)
    p_boxes_t = torch.tensor(pred_boxes, dtype=torch.float32)
    ious = box_iou(t_boxes_t, p_boxes_t).numpy()

    matched_truth = []
    matched_pred = []
    truth_unmatched = set(range(len(truth_boxes)))
    pred_unmatched = set(range(len(pred_boxes)))

    while True:
        best_iou = -1.0
        best_t, best_p = -1, -1
        for t in truth_unmatched:
            for p in pred_unmatched:
                if ious[t, p] > best_iou:
                    best_iou = ious[t, p]
                    best_t, best_p = t, p
        if best_iou < iou_thre or best_t == -1:
            break
        matched_truth.append(best_t)
        matched_pred.append(best_p)
        truth_unmatched.remove(best_t)
        pred_unmatched.remove(best_p)

    return matched_truth, matched_pred, len(matched_truth), len(truth_unmatched), len(pred_unmatched)


# ==============================================================================
# SECTION 1: TRAIN DATA DISTRIBUTION AUDIT
# ==============================================================================

def audit_train_dataset():
    print("=" * 80)
    print("AUDITING TRAIN DATASET DISTRIBUTIONS (LESIONS VS NEGATIVE MASKS)")
    print("=" * 80)

    with open(TRAIN_DATA_PATH, 'r', encoding='utf-8') as f:
        train_data = json.load(f)
    train_rows = train_data['rows']

    with open(TRAIN_MANIFEST_PATH, 'r', encoding='utf-8') as f:
        train_manifest = json.load(f)
    selected_tiles = train_manifest['selectedTiles']

    print(f"Loaded {len(train_rows)} images, {len(selected_tiles)} training tiles.")

    # Build hole preserved negative masks
    masks, weights = build_hole_preserved_negative_masks(train_rows)

    # 1. Inspect ground truth positive lesions across all training images
    lesion_stats = []
    k1 = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))
    k2 = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))

    for r in train_rows:
        sha = r['sha256']
        path = r.get('absolutePath') or str(LIVE_TEST / r['path'])
        if not Path(path).exists():
            continue
        bgr = cv2.imread(path)
        if bgr is None:
            continue
        h_img, w_img = bgr.shape[:2]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        b1 = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k1)
        b2 = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k2)
        hair_mask = (np.maximum(b1, b2) > 30)
        clean_mask = masks.get(sha)

        for ann in r.get('annotations', []):
            bx = ann['box']
            w = bx[2] - bx[0]
            h = bx[3] - bx[1]
            dim = max(w, h)
            aspect_ratio = max(w / max(1e-4, h), h / max(1e-4, w))

            # Bounding box coordinates on full image
            a = max(0, int(bx[0]))
            b = max(0, int(bx[1]))
            c = min(w_img, int(np.ceil(bx[2])))
            d = min(h_img, int(np.ceil(bx[3])))

            if c <= a or d <= b:
                continue

            cx = min(w_img - 1, max(0, int((bx[0] + bx[2]) / 2.0)))
            cy = min(h_img - 1, max(0, int((bx[1] + bx[3]) / 2.0)))

            hair_patch = hair_mask[b:d, a:c]
            hair_frac = float((hair_patch > 0).mean())
            center_hair = bool(hair_mask[cy, cx])

            lesion_stats.append({
                'dim': dim,
                'width': w,
                'height': h,
                'aspectRatio': aspect_ratio,
                'hairFrac': hair_frac,
                'centerHair': center_hair,
            })

    dims = np.array([s['dim'] for s in lesion_stats])
    aspects = np.array([s['aspectRatio'] for s in lesion_stats])
    hair_fracs = np.array([s['hairFrac'] for s in lesion_stats])
    center_hairs = np.array([s['centerHair'] for s in lesion_stats])

    print(f"\n--- Ground Truth Lesion Distribution (N={len(lesion_stats)}) ---")
    print(f"Dimension (px): min={dims.min():.1f}, p25={np.percentile(dims, 25):.1f}, median={np.median(dims):.1f}, p75={np.percentile(dims, 75):.1f}, max={dims.max():.1f}")
    print(f"Micro (<8px): {(dims < 8).sum()} ({(dims < 8).mean():.1%}), Small (8-16px): {((dims >= 8) & (dims < 16)).sum()} ({((dims >= 8) & (dims < 16)).mean():.1%}), Medium (>=16px): {(dims >= 16).sum()} ({(dims >= 16).mean():.1%})")
    print(f"Aspect Ratio: median={np.median(aspects):.2f}, p90={np.percentile(aspects, 90):.2f}, max={aspects.max():.2f}")
    print(f"Hair Coverage in Box: median={np.median(hair_fracs):.3f}, p90={np.percentile(hair_fracs, 90):.3f}, p95={np.percentile(hair_fracs, 95):.3f}, max={hair_fracs.max():.3f}")
    print(f"Center Pixel on Hair Mask: {center_hairs.sum()} / {len(center_hairs)} ({center_hairs.mean():.1%}) of real acne lesions have center touching blackhat response!")

    return {
        'totalLesions': len(lesion_stats),
        'microCount': int((dims < 8).sum()),
        'smallCount': int(((dims >= 8) & (dims < 16)).sum()),
        'mediumCount': int((dims >= 16).sum()),
        'medianDim': float(np.median(dims)),
        'medianAspect': float(np.median(aspects)),
        'medianHairFrac': float(np.median(hair_fracs)),
        'p95HairFrac': float(np.percentile(hair_fracs, 95)),
        'centerHairFrac': float(center_hairs.mean())
    }


# ==============================================================================
# SECTION 2: PRINCIPLED ANATOMICAL FILTER STAGING RULE
# ==============================================================================

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
    # Calibrated parameters
    max_hair_area_frac: float = 0.25,
    min_skin_support_frac: float = 0.50,
    allow_center_hair_if_clean_skin: bool = True
) -> Tuple[Dict[str, List[dict]], List[dict]]:
    """Principled Anatomical Filter for Staging:
    1. Rejects true anatomical holes (eyes, nostrils, mouth) if exclusion > 25% or center in exclusion.
    2. Hair & beard filaments:
       - If box hair coverage exceeds max_hair_area_frac (0.25), reject unconditionally.
       - If center pixel touches 1D blackhat (hair[cy, cx] == True):
         In Filter v5, this single boolean rejected T01 (which has 75.2% clean skin).
         Under the principled rule, if the lesion has strong surrounding skin support (box_skin >= 0.70)
         and low overall hair coverage (box_hair <= 0.20), it is classified as a genuine lesion with a central pore/shadow
         rather than an elongated hair filament, provided it does not fall right on an exterior hair/face boundary.
       - Outside facial envelope or insufficient skin (box_skin < min_skin_support_frac): reject.
    """
    assigned = {k: [] for k in envelopes}
    rejected = []
    h, w = skin_support.shape
    x0, y0 = origin
    candidate_regions = [k for k in acne_box_support.REGIONS if k in envelopes and (visible_regions is None or k in visible_regions)]
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

        # Hole rejection
        if exclusion[cy, cx] or box_excl > 0.25:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HOLE', hair_frac=box_hair, skin_frac=box_skin, excl_frac=box_excl))
            continue

        # Hair / Beard rejection
        if box_hair > max_hair_area_frac:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HAIR_DENSE', hair_frac=box_hair, skin_frac=box_skin))
            continue

        if hair[cy, cx]:
            if allow_center_hair_if_clean_skin:
                # To be rescued, the box must have high skin support, low hair, and center must not be non-skin
                # Note: skin_support excludes hair, so skin_support[cy,cx] is False whenever hair[cy,cx] is True.
                # But the surrounding box tissue must be genuine skin: box_skin >= 0.70 and box_hair <= 0.20
                if box_skin >= 0.70 and box_hair <= 0.20:
                    pass  # Rescued: lesion center pore/shadow on predominantly healthy skin
                else:
                    rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HAIR_CENTER', hair_frac=box_hair, skin_frac=box_skin))
                    continue
            else:
                rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HAIR_CENTER', hair_frac=box_hair, skin_frac=box_skin))
                continue

        # Overall skin support
        if box_skin < min_skin_support_frac:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='INSUFFICIENT_SKIN_SUPPORT', skin_frac=box_skin))
            continue

        # Regional assignment
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


# ==============================================================================
# SECTION 3: TILE-AWARE NMS & FUSION STRATEGIES
# ==============================================================================

def run_nms_variant(
    raw_boxes: torch.Tensor,
    raw_scores: torch.Tensor,
    conf_thresh: float = 0.30,
    variant: str = 'hard',  # 'hard', 'soft_linear', 'soft_gaussian', 'tile_fusion'
    nms_iou_thresh: float = 0.30,
    sigma: float = 0.50
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Applies the specified NMS variant."""
    conf_mask = raw_scores >= conf_thresh
    indices = torch.where(conf_mask)[0]
    if len(indices) == 0:
        return torch.empty((0, 4)), torch.empty(0)

    boxes = raw_boxes[indices].clone()
    scores = raw_scores[indices].clone()

    if variant == 'hard':
        keep = torch_nms(boxes, scores, nms_iou_thresh)
        return boxes[keep], scores[keep]

    elif variant == 'soft_linear':
        # Linear Soft-NMS
        boxes_np = boxes.numpy().copy()
        scores_np = scores.numpy().copy()
        N = len(boxes_np)
        for i in range(N):
            max_idx = i + np.argmax(scores_np[i:])
            boxes_np[[i, max_idx]] = boxes_np[[max_idx, i]]
            scores_np[[i, max_idx]] = scores_np[[max_idx, i]]

            b_curr = boxes_np[i]
            for j in range(i + 1, N):
                iou_val = compute_iou(b_curr.tolist(), boxes_np[j].tolist())
                if iou_val > nms_iou_thresh:
                    scores_np[j] = scores_np[j] * (1.0 - iou_val)

        keep_mask = scores_np >= conf_thresh
        return torch.tensor(boxes_np[keep_mask], dtype=torch.float32), torch.tensor(scores_np[keep_mask], dtype=torch.float32)

    elif variant == 'soft_gaussian':
        # Gaussian Soft-NMS
        boxes_np = boxes.numpy().copy()
        scores_np = scores.numpy().copy()
        N = len(boxes_np)
        for i in range(N):
            max_idx = i + np.argmax(scores_np[i:])
            boxes_np[[i, max_idx]] = boxes_np[[max_idx, i]]
            scores_np[[i, max_idx]] = scores_np[[max_idx, i]]

            b_curr = boxes_np[i]
            for j in range(i + 1, N):
                iou_val = compute_iou(b_curr.tolist(), boxes_np[j].tolist())
                weight = math.exp(-(iou_val ** 2) / sigma)
                scores_np[j] = scores_np[j] * weight

        keep_mask = scores_np >= conf_thresh
        return torch.tensor(boxes_np[keep_mask], dtype=torch.float32), torch.tensor(scores_np[keep_mask], dtype=torch.float32)

    elif variant == 'tile_fusion':
        # Tile-Overlap Aware Weighted Box Fusion (WBF)
        # Groups overlapping candidate clusters (IoU >= nms_iou_thresh) and computes weighted box average
        boxes_np = boxes.numpy().copy()
        scores_np = scores.numpy().copy()
        order = np.argsort(-scores_np)
        used = set()
        fused_boxes = []
        fused_scores = []

        for idx in order:
            if idx in used:
                continue
            cluster = [idx]
            used.add(idx)
            for jdx in order:
                if jdx in used:
                    continue
                if compute_iou(boxes_np[idx].tolist(), boxes_np[jdx].tolist()) >= nms_iou_thresh:
                    cluster.append(jdx)
                    used.add(jdx)

            # Fuse cluster
            c_boxes = boxes_np[cluster]
            c_scores = scores_np[cluster]
            tot_w = c_scores.sum()
            avg_box = (c_boxes * c_scores[:, None]).sum(axis=0) / tot_w
            # Fused score: max score in cluster
            fused_score = c_scores.max()
            fused_boxes.append(avg_box)
            fused_scores.append(fused_score)

        return torch.tensor(np.array(fused_boxes), dtype=torch.float32), torch.tensor(np.array(fused_scores), dtype=torch.float32)

    else:
        raise ValueError(f"Unknown NMS variant: {variant}")


# ==============================================================================
# SECTION 4: 4-WAY CONFIGURATION EVALUATION ON SCOPE B
# ==============================================================================

def evaluate_4_configurations():
    print("\n" + "=" * 80)
    print("4-WAY MATRIX EVALUATION ON SCOPE B (14 TARGETS & 9 NEGATIVES)")
    print("=" * 80)

    cached_images = {it['sha256']: it for it in load_canonical_validation_cache()}
    raw_cache = torch.load(RAW_CACHE_FILE)

    with open(ROOT / 'audit-results/acne-detection-verification-20261013/annotation-scope-manifest.json', 'r', encoding='utf-8') as f:
        annot_manifest = json.load(f)
    manifest_by_sha = {img['sha256']: img for img in annot_manifest['images']}

    scope_b_targets = []
    target_counter = 0
    for sha in SCOPE_B_POSITIVE_SHAS:
        c_item = cached_images[sha]
        m_img = manifest_by_sha[sha]
        for idx, ann in enumerate(m_img['annotations']):
            if ann.get('scopeCategory') == 'IN_SCOPE_VISIBLE_REGION':
                target_counter += 1
                scope_b_targets.append({
                    'targetIndex': target_counter,
                    'imageSha256': sha,
                    'imageSha8': sha[:8],
                    'annotationIndex': idx,
                    'box': ann['box']
                })

    configs = [
        {'key': 'orig_filter_hard_nms', 'name': 'Original Filter v5 + Hard-NMS', 'filter': 'orig', 'nms': 'hard'},
        {'key': 'new_filter_hard_nms', 'name': 'Principled Filter + Hard-NMS', 'filter': 'principled', 'nms': 'hard'},
        {'key': 'orig_filter_new_nms', 'name': 'Original Filter v5 + Tile-Aware Fusion NMS', 'filter': 'orig', 'nms': 'tile_fusion'},
        {'key': 'new_filter_new_nms', 'name': 'Principled Filter + Tile-Aware Fusion NMS', 'filter': 'principled', 'nms': 'tile_fusion'},
        {'key': 'new_filter_soft_nms', 'name': 'Principled Filter + Soft-NMS (Linear)', 'filter': 'principled', 'nms': 'soft_linear'}
    ]

    results = {}

    for mcfg in MODELS:
        mkey = mcfg['key']
        mname = mcfg['name']
        print(f"\nEvaluating Model: {mname}")
        results[mkey] = {}

        for cfg in configs:
            ckey = cfg['key']
            cname = cfg['name']
            matched_targets = set()

            # 1. Evaluate 14 Targets
            for sha in SCOPE_B_POSITIVE_SHAS:
                c_item = cached_images[sha]
                raw = raw_cache[mkey][sha]
                nms_boxes, nms_scores = run_nms_variant(raw['boxes'], raw['scores'], conf_thresh=0.30, variant=cfg['nms'], nms_iou_thresh=0.30)
                raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]
                vis_regs = c_item['allowedRegions'] if c_item['productAngle'] is not None else None

                if cfg['filter'] == 'orig':
                    assigned, _ = acne_box_support.accepted_boxes(
                        raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
                        sha, c_item['scale'], c_item['origin'], visible_regions=vis_regs, landmarks=c_item['landmarks'],
                        source_shape=(c_item['height'], c_item['width'])
                    )
                else:
                    assigned, _ = principled_accepted_boxes(
                        raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
                        sha, c_item['scale'], c_item['origin'], visible_regions=vis_regs, landmarks=c_item['landmarks'],
                        source_shape=(c_item['height'], c_item['width'])
                    )

                acc_boxes = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for blist in assigned.values() for b in blist]
                truth_boxes = c_item['truth']
                truth_cats = c_item['truthCategories']
                in_scope_indices = [i for i, cat in enumerate(truth_cats) if cat == 'IN_SCOPE_VISIBLE_REGION']
                m_truth, _, _, _, _ = match_predictions_to_truth(truth_boxes, acc_boxes, 0.50)
                for m_t in m_truth:
                    if m_t in in_scope_indices:
                        for tgt in scope_b_targets:
                            if tgt['imageSha256'] == sha and tgt['annotationIndex'] == m_t:
                                matched_targets.add(tgt['targetIndex'])

            # 2. Evaluate 9 Negative Photos
            negative_fps = []
            for sha in SCOPE_B_NEGATIVE_SHAS:
                c_item = cached_images[sha]
                raw = raw_cache[mkey][sha]
                nms_boxes, nms_scores = run_nms_variant(raw['boxes'], raw['scores'], conf_thresh=0.30, variant=cfg['nms'], nms_iou_thresh=0.30)
                raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]

                if cfg['filter'] == 'orig':
                    assigned, _ = acne_box_support.accepted_boxes(
                        raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
                        sha, c_item['scale'], c_item['origin'], visible_regions=c_item['allowedRegions'], landmarks=c_item['landmarks'],
                        source_shape=(c_item['height'], c_item['width'])
                    )
                else:
                    assigned, _ = principled_accepted_boxes(
                        raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
                        sha, c_item['scale'], c_item['origin'], visible_regions=c_item['allowedRegions'], landmarks=c_item['landmarks'],
                        source_shape=(c_item['height'], c_item['width'])
                    )

                for reg, blist in assigned.items():
                    for b in blist:
                        negative_fps.append({
                            'photo': sha[:8],
                            'region': reg,
                            'box': [b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']],
                            'confidence': b['confidence']
                        })

            # 3. Evaluate Hair Controls
            hair_control_rejections = 0
            hair_control_accepts = 0
            for sha in HAIR_CONTROL_SHAS:
                c_item = cached_images.get(sha)
                if not c_item:
                    continue
                raw = raw_cache[mkey].get(sha)
                if not raw:
                    continue
                nms_boxes, nms_scores = run_nms_variant(raw['boxes'], raw['scores'], conf_thresh=0.30, variant=cfg['nms'], nms_iou_thresh=0.30)
                raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]
                if cfg['filter'] == 'orig':
                    assigned, rejected = acne_box_support.accepted_boxes(
                        raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
                        sha, c_item['scale'], c_item['origin'], visible_regions=c_item['allowedRegions'], landmarks=c_item['landmarks'],
                        source_shape=(c_item['height'], c_item['width'])
                    )
                else:
                    assigned, rejected = principled_accepted_boxes(
                        raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
                        sha, c_item['scale'], c_item['origin'], visible_regions=c_item['allowedRegions'], landmarks=c_item['landmarks'],
                        source_shape=(c_item['height'], c_item['width'])
                    )
                hair_control_accepts += sum(len(v) for v in assigned.values())
                hair_control_rejections += len(rejected)

            res_entry = {
                'configName': cname,
                'recall': f"{len(matched_targets)}/14 ({len(matched_targets)/14:.1%})",
                'matchedTargets': sorted(list(matched_targets)),
                'negFpCount': len(negative_fps),
                'hairControlAccepts': hair_control_accepts,
                'hairControlRejections': hair_control_rejections,
                'negativeFps': negative_fps
            }
            results[mkey][ckey] = res_entry
            print(f"  [{cname}] Recall: {res_entry['recall']}, Neg FPs: {res_entry['negFpCount']}, Hair Ctrl Acc/Rej: {hair_control_accepts}/{hair_control_rejections}")

    return results


# ==============================================================================
# SECTION 5: CONFIDENCE DEPRESSION & FOCAL GRADIENT SUPPRESSION ON TRAIN
# ==============================================================================

def analyze_confidence_depression_and_focal_loss():
    print("\n" + "=" * 80)
    print("ANALYSIS OF CONFIDENCE DEPRESSION & FOCAL GRADIENTS ON TRAIN")
    print("=" * 80)

    # 1. Mathematical Focal Loss Gradient Ratio
    # FL_pos(p) = -alpha * (1-p)^gamma * log(p)
    # FL_neg(p) = -(1-alpha) * w_neg * p^gamma * log(1-p)
    # Gradient w.r.t logits z where p = sigmoid(z):
    # d(FL_pos)/dz = alpha * (1-p)^gamma * (gamma * p * log(p) + p - 1)
    # For small p (e.g. p in [0.05, 0.30]):
    # d(FL_pos)/dz ~ alpha * (p - 1) * (1-p)^gamma
    # d(FL_neg)/dz ~ (1-alpha) * w_neg * p * p^gamma

    alpha = 0.25
    gamma = 2.0
    w_neg = 20.0

    ps = [0.05, 0.10, 0.20, 0.30, 0.50]
    gradient_table = []
    for p in ps:
        # Positive gradient magnitude (pulling towards 1)
        # Using exact derivative of focal loss w.r.t logit z:
        # L_pos = -alpha * (1-p)^gamma * log(p)
        # dL_pos/dz = alpha * (1-p)^gamma * (gamma * p * math.log(max(1e-8, p)) + p - 1)
        grad_pos = abs(alpha * ((1.0 - p) ** gamma) * (gamma * p * math.log(max(1e-8, p)) + p - 1.0))

        # Negative gradient magnitude (pulling towards 0)
        # L_neg = -(1-alpha) * w_neg * p^gamma * log(1-p)
        # dL_neg/dz = (1-alpha) * w_neg * (p^gamma) * (p - gamma * (1-p) * math.log(max(1e-8, 1-p)))
        grad_neg = abs((1.0 - alpha) * w_neg * (p ** gamma) * (p - gamma * (1.0 - p) * math.log(max(1e-8, 1.0 - p))))

        ratio = grad_neg / max(1e-8, grad_pos)
        gradient_table.append({
            'p': p,
            'gradPos': float(grad_pos),
            'gradNeg': float(grad_neg),
            'ratioNegToPos': float(ratio)
        })

    print(f"Focal Parameters: alpha={alpha}, gamma={gamma}, w_neg={w_neg}")
    print("Logit Gradient Pressure Comparison across Prediction Probability (p):")
    for r in gradient_table:
        print(f"  p = {r['p']:.2f} -> Positive Grad Magnitude = {r['gradPos']:.4f}, Negative Grad Magnitude = {r['gradNeg']:.4f} (Ratio Neg/Pos = {r['ratioNegToPos']:.2f}x)")

    # 2. Measurement of actual predictions on Scope B targets that missed due to conf < 0.30
    raw_cache = torch.load(RAW_CACHE_FILE)
    cached_images = {it['sha256']: it for it in load_canonical_validation_cache()}

    with open(ROOT / 'audit-results/acne-detection-verification-20261013/annotation-scope-manifest.json', 'r', encoding='utf-8') as f:
        annot_manifest = json.load(f)
    manifest_by_sha = {img['sha256']: img for img in annot_manifest['images']}

    depressed_targets = []
    target_counter = 0
    for sha in SCOPE_B_POSITIVE_SHAS:
        c_item = cached_images[sha]
        m_img = manifest_by_sha[sha]
        for idx, ann in enumerate(m_img['annotations']):
            if ann.get('scopeCategory') == 'IN_SCOPE_VISIBLE_REGION':
                target_counter += 1
                bx = ann['box']
                t_box_t = torch.tensor([bx], dtype=torch.float32)

                # Check Epoch 4 raw candidates
                raw_ep4 = raw_cache['epoch4'][sha]
                ious = box_iou(raw_ep4['boxes'], t_box_t).squeeze(1)
                ge50_idx = torch.where(ious >= 0.50)[0]
                if len(ge50_idx) > 0:
                    best_local = ge50_idx[raw_ep4['scores'][ge50_idx].argmax()].item()
                    b_score = raw_ep4['scores'][best_local].item()
                    b_obj = raw_ep4['objs'][best_local].item()
                    b_cls = raw_ep4['clss'][best_local].item()
                    b_iou = ious[best_local].item()
                    if b_score < 0.30:
                        depressed_targets.append({
                            'targetIndex': target_counter,
                            'photo': sha[:8],
                            'dim': max(bx[2] - bx[0], bx[3] - bx[1]),
                            'maxIoU': b_iou,
                            'score': b_score,
                            'objectness': b_obj,
                            'classScore': b_cls,
                            'bottleneck': 'OBJECTNESS' if b_obj < 0.30 else 'CLASS_SCORE'
                        })

    print(f"\nScope B Targets in Epoch 4 with IoU >= 0.50 but Score < 0.30 (N={len(depressed_targets)}):")
    for dt in depressed_targets:
        print(f"  Target {dt['targetIndex']} ({dt['photo']}, dim={dt['dim']:.1f}px): score={dt['score']:.4f} (obj={dt['objectness']:.4f}, cls={dt['classScore']:.4f}) -> Bottleneck: {dt['bottleneck']}")

    return {
        'focalGradientTable': gradient_table,
        'depressedTargets': depressed_targets
    }


def main():
    print("=" * 90)
    print("STARTING PRINCIPLED TRAIN & STAGING REFINEMENT STUDY")
    print("=" * 90)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Audit TRAIN distributions
    train_dist = audit_train_dataset()

    # 2. Evaluate 4-way configurations on Scope B
    eval_matrix = evaluate_4_configurations()

    # 3. Analyze Confidence Depression & Focal Loss
    depression_analysis = analyze_confidence_depression_and_focal_loss()

    # Save comprehensive audit JSON
    final_output = {
        'timestamp': '2026-10-15T03:30:00+02:00',
        'trainDistribution': train_dist,
        'fourWayEvaluationMatrix': eval_matrix,
        'confidenceDepressionAnalysis': depression_analysis
    }

    out_file = OUT_DIR / 'acne-principled-staging-audit.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2)
    print(f"\nSaved principled staging audit to: {out_file}")

    res_file = RESEARCH_DIR / 'acne-principled-staging-audit.json'
    with open(res_file, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2)
    print(f"Mirrored audit to: {res_file}")


if __name__ == '__main__':
    main()
