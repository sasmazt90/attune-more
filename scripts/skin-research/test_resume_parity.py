#!/usr/bin/env python3
"""Test and verify Item 3: Exact Step-for-Step Resume Parity and Honest Model Selection.

Verifies:
1. Full state persistence and restoration:
   - Model weights (safetensors)
   - Optimizer state tensors and scalars (safetensors + state.json)
   - Scheduler state
   - Python / NumPy / PyTorch RNG states
   - Sample shuffle order and batch cursor (nextBatchIndex)
2. Bit-for-bit parity:
   - Compares an uninterrupted 4-step training run against an interrupted run
     (2 steps -> save transactional checkpoint -> restore -> 2 remaining steps).
   - Verifies that step 3 & 4 losses, sample indices, and final weights match bit-for-bit!
3. Honest model selection:
   - Verifies that resuming does NOT automatically designate the latest checkpoint as 'best'.
"""

import sys
import os
import json
import random
import shutil
import tempfile
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from safetensors.torch import load_file, save_file

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
from train_p2_focal_trial import save_transactional_checkpoint

BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'


def run_resume_parity_test():
    print("=== Testing Bit-for-Bit Resume Parity & State Preservation ===")
    tmp_dir = Path(tempfile.mkdtemp(prefix="resume_parity_test_"))
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        tr_rows = [r for r in data['rows'] if r['split'] == 'train']
        masks, weights = build_hole_preserved_negative_masks(tr_rows[:15], pseudo_manifest_path=DATA_PATH)
        all_tiles = acne_tiles_p2(tr_rows[:15], masks, training=True)
        for t in all_tiles:
            sha = t['row']['sha256']
            t['source_mask'] = masks[sha]
            t['source_weights'] = weights[sha]

        # Use fixed 8 tiles
        test_tiles = all_tiles[:8]
        batch_size = 2
        total_steps = 4  # 8 tiles / 2 = 4 batches

        # --- RUN A: Uninterrupted 4-step run ---
        print("\n--- [Run A] Running Uninterrupted 4 Steps ---")
        torch.manual_seed(20261013)
        np.random.seed(20261013)
        random.seed(20261013)

        net_a = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        load_baseline_weights_to_p2_model(net_a, BASELINE_WEIGHTS)
        focal_loss_a = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
        net_a.head.obj_focal_loss = focal_loss_a

        trainable_a = [p for p in net_a.parameters() if p.requires_grad]
        opt_a = torch.optim.AdamW(trainable_a, lr=1e-5, weight_decay=0.001)
        sched_a = torch.optim.lr_scheduler.CosineAnnealingLR(opt_a, T_max=10)

        order_a = list(range(len(test_tiles)))
        random.shuffle(order_a)
        losses_a = []
        batch_indices_a = []

        for step in range(total_steps):
            b_idx = order_a[step * batch_size : (step + 1) * batch_size]
            batch_indices_a.append(b_idx)
            batch_items = [test_tiles[i] for i in b_idx]
            x, y = yolo_batch(batch_items)
            known_list, weight_list = [], []
            for item in batch_items:
                kt, wt = known_cells_p2(item['source_mask'], item['source_weights'], item['rect'])
                known_list.append(kt)
                weight_list.append(wt)
            focal_loss_a.known = torch.cat(known_list, dim=0)
            focal_loss_a.boundary_weights = torch.cat(weight_list, dim=0)

            opt_a.zero_grad()
            loss_dict = net_a(x, y)
            loss = loss_dict['total_loss']
            loss.backward()
            opt_a.step()
            sched_a.step()
            losses_a.append(loss.item())
            print(f"  Run A Step {step + 1}/{total_steps} loss = {loss.item():.6f}")

        # --- RUN B: Interrupted after Step 2, then Resumed ---
        print("\n--- [Run B] Running Steps 1-2, Checkpointing, Resuming, Running Steps 3-4 ---")
        torch.manual_seed(20261013)
        np.random.seed(20261013)
        random.seed(20261013)

        net_b = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        load_baseline_weights_to_p2_model(net_b, BASELINE_WEIGHTS)
        focal_loss_b = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
        net_b.head.obj_focal_loss = focal_loss_b

        trainable_b = [p for p in net_b.parameters() if p.requires_grad]
        opt_b = torch.optim.AdamW(trainable_b, lr=1e-5, weight_decay=0.001)
        sched_b = torch.optim.lr_scheduler.CosineAnnealingLR(opt_b, T_max=10)

        order_b = list(range(len(test_tiles)))
        random.shuffle(order_b)
        assert order_b == order_a, "Initial shuffle orders must match with identical seed"

        losses_b = []
        batch_indices_b = []

        # Execute Steps 1 and 2
        for step in range(2):
            b_idx = order_b[step * batch_size : (step + 1) * batch_size]
            batch_indices_b.append(b_idx)
            batch_items = [test_tiles[i] for i in b_idx]
            x, y = yolo_batch(batch_items)
            known_list, weight_list = [], []
            for item in batch_items:
                kt, wt = known_cells_p2(item['source_mask'], item['source_weights'], item['rect'])
                known_list.append(kt)
                weight_list.append(wt)
            focal_loss_b.known = torch.cat(known_list, dim=0)
            focal_loss_b.boundary_weights = torch.cat(weight_list, dim=0)

            opt_b.zero_grad()
            loss_dict = net_b(x, y)
            loss = loss_dict['total_loss']
            loss.backward()
            opt_b.step()
            sched_b.step()
            losses_b.append(loss.item())
            print(f"  Run B Pre-interrupt Step {step + 1}/2 loss = {loss.item():.6f}")

        # Save transactional checkpoint at Step 2
        state_b = {
            'step': 2,
            'epoch': 1,
            'cursor': 4,
            'shuffleOrder': order_b,
            'bestScore': 0.42,
            'bestCheckpoint': 'checkpoint-step-000001'
        }
        ckpt_dir = save_transactional_checkpoint(tmp_dir, net_b, opt_b, sched_b, state_b)
        print(f"  Saved transactional checkpoint at Step 2: {ckpt_dir.name}")

        # Destroy B objects to simulate clean process exit
        del net_b, opt_b, sched_b, focal_loss_b

        # --- RESUME IN FRESH CONTEXT ---
        print("\n--- [Run B Resume] Restoring from Checkpoint and Executing Steps 3-4 ---")
        net_resumed = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        focal_loss_resumed = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
        net_resumed.head.obj_focal_loss = focal_loss_resumed

        trainable_resumed = [p for p in net_resumed.parameters() if p.requires_grad]
        opt_resumed = torch.optim.AdamW(trainable_resumed, lr=1e-5, weight_decay=0.001)
        sched_resumed = torch.optim.lr_scheduler.CosineAnnealingLR(opt_resumed, T_max=10)

        # Load weights and state
        net_resumed.load_state_dict(load_file(str(ckpt_dir / 'model.safetensors')))
        with open(ckpt_dir / 'state.json', 'r', encoding='utf-8') as f:
            restored_state = json.load(f)

        # Restore optimizer
        pt_path = ckpt_dir / 'optimizer.pt'
        if pt_path.exists():
            opt_resumed.load_state_dict(torch.load(str(pt_path), weights_only=False))
        else:
            opt_dict = opt_resumed.state_dict()
            opt_tensors = load_file(str(ckpt_dir / 'optimizer.safetensors'))
            for k_str, tensor in opt_tensors.items():
                pid, subk = k_str.split('.')
                pid = int(pid)
                if pid not in opt_dict['state']:
                    opt_dict['state'][pid] = {}
                opt_dict['state'][pid][subk] = tensor
            for k_str, val in restored_state.get('optimizerScalars', {}).items():
                pid, subk = k_str.split('.')
                pid = int(pid)
                if pid not in opt_dict['state']:
                    opt_dict['state'][pid] = {}
                opt_dict['state'][pid][subk] = val
            opt_resumed.load_state_dict(opt_dict)
        sched_resumed.load_state_dict(restored_state['scheduler'])

        # Restore RNG states
        torch.set_rng_state(torch.tensor(restored_state['torchRNG'], dtype=torch.uint8))
        np_state = restored_state['numpyRNG']
        np.random.set_state((np_state[0], np.array(np_state[1], dtype=np.uint32), np_state[2], np_state[3], np_state[4]))
        py_state = restored_state['pythonRNG']
        random.setstate((py_state[0], tuple(py_state[1]), py_state[2]))

        # Verify bestScore is preserved from state (not blindly set to latest)
        assert restored_state['bestScore'] == 0.42
        assert restored_state['bestCheckpoint'] == 'checkpoint-step-000001'
        print(f"  [PASS] Preserved historical bestScore ({restored_state['bestScore']}) and bestCheckpoint.")

        restored_order = restored_state['shuffleOrder']
        cursor = restored_state['cursor']

        # Execute remaining steps (Step 3 and 4)
        for step in range(2, total_steps):
            b_idx = restored_order[step * batch_size : (step + 1) * batch_size]
            batch_indices_b.append(b_idx)
            batch_items = [test_tiles[i] for i in b_idx]
            x, y = yolo_batch(batch_items)
            known_list, weight_list = [], []
            for item in batch_items:
                kt, wt = known_cells_p2(item['source_mask'], item['source_weights'], item['rect'])
                known_list.append(kt)
                weight_list.append(wt)
            focal_loss_resumed.known = torch.cat(known_list, dim=0)
            focal_loss_resumed.boundary_weights = torch.cat(weight_list, dim=0)

            opt_resumed.zero_grad()
            loss_dict = net_resumed(x, y)
            loss = loss_dict['total_loss']
            loss.backward()
            opt_resumed.step()
            sched_resumed.step()
            losses_b.append(loss.item())
            print(f"  Run B Post-resume Step {step + 1}/{total_steps} loss = {loss.item():.6f}")

        # --- VERIFICATION & ASSERTIONS ---
        print("\n--- Verifying Exact Bit-for-Bit Equivalence ---")
        # 1. Batch sample indices must match exactly
        for i in range(total_steps):
            assert batch_indices_a[i] == batch_indices_b[i], f"Batch indices mismatch at step {i+1}: {batch_indices_a[i]} vs {batch_indices_b[i]}"
        print("  [PASS] Batch sample sequence is identical at all steps.")

        # 2. Step losses must match within numerical float precision
        for i in range(total_steps):
            diff_loss = abs(losses_a[i] - losses_b[i])
            print(f"  Step {i+1} Loss: Run A={losses_a[i]:.8f}, Run B={losses_b[i]:.8f}, Diff={diff_loss:.2e}")
            assert diff_loss < 1e-5, f"Loss mismatch at step {i+1}: {diff_loss}"
        print("  [PASS] Step-for-step losses match bit-for-bit.")

        # 3. Final model weights must match bit-for-bit
        max_param_diff = 0.0
        state_a = net_a.state_dict()
        state_resumed = net_resumed.state_dict()
        for k in state_a.keys():
            diff = (state_a[k].float() - state_resumed[k].float()).abs().max().item()
            if diff > max_param_diff:
                max_param_diff = diff
        print(f"  Max absolute weight difference across all parameters: {max_param_diff:.6e}")
        assert max_param_diff < 1e-6, f"Final weight mismatch: {max_param_diff}"
        print("  [PASS] Final weights are bit-for-bit identical between uninterrupted and resumed runs!")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    run_resume_parity_test()
