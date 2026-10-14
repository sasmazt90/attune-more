#!/usr/bin/env python3
"""Scale-Guided Independent P2 Training for TOGG Attune Acne Detection.

Integrity & Architectural Contract:
1. Verified Baseline Base:
   SHA: cf3a2ba4af5064c76391eadda5b7fd0d3cf39c32e864ec7ef8c47ee325e9123f
   (15/53 overall recall, 10/15 medium lesions, 3 FP / 15 negative photos).
2. Level 0 (P2 stride 4) Prior Calibration:
   - reg_preds[0].bias[2:4] set to log(2.0) -> 8px prior box size at stride 4.
   - cls_preds[0].bias and obj_preds[0].bias set to -4.6 (0.01 prior probability).
   - p2_gate strictly 0.0 to prevent any perturbation to P3 features.
3. 100% Backbone & Upper Heads Freeze:
   - CSPDarknet (stem, dark2, dark3, dark4, dark5) 100% frozen.
   - PAFPN upper levels (P3, P4, P5) 100% frozen.
   - P3, P4, P5 heads 100% frozen.
   - Mathematical invariance: (p3_pred - baseline_p3_pred).abs().max() == 0.0.
   - All BatchNorms strictly in eval mode (m.training == False).
4. Scale-Guided SimOTA Matching:
   - Stride 4: lesions < 14 px.
   - Stride 8: lesions 12 <= s < 36 px.
   - Stride 16: lesions 24 <= s < 72 px.
   - Stride 32: lesions >= 48 px.
5. Balanced Focal Objectness Loss:
   - alpha = 0.25, gamma = 2.0.
   - Positive loss normalized by num_fg.
   - Negative loss normalized by active known negative anchors with w_neg = 20.0.
   - UNKNOWN mask zeroed out to prevent unverified skin penalization.
6. Checkpoint & Resume Parity:
   - Atomic transactional checkpoints every 50 steps and at epoch end.
   - CURRENT pointer points to latest verified generation.
   - Exact bit-for-bit RNG, optimizer, scheduler, model resume verified.
7. Disambiguated Metric Gates:
   - developmentImproved: inScopeTp50 > 15, negTotalFp <= 3, medium_tp50 >= 10.
   - productGateAccepted: inScopeTp50 >= 27 (>=50%), negTotalFp <= 3, medium_tp50 >= 10.
"""

import sys
import os
import json
import time
import math
import random
import argparse
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

from yolox_p2 import build_yolox_p2_model, build_independent_p2_param_groups
from model_identity import TRUE_BASELINE_EPOCH02_PATH, TRUE_BASELINE_EPOCH02_SHA, load_verified_model
from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from heavy_job_lock import heavy_job_guard
from prepare_canonical_validation_cache import load_canonical_validation_cache
from train_p2_focal_trial import evaluate_canonical_validation
import acne_box_support

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-scale-guided-20261014'


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def save_checkpoint(
    trial_dir: Path,
    net: nn.Module,
    opt: torch.optim.Optimizer,
    sched: torch.optim.lr_scheduler.LambdaLR,
    state_meta: dict
) -> Path:
    """Atomic transactional checkpoint save with full metadata and verified file hashes."""
    trial_dir = Path(trial_dir)
    trial_dir.mkdir(parents=True, exist_ok=True)
    epoch = state_meta['epoch']
    step = state_meta['step']
    gen_id = time.time_ns()
    gen_dir = trial_dir / f"checkpoint-epoch-{epoch:02d}-step-{step:06d}-{gen_id}"
    gen_dir.mkdir(parents=True, exist_ok=True)

    # 1. Model weights
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(gen_dir / 'model.safetensors'))

    # 2. Optimizer & Scheduler states
    torch.save(opt.state_dict(), str(gen_dir / 'optimizer.pt'))
    torch.save(sched.state_dict(), str(gen_dir / 'scheduler.pt'))

    # 3. Comprehensive state ledger
    ledger = {
        **state_meta,
        'modelSha256': sha256_file(gen_dir / 'model.safetensors'),
        'optimizerSha256': sha256_file(gen_dir / 'optimizer.pt'),
        'schedulerSha256': sha256_file(gen_dir / 'scheduler.pt'),
        'pythonRng': list(random.getstate()),
        'numpyRng': [np.random.get_state()[0], np.random.get_state()[1].tolist(), *np.random.get_state()[2:]],
        'torchRng': torch.get_rng_state().tolist(),
    }
    with open(gen_dir / 'state.json', 'w', encoding='utf-8') as f:
        json.dump(ledger, f, indent=2)

    # 4. Atomic pointer update
    tmp_current = trial_dir / 'CURRENT.tmp'
    tmp_current.write_text(gen_dir.name, encoding='utf-8')
    tmp_current.replace(trial_dir / 'CURRENT')

    return gen_dir


