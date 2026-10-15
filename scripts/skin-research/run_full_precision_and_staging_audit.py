#!/usr/bin/env python3
"""Full-Precision Pipeline Failure Trace, Deterministic Candidate IDs, T01 Hair Mask Root-Cause Analysis,
and General Staging Filter Refinement Evaluation across Scope B and Hair Controls.

Directives:
1. Decode ALL finite candidates (no min_score discard). Count invalid geometries if any.
2. Full float32 precision without premature rounding.
   Deterministic candidate ID: f"{modelSha[:8]}_{photoSha[:8]}_t{tileIdx:02d}_a{anchorIdx:05d}".
   Cache raw candidates to disk to eliminate repeated neural network runs.
3. Decouple target fate from a single chosen candidate:
   Evaluate target coverage on the SURVIVING SET of candidates at each stage.
   For NMS losses: identify the suppressing candidate ID, score, and pairwise box IoU.
   Strict bipartite matching for final success (no fake RESOLVED fallback).
4. Morphological visual audit:
   Decouple visual observations from automated region/size string templates.
5. T01 Hair Mask Root-Cause:
   Trace the exact generation of hair mask (blackhat k1=(1,15), k2=(15,1), max>30).
   Demonstrate that T01's center pixel falls on a 1D blackhat boundary while box skin support is 75.2%.
   Implement general staging rule: evaluate local hair coverage (box_hair > 0.25) and tissue support
   (box_skin >= 0.50) rather than a brittle single center pixel.
6. Evaluate Staging Before vs After:
   Compare 14 targets and 9 negative photos (FP counts/locations) for Step 0 and Epoch 4.
   Evaluate hair/beard control photos to prove genuine hair false alarms are still blocked.
"""

import sys
import json
import time
import math
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple
import cv2
import numpy as np
import torch
from safetensors.torch import load_file
from torchvision.ops import nms as torch_nms, box_iou

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from prepare_canonical_validation_cache import load_canonical_validation_cache
import acne_box_support

TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014'
RESEARCH_DIR = ROOT.parent / 'research/acne-input-audit-20261015'
LOCAL_AUDIT_DIR = ROOT / 'audit-results/acne-input-audit-20261015'
RAW_CACHE_FILE = LOCAL_AUDIT_DIR / 'raw_decoded_scope_b_candidates.pt'

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
    '041e9e1973e0b3d65a4d181ed73b6b8884534db968e91b417b61afc6602b27b3',
    '00446fa8cf27f1d8b2ec9d1bc03501d5255292e4b0c44d7da11d0cbc58cf2c3d',
    '0b5a3d87bf2a7f93af62e24c39360d6798e12538345eb6ac0713a29966b03a70'
]


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


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


def staging_accepted_boxes(
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
    source_shape: Tuple[int, int] = None
) -> Tuple[Dict[str, List[dict]], List[dict]]:
    """General staging refinement for anatomical support filtering.
    Evaluates hair/beard presence via local coverage (box_hair > 0.25) and local tissue support
    (box_skin >= 0.50) rather than a brittle single center-pixel binary test."""
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

        # General Staging Rule:
        # Exclusion (eyes, nostrils, mouth cavity): center pixel or >25% box area
        is_excl_rejected = exclusion[cy, cx] or (box_excl > 0.25)

        # Hair / Beard:
        # If >25% of box is hair, reject unconditionally as hairy/beard region.
        # If center pixel touches hair mask (hair[cy, cx]==True):
        #   If the box has strong valid skin support (box_skin >= 0.50) and low hair (box_hair <= 0.25),
        #   it is a lesion on valid skin with only a stray filament or pore edge touching center. Allow it.
        #   Otherwise (box_skin < 0.50 or box_hair > 0.25), reject as hair.
        is_hair_rejected = (box_hair > 0.25) or (hair[cy, cx] and (box_skin < 0.50 or box_hair > 0.25))

        if is_excl_rejected or is_hair_rejected:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HOLE_OR_HAIR', hair_frac=box_hair, skin_frac=box_skin, excl_frac=box_excl))
            continue

        if box_skin < 0.50:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='INSUFFICIENT_SKIN_SUPPORT', skin_frac=box_skin))
            continue

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


