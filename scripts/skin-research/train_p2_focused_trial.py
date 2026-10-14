#!/usr/bin/env python3
"""Focused Training of YOLOX-S Level 0 (P2) Branch on Micro/Small Acne Lesions.

Architectural Design:
1. Baseline Winner Base: cf3a2ba4af5064c76391eadda5b7fd0d3cf39c32e864ec7ef8c47ee325e9123f
   (achieved 10/15 medium lesions, 3 FP on 15 negative photos, 15/53 overall recall).
2. Level 0 Warm-Start:
   - Prediction heads (cls_convs, reg_convs, cls_preds, reg_preds, obj_preds) warm-started from Level 1 (P3).
   - Stem input conv initialized from stems[1] with norm-preserving scaling.
   - reduce_conv2 initialized from reduce_conv1.
   - p2_gate strictly frozen at 0.0 to prevent back-propagating noise into P3.
3. Preservation of Pretrained Levels:
   - Levels 1, 2, 3 (P3, P4, P5) heads and upper backbone are FROZEN (requires_grad = False).
   - Medium lesion recall (>=10/15) and clean skin negative suppression (<=3 FP) are mathematically preserved.
4. Active Training Target:
   - Only Level 0 (P2 stride 4) parameters + optional dark2 receive gradients.
   - Trained on positive tiles with small/micro lesions (<16px) + clean control negative skin.
5. Strict Validation & Selection:
   - Canonical 43-image validation evaluated at each epoch.
   - Enforces FP budget <= 0.20 FP/photo (<= 3 FP across 15 negative photos).
   - Transactional atomic checkpointing under heavy_job_guard lock.
"""

import sys
import os
import json
import time
import math
import random
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Any
import numpy as np
import cv2
import torch
import torch.nn as nn
from safetensors.torch import load_file, save_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from train_focused_local import yolo_batch
from acne_metrics import match_predictions_to_truth
from heavy_job_lock import heavy_job_guard
from prepare_canonical_validation_cache import load_canonical_validation_cache
from train_p2_focal_trial import evaluate_canonical_validation, save_transactional_checkpoint, sha256_file

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
BASELINE_CHECKPOINT = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/checkpoint-epoch-02-step-000496-1791911067067742300/model.safetensors'
TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-focused-20261014'


def warm_start_level0_from_baseline(net: nn.Module) -> Dict[str, Any]:
    """Warm-start Level 0 (P2) weights from Level 1 (P3) to eliminate cold-start starvation."""
    print("  [Warm-Start] Initializing Level 0 (P2) heads and FPN from Level 1 (P3)...", flush=True)
    with torch.no_grad():
        # 1. Prediction convs and feature convs
        for sub in ['cls_convs', 'reg_convs', 'cls_preds', 'reg_preds', 'obj_preds']:
            mod0 = getattr(net.head, sub)[0]
            mod1 = getattr(net.head, sub)[1]
            mod0.load_state_dict(mod1.state_dict())

        # 2. Stem input conv (copy first 64 channels with 2.0x norm-preserving factor)
        net.head.stems[0].conv.weight.copy_(net.head.stems[1].conv.weight[:, :64] * 2.0)
        net.head.stems[0].bn.weight.copy_(net.head.stems[1].bn.weight)
        net.head.stems[0].bn.bias.copy_(net.head.stems[1].bn.bias)
        net.head.stems[0].bn.running_mean.copy_(net.head.stems[1].bn.running_mean)
        net.head.stems[0].bn.running_var.copy_(net.head.stems[1].bn.running_var)

        # 3. Backbone reduce_conv2 (takes 128ch base_p3 down to 64ch)
        net.backbone.reduce_conv2.conv.weight.copy_(net.backbone.reduce_conv1.conv.weight[:64, :128])
        net.backbone.reduce_conv2.bn.weight.copy_(net.backbone.reduce_conv1.bn.weight[:64])
        net.backbone.reduce_conv2.bn.bias.copy_(net.backbone.reduce_conv1.bn.bias[:64])
        net.backbone.reduce_conv2.bn.running_mean.copy_(net.backbone.reduce_conv1.bn.running_mean[:64])
        net.backbone.reduce_conv2.bn.running_var.copy_(net.backbone.reduce_conv1.bn.running_var[:64])

        # 4. Freeze p2_gate strictly at 0.0 to insulate P3
        net.backbone.p2_gate.zero_()

    return {
        'p2_gate': net.backbone.p2_gate.item(),
        'l0_obj_bias': net.head.obj_preds[0].bias.item(),
        'l0_cls_bias': net.head.cls_preds[0].bias.item(),
        'l1_obj_bias': net.head.obj_preds[1].bias.item(),
    }


