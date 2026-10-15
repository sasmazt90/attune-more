#!/usr/bin/env python3
"""Compare Step 0 (Calibrated Baseline) vs Epoch 4 (Fine-tuned) on identical fixed mini-batch cohort.

Directives (Item 3):
- Positive anchor assignments partitioned by dimension (<8px, 8-16px, >=16px) and pyramid stride (P2=4, P3=8, P4=16, P5=32).
- Mean objectness, class score, and combined score (obj * cls) on positive anchors.
- Explicit raw localization loss vs weighted localization loss (reg_weight=5.0).
- Normalized positive vs negative objectness loss and their ratio.
- Gradient norms on head.obj_preds and head.reg_preds with cosine similarity.
- Findings bounded strictly to this representative sample group.
"""

import sys
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Any

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

TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014'
STEP0_PATH = TRIAL_DIR / 'checkpoint-epoch-00-step-000000-1792014463030016700/model.safetensors'
EPOCH4_PATH = TRIAL_DIR / 'checkpoint-epoch-04-step-000828-1792020809525886000/model.safetensors'

COHORT_PATH = ROOT / 'audit-results/acne-pilot-giou-comparison-20261015/controlled_train_cohort.json'
DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
OUT_DIR = ROOT / 'audit-results/acne-pilot-giou-comparison-20261015'


def load_model(weights_path: Path, loss_type="iou"):
    net = build_yolox_p2_model(loss_type=loss_type)
    net.load_state_dict(load_file(str(weights_path)), strict=True)
    focal_loss = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
    net.head.obj_focal_loss = focal_loss
    net.train()
    for m in net.modules():
        if isinstance(m, nn.BatchNorm2d):
            m.eval()
    return net, focal_loss


