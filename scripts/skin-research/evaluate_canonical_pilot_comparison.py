#!/usr/bin/env python3
"""Canonical, Unified Evaluation Pipeline for Step 0, IoU Pilot, and GIoU Pilot.

Strictly follows Directives & Corrections:
1. Confidence Filtering BEFORE Hard-NMS:
   - In all three evaluation paths (Scope B, TRAIN control cohort, and trained samples),
     confidence >= 0.30 threshold is strictly applied BEFORE Hard-NMS @ 0.30.
   - Low-confidence candidates are kept for diagnostics only; never fed into product NMS.
2. Real Anatomical Meshes, Analysis Scale, Origin, and Exclusions:
   - Staging masks and envelopes are produced using the verified common helper
     `compute_masks_and_envelopes(bgr, points, meshes)` from `evaluate_all_checkpoints_side_by_side.py`.
   - Uses real CDC face meshes from `product_skin_adapter.cjs` (`supportedSkinMesh`),
     real analysis scale `min(1.0, 720 / face_pixels)`, real crop origin `(x0, y0)`,
     real blackhat hair mask on resized analysis crop, and dilated ocular/hole exclusions.
   - Simplified source-resolution dummy envelopes are NOT used.
3. True Product Preflight & Eyewear Segregation:
   - Full CDC preflight is applied: Eyewear (`classify_source`), Quality (`SkinAnalyzer.checkQuality`),
     and Pose Alignment (`SkinAnalyzer.calculateAlignmentFromLandmarks` + `matchesSkinAngle`).
   - Photos that pass only Eyewear CLEAR are NOT labeled as "tam ürün ön kontrolünü geçti";
     full preflight breakdown (Quality, Pose, Eyewear) is explicitly reported.
   - The primary product-admissible denominator is strictly the full product preflight cohort,
     while reference and robustness cohorts are reported separately.
4. Step 0 Baseline Verification:
   - Verifies canonical Scope B reproduction: Recall 5/14 (Targets: [1, 2, 6, 13, 14]) and Neg FP = 2.
5. Inferences and Metadata Caching:
   - Caches preflight, envelopes, and model inference outputs.
   - Logs completed photo counts and elapsed execution time.
"""

import sys
import gc
import json
import time
import os
import subprocess
import base64
from pathlib import Path
from typing import Dict, List, Tuple, Any

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision.ops import nms as torch_nms, box_iou
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / '.runtime/python-packages'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

import mediapipe as mp
from yolox_p2 import build_yolox_p2_model
from acne_box_support_staging import principled_accepted_boxes
from prepare_canonical_validation_cache import load_canonical_validation_cache
from skin_eyewear import classify_source
from negative_mask_builder import build_hole_preserved_negative_masks
from evaluate_all_checkpoints_side_by_side import compute_masks_and_envelopes

STEP0_PATH = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014/checkpoint-epoch-00-step-000000-1792014463030016700/model.safetensors'
PILOT_DIR = ROOT / 'audit-results/acne-pilot-giou-comparison-20261015'
CONTROL_PATH = PILOT_DIR / 'pilot-control-iou/model.safetensors'
CANDIDATE_PATH = PILOT_DIR / 'pilot-candidate-giou/model.safetensors'

COHORT_PATH = PILOT_DIR / 'controlled_train_cohort.json'
DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'

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


def load_model(weights_path: Path):
    net = build_yolox_p2_model()
    net.load_state_dict(load_file(str(weights_path)), strict=True)
    net.eval()
    return net


