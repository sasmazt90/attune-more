#!/usr/bin/env python3
"""Diagnose TRAIN learning vs Validation generalization for acne model cf3a2ba4."""

import sys
import os
import json
import time
from pathlib import Path
from collections import defaultdict
import numpy as np
import cv2
import torch
from safetensors.torch import load_file
from torchvision.ops import nms as torch_nms

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2
from prepare_canonical_validation_cache import load_canonical_validation_cache
from acne_metrics import match_predictions_to_truth

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
CHK_PATH = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/checkpoint-epoch-02-step-000496-1791911067067742300/model.safetensors'

def load_model():
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    net.load_state_dict(load_file(str(CHK_PATH)), strict=True)
    net.eval()
    return net

def predict_tile(net, tile_bgr, conf_thresh=0.30, nms_thresh=0.30):
    """tile_bgr: (384, 384, 3) BGR float or uint8. Range [0, 255]."""
    tensor = torch.from_numpy(tile_bgr.transpose(2, 0, 1)).float().unsqueeze(0)
    with torch.no_grad():
        preds = net(tensor) # (1, 12240, 6)
    preds = preds[0]
    scores = preds[:, 4] * preds[:, 5]
    mask = scores >= conf_thresh
    if not mask.any():
        return np.empty((0, 5), dtype=np.float32)
    
    selected_preds = preds[mask]
    selected_scores = scores[mask]
    
    # cx, cy, w, h -> x1, y1, x2, y2
    cx = selected_preds[:, 0]
    cy = selected_preds[:, 1]
    w = selected_preds[:, 2]
    h = selected_preds[:, 3]
    x1 = cx - w / 2
    y1 = cy - h / 2
    x2 = cx + w / 2
    y2 = cy + h / 2
    boxes = torch.stack([x1, y1, x2, y2], dim=-1)
    
    keep = torch_nms(boxes, selected_scores, nms_thresh)
    keep_boxes = boxes[keep].cpu().numpy()
    keep_scores = selected_scores[keep].cpu().numpy()
    return np.column_stack([keep_boxes, keep_scores])

def evaluate_tiles(net, tiles, conf_thresholds=[0.30, 0.50]):
    print(f"Evaluating {len(tiles)} tiles...")
    results = {}
    for conf in conf_thresholds:
        results[conf] = {
            'total_gt': 0,
            'tp50': 0,
            'tp30': 0,
            'by_size': {
                'tiny': {'total': 0, 'tp50': 0},
                'small': {'total': 0, 'tp50': 0},
                'medium': {'total': 0, 'tp50': 0},
                'large': {'total': 0, 'tp50': 0}
            },
            'fp': 0,
            'clean_control_fp': 0
        }

    # Evaluate on a representative sample of 150 training tiles (positives + clean controls)
    pos_tiles = [t for t in tiles if len(t.get('boxes', [])) > 0]
    neg_tiles = [t for t in tiles if len(t.get('boxes', [])) == 0]
    eval_tiles = pos_tiles[:100] + neg_tiles[:50]
    print(f"Sampled {len(eval_tiles)} tiles ({len(pos_tiles[:100])} positive, {len(neg_tiles[:50])} clean control)")

    for t_idx, t in enumerate(eval_tiles):
        row = t['row']
        src_path = Path(row['absolutePath']) if 'absolutePath' in row and Path(row['absolutePath']).exists() else (LIVE_TEST / row['path'])
        full_bgr = None
        # Load image crop
        x0, y0, x1, y1 = t['rect']
        full_bgr = cv2.imread(str(src_path))
        if full_bgr is None:
            continue
        tile_bgr = full_bgr[y0:y1, x0:x1]
        if tile_bgr.shape[0] != 384 or tile_bgr.shape[1] != 384:
            # pad to 384x384
            padded = np.zeros((384, 384, 3), dtype=tile_bgr.dtype)
            padded[:tile_bgr.shape[0], :tile_bgr.shape[1]] = tile_bgr
            tile_bgr = padded

        gt_boxes = np.array(t.get('boxes', []), dtype=np.float32)
        is_clean = t.get('isCleanControl', False)

        for conf in conf_thresholds:
            preds = predict_tile(net, tile_bgr, conf_thresh=conf, nms_thresh=0.30)
            res = results[conf]

            if len(gt_boxes) > 0:
                pred_list = preds.tolist() if len(preds) > 0 else []
                gt_list = gt_boxes.tolist()
                
                # Match: match_predictions_to_truth(truth_boxes, pred_boxes, iou_thresh)
                matched_truth_50, matches_50, duplicate_p50, unmatched_p50, unmatched_t50 = match_predictions_to_truth(
                    gt_list, pred_list, 0.50
                )
                res['total_gt'] += len(gt_boxes)
                res['tp50'] += len(matched_truth_50)
                res['fp'] += len(unmatched_p50) + len(duplicate_p50)

                # Size breakdown
                matched_set = set(matched_truth_50)
                for b_idx, gb in enumerate(gt_boxes):
                    bw = gb[2] - gb[0]
                    bh = gb[3] - gb[1]
                    s = max(bw, bh)
                    cat = 'tiny' if s < 8 else 'small' if s < 16 else 'medium' if s < 32 else 'large'
                    res['by_size'][cat]['total'] += 1
                    if b_idx in matched_set:
                        res['by_size'][cat]['tp50'] += 1
            else:
                res['fp'] += len(preds)
                if is_clean:
                    res['clean_control_fp'] += len(preds)

    return results

def main():
    print("=== TRAIN vs VAL LEARNING DIAGNOSIS FOR cf3a2ba4 ===")
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tr_rows = [r for r in data['rows'] if r['split'] == 'train']
    masks, weights = build_hole_preserved_negative_masks(tr_rows)
    tiles = acne_tiles_p2(tr_rows, masks, training=True)

    net = load_model()

    train_res = evaluate_tiles(net, tiles, conf_thresholds=[0.30, 0.50])
    
    print("\n" + "=" * 80)
    print("TRAIN EVALUATION SUMMARY (Baseline Checkpoint cf3a2ba4)")
    print("=" * 80)
    for conf, r in train_res.items():
        print(f"\n--- Confidence {conf:.2f} ---")
        rec50 = r['tp50'] / max(r['total_gt'], 1)
        print(f"  Overall IoU50 Recall: {r['tp50']}/{r['total_gt']} ({rec50:.1%}) | False Positives: {r['fp']} (Clean control FP: {r['clean_control_fp']})")
        for cat, st in r['by_size'].items():
            cat_rec = st['tp50'] / max(st['total'], 1)
            print(f"    {cat:8s}: {st['tp50']}/{st['total']} ({cat_rec:.1%})")

    print("\n" + "=" * 80)
    print("COMPARISON WITH VALIDATION EVALUATION (Baseline Checkpoint cf3a2ba4)")
    print("=" * 80)
    print("  Validation Overall IoU50 (conf 0.30): 15/53 (28.3%)")
    print("    <8 px:   0/7  (0.0%)")
    print("    8-16 px: 5/31 (16.1%)")
    print("    16-32 px:10/15 (66.7%)")
    print("    Neg FP:  3 / 15 photos (0.20 FP/photo)")

if __name__ == '__main__':
    main()
