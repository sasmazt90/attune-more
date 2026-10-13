#!/usr/bin/env python3
"""Isolated 2-step verification for training checkpoint and exact numerical resume.

Verifies:
1. Model training step 1 produces checkpoint containing weights, optimizer state,
   scheduler state, RNG states (torch, numpy, random), and step cursor.
2. Step 2 run directly produces loss L2 and weight state W2.
3. Resuming from checkpoint at step 1 and running step 2 produces loss L2_resumed and weight state W2_resumed.
4. Exact numerical equality: |L2 - L2_resumed| == 0.0 and max(|W2 - W2_resumed|) == 0.0.
"""

import sys
import copy
import random
import shutil
from pathlib import Path
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
from yolox_numeric import install_bounds
from selected_yolox_loss import KnownObjectnessBCE
import train_acne_candidate as TAC


def run_isolated_verification():
    print("=== Verifying Exact Numerical Checkpoint Resume (2-Step Test) ===")
    test_dir = ROOT / 'audit-results/checkpoint-resume-test'
    test_dir.mkdir(parents=True, exist_ok=True)
    ckpt_file = test_dir / 'test_checkpoint.pt'

    # Set seed
    torch.manual_seed(42)
    np.random.seed(42)
    random.seed(42)

    # Initialize model
    net1 = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net1)
    optimizer1 = torch.optim.AdamW(net1.parameters(), lr=1e-4)
    scheduler1 = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer1, T_max=10)

    # Generate 2 synthetic fixed batches of native tiles
    torch.manual_seed(100)
    batch1_x = torch.randn(2, 3, 384, 384)
    batch1_t = torch.zeros(2, 5, 5) # YOLOX targets [batch, max_labels, 5]
    # Put a dummy box at [cls=0, cx=192, cy=192, w=20, h=20]
    batch1_t[:, 0, :] = torch.tensor([0.0, 192.0, 192.0, 20.0, 20.0])
    batch2_x = torch.randn(2, 3, 384, 384)
    batch2_t = torch.zeros(2, 5, 5)
    batch2_t[:, 0, :] = torch.tensor([0.0, 150.0, 150.0, 25.0, 25.0])

    # Step 1 execution on net1
    torch.manual_seed(200)
    np.random.seed(200)
    random.seed(200)

    optimizer1.zero_grad()
    out1 = net1(batch1_x, batch1_t)
    loss1 = out1['total_loss']
    loss1.backward()
    optimizer1.step()
    scheduler1.step()

    # Save checkpoint after Step 1
    state1 = {'step': 1, 'epoch': 1, 'best_f1': 0.0, 'bad_epochs': 0}
    rng_state1 = {
        'torch': torch.get_rng_state(),
        'numpy': np.random.get_state(),
        'random': random.getstate()
    }
    TAC.save_full_checkpoint(ckpt_file, net1, optimizer1, scheduler1, state1, epoch=1, b_idx=0, rng_state=rng_state1)
    print("  -> Saved Step 1 checkpoint successfully.")

    # Continue Step 2 directly on net1
    optimizer1.zero_grad()
    out2_direct = net1(batch2_x, batch2_t)
    loss2_direct = out2_direct['total_loss']
    loss2_direct.backward()
    optimizer1.step()
    w2_direct = {k: v.clone() for k, v in net1.state_dict().items()}
    loss2_direct_val = float(loss2_direct.item())
    print(f"  -> Direct Step 2 Loss: {loss2_direct_val:.8f}")

    # Now create fresh model net2, load checkpoint, and run Step 2
    net2 = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net2)
    optimizer2 = torch.optim.AdamW(net2.parameters(), lr=1e-4)
    scheduler2 = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer2, T_max=10)

    resumed_epoch, resumed_b_idx, resumed_state = TAC.load_full_checkpoint(ckpt_file, net2, optimizer2, scheduler2)
    assert resumed_state['step'] == 1, "Resumed step mismatch"

    # Run Step 2 on resumed net2
    optimizer2.zero_grad()
    out2_resumed = net2(batch2_x, batch2_t)
    loss2_resumed = out2_resumed['total_loss']
    loss2_resumed.backward()
    optimizer2.step()
    w2_resumed = {k: v.clone() for k, v in net2.state_dict().items()}
    loss2_resumed_val = float(loss2_resumed.item())
    print(f"  -> Resumed Step 2 Loss: {loss2_resumed_val:.8f}")

    # Check loss equality
    loss_diff = abs(loss2_direct_val - loss2_resumed_val)
    print(f"  -> Absolute Loss Difference: {loss_diff:.10f}")
    assert loss_diff == 0.0, f"Loss mismatch on resume: {loss_diff} != 0.0"

    # Check parameter equality across all layers
    max_weight_diff = 0.0
    for k in w2_direct:
        diff = float((w2_direct[k] - w2_resumed[k]).abs().max())
        max_weight_diff = max(max_weight_diff, diff)

    print(f"  -> Max Parameter Discrepancy: {max_weight_diff:.10f}")
    assert max_weight_diff == 0.0, f"Parameter mismatch on resume: {max_weight_diff} != 0.0"

    # Clean up test dir
    shutil.rmtree(test_dir, ignore_errors=True)
    print("=== Checkpoint Resume Numerical Verification PASSED (Bit-for-Bit Exact) ===")
    return True


if __name__ == '__main__':
    run_isolated_verification()