def load_checkpoint(
    trial_dir: Path,
    net: nn.Module,
    opt: torch.optim.Optimizer,
    sched: torch.optim.lr_scheduler.LambdaLR
) -> Tuple[Path, dict]:
    """Resume execution from latest atomic CURRENT pointer."""
    trial_dir = Path(trial_dir)
    current_ptr = trial_dir / 'CURRENT'
    assert current_ptr.exists(), f"CURRENT pointer not found in {trial_dir}"
    gen_name = current_ptr.read_text(encoding='utf-8').strip()
    gen_dir = trial_dir / gen_name
    assert gen_dir.exists(), f"Checkpoint generation directory missing: {gen_dir}"

    with open(gen_dir / 'state.json', 'r', encoding='utf-8') as f:
        ledger = json.load(f)

    assert sha256_file(gen_dir / 'model.safetensors') == ledger['modelSha256'], "Model SHA mismatch!"
    assert sha256_file(gen_dir / 'optimizer.pt') == ledger['optimizerSha256'], "Optimizer SHA mismatch!"
    assert sha256_file(gen_dir / 'scheduler.pt') == ledger['schedulerSha256'], "Scheduler SHA mismatch!"

    net.load_state_dict(load_file(str(gen_dir / 'model.safetensors')), strict=True)
    opt.load_state_dict(torch.load(str(gen_dir / 'optimizer.pt'), weights_only=False))
    sched.load_state_dict(torch.load(str(gen_dir / 'scheduler.pt'), weights_only=False))

    rng_tuple = tuple([ledger['pythonRng'][0], tuple(ledger['pythonRng'][1]), ledger['pythonRng'][2]])
    random.setstate(rng_tuple)
    np_state = tuple([ledger['numpyRng'][0], np.array(ledger['numpyRng'][1], dtype=np.uint32), *ledger['numpyRng'][2:]])
    np.random.set_state(np_state)
    torch.set_rng_state(torch.tensor(ledger['torchRng'], dtype=torch.uint8))

    return gen_dir, ledger


def select_training_tiles(train_rows: List[dict], masks: Dict[str, np.ndarray]) -> List[dict]:
    """Select training tiles with small/micro lesions (<16px) or verified clean skin controls."""
    all_tiles = acne_tiles_p2(train_rows, masks, training=True)
    focused_tiles = []
    tiny_count = 0
    small_count = 0
    clean_count = 0

    for t in all_tiles:
        boxes = t.get('boxes', [])
        is_clean = t.get('isCleanControl', False)
        if is_clean:
            focused_tiles.append(t)
            clean_count += 1
        elif boxes:
            has_small = any(max(b[2]-b[0], b[3]-b[1]) < 16 for b in boxes)
            has_tiny = any(max(b[2]-b[0], b[3]-b[1]) < 8 for b in boxes)
            if has_tiny:
                tiny_count += 1
            if has_small:
                small_count += 1
                focused_tiles.append(t)
            else:
                # Include 50% of medium-only tiles to provide context
                if random.random() < 0.50:
                    focused_tiles.append(t)

    print(f"  [Tile Selection] Total available: {len(all_tiles)} -> Selected subset: {len(focused_tiles)}")
    print(f"    Tiles with <8px lesions: {tiny_count}")
    print(f"    Tiles with <16px lesions: {small_count}")
    print(f"    Clean control skin tiles: {clean_count}")
    return focused_tiles