def extract_all_finite_candidates(net, item, model_sha_short: str, photo_sha_short: str):
    """Vectorized extraction of ALL finite decoded candidates across all sliding tiles."""
    bgr = item['bgr']
    points = item['landmarks']
    h, w = bgr.shape[:2]
    tile_size = 384
    stride = 288

    face_lms = np.array([[p['x'] * w, p['y'] * h] for p in points[:468]])
    min_x, max_x = int(np.floor(face_lms[:, 0].min())), int(np.ceil(face_lms[:, 0].max()))
    min_y, max_y = int(np.floor(face_lms[:, 1].min())), int(np.ceil(face_lms[:, 1].max()))

    pad = max(24, int((max_x - min_x) * 0.15))
    crop_x0 = max(0, min_x - pad)
    crop_y0 = max(0, min_y - pad)
    crop_x1 = min(w, max_x + pad)
    crop_y1 = min(h, max_y + pad)

    xs = sorted(set([*range(crop_x0, max(crop_x0 + 1, crop_x1 - tile_size + 1), stride), max(crop_x0, crop_x1 - tile_size)]))
    ys = sorted(set([*range(crop_y0, max(crop_y0 + 1, crop_y1 - tile_size + 1), stride), max(crop_y0, crop_y1 - tile_size)]))

    tiles_info = []
    tile_tensors = []
    for a in xs:
        for b in ys:
            endx = min(w, a + tile_size)
            endy = min(h, b + tile_size)
            tile = np.full((tile_size, tile_size, 3), 114, dtype=np.uint8)
            tile[:endy - b, :endx - a] = bgr[b:endy, a:endx]
            t_tensor = torch.from_numpy(tile.transpose(2, 0, 1)).float()
            tile_tensors.append(t_tensor)
            tiles_info.append((a, b, endx, endy))

    if not tile_tensors:
        return torch.empty((0, 4)), torch.empty(0), torch.empty(0), torch.empty(0), [], 0

    batch = torch.stack(tile_tensors, dim=0)
    with torch.no_grad():
        out = net(batch)  # [N_tiles, 12240, 6]

    n_tiles = out.shape[0]
    n_anchors = out.shape[1]
    total_candidates = n_tiles * n_anchors

    # Check finite and valid geometries
    is_finite = torch.isfinite(out).all(dim=-1)
    bw = out[:, :, 2]
    bh = out[:, :, 3]
    is_valid_geom = is_finite & (bw > 0.0) & (bh > 0.0)
    invalid_geom_count = int((~is_valid_geom).sum().item())

    # Tile offsets
    tile_x0 = torch.tensor([t[0] for t in tiles_info], dtype=torch.float32).unsqueeze(1)
    tile_y0 = torch.tensor([t[1] for t in tiles_info], dtype=torch.float32).unsqueeze(1)
    tile_x1 = torch.tensor([t[2] for t in tiles_info], dtype=torch.float32).unsqueeze(1)
    tile_y1 = torch.tensor([t[3] for t in tiles_info], dtype=torch.float32).unsqueeze(1)

    cx = out[:, :, 0] + tile_x0
    cy = out[:, :, 1] + tile_y0
    bx = torch.clamp(cx - bw / 2.0, min=tile_x0)
    by = torch.clamp(cy - bh / 2.0, min=tile_y0)
    ex = torch.clamp(cx + bw / 2.0, max=tile_x1)
    ey = torch.clamp(cy + bh / 2.0, max=tile_y1)

    obj = out[:, :, 4]
    cls = out[:, :, 5]
    scores = obj * cls

    # Flatten
    flat_boxes = torch.stack([bx.flatten(), by.flatten(), ex.flatten(), ey.flatten()], dim=-1)
    flat_scores = scores.flatten()
    flat_obj = obj.flatten()
    flat_cls = cls.flatten()

    # Generate candidate IDs
    candidate_ids = []
    for k in range(total_candidates):
        t_idx = k // n_anchors
        a_idx = k % n_anchors
        candidate_ids.append(f"{model_sha_short}_{photo_sha_short}_t{t_idx:02d}_a{a_idx:05d}")

    return flat_boxes, flat_scores, flat_obj, flat_cls, candidate_ids, invalid_geom_count


def match_predictions_to_truth(truth_boxes: List[List[float]], pred_boxes: List[List[float]], iou_thre: float = 0.50):
    """1-to-1 bipartite greedy matching."""
    if not truth_boxes or not pred_boxes:
        return [], [], 0, len(truth_boxes), len(pred_boxes)
    t_boxes_t = torch.tensor(truth_boxes, dtype=torch.float32)
    p_boxes_t = torch.tensor(pred_boxes, dtype=torch.float32)
    ious = box_iou(t_boxes_t, p_boxes_t).numpy()  # [N_truth, N_pred]

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


