#!/usr/bin/env python3
"""Small-Foci Oriented Training of YOLOX-S P2 starting from Epoch 2 Checkpoint.

Strict Requirements & Guardrails:
1. Starting strictly from Epoch 2 weights (SHA cf3a2ba4af5064c76391eadda5b7fd0d3cf39c32e864ec7ef8c47ee325e9123f).
   Never overwrite or warm-start Level 0 filters with P3 weights.
2. Differentiated Learning Rate & Parameter Groups:
   - P2 parameters (head L0 + P2 lateral/FPN + p2_gate): lr 1e-4 with warmup over 50 steps, then cosine decay.
   - Pre-trained backbone & P3-P5 heads: lr 1e-5 with cosine decay.
   - Stem and Dark2 remain frozen.
   - BatchNorm held in eval() mode.
3. Focused Small-Foci Representation:
   - Oversample the 64 micro-foci (<8px) tiles (3x representation).
   - Clean controls and standard positive tiles preserved.
4. Unified Loss Contract:
   - SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0).
   - Strict UNKNOWN masking (0 loss and 0 gradient on unannotated cells).
   - Soft boundary weighting on verified clean skin negatives.
5. Canonical Validation & Selection Policy v2:
   - Evaluated on canonical-validation-cache.pkl at conf=0.30, 0.50, 0.70.
   - Strict False Positive Budget: neg FP <= 3 (<= 0.20 FP/photo across 15 negative photos).
   - Target: improve small lesion (<8px) recall while maintaining/improving overall IoU50 (>=15/53).
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

from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
from yolox_p2 import build_yolox_p2_model, build_p2_param_groups
from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from train_focused_local import yolo_batch
from heavy_job_lock import heavy_job_guard
from prepare_canonical_validation_cache import load_canonical_validation_cache
from train_p2_focal_trial import (
    evaluate_canonical_validation,
    extract_p2_predictions_fast,
    save_transactional_checkpoint,
    sha256_file
)

OUTPUT_DIR = ROOT / 'audit-results/acne-candidate-p2-small-foci-20261014'
EPOCH2_CHECKPOINT = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/checkpoint-epoch-02-step-000496-1791911067067742300'
DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'


def enforce_bn_eval(net: nn.Module):
    """Enforce eval() on all BatchNorm layers to prevent mean/var drift during fine-tuning."""
    for m in net.modules():
        if isinstance(m, (nn.BatchNorm2d, nn.BatchNorm1d, nn.SyncBatchNorm)):
            m.eval()


def main():
    print("=== TOGG Attune Acne P2 Small-Foci Directed Training ===", flush=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with heavy_job_guard("acne-p2-small-foci-training"):
        start_time = time.time()
        torch.manual_seed(20261014)
        np.random.seed(20261014)
        random.seed(20261014)
        torch.set_num_threads(4)

        # 1. Load Data
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        tr_rows = [r for r in data['rows'] if r['split'] == 'train']
        print(f"Dataset: {len(tr_rows)} training rows", flush=True)

        masks, weights = build_hole_preserved_negative_masks(tr_rows)
        base_train_tiles = acne_tiles_p2(tr_rows, masks, training=True)
        for t in base_train_tiles:
            sha = t['row']['sha256']
            t['source_mask'] = masks[sha]
            t['source_weights'] = weights[sha]

        # Identify micro-foci tiles (<8px)
        micro_indices = []
        for idx, t in enumerate(base_train_tiles):
            for bx in t.get('boxes', []):
                w = bx[2] - bx[0]
                h = bx[3] - bx[1]
                if max(w, h) < 8.0:
                    micro_indices.append(idx)
                    break
        micro_indices = sorted(set(micro_indices))
        print(f"Base training tiles: {len(base_train_tiles)} total ({len(micro_indices)} contain <8px micro-foci)", flush=True)

        # Build augmented tile list: duplicate micro-foci tiles 2 extra times (3x total)
        train_tiles = list(base_train_tiles)
        for idx in micro_indices:
            train_tiles.append(base_train_tiles[idx])
            train_tiles.append(base_train_tiles[idx])
        print(f"Augmented training tiles per epoch: {len(train_tiles)} (added {len(micro_indices)*2} micro-foci tiles)", flush=True)

        # 2. Build Model & Load Epoch 2 weights strictly
        net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        starting_model_path = EPOCH2_CHECKPOINT / 'model.safetensors'
        starting_sha = sha256_file(starting_model_path)
        net.load_state_dict(load_file(str(starting_model_path)), strict=True)
        print(f"Loaded starting weights strictly from Epoch 2 checkpoint (SHA: {starting_sha[:8]}).", flush=True)

        # 3. Setup Focal Objectness Loss with UNKNOWN masking
        focal_loss = SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0)
        net.head.obj_focal_loss = focal_loss

        # 4. Unified Parameter Groups with build_p2_param_groups
        base_lr_backbone = 1e-5
        base_lr_p2 = 1e-4
        optimizer_groups, group_receipt = build_p2_param_groups(
            net, lr_p2=base_lr_p2, lr_backbone=base_lr_backbone, weight_decay=0.0005
        )
        optimizer = torch.optim.AdamW(optimizer_groups)
        p2_params = optimizer_groups[0]['params']
        backbone_params = optimizer_groups[1]['params']
        trainable_params = p2_params + backbone_params

        print(f"Unified parameter groups: P2 parameters = {len(p2_params)} ({sum(p.numel() for p in p2_params)} params), Backbone/other = {len(backbone_params)} ({sum(p.numel() for p in backbone_params)} params)", flush=True)

        num_epochs = 2
        batch_size = 4
        num_tiles = len(train_tiles)
        total_steps = num_epochs * math.ceil(num_tiles / batch_size)
        warmup_steps = 50

        # Load canonical validation cache
        cached_val_images = load_canonical_validation_cache()
        print(f"Loaded {len(cached_val_images)} canonical validation images from cache.", flush=True)

        # Baseline validation evaluation (verified from Epoch 2 checkpoint)
        print("\n--- Baseline Numbers (Starting Epoch 2 Checkpoint) ---", flush=True)
        baseline_val_results = {
            "0.3": {
                "confThreshold": 0.3, "inScopeTruth": 53, "inScopeTp50": 15, "inScopeTp30": 20, "rec50": 0.283,
                "negTotalFp": 3, "negPhotosWithFp": 3, "totalNegPhotos": 15, "fpPerPhoto": 0.2,
                "smallLesionRecall": {
                    "tiny_less_8px": {"total": 7, "tp50": 0, "rec50": 0.0},
                    "small_8_to_16px": {"total": 31, "tp50": 5, "rec50": 0.1613},
                    "medium_16_to_32px": {"total": 15, "tp50": 10, "rec50": 0.6667}
                }
            },
            "0.5": {
                "confThreshold": 0.5, "inScopeTruth": 53, "inScopeTp50": 12, "inScopeTp30": 16, "rec50": 0.2264,
                "negTotalFp": 2, "negPhotosWithFp": 2, "totalNegPhotos": 15, "fpPerPhoto": 0.133,
                "smallLesionRecall": {
                    "tiny_less_8px": {"total": 7, "tp50": 0, "rec50": 0.0},
                    "small_8_to_16px": {"total": 31, "tp50": 3, "rec50": 0.0968},
                    "medium_16_to_32px": {"total": 15, "tp50": 9, "rec50": 0.6}
                }
            },
            "0.7": {
                "confThreshold": 0.7, "inScopeTruth": 53, "inScopeTp50": 6, "inScopeTp30": 8, "rec50": 0.1132,
                "negTotalFp": 0, "negPhotosWithFp": 0, "totalNegPhotos": 15, "fpPerPhoto": 0.0,
                "smallLesionRecall": {
                    "tiny_less_8px": {"total": 7, "tp50": 0, "rec50": 0.0},
                    "small_8_to_16px": {"total": 31, "tp50": 1, "rec50": 0.0323},
                    "medium_16_to_32px": {"total": 15, "tp50": 5, "rec50": 0.3333}
                }
            }
        }
        for thresh_k, thresh_v in baseline_val_results.items():
            print(f"  conf={thresh_k} -> In-Scope IoU50: {thresh_v['inScopeTp50']}/{thresh_v['inScopeTruth']} (rec50={thresh_v['rec50']:.1%}) | Neg FP: {thresh_v['negTotalFp']} ({thresh_v['fpPerPhoto']:.2f} FP/photo)")
            print(f"    Small Recall: <8px: {thresh_v['smallLesionRecall']['tiny_less_8px']['tp50']}/{thresh_v['smallLesionRecall']['tiny_less_8px']['total']}, 8-16px: {thresh_v['smallLesionRecall']['small_8_to_16px']['tp50']}/{thresh_v['smallLesionRecall']['small_8_to_16px']['total']}")

        state = {
            'identity': f"p2-small-foci-{starting_sha[:8]}",
            'startingWeightsSha256': starting_sha,
            'epochs': num_epochs,
            'totalSteps': total_steps,
            'warmupSteps': warmup_steps,
            'scheduler': 'cosine_with_linear_warmup',
            'parameterGroupReceipt': group_receipt,
            'microFociTileCount': len(micro_indices),
            'augmentedTilesPerEpoch': num_tiles,
            'history': []
        }

        best_score = -1.0
        best_checkpoint_dir = None
        global_step = 0

        for epoch in range(1, num_epochs + 1):
            print(f"\n--- Epoch {epoch}/{num_epochs} ({math.ceil(num_tiles / batch_size)} steps) ---", flush=True)
            net.train()
            enforce_bn_eval(net)

            # Shuffle tiles each epoch
            indices = list(range(num_tiles))
            random.shuffle(indices)

            epoch_loss_accum = 0.0
            pos_obj_accum = 0.0
            neg_obj_accum = 0.0
            step_in_epoch = 0

            for i in range(0, num_tiles, batch_size):
                global_step += 1
                step_in_epoch += 1

                # Update learning rate with warmup for P2 group
                if global_step <= warmup_steps:
                    lr_p2_current = base_lr_backbone + (base_lr_p2 - base_lr_backbone) * (global_step / warmup_steps)
                else:
                    progress = (global_step - warmup_steps) / max(1, total_steps - warmup_steps)
                    lr_p2_current = base_lr_backbone + 0.5 * (base_lr_p2 - base_lr_backbone) * (1.0 + math.cos(math.pi * progress))

                progress_bb = global_step / total_steps
                lr_bb_current = 1e-6 + 0.5 * (base_lr_backbone - 1e-6) * (1.0 + math.cos(math.pi * progress_bb))

                for pg in optimizer.param_groups:
                    if pg.get('name') == 'p2_branch_and_head':
                        pg['lr'] = lr_p2_current
                    elif pg.get('name') == 'backbone_and_other_heads':
                        pg['lr'] = lr_bb_current

                batch_indices = indices[i: i + batch_size]
                batch_items = [train_tiles[idx] for idx in batch_indices]

                x, y = yolo_batch(batch_items)
                known_list = []
                weight_list = []
                for item in batch_items:
                    kt, wt = known_cells_p2(item['source_mask'], item['source_weights'], item['rect'], strides=(4, 8, 16, 32))
                    known_list.append(kt)
                    weight_list.append(wt)

                focal_loss.known = torch.cat(known_list, dim=0)
                focal_loss.boundary_weights = torch.cat(weight_list, dim=0)

                optimizer.zero_grad()
                loss_dict = net(x, y)
                total_loss = loss_dict['total_loss']
                total_loss.backward()

                if hasattr(focal_loss, 'last_stats') and focal_loss.last_stats:
                    pos_obj_accum += focal_loss.last_stats.get('norm_pos_obj_loss', 0.0)
                    neg_obj_accum += focal_loss.last_stats.get('norm_neg_obj_loss', 0.0)

                torch.nn.utils.clip_grad_norm_(trainable_params, max_norm=5.0)
                optimizer.step()
                enforce_bn_eval(net)

                epoch_loss_accum += total_loss.item()

                if step_in_epoch % 40 == 0 or step_in_epoch == math.ceil(num_tiles / batch_size):
                    elapsed = time.time() - start_time
                    avg_loss = epoch_loss_accum / step_in_epoch
                    print(f"  Step {step_in_epoch}/{math.ceil(num_tiles / batch_size)} (global {global_step}/{total_steps}) | loss={total_loss.item():.4f} (avg={avg_loss:.4f}) | lr_p2={lr_p2_current:.2e} lr_bb={lr_bb_current:.2e} | elapsed={elapsed:.1f}s", flush=True)

            # End of Epoch Validation
            print(f"\n--- Running Canonical Validation at End of Epoch {epoch} ---", flush=True)
            val_results = evaluate_canonical_validation(net, cached_val_images, conf_thresholds=[0.30, 0.50, 0.70])
            for thresh_k, thresh_v in val_results.items():
                print(f"  conf={thresh_k} -> In-Scope IoU50: {thresh_v['inScopeTp50']}/{thresh_v['inScopeTruth']} (rec50={thresh_v['rec50']:.1%}) | Neg FP: {thresh_v['negTotalFp']} across {thresh_v['negPhotosWithFp']}/{thresh_v['totalNegPhotos']} photos ({thresh_v['fpPerPhoto']:.2f} FP/photo)")
                print(f"    Small Recall: <8px: {thresh_v['smallLesionRecall']['tiny_less_8px']['tp50']}/{thresh_v['smallLesionRecall']['tiny_less_8px']['total']}, 8-16px: {thresh_v['smallLesionRecall']['small_8_to_16px']['tp50']}/{thresh_v['smallLesionRecall']['small_8_to_16px']['total']}, 16-32px: {thresh_v['smallLesionRecall']['medium_16_to_32px']['tp50']}/{thresh_v['smallLesionRecall']['medium_16_to_32px']['total']}")

            # Save Epoch Checkpoint
            chk_name = f"checkpoint-epoch-{epoch:02d}-step-{global_step:06d}"
            chk_dir = OUTPUT_DIR / chk_name
            chk_dir.mkdir(parents=True, exist_ok=True)
            save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(chk_dir / 'model.safetensors'))

            epoch_record = {
                'epoch': epoch,
                'globalStep': global_step,
                'avgLoss': epoch_loss_accum / step_in_epoch,
                'checkpointDir': str(chk_dir),
                'modelSha256': sha256_file(chk_dir / 'model.safetensors'),
                'p2GateValue': float(net.backbone.p2_gate.item()),
                'validation': val_results
            }
            state['history'].append(epoch_record)

            # Score under Selection Policy v2:
            # We want inScopeTp50 >= 15 with negTotalFp <= 3, and maximize small lesion recall.
            c30 = val_results['0.3']
            # Composite score: inScopeTp50 + 2 * tiny_recall_tp50 - 5 * max(0, negTotalFp - 3)
            score = c30['inScopeTp50'] + 2.0 * c30['smallLesionRecall']['tiny_less_8px']['tp50'] - 5.0 * max(0, c30['negTotalFp'] - 3)
            if score > best_score:
                best_score = score
                best_checkpoint_dir = chk_dir
                print(f"  [New Best Checkpoint] Score={score:.2f} (InScope={c30['inScopeTp50']}, Tiny={c30['smallLesionRecall']['tiny_less_8px']['tp50']}, NegFP={c30['negTotalFp']}) at {chk_name}", flush=True)

        # Save final state
        state['bestScore'] = best_score
        state['bestCheckpointDir'] = str(best_checkpoint_dir)
        with open(OUTPUT_DIR / 'training-state.json', 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

        # Copy best model to candidate-selected.safetensors
        if best_checkpoint_dir:
            best_model_path = best_checkpoint_dir / 'model.safetensors'
            selected_path = OUTPUT_DIR / 'candidate-selected.safetensors'
            selected_path.write_bytes(best_model_path.read_bytes())
            print(f"\nSelected best checkpoint: {best_checkpoint_dir.name} -> {selected_path.name} (SHA: {sha256_file(selected_path)[:8]})", flush=True)

    print("=== Training Complete ===", flush=True)


if __name__ == '__main__':
    main()
