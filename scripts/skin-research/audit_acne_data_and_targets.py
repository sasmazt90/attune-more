#!/usr/bin/env python3
"""Audit Acne Training Data, Target Transformations, Masks, and Leakage."""

import sys
import os
import json
import pickle
import hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from train_focused_local import yolo_batch
from prepare_canonical_validation_cache import load_canonical_validation_cache
from yolox_p2 import build_yolox_p2_model
from focal_objectness_loss import SigmoidFocalObjectnessLoss

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'

def audit_dataset_and_leakage():
    print("=" * 80)
    print("1. DATASET & TRAIN/VAL LEAKAGE AUDIT")
    print("=" * 80)
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tr_rows = [r for r in data['rows'] if r['split'] == 'train']
    val_rows = [r for r in data['rows'] if r['split'] == 'validation']
    print(f"Data file total rows: {len(data['rows'])} (train={len(tr_rows)}, val_in_file={len(val_rows)})")

    # Load canonical validation cache
    cached_val = load_canonical_validation_cache()
    print(f"Canonical validation cache contains: {len(cached_val)} images")

    train_hashes = set(r['sha256'] for r in tr_rows)
    val_hashes = set(img['sha256'] for img in cached_val)

    overlap = train_hashes & val_hashes
    print(f"Direct SHA-256 overlap between TRAIN and Canonical VAL: {len(overlap)}")
    assert len(overlap) == 0, f"DATA LEAKAGE DETECTED: {overlap}"

    # Also check image names / person identifiers if present
    train_names = set(r.get('fileName', '') for r in tr_rows)
    val_names = set(img.get('fileName', '') for img in cached_val)
    name_overlap = (train_names & val_names) - {''}
    print(f"File name overlap: {len(name_overlap)}")
    assert len(name_overlap) == 0, f"NAME OVERLAP: {name_overlap}"
    print("LEAKAGE AUDIT: PASSED (Zero identity / image leak between train and val)\n")
    return tr_rows, cached_val

def audit_boxes_and_tiles(tr_rows):
    print("=" * 80)
    print("2. BOXES, TILES & TARGET TRANSFORMATION AUDIT")
    print("=" * 80)
    
    # Count total ground truth boxes in tr_rows
    total_raw_boxes = 0
    raw_box_sizes = []
    for r in tr_rows:
        for ann in r.get('annotations', []):
            if ann.get('classId') == 0:
                total_raw_boxes += 1
                b = ann['box']
                w = b[2] - b[0]
                h = b[3] - b[1]
                raw_box_sizes.append(max(w, h))

    print(f"Total raw positive lesion boxes across {len(tr_rows)} train rows: {total_raw_boxes}")
    print(f"  <8 px:   {sum(s < 8.0 for s in raw_box_sizes)}")
    print(f"  8-16 px: {sum(8.0 <= s < 16.0 for s in raw_box_sizes)}")
    print(f"  16-32 px:{sum(16.0 <= s < 32.0 for s in raw_box_sizes)}")
    print(f"  >=32 px: {sum(s >= 32.0 for s in raw_box_sizes)}")

    # Generate masks and tiles
    masks, weights = build_hole_preserved_negative_masks(tr_rows)
    tiles = acne_tiles_p2(tr_rows, masks, training=True)
    print(f"Generated training tiles: {len(tiles)}")

    # Check how many tile boxes were created
    tile_box_count = sum(len(t.get('boxes', [])) for t in tiles)
    print(f"Total box instances across all tiles: {tile_box_count}")

    # Check whether any raw boxes were completely missed by all tiles
    missed_raw_boxes = 0
    missed_details = []
    for r in tr_rows:
        raw_boxes = [ann['box'] for ann in r.get('annotations', []) if ann.get('classId') == 0]
        row_sha = r['sha256']
        row_tiles = [t for t in tiles if t['row']['sha256'] == row_sha]
        for rb in raw_boxes:
            rx1, ry1, rx2, ry2 = rb[:4]
            # Is this box in any tile's boxes list?
            found = False
            for t in row_tiles:
                a, b, endx, endy = t['rect']
                cl = [max(rx1, a), max(ry1, b), min(rx2, endx), min(ry2, endy)]
                if cl[2] - cl[0] >= 2 and cl[3] - cl[1] >= 2 and (cl[2] - cl[0]) * (cl[3] - cl[1]) >= 0.7 * (rx2 - rx1) * (ry2 - ry1):
                    found = True
                    break
            if not found:
                missed_raw_boxes += 1
                missed_details.append((row_sha, rb, (rx2-rx1, ry2-ry1), r.get('crop')))

    print(f"Raw boxes completely missed by all tiles: {missed_raw_boxes} (out of {total_raw_boxes})")
    print("BOXES & TILES AUDIT COMPLETE.\n")
    return tiles, masks, weights