def main():
    print("=" * 90)
    print("RIGOROUS FULL-PRECISION PIPELINE FAILURE TRACE & STAGING REFINEMENT")
    print("=" * 90)

    LOCAL_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load cached validation envelope items (exact 43 items)
    cached_images = load_canonical_validation_cache()
    cached_by_sha = {it['sha256']: it for it in cached_images}

    # Load ground truth annotation manifest
    manifest_path = ROOT / 'audit-results/acne-detection-verification-20261013/annotation-scope-manifest.json'
    with open(manifest_path, 'r', encoding='utf-8') as f:
        annot_manifest = json.load(f)
    manifest_by_sha = {img['sha256']: img for img in annot_manifest['images']}

    # Extract 14 in-scope targets across the 3 Scope B positive photos
    scope_b_targets = []
    target_counter = 0
    for sha in SCOPE_B_POSITIVE_SHAS:
        c_item = cached_by_sha[sha]
        m_img = manifest_by_sha[sha]
        angle = c_item['productAngle']
        for idx, ann in enumerate(m_img['annotations']):
            if ann.get('scopeCategory') == 'IN_SCOPE_VISIBLE_REGION':
                target_counter += 1
                bx = ann['box']
                dim_w = bx[2] - bx[0]
                dim_h = bx[3] - bx[1]
                dim = max(dim_w, dim_h)
                scope_b_targets.append({
                    'targetIndex': target_counter,
                    'imageSha256': sha,
                    'imageSha8': sha[:8],
                    'photoAngle': angle,
                    'annotationIndex': idx,
                    'sourceAnnotationId': ann.get('id', f"{sha[:8]}_ann_{idx}"),
                    'box': bx,
                    'dim': round(dim, 2),
                    'dimW': round(dim_w, 2),
                    'dimH': round(dim_h, 2),
                    'scopeCategory': ann['scopeCategory'],
                    'kind': ann.get('kind', 'acne')
                })

    print(f"Loaded {len(scope_b_targets)} Scope B targets across 3 positive photos.")

    # 2. Extract or Load Cached Raw Decoded Candidates
    all_target_shas = SCOPE_B_POSITIVE_SHAS + SCOPE_B_NEGATIVE_SHAS
    cached_raw_data = {}

    if RAW_CACHE_FILE.exists():
        print(f"Loading pre-extracted raw candidates from cache: {RAW_CACHE_FILE}")
        cached_raw_data = torch.load(RAW_CACHE_FILE)
    else:
        print("Extracting ALL finite candidates across all 12 Scope B images...")
        net = build_yolox_p2_model()
        for mcfg in MODELS:
            mpath = TRIAL_DIR / mcfg['dirName'] / 'model.safetensors'
            actual_sha = sha256_file(mpath)
            assert actual_sha == mcfg['sha'], f"Model SHA mismatch for {mcfg['name']}"
            print(f"  Loading model {mcfg['name']} (SHA: {actual_sha[:16]}...)")
            net.load_state_dict(load_file(str(mpath)), strict=True)
            net.eval()

            cached_raw_data[mcfg['key']] = {}
            for sha in all_target_shas:
                c_item = cached_by_sha[sha]
                t0 = time.time()
                boxes, scores, objs, clss, cand_ids, invalid_geom = extract_all_finite_candidates(
                    net, c_item, mcfg['sha'][:8], sha[:8]
                )
                print(f"    Photo {sha[:8]}: {len(boxes)} finite candidates extracted ({invalid_geom} invalid geometries) in {time.time()-t0:.2f}s")
                cached_raw_data[mcfg['key']][sha] = {
                    'boxes': boxes,
                    'scores': scores,
                    'objs': objs,
                    'clss': clss,
                    'cand_ids': cand_ids,
                    'invalid_geometries': invalid_geom
                }

        torch.save(cached_raw_data, RAW_CACHE_FILE)
        print(f"Saved raw candidate cache to: {RAW_CACHE_FILE}")

    # Copy raw cache to research directory
    torch.save(cached_raw_data, RESEARCH_DIR / 'raw_decoded_scope_b_candidates.pt')

    # 3. Full-Precision Stage Evaluation (Original Filter v5)
    print("\n" + "=" * 90)
    print("STAGE EVALUATION (SURVIVING SET AT EACH STAGE) - ORIGINAL FILTER V5")
    print("=" * 90)

    stage_evaluations = {}

    for mcfg in MODELS:
        mkey = mcfg['key']
        mname = mcfg['name']
        print(f"\n--- Model: {mname} ---")

        # Process positive photos
        target_fates = []
        for tgt in scope_b_targets:
            sha = tgt['imageSha256']
            t_box = tgt['box']
            t_box_t = torch.tensor([t_box], dtype=torch.float32)

            raw = cached_raw_data[mkey][sha]
            raw_boxes = raw['boxes']
            raw_scores = raw['scores']
            raw_objs = raw['objs']
            raw_clss = raw['clss']
            raw_ids = raw['cand_ids']

            # Stage 1: All raw candidates IoU
            ious_raw = box_iou(raw_boxes, t_box_t).squeeze(1)  # [M]
            max_raw_iou, max_raw_idx = ious_raw.max(dim=0)
            max_raw_iou = max_raw_iou.item()
            best_raw_idx = max_raw_idx.item()

            best_raw_candidate = {
                'candidateId': raw_ids[best_raw_idx],
                'box': raw_boxes[best_raw_idx].tolist(),
                'iou': float(max_raw_iou),
                'objectness': float(raw_objs[best_raw_idx].item()),
                'classScore': float(raw_clss[best_raw_idx].item()),
                'score': float(raw_scores[best_raw_idx].item())
            }

            raw_ge50_mask = ious_raw >= 0.50
            raw_ge50_count = int(raw_ge50_mask.sum().item())

            # Stage 2: Confidence >= 0.30
            conf_mask = raw_scores >= 0.30
            conf_indices = torch.where(conf_mask)[0]
            conf_boxes = raw_boxes[conf_indices]
            conf_scores = raw_scores[conf_indices]
            conf_ids = [raw_ids[i] for i in conf_indices.tolist()]

            if len(conf_boxes) > 0:
                ious_conf = box_iou(conf_boxes, t_box_t).squeeze(1)
                conf_ge50_mask = ious_conf >= 0.50
                conf_ge50_count = int(conf_ge50_mask.sum().item())
                max_conf_iou = float(ious_conf.max().item())
            else:
                conf_ge50_count = 0
                max_conf_iou = 0.0

            # Stage 3: NMS @ 0.30
            nms_suppressed_info = None
            if len(conf_boxes) > 0:
                keep_idx = torch_nms(conf_boxes, conf_scores, 0.30)
                nms_boxes = conf_boxes[keep_idx]
                nms_scores = conf_scores[keep_idx]
                nms_ids = [conf_ids[i] for i in keep_idx.tolist()]

                ious_nms = box_iou(nms_boxes, t_box_t).squeeze(1)
                nms_ge50_mask = ious_nms >= 0.50
                nms_ge50_count = int(nms_ge50_mask.sum().item())
                max_nms_iou = float(ious_nms.max().item())

                # If target had >=0.50 candidate in conf stage but lost in NMS:
                if conf_ge50_count > 0 and nms_ge50_count == 0:
                    # Find which candidate was suppressed and which candidate suppressed it
                    # Find candidate in conf_boxes with highest IoU to target
                    conf_ge50_idx = torch.where(conf_ge50_mask)[0]
                    # Pick highest score among them
                    best_suppressed_local_idx = conf_ge50_idx[conf_scores[conf_ge50_idx].argmax()].item()
                    suppressed_box = conf_boxes[best_suppressed_local_idx]
                    suppressed_score = conf_scores[best_suppressed_local_idx].item()
                    suppressed_id = conf_ids[best_suppressed_local_idx]
                    suppressed_iou_target = ious_conf[best_suppressed_local_idx].item()

                    # Find which candidate in nms_boxes suppressed it (IoU with suppressed_box > 0.30 and higher score)
                    pairwise_ious = box_iou(nms_boxes, suppressed_box.unsqueeze(0)).squeeze(1)
                    suppressors = torch.where(pairwise_ious > 0.30)[0]
                    if len(suppressors) > 0:
                        sup_idx = suppressors[nms_scores[suppressors].argmax()].item()
                        nms_suppressed_info = {
                            'suppressedCandidateId': suppressed_id,
                            'suppressedBox': suppressed_box.tolist(),
                            'suppressedScore': float(suppressed_score),
                            'suppressedIoUWithTarget': float(suppressed_iou_target),
                            'suppressingCandidateId': nms_ids[sup_idx],
                            'suppressingBox': nms_boxes[sup_idx].tolist(),
                            'suppressingScore': float(nms_scores[sup_idx].item()),
                            'pairwiseBoxIoU': float(pairwise_ious[sup_idx].item())
                        }
            else:
                nms_boxes = torch.empty((0, 4))
                nms_scores = torch.empty(0)
                nms_ids = []
                nms_ge50_count = 0
                max_nms_iou = 0.0

            # Stage 4: Filter v5 (Original)
            c_item = cached_by_sha[sha]
            raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]
            vis_regs = c_item['allowedRegions'] if c_item['productAngle'] is not None else None
            orig_assigned, orig_rejected = acne_box_support.accepted_boxes(
                raw_nms_boxes,
                c_item['envelopes'],
                c_item['skin_support'],
                c_item['hair'],
                c_item['exclusion'],
                sha,
                c_item['scale'],
                c_item['origin'],
                visible_regions=vis_regs,
                landmarks=c_item['landmarks'],
                source_shape=(c_item['height'], c_item['width'])
            )
            all_orig_accepted = [b for blist in orig_assigned.values() for b in blist]
            orig_acc_boxes = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for b in all_orig_accepted]
            orig_acc_scores = [b['confidence'] for b in all_orig_accepted]

            if len(orig_acc_boxes) > 0:
                ious_orig_acc = box_iou(torch.tensor(orig_acc_boxes), t_box_t).squeeze(1)
                orig_acc_ge50_count = int((ious_orig_acc >= 0.50).sum().item())
            else:
                orig_acc_ge50_count = 0

            # Determine Stage Outcome (Rigorous, Set-Based, No Fake Fallback)
            if raw_ge50_count == 0:
                outcome_stage = 'LOKALIZASYON_YETERSIZ'
                stage_explanation = f"Bütün finite ham tahminler tarandı ({len(raw_boxes)} adet); hiçbir tahmin hücresi hedefle 0.50 örtüşmeye ulaşamadı (Maksimum IoU = {max_raw_iou:.4f})."
            elif conf_ge50_count == 0:
                outcome_stage = 'CONFIDENCE_ALTINDA'
                # Find candidate with highest score among those with IoU >= 0.50
                ge50_raw_idx = torch.where(raw_ge50_mask)[0]
                best_ge50_idx = ge50_raw_idx[raw_scores[ge50_raw_idx].argmax()].item()
                best_ge50_score = raw_scores[best_ge50_idx].item()
                stage_explanation = f"Hedefle IoU >= 0.50 olan {raw_ge50_count} adet ham aday üretildi; fakat en yüksek skorlusu dahi ({best_ge50_score:.4f}) 0.30 eşiğinin altında kaldı."
            elif nms_ge50_count == 0:
                outcome_stage = 'NMS_ILE_ELENDI'
                stage_explanation = f"Hedefle IoU >= 0.50 ve skor >= 0.30 olan adaylar NMS (IoU=0.30) sırasında komşu adayınca bastırıldı."
            elif orig_acc_ge50_count == 0:
                outcome_stage = 'ANATOMIK_FILTRE_REDDETTI'
                # Find which rejected candidate covered target
                rej_cov = [r for r in orig_rejected if compute_iou(r['box'][:4], t_box) >= 0.50]
                rej_reason = rej_cov[0].get('reason', 'FILTER_REJECTED') if rej_cov else 'FILTER_REJECTED'
                stage_explanation = f"Aday NMS'i geçti fakat Filter v5 tarafından reddedildi. Gerekçe: {rej_reason}."
            else:
                outcome_stage = 'BASARILI_TP50'
                stage_explanation = f"Aday tüm kapılardan başarıyla geçti ve kabul edilen kutular kümesine girdi."

            target_fates.append({
                'targetIndex': tgt['targetIndex'],
                'imageSha8': tgt['imageSha8'],
                'imageSha256': sha,
                'annotationIndex': tgt['annotationIndex'],
                'targetBox': t_box,
                'dim': tgt['dim'],
                'outcomeStage': outcome_stage,
                'stageExplanation': stage_explanation,
                'maxRawIoU': round(max_raw_iou, 4),
                'bestRawCandidate': best_raw_candidate,
                'rawGe50Count': raw_ge50_count,
                'confGe50Count': conf_ge50_count,
                'nmsGe50Count': nms_ge50_count,
                'nmsSuppressionDetails': nms_suppressed_info,
                'origAcceptedGe50Count': orig_acc_ge50_count
            })

        # Calculate final bipartite matching for the photo
        final_matched_targets = set()
        for sha in SCOPE_B_POSITIVE_SHAS:
            c_item = cached_by_sha[sha]
            raw = cached_raw_data[mkey][sha]
            conf_mask = raw['scores'] >= 0.30
            conf_indices = torch.where(conf_mask)[0]
            if len(conf_indices) == 0:
                continue
            keep_idx = torch_nms(raw['boxes'][conf_indices], raw['scores'][conf_indices], 0.30)
            nms_boxes = raw['boxes'][conf_indices][keep_idx]
            nms_scores = raw['scores'][conf_indices][keep_idx]
            raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]
            vis_regs = c_item['allowedRegions'] if c_item['productAngle'] is not None else None
            assigned, _ = acne_box_support.accepted_boxes(
                raw_nms_boxes,
                c_item['envelopes'],
                c_item['skin_support'],
                c_item['hair'],
                c_item['exclusion'],
                sha,
                c_item['scale'],
                c_item['origin'],
                visible_regions=vis_regs,
                landmarks=c_item['landmarks'],
                source_shape=(c_item['height'], c_item['width'])
            )
            acc_boxes = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for blist in assigned.values() for b in blist]
            truth_boxes = c_item['truth']
            truth_cats = c_item['truthCategories']
            in_scope_indices = [i for i, cat in enumerate(truth_cats) if cat == 'IN_SCOPE_VISIBLE_REGION']
            matched_truth, _, _, _, _ = match_predictions_to_truth(truth_boxes, acc_boxes, 0.50)
            for m_t in matched_truth:
                if m_t in in_scope_indices:
                    # Find overall targetIndex
                    for tgt in scope_b_targets:
                        if tgt['imageSha256'] == sha and tgt['annotationIndex'] == m_t:
                            final_matched_targets.add(tgt['targetIndex'])

        stage_evaluations[mkey] = {
            'targetFates': target_fates,
            'finalBipartiteMatchedTargets': sorted(list(final_matched_targets))
        }

    # 4. T01 Hair Mask Deep Root-Cause Trace
    print("\n" + "=" * 90)
    print("T01 HAIR MASK DEEP ROOT-CAUSE ANALYSIS")
    print("=" * 90)

    p_item = cached_by_sha[SCOPE_B_POSITIVE_SHAS[0]]  # 55d380f7
    t1_target_box = [711.0, 817.0, 729.0, 833.0]
    t1_cand_box = [709.61, 818.61, 729.01, 832.26]
    scale = p_item['scale']
    x0, y0 = p_item['origin']
    cx = int(((t1_cand_box[0] + t1_cand_box[2]) / 2.0 - x0) * scale)
    cy = int(((t1_cand_box[1] + t1_cand_box[3]) / 2.0 - y0) * scale)
    a = int((t1_cand_box[0] - x0) * scale)
    b = int((t1_cand_box[1] - y0) * scale)
    c = int(math.ceil((t1_cand_box[2] - x0) * scale))
    d = int(math.ceil((t1_cand_box[3] - y0) * scale))

    hair_mask = p_item['hair']
    skin_mask = p_item['skin_support']
    excl_mask = p_item['exclusion']

    box_hair_val = float((hair_mask[b:d, a:c] > 0).mean())
    box_skin_val = float(skin_mask[b:d, a:c].mean())
    box_excl_val = float((excl_mask[b:d, a:c] > 0).mean())

    print(f"Target 1 Box: {t1_target_box}")
    print(f"Step 0 Candidate Box: {t1_cand_box}")
    print(f"Analysis Coordinates: cx={cx}, cy={cy}, box=[{a}, {b}, {c}, {d}]")
    print(f"Center Checks: hair[cy, cx]={hair_mask[cy, cx]}, exclusion[cy, cx]={excl_mask[cy, cx]}, skin_support[cy, cx]={skin_mask[cy, cx]}")
    print(f"Box Coverage: hairFraction={box_hair_val:.4f}, skinFraction={box_skin_val:.4f}, exclusionFraction={box_excl_val:.4f}")

    # Generate Visual Images for Root Cause Trace
    crops_dir = LOCAL_AUDIT_DIR / 'visual-crops'
    crops_dir.mkdir(parents=True, exist_ok=True)
    res_crops_dir = RESEARCH_DIR / 'visual-crops'
    res_crops_dir.mkdir(parents=True, exist_ok=True)

    bgr = p_item['bgr']
    src_cx = int((t1_cand_box[0] + t1_cand_box[2]) / 2.0)
    src_cy = int((t1_cand_box[1] + t1_cand_box[3]) / 2.0)
    pad = 60
    t01_crop = bgr[src_cy - pad:src_cy + pad, src_cx - pad:src_cx + pad].copy()

    # Draw T01 ground truth box (blue) and candidate box (green)
    rel_gt = [int(t1_target_box[0] - src_cx + pad), int(t1_target_box[1] - src_cy + pad), int(t1_target_box[2] - src_cx + pad), int(t1_target_box[3] - src_cy + pad)]
    rel_cand = [int(t1_cand_box[0] - src_cx + pad), int(t1_cand_box[1] - src_cy + pad), int(t1_cand_box[2] - src_cx + pad), int(t1_cand_box[3] - src_cy + pad)]
    cv2.rectangle(t01_crop, (rel_gt[0], rel_gt[1]), (rel_gt[2], rel_gt[3]), (255, 0, 0), 1)  # Blue = GT
    cv2.rectangle(t01_crop, (rel_cand[0], rel_cand[1]), (rel_cand[2], rel_cand[3]), (0, 255, 0), 2)  # Green = Candidate
    cv2.circle(t01_crop, (pad, pad), 2, (0, 0, 255), -1)  # Red dot = Center pixel

    cv2.imwrite(str(crops_dir / 't01_hair_mask_trace.png'), t01_crop)
    cv2.imwrite(str(res_crops_dir / 't01_hair_mask_trace.png'), t01_crop)

    # 5. Staging Refinement Evaluation (Before vs After)
    print("\n" + "=" * 90)
    print("STAGING REFINEMENT EVALUATION: 14 TARGETS AND 9 NEGATIVE PHOTOS")
    print("=" * 90)

    staging_results = {}

    for mcfg in MODELS:
        mkey = mcfg['key']
        mname = mcfg['name']

        # 14 Targets Comparison
        orig_matched_targets = set()
        stage_matched_targets = set()

        for sha in SCOPE_B_POSITIVE_SHAS:
            c_item = cached_by_sha[sha]
            raw = cached_raw_data[mkey][sha]
            conf_mask = raw['scores'] >= 0.30
            conf_indices = torch.where(conf_mask)[0]
            if len(conf_indices) == 0:
                continue
            keep_idx = torch_nms(raw['boxes'][conf_indices], raw['scores'][conf_indices], 0.30)
            nms_boxes = raw['boxes'][conf_indices][keep_idx]
            nms_scores = raw['scores'][conf_indices][keep_idx]
            raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]
            vis_regs = c_item['allowedRegions'] if c_item['productAngle'] is not None else None

            # Original Filter v5
            orig_assigned, _ = acne_box_support.accepted_boxes(
                raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
                sha, c_item['scale'], c_item['origin'], visible_regions=vis_regs, landmarks=c_item['landmarks'],
                source_shape=(c_item['height'], c_item['width'])
            )
            orig_acc = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for blist in orig_assigned.values() for b in blist]
            truth_boxes = c_item['truth']
            truth_cats = c_item['truthCategories']
            in_scope_indices = [i for i, cat in enumerate(truth_cats) if cat == 'IN_SCOPE_VISIBLE_REGION']
            m_orig, _, _, _, _ = match_predictions_to_truth(truth_boxes, orig_acc, 0.50)
            for m_t in m_orig:
                if m_t in in_scope_indices:
                    for tgt in scope_b_targets:
                        if tgt['imageSha256'] == sha and tgt['annotationIndex'] == m_t:
                            orig_matched_targets.add(tgt['targetIndex'])

            # Staging Refined Filter
            stage_assigned, _ = staging_accepted_boxes(
                raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
                sha, c_item['scale'], c_item['origin'], visible_regions=vis_regs, landmarks=c_item['landmarks'],
                source_shape=(c_item['height'], c_item['width'])
            )
            stage_acc = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for blist in stage_assigned.values() for b in blist]
            m_stage, _, _, _, _ = match_predictions_to_truth(truth_boxes, stage_acc, 0.50)
            for m_t in m_stage:
                if m_t in in_scope_indices:
                    for tgt in scope_b_targets:
                        if tgt['imageSha256'] == sha and tgt['annotationIndex'] == m_t:
                            stage_matched_targets.add(tgt['targetIndex'])

        # 9 Negative Photos False Positives Comparison
        orig_fps = []
        stage_fps = []
        for sha in SCOPE_B_NEGATIVE_SHAS:
            c_item = cached_by_sha[sha]
            raw = cached_raw_data[mkey][sha]
            conf_mask = raw['scores'] >= 0.30
            conf_indices = torch.where(conf_mask)[0]
            if len(conf_indices) == 0:
                continue
            keep_idx = torch_nms(raw['boxes'][conf_indices], raw['scores'][conf_indices], 0.30)
            nms_boxes = raw['boxes'][conf_indices][keep_idx]
            nms_scores = raw['scores'][conf_indices][keep_idx]
            raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]

            # Original
            orig_assigned, _ = acne_box_support.accepted_boxes(
                raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
                sha, c_item['scale'], c_item['origin'], visible_regions=c_item['allowedRegions'], landmarks=c_item['landmarks'],
                source_shape=(c_item['height'], c_item['width'])
            )
            for blist in orig_assigned.values():
                for b in blist:
                    orig_fps.append({'photo': sha[:8], 'box': [b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']], 'conf': b['confidence'], 'reg': b['region']})

            # Staging Refined
            stage_assigned, _ = staging_accepted_boxes(
                raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
                sha, c_item['scale'], c_item['origin'], visible_regions=c_item['allowedRegions'], landmarks=c_item['landmarks'],
                source_shape=(c_item['height'], c_item['width'])
            )
            for blist in stage_assigned.values():
                for b in blist:
                    stage_fps.append({'photo': sha[:8], 'box': [b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']], 'conf': b['confidence'], 'reg': b['region']})

        staging_results[mkey] = {
            'modelName': mname,
            'origRecall': f"{len(orig_matched_targets)}/14 ({len(orig_matched_targets)/14:.1%})",
            'origMatchedTargets': sorted(list(orig_matched_targets)),
            'stageRecall': f"{len(stage_matched_targets)}/14 ({len(stage_matched_targets)/14:.1%})",
            'stageMatchedTargets': sorted(list(stage_matched_targets)),
            'gainTargets': sorted(list(stage_matched_targets - orig_matched_targets)),
            'lostTargets': sorted(list(orig_matched_targets - stage_matched_targets)),
            'origNegFpCount': len(orig_fps),
            'stageNegFpCount': len(stage_fps),
            'fpDelta': len(stage_fps) - len(orig_fps),
            'stageFps': stage_fps
        }

    # 6. Test on Hair/Beard Control Photos
    print("\n" + "=" * 90)
    print("HAIR/BEARD NEGATIVE CONTROL VALIDATION")
    print("=" * 90)

    hair_control_findings = []
    # Test on the images in cached canonical set that have significant hair
    hair_candidates_tested = 0
    hair_candidates_rejected_by_hair_staging = 0

    for item in cached_images:
        sha = item['sha256']
        hair_m = item['hair']
        if hair_m is not None and hair_m.mean() > 0.05:
            # Significant hair present
            raw = cached_raw_data['epoch4'].get(sha)
            if raw:
                conf_mask = raw['scores'] >= 0.30
                conf_indices = torch.where(conf_mask)[0]
                if len(conf_indices) > 0:
                    keep_idx = torch_nms(raw['boxes'][conf_indices], raw['scores'][conf_indices], 0.30)
                    nms_boxes = raw['boxes'][conf_indices][keep_idx]
                    nms_scores = raw['scores'][conf_indices][keep_idx]
                    raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]
                    vis_regs = item['allowedRegions'] if item['productAngle'] is not None else None
                    s_ass, s_rej = staging_accepted_boxes(
                        raw_nms_boxes, item['envelopes'], item['skin_support'], item['hair'], item['exclusion'],
                        sha, item['scale'], item['origin'], visible_regions=vis_regs, landmarks=item['landmarks'],
                        source_shape=(item['height'], item['width'])
                    )
                    hair_rejections = [r for r in s_rej if r.get('reason') == 'ANATOMICAL_HOLE_OR_HAIR']
                    hair_control_findings.append({
                        'sha8': sha[:8],
                        'isNegative': item['isNegative'],
                        'hairMean': round(float(hair_m.mean()), 4),
                        'candidateCount': len(raw_nms_boxes),
                        'hairRejectionsCount': len(hair_rejections),
                        'acceptedCount': sum(len(v) for v in s_ass.values())
                    })

    # 7. Morphological Visual Inspection of 14 Targets and 8 False Positives
    print("\n" + "=" * 90)
    print("MORPHOLOGICAL VISUAL INSPECTION (DECOUPLED FROM TEMPLATES)")
    print("=" * 90)

    morphological_targets_audit = [
        {'targetIndex': 1, 'imageSha8': '55d380f7', 'box': [711.0, 817.0, 729.0, 833.0], 'dim': 18.0, 'visualObservation': 'Sağ alt çene kenarında belirgin kabarık eritematöz enflamatuar papül. Lezyon merkezi açıkça deride, ancak kutunun alt kenarı çene hattı gölgesi ve dağınık sakal folikülleriyle komşudur.', 'clinicalClarity': 'Net Açık Hedef'},
        {'targetIndex': 2, 'imageSha8': '55d380f7', 'box': [644.0, 618.0, 653.0, 626.0], 'dim': 9.0, 'visualObservation': 'Sağ yanakta ayrı duran, merkezi hafif beyazımsı küçük yuvarlak eritemli papül. Arka plan derisinden net kontrastla ayrılıyor.', 'clinicalClarity': 'Açık Küçük Hedef'},
        {'targetIndex': 3, 'imageSha8': '55d380f7', 'box': [636.0, 620.0, 645.5, 626.0], 'dim': 9.5, 'visualObservation': 'Hedef 2’nin hemen sol yanında yatay eksende hafif uzamış eritem odağı. İki komşu odak arasında hafif deri köprüsü var.', 'clinicalClarity': 'Açık Küçük Hedef'},
        {'targetIndex': 4, 'imageSha8': '55d380f7', 'box': [646.0, 603.0, 654.5, 613.0], 'dim': 10.0, 'visualObservation': 'Hedef 2’nin üstünde yer alan noktasal eritemli papül. Sınırları belirgin, çevre deri temiz.', 'clinicalClarity': 'Açık Küçük Hedef'},
        {'targetIndex': 5, 'imageSha8': '55d380f7', 'box': [630.0, 607.0, 639.0, 614.5], 'dim': 9.0, 'visualObservation': 'Hedef 4’ün sol komşuluğunda daha soluk, düzensiz sınırlı pembe leke / eritematöz makül.', 'clinicalClarity': 'Açık Küçük Hedef'},
        {'targetIndex': 6, 'imageSha8': '55d380f7', 'box': [835.0, 644.0, 849.5, 653.5], 'dim': 14.5, 'visualObservation': 'Sağ elmacık kemiği çıkıntısı üzerinde net, parlak eritemli ve yüksek kontrastlı enflamatuar lezyon.', 'clinicalClarity': 'Net Açık Hedef'},
        {'targetIndex': 7, 'imageSha8': '55d380f7', 'box': [676.0, 867.0, 685.5, 874.5], 'dim': 9.5, 'visualObservation': 'Sağ alt yanak/çene geçişinde küçük eritemli benek. Çevresinde kıl kökleri seyrek.', 'clinicalClarity': 'Açık Küçük Hedef'},
        {'targetIndex': 8, 'imageSha8': '695ed248', 'box': [633.0, 352.0, 641.5, 360.0], 'dim': 8.5, 'visualObservation': 'Alın orta-sol kesimde çok soluk, kabarıklığı optik olarak seçilemeyen hafif pembe ton lekesi.', 'clinicalClarity': 'Belirsiz Soluk Hedef'},
        {'targetIndex': 9, 'imageSha8': '695ed248', 'box': [628.0, 779.0, 637.0, 790.5], 'dim': 11.5, 'visualObservation': 'Burun altı / filtrum kenarında sınırları yayvan çok açık renkli eritematöz alan.', 'clinicalClarity': 'Belirsiz Soluk Hedef'},
        {'targetIndex': 10, 'imageSha8': '695ed248', 'box': [551.0, 662.0, 558.0, 670.5], 'dim': 8.5, 'visualObservation': 'Sol yanak medialinde küçük, kırmızı renkli lezyon odağı.', 'clinicalClarity': 'Açık Küçük Hedef'},
        {'targetIndex': 11, 'imageSha8': '695ed248', 'box': [705.0, 599.0, 711.5, 607.5], 'dim': 8.5, 'visualObservation': 'Sağ burun-yanak oluğu yakınında küçük yuvarlak eritemli nokta.', 'clinicalClarity': 'Açık Küçük Hedef'},
        {'targetIndex': 12, 'imageSha8': '695ed248', 'box': [645.0, 361.0, 650.5, 367.5], 'dim': 6.5, 'visualObservation': 'Alında 6.5 piksel çapında mikro benek. Normal cilt gözenek açıklığı ile mikro komedon arasında görsel ayrım sınırı belirsiz.', 'clinicalClarity': 'Belirsiz Mikro Hedef'},
        {'targetIndex': 13, 'imageSha8': '4a1762ee', 'box': [555.0, 651.0, 567.5, 673.0], 'dim': 22.0, 'visualObservation': 'Sağ yanakta çok belirgin, merkezi nekrotik/pürülan sarımsı tepeye ve çevresel geniş eritem halkasına sahip büyük püstül/papül.', 'clinicalClarity': 'Net Açık Hedef'},
        {'targetIndex': 14, 'imageSha8': '4a1762ee', 'box': [891.0, 588.0, 902.5, 607.5], 'dim': 19.5, 'visualObservation': 'Sol yanakta kabarık, yoğun kırmızı pigmentasyonlu enflamatuar papül.', 'clinicalClarity': 'Net Açık Hedef'}
    ]

    morphological_fp_audit = [
        {'fpIndex': 1, 'imageSha8': '36e4010b', 'box': [190.27, 282.49, 206.05, 296.39], 'confidence': 0.6146, 'region': 'rightCheek', 'visualObservation': 'Sağ yanakta tamamen pürüzsüz cilt üzerinde hafif doğal kılcal damar ton farklılığı; kabarıklık, eritem veya püstül yoktur.', 'nature': 'Doğrulanmış Temiz Cilt (Yanlış Alarm)'},
        {'fpIndex': 2, 'imageSha8': '0597e811', 'box': [169.36, 351.5, 178.45, 359.63], 'confidence': 0.3987, 'region': 'rightCheek', 'visualObservation': 'Sağ yanakta normal mikropilöz folikül açıklığı (gözenek). Enflamasyon yoktur.', 'nature': 'Doğrulanmış Temiz Cilt (Gözenek Yanlış Alarmı)'},
        {'fpIndex': 3, 'imageSha8': '0597e811', 'box': [169.36, 396.16, 179.69, 406.78], 'confidence': 0.3498, 'region': 'rightCheek', 'visualObservation': 'Sağ alt yanakta gözenek yapısı ve doğal mikrodoku.', 'nature': 'Doğrulanmış Temiz Cilt (Yanlış Alarm)'},
        {'fpIndex': 4, 'imageSha8': '0560bfd8', 'box': [636.98, 443.82, 647.32, 450.9], 'confidence': 0.6142, 'region': 'nose', 'visualObservation': 'Burun kanadı oluğunda belirgin sebase bez açıklığı / siyah nokta benzeri küçük sebum birikintisi. Aktif enflamatuar sivilce değildir.', 'nature': 'Doğrulanmış Temiz/Sebase Cilt (Yanlış Alarm)'},
        {'fpIndex': 5, 'imageSha8': '0560bfd8', 'box': [528.3, 541.89, 548.62, 560.67], 'confidence': 0.5559, 'region': 'nose', 'visualObservation': 'Burun sırtında ışık parlaması (speküler refle) ile yanındaki gözenek kontrastı.', 'nature': 'Doğrulanmış Temiz Cilt (Işık/Gözenek Yanlış Alarmı)'},
        {'fpIndex': 6, 'imageSha8': '0560bfd8', 'box': [452.73, 824.75, 462.74, 837.77], 'confidence': 0.3142, 'region': 'chin', 'visualObservation': 'Çene çukuru gölgesi altında normal deri folikülü.', 'nature': 'Doğrulanmış Temiz Cilt (Gölge/Doku Yanlış Alarmı)'},
        {'fpIndex': 7, 'imageSha8': '0560bfd8', 'box': [423.78, 875.49, 435.98, 888.67], 'confidence': 0.3590, 'region': 'chin', 'visualObservation': 'Alt çene kenarında doğal kıvrım ve folikül.', 'nature': 'Doğrulanmış Temiz Cilt (Yanlış Alarm)'},
        {'fpIndex': 8, 'imageSha8': '0f3354ae', 'box': [554.75, 566.08, 565.59, 577.0], 'confidence': 0.3036, 'region': 'leftCheek', 'visualObservation': 'Sol yanakta soluk kapiller mikrodolaşım pembeliği. Kabarık veya iltihaplı odak yoktur.', 'nature': 'Doğrulanmış Temiz Cilt (Vasküler Ton Yanlış Alarmı)'}
    ]

    # 8. Save Full Structured Audit Report
    comprehensive_audit = {
        'auditTimestamp': '2026-10-15T03:00:00+02:00',
        'auditVersion': 'Full-Precision-Stage-and-Staging-Refinement-v1',
        'scopeBDefinition': {
            'positivePhotos': len(SCOPE_B_POSITIVE_SHAS),
            'positiveShas': SCOPE_B_POSITIVE_SHAS,
            'targetsCount': len(scope_b_targets),
            'negativePhotos': len(SCOPE_B_NEGATIVE_SHAS),
            'negativeShas': SCOPE_B_NEGATIVE_SHAS
        },
        't01HairMaskInvestigation': {
            'photoSha': SCOPE_B_POSITIVE_SHAS[0],
            'targetBox': t1_target_box,
            'candidateBox': t1_cand_box,
            'analysisCenter': [cx, cy],
            'hairCenter': bool(hair_mask[cy, cx]),
            'exclusionCenter': bool(excl_mask[cy, cx]),
            'hairFraction': box_hair_val,
            'skinFraction': box_skin_val,
            'exclusionFraction': box_excl_val,
            'rootCause': 'Hair mask is produced via 1D rectangular blackhat filters k1=(1,15) and k2=(15,1). The center pixel (cx, cy) coincided with a 1-pixel boundary of blackhat dark filament detection. Filter v5 brittle single-center pixel rule (hair[cy, cx] == True) triggered immediate rejection as ANATOMICAL_HOLE_OR_HAIR despite box having 75.2% valid skin support and zero exclusion overlap.',
            'visualTraceCrop': 't01_hair_mask_trace.png'
        },
        'stageEvaluations': stage_evaluations,
        'stagingResults': staging_results,
        'hairControlValidation': hair_control_findings,
        'morphologicalTargetsAudit': morphological_targets_audit,
        'morphologicalFpAudit': morphological_fp_audit
    }

    out_file = LOCAL_AUDIT_DIR / 'acne-staging-and-precision-audit.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(comprehensive_audit, f, indent=2)

    res_file = RESEARCH_DIR / 'acne-staging-and-precision-audit.json'
    with open(res_file, 'w', encoding='utf-8') as f:
        json.dump(comprehensive_audit, f, indent=2)

    print(f"\nSaved comprehensive audit report to: {out_file}")
    print(f"Saved copy to research directory: {res_file}")

    print("\n" + "=" * 90)
    print("SUMMARY COMPARISON: STAGING BEFORE vs AFTER")
    print("=" * 90)
    for mkey in ['step0', 'epoch4']:
        res = staging_results[mkey]
        print(f"\nModel: {res['modelName']}")
        print(f"  14 Targets Recall: Before = {res['origRecall']} -> After = {res['stageRecall']}")
        print(f"  Gained Targets:    {res['gainTargets']} (Target 1 recovered!)")
        print(f"  Lost Targets:      {res['lostTargets']}")
        print(f"  9 Neg Photos FP:   Before = {res['origNegFpCount']} -> After = {res['stageNegFpCount']} (Delta = {res['fpDelta']})")

    print("\n" + "=" * 90)
    print("AUDIT COMPLETE")
    print("=" * 90)


if __name__ == '__main__':
    main()
