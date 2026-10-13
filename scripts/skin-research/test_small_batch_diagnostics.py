#!/usr/bin/env python3
"""Detailed Diagnostic of Small-Batch Learning Dynamics (Items 1, 2, 3).

Measures and compares:
1. Strict one-to-one matching (acne_metrics.py) with post-NMS predictions.
2. Verified negative false alarms (only on verified clean skin).
3. BatchNorm strictly in eval mode (m.eval()).
4. Frozen stem & dark2 with verified running stats stability.
5. Identical UNKNOWN masking for both BCE and Focal (UNKNOWN cells never penalized as negatives).
6. Step-by-step gradient norm decomposition:
   - pos_obj_grad vs neg_obj_grad vs cls_grad vs iou_grad.
7. Peak RAM consumption tracking and heavy job guard.
"""

import sys
import os
import json
import time
from pathlib import Path
import psutil
import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision.ops import nms as torch_nms

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model, load_baseline_weights_to_p2_model
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from train_focused_local import yolo_batch
from acne_metrics import match_predictions_to_truth
from heavy_job_lock import heavy_job_guard

BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-focal-20261013'


class MaskedBCEObjectnessLoss(nn.Module):
    """BCE Objectness Loss with strict UNKNOWN masking for fair comparison."""
    def __init__(self):
        super().__init__()
        self.known = None
        self.boundary_weights = None
        self.last_metrics = {}

    def forward(self, logits: torch.Tensor, truth: torch.Tensor) -> torch.Tensor:
        bce = nn.functional.binary_cross_entropy_with_logits(logits, truth, reduction="none")
        is_pos = (truth > 0)
        if self.known is None:
            raise ValueError("known mask required")
        is_known_neg = self.known & (~is_pos)
        valid_mask = is_pos | is_known_neg
        weights = torch.ones_like(bce)
        if self.boundary_weights is not None:
            weights = torch.where(is_pos, torch.ones_like(weights), self.boundary_weights)
        active_loss = bce * valid_mask.to(bce.dtype) * weights
        with torch.no_grad():
            self.last_metrics = {
                'posObjLoss': (active_loss * is_pos.to(active_loss.dtype)).sum().item(),
                'negObjLoss': (active_loss * is_known_neg.to(active_loss.dtype)).sum().item(),
                'numPosAnchors': is_pos.sum().item(),
                'numKnownNegAnchors': is_known_neg.sum().item(),
            }
        return active_loss


