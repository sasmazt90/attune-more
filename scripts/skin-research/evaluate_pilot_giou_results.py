#!/usr/bin/env python3
"""Evaluate Step 0 Baseline, Control (IoU Pilot), and Candidate (GIoU Pilot).

Directives (Item 5 & 6):
1. Evaluates three models:
   - Baseline: Step 0 (Calibrated Baseline, 18e94a95...)
   - Control: Pilot trained with IoU loss (150 steps)
   - Candidate: Pilot trained with GIoU loss (150 steps)
2. Across three evaluation scopes:
   - Scope A: Held-out TRAIN Control Group (28 photos unseen during pilot training).
   - Scope B: Trained Pilot Samples (25 representative photos from pilot training).
   - Scope C: Scope B Development Set (14 targets, 9 negative photos) using staging filter.
3. Rigorous 1-to-1 bipartite target matching:
   - TP50 (matched IoU >= 0.50),
   - Average matched IoU,
   - Size breakdown: Micro (<8px), Small (8-16px), Medium (>=16px),
   - Verified clean area false positive count.
4. Excludes eyewear-present photos from product success denominator.
5. Impartial decision: if GIoU is not superior, state it clearly.
"""

import sys
import gc
import json
import math
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
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from acne_box_support_staging import principled_accepted_boxes
from prepare_canonical_validation_cache import load_canonical_validation_cache
from skin_eyewear import classify_source

TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014'
STEP0_PATH = TRIAL_DIR / 'checkpoint-epoch-00-step-000000-1792014463030016700/model.safetensors'

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


def load_model_for_eval(weights_path: Path):
    net = build_yolox_p2_model()
    net.load_state_dict(load_file(str(weights_path)), strict=True)
    net.eval()
    return net


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


def infer_image_tiles(net: nn.Module, bgr: np.ndarray, crop: List[int], tile_size=384, stride=288, min_conf=0.30):
    """Sliding-tile inference over image crop."""
    h, w = bgr.shape[:2]
    x0, y0, x1, y1 = crop
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)

    xs = sorted(set([*range(x0, max(x0 + 1, x1 - tile_size + 1), stride), max(x0, x1 - tile_size)]))
    ys = sorted(set([*range(y0, max(y0 + 1, y1 - tile_size + 1), stride), max(y0, y1 - tile_size)]))

    tile_list = []
    tile_coords = []
    for a in xs:
        for b in ys:
            endx = min(w, a + tile_size)
            endy = min(h, b + tile_size)
            tile = np.full((tile_size, tile_size, 3), 114, dtype=np.uint8)
            crop_patch = bgr[b:endy, a:endx]
            tile[:crop_patch.shape[0], :crop_patch.shape[1]] = crop_patch
            tile_list.append(torch.from_numpy(tile.transpose(2, 0, 1)).float())
            tile_coords.append((a, b, endx, endy))

    if not tile_list:
        return []

    # Batch forward
    x = torch.stack(tile_list, dim=0)
    with torch.no_grad():
        preds = net(x)

    all_boxes = []
    all_scores = []
    for i, (a, b, endx, endy) in enumerate(tile_coords):
        p = preds[i]
        scores = p[:, 4] * p[:, 5]
        mask = scores >= min_conf
        if mask.any():
            f_p = p[mask]
            f_sc = scores[mask]
            cx, cy, bw, bh = f_p[:, 0], f_p[:, 1], f_p[:, 2], f_p[:, 3]
            bx = torch.clamp(cx - bw / 2 + a, min=float(a), max=float(endx))
            by = torch.clamp(cy - bh / 2 + b, min=float(b), max=float(endy))
            ex = torch.clamp(cx + bw / 2 + a, min=float(a), max=float(endx))
            ey = torch.clamp(cy + bh / 2 + b, min=float(b), max=float(endy))
            for k in range(len(f_p)):
                all_boxes.append([bx[k].item(), by[k].item(), ex[k].item(), ey[k].item()])
                all_scores.append(f_sc[k].item())

    if not all_boxes:
        return []

    # Hard-NMS @ 0.30 across tiles
    boxes_t = torch.tensor(all_boxes, dtype=torch.float32)
    scores_t = torch.tensor(all_scores, dtype=torch.float32)
    keep = torch_nms(boxes_t, scores_t, 0.30)
    nms_boxes = [all_boxes[i] + [all_scores[i]] for i in keep.numpy()]
    return nms_boxes


