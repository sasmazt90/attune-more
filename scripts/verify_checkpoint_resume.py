#!/usr/bin/env python3
"""Verification of exact mathematical checkpoint resume with real data sampler order and batch cursor."""

import sys
import copy
import random
import shutil
import json
from pathlib import Path
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
from yolox_numeric import install_bounds
from selected_yolox_loss import KnownObjectnessBCE, known_cells
from train_focused_local import acne_tiles, yolo_batch
import train_acne_candidate as TAC

TEST_DIR = ROOT / 'audit-results/checkpoint-resume-test'
DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'


def test_real_sampler_checkpoint_resume():
    print("=== Verifying Exact Numerical Checkpoint Resume with Real Sampler & Batch Cursor ===")
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    ckpt_file = TEST_DIR / 'resume_verification_checkpoint.pt'
    indicator_file = TEST_DIR / 'checkpoint_indicator.json'

    # Load real training dataset
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tr = [r for r in data['rows'] if r['split'] == 'train']

    # Build active tiles with known skin scopes
    train_tiles = acne_tiles(tr, training=False)
    active_tiles = []
    for t in train_tiles:
        if t['boxes'] or t['row'].get('negativeROI'):
            scope = np.ones((t['row']['height'], t['row']['width']), np.uint8)
            t['known'] = known_cells(scope, t['rect'], bool(t['row'].get('negativeROI')))
            active_tiles.append(t)

    assert len(active_tiles) > 10, "Not enough real active tiles for test"
    pos_tiles = [t for t in active_tiles if t['boxes']]
    neg_tiles = [t for t in active_tiles if not t['boxes']]
    tile_to_idx = {id(t): idx for idx, t in enumerate(active_tiles)}

    # Fix base seeds
    torch.manual_seed(20261013)
    np.random.seed(20261013)
    random.seed(20261013)

    # Initialize Model 1
    net1 = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net1)
    obj_loss1 = KnownObjectnessBCE()
    net1.head.bcewithlog_loss = obj_loss1
    for k, p in net1.named_parameters():
        p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))
    trainable_params1 = [p for p in net1.parameters() if p.requires_grad]
    optimizer1 = torch.optim.AdamW(trainable_params1, lr=1e-4)
    scheduler1 = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer1, T_max=10)

    # Generate real balanced sampler order
    neg_sample_count = max(len(neg_tiles), len(pos_tiles) // 3)
    sample_neg = random.choices(neg_tiles, k=neg_sample_count) if neg_tiles else []
    order1 = pos_tiles + sample_neg
    random.shuffle(order1)
    order_indices = [tile_to_idx[id(t)] for t in order1]

    batch_size = 2
    state1 = {
        'identity': 'resume-verification-test',
        'dataset_sha256': 'test-dataset-sha',
        'step': 0,
        'completed_epochs': 0
    }

    # Execute Step 1 and Step 2 on net1
    net1.train()
    for b_idx in range(2):
        b_items = order1[b_idx * batch_size:(b_idx + 1) * batch_size]
        optimizer1.zero_grad()
        obj_loss1.known = torch.cat([t['known'] for t in b_items])
        x, y = yolo_batch(b_items)
        out = net1(x, y)
        loss = out['total_loss']
        loss.backward()
        optimizer1.step()
        state1['step'] += 1

    print(f"  -> Executed Step 1 and Step 2 with real data sampler.")

    # Save full checkpoint after Step 2 (cursor b_idx=1, next batch will be b_idx=2)
    rng_state = {
        'torch': torch.get_rng_state(),
        'numpy': np.random.get_state(),
        'random': random.getstate()
    }
    TAC.save_full_checkpoint(
        ckpt_file, net1, optimizer1, scheduler1, state1,
        epoch=0, b_idx=1, rng_state=rng_state,
        sampler_order=order_indices, accumulated_seconds=12.5
    )
    assert ckpt_file.exists(), "Checkpoint file not saved"
    assert indicator_file.exists(), "Checkpoint indicator file not saved"
    with open(indicator_file, 'r', encoding='utf-8') as f:
        ind_data = json.load(f)
    assert ind_data['b_idx'] == 1
    assert ind_data['step'] == 2
    print("  -> Saved full checkpoint with atomic write & solid indicator.")

    # Continue Step 3 directly on net1
    b_idx_3 = 2
    b_items_3 = order1[b_idx_3 * batch_size:(b_idx_3 + 1) * batch_size]
    optimizer1.zero_grad()
    obj_loss1.known = torch.cat([t['known'] for t in b_items_3])
    x3, y3 = yolo_batch(b_items_3)
    out3_direct = net1(x3, y3)
    loss3_direct = out3_direct['total_loss']
    loss3_direct.backward()
    optimizer1.step()
    w3_direct = {k: v.clone() for k, v in net1.state_dict().items()}
    loss3_direct_val = float(loss3_direct.item())
    print(f"  -> Direct Step 3 Loss: {loss3_direct_val:.8f}")

    # Now create fresh Model 2, load checkpoint, and resume at Step 3
    net2 = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net2)
    obj_loss2 = KnownObjectnessBCE()
    net2.head.bcewithlog_loss = obj_loss2
    for k, p in net2.named_parameters():
        p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))
    trainable_params2 = [p for p in net2.parameters() if p.requires_grad]
    optimizer2 = torch.optim.AdamW(trainable_params2, lr=1e-4)
    scheduler2 = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer2, T_max=10)

    resumed = TAC.load_full_checkpoint(ckpt_file, net2, optimizer2, scheduler2)
    assert resumed['b_idx'] == 1, f"Resumed b_idx mismatch: {resumed['b_idx']}"
    assert resumed['step'] == 2, f"Resumed step mismatch: {resumed['step']}"
    assert len(resumed['sampler_order']) == len(order_indices), "Resumed sampler order mismatch"

    # Reconstruct sampler order from resumed indices
    order2 = [active_tiles[i] for i in resumed['sampler_order']]
    next_b_idx = resumed['b_idx'] + 1  # next batch is 2
    assert next_b_idx == 2

    # Run Step 3 on resumed Model 2
    net2.train()
    b_items_resumed = order2[next_b_idx * batch_size:(next_b_idx + 1) * batch_size]
    optimizer2.zero_grad()
    obj_loss2.known = torch.cat([t['known'] for t in b_items_resumed])
    x3_res, y3_res = yolo_batch(b_items_resumed)
    out3_res = net2(x3_res, y3_res)
    loss3_res = out3_res['total_loss']
    loss3_res.backward()
    optimizer2.step()
    w3_res = {k: v.clone() for k, v in net2.state_dict().items()}
    loss3_res_val = float(loss3_res.item())
    print(f"  -> Resumed Step 3 Loss: {loss3_res_val:.8f}")

    # Numerical verification
    loss_diff = abs(loss3_direct_val - loss3_res_val)
    print(f"  -> Loss Difference: {loss_diff:.10f}")
    assert loss_diff == 0.0, f"Loss mismatch on resume: {loss_diff} != 0.0"

    max_weight_diff = 0.0
    for k in w3_direct:
        diff = float((w3_direct[k] - w3_res[k]).abs().max())
        max_weight_diff = max(max_weight_diff, diff)

    print(f"  -> Maximum Weight Difference across all parameter tensors: {max_weight_diff:.10f}")
    assert max_weight_diff == 0.0, f"Weight mismatch on resume: {max_weight_diff} != 0.0"

    print("=== EXACT BIT-FOR-BIT RESUME VERIFIED SUCCESSFULLY ===")
    return {
        'loss_direct': loss3_direct_val,
        'loss_resumed': loss3_res_val,
        'loss_diff': loss_diff,
        'max_weight_diff': max_weight_diff,
        'verified': True
    }


if __name__ == '__main__':
    res = test_real_sampler_checkpoint_resume()
    receipt_path = ROOT / 'audit-results/checkpoint-resume-test/resume-verification-receipt.json'
    with open(receipt_path, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2)
    print(f"Saved receipt to: {receipt_path}")