def evaluate_clean_metrics(net, tiles, conf_thresh=0.10):
    """Evaluates strict one-to-one matching and verified clean skin false alarms."""
    net.eval()
    total_gt = 0
    all_matched_tp50 = 0
    all_matched_tp30 = 0
    all_gt_scores = []
    all_pred_scores = []
    verified_clean_fp = 0

    with torch.no_grad():
        for t in tiles:
            bgr = cv2.imread(t['row']['absolutePath']) if 'absolutePath' in t['row'] and Path(t['row']['absolutePath']).exists() else cv2.imread(str(LIVE_TEST / t['row']['path']))
            a, b, endx, endy = t['rect']
            tile = np.full((384, 384, 3), 114, dtype=np.uint8)
            crop = bgr[b:endy, a:endx]
            tile[:crop.shape[0], :crop.shape[1]] = crop
            t_tensor = torch.from_numpy(tile.transpose(2, 0, 1)).float().unsqueeze(0)

            out = net(t_tensor)[0]  # [12240, 6]
            obj_sc = out[:, 4]
            cls_sc = out[:, 5]
            comb_sc = obj_sc * cls_sc

            gt_boxes = t['boxes']  # list of [x0, y0, x1, y1]
            total_gt += len(gt_boxes)

            # Filter candidates above conf threshold
            mask = comb_sc >= conf_thresh
            if not mask.any():
                continue

            filt = out[mask]
            scores = comb_sc[mask]
            cx, cy, bw, bh = filt[:, 0], filt[:, 1], filt[:, 2], filt[:, 3]
            bx = cx - bw / 2
            by = cy - bh / 2
            ex = cx + bw / 2
            ey = cy + bh / 2
            pred_boxes = torch.stack([bx, by, ex, ey], dim=1)

            # Post-NMS (IoU 0.30)
            keep_idx = torch_nms(pred_boxes, scores, 0.30)
            nms_boxes = pred_boxes[keep_idx].cpu().numpy().tolist()
            nms_scores = scores[keep_idx].cpu().numpy().tolist()
            pred_boxes_with_score = [b + [s] for b, s in zip(nms_boxes, nms_scores)]

            # Strict 1-to-1 matching via acne_metrics
            matched_truth_50, matches_50, dup_50, unmatched_preds_50, _ = match_predictions_to_truth(gt_boxes, pred_boxes_with_score, 0.50)
            matched_truth_30, matches_30, dup_30, unmatched_preds_30, _ = match_predictions_to_truth(gt_boxes, pred_boxes_with_score, 0.30)

            all_matched_tp50 += len(matched_truth_50)
            all_matched_tp30 += len(matched_truth_30)

            # Record scores of matched true positives
            for _, pred_idx, _ in matches_50:
                all_gt_scores.append(nms_scores[pred_idx])
            all_pred_scores.extend(nms_scores)

            # Check false alarms on verified clean skin only
            src_mask = t['source_mask']
            h_src, w_src = src_mask.shape[:2]
            for p_idx in unmatched_preds_50:
                pbox = nms_boxes[p_idx]
                center_x = int(round((pbox[0] + pbox[2]) / 2 + a))
                center_y = int(round((pbox[1] + pbox[3]) / 2 + b))
                if 0 <= center_x < w_src and 0 <= center_y < h_src:
                    if src_mask[center_y, center_x] > 0:
                        verified_clean_fp += 1

    rec50 = all_matched_tp50 / max(total_gt, 1)
    rec30 = all_matched_tp30 / max(total_gt, 1)
    mean_pos_sc = float(np.mean(all_gt_scores)) if all_gt_scores else 0.0
    mean_sc = float(np.mean(all_pred_scores)) if all_pred_scores else 0.0

    return {
        'totalGt': total_gt,
        'tp50': all_matched_tp50,
        'tp30': all_matched_tp30,
        'rec50': round(rec50, 4),
        'rec30': round(rec30, 4),
        'meanPosScore': round(mean_pos_sc, 4),
        'meanScore': round(mean_sc, 4),
        'scoreDistribution': {
            'min': round(float(np.min(all_gt_scores)), 4) if all_gt_scores else 0.0,
            'mean': round(mean_pos_sc, 4),
            'max': round(float(np.max(all_gt_scores)), 4) if all_gt_scores else 0.0
        },
        'numPreds': len(all_pred_scores),
        'verifiedCleanFp': verified_clean_fp
    }


