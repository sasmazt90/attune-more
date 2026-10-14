#!/usr/bin/env python3
"""Standardized Image-Level TRAIN vs Canonical VAL Learning Diagnosis for Baseline cf3a2ba4.

Adheres strictly to Item 1, 2, 3 requirements:
1. Strict model identity verification: loads cf3a2ba4 with SHA-256 enforcement.
2. Canonical preprocessing: BGR, 384x384, pad=114, float32 via acne_preprocessing.py.
3. Full image-level evaluation with sliding tiles (288 stride) and source-coordinate projection:
   - Eliminates duplicate tile counting of the same lesion.
   - Evaluates on exact unique ground-truth lesions.
   - Respects UNKNOWN skin masks: only detections in verified clean skin are counted as negative FP.
4. Produces transparent, deterministic receipt.
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import numpy as np
import cv2
import torch
from torchvision.ops import nms as torch_nms

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from model_identity import (
    TRUE_BASELINE_EPOCH02_PATH,
    TRUE_BASELINE_EPOCH02_SHA,
    load_verified_model,
    generate_evaluation_receipt
)
from acne_preprocessing import (
    PREPROCESSING_VERSION,
    extract_tile_bgr,
    tile_to_tensor,
    generate_sliding_tile_rects
)
from negative_mask_builder import build_hole_preserved_negative_masks
from prepare_canonical_validation_cache import load_canonical_validation_cache
from acne_metrics import match_predictions_to_truth
import importlib.util
_spec = importlib.util.spec_from_file_location("acne_box_support", str(ROOT / 'services/core-api/acne_box_support.py'))
acne_box_support = importlib.util.module_from_spec(_spec)
sys.modules['acne_box_support'] = acne_box_support
_spec.loader.exec_module(acne_box_support)

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
OUTPUT_RECEIPT_PATH = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/train_vs_val_canonical_receipt.json'


def predict_image_sliding_tiles(
    net: torch.nn.Module,
    bgr: np.ndarray,
    crop_rect: Tuple[int, int, int, int],
    tile_size: int = 384,
    stride: int = 288,
    conf_thresh: float = 0.30,
    nms_thresh: float = 0.30
) -> List[List[float]]:
    """Run canonical sliding tile inference with pad=114 and project back to source coords."""
    h, w = bgr.shape[:2]
    crop_x0, crop_y0, crop_x1, crop_y1 = crop_rect
    tile_rects = generate_sliding_tile_rects(crop_x0, crop_y0, crop_x1, crop_y1, w, h, tile_size=tile_size, stride=stride)

    raw_preds = []
    for rect in tile_rects:
        a, b, endx, endy = rect
        tile_bgr = extract_tile_bgr(bgr, rect, tile_size=tile_size, pad_val=114)
        t_tensor = tile_to_tensor(tile_bgr).unsqueeze(0)

        with torch.no_grad():
            out = net(t_tensor)[0]  # [12240, 6]

        scores = out[:, 4] * out[:, 5]
        mask = scores >= conf_thresh
        if mask.any():
            sel_out = out[mask]
            sel_scores = scores[mask]
            for row, sc in zip(sel_out.numpy(), sel_scores.numpy()):
                cx, cy, bw, bh = row[:4]
                x0 = max(0.0, float(cx - bw / 2.0 + a))
                y0 = max(0.0, float(cy - bh / 2.0 + b))
                x1 = min(float(w), float(cx + bw / 2.0 + a))
                y1 = min(float(h), float(cy + bh / 2.0 + b))
                raw_preds.append([x0, y0, x1, y1, float(sc)])

    if not raw_preds:
        return []

    # Image-level NMS
    boxes_t = torch.tensor([p[:4] for p in raw_preds], dtype=torch.float32)
    scores_t = torch.tensor([p[4] for p in raw_preds], dtype=torch.float32)
    keep = torch_nms(boxes_t, scores_t, nms_thresh)
    return [raw_preds[i] for i in keep.numpy()]


def evaluate_dataset_canonical(
    net: torch.nn.Module,
    rows: List[dict],
    masks: Dict[str, np.ndarray],
    conf_thresh: float = 0.30,
    nms_thresh: float = 0.30,
    is_train: bool = True
) -> Dict[str, Any]:
    """Run full image-level evaluation with deduplicated unique GT lesion matching."""
    total_images = len(rows)
    total_gt = 0
    total_tp50 = 0
    total_tp30 = 0
    total_preds = 0
    verified_clean_fp = 0

    by_size = {
        'tiny': {'total': 0, 'tp50': 0, 'tp30': 0},
        'small': {'total': 0, 'tp50': 0, 'tp30': 0},
        'medium': {'total': 0, 'tp50': 0, 'tp30': 0},
        'large': {'total': 0, 'tp50': 0, 'tp30': 0}
    }

    t0 = time.time()
    for idx, r in enumerate(rows):
        sha = r['sha256']
        path = r.get('absolutePath') or str(LIVE_TEST / r['path'])
        bgr = cv2.imread(path)
        if bgr is None:
            raise FileNotFoundError(f"Cannot load image: {path}")

        h, w = bgr.shape[:2]
        crop_rect = r.get('crop', [0, 0, w, h])
        clean_mask = masks.get(sha)

        # Ground truth lesions in crop
        gt_boxes = []
        for ann in r.get('annotations', []):
            if ann.get('classId') == 0:
                bx, by, ex, ey = ann['box']
                gt_boxes.append([float(bx), float(by), float(ex), float(ey)])

        # Predict image
        preds = predict_image_sliding_tiles(
            net, bgr, crop_rect,
            tile_size=384, stride=288,
            conf_thresh=conf_thresh, nms_thresh=nms_thresh
        )
        total_preds += len(preds)

        if gt_boxes:
            total_gt += len(gt_boxes)
            # Size categorization
            for gb in gt_boxes:
                dim = max(gb[2] - gb[0], gb[3] - gb[1])
                cat = 'tiny' if dim < 8 else ('small' if dim < 16 else ('medium' if dim < 32 else 'large'))
                by_size[cat]['total'] += 1

            matched_50, _, _, unmatched_p50, _ = match_predictions_to_truth(gt_boxes, preds, 0.50)
            matched_30, _, _, _, _ = match_predictions_to_truth(gt_boxes, preds, 0.30)

            total_tp50 += len(matched_50)
            total_tp30 += len(matched_30)

            matched_set_50 = set(matched_50)
            matched_set_30 = set(matched_30)
            for g_i, gb in enumerate(gt_boxes):
                dim = max(gb[2] - gb[0], gb[3] - gb[1])
                cat = 'tiny' if dim < 8 else ('small' if dim < 16 else ('medium' if dim < 32 else 'large'))
                if g_i in matched_set_50:
                    by_size[cat]['tp50'] += 1
                if g_i in matched_set_30:
                    by_size[cat]['tp30'] += 1

            # Check unmatched predictions against verified clean skin mask
            if clean_mask is not None:
                for p_idx in unmatched_p50:
                    px0, py0, px1, py1, _ = preds[p_idx]
                    cx = int(round((px0 + px1) / 2.0))
                    cy = int(round((py0 + py1) / 2.0))
                    if 0 <= cy < h and 0 <= cx < w and clean_mask[cy, cx] > 0:
                        verified_clean_fp += 1
        else:
            # Clean control image
            if clean_mask is not None:
                for p in preds:
                    cx = int(round((p[0] + p[2]) / 2.0))
                    cy = int(round((p[1] + p[3]) / 2.0))
                    if 0 <= cy < h and 0 <= cx < w and clean_mask[cy, cx] > 0:
                        verified_clean_fp += 1

    elapsed = time.time() - t0
    rec50 = total_tp50 / max(total_gt, 1)
    rec30 = total_tp30 / max(total_gt, 1)

    return {
        'totalImages': total_images,
        'totalUniqueGt': total_gt,
        'tp50': total_tp50,
        'tp30': total_tp30,
        'rec50': round(rec50, 4),
        'rec30': round(rec30, 4),
        'totalPreds': total_preds,
        'verifiedCleanSkinFp': verified_clean_fp,
        'bySize': {
            cat: {
                'total': v['total'],
                'tp50': v['tp50'],
                'rec50': round(v['tp50'] / max(v['total'], 1), 4),
                'tp30': v['tp30'],
                'rec30': round(v['tp30'] / max(v['total'], 1), 4)
            }
            for cat, v in by_size.items()
        },
        'elapsedSeconds': round(elapsed, 1)
    }


def main():
    print("=" * 80)
    print("CANONICAL IMAGE-LEVEL TRAIN VS VAL LEARNING DIAGNOSIS")
    print("=" * 80)

    # 1. Load verified model
    net, model_sha = load_verified_model(
        TRUE_BASELINE_EPOCH02_PATH,
        expected_sha=TRUE_BASELINE_EPOCH02_SHA
    )
    print(f"Verified Model: {model_sha} from {TRUE_BASELINE_EPOCH02_PATH.name}")

    # 2. Load dataset
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    train_rows = [r for r in data['rows'] if r['split'] == 'train']
    print(f"Loaded {len(train_rows)} TRAIN rows from reviewed dataset.")

    # Build hole-preserved negative masks for clean skin accounting
    masks, _ = build_hole_preserved_negative_masks(train_rows)

    # 3. Evaluate TRAIN dataset
    print(f"\n[1/2] Running canonical evaluation on all {len(train_rows)} TRAIN images...")
    train_metrics = evaluate_dataset_canonical(
        net, train_rows, masks,
        conf_thresh=0.30, nms_thresh=0.30, is_train=True
    )
    print(f"  TRAIN Result (conf 0.30): IoU50 = {train_metrics['tp50']}/{train_metrics['totalUniqueGt']} ({train_metrics['rec50']:.1%}) | Verified Clean FP = {train_metrics['verifiedCleanSkinFp']}")
    for cat, v in train_metrics['bySize'].items():
        print(f"    {cat:8s}: {v['tp50']:4d}/{v['total']:4d} ({v['rec50']:6.1%})")

    # 4. Canonical Validation from cache
    val_cached = load_canonical_validation_cache()
    # Canonical validation uses acne_box_support + inScopeProductPose
    from train_p2_focal_trial import evaluate_canonical_validation
    print(f"\n[2/2] Running canonical evaluation on 43 validation images...")
    val_res = evaluate_canonical_validation(net, val_cached, conf_thresholds=[0.30])
    v30 = val_res['0.3']

    val_metrics = {
        'inScopeTruth': v30['inScopeTruth'],
        'inScopeTp50': v30['inScopeTp50'],
        'rec50': v30['rec50'],
        'negTotalFp': v30['negTotalFp'],
        'fpPerPhoto': v30['fpPerPhoto'],
        'bySize': {
            'tiny': {'total': 7, 'tp50': v30['smallLesionRecall']['tiny_less_8px']['tp50'], 'rec50': v30['smallLesionRecall']['tiny_less_8px']['tp50'] / 7.0},
            'small': {'total': 31, 'tp50': v30['smallLesionRecall']['small_8_to_16px']['tp50'], 'rec50': v30['smallLesionRecall']['small_8_to_16px']['tp50'] / 31.0},
            'medium': {'total': 15, 'tp50': v30['smallLesionRecall']['medium_16_to_32px']['tp50'], 'rec50': v30['smallLesionRecall']['medium_16_to_32px']['tp50'] / 15.0},
        }
    }
    print(f"  VAL Result (conf 0.30): IoU50 = {val_metrics['inScopeTp50']}/{val_metrics['inScopeTruth']} ({val_metrics['rec50']:.1%}) | Neg FP = {val_metrics['negTotalFp']} ({val_metrics['fpPerPhoto']:.2f}/photo)")
    for cat, v in val_metrics['bySize'].items():
        print(f"    {cat:8s}: {v['tp50']:4d}/{v['total']:4d} ({v['rec50']:6.1%})")

    receipt = generate_evaluation_receipt(
        model_identity="True Baseline cf3a2ba4 (Epoch 02)",
        model_sha=model_sha,
        model_path=str(TRUE_BASELINE_EPOCH02_PATH),
        dataset_path=str(DATA_PATH),
        dataset_version="train-data-engineering-reviewed-20261013",
        preprocessing_version=PREPROCESSING_VERSION,
        conf_threshold=0.30,
        nms_threshold=0.30,
        filter_version=acne_box_support.VERSION,
        metrics={
            'train': train_metrics,
            'validation': val_metrics
        }
    )

    with open(OUTPUT_RECEIPT_PATH, 'w', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2)

    print(f"\nCanonical receipt saved to: {OUTPUT_RECEIPT_PATH}")


if __name__ == '__main__':
    main()
