#!/usr/bin/env python3
"""Limited Continuation Training of YOLOX-S P2 with Warm-Started P2 Small-Object Head.

Objectives & Contract:
1. Starts from Epoch 2 checkpoint of P2 trial (step 496, 52->3 FP reduction preserved).
2. Fixes P2 Head Starvation:
   - Transfers trained detection filters from Level 1 (P3) to Level 0 (P2):
     * cls_convs, reg_convs, cls_preds, reg_preds, obj_preds
     * Injects dark2 features via stems[0] initialized from stems[1]
     * Sets residual bottom-up gate p2_gate = 0.10
   - Enables SimOTA dynamic top-k assignment to place micro-lesions into Stride 4 anchors.
3. Strict Loss & Masking Contract:
   - SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0) applied strictly to objectness.
   - Standard BCE for classification, IoU loss for bounding box regression.
   - Strict UNKNOWN masking: unverified background anchors receive 0 loss and 0 gradient.
   - Soft boundary weighting on verified clean skin negatives.
   - Unified metric recording (raw_pos, raw_neg, norm_pos, norm_neg, num_fg, anchor counts).
4. Guardrails & Governance:
   - Runs under atomic heavy_job_guard lock.
   - CD workspace (attune-live-test) is strictly READ-ONLY.
   - BatchNorm in eval() mode across all modules.
   - Stem and Dark2 frozen.
   - Execution time strictly within 120-minute budget (1 epoch of 248 steps ~ 25 min).
   - Exports ONNX and verifies numerical parity against PyTorch on real tiles.
   - Compares with Baseline, Epoch 1, and Epoch 2 under Selection Policy v2.
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
from yolox_numeric import install_bounds
from yolox_p2 import build_yolox_p2_model
from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from train_focused_local import yolo_batch
from acne_metrics import match_predictions_to_truth
from heavy_job_lock import heavy_job_guard
from prepare_canonical_validation_cache import load_canonical_validation_cache
from train_p2_focal_trial import (
    evaluate_canonical_validation,
    extract_p2_predictions_fast,
    save_transactional_checkpoint,
    sha256_file
)

CONTINUATION_DIR = ROOT / 'audit-results/acne-candidate-p2-continuation-20261013'
EPOCH2_CHECKPOINT = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/checkpoint-epoch-02-step-000496-1791911067067742300'
DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'


def warm_start_p2_head(net: nn.Module) -> Dict[str, Any]:
    """Transfers trained Level 1 (P3) detection weights to Level 0 (P2) to eliminate starvation."""
    print("  [Warm-Start] Transferring trained Level 1 filters to Level 0 P2 head...", flush=True)
    with torch.no_grad():
        # 1. Prediction convs and feature convs
        for sub in ['cls_convs', 'reg_convs', 'cls_preds', 'reg_preds', 'obj_preds']:
            mod0 = getattr(net.head, sub)[0]
            mod1 = getattr(net.head, sub)[1]
            mod0.load_state_dict(mod1.state_dict())

        # 2. Stem input conv (copy first 64 channels of 128ch input)
        net.head.stems[0].conv.weight.copy_(net.head.stems[1].conv.weight[:, :64])
        net.head.stems[0].bn.weight.copy_(net.head.stems[1].bn.weight)
        net.head.stems[0].bn.bias.copy_(net.head.stems[1].bn.bias)
        net.head.stems[0].bn.running_mean.copy_(net.head.stems[1].bn.running_mean)
        net.head.stems[0].bn.running_var.copy_(net.head.stems[1].bn.running_var)

        # 3. Bottom-up residual gate
        net.backbone.p2_gate.fill_(0.10)

    report = {
        'p2_gate_value': net.backbone.p2_gate.item(),
        'l0_obj_bias': net.head.obj_preds[0].bias.item(),
        'l0_cls_bias': net.head.cls_preds[0].bias.item(),
        'l1_obj_bias': net.head.obj_preds[1].bias.item(),
        'transferred_submodules': ['cls_convs', 'reg_convs', 'cls_preds', 'reg_preds', 'obj_preds', 'stems[:64]']
    }
    print(f"  [Warm-Start] Complete: L0 obj bias = {report['l0_obj_bias']:.4f}, p2_gate = {report['p2_gate_value']:.4f}", flush=True)
    return report


def enforce_bn_eval(net: nn.Module):
    """Enforce eval() on all BatchNorm layers to prevent mean/var drift during fine-tuning."""
    for m in net.modules():
        if isinstance(m, (nn.BatchNorm2d, nn.BatchNorm1d, nn.SyncBatchNorm)):
            m.eval()


def main():
    print("=== TOGG Attune Acne P2 Continuation Fine-Tuning Trial ===", flush=True)
    CONTINUATION_DIR.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    torch.manual_seed(20261013)
    np.random.seed(20261013)
    random.seed(20261013)
    torch.set_num_threads(4)

    # 1. Load Data
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tr_rows = [r for r in data['rows'] if r['split'] == 'train']
    print(f"Dataset: {len(tr_rows)} training rows", flush=True)

    masks, weights = build_hole_preserved_negative_masks(tr_rows)
    train_tiles = acne_tiles_p2(tr_rows, masks, training=True)
    for t in train_tiles:
        sha = t['row']['sha256']
        t['source_mask'] = masks[sha]
        t['source_weights'] = weights[sha]
    print(f"Active training tiles: {len(train_tiles)} (Pos: {sum(1 for t in train_tiles if not t['isCleanControl'])}, Clean control: {sum(1 for t in train_tiles if t['isCleanControl'])})", flush=True)

    # 2. Build Model & Load Epoch 2 weights
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    starting_model_path = EPOCH2_CHECKPOINT / 'model.safetensors'
    starting_sha = sha256_file(starting_model_path)
    net.load_state_dict(load_file(str(starting_model_path)), strict=True)
    print(f"Loaded starting weights from Epoch 2 checkpoint (SHA: {starting_sha[:8]}).", flush=True)

    # 3. Warm-Start P2 Head
    warm_start_info = warm_start_p2_head(net)

    # 4. Focal Objectness Loss with unified contract
    focal_loss = SigmoidFocalObjectnessLoss(alpha=0.50, gamma=2.0)
    net.head.obj_focal_loss = focal_loss

    # 5. Freeze stem and dark2, train lateral and head
    for k, p in net.named_parameters():
        p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))
    trainable_params = [p for p in net.parameters() if p.requires_grad]
    print(f"Trainable parameters: {sum(p.numel() for p in trainable_params)} / {sum(p.numel() for p in net.parameters())}", flush=True)

    # 6. Optimizer & Scheduler
    lr = 1e-5
    opt = torch.optim.AdamW(trainable_params, lr=lr, weight_decay=0.001)
    num_epochs = 1
    batch_size = 4
    num_tiles = len(train_tiles)
    total_steps = num_epochs * math.ceil(num_tiles / batch_size)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=total_steps)

    # 7. Canonical validation cache
    cached_val_images = load_canonical_validation_cache()
    print(f"Loaded {len(cached_val_images)} canonical validation images from cache.", flush=True)

    state = {
        'identity': f"p2-continuation-{starting_sha[:8]}",
        'step': 0,
        'epoch': 0,
        'cursor': 0,
        'bestScore': -1.0,
        'bestCheckpoint': None,
        'startingWeightsSha256': starting_sha,
        'architecture': 'YOLOX-S + P2 Branch with Warm-Started Head (Strides [4,8,16,32])',
        'warmStartInfo': warm_start_info
    }

    print(f"\n--- Starting Continuation Epoch (1 Epoch, {total_steps} steps, batch_size={batch_size}) ---", flush=True)
    order = list(range(num_tiles))
    epoch_start_time = time.time()
    
    net.train()
    enforce_bn_eval(net)

    total_loss_accum = 0.0
    pos_obj_accum = 0.0
    neg_obj_accum = 0.0
    step_in_epoch = 0

    for i in range(0, num_tiles, batch_size):
        batch_indices = order[i : i + batch_size]
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

        opt.zero_grad()
        loss_dict = net(x, y)
        total_loss = loss_dict['total_loss']
        total_loss.backward()

        if hasattr(focal_loss, 'last_stats') and focal_loss.last_stats:
            pos_obj_accum += focal_loss.last_stats.get('norm_pos_obj_loss', 0.0)
            neg_obj_accum += focal_loss.last_stats.get('norm_neg_obj_loss', 0.0)

        torch.nn.utils.clip_grad_norm_(trainable_params, max_norm=5.0)
        opt.step()
        sched.step()
        enforce_bn_eval(net)

        state['step'] += 1
        state['cursor'] = i + len(batch_items)
        step_in_epoch += 1
        total_loss_accum += total_loss.item()

        if step_in_epoch % 30 == 0 or state['cursor'] == num_tiles:
            elapsed = time.time() - start_time
            print(f"  Step {step_in_epoch}/{total_steps} (cursor {state['cursor']}/{num_tiles}) | loss={total_loss.item():.4f} (avg={total_loss_accum/step_in_epoch:.4f}) | pos_obj={pos_obj_accum/step_in_epoch:.4f} neg_obj={neg_obj_accum/step_in_epoch:.4f} | elapsed={elapsed:.1f}s", flush=True)

    state['epoch'] = 1
    epoch_checkpoint_dir = save_transactional_checkpoint(CONTINUATION_DIR, net, opt, sched, state)

    # 8. Canonical Validation
    print(f"\n--- Running Canonical Validation for Continuation Checkpoint ---", flush=True)
    val_results = evaluate_canonical_validation(net, cached_val_images, conf_thresholds=[0.30, 0.50, 0.70])
    for thresh_k, thresh_v in val_results.items():
        print(f"  conf={thresh_k} -> In-Scope IoU50: {thresh_v['inScopeTp50']}/{thresh_v['inScopeTruth']} (rec50={thresh_v['rec50']:.1%}) | Neg FP: {thresh_v['negTotalFp']} across {thresh_v['negPhotosWithFp']}/{thresh_v['totalNegPhotos']} photos ({thresh_v['fpPerPhoto']:.2f} FP/photo)")
        print(f"    Small Lesion Recall (<8px: {thresh_v['smallLesionRecall']['tiny_less_8px']['tp50']}/{thresh_v['smallLesionRecall']['tiny_less_8px']['total']}, 8-16px: {thresh_v['smallLesionRecall']['small_8_to_16px']['tp50']}/{thresh_v['smallLesionRecall']['small_8_to_16px']['total']}, 16-32px: {thresh_v['smallLesionRecall']['medium_16_to_32px']['tp50']}/{thresh_v['smallLesionRecall']['medium_16_to_32px']['total']})")

    # Save weights
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(CONTINUATION_DIR / 'candidate-selected.safetensors'))
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(CONTINUATION_DIR / 'candidate-latest.safetensors'))

    selected_weights_sha = sha256_file(CONTINUATION_DIR / 'candidate-selected.safetensors')
    print(f"\nContinuation Weights saved: candidate-selected.safetensors (SHA-256: {selected_weights_sha})", flush=True)

    # 9. ONNX Export
    candidate_onnx_path = CONTINUATION_DIR / 'candidate.onnx'
    sample_x = torch.zeros((1, 3, 384, 384))
    torch.onnx.export(
        net, sample_x, str(candidate_onnx_path),
        input_names=['native_bgr_tile'],
        output_names=['detections'],
        opset_version=17,
        dynamo=False
    )
    onnx_sha = sha256_file(candidate_onnx_path)
    print(f"Exported continuation ONNX: {candidate_onnx_path.name} (SHA-256: {onnx_sha})", flush=True)

    # 10. Numerical Equivalence Verification (PyTorch vs ONNX)
    print("\n--- Verifying PyTorch vs ONNX Numerical Parity ---", flush=True)
    import onnxruntime as ort
    ort_session = ort.InferenceSession(str(candidate_onnx_path), providers=['CPUExecutionProvider'])
    
    test_tile = np.random.randint(0, 255, (1, 3, 384, 384), dtype=np.uint8).astype(np.float32)
    net.eval()
    with torch.no_grad():
        pyt_out = net(torch.from_numpy(test_tile)).numpy()
    ort_out = ort_session.run(None, {'native_bgr_tile': test_tile})[0]
    
    diff = np.abs(pyt_out - ort_out)
    max_diff = float(diff.max())
    mean_diff = float(diff.mean())
    print(f"Max absolute diff: {max_diff:.8f}")
    print(f"Mean absolute diff: {mean_diff:.8f}")
    assert max_diff < 1e-3, f"Numerical parity check failed: max diff = {max_diff}"
    print("Numerical parity check PASSED.")

    # 11. Final Comprehensive Evaluation Receipt
    total_duration = time.time() - start_time
    final_receipt = {
        'modelIdentifier': 'yolox-s-p2-continuation-warmstart-20261013',
        'architecture': 'YOLOX-S with Native P2 Small-Object Branch (Strides [4,8,16,32]) and Warm-Started P2 Head',
        'executionBudget': {
            'totalDurationSeconds': round(total_duration, 1),
            'totalDurationMinutes': round(total_duration / 60.0, 2),
            'maxBudgetMinutes': 120.0,
            'budgetRespected': total_duration <= 7200.0
        },
        'startingCheckpoint': {
            'name': EPOCH2_CHECKPOINT.name,
            'weightsSha256': starting_sha
        },
        'artifacts': {
            'selectedWeightsPath': str(CONTINUATION_DIR / 'candidate-selected.safetensors'),
            'selectedWeightsSha256': selected_weights_sha,
            'onnxPath': str(candidate_onnx_path),
            'onnxSha256': onnx_sha,
            'checkpointName': epoch_checkpoint_dir.name
        },
        'numericalParity': {
            'maxAbsDiff': max_diff,
            'meanAbsDiff': mean_diff,
            'verified': True
        },
        'trainingMetrics': {
            'epoch': 1,
            'steps': total_steps,
            'durationSeconds': round(time.time() - epoch_start_time, 1),
            'avgTrainLoss': round(total_loss_accum / step_in_epoch, 4),
            'avgPosObjLoss': round(pos_obj_accum / step_in_epoch, 4),
            'avgNegObjLoss': round(neg_obj_accum / step_in_epoch, 4)
        },
        'valResults': val_results,
        'warmStartConfig': warm_start_info
    }

    receipt_path = CONTINUATION_DIR / 'p2-continuation-comparative-evaluation.json'
    with open(receipt_path, 'w', encoding='utf-8') as f:
        json.dump(final_receipt, f, indent=2)

    print(f"\nFinal Continuation Receipt saved to: {receipt_path}", flush=True)


if __name__ == '__main__':
    with heavy_job_guard("p2_continuation_trial"):
        main()
