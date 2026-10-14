#!/usr/bin/env python3
"""Short Learning Control (120 steps) on Fixed Native TRAIN Pilot Group.

Integrity Rules (User Directives):
1. Fixed Native Tiles (No Jitter Bug):
   - Uses exact native 384x384 tiles without translation jitter.
   - Crop, GT boxes, clean mask, and boundary weights are 100% bit-exact spatially aligned.
2. 1-to-1 Bipartite Greedy Matching:
   - Evaluates both Step 0 and Step 120 with strict 1-to-1 bipartite matching.
   - Clean skin FP measured strictly on verified clean skin (mask > 0); UNKNOWN skin is excluded.
3. Rigorous Learning Verification Gate:
   - learningVerified is True IF AND ONLY IF:
     * tp50_120 > tp50_0 OR (tp50_120 == tp50_0 and avg_iou_120 > avg_iou_0 and clean_fp_120 <= clean_fp_0)
     * clean_fp_120 <= clean_fp_0
     * tiny_120 >= tiny_0 and small_120 >= small_0 and med_120 >= med_0
     * all 4 parameter groups have verified non-zero, finite gradients.
4. Gradient Flow vs Weight Movement Separation:
   - Gradient norms (max, avg, finite/nonzero ratio) recorded right after backward pass.
   - Parameter weight deltas recorded separately after optimizer step.
5. Comprehensive Ledger:
   - Records transition status (RETAINED, GAINED, LOST, PERSISTENTLY_MISSED) for all 104 GT lesions.
   - Saves audit receipt: audit-results/acne-pilot-diagnosis-20261014/pilot_finetune_receipt.json.
"""

import sys
import os
import json
import time
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple, Any
import numpy as np
import cv2
import torch
import torch.nn as nn
import torchvision

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model, build_finetune_param_groups
from model_identity import TRUE_BASELINE_EPOCH02_PATH, TRUE_BASELINE_EPOCH02_SHA, load_verified_model
from negative_mask_builder import build_hole_preserved_negative_masks, known_cells_p2
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from diagnose_p2_pilot_learning import build_pilot_set, evaluate_pilot_mode
from heavy_job_lock import heavy_job_guard

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
OUT_DIR = ROOT / 'audit-results/acne-pilot-diagnosis-20261014'


