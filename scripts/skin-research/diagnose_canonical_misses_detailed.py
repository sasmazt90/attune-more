#!/usr/bin/env python3
"""Canonical 38-Miss Detailed Diagnosis with Exact Candidate Box, Score, and Pipeline Ledger.

Contract & Integrity Rules (Item 4):
1. Exact canonical product pipeline:
   - Face landmark envelope with 15% pad.
   - Sliding tiles: size=384, stride=288, pad=114, BGR float32.
   - Canonical score formula: score = obj_prob * cls_prob (NOT sqrt).
2. Exact Tracking per Ground Truth Target (53 in-scope targets across 9 product pose images):
   - For every target, records exact target identity (fileName, truthIndex, GT box, category, dimensions).
   - Identifies whether caught at IoU >= 0.50 by accepted boxes (verifies exact 15 caught, 38 missed).
   - For every missed target, pairs the exact best-matching candidate box with:
     * Source coordinates [x0, y0, x1, y1]
     * IoU with GT box
     * Objectness probability (obj_prob)
     * Classification probability (cls_prob)
     * Combined score (obj_prob * cls_prob)
     * Pyramid level and stride (Stride 4, 8, 16, or 32)
     * Exact stage reached:
       - DROPPED_CONF_UNDER_30 (score < 0.30)
       - DROPPED_AT_NMS (suppressed by higher-scoring neighbor)
       - DROPPED_BY_FILTER (rejected by anatomical filter v5 with specific reason)
       - SUB_50_IOU_ONLY (no candidate achieved IoU >= 0.50)
3. Zero dogma / Zero unmeasured claims:
   - Fully documents observed values per target without unmeasured sensor-noise assertions.
"""

import sys
import os
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Any
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
    load_verified_model
)
from acne_preprocessing import (
    PREPROCESSING_VERSION,
    extract_tile_bgr,
    tile_to_tensor,
    generate_sliding_tile_rects
)
from prepare_canonical_validation_cache import load_canonical_validation_cache
from acne_metrics import match_predictions_to_truth, compute_iou
import acne_box_support

OUTPUT_LEDGER_PATH = ROOT / "audit-results/acne-candidate-p2-focal-20261013/canonical_38_misses_ledger.json"


def get_stride_and_level(anchor_idx: int) -> Tuple[int, str]:
    if anchor_idx < 9216:
        return 4, "Level 0 (P2 stride 4)"
    elif anchor_idx < 9216 + 2304:
        return 8, "Level 1 (P3 stride 8)"
    elif anchor_idx < 9216 + 2304 + 576:
        return 16, "Level 2 (P4 stride 16)"
    else:
        return 32, "Level 3 (P5 stride 32)"


def extract_canonical_proposals(net, bgr, points, tile_size=384, stride=288, min_score=0.0001):
    """Run canonical sliding tile inference, preserving anchor index, stride, and scores."""
    h, w = bgr.shape[:2]
    face_lms = np.array([[p['x'] * w, p['y'] * h] for p in points[:468]])
    min_x, max_x = int(np.floor(face_lms[:, 0].min())), int(np.ceil(face_lms[:, 0].max()))
    min_y, max_y = int(np.floor(face_lms[:, 1].min())), int(np.ceil(face_lms[:, 1].max()))

    pad = max(24, int((max_x - min_x) * 0.15))
    crop_x0 = max(0, min_x - pad)
    crop_y0 = max(0, min_y - pad)
    crop_x1 = min(w, max_x + pad)
    crop_y1 = min(h, max_y + pad)

    tile_rects = generate_sliding_tile_rects(crop_x0, crop_y0, crop_x1, crop_y1, w, h, tile_size=tile_size, stride=stride)
    raw_candidates = []

    for t_idx, rect in enumerate(tile_rects):
        a, b, endx, endy = rect
        tile_bgr = extract_tile_bgr(bgr, rect, tile_size=tile_size, pad_val=114)
        t_tensor = tile_to_tensor(tile_bgr).unsqueeze(0)

        with torch.no_grad():
            out = net(t_tensor)[0]  # [12240, 6] -> [cx, cy, w, h, obj_prob, cls_prob]

        # Canonical score formula: obj * cls
        scores = out[:, 4] * out[:, 5]
        mask = scores >= min_score

        if mask.any():
            sel_indices = torch.where(mask)[0]
            for a_idx in sel_indices:
                row = out[a_idx].numpy()
                sc = scores[a_idx].item()
                cx, cy, bw, bh = row[:4]
                x0 = max(0.0, float(cx - bw / 2.0 + a))
                y0 = max(0.0, float(cy - bh / 2.0 + b))
                x1 = min(float(w), float(cx + bw / 2.0 + a))
                y1 = min(float(h), float(cy + bh / 2.0 + b))
                s_val, lvl_str = get_stride_and_level(int(a_idx))

                raw_candidates.append({
                    'cand_id': len(raw_candidates),
                    'box': [x0, y0, x1, y1],
                    'score': float(sc),
                    'obj_prob': float(row[4]),
                    'cls_prob': float(row[5]),
                    'stride': s_val,
                    'level': lvl_str,
                    'anchor_idx': int(a_idx),
                    'tile_idx': t_idx,
                    'tile_rect': rect
                })

    return raw_candidates