def evaluate_cohort_set(net: nn.Module, shas: List[str], train_rows: dict, scope_name: str):
    """Evaluate bipartite matching and clean FP on a set of TRAIN photos."""
    print(f"\nEvaluating on {scope_name} ({len(shas)} photos)...")

    total_gt = 0
    total_tp50 = 0
    all_matched_ious = []
    clean_photos_count = 0
    clean_fp_count = 0
    eyewear_excluded_count = 0

    micro_total, micro_tp = 0, 0
    small_total, small_tp = 0, 0
    med_total, med_tp = 0, 0

    for sha in shas:
        r = train_rows[sha]
        path = r.get('absolutePath') or str(LIVE_TEST / r['path'])
        bgr = cv2.imread(path)
        if bgr is None:
            continue

        # Check eyewear
        pts = r.get('landmarks', [])
        if len(pts) >= 468:
            eye_res = classify_source(bgr, pts)
            if eye_res['status'] != 'CLEAR':
                eyewear_excluded_count += 1
                continue

        anns = r.get('annotations', [])
        gt_boxes = [a['box'] for a in anns]
        crop = r.get('crop', [0, 0, bgr.shape[1], bgr.shape[0]])

        preds = infer_image_tiles(net, bgr, crop, min_conf=0.30)
        pred_boxes = [p[:4] for p in preds]

        if not gt_boxes:
            clean_photos_count += 1
            clean_fp_count += len(pred_boxes)
        else:
            pairs, tp_count, matched_ious = match_predictions_bipartite(gt_boxes, pred_boxes, iou_thresh=0.50)
            total_gt += len(gt_boxes)
            total_tp50 += tp_count
            all_matched_ious.extend(matched_ious)

            matched_gt_indices = set(p[0] for p in pairs)
            for idx, a in enumerate(anns):
                bx = a['box']
                dim = max(bx[2] - bx[0], bx[3] - bx[1])
                is_hit = (idx in matched_gt_indices)
                if dim < 8:
                    micro_total += 1
                    if is_hit: micro_tp += 1
                elif dim < 16:
                    small_total += 1
                    if is_hit: small_tp += 1
                else:
                    med_total += 1
                    if is_hit: med_tp += 1

    rec50 = total_tp50 / max(1, total_gt)
    mean_iou = float(np.mean(all_matched_ious)) if all_matched_ious else 0.0

    return {
        'totalGt': total_gt,
        'tp50': total_tp50,
        'recall50': rec50,
        'meanMatchedIoU': mean_iou,
        'scaleBreakdown': {
            'micro_less_8px': {'gt': micro_total, 'tp50': micro_tp, 'recall': micro_tp / max(1, micro_total)},
            'small_8_to_16px': {'gt': small_total, 'tp50': small_tp, 'recall': small_tp / max(1, small_total)},
            'medium_ge_16px': {'gt': med_total, 'tp50': med_tp, 'recall': med_tp / max(1, med_total)}
        },
        'cleanControlPhotos': clean_photos_count,
        'cleanAreaFp': clean_fp_count,
        'eyewearExcludedPhotos': eyewear_excluded_count
    }


def evaluate_scope_b(net: nn.Module, cached_val_images: list, model_name: str):
    """Evaluate Scope B (14 targets, 9 negative photos) using staging filter."""
    c_images_by_sha = {it['sha256']: it for it in cached_val_images}

    with open(ROOT / 'audit-results/acne-detection-verification-20261013/annotation-scope-manifest.json', 'r', encoding='utf-8') as f:
        annot_manifest = json.load(f)
    manifest_by_sha = {img['sha256']: img for img in annot_manifest['images']}

    # 1. Evaluate 14 targets across 3 positive photos
    matched_targets = set()
    target_counter = 0

    for sha in SCOPE_B_POSITIVE_SHAS:
        c_item = c_images_by_sha[sha]
        m_img = manifest_by_sha[sha]
        bgr = c_item['bgr']
        crop = [0, 0, bgr.shape[1], bgr.shape[0]]

        # Sliding tile inference
        raw_nms_boxes = infer_image_tiles(net, bgr, crop, min_conf=0.30)
        vis_regs = c_item['allowedRegions'] if c_item['productAngle'] is not None else None

        assigned, rejected = principled_accepted_boxes(
            raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
            sha, c_item['scale'], c_item['origin'], visible_regions=vis_regs, landmarks=c_item['landmarks'],
            source_shape=(c_item['height'], c_item['width']), bgr=c_item['bgr']
        )
        acc_boxes = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for blist in assigned.values() for b in blist]

        truth_boxes = c_item['truth']
        truth_cats = c_item['truthCategories']
        in_scope_indices = [i for i, cat in enumerate(truth_cats) if cat == 'IN_SCOPE_VISIBLE_REGION']

        pairs, _, _ = match_predictions_bipartite(truth_boxes, acc_boxes, iou_thresh=0.50)
        matched_gt_inds = set(p[0] for p in pairs)

        for idx, ann in enumerate(m_img['annotations']):
            if ann.get('scopeCategory') == 'IN_SCOPE_VISIBLE_REGION':
                target_counter += 1
                if idx in matched_gt_inds:
                    matched_targets.add(target_counter)

    # 2. Evaluate 9 negative photos
    negative_fps = 0
    fp_by_photo = {}
    for sha in SCOPE_B_NEGATIVE_SHAS:
        c_item = c_images_by_sha[sha]
        bgr = c_item['bgr']
        crop = [0, 0, bgr.shape[1], bgr.shape[0]]

        raw_nms_boxes = infer_image_tiles(net, bgr, crop, min_conf=0.30)
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
        'model': model_name,
        'recall': f"{len(matched_targets)}/14 ({len(matched_targets)/14:.1%})",
        'matchedTargets': sorted(list(matched_targets)),
        'negFpCount': negative_fps,
        'fpByPhoto': fp_by_photo
    }


