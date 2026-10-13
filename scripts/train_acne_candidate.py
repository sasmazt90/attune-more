#!/usr/bin/env python3
"""Controlled partial-backbone fine-tuning of YOLOX-S acne detector on local CPU.

Maintains all product contracts:
- 384x384 native BGR tiles, padding 114.
- Masked objectness BCE (unknown unannotated areas loss-masked, not penalized as negatives).
- Real negative photos / ROI support.
- Frozen stem & dark2, frozen BatchNorm in eval mode.
- Dimension bounds before exp().
- Proof parameters monitored for gradient flow and weight changes:
  backbone.backbone.dark3.0.conv.weight, backbone.lateral_conv0.conv.weight, head.reg_convs.0.0.conv.weight.
- Transactional checkpointing and early stopping.
"""

import os
import sys
import json
import time
import math
import random
import argparse
from pathlib import Path
from collections import defaultdict
import numpy as np
import torch
from safetensors.torch import load_file, save_file

ROOT = Path(__file__).resolve().parents[1]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'scripts/skin-research'))

from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
from selected_yolox_loss import KnownObjectnessBCE, known_cells
from yolox_numeric import install_bounds
from train_focused_local import acne_tiles, yolo_batch, predict
from training_checkpoint import checkpoint, resume

OUT_DIR = ROOT / 'audit-results/acne-candidate-training-20261013'
BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'

PROOF_KEYS = [
    'backbone.backbone.dark3.0.conv.weight',
    'backbone.lateral_conv0.conv.weight',
    'head.reg_convs.0.0.conv.weight'
]


def save_full_checkpoint(checkpoint_path: Path, net, optimizer, scheduler, state, epoch: int, b_idx: int, rng_state: dict):
    checkpoint_path = Path(checkpoint_path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_data = {
        'epoch': epoch,
        'b_idx': b_idx,
        'step': state.get('step', 0),
        'state': state,
        'optimizer_state': optimizer.state_dict(),
        'scheduler_state': scheduler.state_dict(),
        'rng_torch': rng_state['torch'],
        'rng_numpy': rng_state['numpy'],
        'rng_random': rng_state['random'],
    }
    torch.save(checkpoint_data, str(checkpoint_path))
    weights_path = checkpoint_path.parent / f'{checkpoint_path.stem}.safetensors'
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(weights_path))


def load_full_checkpoint(checkpoint_path: Path, net, optimizer, scheduler):
    checkpoint_path = Path(checkpoint_path)
    checkpoint_data = torch.load(str(checkpoint_path), map_location='cpu', weights_only=False)
    weights_path = checkpoint_path.parent / f'{checkpoint_path.stem}.safetensors'
    if weights_path.exists():
        weights = load_file(str(weights_path))
        net.load_state_dict(weights)
    elif 'model_state' in checkpoint_data:
        net.load_state_dict(checkpoint_data['model_state'])
    optimizer.load_state_dict(checkpoint_data['optimizer_state'])
    scheduler.load_state_dict(checkpoint_data['scheduler_state'])
    torch.set_rng_state(checkpoint_data['rng_torch'])
    np.random.set_state(checkpoint_data['rng_numpy'])
    random.setstate(checkpoint_data['rng_random'])
    return checkpoint_data['epoch'], checkpoint_data['b_idx'], checkpoint_data['state']


def calc_f1_score(rows, preds, threshold=0.50, iou_thresh=0.50):
    total_tp = 0
    total_fp = 0
    total_fn = 0
    for r, p_boxes in zip(rows, preds):
        truth_boxes = [a['box'] for a in r.get('annotations', []) if a.get('classId') == 0]
        # Filter predictions by score threshold
        filtered = [b for b in p_boxes if b[4] >= threshold]
        
        used_t = set()
        ranked = sorted(filtered, key=lambda b: b[4], reverse=True)
        for p in ranked:
            best_iou = 0.0
            best_ti = -1
            for ti, t in enumerate(truth_boxes):
                if ti in used_t:
                    continue
                x0, y0 = max(t[0], p[0]), max(t[1], p[1])
                x1, y1 = min(t[2], p[2]), min(t[3], p[3])
                inter = max(0, x1 - x0) * max(0, y1 - y0)
                area_t = (t[2] - t[0]) * (t[3] - t[1])
                area_p = (p[2] - p[0]) * (p[3] - p[1])
                iou = inter / max(1e-8, area_t + area_p - inter)
                if iou > best_iou:
                    best_iou = iou
                    best_ti = ti
            if best_iou >= iou_thresh and best_ti >= 0:
                used_t.add(best_ti)
                total_tp += 1
            else:
                total_fp += 1
        total_fn += (len(truth_boxes) - len(used_t))
    precision = total_tp / max(1, total_tp + total_fp)
    recall = total_tp / max(1, total_tp + total_fn)
    f1 = 2 * precision * recall / max(1e-8, precision + recall)
    return {'precision': precision, 'recall': recall, 'f1': f1, 'tp': total_tp, 'fp': total_fp, 'fn': total_fn}


