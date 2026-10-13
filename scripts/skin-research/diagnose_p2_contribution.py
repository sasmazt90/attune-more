#!/usr/bin/env python3
"""Diagnose and verify Item 3: P2 Branch Real Contribution, Gradient Flow, Gate Dynamics, and SimOTA Assignments."""

import sys
import json
import math
from pathlib import Path
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

from yolox_p2 import build_yolox_p2_model, load_baseline_weights_to_p2_model
from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from train_focused_local import yolo_batch
from prepare_canonical_validation_cache import load_canonical_validation_cache
from train_p2_focal_trial import extract_p2_predictions_fast, evaluate_canonical_validation

TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-focal-20261013'
EPOCH1_PATH = TRIAL_DIR / 'checkpoint-epoch-01-step-000248-1791909523358138100/model.safetensors'
EPOCH2_PATH = TRIAL_DIR / 'checkpoint-epoch-02-step-000496-1791911067067742300/model.safetensors'
BASELINE_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'


def diagnose_p2():
    print("=== ITEM 3 DIAGNOSTIC: P2 Real Contribution & Dynamics ===", flush=True)

    # 1. Gate and Weight Changes
    print("\n--- 1. Parameter Evolution (Initial -> Epoch 1 -> Epoch 2) ---", flush=True)
    m_init = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    load_baseline_weights_to_p2_model(m_init, BASELINE_PATH)
    init_state = m_init.state_dict()

    ep1_state = load_file(str(EPOCH1_PATH))
    ep2_state = load_file(str(EPOCH2_PATH))

    gate_init = init_state['backbone.p2_gate'].item()
    gate_ep1 = ep1_state['backbone.p2_gate'].item()
    gate_ep2 = ep2_state['backbone.p2_gate'].item()
    print(f"p2_gate: initial={gate_init:.6f} -> ep1={gate_ep1:.6f} -> ep2={gate_ep2:.6f}")

    p2_groups = {
        'FPN Top-Down P2 (reduce_conv2, C3_p2)': [k for k in ep1_state if k.startswith(('backbone.reduce_conv2', 'backbone.C3_p2'))],
        'PANet Bottom-Up P2 (bu_conv3, C3_n2)': [k for k in ep1_state if k.startswith(('backbone.bu_conv3', 'backbone.C3_n2'))],
        'P2 Prediction Head Stems/Convs (head.*.0)': [k for k in ep1_state if k.startswith(('head.stems.0', 'head.cls_convs.0', 'head.reg_convs.0'))],
        'P2 Prediction Class/Obj/Reg Heads (head.*_preds.0)': [k for k in ep1_state if k.startswith(('head.cls_preds.0', 'head.obj_preds.0', 'head.reg_preds.0'))],
        'Pre-trained P3/P4/P5 Heads (head.*.[1,2,3])': [k for k in ep1_state if any(k.startswith(f"head.{p}.{idx}") for p in ['stems', 'cls_convs', 'reg_convs', 'cls_preds', 'obj_preds', 'reg_preds'] for idx in [1, 2, 3])]
    }

    weight_evolution_report = {}
    for grp_name, keys in p2_groups.items():
        diff_ep1 = [torch.norm(ep1_state[k].float() - init_state[k].float()).item() for k in keys if k in init_state and ep1_state[k].is_floating_point()]
        diff_ep2 = [torch.norm(ep2_state[k].float() - init_state[k].float()).item() for k in keys if k in init_state and ep2_state[k].is_floating_point()]
        mean_diff1 = float(np.mean(diff_ep1)) if diff_ep1 else 0.0
        mean_diff2 = float(np.mean(diff_ep2)) if diff_ep2 else 0.0
        max_diff2 = float(np.max(diff_ep2)) if diff_ep2 else 0.0
        print(f"  {grp_name}: {len(keys)} params | mean diff ep1: {mean_diff1:.5f} | mean diff ep2: {mean_diff2:.5f} | max diff ep2: {max_diff2:.5f}")
        weight_evolution_report[grp_name] = {
            'paramCount': len(keys),
            'meanL2DeltaEpoch1': round(mean_diff1, 6),
            'meanL2DeltaEpoch2': round(mean_diff2, 6),
            'maxL2DeltaEpoch2': round(max_diff2, 6)
        }

    # Inspect specific Level 0 head parameters
    print(f"  head.obj_preds.0.weight L2 norm: ep1={torch.norm(ep1_state['head.obj_preds.0.weight']).item():.6f}, ep2={torch.norm(ep2_state['head.obj_preds.0.weight']).item():.6f}")
    print(f"  head.obj_preds.0.bias: ep1={ep1_state['head.obj_preds.0.bias'].item():.6f}, ep2={ep2_state['head.obj_preds.0.bias'].item():.6f}")
    print(f"  head.cls_preds.0.bias: ep1={ep1_state['head.cls_preds.0.bias'].item():.6f}, ep2={ep2_state['head.cls_preds.0.bias'].item():.6f}")

    # 2. Gradient Flow Check through P2
    print("\n--- 2. Measuring Gradient Flow through P2 Layers ---", flush=True)
    m_train = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    m_train.load_state_dict(ep1_state)
    focal_loss = SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0)
    m_train.head.obj_focal_loss = focal_loss
    m_train.train()
    for m in m_train.modules():
        if isinstance(m, torch.nn.BatchNorm2d):
            m.eval()

    # Load 4 training tiles
    pseudo_path = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
    with open(pseudo_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tr_rows = [r for r in data['rows'] if r['split'] == 'train']
    masks, weights = build_hole_preserved_negative_masks(tr_rows, pseudo_manifest_path=pseudo_path)
    train_tiles = acne_tiles_p2(tr_rows, masks, training=True)
    pos_tiles = [t for t in train_tiles if len(t['boxes']) > 0][:4]
    for t in pos_tiles:
        sha = t['row']['sha256']
        t['source_mask'] = masks[sha]
        t['source_weights'] = weights[sha]

    x, y = yolo_batch(pos_tiles)
    known_list, weight_list = [], []
    for item in pos_tiles:
        kt, wt = known_cells_p2(item['source_mask'], item['source_weights'], item['rect'], strides=(4, 8, 16, 32))
        known_list.append(kt)
        weight_list.append(wt)
    focal_loss.known = torch.cat(known_list, dim=0)
    focal_loss.boundary_weights = torch.cat(weight_list, dim=0)

    m_train.zero_grad()
    loss_dict = m_train(x, y)
    loss = loss_dict['total_loss']
    loss.backward()

    grad_report = {}
    print("  Gradient Norms across Architecture:")
    for grp_name, keys in p2_groups.items():
        norms = [p.grad.norm().item() for k, p in m_train.named_parameters() if k in keys and p.grad is not None]
        mean_norm = float(np.mean(norms)) if norms else 0.0
        max_norm = float(np.max(norms)) if norms else 0.0
        print(f"    {grp_name}: active grads={len(norms)}/{len(keys)} | mean norm={mean_norm:.6f} | max norm={max_norm:.6f}")
        grad_report[grp_name] = {'activeGradCount': len(norms), 'meanGradNorm': mean_norm, 'maxGradNorm': max_norm}

    gate_grad = m_train.backbone.p2_gate.grad
    print(f"    backbone.p2_gate.grad: {gate_grad.item() if gate_grad is not None else 'None'}")
    grad_report['backbone.p2_gate'] = float(gate_grad.item()) if gate_grad is not None else None

    # 3. Ground Truth Anchor Assignment Distribution across Strides [4, 8, 16, 32]
    print("\n--- 3. Measuring SimOTA Dynamic Assignment across Strides ---", flush=True)
    # Intercept SimOTA assignments across 20 positive batches
    strides_counts = {4: 0, 8: 0, 16: 0, 32: 0}
    total_assigned_gt = 0
    lesion_sizes_by_stride = {4: [], 8: [], 16: [], 32: []}

    # Count stride ranges:
    # Stride 4: 0 to 9216 (96*96)
    # Stride 8: 9216 to 9216+2304 = 11520 (48*48)
    # Stride 16: 11520 to 11520+576 = 12096 (24*24)
    # Stride 32: 12096 to 12240 (12*12)
    s4_end = 9216
    s8_end = 9216 + 2304
    s16_end = 9216 + 2304 + 576
    s32_end = 12240

    all_pos_tiles = [t for t in train_tiles if len(t['boxes']) > 0]
    for t in all_pos_tiles[:25]:
        t['source_mask'] = masks[t['row']['sha256']]
        t['source_weights'] = weights[t['row']['sha256']]
        bx_t, by_t = yolo_batch([t])
        kt, wt = known_cells_p2(t['source_mask'], t['source_weights'], t['rect'], strides=(4, 8, 16, 32))
        focal_loss.known = kt
        focal_loss.boundary_weights = wt
        with torch.no_grad():
            # Run get_losses to see matched_gt_inds and fg_mask
            # We hook into head.get_assignments
            fpn_outs = m_train.backbone(bx_t)
            # Run head
            head_out = m_train.head(fpn_outs, by_t)
            # Find which anchors had obj_target == 1
            # In yolox_p2, we can inspect fg_mask directly or obj_preds
            # Let's inspect where SimOTA placed positive targets:
            # We can replicate get_assignments or inspect the targets:
            # In YOLOX, we can trace by calling get_assignments directly!
            # Or inspect from get_losses
    
    # Direct SimOTA test on 50 training tiles
    print("  Sampling 50 training tiles for SimOTA stride assignment distribution...")
    sample_tiles = [t for t in all_pos_tiles if len(t['boxes']) > 0][:50]
    for t in sample_tiles:
        bx, by = yolo_batch([t])
        with torch.no_grad():
            fpn_outs = m_train.backbone(bx)
            # unpack head components
            outputs, origin_preds, x_shifts, y_shifts, expanded_strides = [], [], [], [], []
            for k, (stride, feat) in enumerate(zip(m_train.head.strides, fpn_outs)):
                cls_feat = m_train.head.cls_convs[k](m_train.head.stems[k](feat))
                reg_feat = m_train.head.reg_convs[k](m_train.head.stems[k](feat))
                cls_output = m_train.head.cls_preds[k](cls_feat)
                reg_output = m_train.head.reg_preds[k](reg_feat)
                obj_output = m_train.head.obj_preds[k](reg_feat)
                output = torch.cat([reg_output, obj_output.sigmoid(), cls_output.sigmoid()], 1)
                
                b, _, h_k, w_k = output.shape
                yv, xv = torch.meshgrid([torch.arange(h_k), torch.arange(w_k)], indexing="ij")
                grid = torch.stack((xv, yv), 2).view(1, 1, h_k, w_k, 2).type_as(output)
                output = output.view(b, 1, 6, h_k, w_k).permute(0, 1, 3, 4, 2).reshape(b, -1, 6)
                grid = grid.view(1, -1, 2)
                output[..., :2] = (output[..., :2] + grid) * stride
                output[..., 2:4] = torch.exp(output[..., 2:4]) * stride
                
                outputs.append(output)
                x_shifts.append(grid[:, :, 0])
                y_shifts.append(grid[:, :, 1])
                expanded_strides.append(torch.full((1, grid.shape[1]), stride, dtype=grid.dtype, device=grid.device))
            
            outputs = torch.cat(outputs, 1)
            x_shifts = torch.cat(x_shifts, 1)
            y_shifts = torch.cat(y_shifts, 1)
            expanded_strides = torch.cat(expanded_strides, 1)
            
            # Run get_assignments
            gt_boxes = by[0, :len(t['boxes']), 1:5]
            gt_classes = by[0, :len(t['boxes']), 0]
            
            _, fg_mask, _, matched_gt_inds, num_fg = m_train.head.get_assignments(
                0, len(t['boxes']), gt_boxes, gt_classes, outputs[0, :, :4],
                expanded_strides, x_shifts, y_shifts,
                outputs[:, :, 5:], outputs[:, :, 4:5]
            )
            
            assigned_strides = expanded_strides[0][fg_mask].cpu().numpy().tolist()
            for s in assigned_strides:
                s_int = int(s)
                strides_counts[s_int] = strides_counts.get(s_int, 0) + 1
                total_assigned_gt += 1
            
            for g_idx, s in zip(matched_gt_inds.cpu().numpy().tolist(), assigned_strides):
                box = gt_boxes[g_idx].cpu().numpy()
                dim = max(box[2], box[3]) # w, h
                lesion_sizes_by_stride[int(s)].append(float(dim))

    print(f"  Total Assigned Positive Anchors across 50 tiles: {total_assigned_gt}")
    for s, count in sorted(strides_counts.items()):
        pct = (count / max(total_assigned_gt, 1)) * 100
        mean_sz = float(np.mean(lesion_sizes_by_stride[s])) if lesion_sizes_by_stride[s] else 0.0
        print(f"    Stride {s:2d} (Feature size {384//s:2d}x{384//s:2d}): {count:4d} anchors ({pct:5.1f}%) | Mean GT box size: {mean_sz:.1f}px")

    # 4. P2 ON vs OFF Diagnostic Ablation on Validation Set
    print("\n--- 4. P2 ON vs OFF Diagnostic Ablation on Canonical Validation ---", flush=True)
    cached_images = load_canonical_validation_cache()

    # Model A: Full P2 Model (Epoch 1)
    net_full = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    net_full.load_state_dict(ep1_state, strict=True)
    val_full = evaluate_canonical_validation(net_full, cached_images, conf_thresholds=[0.30, 0.50, 0.70])

    # Model B: Ablation Model (P2 level 0 disabled - predictions zeroed)
    class YOLOX_P2_Disabled(nn.Module):
        def __init__(self, base_net):
            super().__init__()
            self.base_net = base_net
        def forward(self, x):
            out = self.base_net(x) # [B, 12240, 6]
            # Zero out scores for Level 0 (first 9216 anchors)
            out_clone = out.clone()
            out_clone[:, :9216, 4] = 0.0 # obj score 0
            out_clone[:, :9216, 5] = 0.0 # cls score 0
            return out_clone

    net_disabled = YOLOX_P2_Disabled(net_full)
    net_disabled.eval()
    val_p2_off = evaluate_canonical_validation(net_disabled, cached_images, conf_thresholds=[0.30, 0.50, 0.70])

    print("\nAblation Comparison (Full P2 vs P2 Level 0 Disabled):")
    ablation_report = {}
    for conf in ['0.3', '0.5', '0.7']:
        full_res = val_full[conf]
        off_res = val_p2_off[conf]
        diff_tp = full_res['inScopeTp50'] - off_res['inScopeTp50']
        diff_fp = full_res['negTotalFp'] - off_res['negTotalFp']
        print(f"  conf={conf}:")
        print(f"    Full P2 : In-Scope IoU50={full_res['inScopeTp50']}/53 (rec50={full_res['rec50']:.1%}) | Neg FP={full_res['negTotalFp']} ({full_res['fpPerPhoto']} FP/photo)")
        print(f"    P2-OFF  : In-Scope IoU50={off_res['inScopeTp50']}/53 (rec50={off_res['rec50']:.1%}) | Neg FP={off_res['negTotalFp']} ({off_res['fpPerPhoto']} FP/photo)")
        print(f"    Delta   : In-Scope TP50 Delta = {diff_tp:+d} | Neg FP Delta = {diff_fp:+d}")
        ablation_report[conf] = {
            'full_p2': full_res,
            'p2_level0_disabled': off_res,
            'deltaTp50': diff_tp,
            'deltaNegFp': diff_fp
        }

    # Save full diagnostic report
    out_diag_path = TRIAL_DIR / 'p2_contribution_and_ablation_diagnostic.json'
    full_report = {
        'p2GateEvolution': {
            'initial': gate_init,
            'epoch1': gate_ep1,
            'epoch2': gate_ep2,
            'deltaEpoch1': gate_ep1 - gate_init,
            'deltaEpoch2': gate_ep2 - gate_init
        },
        'weightEvolution': weight_evolution_report,
        'gradientFlow': grad_report,
        'simOtaAssignments': {
            'totalPositiveAnchorsSampled': total_assigned_gt,
            'distributionByStride': {str(s): {'count': c, 'percentage': round((c/max(total_assigned_gt, 1))*100, 2), 'meanGtBoxSizePx': round(float(np.mean(lesion_sizes_by_stride[s])), 2) if lesion_sizes_by_stride[s] else 0.0} for s, c in strides_counts.items()}
        },
        'ablationValidationP2OnVsOff': ablation_report
    }

    with open(out_diag_path, 'w', encoding='utf-8') as f:
        json.dump(full_report, f, indent=2)
    print(f"\nDiagnostic report successfully saved to: {out_diag_path}")


if __name__ == '__main__':
    diagnose_p2()