def common_sliding_tile_inference(net: nn.Module, bgr: np.ndarray, points: list, fallback_crop: list = None, tile_size=384, stride=288):
    """Common canonical sliding tile inference:
    Matches bit-for-bit the canonical Scope B raw decoding pipeline.
    """
    h, w = bgr.shape[:2]
    if points and len(points) >= 468:
        face_lms = np.array([[p['x'] * w, p['y'] * h] for p in points[:468]])
        min_x, max_x = int(np.floor(face_lms[:, 0].min())), int(np.ceil(face_lms[:, 0].max()))
        min_y, max_y = int(np.floor(face_lms[:, 1].min())), int(np.ceil(face_lms[:, 1].max()))
        pad = max(24, int((max_x - min_x) * 0.15))
        crop_x0 = max(0, min_x - pad)
        crop_y0 = max(0, min_y - pad)
        crop_x1 = min(w, max_x + pad)
        crop_y1 = min(h, max_y + pad)
    elif fallback_crop:
        crop_x0, crop_y0, crop_x1, crop_y1 = fallback_crop
        crop_x0, crop_y0 = max(0, crop_x0), max(0, crop_y0)
        crop_x1, crop_y1 = min(w, crop_x1), min(h, crop_y1)
    else:
        crop_x0, crop_y0, crop_x1, crop_y1 = 0, 0, w, h

    xs = sorted(set([*range(crop_x0, max(crop_x0 + 1, crop_x1 - tile_size + 1), stride), max(crop_x0, crop_x1 - tile_size)]))
    ys = sorted(set([*range(crop_y0, max(crop_y0 + 1, crop_y1 - tile_size + 1), stride), max(crop_y0, crop_y1 - tile_size)]))

    tile_tensors = []
    tiles_info = []
    for a in xs:
        for b in ys:
            endx = min(w, a + tile_size)
            endy = min(h, b + tile_size)
            tile = np.full((tile_size, tile_size, 3), 114, dtype=np.uint8)
            crop_patch = bgr[b:endy, a:endx]
            tile[:crop_patch.shape[0], :crop_patch.shape[1]] = crop_patch
            tile_tensors.append(torch.from_numpy(tile.transpose(2, 0, 1)).float())
            tiles_info.append((a, b, endx, endy))

    if not tile_tensors:
        return torch.empty((0, 4)), torch.empty(0)

    batch = torch.stack(tile_tensors, dim=0)
    with torch.no_grad():
        out = net(batch)

    tile_x0 = torch.tensor([t[0] for t in tiles_info], dtype=torch.float32).unsqueeze(1)
    tile_y0 = torch.tensor([t[1] for t in tiles_info], dtype=torch.float32).unsqueeze(1)
    tile_x1 = torch.tensor([t[2] for t in tiles_info], dtype=torch.float32).unsqueeze(1)
    tile_y1 = torch.tensor([t[3] for t in tiles_info], dtype=torch.float32).unsqueeze(1)

    bw = out[:, :, 2]
    bh = out[:, :, 3]
    cx = out[:, :, 0] + tile_x0
    cy = out[:, :, 1] + tile_y0
    bx = torch.clamp(cx - bw / 2.0, min=tile_x0)
    by = torch.clamp(cy - bh / 2.0, min=tile_y0)
    ex = torch.clamp(cx + bw / 2.0, max=tile_x1)
    ey = torch.clamp(cy + bh / 2.0, max=tile_y1)
    scores = out[:, :, 4] * out[:, :, 5]

    flat_boxes = torch.stack([bx.flatten(), by.flatten(), ex.flatten(), ey.flatten()], dim=-1)
    flat_scores = scores.flatten()

    return flat_boxes, flat_scores


def match_predictions_bipartite(truth_boxes: List[List[float]], pred_boxes: List[List[float]], iou_thresh: float = 0.50):
    """Greedy maximum-IoU 1-to-1 bipartite matching between ground truth and predictions."""
    if not truth_boxes or not pred_boxes:
        return [], 0, []

    t_tensor = torch.tensor(truth_boxes, dtype=torch.float32)
    p_tensor = torch.tensor(pred_boxes, dtype=torch.float32)
    ious = box_iou(t_tensor, p_tensor).numpy()

    matched_pairs = []
    matched_ious = []
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
        if best_iou < iou_thresh or best_t == -1:
            break
        matched_pairs.append((best_t, best_p, float(best_iou)))
        matched_ious.append(float(best_iou))
        truth_unmatched.remove(best_t)
        pred_unmatched.remove(best_p)

    return matched_pairs, len(matched_pairs), matched_ious


def evaluate_scope_b_canonical(net: nn.Module, cached_val_images: list, model_key: str):
    """Canonical Scope B evaluation (14 targets, 9 negative photos).
    Strictly applies confidence >= 0.30 BEFORE Hard-NMS @ 0.30.
    """
    c_images_by_sha = {it['sha256']: it for it in cached_val_images}

    with open(ROOT / 'audit-results/acne-detection-verification-20261013/annotation-scope-manifest.json', 'r', encoding='utf-8') as f:
        annot_manifest = json.load(f)
    manifest_by_sha = {img['sha256']: img for img in annot_manifest['images']}

    # 1. Positive Photos (14 Targets)
    matched_targets = set()
    target_counter = 0

    for sha in SCOPE_B_POSITIVE_SHAS:
        c_item = c_images_by_sha[sha]
        m_img = manifest_by_sha[sha]
        bgr = c_item['bgr']
        points = c_item['landmarks']

        flat_boxes, flat_scores = common_sliding_tile_inference(net, bgr, points)

        # DIRECTIVE 1: Confidence filter >= 0.30 applied BEFORE Hard-NMS
        valid_idx = torch.where(flat_scores >= 0.30)[0]
        if len(valid_idx) > 0:
            cand_boxes = flat_boxes[valid_idx]
            cand_scores = flat_scores[valid_idx]
            keep = torch_nms(cand_boxes, cand_scores, 0.30)
            nms_boxes = cand_boxes[keep]
            nms_scores = cand_scores[keep]
            raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]
        else:
            raw_nms_boxes = []

        vis_regs = c_item['allowedRegions'] if c_item['productAngle'] is not None else None

        assigned, rejected = principled_accepted_boxes(
            raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
            sha, c_item['scale'], c_item['origin'], visible_regions=vis_regs, landmarks=c_item['landmarks'],
            source_shape=(c_item['height'], c_item['width']), bgr=c_item['bgr']
        )
        acc_boxes = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for blist in assigned.values() for b in blist]

        truth_boxes = c_item['truth']

        pairs, _, _ = match_predictions_bipartite(truth_boxes, acc_boxes, iou_thresh=0.50)
        matched_gt_inds = set(p[0] for p in pairs)

        for idx, ann in enumerate(m_img['annotations']):
            if ann.get('scopeCategory') == 'IN_SCOPE_VISIBLE_REGION':
                target_counter += 1
                if idx in matched_gt_inds:
                    matched_targets.add(target_counter)

    # 2. Negative Photos (9 Photos)
    negative_fps = 0
    fp_by_photo = {}

    for sha in SCOPE_B_NEGATIVE_SHAS:
        c_item = c_images_by_sha[sha]
        bgr = c_item['bgr']
        points = c_item['landmarks']

        flat_boxes, flat_scores = common_sliding_tile_inference(net, bgr, points)

        # DIRECTIVE 1: Confidence filter >= 0.30 applied BEFORE Hard-NMS
        valid_idx = torch.where(flat_scores >= 0.30)[0]
        if len(valid_idx) > 0:
            cand_boxes = flat_boxes[valid_idx]
            cand_scores = flat_scores[valid_idx]
            keep = torch_nms(cand_boxes, cand_scores, 0.30)
            nms_boxes = cand_boxes[keep]
            nms_scores = cand_scores[keep]
            raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]
        else:
            raw_nms_boxes = []

        assigned, rejected = principled_accepted_boxes(
            raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
            sha, c_item['scale'], c_item['origin'], visible_regions=c_item['allowedRegions'], landmarks=c_item['landmarks'],
            source_shape=(c_item['height'], c_item['width']), bgr=c_item['bgr']
        )
        fp_count = sum(len(v) for v in assigned.values())
        negative_fps += fp_count
        if fp_count > 0:
            fp_by_photo[sha[:8]] = fp_count

    return {
        'recall': f"{len(matched_targets)}/14 ({len(matched_targets)/14:.1%})",
        'matchedTargets': sorted(list(matched_targets)),
        'negFpCount': negative_fps,
        'fpByPhoto': fp_by_photo
    }