def main():
    print("=" * 90)
    print("EMPIRICAL EVALUATION: BASELINE VS CONTROL (IOU) VS CANDIDATE (GIOU)")
    print("=" * 90)

    with open(COHORT_PATH, 'r', encoding='utf-8') as f:
        cohort = json.load(f)
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    train_rows = {r['sha256']: r for r in data['rows'] if r.get('split') == 'train'}

    # 28 held-out control photos
    control_shas = cohort['pilotControlShas']
    # 25 representative trained photos
    train_sample_shas = cohort['pilotTrainShas'][:25]

    cached_val_images = load_canonical_validation_cache()

    models = [
        {'name': 'Baseline (Step 0)', 'path': STEP0_PATH, 'key': 'step0'},
        {'name': 'Control Pilot (IoU 150-step)', 'path': CONTROL_PATH, 'key': 'control_iou'},
        {'name': 'Candidate Pilot (GIoU 150-step)', 'path': CANDIDATE_PATH, 'key': 'candidate_giou'}
    ]

    results = {}

    for mcfg in models:
        mkey = mcfg['key']
        mname = mcfg['name']
        print("\n" + "=" * 80)
        print(f"LOADING AND EVALUATING MODEL: {mname}")
        print("=" * 80)

        net = load_model_for_eval(mcfg['path'])

        # 1. Held-Out Control Group Evaluation
        ctrl_eval = evaluate_cohort_set(net, control_shas, train_rows, f"Held-out Control Group ({mname})")
        print(f"  [Held-Out Control] TP50: {ctrl_eval['tp50']}/{ctrl_eval['totalGt']} ({ctrl_eval['recall50']:.1%}) | Mean Matched IoU: {ctrl_eval['meanMatchedIoU']:.3f} | Clean Area FP: {ctrl_eval['cleanAreaFp']}")
        print(f"    Micro (<8px): {ctrl_eval['scaleBreakdown']['micro_less_8px']['tp50']}/{ctrl_eval['scaleBreakdown']['micro_less_8px']['gt']} ({ctrl_eval['scaleBreakdown']['micro_less_8px']['recall']:.1%})")
        print(f"    Small (8-16px): {ctrl_eval['scaleBreakdown']['small_8_to_16px']['tp50']}/{ctrl_eval['scaleBreakdown']['small_8_to_16px']['gt']} ({ctrl_eval['scaleBreakdown']['small_8_to_16px']['recall']:.1%})")
        print(f"    Medium (>=16px): {ctrl_eval['scaleBreakdown']['medium_ge_16px']['tp50']}/{ctrl_eval['scaleBreakdown']['medium_ge_16px']['gt']} ({ctrl_eval['scaleBreakdown']['medium_ge_16px']['recall']:.1%})")

        # 2. Trained Sample Evaluation
        trn_eval = evaluate_cohort_set(net, train_sample_shas, train_rows, f"Trained Sample Group ({mname})")
        print(f"  [Trained Sample]   TP50: {trn_eval['tp50']}/{trn_eval['totalGt']} ({trn_eval['recall50']:.1%}) | Mean Matched IoU: {trn_eval['meanMatchedIoU']:.3f} | Clean Area FP: {trn_eval['cleanAreaFp']}")

        # 3. Scope B Development Set Evaluation
        scope_b_eval = evaluate_scope_b(net, cached_val_images, mname)
        print(f"  [Scope B Dev Set]  Recall: {scope_b_eval['recall']} {scope_b_eval['matchedTargets']} | Neg FPs: {scope_b_eval['negFpCount']} across {len(scope_b_eval['fpByPhoto'])} photos.")

        results[mkey] = {
            'modelName': mname,
            'weightsPath': str(mcfg['path']),
            'heldOutControlEval': ctrl_eval,
            'trainedSampleEval': trn_eval,
            'scopeBDevelopmentEval': scope_b_eval
        }

        del net
        gc.collect()

    out_file = PILOT_DIR / 'pilot_giou_comparison_evaluation.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved pilot comparison evaluation to {out_file}")

    return results


if __name__ == '__main__':
    main()
