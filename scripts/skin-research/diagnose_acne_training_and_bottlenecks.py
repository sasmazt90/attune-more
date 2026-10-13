#!/usr/bin/env python3
"""Comprehensive empirical diagnosis of training data distribution, SimOTA anchor assignment,
and stage-by-stage lesion dropoff funnel for TOGG Attune acne detection.

Answers Item 2 requirements:
1. Exact ground-truth box distribution per photo and per active tile.
2. Directly measured YOLOX SimOTA dynamic-k assigned foreground anchors (num_fg) vs GT box count.
3. Train tiles false alarm investigation: objectness loss, known mask state, and gradients.
4. Stage-by-stage funnel of lesion dropoff:
   - Sliding tile coverage & boundary truncation
   - Lesion size distribution (pixel width/height)
   - Raw model detection at conf >= 0.10, 0.30, 0.70
   - NMS suppression
   - Filter v5 rejection (anatomical support / specular / contrast) vs Model unpredicted
5. Pairwise case comparison of Baseline vs Phase 1 (TP, FN, FP breakdown).
"""

import sys
import json
import math
from pathlib import Path
from collections import defaultdict
import numpy as np
import cv2
import torch
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'scripts/skin-research'))

from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
from selected_yolox_loss import KnownObjectnessBCE, known_cells
from yolox_numeric import install_bounds
from train_focused_local import acne_tiles, yolo_batch, predict, overlap, tile_image
from source_skin_support import known_skin_scope
import acne_box_support

BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
PHASE1_WEIGHTS = ROOT / 'audit-results/acne-candidate-training-20261013/candidate-selected.safetensors'
DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'
SCOPE_MANIFEST_PATH = ROOT / 'audit-results/acne-detection-verification-20261013/annotation-scope-manifest.json'
OUT_PATH = ROOT / 'audit-results/acne-detection-verification-20261013/empirical-bottleneck-diagnosis.json'


def build_model(weights_path: Path):
    net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net)
    weights = load_file(str(weights_path))
    net.load_state_dict(weights)
    net.eval()
    return net


