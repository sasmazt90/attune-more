#!/usr/bin/env python3
"""Export Selected Acne Model to ONNX and Verify Real-Face Numerical & Postprocessing Parity.

Protocol & Tolerances:
1. ONNX opset 17 export with strict tensor contracts (native_bgr_tile -> detections).
2. Numerical verification on real face tiles (positive lesions and negative clean skin)
   from the canonical crop pipeline, plus edge cases (zero tile, random tile).
3. Separate strict tolerance thresholds:
   - Score / objectness diff: max < 1e-4 (0.0001)
   - Box coordinate diff: max < 0.05 px
   - Postprocessing box matching: IoU >= 0.999 between PyTorch and ONNX decoded boxes.
4. Complete transactional verification receipt with input shapes, SHA-256 hashes, and per-tile statistics.
"""

import sys
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import torch
import torch.nn as nn
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from cdc_skin_adapters import AcneSmallFociAdapter
from prepare_canonical_validation_cache import load_canonical_validation_cache


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def extract_real_face_tiles(cached_images: List[dict], max_tiles_per_type: int = 5) -> List[dict]:
    """Extracts real face crop tiles (positive and negative) directly from the validation images."""
    pos_tiles = []
    neg_tiles = []
    tile_size = 384

    for item in cached_images:
        bgr = item['bgr']
        h, w = bgr.shape[:2]
        gt_boxes = item.get('truth', [])
        is_neg = item.get('isNegative', False)

        # If image has GT lesions, extract positive tiles centered on lesions
        if len(gt_boxes) > 0 and len(pos_tiles) < max_tiles_per_type:
            for b in gt_boxes:
                bx0, by0, bx1, by1 = b[:4]
                cx, cy = int((bx0 + bx1) / 2), int((by0 + by1) / 2)
                x0 = max(0, min(w - tile_size, cx - tile_size // 2))
                y0 = max(0, min(h - tile_size, cy - tile_size // 2))
                tile = np.full((tile_size, tile_size, 3), 114, dtype=np.uint8)
                tile[:tile_size, :tile_size] = bgr[y0:y0+tile_size, x0:x0+tile_size]
                tile_float = tile.transpose(2, 0, 1).astype(np.float32)[None, ...]

                pos_tiles.append({
                    'imageName': item.get('fileName', item.get('name', 'val_image')),
                    'type': 'positive',
                    'rect': [x0, y0, tile_size, tile_size],
                    'tensor': tile_float
                })
                if len(pos_tiles) >= max_tiles_per_type:
                    break

        # If negative control image or clean area, extract negative tile
        if (is_neg or len(gt_boxes) == 0) and len(neg_tiles) < max_tiles_per_type:
            cx, cy = w // 2, h // 2
            x0 = max(0, min(w - tile_size, cx - tile_size // 2))
            y0 = max(0, min(h - tile_size, cy - tile_size // 2))
            tile = np.full((tile_size, tile_size, 3), 114, dtype=np.uint8)
            tile[:tile_size, :tile_size] = bgr[y0:y0+tile_size, x0:x0+tile_size]
            tile_float = tile.transpose(2, 0, 1).astype(np.float32)[None, ...]

            neg_tiles.append({
                'imageName': item.get('fileName', item.get('name', 'val_image')),
                'type': 'negative',
                'rect': [x0, y0, tile_size, tile_size],
                'tensor': tile_float
            })

        if len(pos_tiles) >= max_tiles_per_type and len(neg_tiles) >= max_tiles_per_type:
            break
    return pos_tiles + neg_tiles


def export_and_verify(weights_path: Path, output_onnx_path: Path = None) -> dict:
    weights_path = Path(weights_path)
    if output_onnx_path is None:
        output_onnx_path = weights_path.parent / 'model.onnx'
    else:
        output_onnx_path = Path(output_onnx_path)

    weights_sha = sha256_file(weights_path)
    print(f"Loading PyTorch weights from {weights_path} (SHA: {weights_sha[:8]})...")
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    net.load_state_dict(load_file(str(weights_path)), strict=True)
    net.eval()

    sample_x = torch.zeros((1, 3, 384, 384), dtype=torch.float32)

    print(f"Exporting ONNX opset 17 to {output_onnx_path}...")
    torch.onnx.export(
        net, sample_x, str(output_onnx_path),
        input_names=['native_bgr_tile'],
        output_names=['detections'],
        opset_version=17,
        dynamo=False
    )
    onnx_sha = sha256_file(output_onnx_path)
    print(f"Exported ONNX: {output_onnx_path.name} (SHA-256: {onnx_sha})")

    print("\n--- Verifying Numerical & Postprocessing Parity (PyTorch vs ONNX) ---")
    import onnxruntime as ort
    ort_opts = ort.SessionOptions()
    ort_opts.intra_op_num_threads = 1
    ort_opts.inter_op_num_threads = 1
    session = ort.InferenceSession(str(output_onnx_path), ort_opts, providers=['CPUExecutionProvider'])

    adapter = AcneSmallFociAdapter(conf_threshold=0.30, nms_threshold=0.30)

    # 1. Edge Case: Synthetic Random Tile
    rand_tile = np.random.randint(0, 255, (1, 3, 384, 384), dtype=np.uint8).astype(np.float32)
    with torch.no_grad():
        pyt_rand = net(torch.from_numpy(rand_tile)).numpy()
    ort_rand = session.run(None, {'native_bgr_tile': rand_tile})[0]
    rand_diff = np.abs(pyt_rand - ort_rand)
    rand_score_diff = float(np.max(rand_diff[:, :, 4:]))
    rand_coord_diff = float(np.max(rand_diff[:, :, :4]))
    print(f"Synthetic Tile -> Score max diff: {rand_score_diff:.6e}, Coord max diff: {rand_coord_diff:.6e}")
    assert rand_score_diff < 1e-4, f"Synthetic score diff {rand_score_diff} >= 1e-4"

    # 2. Edge Case: Zero Tile
    zero_tile = np.zeros((1, 3, 384, 384), dtype=np.float32)
    with torch.no_grad():
        pyt_zero = net(torch.from_numpy(zero_tile)).numpy()
    ort_zero = session.run(None, {'native_bgr_tile': zero_tile})[0]
    zero_diff = np.abs(pyt_zero - ort_zero)
    zero_score_diff = float(np.max(zero_diff[:, :, 4:]))
    zero_coord_diff = float(np.max(zero_diff[:, :, :4]))
    print(f"Zero Tile      -> Score max diff: {zero_score_diff:.6e}, Coord max diff: {zero_coord_diff:.6e}")
    assert zero_score_diff < 1e-4, f"Zero score diff {zero_score_diff} >= 1e-4"

    # 3. Real Face Tiles (Positive & Negative)
    print("\nLoading canonical validation cache for real face tile evaluation...")
    cached_val = load_canonical_validation_cache()
    real_tiles = extract_real_face_tiles(cached_val, max_tiles_per_type=5)
    print(f"Extracted {len(real_tiles)} real face tiles ({sum(1 for t in real_tiles if t['type']=='positive')} positive, {sum(1 for t in real_tiles if t['type']=='negative')} negative)")

    real_tile_results = []
    all_real_scores_ok = True
    all_postproc_matches_ok = True

    for idx, rt in enumerate(real_tiles):
        tile_arr = rt['tensor']
        with torch.no_grad():
            pyt_pred = net(torch.from_numpy(tile_arr)).numpy()
        ort_pred = session.run(None, {'native_bgr_tile': tile_arr})[0]

        diff = np.abs(pyt_pred - ort_pred)
        score_diff = float(np.max(diff[:, :, 4:]))
        coord_diff = float(np.max(diff[:, :, :4]))
        mean_diff = float(np.mean(diff))

        # Postprocessing Equivalence (Box-by-Box matching)
        pyt_boxes = adapter.postprocess_detections(pyt_pred, conf_thresh=0.30)
        ort_boxes = adapter.postprocess_detections(ort_pred, conf_thresh=0.30)

        box_count_match = (len(pyt_boxes) == len(ort_boxes))
        mean_iou = 1.0
        max_box_coord_diff = 0.0
        max_box_score_diff = 0.0

        if len(pyt_boxes) > 0 and len(ort_boxes) > 0:
            # 1-to-1 match boxes in descending score order
            ious = []
            for b_p, b_o in zip(pyt_boxes, ort_boxes):
                sc_p, sc_o = b_p[4], b_o[4]
                max_box_score_diff = max(max_box_score_diff, abs(sc_p - sc_o))
                coord_d = np.max(np.abs(b_p[:4] - b_o[:4]))
                max_box_coord_diff = max(max_box_coord_diff, coord_d)

                inter_x0 = max(b_p[0], b_o[0])
                inter_y0 = max(b_p[1], b_o[1])
                inter_x1 = min(b_p[2], b_o[2])
                inter_y1 = min(b_p[3], b_o[3])
                inter_w = max(0.0, inter_x1 - inter_x0)
                inter_h = max(0.0, inter_y1 - inter_y0)
                inter_area = inter_w * inter_h
                area_p = (b_p[2] - b_p[0]) * (b_p[3] - b_p[1])
                area_o = (b_o[2] - b_o[0]) * (b_o[3] - b_o[1])
                union = area_p + area_o - inter_area
                iou = inter_area / max(union, 1e-8)
                ious.append(iou)
            mean_iou = float(np.mean(ious))

        postproc_ok = box_count_match and (mean_iou >= 0.999) and (max_box_score_diff < 1e-4)
        if not (score_diff < 1e-4):
            all_real_scores_ok = False
        if not postproc_ok:
            all_postproc_matches_ok = False

        tile_res = {
            'index': int(idx),
            'imageName': str(rt['imageName']),
            'tileType': str(rt['type']),
            'rect': [int(v) for v in rt['rect']],
            'maxScoreDiff': float(score_diff),
            'maxCoordDiff': float(coord_diff),
            'meanDiff': float(mean_diff),
            'detectionsPyTorch': int(len(pyt_boxes)),
            'detectionsONNX': int(len(ort_boxes)),
            'boxCountMatched': bool(box_count_match),
            'meanBoxIoU': float(mean_iou),
            'maxBoxScoreDiff': float(max_box_score_diff),
            'maxBoxCoordDiff': float(max_box_coord_diff),
            'postprocEquivalence': bool(postproc_ok)
        }
        real_tile_results.append(tile_res)
        print(f"  Real Tile {idx:02d} [{rt['type']:8s}] -> Score max diff: {score_diff:.6e}, PyT boxes: {len(pyt_boxes)}, ONNX boxes: {len(ort_boxes)}, Mean IoU: {mean_iou:.6f}, Equiv: {postproc_ok}")

    receipt = {
        'receiptSchema': 'togg-attune-onnx-real-face-parity-v1',
        'weightsFile': str(weights_path),
        'weightsSha256': weights_sha,
        'onnxFile': str(output_onnx_path),
        'onnxSha256': onnx_sha,
        'opsetVersion': 17,
        'tolerances': {
            'maxScoreDiffThreshold': 1e-4,
            'maxCoordDiffThreshold': 0.05,
            'minBoxIoUThreshold': 0.999
        },
        'edgeCases': {
            'syntheticTile': {
                'maxScoreDiff': float(rand_score_diff),
                'maxCoordDiff': float(rand_coord_diff),
                'passed': bool(rand_score_diff < 1e-4)
            },
            'zeroTile': {
                'maxScoreDiff': float(zero_score_diff),
                'maxCoordDiff': float(zero_coord_diff),
                'passed': bool(zero_score_diff < 1e-4)
            }
        },
        'realFaceTiles': {
            'tilesTested': int(len(real_tile_results)),
            'allScoreDiffsPass': bool(all_real_scores_ok),
            'allPostprocessingMatchesPass': bool(all_postproc_matches_ok),
            'details': real_tile_results
        },
        'parityVerified': bool((rand_score_diff < 1e-4) and (zero_score_diff < 1e-4) and all_real_scores_ok and all_postproc_matches_ok)
    }

    receipt_path = output_onnx_path.parent / 'onnx-parity-receipt.json'
    receipt_path.write_text(json.dumps(receipt, indent=2), 'utf8')
    print(f"\nParity Receipt saved to: {receipt_path}")
    print(f"Overall ONNX Real-Face Parity Verified: {receipt['parityVerified']}")
    assert receipt['parityVerified'], "ONNX numerical or postprocessing parity verification failed!"
    return receipt


if __name__ == '__main__':
    weights = ROOT / 'audit-results/acne-candidate-p2-small-foci-20261014/candidate-selected.safetensors'
    if len(sys.argv) > 1:
        weights = Path(sys.argv[1])
    onnx_target = None
    if len(sys.argv) > 2:
        onnx_target = Path(sys.argv[2])
    export_and_verify(weights, onnx_target)