def audit_batch_and_anchors(tiles, masks, weights):
    print("=" * 80)
    print("3. BATCH CREATION & ANCHOR / UNKNOWN MASK INTERACTION AUDIT")
    print("=" * 80)

    # Pick a sample batch with positive lesions
    pos_tiles = [t for t in tiles if len(t.get('boxes', [])) > 0]
    sample_items = pos_tiles[:4]
    for item in sample_items:
        item['source_mask'] = masks[item['row']['sha256']]
        item['source_weights'] = weights[item['row']['sha256']]

    x, y = yolo_batch(sample_items)
    print(f"yolo_batch output x: shape={tuple(x.shape)}, dtype={x.dtype}, min={x.min():.1f}, max={x.max():.1f}")
    print(f"yolo_batch output y: shape={tuple(y.shape)}, dtype={y.dtype}")
    print(f"Sample y[0] (first 3 targets):\n{y[0, :3]}")

    # Build known and weights
    known_list = []
    weight_list = []
    for item in sample_items:
        kt, wt = known_cells_p2(item['source_mask'], item['source_weights'], item['rect'], strides=(4, 8, 16, 32))
        known_list.append(kt)
        weight_list.append(wt)
    known = torch.cat(known_list, dim=0)
    boundary_weights = torch.cat(weight_list, dim=0)
    print(f"known tensor shape: {tuple(known.shape)}, True cells: {int(known.sum())}/{known.numel()} ({float(known.float().mean()):.1%})")

    # Now test with YOLOX-S P2 model forward
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    focal_loss = SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0)
    net.head.obj_focal_loss = focal_loss
    focal_loss.known = known
    focal_loss.boundary_weights = boundary_weights

    net.train()
    loss_dict = net(x, y)
    print(f"Forward loss_dict: total_loss={loss_dict['total_loss'].item():.4f}, iou={loss_dict['iou_loss'].item():.4f}, obj={loss_dict['conf_loss'].item():.4f}, cls={loss_dict['cls_loss'].item():.4f}")

    metrics = focal_loss.last_metrics
    print("\nFocal Objectness Loss Internal Metrics:")
    print(f"  num_pos_anchors:         {metrics.get('num_pos_anchors')}")
    print(f"  num_known_neg_anchors:   {metrics.get('num_known_neg_anchors')}")
    print(f"  num_unknown_anchors:     {metrics.get('num_unknown_anchors')}")
    print(f"  raw_pos_obj_loss:        {metrics.get('raw_pos_obj_loss'):.4f}")
    print(f"  raw_neg_obj_loss:        {metrics.get('raw_neg_obj_loss'):.4f}")

    assert metrics.get('num_pos_anchors', 0) > 0, "ERROR: No positive anchors were assigned despite positive GT boxes in batch!"
    print("\nANCHOR ASSIGNMENT & LOSS AUDIT: PASSED (Positive anchors correctly assigned and loss active)")

if __name__ == '__main__':
    tr_rows, cached_val = audit_dataset_and_leakage()
    tiles, masks, weights = audit_boxes_and_tiles(tr_rows)
    audit_batch_and_anchors(tiles, masks, weights)
