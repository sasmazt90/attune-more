#!/usr/bin/env python3
"""Exhaustive Pre-Threshold and Pipeline Funnel Miss Diagnosis for True Baseline cf3a2ba4.

Examines every missed target across all stages:
1. Karo coverage & coordinate mapping check.
2. Pre-threshold raw anchor inspection (best geometric IoU, raw obj, raw cls, total score).
3. Score threshold check (low objectness vs low classification).
4. Multi-tile / candidate NMS suppression check.
5. Anatomical Filter v5 rejection check with exact reason.
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
    load_verified_model,
    generate_evaluation_receipt
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

OUTPUT_PATH = ROOT / "audit-results/acne-candidate-p2-focal-20261013/true_baseline_cf3a2ba4_miss_audit.json"


def extract_raw_predictions_with_tile_index(net, bgr, points, tile_size=384, stride=288, min_score=0.001):
    """Run sliding tile inference, preserving source tile coordinates and tile indices."""
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
    tile_data_list = []

    for t_idx, rect in enumerate(tile_rects):
        a, b, endx, endy = rect
        tile_bgr = extract_tile_bgr(bgr, rect, tile_size=tile_size, pad_val=114)
        t_tensor = tile_to_tensor(tile_bgr).unsqueeze(0)

        with torch.no_grad():
            out = net(t_tensor)[0]  # [12240, 6] -> [cx, cy, w, h, obj_prob, cls_prob]

        tile_data_list.append({
            'tile_idx': t_idx,
            'rect': rect,
            'out': out.cpu(),
            'tile_bgr': tile_bgr
        })

        scores = out[:, 4] * out[:, 5]
        mask = scores >= min_score
        if mask.any():
            sel_out = out[mask]
            sel_scores = scores[mask]
            for row, sc in zip(sel_out.numpy(), sel_scores.numpy()):
                cx, cy, bw, bh = row[:4]
                x0 = max(0.0, float(cx - bw / 2.0 + a))
                y0 = max(0.0, float(cy - bh / 2.0 + b))
                x1 = min(float(w), float(cx + bw / 2.0 + a))
                y1 = min(float(h), float(cy + bh / 2.0 + b))
                raw_candidates.append({
                    'box': [x0, y0, x1, y1],
                    'score': float(sc),
                    'obj_prob': float(row[4]),
                    'cls_prob': float(row[5]),
                    'tile_idx': t_idx,
                    'tile_rect': rect,
                    'tile_local_box': [float(cx - bw / 2.0), float(cy - bh / 2.0), float(cx + bw / 2.0), float(cy + bh / 2.0)]
                })

    return raw_candidates, tile_data_list, tile_rects


def inspect_prethreshold_tile_overlap(tile_data, gt_box, tile_rect) -> Dict[str, Any]:
    """Examine all 12,240 anchors of a tile to find highest IoU and pre-threshold logits."""
    a, b, endx, endy = tile_rect
    gx0, gy0, gx1, gy1 = gt_box
    # GT box in tile-local coords
    local_gt = [gx0 - a, gy0 - b, gx1 - a, gy1 - b]
    gt_area = max(0.0, local_gt[2] - local_gt[0]) * max(0.0, local_gt[3] - local_gt[1])

    out = tile_data['out']  # [12240, 6]
    cx = out[:, 0]
    cy = out[:, 1]
    w = out[:, 2]
    h = out[:, 3]
    obj_p = out[:, 4]
    cls_p = out[:, 5]
    total_sc = obj_p * cls_p

    px0 = cx - w / 2.0
    py0 = cy - h / 2.0
    px1 = cx + w / 2.0
    py1 = cy + h / 2.0

    # Vectorized IoU
    ix0 = torch.clamp(px0, min=local_gt[0])
    iy0 = torch.clamp(py0, min=local_gt[1])
    ix1 = torch.clamp(px1, max=local_gt[2])
    iy1 = torch.clamp(py1, max=local_gt[3])
    inter_w = torch.clamp(ix1 - ix0, min=0.0)
    inter_h = torch.clamp(iy1 - iy0, min=0.0)
    inter = inter_w * inter_h
    pred_area = (px1 - px0) * (py1 - py0)
    union = pred_area + gt_area - inter
    ious = torch.where(union > 0, inter / union, torch.zeros_like(union))

    best_iou_val, best_idx = torch.max(ious, dim=0)
    best_idx = int(best_idx.item())
    best_iou_val = float(best_iou_val.item())

    # Stride of best anchor
    stride = 4 if best_idx < 9216 else (8 if best_idx < 11520 else (16 if best_idx < 12096 else 32))

    return {
        'best_iou': best_iou_val,
        'best_anchor_idx': best_idx,
        'best_anchor_stride': stride,
        'best_anchor_pred_local_box': [float(px0[best_idx]), float(py0[best_idx]), float(px1[best_idx]), float(py1[best_idx])],
        'best_anchor_pred_source_box': [float(px0[best_idx] + a), float(py0[best_idx] + b), float(px1[best_idx] + a), float(py1[best_idx] + b)],
        'best_anchor_obj_prob': float(obj_p[best_idx].item()),
        'best_anchor_cls_prob': float(cls_p[best_idx].item()),
        'best_anchor_total_score': float(total_sc[best_idx].item()),
    }


def main():
    print("=" * 80)
    print("DIAGNOSIS OF TRUE BASELINE cf3a2ba4 - EXHAUSTIVE MISS ANALYSIS")
    print("=" * 80)

    # 1. Load true baseline with hash enforcement
    net, model_sha = load_verified_model(
        TRUE_BASELINE_EPOCH02_PATH,
        expected_sha=TRUE_BASELINE_EPOCH02_SHA
    )
    print(f"Loaded verified baseline model: {model_sha}")

    # 2. Load validation cache
    cached_images = load_canonical_validation_cache()
    print(f"Loaded {len(cached_images)} cached validation images.")

    # 3. Filter to in-scope product pose images
    prod_pose_images = [img for img in cached_images if img['isProductPose'] and any(c == 'IN_SCOPE_VISIBLE_REGION' for c in img['truthCategories'])]
    print(f"Evaluating across {len(prod_pose_images)} in-scope product pose validation images.")

    total_in_scope_truth = 0
    all_truth_entries = []

    for img in prod_pose_images:
        for idx, (box, cat) in enumerate(zip(img['truth'], img['truthCategories'])):
            if cat == 'IN_SCOPE_VISIBLE_REGION':
                total_in_scope_truth += 1
                bw = box[2] - box[0]
                bh = box[3] - box[1]
                dim = max(bw, bh)
                size_grp = 'tiny' if dim < 8 else ('small' if dim < 16 else 'medium')
                all_truth_entries.append({
                    'fileName': img['fileName'],
                    'truthIndex': idx,
                    'box': box,
                    'width': bw,
                    'height': bh,
                    'maxDimPx': dim,
                    'sizeGroup': size_grp,
                    'imgData': img
                })

    assert total_in_scope_truth == 53, f"Expected exactly 53 in-scope truth targets, got {total_in_scope_truth}"
    print(f"Total in-scope truth targets: {total_in_scope_truth}")

    # 4. Run pipeline on each image and track every stage
    caught_targets = []
    missed_targets = []
    neg_fps = 0
    neg_photos_with_fp = 0

    # Also evaluate negative photos for exact verification
    neg_images = [img for img in cached_images if img['isNegative']]
    print(f"Evaluating false positives across {len(neg_images)} negative control photos...")
    for img in neg_images:
        bgr = img['bgr']
        points = img['landmarks']
        if not points:
            continue
        raw_cands, _, _ = extract_raw_predictions_with_tile_index(net, bgr, points, min_score=0.30)
        if raw_cands:
            boxes_t = torch.tensor([c['box'] for c in raw_cands], dtype=torch.float32)
            scores_t = torch.tensor([c['score'] for c in raw_cands], dtype=torch.float32)
            keep_idx = torch_nms(boxes_t, scores_t, 0.30)
            nms_cands = [raw_cands[i] for i in keep_idx.numpy()]
        else:
            nms_cands = []
        raw_nms_boxes = [c['box'] + [c['score']] for c in nms_cands]
        vis_regs = img['allowedRegions'] if img['productAngle'] is not None else None
        acc, rej = acne_box_support.accepted_boxes(
            raw_nms_boxes, img['envelopes'], img['skin_support'], img['hair'], img['exclusion'],
            img['sha256'], img['scale'], img['origin'], visible_regions=vis_regs,
            landmarks=points, source_shape=(img['height'], img['width'])
        )
        acc_boxes = [b for blist in acc.values() for b in blist]
        neg_fps += len(acc_boxes)
        if acc_boxes:
            neg_photos_with_fp += 1

    print(f"Baseline Negative FP: {neg_fps} across {neg_photos_with_fp}/{len(neg_images)} photos ({neg_fps/len(neg_images):.2f} FP/photo)")
    assert neg_fps == 3, f"Expected exactly 3 baseline false positives on negative photos, got {neg_fps}"

    # Now evaluate positive images
    per_image_diagnostics = {}

    for img in prod_pose_images:
        fn = img['fileName']
        bgr = img['bgr']
        points = img['landmarks']
        truth_boxes = img['truth']
        truth_cats = img['truthCategories']
        in_scope_indices = [i for i, c in enumerate(truth_cats) if c == 'IN_SCOPE_VISIBLE_REGION']

        # Stage 1: Raw candidates with min_score=0.001
        raw_cands, tile_data_list, tile_rects = extract_raw_predictions_with_tile_index(net, bgr, points, min_score=0.001)

        # Stage 2: Conf threshold 0.30
        conf30_cands = [c for c in raw_cands if c['score'] >= 0.30]

        # Stage 3: NMS 0.30
        if conf30_cands:
            boxes_t = torch.tensor([c['box'] for c in conf30_cands], dtype=torch.float32)
            scores_t = torch.tensor([c['score'] for c in conf30_cands], dtype=torch.float32)
            keep_idx = torch_nms(boxes_t, scores_t, 0.30)
            nms30_cands = [conf30_cands[i] for i in keep_idx.numpy()]
            # Keep set of dropped indices
            dropped_nms_cands = [conf30_cands[i] for i in range(len(conf30_cands)) if i not in set(keep_idx.numpy().tolist())]
        else:
            nms30_cands = []
            dropped_nms_cands = []

        # Stage 4: Anatomical Filter v5
        raw_nms_boxes = [c['box'] + [c['score']] for c in nms30_cands]
        vis_regs = img['allowedRegions'] if img['productAngle'] is not None else None
        acc, rej = acne_box_support.accepted_boxes(
            raw_nms_boxes, img['envelopes'], img['skin_support'], img['hair'], img['exclusion'],
            img['sha256'], img['scale'], img['origin'], visible_regions=vis_regs,
            landmarks=points, source_shape=(img['height'], img['width'])
        )
        accepted_boxes = [b for blist in acc.values() for b in blist]

        # Match final accepted boxes to truth at IoU 0.50
        matched_truth_indices_50, matches_50, _, _, _ = match_predictions_to_truth(truth_boxes, accepted_boxes, 0.50)
        caught_in_scope = set(matched_truth_indices_50).intersection(set(in_scope_indices))

        per_image_diagnostics[fn] = {
            'totalInScope': len(in_scope_indices),
            'caughtInScope': len(caught_in_scope),
            'rawCount': len(raw_cands),
            'conf30Count': len(conf30_cands),
            'nms30Count': len(nms30_cands),
            'acceptedCount': len(accepted_boxes),
            'rejectedCount': len(rej),
            'rejections': rej,
            'tile_data_list': tile_data_list,
            'tile_rects': tile_rects,
            'raw_cands': raw_cands,
            'conf30_cands': conf30_cands,
            'nms30_cands': nms30_cands,
            'dropped_nms_cands': dropped_nms_cands,
            'accepted_boxes': accepted_boxes,
            'caught_indices': list(caught_in_scope)
        }

    # Now audit every in-scope target
    target_audit_records = []
    cause_counts = {}

    for entry in all_truth_entries:
        fn = entry['fileName']
        t_idx = entry['truthIndex']
        gt_box = entry['box']
        diag = per_image_diagnostics[fn]

        is_caught = t_idx in diag['caught_indices']
        entry['isCaught'] = is_caught

        if is_caught:
            caught_targets.append(entry)
            entry['status'] = 'CAUGHT_IOU50'
            target_audit_records.append(entry)
            continue

        # Target was MISSED: Perform exhaustive root-cause diagnosis
        missed_targets.append(entry)

        # 1. Check tile coverage
        covering_tiles = []
        for t_data in diag['tile_data_list']:
            rect = t_data['rect']
            # Target is inside if center is inside, or at least 70% area
            tx0, ty0, tx1, ty1 = gt_box
            cx_gt = (tx0 + tx1) / 2.0
            cy_gt = (ty0 + ty1) / 2.0
            if rect[0] <= cx_gt <= rect[2] and rect[1] <= cy_gt <= rect[3]:
                covering_tiles.append(t_data)

        entry['coveringTileCount'] = len(covering_tiles)
        if not covering_tiles:
            entry['missRootCause'] = 'TILE_COVERAGE_MISS'
            cause_counts['TILE_COVERAGE_MISS'] = cause_counts.get('TILE_COVERAGE_MISS', 0) + 1
            target_audit_records.append(entry)
            continue

        # 2. Inspect pre-threshold raw anchor overlap across covering tiles
        best_overlap_record = None
        for t_data in covering_tiles:
            ov = inspect_prethreshold_tile_overlap(t_data, gt_box, t_data['rect'])
            if best_overlap_record is None or ov['best_iou'] > best_overlap_record['best_iou']:
                best_overlap_record = ov

        entry['preThresholdBestIoU'] = best_overlap_record['best_iou']
        entry['preThresholdBestAnchor'] = best_overlap_record

        # 3. Check if there were any raw candidates with IoU >= 0.50 with this target
        iou50_raw = []
        for c in diag['raw_cands']:
            iou = compute_iou(c['box'], gt_box)
            if iou >= 0.50:
                iou50_raw.append((iou, c))
        iou50_raw.sort(key=lambda x: x[0], reverse=True)

        if iou50_raw:
            best_raw_match_iou, best_raw_cand = iou50_raw[0]
            entry['rawCandidateMatchingIoU'] = best_raw_match_iou
            entry['rawCandidateScore'] = best_raw_cand['score']
            entry['rawCandidateObjProb'] = best_raw_cand['obj_prob']
            entry['rawCandidateClsProb'] = best_raw_cand['cls_prob']

            if best_raw_cand['score'] < 0.30:
                # Score was below 0.30
                if best_raw_cand['obj_prob'] < 0.30 and best_raw_cand['cls_prob'] >= 0.30:
                    cause = 'LOW_OBJECTNESS'
                elif best_raw_cand['cls_prob'] < 0.30 and best_raw_cand['obj_prob'] >= 0.30:
                    cause = 'LOW_CLASSIFICATION'
                else:
                    cause = 'LOW_CONFIDENCE_BOTH'
                entry['missRootCause'] = cause
                cause_counts[cause] = cause_counts.get(cause, 0) + 1
            else:
                # Score was >= 0.30: Why didn't it make it to accepted?
                # Did it survive NMS?
                in_nms = any(compute_iou(c['box'], gt_box) >= 0.50 for c in diag['nms30_cands'])
                if not in_nms:
                    cause = 'DROPPED_AT_NMS'
                    entry['missRootCause'] = cause
                    cause_counts[cause] = cause_counts.get(cause, 0) + 1
                else:
                    # Dropped by anatomical filter: find reason
                    filter_reason = 'UNKNOWN_FILTER_REASON'
                    for r in diag['rejections']:
                        if compute_iou(r['box'][:4], gt_box) >= 0.40:
                            filter_reason = r['reason']
                            break
                    cause = f'REJECTED_BY_FILTER_{filter_reason}'
                    entry['missRootCause'] = cause
                    entry['filterRejectionReason'] = filter_reason
                    cause_counts[cause] = cause_counts.get(cause, 0) + 1
        else:
            # No raw candidate achieved IoU >= 0.50
            if best_overlap_record['best_iou'] >= 0.30:
                cause = 'POOR_LOCALIZATION_IOU_UNDER_50'
            else:
                cause = 'NO_RAW_PROPOSAL_NEAR_TARGET'
            entry['missRootCause'] = cause
            cause_counts[cause] = cause_counts.get(cause, 0) + 1

        target_audit_records.append(entry)

    # Sanity checks
    assert len(caught_targets) == 15, f"Expected exactly 15 caught targets, got {len(caught_targets)}"
    assert len(missed_targets) == 38, f"Expected exactly 38 missed targets (53 - 15), got {len(missed_targets)}"

    print(f"\nExact Validation Count:")
    print(f"  Caught: {len(caught_targets)} / 53 ({len(caught_targets)/53*100:.1f}%)")
    print(f"  Missed: {len(missed_targets)} / 53 ({len(missed_targets)/53*100:.1f}%)")

    # Size breakdown of caught vs missed
    print("\nSize Group Breakdown:")
    for grp in ['tiny', 'small', 'medium']:
        c_grp = sum(1 for t in caught_targets if t['sizeGroup'] == grp)
        m_grp = sum(1 for t in missed_targets if t['sizeGroup'] == grp)
        tot_grp = c_grp + m_grp
        print(f"  {grp:8s}: {c_grp}/{tot_grp} caught ({c_grp/tot_grp*100:.1f}%) | {m_grp} missed")

    print("\nRoot Cause Breakdown for 38 Misses:")
    for cause, cnt in sorted(cause_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cause:35s}: {cnt:2d} ({cnt/38*100:5.1f}%)")

    # Clean serializable records for JSON
    serializable_records = []
    for r in target_audit_records:
        rec = {k: v for k, v in r.items() if k != 'imgData'}
        serializable_records.append(rec)

    audit_summary = {
        'modelIdentity': 'True Baseline cf3a2ba4 (Epoch 02)',
        'modelSha256': TRUE_BASELINE_EPOCH02_SHA,
        'modelPath': str(TRUE_BASELINE_EPOCH02_PATH),
        'datasetVersion': 'train-data-engineering-reviewed-20261013 (Canonical Val Cache)',
        'preprocessingVersion': PREPROCESSING_VERSION,
        'confThreshold': 0.30,
        'nmsThreshold': 0.30,
        'totalInScopeTargets': 53,
        'totalCaughtTargets': len(caught_targets),
        'totalMissedTargets': len(missed_targets),
        'iou50Recall': f"{len(caught_targets)}/53 ({len(caught_targets)/53*100:.1f}%)",
        'falsePositivesAcross15Negatives': neg_fps,
        'falsePositivesPerPhoto': neg_fps / 15.0,
        'sizeBreakdown': {
            'tiny_less_8px': f"{sum(1 for t in caught_targets if t['sizeGroup'] == 'tiny')}/7",
            'small_8_to_16px': f"{sum(1 for t in caught_targets if t['sizeGroup'] == 'small')}/31",
            'medium_16_to_32px': f"{sum(1 for t in caught_targets if t['sizeGroup'] == 'medium')}/15",
        },
        'rootCauseSummary': cause_counts,
        'missedTargetDetails': serializable_records
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(audit_summary, f, indent=2)

    print(f"\nExhaustive miss audit written to: {OUTPUT_PATH}")


if __name__ == '__main__':
    main()
