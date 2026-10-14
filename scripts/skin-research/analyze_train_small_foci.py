#!/usr/bin/env python3
"""Analyze small foci (<8px and 8-16px) in TRAIN dataset for YOLOX-S P2."""

import sys
import json
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from yolox_p2 import build_yolox_p2_model
from train_focused_local import yolo_batch
from safetensors.torch import load_file
from focal_objectness_loss import SigmoidFocalObjectnessLoss

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
EPOCH2_WEIGHTS = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/checkpoint-epoch-02-step-000496-1791911067067742300/model.safetensors'

def analyze():
    print("=== Analyzing Small Foci in TRAIN Dataset ===", flush=True)
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    train_rows = [r for r in data['rows'] if r.get('split') == 'train']
    print(f"Total TRAIN rows: {len(train_rows)}")

    # 1. Dataset-level lesion inventory
    all_lesions = []
    for r in train_rows:
        fam = r.get('family', r.get('source', 'unknown'))
        sha = r['sha256']
        for ann in r.get('annotations', []):
            if ann.get('classId') == 0:
                bx, by, ex, ey = ann['box']
                w = ex - bx
                h = ey - by
                max_dim = max(w, h)
                min_dim = min(w, h)
                area = w * h
                all_lesions.append({
                    'sha': sha,
                    'family': fam,
                    'box': [bx, by, ex, ey],
                    'w': w,
                    'h': h,
                    'max_dim': max_dim,
                    'min_dim': min_dim,
                    'area': area
                })

    tiny_lesions = [l for l in all_lesions if l['max_dim'] < 8]
    small_lesions = [l for l in all_lesions if 8 <= l['max_dim'] < 16]
    med_lesions = [l for l in all_lesions if 16 <= l['max_dim'] < 32]
    large_lesions = [l for l in all_lesions if l['max_dim'] >= 32]

    print(f"\n1. TRAIN Raw Lesions Breakdown (Total: {len(all_lesions)}):")
    print(f"   <8 px (Tiny):      {len(tiny_lesions)} ({len(tiny_lesions)/len(all_lesions)*100:.1f}%)")
    print(f"   8-16 px (Small):    {len(small_lesions)} ({len(small_lesions)/len(all_lesions)*100:.1f}%)")
    print(f"   16-32 px (Medium):  {len(med_lesions)} ({len(med_lesions)/len(all_lesions)*100:.1f}%)")
    print(f"   >=32 px (Large):    {len(large_lesions)} ({len(large_lesions)/len(all_lesions)*100:.1f}%)")

    tiny_groups = Counter([l['family'] for l in tiny_lesions])
    small_groups = Counter([l['family'] for l in small_lesions])

    # 2. Tile-level visibility
    masks, weights = build_hole_preserved_negative_masks(train_rows)
    tiles = acne_tiles_p2(train_rows, masks, training=True)
    print(f"\n2. Active Training Tiles: {len(tiles)}")

    tile_lesions = []
    for t_idx, t in enumerate(tiles):
        for b in t['boxes']:
            w = b[2] - b[0]
            h = b[3] - b[1]
            m = max(w, h)
            tile_lesions.append({
                'tile_idx': t_idx,
                'family': t['row'].get('family', 'unknown'),
                'max_dim': m,
                'w': w,
                'h': h,
                'box': b
            })

    tile_tiny = [l for l in tile_lesions if l['max_dim'] < 8]
    tile_small = [l for l in tile_lesions if 8 <= l['max_dim'] < 16]
    print(f"   In-tile <8 px occurrences:   {len(tile_tiny)}")
    print(f"   In-tile 8-16 px occurrences: {len(tile_small)}")

    # 3. Model GT assignment test with Epoch 2 weights
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    net.load_state_dict(load_file(str(EPOCH2_WEIGHTS)), strict=True)
    focal_loss = SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0)
    net.head.obj_focal_loss = focal_loss
    net.train()

    # Stride boundaries in 12240 anchors:
    # stride 4: 0..9216
    # stride 8: 9216..11520 (2304)
    # stride 16: 11520..12096 (576)
    # stride 32: 12096..12240 (144)
    stride_ranges = [
        (0, 9216, 4),
        (9216, 11520, 8),
        (11520, 12096, 16),
        (12096, 12240, 32)
    ]

    def get_stride(anchor_idx):
        for s_start, s_end, s_val in stride_ranges:
            if s_start <= anchor_idx < s_end:
                return s_val
        return -1

    # Track SimOTA assignment for each lesion size category
    simota_assignments = defaultdict(lambda: Counter())
    gt_assignment_counts = defaultdict(lambda: {'assigned': 0, 'unassigned': 0, 'total_anchors': 0})

    # Hook or intercept get_assignments in net.head
    original_get_assignments = net.head.get_assignments

    captured_assignments = []

    def wrapped_get_assignments(*args, **kwargs):
        res = original_get_assignments(*args, **kwargs)
        # res: (gt_matched_classes, fg_mask, pred_ious_this_matching, matched_gt_inds, num_fg_img)
        # args: (batch_idx, num_gt, gt_bboxes_per_image, gt_classes, bboxes_preds_per_image, expanded_strides, x_shifts, y_shifts, cls_preds, obj_preds)
        gt_bboxes = args[2]
        fg_mask = res[1]
        matched_gt_inds = res[3]
        captured_assignments.append({
            'gt_bboxes': gt_bboxes.detach().cpu(),
            'fg_mask': fg_mask.detach().cpu(),
            'matched_gt_inds': matched_gt_inds.detach().cpu()
        })
        return res

    net.head.get_assignments = wrapped_get_assignments

    # Run over all positive tiles (or first 200 positive tiles)
    pos_tiles = [t for t in tiles if len(t['boxes']) > 0]
    print(f"\n3. Evaluating SimOTA GT assignment across {len(pos_tiles)} positive training tiles...")

    batch_size = 8
    for i in range(0, min(len(pos_tiles), 200), batch_size):
        batch = pos_tiles[i:i+batch_size]
        x, y = yolo_batch(batch)
        known_list = []
        weight_list = []
        for item in batch:
            kt, wt = known_cells_p2(masks[item['row']['sha256']], weights[item['row']['sha256']], item['rect'], strides=(4, 8, 16, 32))
            known_list.append(kt)
            weight_list.append(wt)
        focal_loss.known = torch.cat(known_list, dim=0)
        focal_loss.boundary_weights = torch.cat(weight_list, dim=0)

        captured_assignments.clear()
        with torch.no_grad():
            _ = net(x, y)

        for cap in captured_assignments:
            gt_boxes = cap['gt_bboxes']
            fg_mask = cap['fg_mask']
            matched_gt = cap['matched_gt_inds']
            
            # Map assigned anchors to strides
            assigned_anchor_indices = torch.nonzero(fg_mask, as_tuple=True)[0]
            
            # For each GT box, see which anchors were assigned to it
            for gt_idx in range(len(gt_boxes)):
                gt_w = gt_boxes[gt_idx, 2].item()
                gt_h = gt_boxes[gt_idx, 3].item()
                m = max(gt_w, gt_h)
                cat = '<8px' if m < 8 else ('8-16px' if m < 16 else ('16-32px' if m < 32 else '>=32px'))

                # Find which anchors matched this gt_idx
                matching_anchors = assigned_anchor_indices[matched_gt == gt_idx]
                k_assigned = len(matching_anchors)
                
                if k_assigned > 0:
                    gt_assignment_counts[cat]['assigned'] += 1
                    gt_assignment_counts[cat]['total_anchors'] += k_assigned
                    for a_idx in matching_anchors:
                        st = get_stride(a_idx.item())
                        simota_assignments[cat][f'stride_{st}'] += 1
                else:
                    gt_assignment_counts[cat]['unassigned'] += 1

    print("\n4. SimOTA GT Box Assignment Success Rate by Lesion Size:")
    for cat in ['<8px', '8-16px', '16-32px', '>=32px']:
        counts = gt_assignment_counts[cat]
        tot = counts['assigned'] + counts['unassigned']
        if tot > 0:
            rate = counts['assigned'] / tot * 100
            avg_k = counts['total_anchors'] / max(1, counts['assigned'])
            print(f"   {cat:8s}: {counts['assigned']}/{tot} assigned ({rate:.1f}%), avg anchors/GT: {avg_k:.2f}")
            print(f"             Stride breakdown: {dict(simota_assignments[cat])}")

    output_report = {
        'totalTrainRows': len(train_rows),
        'totalTrainLesions': len(all_lesions),
        'rawBreakdown': {
            'tiny_less_8px': len(tiny_lesions),
            'small_8_to_16px': len(small_lesions),
            'medium_16_to_32px': len(med_lesions),
            'large_32_plus': len(large_lesions)
        },
        'tinySources': dict(tiny_groups),
        'smallSources': dict(small_groups.most_common(15)),
        'inTileBreakdown': {
            'tiny_less_8px': len(tile_tiny),
            'small_8_to_16px': len(tile_small)
        },
        'tilesWithTiny': len([t for t in tiles if any(max(b[2]-b[0], b[3]-b[1]) < 8 for b in t['boxes'])]),
        'tilesWithSmall': len([t for t in tiles if any(8 <= max(b[2]-b[0], b[3]-b[1]) < 16 for b in t['boxes'])]),
        'assignmentCounts': {k: dict(v) for k, v in gt_assignment_counts.items()},
        'strideDistribution': {k: dict(v) for k, v in simota_assignments.items()}
    }

    out_file = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/train_small_foci_analysis.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output_report, f, indent=2)
    print(f"\nSaved analysis to {out_file}")

if __name__ == '__main__':
    analyze()
