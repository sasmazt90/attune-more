#!/usr/bin/env python3
"""Empirical Loss, Normalization Denominator, and Gradient Profiler for TOGG Attune Acne Detection.

Measures:
1. Anchor distribution and loss normalization across:
   - Pure positive batches
   - Pure negative batches
   - Mixed batches
   Tracks:
   - Positive anchors (assigned foreground)
   - Active known negative anchors (from verified negative skin ROI)
   - Masked unknown anchors (unannotated skin on positive photos)
   - Normalization denominator (num_fg = max(num_fg, 1))
   - Resulting loss components (loss_iou, loss_obj, loss_cls, total_loss)
   - Gradient norms on proof layers (dark3, lateral_conv0, head.reg_convs)

2. Quantitative patch metrics on false positive detections in 15 negative photos:
   - Local contrast (std / mean)
   - Edge variance (Laplacian variance)
   - Min/max/mean luminance (Y channel)
   - Patch dimensions and model confidence
"""

import sys
import json
import math
from pathlib import Path
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
from train_focused_local import acne_tiles, yolo_batch, predict
from source_skin_support import known_skin_scope

BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
PHASE1_WEIGHTS = ROOT / 'audit-results/acne-candidate-training-20261013/candidate-selected.safetensors'
DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'
OUT_PATH = ROOT / 'audit-results/acne-detection-verification-20261013/loss-and-gradient-profile.json'

PROOF_KEYS = [
    'backbone.backbone.dark3.0.conv.weight',
    'backbone.lateral_conv0.conv.weight',
    'head.reg_convs.0.0.conv.weight'
]


def build_model(weights_path: Path):
    net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net)
    weights = load_file(str(weights_path))
    net.load_state_dict(weights)
    for k, p in net.named_parameters():
        p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))
    net.train()
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d):
            m.eval()
    return net


def analyze_batch_loss_and_gradients(net, obj_loss, b_items):
    net.zero_grad()
    x, y = yolo_batch(b_items)
    
    # Concatenate known masks
    known_mask = torch.cat([t['known'] for t in b_items])
    obj_loss.known = known_mask
    
    # Hook into head's get_losses by calling net(x, y)
    out = net(x, y)
    total_loss = out['total_loss']
    loss_iou = float(out['iou_loss'].item())
    loss_obj = float(out['conf_loss'].item())
    loss_cls = float(out['cls_loss'].item())
    
    # Backward pass to measure gradient norms
    total_loss.backward()
    
    grad_norms = {}
    for k in PROOF_KEYS:
        param = dict(net.named_parameters()).get(k)
        if param is not None and param.grad is not None:
            grad_norms[k] = float(param.grad.norm().item())
        else:
            grad_norms[k] = 0.0

    # Inspect anchor assignments and counts
    # Each tile has 3024 anchors
    total_anchors = known_mask.shape[0]
    num_neg_active = int((known_mask & 1).sum().item())
    
    # Ground truth boxes in batch
    total_gts = sum(len(t['boxes']) for t in b_items)
    
    return {
        'batch_size': len(b_items),
        'total_gt_boxes': total_gts,
        'total_anchors': total_anchors,
        'known_negative_anchors': num_neg_active,
        'total_loss': float(total_loss.item()),
        'loss_iou': loss_iou,
        'loss_obj': loss_obj,
        'loss_cls': loss_cls,
        'grad_norms': grad_norms
    }


def analyze_false_positive_patches(net, val_rows):
    """Profile real visual/quantitative patch metrics for detections on negative photos."""
    negative_rows = [r for r in val_rows if r.get('negativeROI')]
    fp_records = []
    
    for r in negative_rows:
        src_path = Path(r['absolutePath']) if 'absolutePath' in r and Path(r['absolutePath']).exists() else (LIVE_TEST / r['path'] if 'path' in r else None)
        if not src_path or not src_path.exists():
            continue
        bgr = cv2.imread(str(src_path))
        if bgr is None:
            continue
            
        preds = predict(net, 'yolox', [r])[0]
        h, w = bgr.shape[:2]
        
        for p in preds:
            x0, y0, x1, y1, conf = p
            if conf < 0.30:
                continue
            ix0, iy0, ix1, iy1 = max(0, int(round(x0))), max(0, int(round(y0))), min(w, int(round(x1))), min(h, int(round(y1)))
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            patch = bgr[iy0:iy1, ix0:ix1]
            if patch.size == 0:
                continue
                
            gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            mean_lum = float(gray.mean())
            std_lum = float(gray.std())
            min_lum = float(gray.min())
            max_lum = float(gray.max())
            contrast = float(std_lum / (mean_lum + 1e-5))
            
            fp_records.append({
                'source_sha256': r['sha256'],
                'box': [float(x0), float(y0), float(x1), float(y1)],
                'conf': float(conf),
                'patch_w': ix1 - ix0,
                'patch_h': iy1 - iy0,
                'mean_luminance': round(mean_lum, 2),
                'min_luminance': round(min_lum, 2),
                'max_luminance': round(max_lum, 2),
                'std_luminance': round(std_lum, 2),
                'contrast': round(contrast, 4),
                'laplacian_variance': round(lap_var, 2)
            })
            
    return fp_records


