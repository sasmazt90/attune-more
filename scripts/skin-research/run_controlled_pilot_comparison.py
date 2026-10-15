#!/usr/bin/env python3
"""Run Controlled Single-Variable Pilot Training: Control (IoU Loss) vs Candidate (GIoU Loss).

Directives:
1. Hypothesis: Bounding box placement / localization regression formulation.
   - Arm A (Control): Existing IoU loss (loss_type="iou")
   - Arm B (Candidate): GIoU loss (loss_type="giou")
2. Strictly identical conditions:
   - Initial weights: EXACT Step 0 checkpoint (model.safetensors, sha: 18e94a95...)
   - Exactly 150 optimizer steps each (batch_size=4, 600 tiles).
   - Identical batch sequence and data from pilot_train_shas (held-out control is NOT touched).
   - Identical learning rates, scheduler (30 warmup steps, cosine decay), seed (20261015).
   - Identical architecture, P2 geometry constraints, Sigmoid Focal Objectness Loss (alpha=0.25, gamma=2.0).
   - reg_weight = 5.0 (NEVER multiplied twice).
   - Zero jitter, zero new augmentations.
3. Sequential execution with memory management (gc.collect).
4. Distinct output directories (no overwriting).
"""

import sys
import gc
import json
import math
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any

import cv2
import numpy as np
import torch
import torch.nn as nn
from safetensors.torch import load_file, save_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model, build_finetune_param_groups
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from negative_mask_builder import build_hole_preserved_negative_masks, known_cells_p2

TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014'
STEP0_PATH = TRIAL_DIR / 'checkpoint-epoch-00-step-000000-1792014463030016700/model.safetensors'

COHORT_PATH = ROOT / 'audit-results/acne-pilot-giou-comparison-20261015/controlled_train_cohort.json'
DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
OUT_DIR = ROOT / 'audit-results/acne-pilot-giou-comparison-20261015'


def prepare_training_batches(num_steps=150, batch_size=4):
    print("Preparing 150 training mini-batches from pilot_train_shas...")
    with open(COHORT_PATH, 'r', encoding='utf-8') as f:
        cohort = json.load(f)
    train_tiles = cohort['pilotTrainTiles']
    print(f"Total available pilot train tiles: {len(train_tiles)}")

    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    train_rows = {r['sha256']: r for r in data['rows'] if r.get('split') == 'train'}

    # Build hole preserved negative masks
    all_train_rows = list(train_rows.values())
    masks, weights = build_hole_preserved_negative_masks(all_train_rows)

    # Order tiles deterministically with seed 20261015
    rng = np.random.RandomState(20261015)
    order = list(range(len(train_tiles)))
    rng.shuffle(order)

    # Need 150 * 4 = 600 tiles
    total_needed = num_steps * batch_size
    selected_indices = order[:total_needed]

    batches = []
    needed_shas = set(train_tiles[i]['imageSha256'] for i in selected_indices)

    # Preload only needed photos on-demand and crop tiles
    img_cache = {}
    for sha in needed_shas:
        r = train_rows[sha]
        path = r.get('absolutePath') or str(LIVE_TEST / r['path'])
        bgr = cv2.imread(path)
        assert bgr is not None, f"Could not read {path}"
        img_cache[sha] = bgr

    print(f"Preloaded {len(img_cache)} images. Pre-cropping {total_needed} tiles into memory...")

    prebuilt_tiles = []
    for idx in selected_indices:
        t = train_tiles[idx]
        sha = t['imageSha256']
        full_bgr = img_cache[sha]
        a, b, endx, endy = t['rect']
        tile = np.full((384, 384, 3), 114, dtype=np.uint8)
        crop = full_bgr[b:endy, a:endx]
        tile[:crop.shape[0], :crop.shape[1]] = crop

        kt, wt = known_cells_p2(masks[sha], weights[sha], t['rect'], strides=(4, 8, 16, 32))
        boxes = t.get('boxes', [])

        prebuilt_tiles.append({
            'tile': tile,
            'known': kt,
            'weight': wt,
            'boxes': boxes
        })

    # Free full BGR images to conserve RAM
    del img_cache
    gc.collect()

    for s in range(num_steps):
        batches.append(prebuilt_tiles[s * batch_size : (s + 1) * batch_size])

    print(f"Prepared {len(batches)} mini-batches ({total_needed} tiles ready in memory).")
    return batches


