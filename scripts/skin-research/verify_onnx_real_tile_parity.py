#!/usr/bin/env python3
"""Verify Numerical Parity between PyTorch and ONNX Models on Real Validation Face Tiles."""

import sys
import os
import json
import numpy as np
import torch
from pathlib import Path
from safetensors.torch import load_file
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from prepare_canonical_validation_cache import load_canonical_validation_cache

TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-focal-20261013'
WEIGHTS_PATH = TRIAL_DIR / 'candidate-selected.safetensors'
ONNX_PATH = TRIAL_DIR / 'candidate.onnx'


def test_real_tile_parity():
    print("=== PyTorch vs ONNX Parity on Real Face Tiles ===", flush=True)
    assert WEIGHTS_PATH.exists(), f"Weights not found: {WEIGHTS_PATH}"
    assert ONNX_PATH.exists(), f"ONNX not found: {ONNX_PATH}"

    # 1. Load PyTorch model
    pyt_net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    pyt_net.load_state_dict(load_file(str(WEIGHTS_PATH)), strict=True)
    pyt_net.eval()

    # 2. Load ONNX model
    ort_session = ort.InferenceSession(str(ONNX_PATH), providers=['CPUExecutionProvider'])

    # 3. Load canonical validation cache
    cached_images = load_canonical_validation_cache()
    print(f"Loaded {len(cached_images)} images from validation cache.", flush=True)

    # 4. Extract real tiles from first 5 real photos
    max_pixel_diff_all = 0.0
    max_score_diff_all = 0.0
    tiles_tested = 0

    for item in cached_images[:5]:
        bgr = item['bgr']
        h, w = bgr.shape[:2]
        points = item['landmarks']
        if not points:
            continue
        face_lms = np.array([[p['x'] * w, p['y'] * h] for p in points[:468]])
        min_x, max_x = int(np.floor(face_lms[:, 0].min())), int(np.ceil(face_lms[:, 0].max()))
        min_y, max_y = int(np.floor(face_lms[:, 1].min())), int(np.ceil(face_lms[:, 1].max()))
        pad = max(24, int((max_x - min_x) * 0.15))
        crop_x0, crop_y0 = max(0, min_x - pad), max(0, min_y - pad)
        crop_x1, crop_y1 = min(w, max_x + pad), min(h, max_y + pad)

        for a in [crop_x0, max(crop_x0, crop_x1 - 384)]:
            for b in [crop_y0, max(crop_y0, crop_y1 - 384)]:
                endx, endy = min(w, a + 384), min(h, b + 384)
                tile = np.full((384, 384, 3), 114, dtype=np.uint8)
                tile[:endy - b, :endx - a] = bgr[b:endy, a:endx]
                t_input = tile.transpose(2, 0, 1)[None].astype(np.float32)

                # PyTorch Inference
                with torch.no_grad():
                    pyt_out = pyt_net(torch.from_numpy(t_input)).numpy()[0]  # [12240, 6]

                # ONNX Inference
                ort_out = ort_session.run(None, {'native_bgr_tile': t_input})[0][0]  # [12240, 6]

                pixel_diff = np.max(np.abs(pyt_out[:, :4] - ort_out[:, :4]))
                score_diff = np.max(np.abs(pyt_out[:, 4:] - ort_out[:, 4:]))

                max_pixel_diff_all = max(max_pixel_diff_all, float(pixel_diff))
                max_score_diff_all = max(max_score_diff_all, float(score_diff))
                tiles_tested += 1

    print(f"Tested {tiles_tested} real face tiles.")
    print(f"Max Pixel Diff (bbox coordinates): {max_pixel_diff_all:.6e} px (Normalized: {max_pixel_diff_all/384.0:.6e})")
    print(f"Max Score Diff (objectness + class): {max_score_diff_all:.6e}")

    assert max_score_diff_all < 1e-4, f"Score mismatch: {max_score_diff_all}"
    assert max_pixel_diff_all < 0.5, f"Pixel coordinate mismatch: {max_pixel_diff_all}"
    print("[VERIFIED] Exact numerical parity confirmed on real face skin tiles within float32 tolerance.")


if __name__ == '__main__':
    test_real_tile_parity()