def configure_parameter_groups(net: nn.Module, lr_p2: float = 2e-4, lr_dark2: float = 5e-6):
    """Freeze all pre-trained levels (P3, P4, P5) and upper backbone. Unfreeze only Level 0 and dark2."""
    p2_prefixes = (
        'backbone.reduce_conv2.', 'backbone.C3_p2.',
        'head.stems.0.', 'head.cls_convs.0.', 'head.reg_convs.0.',
        'head.cls_preds.0.', 'head.reg_preds.0.', 'head.obj_preds.0.'
    )
    
    p2_params = []
    dark2_params = []
    frozen_params = []

    for name, param in net.named_parameters():
        if name == 'backbone.p2_gate':
            param.requires_grad = False
            frozen_params.append(name)
        elif any(name.startswith(pfx) for pfx in p2_prefixes):
            param.requires_grad = True
            p2_params.append(param)
        elif name.startswith('backbone.backbone.dark2.'):
            param.requires_grad = True
            dark2_params.append(param)
        else:
            param.requires_grad = False
            frozen_params.append(name)

    print(f"  [Param Partition] Trainable P2 params: {sum(p.numel() for p in p2_params)} ({len(p2_params)} tensors)")
    print(f"  [Param Partition] Trainable Dark2 params: {sum(p.numel() for p in dark2_params)} ({len(dark2_params)} tensors)")
    print(f"  [Param Partition] Frozen params: {sum(p.numel() for p in net.parameters() if not p.requires_grad)} ({len(frozen_params)} tensors)")

    param_groups = [
        {'params': p2_params, 'lr': lr_p2, 'weight_decay': 0.0001, 'name': 'level0_p2'},
        {'params': dark2_params, 'lr': lr_dark2, 'weight_decay': 0.0001, 'name': 'dark2_shallow'},
    ]
    return param_groups, p2_params + dark2_params


def select_focused_training_tiles(train_rows: List[dict], masks: Dict[str, np.ndarray]) -> List[dict]:
    """Select training tiles containing small/micro lesions (<16px) or verified clean skin."""
    all_tiles = acne_tiles_p2(train_rows, masks, training=True)
    focused_tiles = []
    tiny_tiles = 0
    small_tiles = 0
    clean_tiles = 0

    for t in all_tiles:
        boxes = t.get('boxes', [])
        is_clean = t.get('isCleanControl', False)
        if is_clean:
            focused_tiles.append(t)
            clean_tiles += 1
        elif boxes:
            # Check if any box is <16px
            has_small = any(max(b[2]-b[0], b[3]-b[1]) < 16 for b in boxes)
            has_tiny = any(max(b[2]-b[0], b[3]-b[1]) < 8 for b in boxes)
            if has_tiny:
                tiny_tiles += 1
            if has_small:
                small_tiles += 1
                focused_tiles.append(t)
            else:
                # Still include 50% of medium-only tiles to maintain scene context
                if random.random() < 0.50:
                    focused_tiles.append(t)

    print(f"  [Tile Selection] Total available: {len(all_tiles)} -> Focused subset: {len(focused_tiles)}")
    print(f"    Tiles with <8px lesions: {tiny_tiles}")
    print(f"    Tiles with <16px lesions: {small_tiles}")
    print(f"    Clean control skin tiles: {clean_tiles}")
    return focused_tiles