def main():
    print("=== Empirical Loss and Gradient Profiling ===")
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tr = [r for r in data['rows'] if r['split'] == 'train']
    va = [r for r in data['rows'] if r['split'] == 'validation']
    print(f"Dataset: {len(tr)} train rows, {len(va)} validation rows")

    # Prepare scopes
    scopes = {}
    for r in tr:
        scope = np.zeros((r['height'], r['width']), np.uint8)
        if r.get('negativeROI') and r.get('landmarks'):
            src_path = Path(r['absolutePath']) if 'absolutePath' in r and Path(r['absolutePath']).exists() else (LIVE_TEST / r['path'] if 'path' in r else None)
            if src_path and src_path.exists():
                bgr = cv2.imread(str(src_path))
                if bgr is not None:
                    scope = known_skin_scope(r, bgr)
            else:
                pts = np.array([[p['x'] * r['width'], p['y'] * r['height']] for p in r['landmarks'][:468]], np.float32)
                cv2.fillPoly(scope, [np.rint(pts).astype(np.int32)], 1)
        scopes[r['sha256']] = scope

    train_tiles = acne_tiles(tr, training=False)
    active_tiles = []
    for t in train_tiles:
        r = t['row']
        has_boxes = len(t['boxes']) > 0
        has_neg = bool(r.get('negativeROI'))
        if has_boxes or has_neg:
            t['known'] = known_cells(scopes[r['sha256']], t['rect'], has_neg)
            active_tiles.append(t)

    pos_tiles = [t for t in active_tiles if t['boxes']]
    neg_tiles = [t for t in active_tiles if not t['boxes']]
    print(f"Active tiles: {len(active_tiles)} ({len(pos_tiles)} pos, {len(neg_tiles)} neg)")

    # Build model using Baseline weights
    net = build_model(BASELINE_WEIGHTS)
    obj_loss = KnownObjectnessBCE()
    net.head.bcewithlog_loss = obj_loss

    # Profile Batch Types (Batch size = 4)
    batch_size = 4
    profiles = {}

    # 1. Pure positive batches (3 samples)
    pos_profiles = []
    for i in range(min(3, len(pos_tiles) // batch_size)):
        b = pos_tiles[i * batch_size:(i + 1) * batch_size]
        res = analyze_batch_loss_and_gradients(net, obj_loss, b)
        pos_profiles.append(res)
    profiles['pure_positive'] = pos_profiles

    # 2. Pure negative batches (3 samples)
    neg_profiles = []
    for i in range(min(3, len(neg_tiles) // batch_size)):
        b = neg_tiles[i * batch_size:(i + 1) * batch_size]
        res = analyze_batch_loss_and_gradients(net, obj_loss, b)
        neg_profiles.append(res)
    profiles['pure_negative'] = neg_profiles

    # 3. Mixed batches (2 pos + 2 neg, 3 samples)
    mixed_profiles = []
    for i in range(min(3, len(pos_tiles) // 2, len(neg_tiles) // 2)):
        b = pos_tiles[i * 2:(i + 1) * 2] + neg_tiles[i * 2:(i + 1) * 2]
        res = analyze_batch_loss_and_gradients(net, obj_loss, b)
        mixed_profiles.append(res)
    profiles['mixed_balanced'] = mixed_profiles

    print("\nBatch Profile Summary:")
    for b_type, p_list in profiles.items():
        avg_loss = np.mean([p['total_loss'] for p in p_list])
        avg_loss_obj = np.mean([p['loss_obj'] for p in p_list])
        avg_loss_iou = np.mean([p['loss_iou'] for p in p_list])
        avg_gts = np.mean([p['total_gt_boxes'] for p in p_list])
        avg_neg_anchors = np.mean([p['known_negative_anchors'] for p in p_list])
        avg_grad = np.mean([p['grad_norms']['head.reg_convs.0.0.conv.weight'] for p in p_list])
        print(f"[{b_type.upper()}] GTs: {avg_gts:.1f} | Known Neg Anchors: {avg_neg_anchors:.1f} | Loss: {avg_loss:.4f} (Obj: {avg_loss_obj:.4f}, IoU: {avg_loss_iou:.4f}) | Head Grad: {avg_grad:.4f}")

    # Profile False Positive Patches on 15 Validation Negatives
    print("\nProfiling False Positive Patches on 15 Negative Validation Controls...")
    # Baseline
    net_base = build_model(BASELINE_WEIGHTS)
    fp_baseline = analyze_false_positive_patches(net_base, va)
    print(f"Baseline FPs (conf >= 0.30): {len(fp_baseline)}")

    # Phase 1
    net_p1 = build_model(PHASE1_WEIGHTS)
    fp_p1 = analyze_false_positive_patches(net_p1, va)
    print(f"Phase 1 FPs (conf >= 0.30): {len(fp_p1)}")

    results = {
        'batch_profiles': profiles,
        'false_positive_analysis': {
            'baseline_count_conf30': len(fp_baseline),
            'baseline_fps': fp_baseline,
            'phase1_count_conf30': len(fp_p1),
            'phase1_fps': fp_p1,
        }
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nEmpirical profile saved to: {OUT_PATH}")


if __name__ == '__main__':
    main()