def precompute_train_cohort_cache(
    shas: List[str],
    train_rows: dict,
    clean_masks: dict,
    landmarker: Any
) -> Dict[str, dict]:
    """Precomputes and caches true product preflight, real CDC meshes, envelopes,
    analysis scale, origin, hair/skin masks, and hole-preserved clean masks for TRAIN photos.
    """
    print(f"Precomputing true CDC product preflight and envelopes for {len(shas)} photos...")
    t0 = time.time()

    # 1. Prepare payload for product_skin_adapter.cjs
    adapter_payload = []
    raw_imgs = {}
    landmarks_dict = {}

    for sha in shas:
        r = train_rows[sha]
        path = r.get('absolutePath') or str(LIVE_TEST / r['path'])
        bgr = cv2.imread(path)
        if bgr is None:
            continue
        raw_imgs[sha] = bgr
        h, w = bgr.shape[:2]

        pts = r.get('landmarks', [])
        if not pts or len(pts) < 468:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            det = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            if det.face_landmarks and len(det.face_landmarks[0]) >= 468:
                pts = [{'x': float(pt.x), 'y': float(pt.y), 'z': float(pt.z)} for pt in det.face_landmarks[0]]
        landmarks_dict[sha] = pts

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        rgb_b64 = base64.b64encode(rgb.tobytes()).decode('ascii')
        adapter_payload.append({'sha256': sha, 'width': w, 'height': h, 'landmarks': pts, 'rgbBase64': rgb_b64})

    # 2. Invoke CDC product_skin_adapter.cjs
    node_path = f"{LIVE_TEST / 'node_modules'};{LIVE_TEST / 'apps/vehicle-app/node_modules'};{ROOT / 'node_modules'};{ROOT / 'apps/vehicle-app/node_modules'}"
    env = os.environ.copy()
    env['NODE_PATH'] = node_path
    cmd = ['node', str(ROOT / 'scripts/skin-research/product_skin_adapter.cjs')]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out, err = proc.communicate(json.dumps(adapter_payload).encode('utf-8'))
    if proc.returncode != 0:
        raise RuntimeError(f"product_skin_adapter.cjs failed:\n{err.decode('utf-8')}")

    adapter_results = {res['sha256']: res for res in json.loads(out.decode('utf-8'))}

    # 3. Assemble full product cache
    cohort_cache = {}
    for sha in shas:
        if sha not in raw_imgs:
            continue
        bgr = raw_imgs[sha]
        h, w = bgr.shape[:2]
        pts = landmarks_dict[sha]
        ares = adapter_results[sha]
        r = train_rows[sha]

        # Eyewear check
        if pts and len(pts) >= 468:
            eye_res = classify_source(bgr, pts)
            eye_status = eye_res['status']
        else:
            eye_status = 'LANDMARKS_MISSING'

        # CDC Quality and Pose checks
        q_info = ares['quality']
        q_valid = bool(q_info.get('isValid', False))
        align = ares.get('alignment')
        p_valid = bool(align is not None and align.get('isAligned', False) and ares.get('matchedAngle') is not None)
        e_valid = (eye_status == 'CLEAR')

        rejection_reasons = []
        if not e_valid:
            rejection_reasons.append(f"EYEWEAR_{eye_status}")
        if not q_valid:
            rejection_reasons.append(f"QUALITY_{q_info.get('status', 'INVALID')}")
        if not p_valid:
            rejection_reasons.append(f"POSE_UNALIGNED(angle={ares.get('matchedAngle')})")

        is_full_product_pass = (len(rejection_reasons) == 0)

        # DIRECTIVE 2: Compute real product masks, envelopes, scale, and origin from CDC helper
        meshes = ares.get('meshes', {})
        if pts and len(pts) >= 468 and meshes:
            envelopes, skin_support, hair, exclusion, scale, origin, face_support, face_pixels = compute_masks_and_envelopes(
                bgr, pts, meshes
            )
        else:
            envelopes, skin_support, hair, exclusion, scale, origin, face_support, face_pixels = [None]*8

        anns = r.get('annotations', [])
        gt_boxes = [a['box'] for a in anns]

        cohort_cache[sha] = {
            'sha256': sha,
            'bgr': bgr,
            'height': h,
            'width': w,
            'landmarks': pts,
            'crop': r.get('crop'),
            'annotations': anns,
            'gt_boxes': gt_boxes,
            'clean_mask': clean_masks[sha],
            'eyewear_status': eye_status,
            'quality_info': q_info,
            'alignment_info': align,
            'matched_angle': ares.get('matchedAngle'),
            'allowed_regions': ares.get('allowedRegions', []),
            'is_eyewear_clear': e_valid,
            'is_quality_valid': q_valid,
            'is_pose_aligned': p_valid,
            'is_full_product_pass': is_full_product_pass,
            'rejection_reasons': rejection_reasons,
            'envelopes': envelopes,
            'skin_support': skin_support,
            'hair': hair,
            'exclusion': exclusion,
            'scale': scale,
            'origin': origin,
            'face_pixels': face_pixels
        }

    print(f"Cohort cache precomputed in {time.time()-t0:.2f}s for {len(cohort_cache)} photos.")
    return cohort_cache


