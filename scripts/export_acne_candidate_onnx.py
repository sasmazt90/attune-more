#!/usr/bin/env python3
"""Export candidate fine-tuned YOLOX acne detector to ONNX with parity checks."""

import time
import json
import hashlib
from pathlib import Path
import torch
import numpy as np
import onnxruntime as ort
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[1]
LIVE_TEST = ROOT.parent / 'attune-live-test'

import sys
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
from yolox_numeric import install_bounds

CANDIDATE_WEIGHTS = ROOT / 'audit-results/acne-candidate-training-20261013/candidate-selected.safetensors'
BASELINE_ONNX = LIVE_TEST / 'audit-results/skin-expanded-20261011/interim-diagnosis/selected-detector-export-1a014adad262/selected.onnx'
OUTPUT_ONNX = ROOT / 'audit-results/acne-candidate-training-20261013/candidate.onnx'
RECEIPT_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/export-receipt.json'


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("=== Exporting Acne Candidate Model to ONNX ===")
    assert CANDIDATE_WEIGHTS.exists(), f"Weights not found: {CANDIDATE_WEIGHTS}"

    net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net)

    weights = load_file(str(CANDIDATE_WEIGHTS))
    net.load_state_dict(weights)
    net.eval()

    # Dummy native tile input (1, 3, 384, 384) BGR float32
    dummy_input = torch.full((1, 3, 384, 384), 114.0, dtype=torch.float32)

    print(f"Exporting to: {OUTPUT_ONNX}...")
    torch.onnx.export(
        net,
        dummy_input,
        str(OUTPUT_ONNX),
        input_names=['native_bgr_tile'],
        output_names=['detections'],
        opset_version=17,
        do_constant_folding=True,
        dynamo=False
    )
    assert OUTPUT_ONNX.exists(), "Export failed"

    onnx_sha = compute_sha256(OUTPUT_ONNX)
    onnx_size = OUTPUT_ONNX.stat().st_size
    print(f"Exported ONNX SHA-256: {onnx_sha} ({onnx_size / 1024 / 1024:.2f} MB)")

    # Parity verification with ONNX Runtime
    print("Verifying numerical parity between PyTorch and ONNX Runtime...")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(OUTPUT_ONNX), sess_options=options, providers=['CPUExecutionProvider'])

    with torch.no_grad():
        torch_out = net(dummy_input).numpy()

    onnx_out = session.run(None, {'native_bgr_tile': dummy_input.numpy()})[0]

    max_abs_error = float(np.max(np.abs(torch_out - onnx_out)))
    mean_abs_error = float(np.mean(np.abs(torch_out - onnx_out)))
    print(f"Max Absolute Error:  {max_abs_error:.6f}")
    print(f"Mean Absolute Error: {mean_abs_error:.6f}")
    assert max_abs_error < 0.05, f"Parity check failed: max error {max_abs_error} >= 0.05"
    print("Numerical parity check PASSED (< 0.05).")

    # Latency benchmarking
    print("Benchmarking ONNX inference latencies...")
    cold_start = time.monotonic()
    _ = session.run(None, {'native_bgr_tile': dummy_input.numpy()})
    cold_seconds = time.monotonic() - cold_start

    warm_times = []
    for _ in range(20):
        t0 = time.monotonic()
        _ = session.run(None, {'native_bgr_tile': dummy_input.numpy()})
        warm_times.append(time.monotonic() - t0)

    warm_mean_ms = float(np.mean(warm_times) * 1000.0)
    print(f"Cold start time: {cold_seconds * 1000.0:.2f} ms")
    print(f"Warm step latency: {warm_mean_ms:.2f} ms")

    receipt = {
        'exportDate': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'candidateWeightsSha256': compute_sha256(CANDIDATE_WEIGHTS),
        'candidateOnnxSha256': onnx_sha,
        'candidateOnnxSizeBytes': onnx_size,
        'maxAbsParityError': round(max_abs_error, 6),
        'meanAbsParityError': round(mean_abs_error, 6),
        'parityCheckPassed': max_abs_error < 0.05,
        'coldStartLatencyMs': round(cold_seconds * 1000.0, 2),
        'warmStepLatencyMs': round(warm_mean_ms, 2),
        'inputShape': [1, 3, 384, 384],
        'outputShape': list(onnx_out.shape),
        'opsetVersion': 17
    }

    with open(RECEIPT_PATH, 'w', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2)

    print(f"Export receipt written to: {RECEIPT_PATH}")


if __name__ == '__main__':
    main()