def run_cohort_comparison():
    print("=" * 80)
    print("COMPARISON OF STEP 0 BASELINE VS EPOCH 4 ON IDENTICAL FIXED COHORT")
    print("=" * 80)

    with open(COHORT_PATH, 'r', encoding='utf-8') as f:
        cohort = json.load(f)
    comparison_tiles = cohort['comparisonTiles40']
    batch_size = 4
    num_batches = len(comparison_tiles) // batch_size
    print(f"Evaluating {num_batches} fixed mini-batches ({len(comparison_tiles)} tiles, batch_size={batch_size}).")

    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    train_rows = {r['sha256']: r for r in data['rows'] if r.get('split') == 'train'}

    # Build hole preserved negative masks
    all_train_rows_list = list(train_rows.values())
    masks, weights = build_hole_preserved_negative_masks(all_train_rows_list)

    # Preload only images needed for these 40 tiles
    needed_shas = set(t['imageSha256'] for t in comparison_tiles)
    img_cache = {}
    for sha in needed_shas:
        r = train_rows[sha]
        path = r.get('absolutePath') or str(LIVE_TEST / r['path'])
        bgr = cv2.imread(path)
        assert bgr is not None, f"Image not found: {path}"
        img_cache[sha] = bgr

    # Prepare batches
    batches = []
    for b_idx in range(num_batches):
        batches.append(comparison_tiles[b_idx * batch_size : (b_idx + 1) * batch_size])

    models = [
        {'name': 'Step 0 (Calibrated Baseline)', 'path': STEP0_PATH, 'key': 'step0'},
        {'name': 'Epoch 4 (Fine-tuned)', 'path': EPOCH4_PATH, 'key': 'epoch4'}
    ]

    results = {}

    for mcfg in models:
        mkey = mcfg['key']
        mname = mcfg['name']
        print(f"\n--- Evaluating Model: {mname} ---")

        net, focal_loss = load_model(mcfg['path'])
        obj_params = [p for name, p in net.head.named_parameters() if 'obj_preds' in name and p.requires_grad]
        reg_params = [p for name, p in net.head.named_parameters() if 'reg_preds' in name and p.requires_grad]

        batch_records = []

        for b_idx, b_tiles in enumerate(batches):
            images = []
            targets = torch.zeros((len(b_tiles), max(max(len(t.get('boxes', [])) for t in b_tiles), 1), 5), dtype=torch.float32)

            for bi, t in enumerate(b_tiles):
                full_bgr = img_cache[t['imageSha256']]
                a, b, endx, endy = t['rect']
                tile = np.full((384, 384, 3), 114, dtype=np.uint8)
                crop = full_bgr[b:endy, a:endx]
                tile[:crop.shape[0], :crop.shape[1]] = crop
                images.append(torch.from_numpy(tile.transpose(2, 0, 1)).float())
                for bj, (x0, y0, x1, y1) in enumerate(t.get('boxes', [])):
                    targets[bi, bj] = torch.tensor([0, (x0 + x1) / 2.0, (y0 + y1) / 2.0, x1 - x0, y1 - y0])

            x = torch.stack(images)
            y = targets

            known_list = []
            weight_list = []
            for t in b_tiles:
                sha = t['imageSha256']
                kt, wt = known_cells_p2(masks[sha], weights[sha], t['rect'], strides=(4, 8, 16, 32))
                known_list.append(kt)
                weight_list.append(wt)

            focal_loss.known = torch.cat(known_list, dim=0)
            focal_loss.boundary_weights = torch.cat(weight_list, dim=0)

            net.zero_grad()
            loss_dict = net(x, y)

            fl_metrics = focal_loss.last_metrics
            num_fg = fl_metrics['num_fg']
            num_known_neg = fl_metrics['num_known_neg_anchors']
            num_unknown = fl_metrics['num_unknown_anchors']

            norm_pos_loss = fl_metrics['norm_pos_obj_loss']
            norm_neg_loss = fl_metrics['norm_neg_obj_loss']

            # Explicitly separate raw and weighted localization loss
            raw_loc_loss = float(net.head.last_raw_loc_loss.item())
            weighted_loc_loss = float(net.head.last_weighted_loc_loss.item())
            loss_cls = float(loss_dict['cls_loss'].item())
            loss_obj = float(loss_dict['conf_loss'].item())
            total_loss = float(loss_dict['total_loss'].item())

            # Gradient norms for positive vs negative objectness loss on head.obj_preds
            norm_pos_tensor = net.head.last_norm_pos
            norm_neg_tensor = net.head.last_norm_neg

            grad_pos = torch.autograd.grad(norm_pos_tensor, obj_params, retain_graph=True, allow_unused=True)
            grad_pos_vec = torch.cat([g.flatten() for g in grad_pos if g is not None])
            grad_pos_norm = float(grad_pos_vec.norm(2).item())

            grad_neg = torch.autograd.grad(norm_neg_tensor, obj_params, retain_graph=False, allow_unused=True)
            grad_neg_vec = torch.cat([g.flatten() for g in grad_neg if g is not None])
            grad_neg_norm = float(grad_neg_vec.norm(2).item())

            cos_sim = float((grad_pos_vec.dot(grad_neg_vec) / (max(grad_pos_norm, 1e-8) * max(grad_neg_norm, 1e-8))).item())

            # Anchor assignment breakdown by pyramid stride and lesion scale
            with torch.no_grad():
                is_pos = net.head.last_is_pos.squeeze(1)
                is_neg = net.head.last_is_neg.squeeze(1)
                obj_p = torch.sigmoid(net.head.last_obj_preds.view(-1))
                cls_p = torch.sigmoid(net.head.last_cls_preds.view(-1))

                # Strides of anchors: 4 anchors per image (stride 4, 8, 16, 32)
                # Anchors per tile: 9216 (p2), 2304 (p3), 576 (p4), 144 (p5) = 12240 per tile
                # For batch_size=4: total 48960 anchors
                anchors_per_tile = 12240
                p2_count, p3_count, p4_count, p5_count = 0, 0, 0, 0
                pos_indices = torch.where(is_pos)[0]
                for p_idx in pos_indices:
                    idx_in_tile = int(p_idx.item()) % anchors_per_tile
                    if idx_in_tile < 9216:
                        p2_count += 1
                    elif idx_in_tile < 9216 + 2304:
                        p3_count += 1
                    elif idx_in_tile < 9216 + 2304 + 576:
                        p4_count += 1
                    else:
                        p5_count += 1

                # Lesion sizes inside batch targets
                micro_tgt = 0
                small_tgt = 0
                med_tgt = 0
                for t in b_tiles:
                    for b in t.get('boxes', []):
                        dim = max(b[2] - b[0], b[3] - b[1])
                        if dim < 8:
                            micro_tgt += 1
                        elif dim < 16:
                            small_tgt += 1
                        else:
                            med_tgt += 1

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

            b_record = {
                'batchIndex': b_idx + 1,
                'numFg': float(num_fg),
                'strideAssignment': {'p2_s4': p2_count, 'p3_s8': p3_count, 'p4_s16': p4_count, 'p5_s32': p5_count},
                'targetSizes': {'micro': micro_tgt, 'small': small_tgt, 'medium': med_tgt},
                'rawLocLoss': raw_loc_loss,
                'weightedLocLoss': weighted_loc_loss,
                'normPosObjLoss': float(norm_pos_loss),
                'normNegObjLoss': float(norm_neg_loss),
                'lossCls': loss_cls,
                'lossObj': loss_obj,
                'totalLoss': total_loss,
                'meanPosObj': mean_pos_obj,
                'meanPosCls': mean_pos_cls,
                'meanPosScore': mean_pos_score,
                'meanNegObj': mean_neg_obj,
                'gradPosNorm': grad_pos_norm,
                'gradNegNorm': grad_neg_norm,
                'gradCosineSim': cos_sim
            }
            batch_records.append(b_record)

        # Aggregate metrics
        avg_raw_loc = float(np.mean([b['rawLocLoss'] for b in batch_records]))
        avg_weighted_loc = float(np.mean([b['weightedLocLoss'] for b in batch_records]))
        avg_pos_loss = float(np.mean([b['normPosObjLoss'] for b in batch_records]))
        avg_neg_loss = float(np.mean([b['normNegObjLoss'] for b in batch_records]))
        avg_pos_obj = float(np.mean([b['meanPosObj'] for b in batch_records]))
        avg_pos_cls = float(np.mean([b['meanPosCls'] for b in batch_records]))
        avg_pos_score = float(np.mean([b['meanPosScore'] for b in batch_records]))
        avg_neg_obj = float(np.mean([b['meanNegObj'] for b in batch_records]))
        avg_pos_grad = float(np.mean([b['gradPosNorm'] for b in batch_records]))
        avg_neg_grad = float(np.mean([b['gradNegNorm'] for b in batch_records]))
        avg_cossim = float(np.mean([b['gradCosineSim'] for b in batch_records]))
        total_p2 = sum(b['strideAssignment']['p2_s4'] for b in batch_records)
        total_p3 = sum(b['strideAssignment']['p3_s8'] for b in batch_records)
        total_p4 = sum(b['strideAssignment']['p4_s16'] for b in batch_records)
        total_p5 = sum(b['strideAssignment']['p5_s32'] for b in batch_records)

        summary = {
            'model': mname,
            'numBatches': num_batches,
            'totalPositiveAnchors': total_p2 + total_p3 + total_p4 + total_p5,
            'pyramidAssignments': {'P2 (s=4)': total_p2, 'P3 (s=8)': total_p3, 'P4 (s=16)': total_p4, 'P5 (s=32)': total_p5},
            'avgRawLocLoss': avg_raw_loc,
            'avgWeightedLocLoss': avg_weighted_loc,
            'avgNormPosObjLoss': avg_pos_loss,
            'avgNormNegObjLoss': avg_neg_loss,
            'ratioNegToPosLoss': avg_neg_loss / max(1e-8, avg_pos_loss),
            'avgPosObjectness': avg_pos_obj,
            'avgPosClassScore': avg_pos_cls,
            'avgPosTotalScore': avg_pos_score,
            'avgNegObjectness': avg_neg_obj,
            'avgPosGradNorm': avg_pos_grad,
            'avgNegGradNorm': avg_neg_grad,
            'ratioNegToPosGradNorm': avg_neg_grad / max(1e-8, avg_pos_grad),
            'avgGradientCosineSim': avg_cossim,
            'batches': batch_records
        }
        results[mkey] = summary

        print(f"Summary for {mname}:")
        print(f"  Pyramid Assignments: P2={total_p2}, P3={total_p3}, P4={total_p4}, P5={total_p5}")
        print(f"  Localization Loss: Raw={avg_raw_loc:.4f}, Weighted (5x)={avg_weighted_loc:.4f}")
        print(f"  Objectness Loss: Pos={avg_pos_loss:.4f}, Neg={avg_neg_loss:.4f} (Neg/Pos Ratio={summary['ratioNegToPosLoss']:.2f}x)")
        print(f"  Predictions on Positives: obj={avg_pos_obj:.4f}, cls={avg_pos_cls:.4f}, score={avg_pos_score:.4f} (Neg obj={avg_neg_obj:.6f})")
        print(f"  Gradient Norms (obj_preds): Pos={avg_pos_grad:.6f}, Neg={avg_neg_grad:.6f} (Neg/Pos Ratio={summary['ratioNegToPosGradNorm']:.2f}x, CosSim={avg_cossim:+.4f})")

    out_file = OUT_DIR / 'step0_vs_epoch4_cohort_comparison.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved Step 0 vs Epoch 4 cohort comparison to {out_file}")

    return results


if __name__ == '__main__':
    run_cohort_comparison()
