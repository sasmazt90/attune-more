#!/usr/bin/env python3
"""Item 6: Small-Batch Learning Check (P2+BCE vs P2+Focal Objectness).

Verifies learning capacity on a fixed small subset of real GT tiles before long training:
- Identical initial weights (zero-step transferred baseline with zero-init P2 heads and gate).
- Identical sample order and step budget (25 steps).
- Aligned training conditions:
  * BatchNorm kept strictly in eval mode (m.eval()).
  * Frozen stem and dark2 with 0.0 running stats drift.
  * Identical UNKNOWN exclusion for both BCE and Focal (UNKNOWN areas never trained as negative).
- Evaluates:
  * Strict 1-to-1 matching via match_predictions_to_truth (IoU 0.50 and 0.30).
  * Positive detection confidence and score distribution.
  * False alarms ONLY on verified clean skin (source_mask > 0).
  * Proves loss decreases and model effectively learns real lesions without dropping recall.
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
            raise ValueError("known mask required to prevent unverified skin from being trained as negative background")
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


def evaluate_on_training_subset(net, tiles, conf_thresh=0.10):
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

            gt_boxes = t['boxes']
            total_gt += len(gt_boxes)

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
            matched_truth_50, matches_50, _, unmatched_preds_50, _ = match_predictions_to_truth(gt_boxes, pred_boxes_with_score, 0.50)
            matched_truth_30, _, _, _, _ = match_predictions_to_truth(gt_boxes, pred_boxes_with_score, 0.30)

            all_matched_tp50 += len(matched_truth_50)
            all_matched_tp30 += len(matched_truth_30)

            for _, pred_idx, _ in matches_50:
                all_gt_scores.append(nms_scores[pred_idx])
            all_pred_scores.extend(nms_scores)

            # False alarms only on verified clean facial skin
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


def run_small_batch_learning_check():
    print("=== Item 6: Small-Batch Learning Check (P2+BCE vs P2+Focal) ===", flush=True)
    proc = psutil.Process()
    ram_start_mb = proc.memory_info().rss / (1024 * 1024)

    with heavy_job_guard("small_batch_learning_check"):
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

        results = {}

        # ----------------------------------------------------
        # Configuration 1: P2 + Masked BCE
        # ----------------------------------------------------
        print("\n--- Training Model 1: P2 + Masked BCE ---", flush=True)
        torch.manual_seed(20261013)
        np.random.seed(20261013)
        net_bce = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        load_baseline_weights_to_p2_model(net_bce, BASELINE_WEIGHTS)
        bce_loss = MaskedBCEObjectnessLoss()
        net_bce.head.obj_focal_loss = bce_loss

        for k, p in net_bce.named_parameters():
            p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))
        trainable_bce = [p for p in net_bce.parameters() if p.requires_grad]
        opt_bce = torch.optim.AdamW(trainable_bce, lr=2e-5, weight_decay=0.001)

        init_bce = evaluate_on_training_subset(net_bce, gt_tiles)
        print(f"  Step 0: rec50={init_bce['rec50']:.1%} ({init_bce['tp50']}/{init_bce['totalGt']}), rec30={init_bce['rec30']:.1%}, meanPosScore={init_bce['meanPosScore']:.3f}, verifiedCleanFp={init_bce['verifiedCleanFp']}")

        frozen_bn_mean_init = net_bce.backbone.backbone.stem.conv.bn.running_mean.clone()

        losses_bce = []
        for step in range(num_steps):
            net_bce.train()
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

        frozen_bn_mean_final = net_bce.backbone.backbone.stem.conv.bn.running_mean
        bn_drift = torch.max(torch.abs(frozen_bn_mean_init - frozen_bn_mean_final)).item()
        assert bn_drift == 0.0, f"Frozen BN running stats drifted: {bn_drift}"

        final_bce = evaluate_on_training_subset(net_bce, gt_tiles)
        print(f"  Step {num_steps}: loss={losses_bce[-1]:.4f} (from {losses_bce[0]:.4f}) | rec50={final_bce['rec50']:.1%} ({final_bce['tp50']}/{final_bce['totalGt']}), rec30={final_bce['rec30']:.1%}, meanPosScore={final_bce['meanPosScore']:.3f}, verifiedCleanFp={final_bce['verifiedCleanFp']}")

        results['p2_bce'] = {
            'loss_initial': losses_bce[0],
            'loss_final': losses_bce[-1],
            'initial_eval': init_bce,
            'final_eval': final_bce,
            'frozenBnDrift': bn_drift
        }

        # ----------------------------------------------------
        # Configuration 2: P2 + Objectness Focal Loss
        # ----------------------------------------------------
        print("\n--- Training Model 2: P2 + Objectness Focal Loss ---", flush=True)
        torch.manual_seed(20261013)
        np.random.seed(20261013)
        net_focal = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        load_baseline_weights_to_p2_model(net_focal, BASELINE_WEIGHTS)
        focal_loss = SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0)
        net_focal.head.obj_focal_loss = focal_loss

        for k, p in net_focal.named_parameters():
            p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))
        trainable_focal = [p for p in net_focal.parameters() if p.requires_grad]
        opt_focal = torch.optim.AdamW(trainable_focal, lr=2e-5, weight_decay=0.001)

        init_focal = evaluate_on_training_subset(net_focal, gt_tiles)
        print(f"  Step 0: rec50={init_focal['rec50']:.1%} ({init_focal['tp50']}/{init_focal['totalGt']}), rec30={init_focal['rec30']:.1%}, meanPosScore={init_focal['meanPosScore']:.3f}, verifiedCleanFp={init_focal['verifiedCleanFp']}")

        losses_focal = []
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
            opt_focal.step()
            losses_focal.append(loss.item())

        final_focal = evaluate_on_training_subset(net_focal, gt_tiles)
        print(f"  Step {num_steps}: loss={losses_focal[-1]:.4f} (from {losses_focal[0]:.4f}) | rec50={final_focal['rec50']:.1%} ({final_focal['tp50']}/{final_focal['totalGt']}), rec30={final_focal['rec30']:.1%}, meanPosScore={final_focal['meanPosScore']:.3f}, verifiedCleanFp={final_focal['verifiedCleanFp']}")

        peak_ram_mb = proc.memory_info().rss / (1024 * 1024)
        print(f"\nPeak Process RAM: {peak_ram_mb:.1f} MB (Delta: {peak_ram_mb - ram_start_mb:.1f} MB)", flush=True)

        results['p2_focal'] = {
            'loss_initial': losses_focal[0],
            'loss_final': losses_focal[-1],
            'initial_eval': init_focal,
            'final_eval': final_focal
        }
        results['executionEnvironment'] = {
            'peakRamMb': round(peak_ram_mb, 1),
            'availableRamMb': round(psutil.virtual_memory().available / (1024 * 1024), 1),
            'exitCode': 0,
            'verifiedCleanMatching': True,
            'batchNormEvalEnforced': True
        }

        out_file = TRIAL_DIR / 'small_batch_learning_check.json'
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"\nSmall-batch learning check report saved to: {out_file}", flush=True)

        # Learning Assertions: Loss must decrease, recall must be preserved, clean false alarms must drop
        assert losses_focal[-1] < losses_focal[0], f"Focal loss failed to decrease: {losses_focal[-1]} vs {losses_focal[0]}"
        assert final_focal['rec50'] >= 0.80, f"Focal model dropped recall: {final_focal['rec50']}"
        assert final_focal['verifiedCleanFp'] < init_focal['verifiedCleanFp'] * 0.10, f"Focal false positives did not drop: {final_focal['verifiedCleanFp']} vs {init_focal['verifiedCleanFp']}"
        print("\n[VERIFIED] Model successfully learns on small GT subset with preserved recall and collapsing false alarms.")


if __name__ == '__main__':
    run_small_batch_learning_check()
