#!/usr/bin/env python3
"""Controlled 3-Way Equal-Step Architecture & Loss Comparison (Item 4).

Configurations compared across exactly 20 identical batches (seed 20261013):
Configuration A: P3/P4/P5 Reference (Baseline weights, corrected data, KnownObjectnessBCE)
Configuration B: P2 Architecture    (Transferred weights, corrected data, KnownObjectnessBCE)
Configuration C: P2 + Focal Loss    (Transferred weights, corrected data, SigmoidFocalLoss + soft boundary weights)

Measures:
- Per-batch step time (CPU efficiency)
- Total loss, IoU regression loss, objectness loss (pos vs neg breakdown)
- Gradient flow on lateral and head convs
- Positive signal retention
"""

import sys
import json
import time
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
from yolox_numeric import install_bounds
from yolox_p2 import build_yolox_p2_model, load_baseline_weights_to_p2_model
from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from selected_yolox_loss import KnownObjectnessBCE, known_cells
from train_focused_local import yolo_batch

DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'
BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
PSEUDO_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
OUT_COMPARISON_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/initial-p2-3way-comparison.json'


def run_configuration_trial(config_name: str, batch_items_list: list, num_steps: int = 20) -> dict:
    print(f"\n--- Running Configuration: {config_name} ({num_steps} steps) ---", flush=True)
    torch.manual_seed(20261013)
    np.random.seed(20261013)

    # 1. Instantiate model
    if config_name == "Config_A_P345_Reference":
        net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
        install_bounds(net)
        weights = load_file(str(BASELINE_WEIGHTS))
        net.load_state_dict(weights)
        loss_fn = KnownObjectnessBCE()
        net.head.bcewithlog_loss = loss_fn
        is_p2 = False
    elif config_name == "Config_B_P2_BaseBCE":
        net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        load_baseline_weights_to_p2_model(net, BASELINE_WEIGHTS)
        loss_fn = KnownObjectnessBCE()
        net.head.bcewithlog_loss = loss_fn
        is_p2 = True
    elif config_name == "Config_C_P2_FocalLoss":
        net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        load_baseline_weights_to_p2_model(net, BASELINE_WEIGHTS)
        loss_fn = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
        net.head.bcewithlog_loss = loss_fn
        is_p2 = True
    else:
        raise ValueError(f"Unknown config: {config_name}")

    # Freeze stem and dark2, train lateral and head
    for k, p in net.named_parameters():
        p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))

    trainable_params = [p for p in net.parameters() if p.requires_grad]
    lr = 1e-5
    opt = torch.optim.AdamW(trainable_params, lr=lr, weight_decay=0.001)

    net.train()
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d):
            m.eval()

    step_records = []
    start_total_time = time.time()

    for step in range(num_steps):
        batch_items = batch_items_list[step]
        t_step_start = time.time()

        x, y = yolo_batch(batch_items)
        
        # Build known mask
        strides = (4, 8, 16, 32) if is_p2 else (8, 16, 32)
        known_list = []
        weight_list = []
        for item in batch_items:
            m = item['source_mask']
            w = item['source_weights']
            if is_p2:
                kt, wt = known_cells_p2(m, w, item['rect'], strides=strides)
            else:
                side_3 = known_cells(m, item['rect'], fully_reviewed=True, strides=strides)
                kt, wt = side_3.bool(), torch.ones_like(side_3).float()
            known_list.append(kt)
            weight_list.append(wt)

        loss_fn.known = torch.cat(known_list, dim=0)
        if hasattr(loss_fn, 'boundary_weights'):
            loss_fn.boundary_weights = torch.cat(weight_list, dim=0)

        opt.zero_grad()
        loss_dict = net(x, y)
        total_loss = loss_dict['total_loss']
        total_loss.backward()

        # Check gradient norm on key layers
        grad_norms = {}
        for name, p in net.named_parameters():
            if p.grad is not None and ('head.reg_convs' in name or 'lateral' in name):
                grad_norms[name] = p.grad.norm().item()

        torch.nn.utils.clip_grad_norm_(trainable_params, max_norm=5.0)
        opt.step()

        elapsed_step = time.time() - t_step_start
        rec = {
            'step': step,
            'totalLoss': round(total_loss.item(), 4),
            'iouLoss': round(loss_dict['iou_loss'].item(), 4),
            'confLoss': round(loss_dict['conf_loss'].item(), 4),
            'clsLoss': round(loss_dict['cls_loss'].item(), 4),
            'numFg': round(loss_dict['num_fg'], 2),
            'stepTimeMs': round(elapsed_step * 1000, 1),
            'topGradNorm': round(max(grad_norms.values()) if grad_norms else 0.0, 4)
        }
        if hasattr(loss_fn, 'last_metrics') and loss_fn.last_metrics:
            rec['posObjLoss'] = round(loss_fn.last_metrics.get('posObjLoss', 0.0), 5)
            rec['negObjLoss'] = round(loss_fn.last_metrics.get('negObjLoss', 0.0), 5)
        step_records.append(rec)

        if step % 5 == 0 or step == num_steps - 1:
            print(f"  Step {step:2d}/{num_steps} | Loss: {rec['totalLoss']:.4f} (IoU: {rec['iouLoss']:.4f}, Conf: {rec['confLoss']:.4f}) | stepTime: {rec['stepTimeMs']:.1f}ms", flush=True)

    total_duration = time.time() - start_total_time
    avg_step_time = np.mean([r['stepTimeMs'] for r in step_records])
    initial_loss = step_records[0]['totalLoss']
    final_loss = step_records[-1]['totalLoss']

    return {
        'configName': config_name,
        'numSteps': num_steps,
        'totalDurationSeconds': round(total_duration, 2),
        'avgStepTimeMs': round(avg_step_time, 1),
        'initialLoss': initial_loss,
        'finalLoss': final_loss,
        'lossReductionRatio': round(final_loss / max(initial_loss, 1e-4), 4),
        'finalConfLoss': step_records[-1]['confLoss'],
        'finalIouLoss': step_records[-1]['iouLoss'],
        'finalNumFg': step_records[-1]['numFg'],
        'steps': step_records
    }