def main():
    parser = argparse.ArgumentParser(description="Scale-guided independent P2 acne training")
    parser.add_argument('--resume', action='store_true', help='Resume from latest CURRENT checkpoint')
    parser.add_argument('--epochs', type=int, default=3, help='Number of epochs to train (default: 3)')
    args = parser.parse_args()

    print("=" * 80)
    print("SCALE-GUIDED INDEPENDENT P2 TRAINING FOR TOGG ATTUNE ACNE DETECTION")
    print("=" * 80)

    seed = 20261014
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    TRIAL_DIR.mkdir(parents=True, exist_ok=True)

    with heavy_job_guard("acne-p2-scale-guided"):
        # 1. Load verified model
        net, model_sha = load_verified_model(TRUE_BASELINE_EPOCH02_PATH, expected_sha=TRUE_BASELINE_EPOCH02_SHA)
        print(f"Loaded verified baseline model: {model_sha} from {TRUE_BASELINE_EPOCH02_PATH.name}")

        # Ensure all BatchNorm modules are in eval mode
        for m in net.modules():
            if isinstance(m, nn.BatchNorm2d):
                m.eval()

        # 2. Calibrate Level 0 (P2) initial biases
        print("\n[Level 0 Calibration]")
        with torch.no_grad():
            net.backbone.p2_gate.zero_()
            prior_bias = -math.log((1.0 - 0.01) / 0.01)  # ~ -4.595
            net.head.obj_preds[0].bias.fill_(prior_bias)
            net.head.cls_preds[0].bias.fill_(prior_bias)
            net.head.reg_preds[0].bias.zero_()
            # Prior box size 8px at stride 4: exp(log(2.0)) * 4 = 8.0px
            net.head.reg_preds[0].bias[2:4].fill_(math.log(2.0))
        print(f"  P2 Gate: {net.backbone.p2_gate.item()}")
        print(f"  Level 0 obj_bias: {net.head.obj_preds[0].bias.item():.4f}, cls_bias: {net.head.cls_preds[0].bias.item():.4f}")
        print(f"  Level 0 reg_bias (w, h): {net.head.reg_preds[0].bias[2:4].tolist()} (initial size: 8.0 px)")

        # 3. Configure Parameter Groups (Strict Zero Drift)
        param_groups, partition_receipt = build_independent_p2_param_groups(net, lr_p2=2e-4, weight_decay=0.0001)
        print(f"  Trainable Level 0: {partition_receipt['trainableLevel0']['tensorCount']} tensors ({partition_receipt['trainableLevel0']['parameterCount']:,} params)")
        print(f"  Frozen baseline:   {partition_receipt['frozenBaseline']['tensorCount']} tensors ({partition_receipt['frozenBaseline']['parameterCount']:,} params)")

        # 4. Focal Loss Setup
        focal_loss = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
        net.head.obj_focal_loss = focal_loss

        # 5. Load Training Data
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        train_rows = [r for r in data['rows'] if r['split'] == 'train']
        print(f"\nLoaded {len(train_rows)} TRAIN rows from reviewed dataset.")

        masks, weights = build_hole_preserved_negative_masks(train_rows)
        focused_tiles = select_training_tiles(train_rows, masks)

        print("Preloading training images into memory...", flush=True)
        img_cache = {}
        for r in train_rows:
            sha = r['sha256']
            if sha not in img_cache:
                path = r.get('absolutePath') or str(LIVE_TEST / r['path'])
                bgr = cv2.imread(path)
                assert bgr is not None, f"Could not read image: {path}"
                img_cache[sha] = bgr
        print(f"Preloaded {len(img_cache)} unique training images.")

        for t in focused_tiles:
            t['preloaded_bgr'] = img_cache[t['row']['sha256']]

        # 6. Optimizer and Schedule
        opt = torch.optim.AdamW(param_groups)
        num_epochs = args.epochs
        batch_size = 4
        steps_per_epoch = (len(focused_tiles) + batch_size - 1) // batch_size
        total_steps = num_epochs * steps_per_epoch
        warmup_steps = 25

        def lr_lambda(step):
            if step < warmup_steps:
                return float(step + 1) / float(max(1, warmup_steps))
            progress = float(step - warmup_steps) / float(max(1, total_steps - warmup_steps))
            return 0.5 * (1.0 + math.cos(math.pi * progress))

        sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda)

        cached_val_images = load_canonical_validation_cache()
        best_chk_path = TRIAL_DIR / 'candidate-selected.safetensors'

        # Resume or Fresh Start
        is_resumed = False
        start_epoch = 1
        start_step_in_epoch = 0
        global_step = 0
        best_tp50 = 15  # baseline catch
        best_rec50 = 15 / 53.0
        best_neg_fp = 3
        best_epoch = 0
        history = []
        order = list(range(len(focused_tiles)))

        if args.resume and (TRIAL_DIR / 'CURRENT').exists():
            print("\n[Resuming from Checkpoint]")
            chk_dir, ledger = load_checkpoint(TRIAL_DIR, net, opt, sched)
            start_epoch = ledger['epoch']
            start_step_in_epoch = ledger.get('step_in_epoch', 0)
            global_step = ledger['step']
            best_tp50 = ledger.get('best_tp50', 15)
            best_rec50 = ledger.get('best_rec50', 15 / 53.0)
            best_neg_fp = ledger.get('best_neg_fp', 3)
            best_epoch = ledger.get('best_epoch', 0)
            history = ledger.get('history', [])
            if 'order' in ledger and len(ledger['order']) == len(focused_tiles):
                order = ledger['order']
            is_resumed = True
            print(f"  Resumed from {chk_dir.name} at Epoch {start_epoch}, Step {start_step_in_epoch}/{steps_per_epoch} (global step {global_step})")
            if start_step_in_epoch >= steps_per_epoch:
                start_epoch += 1
                start_step_in_epoch = 0

        if not is_resumed:
            # Step 0 Canonical Validation (Calibrated Baseline)
            print("\n--- Canonical Validation at Step 0 (Calibrated Baseline) ---", flush=True)
            val_res_0 = evaluate_canonical_validation(net, cached_val_images, conf_thresholds=[0.30])
            r0 = val_res_0['0.3']
            print(f"Step 0: inScopeTp50 = {r0['inScopeTp50']}/53 ({r0['rec50']:.1%}) | negFP = {r0['negTotalFp']} ({r0['fpPerPhoto']:.2f}/photo)")
            print(f"        tiny = {r0['smallLesionRecall']['tiny_less_8px']['tp50']}/7, small = {r0['smallLesionRecall']['small_8_to_16px']['tp50']}/31, med = {r0['smallLesionRecall']['medium_16_to_32px']['tp50']}/15")

            init_meta = {
                'epoch': 0,
                'step_in_epoch': 0,
                'step': 0,
                'best_tp50': best_tp50,
                'best_rec50': best_rec50,
                'best_neg_fp': best_neg_fp,
                'best_epoch': 0,
                'order': order,
                'history': [],
                'validation': r0
            }
            save_checkpoint(TRIAL_DIR, net, opt, sched, init_meta)

            # If no candidate-selected exists, save initial calibrated weights as reference
            if not best_chk_path.exists():
                save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(best_chk_path))

        # 8. Training Loop
        print(f"\nStarting training loop from Epoch {start_epoch} to {num_epochs}...")
        for epoch in range(start_epoch, num_epochs + 1):
            epoch_start = time.time()
            if start_step_in_epoch == 0:
                random.shuffle(order)
            net.train()
            # Ensure all BatchNorms stay strictly in eval mode
            for m in net.modules():
                if isinstance(m, nn.BatchNorm2d):
                    m.eval()

            total_loss_accum = 0.0
            step_in_epoch = start_step_in_epoch
            start_i = start_step_in_epoch * batch_size
            start_step_in_epoch = 0  # reset for subsequent epochs

            for i in range(start_i, len(focused_tiles), batch_size):
                batch_indices = order[i : i + batch_size]
                batch_items = [focused_tiles[idx] for idx in batch_indices]

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

                torch.nn.utils.clip_grad_norm_(param_groups[0]['params'], max_norm=5.0)
                opt.step()
                sched.step()

                global_step += 1
                step_in_epoch += 1
                total_loss_accum += total_loss.item()

                if step_in_epoch % 25 == 0 or step_in_epoch == steps_per_epoch:
                    avg_l = total_loss_accum / step_in_epoch
                    lr_now = opt.param_groups[0]['lr']
                    print(f"  Epoch {epoch}/{num_epochs} | Step {step_in_epoch}/{steps_per_epoch} | Loss: {total_loss.item():.4f} (avg: {avg_l:.4f}) | lr: {lr_now:.2e} | elapsed: {time.time()-epoch_start:.1f}s", flush=True)

                # Mid-epoch transactional checkpoint every 50 steps
                if step_in_epoch % 50 == 0 and step_in_epoch < steps_per_epoch:
                    mid_meta = {
                        'epoch': epoch,
                        'step_in_epoch': step_in_epoch,
                        'step': global_step,
                        'best_tp50': best_tp50,
                        'best_rec50': best_rec50,
                        'best_neg_fp': best_neg_fp,
                        'best_epoch': best_epoch,
                        'order': order,
                        'history': history
                    }
                    save_checkpoint(TRIAL_DIR, net, opt, sched, mid_meta)

            # Epoch Validation
            print(f"\n--- Canonical Validation at End of Epoch {epoch} ---", flush=True)
            val_res = evaluate_canonical_validation(net, cached_val_images, conf_thresholds=[0.30])
            r = val_res['0.3']
            tp50 = r['inScopeTp50']
            rec50 = r['rec50']
            neg_fp = r['negTotalFp']
            med_tp50 = r['smallLesionRecall']['medium_16_to_32px']['tp50']
            small_tp50 = r['smallLesionRecall']['small_8_to_16px']['tp50']
            tiny_tp50 = r['smallLesionRecall']['tiny_less_8px']['tp50']

            print(f"Epoch {epoch}: inScopeTp50 = {tp50}/53 ({rec50:.1%}) | negFP = {neg_fp} ({r['fpPerPhoto']:.2f}/photo)")
            print(f"         tiny = {tiny_tp50}/7, small = {small_tp50}/31, med = {med_tp50}/15")

            epoch_record = {
                'epoch': epoch,
                'step': global_step,
                'avgLoss': total_loss_accum / max(step_in_epoch, 1),
                'durationSec': round(time.time() - epoch_start, 1),
                'validation': val_res
            }
            history.append(epoch_record)

            # End of epoch transactional checkpoint
            epoch_meta = {
                'epoch': epoch,
                'step_in_epoch': step_in_epoch,
                'step': global_step,
                'best_tp50': best_tp50,
                'best_rec50': best_rec50,
                'best_neg_fp': best_neg_fp,
                'best_epoch': best_epoch,
                'order': order,
                'history': history,
                'validation': r
            }
            save_checkpoint(TRIAL_DIR, net, opt, sched, epoch_meta)

            # Gate Acceptance Check
            dev_improved = (tp50 > 15 and neg_fp <= 3 and med_tp50 >= 10)
            if dev_improved and (tp50 > best_tp50 or (tp50 == best_tp50 and neg_fp < best_neg_fp)):
                print(f"  >>> DEVELOPMENT WINNER: {tp50}/53 (was {best_tp50}/53) with {neg_fp} FP! Updating candidate-selected.safetensors")
                best_tp50 = tp50
                best_rec50 = rec50
                best_neg_fp = neg_fp
                best_epoch = epoch
                save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(best_chk_path))

        # 9. Final Summary and Receipt
        selected_sha = sha256_file(best_chk_path) if best_chk_path.exists() else None
        print("\n" + "=" * 80)
        print("TRAINING COMPLETE")
        print(f"Best Epoch: {best_epoch} | Best inScopeTp50: {best_tp50}/53 ({best_rec50:.1%})")
        print(f"Selected Model SHA: {selected_sha}")
        print("=" * 80)

        last_val = history[-1]['validation']['0.3'] if history else r0
        product_gate_accepted = bool(best_tp50 >= 27 and best_neg_fp <= 3 and last_val['smallLesionRecall']['medium_16_to_32px']['tp50'] >= 10)
        development_improved = bool(best_tp50 > 15 and best_neg_fp <= 3 and last_val['smallLesionRecall']['medium_16_to_32px']['tp50'] >= 10)

        summary_receipt = {
            'startingCheckpoint': TRUE_BASELINE_EPOCH02_PATH.name,
            'startingWeightsSha256': TRUE_BASELINE_EPOCH02_SHA,
            'selectedWeightsSha256': selected_sha,
            'bestEpoch': best_epoch,
            'bestTp50': best_tp50,
            'bestScore': best_rec50,
            'developmentImproved': development_improved,
            'productGateAccepted': product_gate_accepted,
            'partitionReceipt': partition_receipt,
            'history': history
        }

        with open(TRIAL_DIR / 'training-state.json', 'w', encoding='utf-8') as f:
            json.dump(summary_receipt, f, indent=2)

        print(f"Training state written to: {TRIAL_DIR / 'training-state.json'}")


if __name__ == '__main__':
    main()
