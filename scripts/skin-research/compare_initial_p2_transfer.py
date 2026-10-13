#!/usr/bin/env python3
"""Item 4: Empirical Measurement of Zero-Step P2 Transfer Impact vs Baseline and Trained Checkpoints.

Evaluates on canonical validation dev photos:
1. Frozen Baseline (3-scale YOLOX-S, SHA: 1a014ad...)
2. Zero-Step P2 (Transferred weights, p2_gate = 0.0, zero training steps)
3. P2 Epoch 1 (checkpoint-epoch-01-step-000248)
4. P2 Epoch 2 (checkpoint-epoch-02-step-000496)

Measures and records:
- Raw candidates (count, objectness distribution, classification score distribution, combined score distribution, scale breakdown)
- Post-NMS detections (IoU 0.30)
- Post-Filter v5 (anatomical mesh & exclusion) detections (TP50, TP30, FP on negative photos, FP per photo)
- Lesion size recall (<8px, 8-16px, 16-32px)
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import torch
import torch.nn as nn
from safetensors.torch import load_file
from torchvision.ops import nms as torch_nms

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
from yolox_numeric import install_bounds
from yolox_p2 import build_yolox_p2_model, load_baseline_weights_to_p2_model
from acne_metrics import match_predictions_to_truth
from prepare_canonical_validation_cache import load_canonical_validation_cache
import importlib.util

# Ensure local acne_box_support is loaded
_spec = importlib.util.spec_from_file_location("acne_box_support", str(ROOT / 'services/core-api/acne_box_support.py'))
acne_box_support = importlib.util.module_from_spec(_spec)
sys.modules['acne_box_support'] = acne_box_support
_spec.loader.exec_module(acne_box_support)

BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-focal-20261013'
EPOCH1_WEIGHTS = TRIAL_DIR / 'checkpoint-epoch-01-step-000248-1791893135864784800/model.safetensors'
EPOCH2_WEIGHTS = TRIAL_DIR / 'checkpoint-epoch-02-step-000496-1791896207482816200/model.safetensors'


def extract_raw_predictions_with_scores(net, bgr, points, tile_size=384, stride=288, min_score=0.01):
    """Extract raw predictions including decomposed obj, cls, and combined scores."""
    h, w = bgr.shape[:2]
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
        return []

    batch = torch.stack(tile_tensors, dim=0)
    with torch.no_grad():
        out = net(batch)

    raw_cands = []
    for i, (a, b, endx, endy) in enumerate(tiles_info):
        pred = out[i]
        obj_sc = pred[:, 4]
        cls_sc = pred[:, 5]
        scores = obj_sc * cls_sc
        mask = scores >= min_score
        if mask.any():
            filt = pred[mask]
            sc = scores[mask]
            obj = obj_sc[mask]
            cls_ = cls_sc[mask]
            cx, cy, bw, bh = filt[:, 0], filt[:, 1], filt[:, 2], filt[:, 3]
            bx = torch.clamp(cx - bw / 2 + a, min=float(a))
            by = torch.clamp(cy - bh / 2 + b, min=float(b))
            ex = torch.clamp(cx + bw / 2 + a, max=float(endx))
            ey = torch.clamp(cy + bh / 2 + b, max=float(endy))
            for k in range(len(filt)):
                raw_cands.append({
                    'box': [bx[k].item(), by[k].item(), ex[k].item(), ey[k].item()],
                    'score': sc[k].item(),
                    'obj_score': obj[k].item(),
                    'cls_score': cls_[k].item()
                })
    return raw_cands


def evaluate_model_pipeline(net, model_name: str, cached_images: List[dict]):
    """Evaluates raw candidates, NMS, and Filter v5 across cached validation images."""
    print(f"\n--- Evaluating Model: {model_name} ---", flush=True)
    net.eval()
    t0 = time.time()

    all_raw_cands = []
    per_image_raw = []

    for item in cached_images:
        bgr = item['bgr']
        points = item['landmarks']
        if not points:
            per_image_raw.append([])
            continue
        raw_c = extract_raw_predictions_with_scores(net, bgr, points, min_score=0.01)
        per_image_raw.append(raw_c)
        all_raw_cands.extend(raw_c)

    elapsed_extract = time.time() - t0

    # Score distributions
    def score_stats(scores_list):
        if not scores_list:
            return {'count': 0, 'min': 0, 'mean': 0, 'max': 0, 'p50': 0, 'p75': 0, 'p90': 0}
        arr = np.array(scores_list)
        return {
            'count': len(arr),
            'min': round(float(np.min(arr)), 4),
            'mean': round(float(np.mean(arr)), 4),
            'max': round(float(np.max(arr)), 4),
            'p50': round(float(np.percentile(arr, 50)), 4),
            'p75': round(float(np.percentile(arr, 75)), 4),
            'p90': round(float(np.percentile(arr, 90)), 4)
        }

    raw_scores = [c['score'] for c in all_raw_cands]
    raw_obj = [c['obj_score'] for c in all_raw_cands]
    raw_cls = [c['cls_score'] for c in all_raw_cands]

    # Evaluate across confidence thresholds: 0.30, 0.50, 0.70
    threshold_metrics = {}
    for conf_thre in [0.30, 0.50, 0.70]:
        total_nms_cands = 0
        total_accepted = 0
        in_scope_tp50 = 0
        in_scope_tp30 = 0
        neg_fp = 0
        neg_photos_with_fp = 0
        small_rec = {
            'tiny_less_8px': {'total': 0, 'tp50': 0},
            'small_8_to_16px': {'total': 0, 'tp50': 0},
            'medium_16_to_32px': {'total': 0, 'tp50': 0}
        }

        total_in_scope = 0
        total_neg_photos = 0

        for item, raw_cands in zip(cached_images, per_image_raw):
            points = item['landmarks']
            is_neg = item['isNegative']
            is_prod_pose = item['isProductPose']
            truth_boxes = item['truth']
            truth_categories = item['truthCategories']

            if is_neg:
                total_neg_photos += 1

            if not points or not raw_cands:
                accepted_boxes = []
            else:
                cands = [c for c in raw_cands if c['score'] >= conf_thre]
                if cands:
                    boxes_t = torch.tensor([c['box'] for c in cands], dtype=torch.float32)
                    scores_t = torch.tensor([c['score'] for c in cands], dtype=torch.float32)
                    keep_idx = torch_nms(boxes_t, scores_t, 0.30)
                    nms_cands = [cands[i] for i in keep_idx.numpy()]
                else:
                    nms_cands = []

                total_nms_cands += len(nms_cands)

                raw_nms_boxes = [c['box'] + [c['score']] for c in nms_cands]
                vis_regs = item['allowedRegions'] if item['productAngle'] is not None else None
                acc, rej = acne_box_support.accepted_boxes(
                    raw_nms_boxes,
                    item['envelopes'],
                    item['skin_support'],
                    item['hair'],
                    item['exclusion'],
                    item['sha256'],
                    item['scale'],
                    item['origin'],
                    visible_regions=vis_regs,
                    landmarks=points,
                    source_shape=(item['height'], item['width'])
                )
                accepted_boxes = [b for blist in acc.values() for b in blist]

            total_accepted += len(accepted_boxes)

            matched_50, _, _, _, _ = match_predictions_to_truth(truth_boxes, accepted_boxes, 0.50)
            matched_30, _, _, _, _ = match_predictions_to_truth(truth_boxes, accepted_boxes, 0.30)

            in_scope_indices = [i for i, cat in enumerate(truth_categories) if cat == 'IN_SCOPE_VISIBLE_REGION']
            matched_in_scope50 = set(matched_50).intersection(set(in_scope_indices))
            matched_in_scope30 = set(matched_30).intersection(set(in_scope_indices))

            if is_prod_pose:
                total_in_scope += len(in_scope_indices)
                in_scope_tp50 += len(matched_in_scope50)
                in_scope_tp30 += len(matched_in_scope30)

                for idx in in_scope_indices:
                    bx = truth_boxes[idx]
                    dim = max(bx[2] - bx[0], bx[3] - bx[1])
                    if dim < 8:
                        grp = 'tiny_less_8px'
                    elif dim < 16:
                        grp = 'small_8_to_16px'
                    else:
                        grp = 'medium_16_to_32px'
                    small_rec[grp]['total'] += 1
                    if idx in matched_in_scope50:
                        small_rec[grp]['tp50'] += 1

            if is_neg:
                fp_count = len(accepted_boxes)
                neg_fp += fp_count
                if fp_count > 0:
                    neg_photos_with_fp += 1

        rec50 = in_scope_tp50 / max(total_in_scope, 1)
        rec30 = in_scope_tp30 / max(total_in_scope, 1)
        fp_rate = neg_fp / max(total_neg_photos, 1)

        threshold_metrics[str(conf_thre)] = {
            'confThreshold': conf_thre,
            'totalNmsCandidates': total_nms_cands,
            'totalAcceptedBoxes': total_accepted,
            'inScopeTruth': total_in_scope,
            'inScopeTp50': in_scope_tp50,
            'inScopeTp30': in_scope_tp30,
            'rec50': round(rec50, 4),
            'rec30': round(rec30, 4),
            'negTotalFp': neg_fp,
            'negPhotosWithFp': neg_photos_with_fp,
            'totalNegPhotos': total_neg_photos,
            'fpPerPhoto': round(fp_rate, 3),
            'smallLesionRecall': {
                k: {
                    'total': v['total'],
                    'tp50': v['tp50'],
                    'rec50': round(v['tp50'] / max(v['total'], 1), 4)
                }
                for k, v in small_rec.items()
            }
        }

    report = {
        'modelName': model_name,
        'inferenceTimeSec': round(elapsed_extract, 2),
        'rawCandidates': {
            'totalCount': len(all_raw_cands),
            'combinedScoreStats': score_stats(raw_scores),
            'objectnessScoreStats': score_stats(raw_obj),
            'classificationScoreStats': score_stats(raw_cls)
        },
        'thresholdMetrics': threshold_metrics
    }
    return report


def main():
    print("=== Empirical Zero-Step P2 Transfer Impact Comparison ===", flush=True)
    cached_images = load_canonical_validation_cache()
    print(f"Loaded {len(cached_images)} canonical validation images from cache.", flush=True)

    results = {}

    # 1. Baseline Model (3-scale YOLOX-S)
    print("\n[1/4] Loading Frozen Baseline YOLOX-S...", flush=True)
    base_net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(base_net)
    base_net.load_state_dict(load_file(str(BASELINE_WEIGHTS)))
    results['baseline'] = evaluate_model_pipeline(base_net, 'Frozen Baseline (3-scale YOLOX-S)', cached_images)

    # 2. Zero-Step P2 Model (4-scale YOLOX-S with zero-init gate)
    print("\n[2/4] Loading Zero-Step Transferred P2 (with Zero-Init Gate)...", flush=True)
    p2_zero_net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    load_baseline_weights_to_p2_model(p2_zero_net, BASELINE_WEIGHTS)
    results['p2_zero_step'] = evaluate_model_pipeline(p2_zero_net, 'Zero-Step P2 (Transferred, p2_gate=0.0)', cached_images)

    # 3. Checkpoint Epoch 1
    if EPOCH1_WEIGHTS.exists():
        print("\n[3/4] Loading Checkpoint Epoch 1...", flush=True)
        ep1_net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        # Note: ep1 checkpoint was saved without p2_gate, strict=False loads cleanly
        ep1_net.load_state_dict(load_file(str(EPOCH1_WEIGHTS)), strict=False)
        results['p2_epoch1'] = evaluate_model_pipeline(ep1_net, 'P2 Checkpoint Epoch 1 (step 248)', cached_images)

    # 4. Checkpoint Epoch 2
    if EPOCH2_WEIGHTS.exists():
        print("\n[4/4] Loading Checkpoint Epoch 2...", flush=True)
        ep2_net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        ep2_net.load_state_dict(load_file(str(EPOCH2_WEIGHTS)), strict=False)
        results['p2_epoch2'] = evaluate_model_pipeline(ep2_net, 'P2 Checkpoint Epoch 2 (step 496)', cached_images)

    # Save detailed JSON report
    out_path = TRIAL_DIR / 'zero_step_p2_transfer_comparison.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nFull comparison saved to: {out_path}", flush=True)

    # Print summary table
    print("\n" + "=" * 95)
    print(f"{'Model':<35} | {'Raw Cands':<9} | {'In-Scope IoU50 (conf 0.70)':<25} | {'Neg FP/photo':<12}")
    print("-" * 95)
    for k, v in results.items():
        m70 = v['thresholdMetrics']['0.7']
        print(f"{v['modelName']:<35} | {v['rawCandidates']['totalCount']:<9} | {m70['inScopeTp50']}/{m70['inScopeTruth']} ({m70['rec50']:.1%}) | {m70['fpPerPhoto']:.3f} ({m70['negTotalFp']} total)")
    print("=" * 95)


if __name__ == '__main__':
    main()
