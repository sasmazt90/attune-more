#!/usr/bin/env python3
"""Controlled partial-backbone fine-tuning of YOLOX-S acne detector on local CPU.

Maintains all product contracts:
- 384x384 native BGR tiles, padding 114.
- Masked objectness BCE (unknown unannotated areas loss-masked, not penalized as negatives).
- Real negative photos / known skin ROI support (excluding eyes, lips, nostrils, hair).
- Frozen stem & dark2, frozen BatchNorm in eval mode.
- Dimension bounds before exp().
- Proof parameters monitored for gradient flow and weight changes:
  backbone.backbone.dark3.0.conv.weight, backbone.lateral_conv0.conv.weight, head.reg_convs.0.0.conv.weight.
- Transactional atomic checkpointing and exact resume with sampler cursor.
- Shared metric scope evaluation: in-scope IoU50 recall, in-scope IoU30 recall, verified negative FP.
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
import cv2
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
from source_skin_support import known_skin_scope
from acne_metrics import match_predictions_to_truth, compute_scope_recall

BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'

PROOF_KEYS = [
    'backbone.backbone.dark3.0.conv.weight',
    'backbone.lateral_conv0.conv.weight',
    'head.reg_convs.0.0.conv.weight'
]


def save_full_checkpoint(
    checkpoint_path: Path,
    net,
    optimizer,
    scheduler,
    state: dict,
    epoch: int,
    b_idx: int,
    rng_state: dict,
    sampler_order: list = None,
    accumulated_seconds: float = 0.0
):
    """Atomically saves full checkpoint including weights, optimizer, scheduler, RNG, and sampler cursor."""
    checkpoint_path = Path(checkpoint_path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = checkpoint_path.with_suffix('.pt.tmp')
    tmp_weights = checkpoint_path.parent / f'{checkpoint_path.stem}.safetensors.tmp'
    final_weights = checkpoint_path.parent / f'{checkpoint_path.stem}.safetensors'

    checkpoint_data = {
        'epoch': epoch,
        'b_idx': b_idx,
        'step': state.get('step', 0),
        'completed_epochs': state.get('completed_epochs', 0),
        'accumulated_seconds': accumulated_seconds,
        'sampler_order': sampler_order or [],
        'state': state,
        'optimizer_state': optimizer.state_dict(),
        'scheduler_state': scheduler.state_dict(),
        'rng_torch': rng_state['torch'],
        'rng_numpy': rng_state['numpy'],
        'rng_random': rng_state['random'],
        'protocol_identity': state.get('identity', 'acne-candidate-finetune-20261013'),
        'dataset_sha256': state.get('dataset_sha256', ''),
    }

    # Atomic write of torch checkpoint
    torch.save(checkpoint_data, str(tmp_path))
    if tmp_path.exists():
        os.replace(str(tmp_path), str(checkpoint_path))

    # Atomic write of safetensors
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(tmp_weights))
    if tmp_weights.exists():
        os.replace(str(tmp_weights), str(final_weights))

    # Write solid checkpoint indicator atomically
    indicator_path = checkpoint_path.parent / 'checkpoint_indicator.json'
    tmp_indicator = checkpoint_path.parent / 'checkpoint_indicator.json.tmp'
    indicator_data = {
        'latestCheckpoint': str(checkpoint_path.name),
        'latestWeights': str(final_weights.name),
        'epoch': epoch,
        'b_idx': b_idx,
        'step': state.get('step', 0),
        'completedEpochs': state.get('completed_epochs', 0),
        'accumulatedSeconds': round(accumulated_seconds, 1),
        'status': state.get('status', 'IN_PROGRESS'),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    with open(tmp_indicator, 'w', encoding='utf-8') as f:
        json.dump(indicator_data, f, indent=2)
    if tmp_indicator.exists():
        os.replace(str(tmp_indicator), str(indicator_path))


def load_full_checkpoint(checkpoint_path: Path, net, optimizer, scheduler):
    """Loads full checkpoint and restores weights, optimizer, scheduler, RNG, and sampler cursor."""
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

    return {
        'epoch': checkpoint_data.get('epoch', 0),
        'b_idx': checkpoint_data.get('b_idx', 0),
        'step': checkpoint_data.get('step', 0),
        'completed_epochs': checkpoint_data.get('completed_epochs', 0),
        'accumulated_seconds': checkpoint_data.get('accumulated_seconds', 0.0),
        'sampler_order': checkpoint_data.get('sampler_order', []),
        'state': checkpoint_data.get('state', {}),
        'dataset_sha256': checkpoint_data.get('dataset_sha256', ''),
        'protocol_identity': checkpoint_data.get('protocol_identity', '')
    }


def predict_val_fast(net, val_rows, tile_size=384, stride=288):
    """Fast validation predictor that loads each image ONCE into memory."""
    from torchvision.ops import nms as torch_nms
    net.eval()
    results = []
    with torch.no_grad():
        for r in val_rows:
            img_path = Path(r['absolutePath']) if 'absolutePath' in r and Path(r['absolutePath']).exists() else (LIVE_TEST / r['path'] if 'path' in r else None)
            if img_path is None or not img_path.exists():
                results.append([])
                continue
            bgr = cv2.imread(str(img_path))
            if bgr is None:
                results.append([])
                continue
            x, y, x1, y1 = r['crop']
            xs = sorted(set([*range(x, max(x + 1, x1 - tile_size + 1), stride), max(x, x1 - tile_size)]))
            ys = sorted(set([*range(y, max(y + 1, y1 - tile_size + 1), stride), max(y, y1 - tile_size)]))

            tile_canvases = []
            tile_coords = []
            for a in xs:
                for b in ys:
                    endx = min(x1, a + tile_size)
                    endy = min(y1, b + tile_size)
                    canvas = np.full((tile_size, tile_size, 3), 114, np.uint8)
                    crop = bgr[b:endy, a:endx]
                    canvas[:crop.shape[0], :crop.shape[1]] = crop
                    tile_canvases.append(canvas)
                    tile_coords.append((a, b, endx, endy))

            raw_cands = []
            # Process tiles in mini-batches of 8 for high CPU cache efficiency
            for i in range(0, len(tile_canvases), 8):
                b_canvases = np.stack(tile_canvases[i:i + 8])
                b_tensor = torch.from_numpy(b_canvases.transpose(0, 3, 1, 2)).float()
                b_outs = net(b_tensor)  # shape: (B, 3528, 6)
                for out_t, (a, b, endx, endy) in zip(b_outs, tile_coords[i:i + 8]):
                    scores = out_t[:, 4] * out_t[:, 5]
                    mask = scores >= 0.05
                    if mask.any():
                        filt = out_t[mask]
                        sc = scores[mask]
                        cx = filt[:, 0]
                        cy = filt[:, 1]
                        bw = filt[:, 2]
                        bh = filt[:, 3]
                        bx = torch.clamp(cx - bw / 2 + a, min=float(a))
                        by = torch.clamp(cy - bh / 2 + b, min=float(b))
                        ex = torch.clamp(cx + bw / 2 + a, max=float(endx))
                        ey = torch.clamp(cy + bh / 2 + b, max=float(endy))
                        valid = (ex > bx) & (ey > by)
                        if valid.any():
                            boxes_xyxy = torch.stack([bx[valid], by[valid], ex[valid], ey[valid], sc[valid]], dim=1)
                            raw_cands.extend(boxes_xyxy.cpu().numpy().tolist())

            # Image-level NMS at 0.30
            if raw_cands:
                boxes_t = torch.tensor([c[:4] for c in raw_cands], dtype=torch.float32)
                scores_t = torch.tensor([c[4] for c in raw_cands], dtype=torch.float32)
                keep = torch_nms(boxes_t, scores_t, 0.30)
                kept_cands = [raw_cands[i] for i in keep.numpy()]
            else:
                kept_cands = []
            results.append(kept_cands)
    return results


def evaluate_validation_epoch(net, val_rows, threshold=0.70, nms_threshold=0.30):
    """Evaluates detector on validation set using product contract:
    - In-scope IoU50 recall (same scope for numerator and denominator)
    - In-scope IoU30 recall
    - Verified negative control FP / image
    - Annotation unknown candidates (on positive images)
    - Global F1 is None (PARTIAL_ANNOTATION_UNKNOWN_SKIN)
    """
    val_preds = predict_val_fast(net, val_rows, tile_size=384, stride=288)

    total_truth = 0
    in_scope_truth = 0
    matched_50 = 0
    matched_30 = 0
    in_scope_tp50 = 0
    in_scope_tp30 = 0
    verified_neg_fp = 0
    neg_images = 0
    annotation_unknown = 0

    for r, p_boxes in zip(val_rows, val_preds):
        is_neg = bool(r.get('isNegative') or not r.get('annotations'))
        truth_boxes = [a['box'] for a in r.get('annotations', []) if a.get('classId') == 0]
        truth_categories = [a.get('scopeCategory', 'IN_SCOPE_VISIBLE_REGION') for a in r.get('annotations', []) if a.get('classId') == 0]

        # Filter boxes by confidence threshold
        kept = [b for b in p_boxes if b[4] >= threshold]

        matched_t50, _, _, unp50, _ = match_predictions_to_truth(truth_boxes, kept, 0.50)
        matched_t30, _, _, unp30, _ = match_predictions_to_truth(truth_boxes, kept, 0.30)

        in_scope_indices = [i for i, cat in enumerate(truth_categories) if cat == 'IN_SCOPE_VISIBLE_REGION']
        in_s_tp50 = len(set(matched_t50).intersection(set(in_scope_indices)))
        in_s_tp30 = len(set(matched_t30).intersection(set(in_scope_indices)))

        total_truth += len(truth_boxes)
        in_scope_truth += len(in_scope_indices)
        matched_50 += len(matched_t50)
        matched_30 += len(matched_t30)
        in_scope_tp50 += in_s_tp50
        in_scope_tp30 += in_s_tp30

        if is_neg:
            verified_neg_fp += len(kept)
            neg_images += 1
        else:
            annotation_unknown += len(unp50)

    in_scope_rec50 = compute_scope_recall(in_scope_tp50, in_scope_truth)
    in_scope_rec30 = compute_scope_recall(in_scope_tp30, in_scope_truth)
    all_rec50 = compute_scope_recall(matched_50, total_truth)
    all_rec30 = compute_scope_recall(matched_30, total_truth)
    mean_neg_fp = round(verified_neg_fp / max(1, neg_images), 4) if neg_images > 0 else 0.0

    return {
        'inScopeRec50': in_scope_rec50,
        'inScopeRec30': in_scope_rec30,
        'inScopeTp50': in_scope_tp50,
        'inScopeTp30': in_scope_tp30,
        'inScopeTruth': in_scope_truth,
        'allRec50': all_rec50,
        'allRec30': all_rec30,
        'allTp50': matched_50,
        'allTp30': matched_30,
        'allTruth': total_truth,
        'verifiedNegFp': verified_neg_fp,
        'meanNegFp': mean_neg_fp,
        'negImages': neg_images,
        'annotationUnknown': annotation_unknown,
        'f1_evaluable': None,
        'f1_ineligibility_reason': 'PARTIAL_ANNOTATION_UNKNOWN_SKIN'
    }


def main():
    parser = argparse.ArgumentParser(description="Train acne detector candidate model.")
    parser.add_argument('--initial-weights', type=str, default=str(BASELINE_WEIGHTS), help="Initial weights file (.safetensors).")
    parser.add_argument('--output-dir', type=str, default=str(ROOT / 'audit-results/acne-candidate-phase2-20261013'), help="Output directory for training results.")
    parser.add_argument('--resume', type=str, default=None, help="Path to checkpoint file (.pt) to resume from.")
    parser.add_argument('--max-epochs', type=int, default=3, help="Maximum epochs to train.")
    parser.add_argument('--patience', type=int, default=3, help="Early stopping patience.")
    parser.add_argument('--max-seconds', type=int, default=7200, help="Max run duration in seconds (under 2h).")
    parser.add_argument('--batch-size', type=int, default=2, help="Batch size.")
    parser.add_argument('--lr', type=float, default=1.0e-4, help="Learning rate.")
    parser.add_argument('--num-threads', type=int, default=4, help="PyTorch CPU threads.")
    parser.add_argument('--dry-run', action='store_true', help="Run 2 steps and 1 val check for verification.")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    start_time = time.monotonic()

    torch.set_num_threads(args.num_threads)
    torch.manual_seed(20261013)
    random.seed(20261013)
    np.random.seed(20261013)

    print("=== TOGG Attune Acne Candidate Fine-Tuning (Phase 2) ===")
    print(f"Output directory: {out_dir}")
    print(f"Loading data from: {DATA_PATH}")

    import hashlib
    with open(DATA_PATH, 'rb') as f:
        dataset_sha256 = hashlib.sha256(f.read()).hexdigest()

    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tr = [r for r in data['rows'] if r['split'] == 'train']
    va = [r for r in data['rows'] if r['split'] == 'validation']
    print(f"Train split images: {len(tr)}, Validation split images: {len(va)}")

    # Prepare training tiles and known masks with known_skin_scope
    print("Preparing training tiles and loss-masking scopes with known_skin_scope...")
    import cv2
    scopes = {}
    for r in tr:
        scope = np.zeros((r['height'], r['width']), np.uint8)
        if r.get('negativeROI') and r.get('landmarks'):
            # Load real photo to extract known anatomical skin scope (excluding eyes/lips/hair)
            src_path = Path(r['absolutePath']) if 'absolutePath' in r and Path(r['absolutePath']).exists() else (LIVE_TEST / r['path'] if 'path' in r else None)
            if src_path and src_path.exists():
                bgr = cv2.imread(str(src_path))
                if bgr is not None:
                    scope = known_skin_scope(r, bgr)
            else:
                pts = np.array([[p['x'] * r['width'], p['y'] * r['height']] for p in r['landmarks'][:468]], np.float32)
                cv2.fillPoly(scope, [np.rint(pts).astype(np.int32)], 1)
        scopes[r['sha256']] = scope

    train_tiles = acne_tiles(tr, training=False)
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

    # Index active tiles for sampler order tracking
    tile_to_idx = {id(t): idx for idx, t in enumerate(active_tiles)}

    # Build model
    net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net)

    # Freeze stem and dark2
    for k, p in net.named_parameters():
        p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))

    # Setup masked loss
    obj_loss = KnownObjectnessBCE()
    net.head.bcewithlog_loss = obj_loss

    trainable_params = [p for p in net.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=args.lr, weight_decay=1e-3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.max_epochs)

    # Initial weights & checkpoint resume logic
    protocol_identity = "acne-candidate-phase2-20261013"
    accumulated_seconds = 0.0
    start_epoch = 0
    start_b_idx = 0
    saved_order_indices = []

    state = {
        'identity': protocol_identity,
        'dataset_sha256': dataset_sha256,
        'step': 0,
        'epoch': 0,
        'completed_epochs': 0,
        'history': [],
        'best_score': -999.0,
        'bad_epochs': 0,
        'max_gradients': {k: 0.0 for k in PROOF_KEYS},
        'status': 'IN_PROGRESS'
    }

    if args.resume and Path(args.resume).exists():
        print(f"Resuming training from checkpoint: {args.resume}")
        resumed = load_full_checkpoint(Path(args.resume), net, optimizer, scheduler)
        start_epoch = resumed['epoch']
        start_b_idx = resumed['b_idx']
        state = resumed['state']
        accumulated_seconds = resumed['accumulated_seconds']
        saved_order_indices = resumed.get('sampler_order', [])
        print(f"  -> Resumed at Epoch {start_epoch + 1}, Batch {start_b_idx + 1}, Step {state.get('step', 0)}, Elapsed: {accumulated_seconds:.1f} s")
    else:
        init_weights_path = Path(args.initial_weights)
        print(f"Warm-starting from initial weights: {init_weights_path}")
        assert init_weights_path.exists(), f"Initial weights file not found: {init_weights_path}"
        weights = load_file(str(init_weights_path))
        net.load_state_dict(weights)
        # Baseline snapshot in output dir
        save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(out_dir / 'warmstart-initial-weights.safetensors'))

    # Record initial weights of proof layers for verification
    current_state_dict = net.state_dict()
    proof_initial = {k: current_state_dict[k].clone() for k in PROOF_KEYS}

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
        print(f"Step 1 loss: {float(loss.item()):.4f}", flush=True)
        print("Dry run completed successfully.", flush=True)
        return

    # Initial validation evaluation
    print("\nEvaluating initial model on validation set with product contract...", flush=True)
    init_eval = evaluate_validation_epoch(net, va, threshold=0.70, nms_threshold=0.30)
    print(f"Initial Validation (conf=0.70): InScope IoU50 Rec = {init_eval['inScopeRec50']} (TP={init_eval['inScopeTp50']}/{init_eval['inScopeTruth']}) | Verified Neg FP = {init_eval['verifiedNegFp']} ({init_eval['meanNegFp']}/img)", flush=True)
    state['initial_val'] = init_eval
    init_score = (init_eval['inScopeRec50'] or 0.0) - 0.1 * init_eval['meanNegFp']
    state['best_score'] = init_score

    # Training loop across max_epochs
    max_epochs = args.max_epochs
    batch_size = args.batch_size
    print(f"\nStarting training for up to {max_epochs} epochs (budget: {args.max_seconds} s)...")

    for epoch in range(start_epoch, max_epochs):
        epoch_start = time.monotonic()
        set_train_mode()

        # Build balanced batch order or resume from saved sampler order
        if saved_order_indices and epoch == start_epoch:
            order = [active_tiles[i] for i in saved_order_indices]
            order_indices = saved_order_indices
            saved_order_indices = []
        else:
            neg_sample_count = max(len(neg_tiles), len(pos_tiles) // 3)
            sample_neg = random.choices(neg_tiles, k=neg_sample_count) if neg_tiles else []
            order = pos_tiles + sample_neg
            random.shuffle(order)
            order_indices = [tile_to_idx[id(t)] for t in order]

        epoch_losses = []
        num_batches = len(order) // batch_size
        print(f"\n--- Epoch {epoch + 1}/{max_epochs} ({num_batches} batches) ---")

        for b_idx in range(start_b_idx, num_batches):
            total_elapsed = accumulated_seconds + (time.monotonic() - start_time)
            if total_elapsed >= args.max_seconds:
                print(f"Time limit reached ({total_elapsed:.1f} s >= {args.max_seconds} s). Stopping training.")
                state['status'] = 'STOPPED_TIME_LIMIT'
                # Save exact step checkpoint
                ckpt_path = out_dir / f'checkpoint-step-{state["step"]:05d}.pt'
                rng_state = {
                    'torch': torch.get_rng_state(),
                    'numpy': np.random.get_state(),
                    'random': random.getstate()
                }
                save_full_checkpoint(
                    ckpt_path, net, optimizer, scheduler, state,
                    epoch=epoch, b_idx=b_idx, rng_state=rng_state,
                    sampler_order=order_indices, accumulated_seconds=total_elapsed
                )
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
                cur_elapsed = accumulated_seconds + (time.monotonic() - start_time)
                print(f"  Step {b_idx + 1}/{num_batches} - Batch Loss: {loss_val:.4f} (Elapsed: {cur_elapsed:.1f} s)", flush=True)

        if state['status'] == 'STOPPED_TIME_LIMIT':
            break

        # Reset batch start cursor for subsequent epochs
        start_b_idx = 0
        mean_loss = float(np.mean(epoch_losses)) if epoch_losses else 0.0
        scheduler.step()

        # Update completed epochs count
        state['completed_epochs'] = epoch + 1
        epoch_sec = time.monotonic() - epoch_start
        accumulated_seconds += epoch_sec

        # Validation evaluation after fully completed epoch
        print(f"\nEvaluating validation split after completed Epoch {epoch + 1}...")
        val_eval = evaluate_validation_epoch(net, va, threshold=0.70, nms_threshold=0.30)
        epoch_score = (val_eval['inScopeRec50'] or 0.0) - 0.1 * val_eval['meanNegFp']

        print(
            f"Epoch {epoch + 1} Result: Mean Loss = {mean_loss:.4f} | "
            f"InScope IoU50 Rec = {val_eval['inScopeRec50']} (TP={val_eval['inScopeTp50']}/{val_eval['inScopeTruth']}) | "
            f"InScope IoU30 Rec = {val_eval['inScopeRec30']} | "
            f"Verified Neg FP = {val_eval['verifiedNegFp']} ({val_eval['meanNegFp']}/img) | "
            f"Epoch Time: {epoch_sec:.1f} s"
        )

        epoch_record = {
            'epoch': epoch + 1,
            'train_loss': round(mean_loss, 4),
            'val_in_scope_rec50': val_eval['inScopeRec50'],
            'val_in_scope_rec30': val_eval['inScopeRec30'],
            'val_in_scope_tp50': val_eval['inScopeTp50'],
            'val_in_scope_tp30': val_eval['inScopeTp30'],
            'val_in_scope_truth': val_eval['inScopeTruth'],
            'val_verified_neg_fp': val_eval['verifiedNegFp'],
            'val_mean_neg_fp': val_eval['meanNegFp'],
            'val_annotation_unknown': val_eval['annotationUnknown'],
            'selection_score': round(epoch_score, 4),
            'epoch_seconds': round(epoch_sec, 1)
        }
        state['history'].append(epoch_record)
        state['epoch'] = epoch + 1

        # Save transactional checkpoint for completed epoch
        ckpt_path = out_dir / f'checkpoint-epoch-{epoch + 1:02d}.pt'
        rng_state = {
            'torch': torch.get_rng_state(),
            'numpy': np.random.get_state(),
            'random': random.getstate()
        }
        save_full_checkpoint(
            ckpt_path, net, optimizer, scheduler, state,
            epoch=epoch + 1, b_idx=0, rng_state=rng_state,
            sampler_order=[], accumulated_seconds=accumulated_seconds
        )

        # Track best candidate
        if epoch_score > state['best_score'] + 1e-4:
            state['best_score'] = epoch_score
            state['bad_epochs'] = 0
            save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(out_dir / 'candidate-selected.safetensors'))
            print(f"  --> New best candidate model saved! (Score = {epoch_score:.4f})")
        else:
            state['bad_epochs'] += 1
            print(f"  --> No improvement. Bad epochs: {state['bad_epochs']}/{args.patience}")

        with open(out_dir / 'training-state.json', 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

        if state['bad_epochs'] >= args.patience:
            print(f"Early stopping triggered after {state['bad_epochs']} epochs without improvement.")
            state['status'] = 'EARLY_STOPPED_PATIENCE'
            break

    if state['status'] == 'IN_PROGRESS':
        state['status'] = 'COMPLETED'

    total_training_seconds = accumulated_seconds + (time.monotonic() - start_time)

    # Ensure candidate-selected.safetensors exists
    if not (out_dir / 'candidate-selected.safetensors').exists():
        candidate_weights = {k: v.clone() for k, v in net.state_dict().items()}
        save_file({k: v.contiguous() for k, v in candidate_weights.items()}, str(out_dir / 'candidate-selected.safetensors'))

    candidate_weights = load_file(str(out_dir / 'candidate-selected.safetensors'))

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

    state['proof_evidence'] = proof_evidence
    state['total_accumulated_seconds'] = round(total_training_seconds, 1)

    with open(out_dir / 'training-state.json', 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

    print("\n=== Training Completed ===")
    print(f"Status: {state['status']}")
    print(f"Completed Epochs: {state['completed_epochs']}")
    print(f"Total Time: {total_training_seconds:.1f} s")
    print(f"Proof Evidence: {json.dumps(proof_evidence, indent=2)}")


if __name__ == '__main__':
    main()
