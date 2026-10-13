#!/usr/bin/env python3
"""Diagnose Item 4: Detection Pipeline Funnel (Raw -> Conf -> NMS -> Product/Anatomical Filter) and Miss Analysis."""

import sys
import json
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from acne_metrics import match_predictions_to_truth
from evaluate_all_checkpoints_side_by_side import torch_nms
from prepare_canonical_validation_cache import load_canonical_validation_cache
from train_p2_focal_trial import extract_p2_predictions_fast

import importlib.util
_spec = importlib.util.spec_from_file_location("acne_box_support", str(ROOT / 'services/core-api/acne_box_support.py'))
acne_box_support = importlib.util.module_from_spec(_spec)
sys.modules['acne_box_support'] = acne_box_support
_spec.loader.exec_module(acne_box_support)

TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-focal-20261013'
SELECTED_PATH = TRIAL_DIR / 'candidate-selected.safetensors'


def diagnose_misses():
    print("=== ITEM 4 DIAGNOSTIC: 4-Stage Funnel & Miss Breakdown ===", flush=True)

    # 1. Load winning model
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    net.load_state_dict(load_file(str(SELECTED_PATH)), strict=True)
    net.eval()

    cached_images = load_canonical_validation_cache()
    print(f"Loaded {len(cached_images)} validation images from canonical cache.", flush=True)

    # Run inference with very low threshold (0.01) to capture raw model output
    print("Running sliding tile inference with threshold 0.01 to capture raw predictions...", flush=True)
    per_image_raw = []
    for item in cached_images:
        bgr = item['bgr']
        points = item['landmarks']
        if not points:
            per_image_raw.append([])
        else:
            raw_cands = extract_p2_predictions_fast(net, bgr, points, min_score=0.01)
            per_image_raw.append(raw_cands)

    thresholds = [0.30, 0.50, 0.70]
    funnel_results = {}

    for conf_thre in thresholds:
        print(f"\nEvaluating Detection Funnel at Confidence {conf_thre:.2f}...", flush=True)

        stage_counts = {
            'stage1_raw': {'total': 0, 'tp50': 0, 'tiny': {'total': 0, 'tp50': 0}, 'small': {'total': 0, 'tp50': 0}, 'medium': {'total': 0, 'tp50': 0}},
            'stage2_conf': {'total': 0, 'tp50': 0, 'tiny': {'total': 0, 'tp50': 0}, 'small': {'total': 0, 'tp50': 0}, 'medium': {'total': 0, 'tp50': 0}},
            'stage3_nms': {'total': 0, 'tp50': 0, 'tiny': {'total': 0, 'tp50': 0}, 'small': {'total': 0, 'tp50': 0}, 'medium': {'total': 0, 'tp50': 0}},
            'stage4_accepted': {'total': 0, 'tp50': 0, 'tiny': {'total': 0, 'tp50': 0}, 'small': {'total': 0, 'tp50': 0}, 'medium': {'total': 0, 'tp50': 0}}
        }

        missed_lesions_details = []

        for item, raw_cands in zip(cached_images, per_image_raw):
            points = item['landmarks']
            is_prod_pose = item['isProductPose']
            truth_boxes = item['truth']
            truth_categories = item['truthCategories']
            sha = item['sha256']
            fn = item['fileName']

            if not is_prod_pose or not points:
                continue

            in_scope_indices = [i for i, cat in enumerate(truth_categories) if cat == 'IN_SCOPE_VISIBLE_REGION']
            if not in_scope_indices:
                continue

            # Stage 1: Raw candidates (min_score=0.01)
            raw_boxes = [c['box'] + [c['score']] for c in raw_cands]
            matched1_50, _, _, _, _ = match_predictions_to_truth(truth_boxes, raw_boxes, 0.50)
            s1_matched_in_scope = set(matched1_50).intersection(set(in_scope_indices))

            # Stage 2: Conf filtered
            conf_cands = [c for c in raw_cands if c['score'] >= conf_thre]
            conf_boxes = [c['box'] + [c['score']] for c in conf_cands]
            matched2_50, _, _, _, _ = match_predictions_to_truth(truth_boxes, conf_boxes, 0.50)
            s2_matched_in_scope = set(matched2_50).intersection(set(in_scope_indices))

            # Stage 3: NMS
            if conf_cands:
                boxes_t = torch.tensor([c['box'] for c in conf_cands], dtype=torch.float32)
                scores_t = torch.tensor([c['score'] for c in conf_cands], dtype=torch.float32)
                keep_idx = torch_nms(boxes_t, scores_t, 0.30)
                nms_cands = [conf_cands[i] for i in keep_idx.numpy()]
            else:
                nms_cands = []
            nms_boxes = [c['box'] + [c['score']] for c in nms_cands]
            matched3_50, _, _, _, _ = match_predictions_to_truth(truth_boxes, nms_boxes, 0.50)
            s3_matched_in_scope = set(matched3_50).intersection(set(in_scope_indices))

            # Stage 4: Anatomical & Product filter
            if nms_cands:
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
            else:
                accepted_boxes = []
            matched4_50, _, _, _, _ = match_predictions_to_truth(truth_boxes, accepted_boxes, 0.50)
            s4_matched_in_scope = set(matched4_50).intersection(set(in_scope_indices))

            # Record per-stage and size breakdown
            for idx in in_scope_indices:
                bx = truth_boxes[idx]
                dim = max(bx[2] - bx[0], bx[3] - bx[1])
                grp = 'tiny' if dim < 8 else ('small' if dim < 16 else 'medium')

                stage_counts['stage1_raw']['total'] += 1
                stage_counts['stage1_raw'][grp]['total'] += 1
                if idx in s1_matched_in_scope:
                    stage_counts['stage1_raw']['tp50'] += 1
                    stage_counts['stage1_raw'][grp]['tp50'] += 1

                stage_counts['stage2_conf']['total'] += 1
                stage_counts['stage2_conf'][grp]['total'] += 1
                if idx in s2_matched_in_scope:
                    stage_counts['stage2_conf']['tp50'] += 1
                    stage_counts['stage2_conf'][grp]['tp50'] += 1

                stage_counts['stage3_nms']['total'] += 1
                stage_counts['stage3_nms'][grp]['total'] += 1
                if idx in s3_matched_in_scope:
                    stage_counts['stage3_nms']['tp50'] += 1
                    stage_counts['stage3_nms'][grp]['tp50'] += 1

                stage_counts['stage4_accepted']['total'] += 1
                stage_counts['stage4_accepted'][grp]['total'] += 1
                if idx in s4_matched_in_scope:
                    stage_counts['stage4_accepted']['tp50'] += 1
                    stage_counts['stage4_accepted'][grp]['tp50'] += 1
                else:
                    # Diagnose where this lesion was dropped
                    drop_stage = 'dropped_at_raw' if idx not in s1_matched_in_scope else (
                        'dropped_at_confidence' if idx not in s2_matched_in_scope else (
                            'dropped_at_nms' if idx not in s3_matched_in_scope else 'dropped_at_filter'
                        )
                    )
                    missed_lesions_details.append({
                        'fileName': fn,
                        'sha256': sha,
                        'truthIndex': idx,
                        'box': bx,
                        'maxDimPx': round(dim, 1),
                        'sizeGroup': grp,
                        'droppedStage': drop_stage
                    })

        funnel_results[str(conf_thre)] = {
            'stageCounts': stage_counts,
            'missedCount': len(missed_lesions_details),
            'missedDetails': missed_lesions_details
        }

        print(f"  Stage 1 (Raw min_score=0.01)    : {stage_counts['stage1_raw']['tp50']}/{stage_counts['stage1_raw']['total']} ({stage_counts['stage1_raw']['tp50']/53:.1%}) | tiny: {stage_counts['stage1_raw']['tiny']['tp50']}/7, small: {stage_counts['stage1_raw']['small']['tp50']}/31, med: {stage_counts['stage1_raw']['medium']['tp50']}/15")
        print(f"  Stage 2 (Conf >= {conf_thre:.2f})       : {stage_counts['stage2_conf']['tp50']}/{stage_counts['stage2_conf']['total']} ({stage_counts['stage2_conf']['tp50']/53:.1%}) | tiny: {stage_counts['stage2_conf']['tiny']['tp50']}/7, small: {stage_counts['stage2_conf']['small']['tp50']}/31, med: {stage_counts['stage2_conf']['medium']['tp50']}/15")
        print(f"  Stage 3 (Post-NMS IoU 0.30)     : {stage_counts['stage3_nms']['tp50']}/{stage_counts['stage3_nms']['total']} ({stage_counts['stage3_nms']['tp50']/53:.1%}) | tiny: {stage_counts['stage3_nms']['tiny']['tp50']}/7, small: {stage_counts['stage3_nms']['small']['tp50']}/31, med: {stage_counts['stage3_nms']['medium']['tp50']}/15")
        print(f"  Stage 4 (Anatomical Filter v5)  : {stage_counts['stage4_accepted']['tp50']}/{stage_counts['stage4_accepted']['total']} ({stage_counts['stage4_accepted']['tp50']/53:.1%}) | tiny: {stage_counts['stage4_accepted']['tiny']['tp50']}/7, small: {stage_counts['stage4_accepted']['small']['tp50']}/31, med: {stage_counts['stage4_accepted']['medium']['tp50']}/15")

    out_file = TRIAL_DIR / 'detection_pipeline_funnel_and_miss_breakdown.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(funnel_results, f, indent=2)
    print(f"\nPipeline funnel and miss diagnosis saved to: {out_file}", flush=True)


if __name__ == '__main__':
    diagnose_misses()