def main():
    print("=== Controlled 3-Way Architecture & Loss Comparison ===", flush=True)
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tr = [r for r in data['rows'] if r['split'] == 'train']

    # Build hole-preserved masks
    masks, weights = build_hole_preserved_negative_masks(tr, pseudo_manifest_path=PSEUDO_PATH)
    tiles = acne_tiles_p2(tr, masks, training=True)

    # Attach mask references to tiles
    for t in tiles:
        sha = t['row']['sha256']
        t['source_mask'] = masks[sha]
        t['source_weights'] = weights[sha]

    print(f"Dataset active training tiles: {len(tiles)}")

    # Pre-select fixed 20 batches of size 4
    np.random.seed(20261013)
    order = list(range(len(tiles)))
    np.random.shuffle(order)
    
    batch_size = 4
    num_steps = 20
    fixed_batches = []
    for step in range(num_steps):
        indices = order[step * batch_size : (step + 1) * batch_size]
        fixed_batches.append([tiles[i] for i in indices])

    # Run 3 configurations
    res_a = run_configuration_trial("Config_A_P345_Reference", fixed_batches, num_steps=num_steps)
    res_b = run_configuration_trial("Config_B_P2_BaseBCE", fixed_batches, num_steps=num_steps)
    res_c = run_configuration_trial("Config_C_P2_FocalLoss", fixed_batches, num_steps=num_steps)

    comparison_summary = {
        'trialTitle': 'Initial Controlled 3-Way Architecture & Loss Comparison',
        'dataset': {
            'trainImages': len(tr),
            'activeTiles': len(tiles),
            'batchSize': batch_size,
            'stepsEvaluated': num_steps
        },
        'comparisonResults': {
            'Config_A_P345_Reference': res_a,
            'Config_B_P2_BaseBCE': res_b,
            'Config_C_P2_FocalLoss': res_c
        },
        'crossConfigComparison': {
            'stepTimeMs': {
                'Config_A': res_a['avgStepTimeMs'],
                'Config_B': res_b['avgStepTimeMs'],
                'Config_C': res_c['avgStepTimeMs'],
                'p2OverheadPercent': round(((res_c['avgStepTimeMs'] - res_a['avgStepTimeMs']) / res_a['avgStepTimeMs']) * 100, 1)
            },
            'lossProgression': {
                'Config_A_final': res_a['finalLoss'],
                'Config_B_final': res_b['finalLoss'],
                'Config_C_final': res_c['finalLoss']
            },
            'iouRetention': {
                'Config_A_iou': res_a['finalIouLoss'],
                'Config_B_iou': res_b['finalIouLoss'],
                'Config_C_iou': res_c['finalIouLoss']
            }
        }
    }

    OUT_COMPARISON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_COMPARISON_PATH, 'w', encoding='utf-8') as f:
        json.dump(comparison_summary, f, indent=2)

    print(f"\n3-Way comparison summary saved to: {OUT_COMPARISON_PATH}", flush=True)
    print("\n--- Summary Comparison ---")
    print(f"Config A (P3/P4/P5 Ref):  StepTime: {res_a['avgStepTimeMs']}ms | Final Loss: {res_a['finalLoss']:.4f} (IoU: {res_a['finalIouLoss']:.4f})")
    print(f"Config B (P2 + BaseBCE):  StepTime: {res_b['avgStepTimeMs']}ms | Final Loss: {res_b['finalLoss']:.4f} (IoU: {res_b['finalIouLoss']:.4f})")
    print(f"Config C (P2 + FocalLoss): StepTime: {res_c['avgStepTimeMs']}ms | Final Loss: {res_c['finalLoss']:.4f} (IoU: {res_c['finalIouLoss']:.4f})")


if __name__ == '__main__':
    main()
