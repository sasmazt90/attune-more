#!/usr/bin/env python3
"""Investigate Real Objective vs Classification vs Localization on All 38 Missed Lesions."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

import torch
import numpy as np
from yolox.models.yolo_head import bboxes_iou

from model_identity import load_verified_model, TRUE_BASELINE_EPOCH02_PATH, TRUE_BASELINE_EPOCH02_SHA
from prepare_canonical_validation_cache import load_canonical_validation_cache
from acne_preprocessing import extract_tile_bgr, tile_to_tensor, TILE_SIZE, STRIDE, PAD_VAL

def main():
    print("=" * 80)
    print("AUDITING REAL CLASSIFICATION, LOCALIZATION, AND OBJECTNESS ON MISSED LESIONS")
    print("=" * 80)

    net, sha = load_verified_model(TRUE_BASELINE_EPOCH02_PATH, TRUE_BASELINE_EPOCH02_SHA)
    net.eval()

    cached = load_canonical_validation_cache()
    pos_items = [item for item in cached if item.get('isProductPose') and not item.get('isNegative') and len(item.get('truth', [])) > 0]

    high_cls_misses = 0
    good_iou_misses = 0
    total_misses = 0
    miss_records = []

    for item in pos_items:
        fn = item['fileName']
        bgr = item['bgr']
        H, W = bgr.shape[:2]
        truth = item['truth']
        truth_cats = item['truthCategories']
        in_scope_indices = [i for i, c in enumerate(truth_cats) if c == 'IN_SCOPE_VISIBLE_REGION']

        for t_idx in in_scope_indices:
            gt_box = truth[t_idx]
            gx0, gy0, gx1, gy1 = gt_box
            gw, gh = gx1 - gx0, gy1 - gy0
            gcx, gcy = (gx0 + gx1) / 2.0, (gy0 + gy1) / 2.0
            cat = 'tiny' if max(gw, gh) < 8 else 'small' if max(gw, gh) < 16 else 'medium'

            # Crop 384x384 centered on lesion
            x0 = int(round(gcx - 192))
            y0 = int(round(gcy - 192))
            tile = extract_tile_bgr(bgr, (x0, y0, x0 + 384, y0 + 384), 384, 114)
            inp = tile_to_tensor(tile).unsqueeze(0)

            with torch.no_grad():
                out = net(inp)[0]  # [12240, 6]

            # In tile coordinates, lesion center is at:
            tcx = gcx - x0
            tcy = gcy - y0

            dists = torch.hypot(out[:, 0] - tcx, out[:, 1] - tcy)
            # Find anchors within 16 px of lesion center
            near_mask = dists < 16.0
            if not near_mask.any():
                continue

            near_out = out[near_mask]
            near_dists = dists[near_mask]

            # Compute IoU of all near anchors with GT in tile coordinates
            gt_t = torch.tensor([[tcx, tcy, gw, gh]])
            pred_boxes = near_out[:, :4]
            ious = bboxes_iou(gt_t, pred_boxes, False)[0]

            obj_scores = near_out[:, 4]
            cls_scores = near_out[:, 5]
            total_scores = (obj_scores * cls_scores).sqrt()

            # Find anchor with highest classification score
            best_cls_idx = torch.argmax(cls_scores)
            # Find anchor with highest IoU
            best_iou_idx = torch.argmax(ious)
            # Find anchor with highest total score
            best_tot_idx = torch.argmax(total_scores)

            tot_sc = total_scores[best_tot_idx].item()
            best_c = cls_scores[best_cls_idx].item()
            best_o = obj_scores[best_cls_idx].item()
            best_i = ious[best_cls_idx].item()
            max_i = ious[best_iou_idx].item()

            is_miss = (tot_sc < 0.30 or best_i < 0.50)
            if is_miss:
                total_misses += 1
                if best_c >= 0.30:
                    high_cls_misses += 1
                if max_i >= 0.50:
                    good_iou_misses += 1

                miss_records.append({
                    'fileName': fn,
                    'gt_size': (round(gw, 1), round(gh, 1)),
                    'cat': cat,
                    'best_cls': round(best_c, 3),
                    'obj_at_best_cls': round(best_o, 4),
                    'iou_at_best_cls': round(best_i, 3),
                    'max_iou_nearby': round(max_i, 3),
                    'tot_score': round(tot_sc, 4),
                })

    print(f"Total in-scope misses audited: {total_misses}")
    print(f"Misses with CLS >= 0.30 nearby: {high_cls_misses} / {total_misses} ({high_cls_misses/max(total_misses,1)*100:.1f}%)")
    print(f"Misses with IoU >= 0.50 nearby: {good_iou_misses} / {total_misses} ({good_iou_misses/max(total_misses,1)*100:.1f}%)")
    print("\nSample missed targets breakdown:")
    for r in miss_records[:15]:
        print(f"  {r['fileName']} [{r['cat']} {r['gt_size']}]: best_cls={r['best_cls']} | obj={r['obj_at_best_cls']} | iou={r['iou_at_best_cls']} (max_iou={r['max_iou_nearby']}) | tot_sc={r['tot_score']}")

if __name__ == '__main__':
    main()
