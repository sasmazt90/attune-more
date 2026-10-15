#!/usr/bin/env python3
"""Empirical Measurement of SimOTA Assignment, Normalized Loss Components, and Positive vs Negative Gradients on Reproducible TRAIN Batches.

Directives:
1. Retract analytical 60x single-anchor claim; measure the REAL loss calculation:
   - pos_obj_loss = sum(focal_pos) / num_fg
   - neg_obj_loss = (sum(focal_neg * boundary_weights) / num_known_neg) * w_neg (w_neg=20.0)
   - UNKNOWN mask zeroing out unverified skin.
2. Measure across a fixed, reproducible mini-batch group (batch_size=4, 5 consecutive batches):
   - num_fg (positive anchors assigned by SimOTA)
   - num_known_neg (known negative anchors in clean facial mask)
   - num_unknown (masked background anchors receiving 0 loss)
   - Normalized positive objectness loss vs normalized negative objectness loss
   - IoU (localization) loss and classification loss
   - Gradient norms of pos_obj_loss vs neg_obj_loss on the detector head and backbone
   - Cosine similarity between pos and neg gradient vectors
   - Distribution of obj, cls, and obj*cls on the assigned positive anchors.
"""

import sys
import os
import json
import math
from pathlib import Path
import cv2
import numpy as np
import torch
import torch.nn as nn
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from negative_mask_builder import build_hole_preserved_negative_masks, known_cells_p2
from train_p2_scale_guided import select_training_tiles

TRAIN_MANIFEST_PATH = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014/training_tiles_manifest.json'
TRAIN_DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014'

STEP0_PATH = TRIAL_DIR / 'checkpoint-epoch-00-step-000000-1792014463030016700/model.safetensors'
EPOCH4_PATH = TRIAL_DIR / 'checkpoint-epoch-04-step-000828-1792020809525886000/model.safetensors'