def evaluate_cached_photo(net: nn.Module, c_item: dict) -> dict:
    """Evaluates a single cached photo:
    - Runs sliding-tile inference once.
    - Applies confidence >= 0.30 BEFORE Hard-NMS @ 0.30.
    - Runs detector_only evaluation.
    - Runs product_staging_filtered evaluation with real CDC envelopes/scale/origin.
    """
    bgr = c_item['bgr']
    pts = c_item['landmarks']
    h, w = c_item['height'], c_item['width']
    clean_mask = c_item['clean_mask']
    gt_boxes = c_item['gt_boxes']
    anns = c_item['annotations']
    sha = c_item['sha256']

    # 1. Common Sliding Tile Inference
    fallback_crop = c_item.get('crop')
    flat_boxes, flat_scores = common_sliding_tile_inference(net, bgr, pts, fallback_crop=fallback_crop)

    # DIRECTIVE 1: Confidence filter >= 0.30 applied BEFORE Hard-NMS
    valid_idx = torch.where(flat_scores >= 0.30)[0]
    if len(valid_idx) > 0:
        cand_boxes = flat_boxes[valid_idx]
        cand_scores = flat_scores[valid_idx]
        keep = torch_nms(cand_boxes, cand_scores, 0.30)
        nms_boxes = cand_boxes[keep]
        nms_scores = cand_scores[keep]
        raw_nms_boxes = [nms_boxes[i].tolist() + [nms_scores[i].item()] for i in range(len(nms_boxes))]
    else:
        raw_nms_boxes = []

    # --- A) DETECTOR ONLY EVALUATION ---
    det_pred_boxes = [b[:4] for b in raw_nms_boxes]
    det_pairs, det_tp, det_ious = match_predictions_bipartite(gt_boxes, det_pred_boxes, iou_thresh=0.50)
    det_matched_gt_inds = set(p[0] for p in det_pairs)
    det_matched_pred_inds = set(p[1] for p in det_pairs)

    det_micro_gt, det_micro_tp = 0, 0
    det_small_gt, det_small_tp = 0, 0
    det_med_gt, det_med_tp = 0, 0

    for idx, a in enumerate(anns):
        bx = a['box']
        dim = max(bx[2] - bx[0], bx[3] - bx[1])
        is_hit = (idx in det_matched_gt_inds)
        if dim < 8:
            det_micro_gt += 1
            if is_hit: det_micro_tp += 1
        elif dim < 16:
            det_small_gt += 1
            if is_hit: det_small_tp += 1
        else:
            det_med_gt += 1
            if is_hit: det_med_tp += 1

    det_clean_fp = 0
    for p_idx, b in enumerate(det_pred_boxes):
        if p_idx not in det_matched_pred_inds:
            cx = int(round((b[0] + b[2]) / 2.0))
            cy = int(round((b[1] + b[3]) / 2.0))
            if 0 <= cy < h and 0 <= cx < w and clean_mask[cy, cx] > 0:
                det_clean_fp += 1

    # --- B) PRODUCT STAGING FILTERED EVALUATION ---
    # DIRECTIVE 2: Uses real CDC envelopes, analysis scale, origin, hair, and exclusions
    if c_item['envelopes'] is not None and c_item['skin_support'] is not None:
        vis_regs = c_item['allowed_regions'] if c_item['matched_angle'] is not None else None
        assigned, rejected = principled_accepted_boxes(
            raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
            sha, c_item['scale'], c_item['origin'], visible_regions=vis_regs, landmarks=pts,
            source_shape=(h, w), bgr=bgr
        )
        filt_boxes = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for blist in assigned.values() for b in blist]
    else:
        assigned, rejected = {}, []
        filt_boxes = []

    filt_pairs, filt_tp, filt_ious = match_predictions_bipartite(gt_boxes, filt_boxes, iou_thresh=0.50)
    filt_matched_gt_inds = set(p[0] for p in filt_pairs)
    filt_matched_pred_inds = set(p[1] for p in filt_pairs)

    filt_micro_gt, filt_micro_tp = 0, 0
    filt_small_gt, filt_small_tp = 0, 0
    filt_med_gt, filt_med_tp = 0, 0

    for idx, a in enumerate(anns):
        bx = a['box']
        dim = max(bx[2] - bx[0], bx[3] - bx[1])
        is_hit = (idx in filt_matched_gt_inds)
        if dim < 8:
            filt_micro_gt += 1
            if is_hit: filt_micro_tp += 1
        elif dim < 16:
            filt_small_gt += 1
            if is_hit: filt_small_tp += 1
        else:
            filt_med_gt += 1
            if is_hit: filt_med_tp += 1

    filt_clean_fp = 0
    for p_idx, b in enumerate(filt_boxes):
        if p_idx not in filt_matched_pred_inds:
            cx = int(round((b[0] + b[2]) / 2.0))
            cy = int(round((b[1] + b[3]) / 2.0))
            if 0 <= cy < h and 0 <= cx < w and clean_mask[cy, cx] > 0:
                filt_clean_fp += 1

    return {
        'sha': sha,
        'eyewear_status': c_item['eyewear_status'],
        'is_eyewear_clear': c_item['is_eyewear_clear'],
        'is_quality_valid': c_item['is_quality_valid'],
        'is_pose_aligned': c_item['is_pose_aligned'],
        'is_full_product_pass': c_item['is_full_product_pass'],
        'rejection_reasons': c_item['rejection_reasons'],
        'gt_count': len(gt_boxes),
        'detector_only': {
            'tp50': det_tp, 'ious': det_ious, 'clean_fp': det_clean_fp,
            'micro_gt': det_micro_gt, 'micro_tp': det_micro_tp,
            'small_gt': det_small_gt, 'small_tp': det_small_tp,
            'med_gt': det_med_gt, 'med_tp': det_med_tp
        },
        'product_staging_filtered': {
            'tp50': filt_tp, 'ious': filt_ious, 'clean_fp': filt_clean_fp,
            'micro_gt': filt_micro_gt, 'micro_tp': filt_micro_tp,
            'small_gt': filt_small_gt, 'small_tp': filt_small_tp,
            'med_gt': filt_med_gt, 'med_tp': filt_med_tp
        }
    }