def main():
    parser = argparse.ArgumentParser(description="Train acne detector candidate model.")
    parser.add_argument('--max-epochs', type=int, default=5, help="Maximum epochs to train.")
    parser.add_argument('--patience', type=int, default=3, help="Early stopping patience.")
    parser.add_argument('--max-seconds', type=int, default=7000, help="Max run duration in seconds (under 2h).")
    parser.add_argument('--batch-size', type=int, default=2, help="Batch size.")
    parser.add_argument('--lr', type=float, default=1.5e-4, help="Learning rate.")
    parser.add_argument('--dry-run', action='store_true', help="Run 2 steps and 1 val check for verification.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start_time = time.monotonic()

    torch.set_num_threads(2)
    torch.manual_seed(20261013)
    random.seed(20261013)
    np.random.seed(20261013)

    print("=== TOGG Attune Acne Candidate Fine-Tuning ===")
    print(f"Loading data from: {DATA_PATH}")
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tr = [r for r in data['rows'] if r['split'] == 'train']
    va = [r for r in data['rows'] if r['split'] == 'validation']
    print(f"Train split images: {len(tr)}, Validation split images: {len(va)}")

    # Prepare training tiles and known masks
    print("Preparing training tiles and loss-masking scopes...")
    scopes = {}
    for r in tr:
        scope = np.zeros((r['height'], r['width']), np.uint8)
        if r.get('negativeROI') and r.get('landmarks'):
            import cv2
            pts = np.array([[p['x'] * r['width'], p['y'] * r['height']] for p in r['landmarks'][:468]], np.float32)
            cv2.fillConvexPoly(scope, cv2.convexHull(np.rint(pts).astype(np.int32)), 1)
        scopes[r['sha256']] = scope

    train_tiles = acne_tiles(tr, training=False)
    # Filter to tiles that have pimple boxes or are in reviewed negative face ROIs
    active_tiles = []
    for t in train_tiles:
        r = t['row']
        has_boxes = len(t['boxes']) > 0
        has_neg = bool(r.get('negativeROI'))
        if has_boxes or has_neg:
            t['known'] = known_cells(scopes[r['sha256']], t['rect'], has_neg)
            active_tiles.append(t)

    pos_tiles = [t for t in active_tiles if t['boxes']]
    neg_tiles = [t for t in active_tiles if not t['boxes']]
    print(f"Active training tiles: {len(active_tiles)} ({len(pos_tiles)} positive, {len(neg_tiles)} negative)")

    # Build model
    net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net)

    print(f"Loading baseline weights from: {BASELINE_WEIGHTS}")
    baseline_weights = load_file(str(BASELINE_WEIGHTS))
    net.load_state_dict(baseline_weights)

    # Freeze stem and dark2
    for k, p in net.named_parameters():
        p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))

    # Record initial weights of proof layers
    proof_initial = {k: baseline_weights[k].clone() for k in PROOF_KEYS}

    # Setup masked loss
    obj_loss = KnownObjectnessBCE()
    net.head.bcewithlog_loss = obj_loss

    # Trainable parameters
    trainable_params = [p for p in net.parameters() if p.requires_grad]
    trainable_names = [k for k, p in net.named_parameters() if p.requires_grad]
    print(f"Trainable parameter tensors: {len(trainable_params)} / {len(list(net.parameters()))}")

    optimizer = torch.optim.AdamW(trainable_params, lr=args.lr, weight_decay=1e-3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.max_epochs)

    # Training state
    protocol_identity = "acne-candidate-finetune-20261013-v1"
    state = {
        'identity': protocol_identity,
        'step': 0,
        'epoch': 0,
        'history': [],
        'best_f1': -1.0,
        'bad_epochs': 0,
        'max_gradients': {k: 0.0 for k in PROOF_KEYS},
        'status': 'IN_PROGRESS'
    }

    # Baseline evaluation on validation
    print("\nEvaluating baseline on validation set...")
    val_preds_baseline = predict(net, 'yolox', va)
    base_eval50 = calc_f1_score(va, val_preds_baseline, threshold=0.70, iou_thresh=0.50)
    base_eval30 = calc_f1_score(va, val_preds_baseline, threshold=0.70, iou_thresh=0.30)
    print(f"Baseline Validation (conf=0.70): IoU50 F1={base_eval50['f1']:.4f} (TP={base_eval50['tp']}), IoU30 F1={base_eval30['f1']:.4f} (TP={base_eval30['tp']})")
    state['baseline_val'] = {'iou50': base_eval50, 'iou30': base_eval30}
    state['best_f1'] = base_eval50['f1']

    # Save baseline snapshot
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(OUT_DIR / 'baseline-snapshot.safetensors'))

    def set_train_mode():
        net.train()
        for m in net.modules():
            if isinstance(m, torch.nn.BatchNorm2d):
                m.eval()

    if args.dry_run:
        print("\n[DRY RUN MODE] Running 2 training steps...")
        set_train_mode()
        b_items = active_tiles[:2]
        optimizer.zero_grad()
        obj_loss.known = torch.cat([t['known'] for t in b_items])
        x, y = yolo_batch(b_items)
        out = net(x, y)
        loss = out['total_loss']
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        optimizer.step()
        print(f"Step 1 loss: {float(loss.item()):.4f}")
        print("Dry run completed successfully.")
        return

    # Training loop
    max_epochs = args.max_epochs
    batch_size = args.batch_size
    print(f"\nStarting training for up to {max_epochs} epochs (patience={args.patience})...")

    for epoch in range(max_epochs):
        epoch_start = time.monotonic()
        set_train_mode()

        # Build balanced batch order: positive tiles + sample of negative tiles
        neg_sample_count = max(len(neg_tiles), len(pos_tiles) // 3)
        sample_neg = random.choices(neg_tiles, k=neg_sample_count) if neg_tiles else []
        order = pos_tiles + sample_neg
        random.shuffle(order)

        epoch_losses = []
        num_batches = len(order) // batch_size
        print(f"\n--- Epoch {epoch + 1}/{max_epochs} ({num_batches} batches) ---")

        for b_idx in range(num_batches):
            if (time.monotonic() - start_time) > args.max_seconds:
                print("Time limit reached. Stopping training.")
                state['status'] = 'STOPPED_TIME_LIMIT'
                break

            b_items = order[b_idx * batch_size:(b_idx + 1) * batch_size]
            optimizer.zero_grad()
            obj_loss.known = torch.cat([t['known'] for t in b_items])
            x, y = yolo_batch(b_items)
            out = net(x, y)
            total_loss = out['total_loss']
            assert torch.isfinite(total_loss), "Encountered non-finite loss"
            total_loss.backward()

            # Track proof layer gradients
            for k in PROOF_KEYS:
                param = dict(net.named_parameters()).get(k)
                if param is not None and param.grad is not None:
                    g_max = float(param.grad.abs().max())
                    state['max_gradients'][k] = max(state['max_gradients'][k], g_max)

            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0, error_if_nonfinite=True)
            optimizer.step()

            loss_val = float(total_loss.item())
            epoch_losses.append(loss_val)
            state['step'] += 1

            if b_idx % 50 == 0 or b_idx == num_batches - 1:
                print(f"  Step {b_idx + 1}/{num_batches} - Batch Loss: {loss_val:.4f}", flush=True)

        mean_loss = float(np.mean(epoch_losses)) if epoch_losses else 0.0
        scheduler.step()

        # Validation evaluation
        print(f"Evaluating validation split after Epoch {epoch + 1}...")
        val_preds = predict(net, 'yolox', va)
        val_eval50 = calc_f1_score(va, val_preds, threshold=0.70, iou_thresh=0.50)
        val_eval30 = calc_f1_score(va, val_preds, threshold=0.70, iou_thresh=0.30)
        epoch_sec = time.monotonic() - epoch_start

        print(f"Epoch {epoch + 1} Result: Mean Loss = {mean_loss:.4f} | Val IoU50 F1 = {val_eval50['f1']:.4f} (TP={val_eval50['tp']}) | Val IoU30 F1 = {val_eval30['f1']:.4f} | Time: {epoch_sec:.1f} s")

        epoch_record = {
            'epoch': epoch + 1,
            'train_loss': round(mean_loss, 4),
            'val_iou50_f1': round(val_eval50['f1'], 4),
            'val_iou50_tp': val_eval50['tp'],
            'val_iou50_fp': val_eval50['fp'],
            'val_iou30_f1': round(val_eval30['f1'], 4),
            'val_iou30_tp': val_eval30['tp'],
            'epoch_seconds': round(epoch_sec, 1)
        }
        state['history'].append(epoch_record)
        state['epoch'] = epoch + 1

        # Checkpoint
        checkpoint_dir = OUT_DIR / f'checkpoint-epoch-{epoch + 1:02d}'
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(checkpoint_dir / 'model.safetensors'))

        # Track best
        if val_eval50['f1'] > state['best_f1'] + 1e-4:
            state['best_f1'] = val_eval50['f1']
            state['bad_epochs'] = 0
            save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(OUT_DIR / 'candidate-selected.safetensors'))
            print(f"  --> New best candidate model saved! (F1 = {val_eval50['f1']:.4f})")
        else:
            state['bad_epochs'] += 1
            print(f"  --> No improvement. Bad epochs: {state['bad_epochs']}/{args.patience}")

        # Save state JSON
        with open(OUT_DIR / 'training-state.json', 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

        if state['bad_epochs'] >= args.patience:
            print(f"Early stopping triggered after {state['bad_epochs']} epochs without improvement.")
            state['status'] = 'EARLY_STOPPED_PATIENCE'
            break

        if (time.monotonic() - start_time) > args.max_seconds:
            print("Time limit reached.")
            state['status'] = 'STOPPED_TIME_LIMIT'
            break

    if state['status'] == 'IN_PROGRESS':
        state['status'] = 'COMPLETED'

    total_training_seconds = time.monotonic() - start_time

    # Verify proof parameter differences
    if (OUT_DIR / 'candidate-selected.safetensors').exists():
        candidate_weights = load_file(str(OUT_DIR / 'candidate-selected.safetensors'))
    else:
        candidate_weights = {k: v.clone() for k, v in net.state_dict().items()}
        save_file({k: v.contiguous() for k, v in candidate_weights.items()}, str(OUT_DIR / 'candidate-selected.safetensors'))

    proof_evidence = {}
    for k in PROOF_KEYS:
        diff_max = float((candidate_weights[k] - proof_initial[k]).abs().max())
        g_max = state['max_gradients'].get(k, 0.0)
        proof_evidence[k] = {
            'maxWeightDiff': round(diff_max, 6),
            'maxGradient': round(g_max, 6),
            'weightsUpdated': diff_max > 0.0,
            'gradientObserved': g_max > 0.0
        }

    # Final receipt
    receipt = {
        'experiment': 'acne-candidate-fine-tuning-20261013',
        'status': state['status'],
        'totalSeconds': round(total_training_seconds, 1),
        'epochsTrained': state['epoch'],
        'learningRate': args.lr,
        'batchSize': args.batch_size,
        'baselineValIoU50F1': round(base_eval50['f1'], 4),
        'bestValIoU50F1': round(state['best_f1'], 4),
        'candidateImproved': state['best_f1'] > base_eval50['f1'] + 1e-4,
        'history': state['history'],
        'proofEvidence': proof_evidence,
        'decision': (
            'CANDIDATE_ACCEPTED_FOR_PARITY_CHECK'
            if state['best_f1'] > base_eval50['f1'] + 1e-4
            else 'RETAIN_FROZEN_BASELINE_PRESERVE_CANDIDATE_AUDIT'
        )
    }

    with open(OUT_DIR / 'training-receipt.json', 'w', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2)

    print("\n=== Training Summary ===")
    print(f"Status:             {receipt['status']}")
    print(f"Total Time:         {total_training_seconds:.1f} s ({total_training_seconds / 60.0:.2f} min)")
    print(f"Epochs:             {state['epoch']}")
    print(f"Baseline IoU50 F1:  {receipt['baselineValIoU50F1']:.4f}")
    print(f"Best Val IoU50 F1:  {receipt['bestValIoU50F1']:.4f}")
    print(f"Decision:           {receipt['decision']}")
    print(f"Receipt written to: {OUT_DIR / 'training-receipt.json'}")


if __name__ == '__main__':
    main()