def run_pilot():
    print("=" * 80)
    print("SHORT LEARNING CONTROL: 120-STEP FULL FINE-TUNING ON NATIVE TRAIN PILOT")
    print("=" * 80)

    seed = 20261014
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load verified baseline model
    net, model_sha = load_verified_model(TRUE_BASELINE_EPOCH02_PATH, expected_sha=TRUE_BASELINE_EPOCH02_SHA)
    print(f"Loaded verified baseline model: {model_sha}")

    # Ensure all BatchNorm modules are in eval mode (fixed running statistics)
    for m in net.modules():
        if isinstance(m, nn.BatchNorm2d):
            m.eval()

    # 2. Calibrate Level 0 (P2 stride 4)
    with torch.no_grad():
        net.backbone.p2_gate.zero_()
        prior_bias = -math.log((1.0 - 0.01) / 0.01)
        net.head.obj_preds[0].bias.fill_(prior_bias)
        net.head.cls_preds[0].bias.fill_(prior_bias)
        net.head.reg_preds[0].bias.zero_()
        net.head.reg_preds[0].bias[2:4].fill_(math.log(2.0))

    # 3. Multi-tier Parameter Groups
    param_groups, partition_receipt = build_finetune_param_groups(
        net,
        lr_p2=1.5e-4,
        lr_heads=3.0e-5,
        lr_pafpn=1.5e-5,
        lr_backbone=5.0e-6,
        unfreeze_backbone=True
    )
    print(f"Configured {partition_receipt['totalTrainableTensors']} trainable tensors ({partition_receipt['totalTrainableParams']:,} params):")
    print(f"  Level 0 P2 Task:   {partition_receipt['level0_p2_task']['paramCount']:,} params (lr={partition_receipt['level0_p2_task']['lr']:.1e})")
    print(f"  Pretrained Heads:  {partition_receipt['pretrained_heads']['paramCount']:,} params (lr={partition_receipt['pretrained_heads']['lr']:.1e})")
    print(f"  PAFPN Fusion:      {partition_receipt['pafpn_fusion']['paramCount']:,} params (lr={partition_receipt['pafpn_fusion']['lr']:.1e})")
    print(f"  Backbone (dark2-5):{partition_receipt['backbone_adaptation']['paramCount']:,} params (lr={partition_receipt['backbone_adaptation']['lr']:.1e})")

    # 4. Focal Loss Setup
    focal_loss = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
    net.head.obj_focal_loss = focal_loss

    # 5. Load Pilot Set
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    train_rows = [r for r in data['rows'] if r['split'] == 'train']
    masks, weights = build_hole_preserved_negative_masks(train_rows)
    pilot_tiles = build_pilot_set(train_rows, masks, weights)

    # 6. Snapshot initial weights of key representative layers
    track_layers = {
        'p2_head_reg': net.head.reg_preds[0].weight.detach().clone(),
        'p2_head_obj': net.head.obj_preds[0].weight.detach().clone(),
        'upper_head_p3_reg': net.head.reg_preds[1].weight.detach().clone(),
        'pafpn_C3_p3': net.backbone.C3_p3.conv1.conv.weight.detach().clone(),
        'backbone_dark3': net.backbone.backbone.dark3[0].conv.weight.detach().clone(),
        'p2_gate': net.backbone.p2_gate.detach().clone()
    }

    # 7. Evaluate Step-0 Pilot Performance under strict 1-to-1 bipartite matching
    print("\n--- Evaluating Step 0 (Before Fine-Tuning) ---")
    step0_res = evaluate_pilot_mode(net, pilot_tiles, mode='combined', conf_thresh=0.30)
    bs0 = step0_res['bySize']
    print(f"Step 0: IoU50: {step0_res['tp50']}/{step0_res['totalGt']} ({step0_res['rec50']:.1%}) | "
          f"Tiny: {bs0['tiny_less_8px']['tp50']}/{bs0['tiny_less_8px']['gt']} | "
          f"Small: {bs0['small_8_to_16px']['tp50']}/{bs0['small_8_to_16px']['gt']} | "
          f"Med: {bs0['medium_16_to_32px']['tp50']}/{bs0['medium_16_to_32px']['gt']} | "
          f"Clean FP: {step0_res['cleanFpCount']} | Avg IoU: {step0_res['avgMatchedIoU']:.3f}")

    # 8. Setup Optimizer and Scheduler (120 steps)
    opt = torch.optim.AdamW(param_groups)
    total_steps = 120
    warmup_steps = 20
    batch_size = 4

    def lr_lambda(step):
        if step < warmup_steps:
            return float(step + 1) / float(max(1, warmup_steps))
        progress = float(step - warmup_steps) / float(max(1, total_steps - warmup_steps))
        return 0.5 * (1.0 + math.cos(math.pi * progress))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda)

    # 9. Training Loop on Pilot (Exact Native Tiles - ZERO Jitter Bug)
    print(f"\nStarting {total_steps}-step fine-tuning on Pilot ({len(pilot_tiles)} native tiles)...")
    net.train()
    for m in net.modules():
        if isinstance(m, nn.BatchNorm2d):
            m.eval()

    loss_history = []
    gradient_telemetry = {}
    t0 = time.time()

    for step in range(1, total_steps + 1):
        batch_items = random.sample(pilot_tiles, batch_size)

        images = []
        targets = torch.zeros((len(batch_items), max(max(len(t['boxes']) for t in batch_items), 1), 5), dtype=torch.float32)

        for bi, t in enumerate(batch_items):
            full_bgr = t['preloaded_bgr']
            a, b, endx, endy = t['rect']

            # Fixed Native Tile (Zero jitter, exact spatial alignment with mask and weights)
            tile = np.full((384, 384, 3), 114, dtype=np.uint8)
            crop = full_bgr[b:endy, a:endx]
            tile[:crop.shape[0], :crop.shape[1]] = crop
            images.append(torch.from_numpy(tile.transpose(2, 0, 1)).float())

            for bj, (gx0, gy0, gx1, gy1) in enumerate(t.get('boxes', [])):
                targets[bi, bj] = torch.tensor([0, (gx0 + gx1) / 2.0, (gy0 + gy1) / 2.0, gx1 - gx0, gy1 - gy0])

        x = torch.stack(images)
        y = targets

        known_list = []
        weight_list = []
        for item in batch_items:
            kt, wt = known_cells_p2(item['clean_mask'], item['mask_weight'], item['rect'], strides=(4, 8, 16, 32))
            known_list.append(kt)
            weight_list.append(wt)

        focal_loss.known = torch.cat(known_list, dim=0)
        focal_loss.boundary_weights = torch.cat(weight_list, dim=0)

        opt.zero_grad()
        loss_dict = net(x, y)
        total_loss = loss_dict['total_loss']
        assert torch.isfinite(total_loss), f"Non-finite loss at step {step}: {total_loss.item()}"
        total_loss.backward()

        # Audit and record gradient norms per group (Separating Gradient Flow from Weight Decay)
        if step in (1, 25, 50, 75, 100, total_steps):
            step_grads = {}
            for g in opt.param_groups:
                gname = g['name']
                finite_count = sum(1 for p in g['params'] if p.grad is not None and torch.isfinite(p.grad).all() and p.grad.abs().max() > 0)
                norms = [p.grad.norm().item() for p in g['params'] if p.grad is not None]
                step_grads[gname] = {
                    'totalTensors': len(g['params']),
                    'finiteNonzeroCount': finite_count,
                    'maxNorm': max(norms) if norms else 0.0,
                    'meanNorm': float(np.mean(norms)) if norms else 0.0,
                    'allGradientsFiniteNonzero': (finite_count == len(g['params']))
                }
            gradient_telemetry[f"step_{step}"] = step_grads

        torch.nn.utils.clip_grad_norm_(net.parameters(), max_norm=5.0)
        opt.step()
        sched.step()

        loss_history.append(total_loss.item())

        if step % 20 == 0 or step == total_steps:
            avg_l = float(np.mean(loss_history[-20:]))
            lr_p2_now = opt.param_groups[0]['lr']
            print(f"  Step {step:3d}/{total_steps} | Loss: {total_loss.item():.4f} (avg20: {avg_l:.4f}) | "
                  f"lr_p2: {lr_p2_now:.2e} | p2_gate: {net.backbone.p2_gate.item():.4f} | elapsed: {time.time()-t0:.1f}s", flush=True)

    # 10. Compute Actual Weight Movement
    weight_deltas = {}
    for lname, w_init in track_layers.items():
        if lname == 'p2_head_reg':
            w_final = net.head.reg_preds[0].weight
        elif lname == 'p2_head_obj':
            w_final = net.head.obj_preds[0].weight
        elif lname == 'upper_head_p3_reg':
            w_final = net.head.reg_preds[1].weight
        elif lname == 'pafpn_C3_p3':
            w_final = net.backbone.C3_p3.conv1.conv.weight
        elif lname == 'backbone_dark3':
            w_final = net.backbone.backbone.dark3[0].conv.weight
        elif lname == 'p2_gate':
            w_final = net.backbone.p2_gate
        delta = (w_final.detach() - w_init).norm().item()
        weight_deltas[lname] = delta

    print("\n--- Parameter Weight Deltas Across Layer Groups ---")
    for lname, d in weight_deltas.items():
        print(f"  {lname:20s}: ||W_final - W_init|| = {d:.6f}")

    # 11. Evaluate Step-120 Pilot Performance under strict 1-to-1 bipartite matching
    print("\n--- Evaluating Step 120 (After Fine-Tuning) ---")
    step120_res = evaluate_pilot_mode(net, pilot_tiles, mode='combined', conf_thresh=0.30)
    bs120 = step120_res['bySize']
    print(f"Step 120: IoU50: {step120_res['tp50']}/{step120_res['totalGt']} ({step120_res['rec50']:.1%}) | "
          f"Tiny: {bs120['tiny_less_8px']['tp50']}/{bs120['tiny_less_8px']['gt']} | "
          f"Small: {bs120['small_8_to_16px']['tp50']}/{bs120['small_8_to_16px']['gt']} | "
          f"Med: {bs120['medium_16_to_32px']['tp50']}/{bs120['medium_16_to_32px']['gt']} | "
          f"Clean FP: {step120_res['cleanFpCount']} | Avg IoU: {step120_res['avgMatchedIoU']:.3f}")

    # Also evaluate P2-only after fine-tuning
    p2_only_120 = evaluate_pilot_mode(net, pilot_tiles, mode='p2_only', conf_thresh=0.30)
    print(f"Step 120 (P2 Only): IoU50: {p2_only_120['tp50']}/{p2_only_120['totalGt']} ({p2_only_120['rec50']:.1%}) | "
          f"Tiny: {p2_only_120['bySize']['tiny_less_8px']['tp50']} | Small: {p2_only_120['bySize']['small_8_to_16px']['tp50']} | "
          f"Clean FP: {p2_only_120['cleanFpCount']}")

    # 12. Build Target-by-Target Transition Ledger (All 104 GT lesions)
    step0_map = {d['id']: d for d in step0_res['targetDetails']}
    step120_map = {d['id']: d for d in step120_res['targetDetails']}

    transition_ledger = []
    transition_counts = {'RETAINED': 0, 'GAINED': 0, 'LOST': 0, 'PERSISTENTLY_MISSED': 0}

    for tid, d0 in step0_map.items():
        d120 = step120_map.get(tid)
        m0 = d0['matched_50']
        m120 = d120['matched_50'] if d120 else False

        if m0 and m120:
            status = 'RETAINED'
        elif not m0 and m120:
            status = 'GAINED'
        elif m0 and not m120:
            status = 'LOST'
        else:
            status = 'PERSISTENTLY_MISSED'

        transition_counts[status] += 1
        transition_ledger.append({
            'targetId': tid,
            'category': d0['category'],
            'dim': d0['dim'],
            'status': status,
            'step0': {'matched50': m0, 'iou': d0['matched_iou'], 'score': d0['score']},
            'step120': {'matched50': m120, 'iou': d120['matched_iou'] if d120 else 0.0, 'score': d120['score'] if d120 else 0.0}
        })

    print(f"\n--- Target Transition Summary ({len(transition_ledger)} lesions) ---")
    print(f"  RETAINED:             {transition_counts['RETAINED']}")
    print(f"  GAINED:               {transition_counts['GAINED']}")
    print(f"  LOST:                 {transition_counts['LOST']}")
    print(f"  PERSISTENTLY_MISSED:  {transition_counts['PERSISTENTLY_MISSED']}")

    # 13. Objective Learning Verification Evaluation (Item 3 & 4)
    # Verification Rules:
    # 1. Total recall strictly improves or ties with higher average IoU and no FP increase
    rule1_recall = (step120_res['tp50'] > step0_res['tp50']) or (
        step120_res['tp50'] == step0_res['tp50'] and
        step120_res['avgMatchedIoU'] > step0_res['avgMatchedIoU'] and
        step120_res['cleanFpCount'] <= step0_res['cleanFpCount']
    )
    # 2. Clean skin false positives do not worsen
    rule2_fp = (step120_res['cleanFpCount'] <= step0_res['cleanFpCount'])
    # 3. No category degradation
    rule3_categories = (
        bs120['tiny_less_8px']['tp50'] >= bs0['tiny_less_8px']['tp50'] and
        bs120['small_8_to_16px']['tp50'] >= bs0['small_8_to_16px']['tp50'] and
        bs120['medium_16_to_32px']['tp50'] >= bs0['medium_16_to_32px']['tp50']
    )
    # 4. Gradients confirmed in all parameter groups
    rule4_gradients = all(
        telemetry['allGradientsFiniteNonzero']
        for telemetry in gradient_telemetry.get('step_120', gradient_telemetry.get(f'step_{total_steps}', {})).values()
    )

    learning_verified = bool(rule1_recall and rule2_fp and rule3_categories and rule4_gradients)

    receipt = {
        'timestamp': time.time(),
        'notice': 'TRAIN LEARNING CONTROL FOR VERIFICATION OF MEMORIZATION & ADAPTATION; NOT A VALIDATION REPORT',
        'startingModelSha256': TRUE_BASELINE_EPOCH02_SHA,
        'totalSteps': total_steps,
        'durationSec': round(time.time() - t0, 1),
        'partitionReceipt': partition_receipt,
        'step0': step0_res,
        'step120': step120_res,
        'step120_p2_only': p2_only_120,
        'gradientTelemetry': gradient_telemetry,
        'weightDeltas': weight_deltas,
        'finalP2Gate': net.backbone.p2_gate.item(),
        'targetTransitions': transition_counts,
        'transitionLedger': transition_ledger,
        'verificationRules': {
            'rule1_recall': rule1_recall,
            'rule2_fp': rule2_fp,
            'rule3_categories': rule3_categories,
            'rule4_gradients': rule4_gradients,
            'learningVerified': learning_verified
        }
    }

    out_file = OUT_DIR / 'pilot_finetune_receipt.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2)

    print("\n" + "=" * 80)
    print(f"PILOT LEARNING CONTROL RESULT: {'VERIFIED (READY FOR FULL TRAINING)' if learning_verified else 'NOT VERIFIED'}")
    print(f"  Rule 1 (Recall/Localization): {rule1_recall} (Tp50: {step0_res['tp50']} -> {step120_res['tp50']}, AvgIoU: {step0_res['avgMatchedIoU']:.3f} -> {step120_res['avgMatchedIoU']:.3f})")
    print(f"  Rule 2 (Clean Skin FP):      {rule2_fp} (FP: {step0_res['cleanFpCount']} -> {step120_res['cleanFpCount']})")
    print(f"  Rule 3 (Size Retention):     {rule3_categories} (Tiny: {bs0['tiny_less_8px']['tp50']}->{bs120['tiny_less_8px']['tp50']}, Small: {bs0['small_8_to_16px']['tp50']}->{bs120['small_8_to_16px']['tp50']}, Med: {bs0['medium_16_to_32px']['tp50']}->{bs120['medium_16_to_32px']['tp50']})")
    print(f"  Rule 4 (Gradient Flow):      {rule4_gradients}")
    print(f"Receipt written to: {out_file}")
    print("=" * 80)


def main():
    with heavy_job_guard("pilot-finetune"):
        run_pilot()


if __name__ == '__main__':
    main()