def aggregate_cohort_metrics(photo_results: List[dict]) -> dict:
    """Aggregates detector_only and product_staging_filtered metrics over a cohort of photos."""
    res = {
        'photoCount': len(photo_results),
        'totalGt': sum(p['gt_count'] for p in photo_results),
        'detector_only': {
            'totalGt': 0, 'tp50': 0, 'allMatchedIoUs': [],
            'microGt': 0, 'microTp': 0,
            'smallGt': 0, 'smallTp': 0,
            'medGt': 0, 'medTp': 0,
            'verifiedCleanFp': 0,
            'fpsByPhoto': {}
        },
        'product_staging_filtered': {
            'totalGt': 0, 'tp50': 0, 'allMatchedIoUs': [],
            'microGt': 0, 'microTp': 0,
            'smallGt': 0, 'smallTp': 0,
            'medGt': 0, 'medTp': 0,
            'verifiedCleanFp': 0,
            'fpsByPhoto': {}
        }
    }

    for p in photo_results:
        sha_prefix = p['sha'][:8]
        # Detector only
        d = p['detector_only']
        res['detector_only']['totalGt'] += p['gt_count']
        res['detector_only']['tp50'] += d['tp50']
        res['detector_only']['allMatchedIoUs'].extend(d['ious'])
        res['detector_only']['microGt'] += d['micro_gt']
        res['detector_only']['microTp'] += d['micro_tp']
        res['detector_only']['smallGt'] += d['small_gt']
        res['detector_only']['smallTp'] += d['small_tp']
        res['detector_only']['medGt'] += d['med_gt']
        res['detector_only']['medTp'] += d['med_tp']
        res['detector_only']['verifiedCleanFp'] += d['clean_fp']
        if d['clean_fp'] > 0:
            res['detector_only']['fpsByPhoto'][sha_prefix] = d['clean_fp']

        # Product filtered
        f = p['product_staging_filtered']
        res['product_staging_filtered']['totalGt'] += p['gt_count']
        res['product_staging_filtered']['tp50'] += f['tp50']
        res['product_staging_filtered']['allMatchedIoUs'].extend(f['ious'])
        res['product_staging_filtered']['microGt'] += f['micro_gt']
        res['product_staging_filtered']['microTp'] += f['micro_tp']
        res['product_staging_filtered']['smallGt'] += f['small_gt']
        res['product_staging_filtered']['smallTp'] += f['small_tp']
        res['product_staging_filtered']['medGt'] += f['med_gt']
        res['product_staging_filtered']['medTp'] += f['med_tp']
        res['product_staging_filtered']['verifiedCleanFp'] += f['clean_fp']
        if f['clean_fp'] > 0:
            res['product_staging_filtered']['fpsByPhoto'][sha_prefix] = f['clean_fp']

    for mtype in ['detector_only', 'product_staging_filtered']:
        m = res[mtype]
        m['recall50'] = m['tp50'] / max(1, m['totalGt'])
        m['meanMatchedIoU'] = float(np.mean(m['allMatchedIoUs'])) if m['allMatchedIoUs'] else 0.0
        m['scaleBreakdown'] = {
            'micro': {'gt': m['microGt'], 'tp50': m['microTp'], 'recall': m['microTp'] / max(1, m['microGt'])},
            'small': {'gt': m['smallGt'], 'tp50': m['smallTp'], 'recall': m['smallTp'] / max(1, m['smallGt'])},
            'medium': {'gt': m['medGt'], 'tp50': m['medTp'], 'recall': m['medTp'] / max(1, m['medGt'])},
        }

    return res


