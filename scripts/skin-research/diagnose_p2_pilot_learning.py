#!/usr/bin/env python3
"""Diagnose Real P2 Learning on a Fixed Representative TRAIN Pilot Group.

Integrity Rules (User Directives):
1. Fixes a small, representative TRAIN pilot group:
   - diverse source photos ('smart', 'old-skin', 'v11', 'arnold'),
   - micro (<8px), small (8–16px), and medium (16–32px) lesions,
   - verified clean skin control negatives from negative photos.
2. Evaluates and compares on this exact pilot:
   - Baseline winner (cf3a2ba4)
   - Step-0 calibrated (18e94a95)
   - Epoch 1 checkpoint (625e3e20)
   - Epoch 2 checkpoint (83d19d4f)
   - Epoch 3 checkpoint (2d9571dad8)
3. 1-to-1 Bipartite Matching: A single predicted candidate CANNOT match multiple ground truth targets.
4. Clean Skin FP Scope: Evaluated strictly against verified clean skin (mask > 0); UNKNOWN skin is not penalized.
5. Saves audit receipt: audit-results/acne-pilot-diagnosis-20261014/pilot_learning_receipt.json.
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any
import numpy as np
import cv2
import torch
import torchvision

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from safetensors.torch import load_file
from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2
from model_identity import TRUE_BASELINE_EPOCH02_PATH, TRUE_BASELINE_EPOCH02_SHA

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
OUT_DIR = ROOT / 'audit-results/acne-pilot-diagnosis-20261014'

MODELS = {
    'baseline': {
        'path': TRUE_BASELINE_EPOCH02_PATH,
        'sha': TRUE_BASELINE_EPOCH02_SHA,
        'desc': 'Verified Baseline Winner (frozen upper)'
    },
    'step0': {
        'path': ROOT / 'audit-results/acne-candidate-p2-scale-guided-20261014/checkpoint-epoch-00-step-000000-1792005708951914200/model.safetensors',
        'sha': '18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655',
        'desc': 'Step 0 Calibrated (prior 0.01, 8px prior box)'
    },
    'epoch1': {
        'path': ROOT / 'audit-results/acne-candidate-p2-scale-guided-20261014/checkpoint-epoch-01-step-000207-1792006464849481400/model.safetensors',
        'sha': '625e3e20f626e8d0b8da0803faf0a9cf6d1fc08ff7214f6697407f7c8bb25da9',
        'desc': 'Completed Epoch 1 (frozen upper)'
    },
    'epoch2': {
        'path': ROOT / 'audit-results/acne-candidate-p2-scale-guided-20261014/checkpoint-epoch-02-step-000414-1792007306411803500/model.safetensors',
        'sha': '83d19d4f0114070b3e8d0a71767bb046e8113715276a33a9713511b3c3d98b39',
        'desc': 'Completed Epoch 2 (frozen upper)'
    },
    'epoch3': {
        'path': ROOT / 'audit-results/acne-candidate-p2-scale-guided-20261014/checkpoint-epoch-03-step-000621-1792008046683220700/model.safetensors',
        'sha': '2d9571dad817c5ef9719add03cc7555419b87e60faf18987f6346cd5e9bf5bd3',
        'desc': 'Completed Epoch 3 (frozen upper)'
    }
}


def build_pilot_set(train_rows: List[dict], masks: Dict[str, np.ndarray], weights: Dict[str, np.ndarray]) -> List[dict]:
    """Select a fixed, balanced pilot set with diverse sources, lesion sizes, and clean controls."""
    all_tiles = acne_tiles_p2(train_rows, masks, training=True)

    micro_tiles = []
    small_tiles = []
    med_tiles = []
    clean_tiles = []

    seen_shas = set()

    for t in all_tiles:
        boxes = t.get('boxes', [])
        sha = t['row']['sha256']
        is_clean = t.get('isCleanControl', False)

        if is_clean:
            if sha not in seen_shas or len(clean_tiles) < 8:
                clean_tiles.append(t)
                seen_shas.add(sha)
        elif boxes:
            dims = [max(b[2]-b[0], b[3]-b[1]) for b in boxes]
            min_dim = min(dims)
            if min_dim < 8.0:
                micro_tiles.append(t)
            elif min_dim < 16.0:
                small_tiles.append(t)
            else:
                med_tiles.append(t)

    # Deterministic selection
    micro_selected = micro_tiles[:8]
    small_selected = small_tiles[:8]
    med_selected = med_tiles[:6]
    clean_selected = clean_tiles[:8]

    pilot = micro_selected + small_selected + med_selected + clean_selected
    print(f"Constructed Fixed Pilot Group ({len(pilot)} tiles):")
    print(f"  Micro tiles (<8px):   {len(micro_selected)}")
    print(f"  Small tiles (8-16px): {len(small_selected)}")
    print(f"  Medium tiles (16-32px): {len(med_selected)}")
    print(f"  Clean control tiles:  {len(clean_selected)}")

    # Preload images and attach clean masks
    img_cache = {}
    for t in pilot:
        sha = t['row']['sha256']
        if sha not in img_cache:
            p = t['row'].get('absolutePath') or str(LIVE_TEST / t['row']['path'])
            bgr = cv2.imread(p)
            assert bgr is not None, f"Could not read {p}"
            img_cache[sha] = bgr
        t['preloaded_bgr'] = img_cache[sha]
        t['clean_mask'] = masks[sha]
        t['mask_weight'] = weights[sha]

    return pilot


def evaluate_pilot_mode(net, pilot_tiles: List[dict], mode: str, conf_thresh: float = 0.30) -> dict:
    """Evaluate pilot tiles under specific pyramid mode with strict 1-to-1 matching and clean mask support."""
    net.eval()

    total_gt = 0
    gt_by_size = {'tiny_less_8px': 0, 'small_8_to_16px': 0, 'medium_16_to_32px': 0}
    tp50_by_size = {'tiny_less_8px': 0, 'small_8_to_16px': 0, 'medium_16_to_32px': 0}
    tp30_by_size = {'tiny_less_8px': 0, 'small_8_to_16px': 0, 'medium_16_to_32px': 0}

    matched_ious = []
    matched_objs = []
    matched_clss = []
    matched_scores = []

    target_details = []

    clean_fp_count = 0
    clean_tile_count = 0

    for t in pilot_tiles:
        bgr = t['preloaded_bgr']
        a, b, endx, endy = t['rect']
        tile = np.full((384, 384, 3), 114, dtype=np.uint8)
        crop = bgr[b:endy, a:endx]
        tile[:crop.shape[0], :crop.shape[1]] = crop
        inp = torch.from_numpy(tile.transpose(2, 0, 1)).unsqueeze(0).float()

        with torch.no_grad():
            out = net(inp)[0]  # [12240, 6] -> [cx, cy, w, h, obj, cls]

        # Slice by mode
        if mode == 'p2_only':
            pred = out[:9216]
        elif mode == 'p3_p4_p5_only':
            pred = out[9216:]
        else:
            pred = out

        # Compute candidate boxes
        scores = pred[:, 4] * pred[:, 5]
        mask_conf = scores >= conf_thresh
        filt = pred[mask_conf]
        sc = scores[mask_conf]

        cands = []
        if len(filt) > 0:
            cx, cy, bw, bh = filt[:, 0], filt[:, 1], filt[:, 2], filt[:, 3]
            x0 = torch.clamp(cx - bw / 2, min=0.0)
            y0 = torch.clamp(cy - bh / 2, min=0.0)
            x1 = torch.clamp(cx + bw / 2, max=384.0)
            y1 = torch.clamp(cy + bh / 2, max=384.0)
            cand_boxes = torch.stack([x0, y0, x1, y1], dim=1)

            # NMS per tile
            keep = torchvision.ops.nms(cand_boxes, sc, iou_threshold=0.45)
            for k in keep:
                cands.append({
                    'box': cand_boxes[k].tolist(),
                    'score': sc[k].item(),
                    'obj': filt[k, 4].item(),
                    'cls': filt[k, 5].item()
                })

        boxes_gt = t.get('boxes', [])
        is_clean = t.get('isCleanControl', False)
        sha = t['row']['sha256']

        if is_clean:
            clean_tile_count += 1
            clean_mask = t.get('clean_mask')
            for c in cands:
                cx0, cy0, cx1, cy1 = c['box']
                full_cx = int(round((cx0 + cx1) / 2.0 + a))
                full_cy = int(round((cy0 + cy1) / 2.0 + b))
                # Only count as FP if center lands inside verified clean skin polygon (mask > 0)
                if 0 <= full_cy < clean_mask.shape[0] and 0 <= full_cx < clean_mask.shape[1]:
                    if clean_mask[full_cy, full_cx] > 0:
                        clean_fp_count += 1
            continue

        num_gt = len(boxes_gt)
        num_cand = len(cands)

        # Count ground truths by size
        for gi, bx in enumerate(boxes_gt):
            gx0, gy0, gx1, gy1 = bx
            dim = max(gx1 - gx0, gy1 - gy0)
            grp = 'tiny_less_8px' if dim < 8.0 else ('small_8_to_16px' if dim < 16.0 else 'medium_16_to_32px')
            total_gt += 1
            gt_by_size[grp] += 1

        if num_gt == 0 or num_cand == 0:
            for gi, bx in enumerate(boxes_gt):
                gx0, gy0, gx1, gy1 = bx
                dim = max(gx1 - gx0, gy1 - gy0)
                grp = 'tiny_less_8px' if dim < 8.0 else ('small_8_to_16px' if dim < 16.0 else 'medium_16_to_32px')
                target_details.append({
                    'id': f"{sha[:8]}_g{gi}_{int(round(gx0+a))}_{int(round(gy0+b))}",
                    'category': grp,
                    'dim': round(dim, 1),
                    'matched_50': False,
                    'matched_30': False,
                    'matched_iou': 0.0,
                    'score': 0.0
                })
            continue

        # Compute IoU matrix
        iou_matrix = np.zeros((num_gt, num_cand), dtype=np.float32)
        for gi, gbx in enumerate(boxes_gt):
            gx0, gy0, gx1, gy1 = gbx
            for ci, c in enumerate(cands):
                cx0, cy0, cx1, cy1 = c['box']
                ix0 = max(gx0, cx0)
                iy0 = max(gy0, cy0)
                ix1 = min(gx1, cx1)
                iy1 = min(gy1, cy1)
                iw = max(0.0, ix1 - ix0)
                ih = max(0.0, iy1 - iy0)
                inter = iw * ih
                union = (gx1 - gx0) * (gy1 - gy0) + (cx1 - cx0) * (cy1 - cy0) - inter
                iou_matrix[gi, ci] = inter / max(union, 1e-6)

        # 1. Greedy 1-to-1 matching for IoU >= 0.50
        matched_gt_50 = {}
        matched_cand_50 = set()
        pairs_50 = []
        for gi in range(num_gt):
            for ci in range(num_cand):
                if iou_matrix[gi, ci] >= 0.50:
                    pairs_50.append((iou_matrix[gi, ci], gi, ci))
        pairs_50.sort(key=lambda x: x[0], reverse=True)
        for iou_val, gi, ci in pairs_50:
            if gi not in matched_gt_50 and ci not in matched_cand_50:
                matched_gt_50[gi] = ci
                matched_cand_50.add(ci)
                bx = boxes_gt[gi]
                dim = max(bx[2] - bx[0], bx[3] - bx[1])
                grp = 'tiny_less_8px' if dim < 8.0 else ('small_8_to_16px' if dim < 16.0 else 'medium_16_to_32px')
                tp50_by_size[grp] += 1
                matched_ious.append(iou_val)
                matched_objs.append(cands[ci]['obj'])
                matched_clss.append(cands[ci]['cls'])
                matched_scores.append(cands[ci]['score'])

        # 2. Greedy 1-to-1 matching for IoU >= 0.30
        matched_gt_30 = {}
        matched_cand_30 = set()
        pairs_30 = []
        for gi in range(num_gt):
            for ci in range(num_cand):
                if iou_matrix[gi, ci] >= 0.30:
                    pairs_30.append((iou_matrix[gi, ci], gi, ci))
        pairs_30.sort(key=lambda x: x[0], reverse=True)
        for iou_val, gi, ci in pairs_30:
            if gi not in matched_gt_30 and ci not in matched_cand_30:
                matched_gt_30[gi] = ci
                matched_cand_30.add(ci)
                bx = boxes_gt[gi]
                dim = max(bx[2] - bx[0], bx[3] - bx[1])
                grp = 'tiny_less_8px' if dim < 8.0 else ('small_8_to_16px' if dim < 16.0 else 'medium_16_to_32px')
                tp30_by_size[grp] += 1

        # Record target-level detail
        for gi, bx in enumerate(boxes_gt):
            gx0, gy0, gx1, gy1 = bx
            dim = max(gx1 - gx0, gy1 - gy0)
            grp = 'tiny_less_8px' if dim < 8.0 else ('small_8_to_16px' if dim < 16.0 else 'medium_16_to_32px')
            m50 = (gi in matched_gt_50)
            m30 = (gi in matched_gt_30)
            cand_ci = matched_gt_50.get(gi, matched_gt_30.get(gi, None))
            best_iou_val = float(iou_matrix[gi, cand_ci]) if cand_ci is not None else 0.0
            cand_sc = cands[cand_ci]['score'] if cand_ci is not None else 0.0
            target_details.append({
                'id': f"{sha[:8]}_g{gi}_{int(round(gx0+a))}_{int(round(gy0+b))}",
                'category': grp,
                'dim': round(dim, 1),
                'matched_50': m50,
                'matched_30': m30,
                'matched_iou': round(best_iou_val, 4),
                'score': round(cand_sc, 4)
            })

    total_tp50 = sum(tp50_by_size.values())
    total_tp30 = sum(tp30_by_size.values())

    return {
        'mode': mode,
        'totalGt': total_gt,
        'tp50': total_tp50,
        'rec50': round(total_tp50 / max(total_gt, 1), 4),
        'tp30': total_tp30,
        'rec30': round(total_tp30 / max(total_gt, 1), 4),
        'bySize': {
            k: {
                'gt': gt_by_size[k],
                'tp50': tp50_by_size[k],
                'rec50': round(tp50_by_size[k] / max(gt_by_size[k], 1), 4)
            } for k in gt_by_size
        },
        'avgMatchedIoU': round(float(np.mean(matched_ious)), 4) if matched_ious else 0.0,
        'avgObjProb': round(float(np.mean(matched_objs)), 4) if matched_objs else 0.0,
        'avgClsProb': round(float(np.mean(matched_clss)), 4) if matched_clss else 0.0,
        'avgScore': round(float(np.mean(matched_scores)), 4) if matched_scores else 0.0,
        'cleanFpCount': clean_fp_count,
        'cleanTilesEvaluated': clean_tile_count,
        'fpPerCleanTile': round(clean_fp_count / max(clean_tile_count, 1), 3),
        'targetDetails': target_details
    }


def main():
    print("=" * 80)
    print("DIAGNOSING REAL P2 LEARNING ON FIXED TRAIN PILOT GROUP (1-TO-1 MATCHING)")
    print("=" * 80)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    train_rows = [r for r in data['rows'] if r['split'] == 'train']
    masks, weights = build_hole_preserved_negative_masks(train_rows)

    pilot_tiles = build_pilot_set(train_rows, masks, weights)

    receipt = {
        'timestamp': time.time(),
        'pilotTileCount': len(pilot_tiles),
        'matchingContract': 'Strict 1-to-1 greedy bipartite matching; clean skin FP verified inside active clean skin mask only',
        'models': {}
    }

    modes = ['only_p2', 'only_p3_p4_p5', 'combined']

    for m_key, m_info in MODELS.items():
        m_path = m_info['path']
        assert m_path.exists(), f"Model path missing: {m_path}"
        print(f"\n--- Evaluating Model: {m_key.upper()} ({m_info['sha'][:16]}...) ---")

        net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
        st = load_file(str(m_path))
        net.load_state_dict(st)

        model_results = {'sha256': m_info['sha'], 'description': m_info['desc'], 'modes': {}}

        for mode_name in modes:
            internal_mode = 'p2_only' if mode_name == 'only_p2' else ('p3_p4_p5_only' if mode_name == 'only_p3_p4_p5' else 'combined')
            res = evaluate_pilot_mode(net, pilot_tiles, mode=internal_mode, conf_thresh=0.30)
            model_results['modes'][mode_name] = res

            bs = res['bySize']
            print(f"  [{mode_name:15s}] IoU50: {res['tp50']}/{res['totalGt']} ({res['rec50']:.1%}) | "
                  f"Tiny: {bs['tiny_less_8px']['tp50']}/{bs['tiny_less_8px']['gt']} | "
                  f"Small: {bs['small_8_to_16px']['tp50']}/{bs['small_8_to_16px']['gt']} | "
                  f"Med: {bs['medium_16_to_32px']['tp50']}/{bs['medium_16_to_32px']['gt']} | "
                  f"Clean FP: {res['cleanFpCount']} ({res['fpPerCleanTile']:.2f}/tile) | "
                  f"Avg IoU: {res['avgMatchedIoU']:.3f} | Obj: {res['avgObjProb']:.3f} | Cls: {res['avgClsProb']:.3f}")

        receipt['models'][m_key] = model_results

    out_file = OUT_DIR / 'pilot_learning_receipt.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2)

    print(f"\nPilot learning diagnosis complete! Receipt written to:\n{out_file}")


if __name__ == '__main__':
    main()