def main():
    print("=" * 80)
    print("CANONICAL 38-MISS DETAILED DIAGNOSIS & PROPOSAL LEDGER")
    print(f"Target: True Baseline cf3a2ba4")
    print("=" * 80)

    # 1. Load verified model
    net, model_sha = load_verified_model(TRUE_BASELINE_EPOCH02_PATH, expected_sha=TRUE_BASELINE_EPOCH02_SHA)
    net.eval()
    print(f"Verified Model: {model_sha} from {TRUE_BASELINE_EPOCH02_PATH.name}")

    # 2. Load canonical validation cache
    cached_images = load_canonical_validation_cache()
    pos_items = [item for item in cached_images if item.get('isProductPose') and not item.get('isNegative') and len(item.get('truth', [])) > 0]
    print(f"Found {len(pos_items)} positive product pose validation images.")

    # 3. Process each image through canonical pipeline
    all_truth_records = []
    caught_count = 0
    missed_count = 0

    for item in pos_items:
        fn = item['fileName']
        bgr = item['bgr']
        points = item['landmarks']
        truth_boxes = item['truth']
        truth_cats = item['truthCategories']
        in_scope_indices = [i for i, c in enumerate(truth_cats) if c == 'IN_SCOPE_VISIBLE_REGION']

        # Extract all candidates down to 0.0001
        raw_cands = extract_canonical_proposals(net, bgr, points, min_score=0.0001)

        # Stage 1: Filter at conf >= 0.30
        conf30_cands = [c for c in raw_cands if c['score'] >= 0.30]

        # Stage 2: NMS at 0.30
        nms_kept_ids = set()
        if conf30_cands:
            boxes_t = torch.tensor([c['box'] for c in conf30_cands], dtype=torch.float32)
            scores_t = torch.tensor([c['score'] for c in conf30_cands], dtype=torch.float32)
            keep_idx = torch_nms(boxes_t, scores_t, 0.30)
            nms30_cands = [conf30_cands[i] for i in keep_idx.numpy()]
            nms_kept_ids = set(c['cand_id'] for c in nms30_cands)
        else:
            nms30_cands = []

        # Stage 3: Anatomical filter v5
        raw_nms_boxes = [c['box'] + [c['score']] for c in nms30_cands]
        vis_regs = item['allowedRegions'] if item['productAngle'] is not None else None
        acc, rej = acne_box_support.accepted_boxes(
            raw_nms_boxes, item['envelopes'], item['skin_support'], item['hair'], item['exclusion'],
            item['sha256'], item['scale'], item['origin'], visible_regions=vis_regs,
            landmarks=points, source_shape=(item['height'], item['width'])
        )
        accepted_boxes = [b for blist in acc.values() for b in blist]

        # Match accepted boxes to truth at IoU 0.50
        matched_truth_indices_50, matches_50, _, _, _ = match_predictions_to_truth(truth_boxes, accepted_boxes, 0.50)
        caught_set = set(matched_truth_indices_50).intersection(set(in_scope_indices))

        for t_idx in in_scope_indices:
            gt_box = truth_boxes[t_idx]
            gx0, gy0, gx1, gy1 = gt_box
            gw = gx1 - gx0
            gh = gy1 - gy0
            max_dim = max(gw, gh)
            cat = 'tiny_less_8px' if max_dim < 8.0 else ('small_8_to_16px' if max_dim < 16.0 else 'medium_16_to_32px')

            is_caught = t_idx in caught_set
            record = {
                'fileName': fn,
                'truthIndex': t_idx,
                'gt_box': [round(x, 1) for x in gt_box],
                'dimensions': {'w': round(gw, 1), 'h': round(gh, 1), 'maxDim': round(max_dim, 1)},
                'sizeCategory': cat,
                'isCaught': is_caught,
            }

            if is_caught:
                caught_count += 1
                record['status'] = 'CAUGHT_IOU50'
                all_truth_records.append(record)
                continue

            missed_count += 1
            record['status'] = 'MISSED'

            # Find best overlapping candidate in raw proposals
            best_cand = None
            best_iou = 0.0

            for c in raw_cands:
                iou = compute_iou(c['box'], gt_box)
                if iou > best_iou:
                    best_iou = iou
                    best_cand = c

            if best_cand is not None:
                # Determine stage reached
                c_id = best_cand['cand_id']
                score = best_cand['score']
                obj = best_cand['obj_prob']
                cls_p = best_cand['cls_prob']

                stage_dropped = "UNKNOWN"
                filter_rej_reason = None

                if best_iou < 0.50:
                    stage_dropped = "SUB_50_IOU_LOCALIZATION"
                elif score < 0.30:
                    if obj < 0.10 and cls_p >= 0.30:
                        stage_dropped = "DROPPED_LOW_OBJECTNESS"
                    elif cls_p < 0.30 and obj >= 0.10:
                        stage_dropped = "DROPPED_LOW_CLASSIFICATION"
                    else:
                        stage_dropped = "DROPPED_LOW_COMBINED_SCORE"
                elif c_id not in nms_kept_ids:
                    stage_dropped = "DROPPED_AT_NMS"
                else:
                    # In NMS but check filter
                    stage_dropped = "DROPPED_BY_ANATOMICAL_FILTER"
                    for r in rej:
                        if compute_iou(r['box'][:4], gt_box) >= 0.40:
                            filter_rej_reason = r['reason']
                            break

                record['bestMatchingCandidate'] = {
                    'box': [round(x, 1) for x in best_cand['box']],
                    'iou': round(best_iou, 4),
                    'score': round(score, 4),
                    'obj_prob': round(obj, 4),
                    'cls_prob': round(cls_p, 4),
                    'stride': best_cand['stride'],
                    'level': best_cand['level'],
                    'stageDropped': stage_dropped,
                    'filterRejectionReason': filter_rej_reason
                }
                record['primaryReason'] = stage_dropped
            else:
                record['bestMatchingCandidate'] = None
                record['primaryReason'] = "NO_CANDIDATE_ABOVE_FLOOR"

            all_truth_records.append(record)

    # Sanity check
    assert caught_count == 15, f"Expected 15 caught targets, got {caught_count}"
    assert missed_count == 38, f"Expected 38 missed targets, got {missed_count}"
    print(f"\nVerification:")
    print(f"  Total In-Scope Targets: {len(all_truth_records)}")
    print(f"  Caught: {caught_count} / 53 ({caught_count/53*100:.1f}%)")
    print(f"  Missed: {missed_count} / 53 ({missed_count/53*100:.1f}%)")

    # Aggregate missed breakdown
    reason_counts = {}
    for r in all_truth_records:
        if not r['isCaught']:
            r_str = r['primaryReason']
            reason_counts[r_str] = reason_counts.get(r_str, 0) + 1

    print("\nExact Miss Reason Distribution across 38 Misses:")
    for k, v in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {k:35s}: {v:2d} ({v/38*100:5.1f}%)")

    ledger_payload = {
        'modelIdentity': 'True Baseline cf3a2ba4 (Epoch 02)',
        'modelSha256': model_sha,
        'modelPath': str(TRUE_BASELINE_EPOCH02_PATH),
        'totalInScope': len(all_truth_records),
        'caughtCount': caught_count,
        'missedCount': missed_count,
        'reasonBreakdown': reason_counts,
        'truthRecords': all_truth_records
    }

    OUTPUT_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_LEDGER_PATH, 'w', encoding='utf-8') as f:
        json.dump(ledger_payload, f, indent=2)

    print(f"\nCanonical 38-miss detailed ledger saved to: {OUTPUT_LEDGER_PATH}")


if __name__ == '__main__':
    main()