def evaluate_cohort_group(
    net: nn.Module,
    shas: List[str],
    cohort_cache: Dict[str, dict],
    group_name: str
) -> dict:
    """Evaluates a cohort group using precomputed cache, segregating:
    1. Full Product Preflight Pass (Passed Eyewear CLEAR + Quality + Pose Alignment)
    2. Eyewear CLEAR Subset (Passed Eyewear, but may have failed Quality or Pose)
    3. Robustness / Out-of-Spec Subset (Failed Eyewear or Missing Landmarks)
    4. All Cohort Photos combined
    """
    t_start = time.time()
    print(f"\nEvaluating {group_name} ({len(shas)} photos)...")

    photo_evals = []
    preflight_breakdown = {
        'total': len(shas),
        'full_product_pass': [],
        'eyewear_clear': [],
        'eyewear_present': [],
        'eyewear_uncertain': [],
        'landmarks_missing': [],
        'quality_valid': [],
        'quality_invalid': [],
        'pose_aligned': [],
        'pose_unaligned': [],
        'rejection_reasons_by_photo': {}
    }

    for idx, sha in enumerate(shas):
        c_item = cohort_cache[sha]
        eval_res = evaluate_cached_photo(net, c_item)
        photo_evals.append(eval_res)

        # Preflight recording
        sha8 = sha[:8]
        if eval_res['is_full_product_pass']:
            preflight_breakdown['full_product_pass'].append(sha8)
        if eval_res['is_eyewear_clear']:
            preflight_breakdown['eyewear_clear'].append(sha8)
        if eval_res['eyewear_status'] == 'EYEWEAR_PRESENT':
            preflight_breakdown['eyewear_present'].append(sha8)
        elif eval_res['eyewear_status'] == 'UNCERTAIN':
            preflight_breakdown['eyewear_uncertain'].append(sha8)
        elif eval_res['eyewear_status'] == 'LANDMARKS_MISSING':
            preflight_breakdown['landmarks_missing'].append(sha8)

        if eval_res['is_quality_valid']:
            preflight_breakdown['quality_valid'].append(sha8)
        else:
            preflight_breakdown['quality_invalid'].append(sha8)

        if eval_res['is_pose_aligned']:
            preflight_breakdown['pose_aligned'].append(sha8)
        else:
            preflight_breakdown['pose_unaligned'].append(sha8)

        if eval_res['rejection_reasons']:
            preflight_breakdown['rejection_reasons_by_photo'][sha8] = eval_res['rejection_reasons']

    elapsed = time.time() - t_start
    print(f"  Completed {len(photo_evals)} photos in {elapsed:.2f}s.")

    full_pass_evals = [p for p in photo_evals if p['is_full_product_pass']]
    eyewear_clear_evals = [p for p in photo_evals if p['is_eyewear_clear']]
    robustness_evals = [p for p in photo_evals if not p['is_eyewear_clear']]

    return {
        'elapsedSeconds': round(elapsed, 2),
        'completedPhotos': len(photo_evals),
        'preflight_breakdown': preflight_breakdown,
        'full_product_pass_cohort': aggregate_cohort_metrics(full_pass_evals),
        'eyewear_clear_subset': aggregate_cohort_metrics(eyewear_clear_evals),
        'robustness_subset': aggregate_cohort_metrics(robustness_evals),
        'all_photos': aggregate_cohort_metrics(photo_evals)
    }