def run_empirical_loss_measurement():
    print("=" * 80)
    print("EMPIRICAL MEASUREMENT OF SIMOTA LOSS AND GRADIENTS ON TRAIN DATA")
    print("=" * 80)

    # 1. Load strict TRAIN split rows (132 photos, 1235 annotations)
    with open(TRAIN_DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    train_rows = [r for r in data['rows'] if r.get('split') == 'train']
    print(f"Loaded {len(train_rows)} strict TRAIN rows.")

    # 2. Build hole preserved negative masks & select tiles
    masks, weights = build_hole_preserved_negative_masks(train_rows)
    focused_tiles = select_training_tiles(train_rows, masks)

    # Preload images into memory
    img_cache = {}
    for r in train_rows:
        sha = r['sha256']
        if sha not in img_cache:
            path = r.get('absolutePath') or str(LIVE_TEST / r['path'])
            bgr = cv2.imread(path)
            assert bgr is not None, f"Could not read: {path}"
            img_cache[sha] = bgr

    for t in focused_tiles:
        t['preloaded_bgr'] = img_cache[t['row']['sha256']]
        t['clean_mask'] = masks[t['row']['sha256']]
        t['mask_weight'] = weights[t['row']['sha256']]

    print(f"Prepared {len(focused_tiles)} training tiles.")

    # Load Step 0 model
    net = build_yolox_p2_model()
    net.load_state_dict(load_file(str(STEP0_PATH)), strict=True)
    focal_loss = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
    net.head.obj_focal_loss = focal_loss
    net.train()
    # Keep BN in eval mode per contract
    for m in net.modules():
        if isinstance(m, nn.BatchNorm2d):
            m.eval()

    # Mini-batch configuration
    batch_size = 4
    num_batches = 5
    torch.manual_seed(20261014)
    np.random.seed(20261014)

    # Prepare batches
    batches = []
    for b_idx in range(num_batches):
        b_tiles = focused_tiles[b_idx * batch_size : (b_idx + 1) * batch_size]
        batches.append(b_tiles)

    print(f"\nEvaluating {num_batches} reproducible mini-batches (batch_size={batch_size}):")

    batch_measurements = []

    for b_idx, b_tiles in enumerate(batches):
        images = []
        targets = torch.zeros((len(b_tiles), max(max(len(t['boxes']) for t in b_tiles), 1), 5), dtype=torch.float32)

        for bi, t in enumerate(b_tiles):
            full_bgr = t['preloaded_bgr']
            a, b, endx, endy = t['rect']
            tile = np.full((384, 384, 3), 114, dtype=np.uint8)
            crop = full_bgr[b:endy, a:endx]
            tile[:crop.shape[0], :crop.shape[1]] = crop
            images.append(torch.from_numpy(tile.transpose(2, 0, 1)).float())
            for bj, (x0, y0, x1, y1) in enumerate(t['boxes']):
                targets[bi, bj] = torch.tensor([0, (x0 + x1) / 2.0, (y0 + y1) / 2.0, x1 - x0, y1 - y0])

        x = torch.stack(images)
        y = targets

        known_list = []
        weight_list = []
        for item in b_tiles:
            kt, wt = known_cells_p2(item['clean_mask'], item['mask_weight'], item['rect'], strides=(4, 8, 16, 32))
            known_list.append(kt)
            weight_list.append(wt)

        focal_loss.known = torch.cat(known_list, dim=0)
        focal_loss.boundary_weights = torch.cat(weight_list, dim=0)

        # Forward pass to get head outputs and SimOTA assignment
        net.zero_grad()
        loss_dict = net(x, y)

        # Extract metrics logged by SigmoidFocalObjectnessLoss
        fl_metrics = focal_loss.last_metrics
        num_fg = fl_metrics['num_fg']
        num_pos = fl_metrics['num_pos_anchors']
        num_known_neg = fl_metrics['num_known_neg_anchors']
        num_unknown = fl_metrics['num_unknown_anchors']

        norm_pos_loss = fl_metrics['norm_pos_obj_loss']
        norm_neg_loss = fl_metrics['norm_neg_obj_loss']

        loss_iou = loss_dict['iou_loss'].item()
        loss_cls = loss_dict['cls_loss'].item()
        loss_obj = loss_dict['conf_loss'].item()
        total_loss = loss_dict['total_loss'].item()

        # Compute gradient norms for pos_obj_loss vs neg_obj_loss on head.obj_preds
        obj_params = [p for name, p in net.head.named_parameters() if 'obj_preds' in name and p.requires_grad]

        norm_pos_tensor = net.head.last_norm_pos
        norm_neg_tensor = net.head.last_norm_neg

        # Gradient of positive objectness loss
        grad_pos_tensors = torch.autograd.grad(norm_pos_tensor, obj_params, retain_graph=True, allow_unused=True)
        grad_pos_vec = torch.cat([g.flatten() for g in grad_pos_tensors if g is not None])
        grad_pos_norm = float(grad_pos_vec.norm(2).item())

        # Gradient of negative objectness loss
        grad_neg_tensors = torch.autograd.grad(norm_neg_tensor, obj_params, retain_graph=False, allow_unused=True)
        grad_neg_vec = torch.cat([g.flatten() for g in grad_neg_tensors if g is not None])
        grad_neg_norm = float(grad_neg_vec.norm(2).item())

        # Cosine similarity between positive and negative gradients
        cos_sim = float((grad_pos_vec.dot(grad_neg_vec) / (max(grad_pos_norm, 1e-8) * max(grad_neg_norm, 1e-8))).item())

        # Measure positive anchor predictions (obj, cls, score)
        with torch.no_grad():
            is_pos = net.head.last_is_pos.squeeze(1)
            is_neg = net.head.last_is_neg.squeeze(1)
            obj_p = torch.sigmoid(net.head.last_obj_preds.view(-1))
            cls_p = torch.sigmoid(net.head.last_cls_preds.view(-1))

            if is_pos.sum() > 0:
                pos_obj_p = obj_p[is_pos].cpu().numpy()
                pos_cls_p = cls_p[is_pos].cpu().numpy()
                pos_scores = pos_obj_p * pos_cls_p
                mean_pos_obj = float(pos_obj_p.mean())
                mean_pos_cls = float(pos_cls_p.mean())
                mean_pos_score = float(pos_scores.mean())
            else:
                mean_pos_obj, mean_pos_cls, mean_pos_score = 0.0, 0.0, 0.0

            if is_neg.sum() > 0:
                neg_obj_p = obj_p[is_neg].cpu().numpy()
                mean_neg_obj = float(neg_obj_p.mean())
            else:
                mean_neg_obj = 0.0

        b_entry = {
            'batchIndex': b_idx + 1,
            'numFg': float(num_fg),
            'numKnownNeg': int(num_known_neg),
            'numUnknown': int(num_unknown),
            'normPosObjLoss': float(norm_pos_loss),
            'normNegObjLoss': float(norm_neg_loss),
            'ratioNegToPosLoss': float(norm_neg_loss / max(1e-8, norm_pos_loss)),
            'lossIoU': float(loss_iou),
            'lossCls': float(loss_cls),
            'totalLoss': float(total_loss),
            'gradPosNorm': grad_pos_norm,
            'gradNegNorm': grad_neg_norm,
            'ratioNegToPosGradNorm': float(grad_neg_norm / max(1e-8, grad_pos_norm)),
            'gradCosineSimilarity': cos_sim,
            'meanPosObjectness': mean_pos_obj,
            'meanPosClassScore': mean_pos_cls,
            'meanPosTotalScore': mean_pos_score,
            'meanNegObjectness': mean_neg_obj
        }
        batch_measurements.append(b_entry)

        print(f"Batch {b_idx+1}:")
        print(f"  Anchors: FG={num_fg:.0f}, KnownNeg={num_known_neg}, UnknownMasked={num_unknown}")
        print(f"  Normalized Losses: PosObj={norm_pos_loss:.4f}, NegObj={norm_neg_loss:.4f} (Neg/Pos Ratio={norm_neg_loss/max(1e-8, norm_pos_loss):.2f}x), IoU={loss_iou:.4f}, Cls={loss_cls:.4f}")
        print(f"  Gradient Norms (obj_preds): Pos={grad_pos_norm:.6f}, Neg={grad_neg_norm:.6f} (Neg/Pos Ratio={grad_neg_norm/max(1e-8, grad_pos_norm):.2f}x, CosSim={cos_sim:+.3f})")
        print(f"  Predictions on Positives: mean obj={mean_pos_obj:.4f}, mean cls={mean_pos_cls:.4f}, mean score={mean_pos_score:.4f} (Neg mean obj={mean_neg_obj:.6f})")

    # Aggregate averages
    avg_pos_loss = np.mean([m['normPosObjLoss'] for m in batch_measurements])
    avg_neg_loss = np.mean([m['normNegObjLoss'] for m in batch_measurements])
    avg_pos_grad = np.mean([m['gradPosNorm'] for m in batch_measurements])
    avg_neg_grad = np.mean([m['gradNegNorm'] for m in batch_measurements])
    avg_cossim = np.mean([m['gradCosineSimilarity'] for m in batch_measurements])
    avg_pos_obj = np.mean([m['meanPosObjectness'] for m in batch_measurements])
    avg_pos_cls = np.mean([m['meanPosClassScore'] for m in batch_measurements])
    avg_pos_score = np.mean([m['meanPosTotalScore'] for m in batch_measurements])

    summary = {
        'numBatches': num_batches,
        'batchSize': batch_size,
        'avgNormPosObjLoss': float(avg_pos_loss),
        'avgNormNegObjLoss': float(avg_neg_loss),
        'avgLossRatioNegToPos': float(avg_neg_loss / max(1e-8, avg_pos_loss)),
        'avgPosGradNorm': float(avg_pos_grad),
        'avgNegGradNorm': float(avg_neg_grad),
        'avgGradNormRatioNegToPos': float(avg_neg_grad / max(1e-8, avg_pos_grad)),
        'avgGradientCosineSimilarity': float(avg_cossim),
        'avgPosObjectness': float(avg_pos_obj),
        'avgPosClassScore': float(avg_pos_cls),
        'avgPosTotalScore': float(avg_pos_score),
        'batchDetails': batch_measurements
    }

    print("\n" + "=" * 80)
    print("EMPIRICAL LOSS & GRADIENT SUMMARY ACROSS REPRODUCIBLE TRAIN BATCHES:")
    print("=" * 80)
    print(f"Average Normalized Pos Obj Loss: {avg_pos_loss:.4f}")
    print(f"Average Normalized Neg Obj Loss: {avg_neg_loss:.4f} (Ratio: {avg_neg_loss/max(1e-8, avg_pos_loss):.2f}x)")
    print(f"Average Pos Obj Grad Norm:      {avg_pos_grad:.6f}")
    print(f"Average Neg Obj Grad Norm:      {avg_neg_grad:.6f} (Ratio: {avg_neg_grad/max(1e-8, avg_pos_grad):.2f}x)")
    print(f"Average Gradient Cosine Sim:    {avg_cossim:+.4f}")
    print(f"Positive Anchor Predictions:     obj={avg_pos_obj:.4f}, cls={avg_pos_cls:.4f}, score={avg_pos_score:.4f}")

    return summary


if __name__ == '__main__':
    res = run_empirical_loss_measurement()
    out_p = ROOT / 'audit-results/acne-input-audit-20261015/train_empirical_loss_measurements.json'
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2)
    print(f"\nSaved empirical loss measurements to {out_p}")
