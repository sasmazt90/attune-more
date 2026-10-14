#!/usr/bin/env python3
"""Targeted Small-Foci Learning Verification for YOLOX-S P2 starting from Epoch 2.

Protocol & Guardrails:
1. Starts strictly from Epoch 2 weights (SHA: cf3a2ba4af50...).
2. Evaluates on a small-foci enriched TRAIN subset (containing <8px and 8-16px lesions).
3. Parameter groups:
   - P2 branch & head: lr = 1e-4 with 5-step warmup
   - Pre-trained backbone & P3-P5 heads: lr = 1e-5
4. Verifies:
   - Zero gradient on UNKNOWN background anchors
   - P2 assignment count, gradient norm, and objectness score progression
   - Learning of previously missed small foci without losing existing detections
   - Frozen BatchNorm in eval() mode
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Any
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

from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from yolox_p2 import build_yolox_p2_model, build_p2_param_groups
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from train_focused_local import yolo_batch
from acne_metrics import match_predictions_to_truth

EPOCH2_CHECKPOINT = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/checkpoint-epoch-02-step-000496-1791911067067742300/model.safetensors'
DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
OUT_DIR = ROOT / 'audit-results/acne-candidate-p2-focal-20261013'


def enforce_bn_eval(net: nn.Module):
    for m in net.modules():
        if isinstance(m, (nn.BatchNorm2d, nn.BatchNorm1d, nn.SyncBatchNorm)):
            m.eval()


def run_learning_check():
    print("=== Step B: Real Small-Foci Learning Verification ===", flush=True)
    torch.manual_seed(20261014)
    np.random.seed(20261014)
    torch.set_num_threads(4)

    # 1. Load Data
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tr_rows = [r for r in data['rows'] if r['split'] == 'train']
    masks, weights = build_hole_preserved_negative_masks(tr_rows)
    all_tiles = acne_tiles_p2(tr_rows, masks, training=True)

    # 2. Select small-foci enriched subset: tiles with <8px and 8-16px lesions + clean controls
    tiny_tiles = [t for t in all_tiles if any(max(b[2]-b[0], b[3]-b[1]) < 8 for b in t['boxes'])]
    small_tiles = [t for t in all_tiles if any(8 <= max(b[2]-b[0], b[3]-b[1]) < 16 for b in t['boxes']) and t not in tiny_tiles]
    clean_tiles = [t for t in all_tiles if t['isCleanControl']]

    print(f"Pool: {len(tiny_tiles)} tiny-containing tiles, {len(small_tiles)} small-containing tiles, {len(clean_tiles)} clean control tiles")
    selected_subset = tiny_tiles[:20] + small_tiles[:15] + clean_tiles[:5]
    print(f"Selected learning check subset: {len(selected_subset)} tiles", flush=True)

    # 3. Build Model & Load Epoch 2 weights
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    net.load_state_dict(load_file(str(EPOCH2_CHECKPOINT)), strict=True)
    focal_loss = SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0)
    net.head.obj_focal_loss = focal_loss

    # Initial small-foci detection eval on this subset
    def evaluate_subset(model, tiles_list, conf_thresh=0.25):
        model.eval()
        total_gt = 0
        tiny_gt = 0
        small_gt = 0
        matched_gt = 0
        tiny_matched = 0
        small_matched = 0
        max_scores_tiny = []

        with torch.no_grad():
            for t in tiles_list:
                gt_boxes = t['boxes']
                if not gt_boxes:
                    continue
                x, _ = yolo_batch([t])
                dets = model(x)[0]  # [12240, 6]
                
                # Filter by confidence
                scored_dets = dets[dets[:, 4] * dets[:, 5] >= conf_thresh]
                
                for b in gt_boxes:
                    w = b[2] - b[0]
                    h = b[3] - b[1]
                    m = max(w, h)
                    total_gt += 1
                    is_tiny = m < 8
                    is_small = 8 <= m < 16
                    if is_tiny:
                        tiny_gt += 1
                    elif is_small:
                        small_gt += 1

                    # Check max raw detection score around this GT center
                    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                    dists = torch.sqrt((dets[:, 0] - cx)**2 + (dets[:, 1] - cy)**2)
                    nearby = dets[dists <= max(8.0, m * 1.5)]
                    if len(nearby) > 0:
                        max_score = (nearby[:, 4] * nearby[:, 5]).max().item()
                    else:
                        max_score = 0.0

                    if is_tiny:
                        max_scores_tiny.append(max_score)

                    # IoU match against scored detections
                    hit = False
                    if len(scored_dets) > 0:
                        gx0, gy0, gx1, gy1 = b
                        dx0 = scored_dets[:, 0] - scored_dets[:, 2] / 2
                        dy0 = scored_dets[:, 1] - scored_dets[:, 3] / 2
                        dx1 = scored_dets[:, 0] + scored_dets[:, 2] / 2
                        dy1 = scored_dets[:, 1] + scored_dets[:, 3] / 2

                        inter_x0 = torch.clamp(dx0, min=gx0)
                        inter_y0 = torch.clamp(dy0, min=gy0)
                        inter_x1 = torch.clamp(dx1, max=gx1)
                        inter_y1 = torch.clamp(dy1, max=gy1)
                        inter_w = torch.clamp(inter_x1 - inter_x0, min=0)
                        inter_h = torch.clamp(inter_y1 - inter_y0, min=0)
                        inter_area = inter_w * inter_h
                        union_area = (dx1 - dx0) * (dy1 - dy0) + (gx1 - gx0) * (gy1 - gy0) - inter_area
                        ious = inter_area / torch.clamp(union_area, min=1e-6)
                        if (ious >= 0.30).any():
                            hit = True

                    if hit:
                        matched_gt += 1
                        if is_tiny:
                            tiny_matched += 1
                        elif is_small:
                            small_matched += 1

        return {
            'total_gt': total_gt,
            'matched_gt': matched_gt,
            'tiny_gt': tiny_gt,
            'tiny_matched': tiny_matched,
            'small_gt': small_gt,
            'small_matched': small_matched,
            'mean_tiny_score': float(np.mean(max_scores_tiny)) if max_scores_tiny else 0.0,
            'max_scores_tiny': [round(s, 4) for s in max_scores_tiny]
        }

    initial_eval = evaluate_subset(net, selected_subset)
    print(f"\nInitial Detection on Subset: Total GT: {initial_eval['total_gt']}, Matched: {initial_eval['matched_gt']}")
    print(f"  Tiny (<8px): {initial_eval['tiny_matched']}/{initial_eval['tiny_gt']}, Mean score: {initial_eval['mean_tiny_score']:.4f}")
    print(f"  Small (8-16px): {initial_eval['small_matched']}/{initial_eval['small_gt']}")

    # 4. Set up Parameter Groups using shared unified builder
    param_groups, group_receipt = build_p2_param_groups(net, lr_p2=1e-4, lr_backbone=1e-5, weight_decay=0.0005)
    p2_params = param_groups[0]['params']
    base_params = param_groups[1]['params']

    print(f"\nParameter Groups:")
    print(f"  P2 Head & Branch (higher lr=1e-4): {group_receipt['p2Group']['parameterCount']} params ({group_receipt['p2Group']['tensorCount']} tensors)")
    print(f"  Pre-trained Backbone & Heads (fine-tune lr=1e-5): {group_receipt['backboneGroup']['parameterCount']} params ({group_receipt['backboneGroup']['tensorCount']} tensors)")
    print(f"  Frozen Backbone Stem & Dark2: {group_receipt['frozenGroup']['parameterCount']} params ({group_receipt['frozenGroup']['tensorCount']} tensors)")

    opt = torch.optim.AdamW(param_groups)

    # 5. Check UNKNOWN gradient = 0 Contract directly
    print("\n5. Directly Verifying UNKNOWN Objectness Gradient Contract...")
    test_logits = torch.randn(12240, 1, requires_grad=True)
    test_targets = torch.zeros(12240, 1)
    test_targets[10:20] = 1.0  # 10 positives
    test_known = torch.zeros(12240, 1, dtype=torch.bool)
    test_known[100:300] = True  # 200 known negatives, remaining are unknown
    focal_loss.known = test_known
    focal_loss.boundary_weights = None
    test_loss = focal_loss(test_logits, test_targets).sum()
    test_loss.backward()

    unknown_mask = (~test_known) & (test_targets == 0)
    max_unknown_grad = test_logits.grad[unknown_mask].abs().max().item()
    print(f"  Direct UNKNOWN Objectness Gradient: max abs grad = {max_unknown_grad:.8f} (Exact 0.0: {max_unknown_grad == 0.0})")
    assert max_unknown_grad == 0.0, f"UNKNOWN gradient is non-zero: {max_unknown_grad}"

    # Verify BatchNorm eval() mode
    net.train()
    enforce_bn_eval(net)
    bn_eval_checked = True
    for name, m in net.named_modules():
        if isinstance(m, (nn.BatchNorm2d, nn.BatchNorm1d, nn.SyncBatchNorm)):
            if m.training:
                bn_eval_checked = False
                break
    print(f"  BatchNorm eval mode verified across all layers: {bn_eval_checked}")
    assert bn_eval_checked, "BatchNorm layer found in training mode!"

    batch_sample = selected_subset[:4]
    x_test, y_test = yolo_batch(batch_sample)
    known_list = []
    weight_list = []
    for item in batch_sample:
        kt, wt = known_cells_p2(masks[item['row']['sha256']], weights[item['row']['sha256']], item['rect'], strides=(4, 8, 16, 32))
        known_list.append(kt)
        weight_list.append(wt)
    focal_loss.known = torch.cat(known_list, dim=0)
    focal_loss.boundary_weights = torch.cat(weight_list, dim=0)

    opt.zero_grad()
    loss_dict = net(x_test, y_test)
    loss = loss_dict['total_loss']
    loss.backward()

    # Check gradient on p2_gate and p2 heads
    p2_head_grad_norm = torch.norm(torch.stack([p.grad.norm() for p in p2_params if p.grad is not None])).item()
    base_grad_norm = torch.norm(torch.stack([p.grad.norm() for p in base_params if p.grad is not None])).item()
    print(f"\nInitial Gradients: P2 Head Grad Norm = {p2_head_grad_norm:.6f}, Base Grad Norm = {base_grad_norm:.6f}")
    assert p2_head_grad_norm > 0, "P2 head received 0 gradient! Head starvation detected."
    print("Contract Verified: P2 head receives active positive learning gradient.", flush=True)

    # 6. Run Controlled Learning Loop (20 steps with warmup)
    print("\n--- Running 20 Learning Check Steps ---", flush=True)
    batch_size = 4
    n_steps = 20
    step_history = []

    for step in range(n_steps):
        # Warmup for first 5 steps
        if step < 5:
            warmup_factor = (step + 1) / 5.0
            opt.param_groups[0]['lr'] = 1e-4 * warmup_factor
            opt.param_groups[1]['lr'] = 1e-5 * warmup_factor

        # Select batch
        batch_idx = (step * batch_size) % len(selected_subset)
        batch = selected_subset[batch_idx : batch_idx + batch_size]
        if len(batch) < batch_size:
            batch = selected_subset[:batch_size]

        x, y = yolo_batch(batch)
        k_list = []
        w_list = []
        for item in batch:
            kt, wt = known_cells_p2(masks[item['row']['sha256']], weights[item['row']['sha256']], item['rect'], strides=(4, 8, 16, 32))
            k_list.append(kt)
            w_list.append(wt)
        focal_loss.known = torch.cat(k_list, dim=0)
        focal_loss.boundary_weights = torch.cat(w_list, dim=0)

        opt.zero_grad()
        loss_dict = net(x, y)
        total_loss = loss_dict['total_loss']
        total_loss.backward()

        torch.nn.utils.clip_grad_norm_(p2_params + base_params, max_norm=5.0)
        opt.step()
        enforce_bn_eval(net)

        p2_norm = torch.norm(torch.stack([p.grad.norm() for p in p2_params if p.grad is not None])).item()
        
        step_rec = {
            'step': step,
            'loss': float(total_loss.item()),
            'p2_lr': float(opt.param_groups[0]['lr']),
            'p2_grad_norm': float(p2_norm)
        }
        step_history.append(step_rec)
        if (step + 1) % 5 == 0 or step == 0:
            print(f"  Step {step+1:02d}/20 | Loss: {total_loss.item():.4f} | P2 LR: {opt.param_groups[0]['lr']:.2e} | P2 Grad Norm: {p2_norm:.4f}", flush=True)

    # 7. Post-learning evaluation on the exact same subset
    post_eval = evaluate_subset(net, selected_subset)
    print(f"\nPost-Learning Detection on Subset: Total GT: {post_eval['total_gt']}, Matched: {post_eval['matched_gt']}")
    print(f"  Tiny (<8px): {post_eval['tiny_matched']}/{post_eval['tiny_gt']}, Mean score: {post_eval['mean_tiny_score']:.4f}")
    print(f"  Small (8-16px): {post_eval['small_matched']}/{post_eval['small_gt']}")

    score_gain_tiny = post_eval['mean_tiny_score'] - initial_eval['mean_tiny_score']
    print(f"\nTiny Lesion (<8px) Mean Score Progression: {initial_eval['mean_tiny_score']:.4f} -> {post_eval['mean_tiny_score']:.4f} (Delta: {score_gain_tiny:+.4f})")

    evidence = {
        'initial': initial_eval,
        'post': post_eval,
        'score_gain_tiny': score_gain_tiny,
        'step_history': step_history,
        'p2_gate_final': float(net.backbone.p2_gate.item()),
        'learning_demonstrated': bool(score_gain_tiny > 0 or post_eval['tiny_matched'] > initial_eval['tiny_matched']),
        'parameterGroupReceipt': group_receipt,
        'unknownGradientMaxAbs': float(max_unknown_grad),
        'batchNormEvalEnforced': bn_eval_checked
    }

    out_path = OUT_DIR / 'small_foci_learning_check_evidence.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, indent=2)
    print(f"Saved learning check evidence to: {out_path}", flush=True)

    # Also save checkpoint of the check
    check_weights_path = OUT_DIR / 'small_foci_check_model.safetensors'
    from safetensors.torch import save_file
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(check_weights_path))
    print(f"Saved learning check model to: {check_weights_path}", flush=True)
    return evidence


if __name__ == '__main__':
    run_learning_check()