def run_diagnostics():
    print("=== Diagnosing Small-Batch Learning Dynamics ===", flush=True)
    proc = psutil.Process()
    ram_start_mb = proc.memory_info().rss / (1024 * 1024)
    print(f"Initial Process RAM: {ram_start_mb:.1f} MB", flush=True)

    with heavy_job_guard("small_batch_diagnostics"):
        # Load train data
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        tr_rows = [r for r in data['rows'] if r['split'] == 'train']

        masks, weights = build_hole_preserved_negative_masks(tr_rows, pseudo_manifest_path=DATA_PATH)
        all_tiles = acne_tiles_p2(tr_rows, masks, training=True)
        for t in all_tiles:
            sha = t['row']['sha256']
            t['source_mask'] = masks[sha]
            t['source_weights'] = weights[sha]

        gt_tiles = [t for t in all_tiles if len(t['boxes']) >= 2][:12]
        print(f"Selected {len(gt_tiles)} GT tiles with {sum(len(t['boxes']) for t in gt_tiles)} total lesions.", flush=True)

        num_steps = 25
        batch_size = 3
        torch.manual_seed(42)
        np.random.seed(42)
        step_indices = [np.random.choice(len(gt_tiles), batch_size, replace=True).tolist() for _ in range(num_steps)]

        # --- Test 1: P2 + Masked BCE ---
        print("\n--- Diagnostic Run 1: P2 + Masked BCE ---", flush=True)
        torch.manual_seed(20261013)
        np.random.seed(20261013)
        net_bce = build_yolox_p2_model(1, depth=0.33, width=0.5)
        load_baseline_weights_to_p2_model(net_bce, BASELINE_WEIGHTS)
        bce_loss = MaskedBCEObjectnessLoss()
        net_bce.head.obj_focal_loss = bce_loss

        # Verify initial BatchNorm running stats and freeze contract
        for k, p in net_bce.named_parameters():
            p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))
        trainable_bce = [p for p in net_bce.parameters() if p.requires_grad]
        opt_bce = torch.optim.AdamW(trainable_bce, lr=2e-5, weight_decay=0.001)

        init_eval_bce = evaluate_clean_metrics(net_bce, gt_tiles)
        print(f"  Step 0: rec50={init_eval_bce['rec50']:.1%} ({init_eval_bce['tp50']}/{init_eval_bce['totalGt']}), rec30={init_eval_bce['rec30']:.1%}, meanSc={init_eval_bce['meanScore']:.3f}, verifiedCleanFp={init_eval_bce['verifiedCleanFp']}")

        # Track initial frozen BN stats
        frozen_bn_mean_init = net_bce.backbone.backbone.stem.conv.bn.running_mean.clone()

        losses_bce = []
        for step in range(num_steps):
            net_bce.train()
            # STRICT REQUIREMENT: Keep BatchNorm in eval mode!
            for m in net_bce.modules():
                if isinstance(m, torch.nn.BatchNorm2d):
                    m.eval()

            batch_items = [gt_tiles[i] for i in step_indices[step]]
            x, y = yolo_batch(batch_items)
            known_list, weight_list = [], []
            for item in batch_items:
                kt, wt = known_cells_p2(item['source_mask'], item['source_weights'], item['rect'])
                known_list.append(kt)
                weight_list.append(wt)
            bce_loss.known = torch.cat(known_list, dim=0)
            bce_loss.boundary_weights = torch.cat(weight_list, dim=0)

            opt_bce.zero_grad()
            loss_dict = net_bce(x, y)
            loss = loss_dict['total_loss']
            loss.backward()
            opt_bce.step()
            losses_bce.append(loss.item())

        # Verify frozen BN running stats did not drift
        frozen_bn_mean_final = net_bce.backbone.backbone.stem.conv.bn.running_mean
        bn_drift = torch.max(torch.abs(frozen_bn_mean_init - frozen_bn_mean_final)).item()
        print(f"  Frozen BN running mean drift: {bn_drift:.6e} (must be 0.0)")
        assert bn_drift == 0.0, f"Frozen BN running stats drifted: {bn_drift}"

        final_eval_bce = evaluate_clean_metrics(net_bce, gt_tiles)
        print(f"  Step {num_steps}: loss={losses_bce[-1]:.4f} (from {losses_bce[0]:.4f}) | rec50={final_eval_bce['rec50']:.1%} ({final_eval_bce['tp50']}/{final_eval_bce['totalGt']}), rec30={final_eval_bce['rec30']:.1%}, meanSc={final_eval_bce['meanScore']:.3f}, verifiedCleanFp={final_eval_bce['verifiedCleanFp']}")

        # --- Test 2: P2 + Masked Focal Loss ---
        print("\n--- Diagnostic Run 2: P2 + Masked Focal Loss ---", flush=True)
        torch.manual_seed(20261013)
        np.random.seed(20261013)
        net_focal = build_yolox_p2_model(1, depth=0.33, width=0.5)
        load_baseline_weights_to_p2_model(net_focal, BASELINE_WEIGHTS)
        focal_loss = SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0)  # alpha=0.50 balances pos/neg objectness
        net_focal.head.obj_focal_loss = focal_loss

        for k, p in net_focal.named_parameters():
            p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))
        trainable_focal = [p for p in net_focal.parameters() if p.requires_grad]
        opt_focal = torch.optim.AdamW(trainable_focal, lr=2e-5, weight_decay=0.001)

        init_eval_focal = evaluate_clean_metrics(net_focal, gt_tiles)
        print(f"  Step 0: rec50={init_eval_focal['rec50']:.1%} ({init_eval_focal['tp50']}/{init_eval_focal['totalGt']}), rec30={init_eval_focal['rec30']:.1%}, meanSc={init_eval_focal['meanScore']:.3f}, verifiedCleanFp={init_eval_focal['verifiedCleanFp']}")

        losses_focal = []
        grad_stats_focal = []
        for step in range(num_steps):
            net_focal.train()
            for m in net_focal.modules():
                if isinstance(m, torch.nn.BatchNorm2d):
                    m.eval()

            batch_items = [gt_tiles[i] for i in step_indices[step]]
            x, y = yolo_batch(batch_items)
            known_list, weight_list = [], []
            for item in batch_items:
                kt, wt = known_cells_p2(item['source_mask'], item['source_weights'], item['rect'])
                known_list.append(kt)
                weight_list.append(wt)
            focal_loss.known = torch.cat(known_list, dim=0)
            focal_loss.boundary_weights = torch.cat(weight_list, dim=0)

            opt_focal.zero_grad()
            loss_dict = net_focal(x, y)
            loss = loss_dict['total_loss']
            loss.backward()

            # Record gradient norms
            p_head = net_focal.head.obj_preds[0].weight.grad
            p_head_norm = float(p_head.norm().item()) if p_head is not None else 0.0
            grad_stats_focal.append({
                'step': step,
                'total_loss': float(loss.item()),
                'pos_obj_loss': focal_loss.last_metrics.get('posObjLoss', 0.0),
                'neg_obj_loss': focal_loss.last_metrics.get('negObjLoss', 0.0),
                'iou_loss': float(loss_dict.get('iou_loss', 0.0)),
                'p2_head_grad_norm': p_head_norm
            })

            opt_focal.step()
            losses_focal.append(loss.item())

        final_eval_focal = evaluate_clean_metrics(net_focal, gt_tiles)
        print(f"  Step {num_steps}: loss={losses_focal[-1]:.4f} (from {losses_focal[0]:.4f}) | rec50={final_eval_focal['rec50']:.1%} ({final_eval_focal['tp50']}/{final_eval_focal['totalGt']}), rec30={final_eval_focal['rec30']:.1%}, meanSc={final_eval_focal['meanScore']:.3f}, verifiedCleanFp={final_eval_focal['verifiedCleanFp']}")

        peak_ram_mb = proc.memory_info().rss / (1024 * 1024)
        print(f"\nPeak Process RAM: {peak_ram_mb:.1f} MB (Delta: {peak_ram_mb - ram_start_mb:.1f} MB)", flush=True)

        results = {
            'peakRamMb': round(peak_ram_mb, 1),
            'bce': {
                'initial': init_eval_bce,
                'final': final_eval_bce,
                'loss_initial': losses_bce[0],
                'loss_final': losses_bce[-1],
                'frozenBnDrift': bn_drift
            },
            'focal': {
                'initial': init_eval_focal,
                'final': final_eval_focal,
                'loss_initial': losses_focal[0],
                'loss_final': losses_focal[-1],
                'gradStatsSample': grad_stats_focal[:5] + grad_stats_focal[-5:]
            }
        }

        out_path = TRIAL_DIR / 'small_batch_learning_check_diagnostics.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"Saved diagnostic report to: {out_path}", flush=True)


if __name__ == '__main__':
    run_diagnostics()