def run_single_arm(arm_name: str, loss_type: str, batches: list, out_dir: Path):
    print("\n" + "=" * 80)
    print(f"STARTING 150-STEP PILOT: ARM [{arm_name.upper()}] (loss_type='{loss_type}')")
    print("=" * 80)

    out_dir.mkdir(parents=True, exist_ok=True)
    chk_file = out_dir / 'model.safetensors'

    torch.manual_seed(20261015)
    np.random.seed(20261015)

    # 1. Build model with exact loss_type
    net = build_yolox_p2_model(loss_type=loss_type)
    net.load_state_dict(load_file(str(STEP0_PATH)), strict=True)
    focal_loss = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
    net.head.obj_focal_loss = focal_loss

    # 2. Configure Optimizer and Schedule
    param_groups, partition_receipt = build_finetune_param_groups(
        net,
        lr_p2=1.5e-4,
        lr_heads=3.0e-5,
        lr_pafpn=1.5e-5,
        lr_backbone=5.0e-6,
        unfreeze_backbone=True
    )
    opt = torch.optim.AdamW(param_groups)

    num_steps = len(batches)
    warmup_steps = 30

    def lr_lambda(step):
        if step < warmup_steps:
            return float(step + 1) / float(max(1, warmup_steps))
        progress = float(step - warmup_steps) / float(max(1, num_steps - warmup_steps))
        return 0.5 * (1.0 + math.cos(math.pi * progress))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda)

    # Keep BatchNorm in eval mode
    net.train()
    for m in net.modules():
        if isinstance(m, nn.BatchNorm2d):
            m.eval()

    step_logs = []
    t0 = time.time()

    for step, b_items in enumerate(batches):
        images = []
        targets = torch.zeros((len(b_items), max(max(len(t['boxes']) for t in b_items), 1), 5), dtype=torch.float32)

        for bi, item in enumerate(b_items):
            images.append(torch.from_numpy(item['tile'].transpose(2, 0, 1)).float())
            for bj, (x0, y0, x1, y1) in enumerate(item['boxes']):
                targets[bi, bj] = torch.tensor([0, (x0 + x1) / 2.0, (y0 + y1) / 2.0, x1 - x0, y1 - y0])

        x = torch.stack(images)
        y = targets

        focal_loss.known = torch.cat([it['known'] for it in b_items], dim=0)
        focal_loss.boundary_weights = torch.cat([it['weight'] for it in b_items], dim=0)

        opt.zero_grad()
        loss_dict = net(x, y)
        total_loss = loss_dict['total_loss']

        assert torch.isfinite(total_loss), f"Non-finite loss at step {step}: {total_loss.item()}"
        total_loss.backward()

        torch.nn.utils.clip_grad_norm_(net.parameters(), max_norm=5.0)
        opt.step()
        sched.step()

        raw_loc = float(net.head.last_raw_loc_loss.item())
        weighted_loc = float(net.head.last_weighted_loc_loss.item())
        loss_obj = float(loss_dict['conf_loss'].item())
        loss_cls = float(loss_dict['cls_loss'].item())
        tot_val = float(total_loss.item())

        if (step + 1) % 10 == 0 or step == 0 or (step + 1) == num_steps:
            elapsed = time.time() - t0
            print(f"[{arm_name}] Step {step+1:3d}/{num_steps:3d} | Total: {tot_val:.4f} | Raw Loc ({loss_type}): {raw_loc:.4f} (5x: {weighted_loc:.4f}) | Obj: {loss_obj:.4f} | Cls: {loss_cls:.4f} | Elapsed: {elapsed:.1f}s")

        step_logs.append({
            'step': step + 1,
            'totalLoss': tot_val,
            'rawLocLoss': raw_loc,
            'weightedLocLoss': weighted_loc,
            'lossObj': loss_obj,
            'lossCls': loss_cls,
            'lr_p2': sched.get_last_lr()[0]
        })

    total_time = time.time() - t0
    print(f"\nArm [{arm_name}] finished 150 steps in {total_time:.1f}s.")

    # Save trained checkpoint
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(chk_file))
    print(f"Saved checkpoint to {chk_file}")

    receipt = {
        'armName': arm_name,
        'lossType': loss_type,
        'numSteps': num_steps,
        'initialWeights': str(STEP0_PATH.name),
        'checkpointSha256': None,  # Will compute below
        'totalElapsedSeconds': total_time,
        'stepLogs': step_logs,
        'finalLoss': step_logs[-1]
    }

    import hashlib
    chk_sha = hashlib.sha256(chk_file.read_bytes()).hexdigest()
    receipt['checkpointSha256'] = chk_sha

    with open(out_dir / 'training_receipt.json', 'w', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2)

    # Clean up memory
    del net, opt, sched, focal_loss
    gc.collect()

    return receipt


def main():
    print("=" * 90)
    print("STARTING CONTROLLED SINGLE-VARIABLE PILOT STUDY: IOU VS GIOU")
    print("=" * 90)

    # 1. Prepare identical training mini-batches
    batches = prepare_training_batches(num_steps=150, batch_size=4)

    # 2. Arm A: Control (IoU)
    control_dir = OUT_DIR / 'pilot-control-iou'
    receipt_control = run_single_arm("Control (IoU Loss)", "iou", batches, control_dir)

    # 3. Arm B: Candidate (GIoU)
    candidate_dir = OUT_DIR / 'pilot-candidate-giou'
    receipt_candidate = run_single_arm("Candidate (GIoU Loss)", "giou", batches, candidate_dir)

    print("\n" + "=" * 90)
    print("PILOT TRAINING COMPLETE FOR BOTH ARMS")
    print("=" * 90)
    print(f"Control (IoU) Final Loss:   Total={receipt_control['finalLoss']['totalLoss']:.4f}, Raw Loc={receipt_control['finalLoss']['rawLocLoss']:.4f}")
    print(f"Candidate (GIoU) Final Loss: Total={receipt_candidate['finalLoss']['totalLoss']:.4f}, Raw Loc={receipt_candidate['finalLoss']['rawLocLoss']:.4f}")


if __name__ == '__main__':
    main()