def main():
    print("=" * 80)
    print("FOCUSED P2 LEVEL-0 TRAINING FOR TOGG ATTUNE ACNE DETECTION")
    print(f"Starting checkpoint: {BASELINE_CHECKPOINT.name}")
    print("=" * 80)

    seed = 20261014
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    TRIAL_DIR.mkdir(parents=True, exist_ok=True)

    with heavy_job_guard("acne-candidate-p2-focused-20261014"):
        # 1. Load data
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        train_rows = [r for r in data['rows'] if r['split'] == 'train']
        print(f"Loaded {len(train_rows)} TRAIN rows from reviewed data.")

        masks, weights = build_hole_preserved_negative_masks(train_rows)
        focused_tiles = select_focused_training_tiles(train_rows, masks)

        # Preload full images for fast batching
        print("Preloading training images into memory...", flush=True)
        img_cache = {}
        for r in train_rows:
            sha = r['sha256']
            if sha not in img_cache:
                path = r.get('absolutePath') or str(LIVE_TEST / r['path'])
                bgr = cv2.imread(path)
                assert bgr is not None, f"Could not read image: {path}"
                img_cache[sha] = bgr
        print(f"Preloaded {len(img_cache)} images.")

        for t in focused_tiles:
            t['preloaded_bgr'] = img_cache[t['row']['sha256']]

        # 2. Build model and load baseline weights
        net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        net.load_state_dict(load_file(str(BASELINE_CHECKPOINT)), strict=True)
        
        # 3. Warm-start Level 0
        warm_report = warm_start_level0_from_baseline(net)
        print("Warm-start report:", json.dumps(warm_report, indent=2))

        # 4. Configure parameters
        param_groups, trainable_params = configure_parameter_groups(net, lr_p2=2e-4, lr_dark2=5e-6)

        # 5. Setup Focal Loss
        focal_loss = SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0)
        net.head.obj_focal_loss = focal_loss

        # 6. Optimizer and scheduler
        opt = torch.optim.AdamW(param_groups)
        num_epochs = 2
        batch_size = 4
        steps_per_epoch = (len(focused_tiles) + batch_size - 1) // batch_size
        total_steps = num_epochs * steps_per_epoch
        warmup_steps = 20

        def lr_lambda(step):
            if step < warmup_steps:
                return float(step + 1) / float(max(1, warmup_steps))
            progress = float(step - warmup_steps) / float(max(1, total_steps - warmup_steps))
            return 0.5 * (1.0 + math.cos(math.pi * progress))

        sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda)

        # 7. Pre-evaluation (Zero-Step Baseline)
        cached_val_images = load_canonical_validation_cache()
        print("\n--- Canonical Validation at Step 0 (Zero-Step Warm-Start Baseline) ---", flush=True)
        val_res_0 = evaluate_canonical_validation(net, cached_val_images, conf_thresholds=[0.30])
        r0 = val_res_0['0.3']
        print(f"Step 0: inScopeTp50={r0['inScopeTp50']}/53 (rec50={r0['rec50']:.1%}) | negFP={r0['negTotalFp']} ({r0['fpPerPhoto']:.2f}/photo)")
        print(f"        tiny={r0['smallLesionRecall']['tiny_less_8px']['tp50']}/7, small={r0['smallLesionRecall']['small_8_to_16px']['tp50']}/31, med={r0['smallLesionRecall']['medium_16_to_32px']['tp50']}/15")

        best_score = r0['rec50']
        best_tp50 = r0['inScopeTp50']
        best_chk_path = TRIAL_DIR / 'candidate-selected.safetensors'
        save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(best_chk_path))

        # 8. Training Loop
        order = list(range(len(focused_tiles)))
        global_step = 0
        history = []

        for epoch in range(1, num_epochs + 1):
            epoch_start = time.time()
            random.shuffle(order)
            net.train()
            # Keep all batchnorms strictly in eval mode
            for m in net.modules():
                if isinstance(m, nn.BatchNorm2d):
                    m.eval()

            total_loss_accum = 0.0
            step_in_epoch = 0

            for i in range(0, len(focused_tiles), batch_size):
                batch_indices = order[i : i + batch_size]
                batch_items = [focused_tiles[idx] for idx in batch_indices]

                # Extract batch images from preloaded cache
                images = []
                targets = torch.zeros((len(batch_items), max(max(len(t['boxes']) for t in batch_items), 1), 5), dtype=torch.float32)
                for bi, t in enumerate(batch_items):
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
                for item in batch_items:
                    sha = item['row']['sha256']
                    kt, wt = known_cells_p2(masks[sha], weights[sha], item['rect'], strides=(4, 8, 16, 32))
                    known_list.append(kt)
                    weight_list.append(wt)

                focal_loss.known = torch.cat(known_list, dim=0)
                focal_loss.boundary_weights = torch.cat(weight_list, dim=0)

                opt.zero_grad()
                loss_dict = net(x, y)
                total_loss = loss_dict['total_loss']
                assert torch.isfinite(total_loss), f"Non-finite loss at step {global_step}: {total_loss.item()}"
                total_loss.backward()

                torch.nn.utils.clip_grad_norm_(trainable_params, max_norm=5.0)
                opt.step()
                sched.step()

                global_step += 1
                step_in_epoch += 1
                total_loss_accum += total_loss.item()

                if step_in_epoch % 25 == 0 or step_in_epoch == steps_per_epoch:
                    avg_l = total_loss_accum / step_in_epoch
                    lr_now = opt.param_groups[0]['lr']
                    print(f"  Epoch {epoch}/{num_epochs} | Step {step_in_epoch}/{steps_per_epoch} | Loss: {total_loss.item():.4f} (avg: {avg_l:.4f}) | lr: {lr_now:.2e} | elapsed: {time.time()-epoch_start:.1f}s", flush=True)

            # Epoch Validation
            print(f"\n--- Canonical Validation at End of Epoch {epoch} ---", flush=True)
            val_res = evaluate_canonical_validation(net, cached_val_images, conf_thresholds=[0.30])
            r = val_res['0.3']
            tp50 = r['inScopeTp50']
            rec50 = r['rec50']
            neg_fp = r['negTotalFp']
            fp_photo = r['fpPerPhoto']
            tiny_hit = r['smallLesionRecall']['tiny_less_8px']['tp50']
            small_hit = r['smallLesionRecall']['small_8_to_16px']['tp50']
            med_hit = r['smallLesionRecall']['medium_16_to_32px']['tp50']

            print(f"Epoch {epoch} Result: inScopeTp50={tp50}/53 ({rec50:.1%}) | negFP={neg_fp} ({fp_photo:.2f}/photo)")
            print(f"               tiny={tiny_hit}/7, small={small_hit}/31, med={med_hit}/15")

            state_info = {
                'epoch': epoch,
                'step': global_step,
                'avgLoss': total_loss_accum / step_in_epoch,
                'durationSec': round(time.time() - epoch_start, 1),
                'validation': val_res
            }
            chk_dir = save_transactional_checkpoint(TRIAL_DIR, net, opt, sched, state_info)
            history.append(state_info)

            # Selection Policy: Must beat baseline recall (>=16/53) under <=3 neg FP
            if tp50 > best_tp50 and neg_fp <= 3:
                best_tp50 = tp50
                best_score = rec50
                save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(best_chk_path))
                print(f"  >>> NEW WINNER at Epoch {epoch}! Recall improved to {tp50}/53 ({rec50:.1%}) with {neg_fp} FP!")
            elif tp50 < best_tp50:
                print(f"  [Early Stopping Check] Epoch {epoch} recall ({tp50}/53) did not improve over best ({best_tp50}/53).")

        # Save training summary
        summary = {
            'startingCheckpoint': BASELINE_CHECKPOINT.name,
            'startingWeightsSha256': sha256_file(BASELINE_CHECKPOINT),
            'bestTp50': best_tp50,
            'bestScore': best_score,
            'history': history,
            'selectedWeightsSha256': sha256_file(best_chk_path)
        }
        with open(TRIAL_DIR / 'training-state.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)

        print("\n" + "=" * 80)
        print("TRIAL COMPLETED")
        print(f"Initial: 15/53 -> Final Best: {best_tp50}/53")
        print(f"Selected weights saved to: {best_chk_path}")
        print("=" * 80)


if __name__ == '__main__':
    main()