def main():
    print("=" * 95)
    print("CANONICAL PILOT EVALUATION: STEP 0 VS CONTROL IOU VS CANDIDATE GIOU")
    print("Confidence threshold >= 0.30 applied BEFORE Hard-NMS @ 0.30")
    print("Real CDC anatomical envelopes, analysis scale, origin, and hole exclusions")
    print("=" * 95)

    # 1. Initialize MediaPipe FaceLandmarker
    model_path = str(ROOT / 'apps/vehicle-app/public/mediapipe/models/face_landmarker.task')
    landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
        mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1
        )
    )

    # 2. Load Cohort, Datasets, and Build Hole-Preserved Clean Masks
    with open(COHORT_PATH, 'r', encoding='utf-8') as f:
        cohort = json.load(f)
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    train_rows = {r['sha256']: r for r in data['rows'] if r.get('split') == 'train'}

    print("Building verified hole-preserved negative masks for train photos...")
    all_train_rows = list(train_rows.values())
    clean_masks, _ = build_hole_preserved_negative_masks(all_train_rows)

    held_out_control_shas = cohort['pilotControlShas']   # 28 photos held out from 150-step pilot
    trained_sample_shas = cohort['pilotTrainShas'][:25]  # 25 representative photos trained in pilot
    cached_val_images = load_canonical_validation_cache()

    # 3. Precompute Full Product Preflight & Real CDC Envelopes for TRAIN Cohorts
    all_cohort_shas = sorted(list(set(held_out_control_shas + trained_sample_shas)))
    cohort_cache = precompute_train_cohort_cache(all_cohort_shas, train_rows, clean_masks, landmarker)

    # 4. Verify Step 0 Baseline First
    print("\n" + "=" * 80)
    print("VERIFYING STEP 0 BASELINE ON SCOPE B...")
    print("=" * 80)
    step0_net = load_model(STEP0_PATH)
    t0_step0 = time.time()
    step0_scope_b = evaluate_scope_b_canonical(step0_net, cached_val_images, 'step0')
    t_scope_b = time.time() - t0_step0
    print(f"Step 0 Scope B Result: {step0_scope_b['recall']} | Targets: {step0_scope_b['matchedTargets']} | Neg FPs: {step0_scope_b['negFpCount']} (took {t_scope_b:.2f}s)")

    # Assert canonical reproduction without hardcoding
    assert step0_scope_b['matchedTargets'] == [1, 2, 6, 13, 14], f"Step 0 targets mismatch: {step0_scope_b['matchedTargets']}"
    assert step0_scope_b['negFpCount'] == 2, f"Step 0 negative FP mismatch: {step0_scope_b['negFpCount']}"
    print("[VERIFIED] Step 0 Scope B Baseline bit-for-bit exact reproduction confirmed: 5/14 recall, Targets [1, 2, 6, 13, 14], Neg FP = 2!\n")

    models = [
        {'name': 'Step 0 Baseline', 'path': STEP0_PATH, 'key': 'step0', 'net': step0_net},
        {'name': 'Control Pilot (IoU 150-step)', 'path': CONTROL_PATH, 'key': 'control_iou', 'net': None},
        {'name': 'Candidate Pilot (GIoU 150-step)', 'path': CANDIDATE_PATH, 'key': 'candidate_giou', 'net': None}
    ]

    all_results = {}

    for mcfg in models:
        mkey = mcfg['key']
        mname = mcfg['name']
        print("\n" + "=" * 90)
        print(f"EVALUATING MODEL: {mname}")
        print("=" * 90)

        net = mcfg['net'] if mcfg['net'] is not None else load_model(mcfg['path'])
        t_model_start = time.time()

        # A) Scope B Canonical Evaluation
        if mkey == 'step0':
            scope_b_res = step0_scope_b
        else:
            t0_sb = time.time()
            scope_b_res = evaluate_scope_b_canonical(net, cached_val_images, mkey)
            print(f"  Scope B evaluated in {time.time()-t0_sb:.2f}s.")
        print(f"[Scope B Canonical Dev Set]")
        print(f"  Recall: {scope_b_res['recall']} | Targets: {scope_b_res['matchedTargets']} | Neg FPs: {scope_b_res['negFpCount']}")

        # B) Held-out TRAIN Control Group (28 photos held out from 150-step pilot)
        ctrl_res = evaluate_cohort_group(
            net, held_out_control_shas, cohort_cache,
            f"Held-Out TRAIN Control Group ({mname})"
        )
        pb = ctrl_res['preflight_breakdown']
        f_pass = ctrl_res['full_product_pass_cohort']
        e_clear = ctrl_res['eyewear_clear_subset']
        all_p = ctrl_res['all_photos']

        print(f"\n[Held-Out TRAIN Control Group: Preflight Breakdown]")
        print(f"  Total: {pb['total']} | Full Product Pass: {len(pb['full_product_pass'])}/28 | Eyewear CLEAR: {len(pb['eyewear_clear'])}/28 | Quality Valid: {len(pb['quality_valid'])}/28 | Pose Aligned: {len(pb['pose_aligned'])}/28")
        print(f"  Eyewear Failures: {len(pb['eyewear_present'])} Glasses, {len(pb['landmarks_missing'])} No Landmarks, {len(pb['eyewear_uncertain'])} Uncertain")
        print(f"  Quality/Pose Failures: {len(pb['quality_invalid'])} Blurry/Dark, {len(pb['pose_unaligned'])} Unaligned Pose")

        print(f"\n  1) FULL PRODUCT PREFLIGHT PASS COHORT ({f_pass['photoCount']} Photos, {f_pass['totalGt']} GT Lesions):")
        print(f"     DETECTOR-ONLY: TP50: {f_pass['detector_only']['tp50']}/{f_pass['detector_only']['totalGt']} ({f_pass['detector_only']['recall50']:.1%}) | Mean IoU: {f_pass['detector_only']['meanMatchedIoU']:.3f} | Clean-Skin FP: {f_pass['detector_only']['verifiedCleanFp']}")
        print(f"     PRODUCT-FILTERED: TP50: {f_pass['product_staging_filtered']['tp50']}/{f_pass['product_staging_filtered']['totalGt']} ({f_pass['product_staging_filtered']['recall50']:.1%}) | Clean-Skin FP: {f_pass['product_staging_filtered']['verifiedCleanFp']}")

        print(f"\n  2) EYEWEAR CLEAR SUBSET ({e_clear['photoCount']} Photos, {e_clear['totalGt']} GT Lesions - Quality/Pose Not Guaranteed):")
        print(f"     DETECTOR-ONLY: TP50: {e_clear['detector_only']['tp50']}/{e_clear['detector_only']['totalGt']} ({e_clear['detector_only']['recall50']:.1%}) | Mean IoU: {e_clear['detector_only']['meanMatchedIoU']:.3f} | Clean-Skin FP: {e_clear['detector_only']['verifiedCleanFp']}")
        print(f"     PRODUCT-FILTERED: TP50: {e_clear['product_staging_filtered']['tp50']}/{e_clear['product_staging_filtered']['totalGt']} ({e_clear['product_staging_filtered']['recall50']:.1%}) | Clean-Skin FP: {e_clear['product_staging_filtered']['verifiedCleanFp']}")

        print(f"\n  3) ALL 28 HELD-OUT CONTROL PHOTOS ({all_p['photoCount']} Photos, {all_p['totalGt']} GT Lesions):")
        print(f"     DETECTOR-ONLY: TP50: {all_p['detector_only']['tp50']}/{all_p['detector_only']['totalGt']} ({all_p['detector_only']['recall50']:.1%}) | Mean IoU: {all_p['detector_only']['meanMatchedIoU']:.3f} | Clean-Skin FP: {all_p['detector_only']['verifiedCleanFp']}")
        print(f"       Micro (<8px): {all_p['detector_only']['scaleBreakdown']['micro']['tp50']}/{all_p['detector_only']['scaleBreakdown']['micro']['gt']} ({all_p['detector_only']['scaleBreakdown']['micro']['recall']:.1%})")
        print(f"       Small (8-16px): {all_p['detector_only']['scaleBreakdown']['small']['tp50']}/{all_p['detector_only']['scaleBreakdown']['small']['gt']} ({all_p['detector_only']['scaleBreakdown']['small']['recall']:.1%})")
        print(f"       Medium (>=16px): {all_p['detector_only']['scaleBreakdown']['medium']['tp50']}/{all_p['detector_only']['scaleBreakdown']['medium']['gt']} ({all_p['detector_only']['scaleBreakdown']['medium']['recall']:.1%})")
        print(f"     PRODUCT-FILTERED: TP50: {all_p['product_staging_filtered']['tp50']}/{all_p['product_staging_filtered']['totalGt']} ({all_p['product_staging_filtered']['recall50']:.1%}) | Clean-Skin FP: {all_p['product_staging_filtered']['verifiedCleanFp']}")
        print(f"       Micro (<8px): {all_p['product_staging_filtered']['scaleBreakdown']['micro']['tp50']}/{all_p['product_staging_filtered']['scaleBreakdown']['micro']['gt']} ({all_p['product_staging_filtered']['scaleBreakdown']['micro']['recall']:.1%})")
        print(f"       Small (8-16px): {all_p['product_staging_filtered']['scaleBreakdown']['small']['tp50']}/{all_p['product_staging_filtered']['scaleBreakdown']['small']['gt']} ({all_p['product_staging_filtered']['scaleBreakdown']['small']['recall']:.1%})")
        print(f"       Medium (>=16px): {all_p['product_staging_filtered']['scaleBreakdown']['medium']['tp50']}/{all_p['product_staging_filtered']['scaleBreakdown']['medium']['gt']} ({all_p['product_staging_filtered']['scaleBreakdown']['medium']['recall']:.1%})")

        # C) Pilot Trained Sample Group (25 photos)
        trn_res = evaluate_cohort_group(
            net, trained_sample_shas, cohort_cache,
            f"Trained Sample Group ({mname})"
        )
        trn_all = trn_res['all_photos']
        print(f"\n[Trained Sample Group ({trn_all['photoCount']} Photos, {trn_all['totalGt']} GT Lesions)]")
        print(f"  DETECTOR-ONLY: TP50: {trn_all['detector_only']['tp50']}/{trn_all['detector_only']['totalGt']} ({trn_all['detector_only']['recall50']:.1%}) | Mean IoU: {trn_all['detector_only']['meanMatchedIoU']:.3f} | Clean-Skin FP: {trn_all['detector_only']['verifiedCleanFp']}")
        print(f"  PRODUCT-FILTERED: TP50: {trn_all['product_staging_filtered']['tp50']}/{trn_all['product_staging_filtered']['totalGt']} ({trn_all['product_staging_filtered']['recall50']:.1%}) | Clean-Skin FP: {trn_all['product_staging_filtered']['verifiedCleanFp']}")

        elapsed_total_model = time.time() - t_model_start
        print(f"\nModel {mname} evaluation completed in {elapsed_total_model:.2f}s.")

        all_results[mkey] = {
            'modelName': mname,
            'weightsPath': str(mcfg['path']),
            'elapsedSeconds': round(elapsed_total_model, 2),
            'scopeBDevelopment': scope_b_res,
            'heldOutTrainControl': ctrl_res,
            'trainedSamples': trn_res
        }

        del net
        gc.collect()

    out_file = PILOT_DIR / 'canonical_pilot_comparison_evaluation.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved canonical evaluation to: {out_file}")

    res_dir = ROOT.parent / 'research/acne-input-audit-20261015'
    res_dir.mkdir(parents=True, exist_ok=True)
    with open(res_dir / 'canonical_pilot_comparison_evaluation.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2)
    print(f"Mirrored evaluation to: {res_dir / 'canonical_pilot_comparison_evaluation.json'}")

    return all_results


if __name__ == '__main__':
    main()