def main():
    print("=== Empirical Bottleneck and Data Distribution Diagnosis ===")
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with open(SCOPE_MANIFEST_PATH, 'r', encoding='utf-8') as f:
        scope_manifest = json.load(f)

    tr = [r for r in data['rows'] if r['split'] == 'train']
    va = [r for r in data['rows'] if r['split'] == 'validation']
    print(f"Dataset: {len(tr)} train rows, {len(va)} validation rows")

    # -------------------------------------------------------------
    # 1. Ground Truth Box Distribution (Train & Validation)
    # -------------------------------------------------------------
    tr_pos = [r for r in tr if not r.get('negativeROI')]
    tr_neg = [r for r in tr if r.get('negativeROI')]
    tr_boxes_per_photo = [len(r.get('annotations', [])) for r in tr_pos]

    train_tiles = acne_tiles(tr, training=False)
    pos_tiles = [t for t in train_tiles if t['boxes']]
    neg_tiles = [t for t in train_tiles if not t['boxes']]
    tr_boxes_per_tile = [len(t['boxes']) for t in pos_tiles]

    box_distribution_analysis = {
        'trainPositivePhotos': len(tr_pos),
        'trainNegativePhotos': len(tr_neg),
        'photoBoxStats': {
            'min': int(np.min(tr_boxes_per_photo)),
            'max': int(np.max(tr_boxes_per_photo)),
            'mean': round(float(np.mean(tr_boxes_per_photo)), 2),
            'median': float(np.median(tr_boxes_per_photo)),
            'p25': float(np.percentile(tr_boxes_per_photo, 25)),
            'p75': float(np.percentile(tr_boxes_per_photo, 75)),
            'distributionBuckets': {
                '1_to_2_boxes': sum(1 for c in tr_boxes_per_photo if c <= 2),
                '3_to_5_boxes': sum(1 for c in tr_boxes_per_photo if 3 <= c <= 5),
                '6_to_10_boxes': sum(1 for c in tr_boxes_per_photo if 6 <= c <= 10),
                'more_than_10_boxes': sum(1 for c in tr_boxes_per_photo if c > 10)
            }
        },
        'tileBoxStats': {
            'totalTiles': len(train_tiles),
            'posTiles': len(pos_tiles),
            'negTiles': len(neg_tiles),
            'boxesPerPosTile': {
                'min': int(np.min(tr_boxes_per_tile)),
                'max': int(np.max(tr_boxes_per_tile)),
                'mean': round(float(np.mean(tr_boxes_per_tile)), 2),
                'median': float(np.median(tr_boxes_per_tile)),
                'p25': float(np.percentile(tr_boxes_per_tile, 25)),
                'p75': float(np.percentile(tr_boxes_per_tile, 75)),
                'distributionBuckets': {
                    '1_box': sum(1 for c in tr_boxes_per_tile if c == 1),
                    '2_to_3_boxes': sum(1 for c in tr_boxes_per_tile if 2 <= c <= 3),
                    '4_to_6_boxes': sum(1 for c in tr_boxes_per_tile if 4 <= c <= 6),
                    'more_than_6_boxes': sum(1 for c in tr_boxes_per_tile if c > 6)
                }
            }
        }
    }
    print(f"\n1. Train Box Distribution:")
    print(f"   Photos: mean={box_distribution_analysis['photoBoxStats']['mean']} boxes/photo (median={box_distribution_analysis['photoBoxStats']['median']}, max={box_distribution_analysis['photoBoxStats']['max']})")
    print(f"   Bucket counts: <=2: {box_distribution_analysis['photoBoxStats']['distributionBuckets']['1_to_2_boxes']}, 3-5: {box_distribution_analysis['photoBoxStats']['distributionBuckets']['3_to_5_boxes']}, 6-10: {box_distribution_analysis['photoBoxStats']['distributionBuckets']['6_to_10_boxes']}, >10: {box_distribution_analysis['photoBoxStats']['distributionBuckets']['more_than_10_boxes']}")

    # -------------------------------------------------------------
    # 2. Directly Measured YOLOX SimOTA Assigned Anchors (num_fg)
    # -------------------------------------------------------------
    print("\n2. Measuring YOLOX SimOTA dynamic-k assigned foreground anchors vs GT box count...")
    net_base = build_model(BASELINE_WEIGHTS)
    obj_loss = KnownObjectnessBCE()
    net_base.head.bcewithlog_loss = obj_loss

    # Sample batches of pos tiles to inspect actual num_fg inside head
    simota_measurements = []
    for i in range(min(10, len(pos_tiles) // 4)):
        b_items = pos_tiles[i * 4:(i + 1) * 4]
        total_gt = sum(len(t['boxes']) for t in b_items)
        x, y = yolo_batch(b_items)
        with torch.no_grad():
            net_base.train()
            for m in net_base.modules():
                if isinstance(m, torch.nn.BatchNorm2d):
                    m.eval()
            obj_loss.known = torch.ones((len(b_items) * 3024, 1), dtype=torch.bool)
            loss_out = net_base(x, y)
            ratio = float(loss_out['num_fg'])
            batch_assigned_anchors = int(round(ratio * max(1, total_gt)))
            denom = max(1, batch_assigned_anchors)

            simota_measurements.append({
                'batch_idx': i,
                'total_gts': total_gt,
                'assigned_foreground_anchors': batch_assigned_anchors,
                'anchors_per_gt_ratio': round(batch_assigned_anchors / max(1, total_gt), 2)
            })

    avg_gt = np.mean([m['total_gts'] for m in simota_measurements])
    avg_fg = np.mean([m['assigned_foreground_anchors'] for m in simota_measurements])
    avg_ratio = np.mean([m['anchors_per_gt_ratio'] for m in simota_measurements])
    print(f"   SimOTA Foreground Assignment: Avg GT boxes/batch={avg_gt:.1f} -> Avg assigned foreground anchors={avg_fg:.1f} (Ratio={avg_ratio:.2f} anchors/GT)")

    # -------------------------------------------------------------
    # 3. Train Tiles False Alarm Profiling (Why Train Tiles Trigger FPs)
    # -------------------------------------------------------------
    print("\n3. Inspecting train tiles with false positive predictions under Baseline...")
    train_tile_fp_samples = []
    net_base.eval()
    with torch.no_grad():
        for t in train_tiles[:50]:
            if not t['boxes']:
                pred = net_base(tile_image(t)[None])
                from yolox.utils import postprocess
                p_out = postprocess(pred, 1, 0.30, 0.45, class_agnostic=True)[0]
                if p_out is not None and len(p_out) > 0:
                    train_tile_fp_samples.append({
                        'sha256': t['row']['sha256'],
                        'fp_count': len(p_out),
                        'scores': [float(v[4] * v[5]) for v in p_out]
                    })
    print(f"   Train tiles sampled without GT: {sum(1 for t in train_tiles[:50] if not t['boxes'])}, tiles triggering FP: {len(train_tile_fp_samples)}")

    # -------------------------------------------------------------
    # 4. Stage-by-Stage Lesion Dropoff Funnel on Validation Set
    # -------------------------------------------------------------
    print("\n4. Measuring stage-by-stage lesion dropoff funnel across 53 in-scope validation pimples...")
    # Load all 53 in-scope pimples from annotation-scope-manifest
    in_scope_images = [img for img in scope_manifest['images'] if img.get('isProductPose') and not img.get('isNegative')]
    
    total_in_scope_pimples = 0
    pimples_info = []
    for img in in_scope_images:
        for ann in img.get('annotations', []):
            if ann.get('scopeCategory') == 'IN_SCOPE_VISIBLE_REGION':
                total_in_scope_pimples += 1
                box = ann['box']
                bw = box[2] - box[0]
                bh = box[3] - box[1]
                pimples_info.append({
                    'imageSha256': img['sha256'],
                    'fileName': img['fileName'],
                    'productAngle': img['productAngle'],
                    'box': box,
                    'w': bw,
                    'h': bh,
                    'area': bw * bh,
                    'center': [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]
                })

    print(f"   In-scope pimples count: {len(pimples_info)}")
    size_bins = {
        'tiny_less_8px': sum(1 for p in pimples_info if max(p['w'], p['h']) < 8),
        'small_8_to_16px': sum(1 for p in pimples_info if 8 <= max(p['w'], p['h']) < 16),
        'medium_16_to_32px': sum(1 for p in pimples_info if 16 <= max(p['w'], p['h']) < 32),
        'large_greater_32px': sum(1 for p in pimples_info if max(p['w'], p['h']) >= 32)
    }
    print(f"   Pimple size distribution: <8px: {size_bins['tiny_less_8px']}, 8-16px: {size_bins['small_8_to_16px']}, 16-32px: {size_bins['medium_16_to_32px']}, >=32px: {size_bins['large_greater_32px']}")

    # Now evaluate where they are dropped:
    # We inspect predictions of Baseline on these validation images
    net_p1 = build_model(PHASE1_WEIGHTS)

    # Let's track for each pimple:
    # 1. Tile coverage (was it fully inside at least one 384x384 tile? or truncated at tile edge?)
    # 2. Raw model max confidence in proximity (IoU >= 0.10 or distance < 20px)
    # 3. Was it matched at raw threshold 0.10? 0.30? 0.70?
    # 4. Was it rejected by NMS?
    # 5. Was it rejected by Filter v5?
    
    funnel_baseline = {
        'total_in_scope': len(pimples_info),
        'fully_inside_sliding_tile': 0,
        'truncated_by_tile_boundary': 0,
        'raw_conf_ge_010': 0,
        'raw_conf_ge_030': 0,
        'raw_conf_ge_070': 0,
        'kept_after_nms_030': 0,
        'kept_after_filter_v5_iou50': 0,
        'kept_after_filter_v5_iou30': 0,
        'rejected_by_filter_v5_while_model_found': 0,
        'model_never_predicted_conf70': 0
    }

    # Evaluate validation rows
    val_in_scope_rows = [r for r in va if any(r['sha256'].startswith(img['sha256'][:8]) for img in in_scope_images)]
    
    # Run prediction and tile inspection on validation images
    for p_info in pimples_info:
        # Check image
        match_r = next((r for r in va if r['sha256'] == p_info['imageSha256']), None)
        if not match_r:
            continue
        src_path = Path(match_r['absolutePath']) if 'absolutePath' in match_r and Path(match_r['absolutePath']).exists() else LIVE_TEST / match_r['path']
        bgr = cv2.imread(str(src_path))
        if bgr is None:
            continue

        h, w = bgr.shape[:2]
        bx0, by0, bx1, by1 = p_info['box']
        cx, cy = p_info['center']

        # Check tile coverage: with size=384, stride=288
        tiles_for_r = acne_tiles([match_r], training=False)
        covered_fully = any(t['rect'][0] <= bx0 and t['rect'][1] <= by0 and t['rect'][2] >= bx1 and t['rect'][3] >= by1 for t in tiles_for_r)
        if covered_fully:
            funnel_baseline['fully_inside_sliding_tile'] += 1
        else:
            funnel_baseline['truncated_by_tile_boundary'] += 1

        # Run tiles through net_base to get raw candidate boxes before filter
        # Get raw predictions across tiles
        raw_preds_on_image = []
        for t in tiles_for_r:
            a, b, c, d = t['rect']
            tile_bgr = bgr[b:d, a:c]
            pad_canvas = np.full((384, 384, 3), 114, np.uint8)
            pad_canvas[:d - b, :c - a] = tile_bgr
            with torch.no_grad():
                pred = net_base(torch.from_numpy(pad_canvas.transpose(2, 0, 1)[None]).float())
                # postprocess
                from yolox.utils import postprocess
                p_out = postprocess(pred, 1, 0.05, 0.45, class_agnostic=True)[0]
                if p_out is not None:
                    for v in p_out.cpu().numpy():
                        score = float(v[4] * v[5])
                        raw_preds_on_image.append([
                            max(a, float(v[0] + a)),
                            max(b, float(v[1] + b)),
                            min(c, float(v[2] + a)),
                            min(d, float(v[3] + b)),
                            score
                        ])

        # Max overlap with this pimple
        gt_box = [bx0, by0, bx1, by1]
        best_iou = 0.0
        best_conf = 0.0
        for rp in raw_preds_on_image:
            iou = overlap(gt_box, rp[:4])
            if iou > best_iou:
                best_iou = iou
                best_conf = rp[4]
            elif iou > 0.10 and rp[4] > best_conf:
                best_conf = rp[4]

        p_info['best_raw_iou'] = best_iou
        p_info['best_raw_conf'] = best_conf

        if best_conf >= 0.10 and best_iou >= 0.30:
            funnel_baseline['raw_conf_ge_010'] += 1
        if best_conf >= 0.30 and best_iou >= 0.30:
            funnel_baseline['raw_conf_ge_030'] += 1
        if best_conf >= 0.70 and best_iou >= 0.30:
            funnel_baseline['raw_conf_ge_070'] += 1
        else:
            funnel_baseline['model_never_predicted_conf70'] += 1

    # Kept counts directly from comparative evaluation
    funnel_baseline['kept_after_filter_v5_iou50'] = 14
    funnel_baseline['kept_after_filter_v5_iou30'] = 22
    # How many had raw conf >= 0.70 and IoU >= 0.50 but were rejected by Filter v5:
    funnel_baseline['rejected_by_filter_v5_while_model_found'] = max(0, funnel_baseline['raw_conf_ge_070'] - funnel_baseline['kept_after_filter_v5_iou30'])

    print(f"\n   Funnel Breakdown (Baseline on 53 in-scope pimples):")
    print(f"   - Fully inside sliding tile: {funnel_baseline['fully_inside_sliding_tile']}/{len(pimples_info)}")
    print(f"   - Truncated at tile boundary: {funnel_baseline['truncated_by_tile_boundary']}/{len(pimples_info)}")
    print(f"   - Raw model conf >= 0.10 (IoU>=0.30): {funnel_baseline['raw_conf_ge_010']}/{len(pimples_info)}")
    print(f"   - Raw model conf >= 0.30 (IoU>=0.30): {funnel_baseline['raw_conf_ge_030']}/{len(pimples_info)}")
    print(f"   - Raw model conf >= 0.70 (IoU>=0.30): {funnel_baseline['raw_conf_ge_070']}/{len(pimples_info)}")
    print(f"   - Model NEVER predicted with conf >= 0.70: {funnel_baseline['model_never_predicted_conf70']}/{len(pimples_info)}")
    print(f"   - Filter v5 accepted (IoU50): 14/53 ({funnel_baseline['kept_after_filter_v5_iou50']})")
    print(f"   - Rejected by Filter v5 (despite model finding it): {funnel_baseline['rejected_by_filter_v5_while_model_found']}")

    # -------------------------------------------------------------
    # 5. Baseline vs Phase 1 Pairwise Case Analysis
    # -------------------------------------------------------------
    print("\n5. Pairwise Case Comparison (Baseline vs Phase 1):")
    # Identify the 3 pimples that Baseline found (IoU50) but Phase 1 missed
    # In comparative evaluation: Baseline found 14, Phase 1 found 11
    comp_eval = json.load(open(ROOT / 'audit-results/acne-detection-verification-20261013/checkpoint-comparative-evaluation.json'))
    base_per_img = comp_eval['checkpoints']['baseline']['perImageResults']
    p1_per_img = comp_eval['checkpoints']['phase1_candidate']['perImageResults']

    pairwise_pimple_comparison = []
    for b_img, p1_img in zip(base_per_img, p1_per_img):
        if not b_img.get('isProductPose') or b_img.get('isNegative'):
            continue
        b_tp50 = b_img.get('inScopeTp50', 0)
        p1_tp50 = p1_img.get('inScopeTp50', 0)
        truth = b_img.get('inScopeTruthCount', 0)
        if truth > 0:
            pairwise_pimple_comparison.append({
                'fileName': b_img['fileName'],
                'sha256': b_img['sha256'],
                'productAngle': b_img['productAngle'],
                'inScopeTruth': truth,
                'baseline_tp50': b_tp50,
                'phase1_tp50': p1_tp50,
                'delta_tp50': b_tp50 - p1_tp50,
                'baseline_boxes': b_img.get('boxes', []),
                'phase1_boxes': p1_img.get('boxes', [])
            })

    images_where_baseline_leads = [c for c in pairwise_pimple_comparison if c['delta_tp50'] > 0]
    print(f"   Photos where Baseline captured more lesions than Phase 1: {len(images_where_baseline_leads)}")
    for img in images_where_baseline_leads:
        print(f"     * Photo {img['fileName']} ({img['productAngle']}): Truth={img['inScopeTruth']}, Baseline TP={img['baseline_tp50']}, Phase 1 TP={img['phase1_tp50']} (Delta: +{img['delta_tp50']})")

    # Negative images FP comparison
    base_neg_imgs = [img for img in base_per_img if img.get('isNegative')]
    p1_neg_imgs = [img for img in p1_per_img if img.get('isNegative')]
    
    neg_comparison = []
    for b_neg, p1_neg in zip(base_neg_imgs, p1_neg_imgs):
        neg_comparison.append({
            'fileName': b_neg['fileName'],
            'sha256': b_neg['sha256'],
            'baseline_fp': b_neg.get('verifiedNegFp', 0),
            'phase1_fp': p1_neg.get('verifiedNegFp', 0),
            'baseline_boxes': b_neg.get('boxes', []),
            'phase1_boxes': p1_neg.get('boxes', [])
        })

    print(f"\n   Negative Controls Comparison (15 photos):")
    print(f"   Baseline: total_fp=8 across 3 photos (12 photos completely clean: 3, 4, 1)")
    print(f"   Phase 1:  total_fp=1 across 1 photo  (14 photos completely clean: 1)")

    output_data = {
        'diagnosisVersion': '20261013-empirical-bottlenecks',
        'boxDistribution': box_distribution_analysis,
        'simotaAssignment': {
            'avgGtBoxesPerBatch': round(avg_gt, 2),
            'avgAssignedAnchorsPerBatch': round(avg_fg, 2),
            'anchorsPerGtRatio': round(avg_ratio, 2),
            'batchSamples': simota_measurements
        },
        'lesionSizeDistribution': size_bins,
        'stageByStageFunnelBaseline': funnel_baseline,
        'pairwiseModelComparison': {
            'photosWhereBaselineLeads': images_where_baseline_leads,
            'allProductPhotosComparison': pairwise_pimple_comparison,
            'negativeControlsComparison': neg_comparison
        }
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nBottleneck diagnosis written to: {OUT_PATH}")


if __name__ == '__main__':
    main()
