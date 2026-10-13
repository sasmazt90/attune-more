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
    print(f"Candidate ONNX SHA-256: {onnx_sha} ({onnx_size / 1024 / 1024:.2f} MB)")
    assert onnx_sha == '006927cd14d46a47fa763c7d1a0f1348b4e5d2dffdcdfd47bc136476e77af6b8', f"ONNX hash mismatch: {onnx_sha}"

    # Parity verification with ONNX Runtime
    print("Verifying numerical and structural parity across real validation photo tiles...")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(OUTPUT_ONNX), sess_options=options, providers=['CPUExecutionProvider'])

    import cv2
    real_sample_specs = [
        {
            'description': 'Positive photo with multiple facial blemishes (smart-train licatvncr8w71)',
            'path': LIVE_TEST / 'audit-results/skin-selected-20261011/sources/smart/train/licatvncr8w71_jpg.rf.50542c582cdf880a9d8da1bdc0e45de8.jpg',
            'crop': (350, 350)
        },
        {
            'description': 'Positive photo with isolated pustule lesion (smart-test uhknm3639n791)',
            'path': LIVE_TEST / 'audit-results/skin-selected-20261011/sources/smart/test/uhknm3639n791_jpg.rf.4f03ba2d71318e5a27cfe10a86390dad.jpg',
            'crop': (200, 200)
        },
        {
            'description': 'Negative control photo without acne lesions (v11-valid 2937757570_1)',
            'path': LIVE_TEST / 'audit-results/skin-selected-20261011/sources/v11/valid/2937757570_1_jpg.rf.957c1512b417908bf0ada1e46d14a4dc.jpg',
            'crop': (100, 100)
        }
    ]

    def decode_boxes(pred_tensor, min_score=0.40):
        boxes = []
        for p in pred_tensor:
            cx, cy, bw, bh, obj, cls = p
            score = float(obj * cls)
            if score >= min_score:
                boxes.append([float(cx - bw / 2), float(cy - bh / 2), float(cx + bw / 2), float(cy + bh / 2), score])
        return boxes

    def run_nms(boxes, threshold=0.45):
        if not boxes:
            return []
        ranked = sorted(boxes, key=lambda b: b[4], reverse=True)
        kept = []
        for b in ranked:
            suppress = False
            for k in kept:
                x0 = max(b[0], k[0])
                y0 = max(b[1], k[1])
                x1 = min(b[2], k[2])
                y1 = min(b[3], k[3])
                inter = max(0, x1 - x0) * max(0, y1 - y0)
                area_b = (b[2] - b[0]) * (b[3] - b[1])
                area_k = (k[2] - k[0]) * (k[3] - k[1])
                iou = inter / max(1e-8, area_b + area_k - inter)
                if iou >= threshold:
                    suppress = True
                    break
            if not suppress:
                kept.append(b)
        return kept

    real_tile_results = []
    overall_max_tensor_err = 0.0
    overall_mean_tensor_err = []
    overall_max_coord_diff = 0.0
    overall_max_score_diff = 0.0
    nms_discrepancies = 0

    for spec in real_sample_specs:
        im = cv2.imread(str(spec['path']))
        assert im is not None, f"Image not found: {spec['path']}"
        y0, x0 = spec['crop']
        tile = im[y0:y0 + 384, x0:x0 + 384]
        if tile.shape[:2] != (384, 384):
            canvas = np.full((384, 384, 3), 114, np.uint8)
            canvas[:tile.shape[0], :tile.shape[1]] = tile
            tile = canvas

        tensor = torch.from_numpy(tile.transpose(2, 0, 1)[None].astype(np.float32))
        with torch.no_grad():
            torch_out = net(tensor).numpy()[0]
        onnx_out = session.run(None, {'native_bgr_tile': tensor.numpy()})[0][0]

        tensor_diff = np.abs(torch_out - onnx_out)
        t_max_err = float(np.max(tensor_diff))
        t_mean_err = float(np.mean(tensor_diff))
        overall_max_tensor_err = max(overall_max_tensor_err, t_max_err)
        overall_mean_tensor_err.append(t_mean_err)

        torch_boxes = decode_boxes(torch_out, min_score=0.40)
        onnx_boxes = decode_boxes(onnx_out, min_score=0.40)
        assert len(torch_boxes) == len(onnx_boxes), f"Decoded box count mismatch on {spec['description']}"

        coord_diff = 0.0
        score_diff = 0.0
        for tb, ob in zip(torch_boxes, onnx_boxes):
            cd = float(np.max(np.abs(np.array(tb[:4]) - np.array(ob[:4]))))
            sd = abs(tb[4] - ob[4])
            coord_diff = max(coord_diff, cd)
            score_diff = max(score_diff, sd)

        overall_max_coord_diff = max(overall_max_coord_diff, coord_diff)
        overall_max_score_diff = max(overall_max_score_diff, score_diff)

        torch_nms = run_nms(torch_boxes, threshold=0.45)
        onnx_nms = run_nms(onnx_boxes, threshold=0.45)
        if len(torch_nms) != len(onnx_nms):
            nms_discrepancies += 1

        real_tile_results.append({
            'description': spec['description'],
            'imageSha256': compute_sha256(spec['path']),
            'cropCoordinates': [x0, y0, x0 + 384, y0 + 384],
            'maxTensorAbsError': round(t_max_err, 6),
            'meanTensorAbsError': round(t_mean_err, 6),
            'decodedBoxesCount': len(torch_boxes),
            'maxCoordDiffPx': round(coord_diff, 6),
            'maxScoreDiff': round(score_diff, 6),
            'nmsBoxesCount': len(torch_nms),
            'nmsAgreement': len(torch_nms) == len(onnx_nms)
        })

    # Benchmark latencies on real tile
    print("Benchmarking ONNX inference latencies on real validation photo tiles...")
    sample_tile_np = real_tile_results[0]
    sample_tensor_np = torch.from_numpy(im[y0:y0+384, x0:x0+384].transpose(2, 0, 1)[None].astype(np.float32)).numpy()

    cold_start = time.monotonic()
    _ = session.run(None, {'native_bgr_tile': sample_tensor_np})
    cold_seconds = time.monotonic() - cold_start

    warm_times = []
    for _ in range(20):
        t0 = time.monotonic()
        _ = session.run(None, {'native_bgr_tile': sample_tensor_np})
        warm_times.append(time.monotonic() - t0)

    warm_mean_ms = float(np.mean(warm_times) * 1000.0)
    print(f"Cold start time: {cold_seconds * 1000.0:.2f} ms")
    print(f"Warm step latency: {warm_mean_ms:.2f} ms")
    print(f"Overall Max Tensor Parity Error: {overall_max_tensor_err:.6f}")
    print(f"Overall Max Coord Diff:          {overall_max_coord_diff:.6f} px")
    print(f"Overall Max Score Diff:          {overall_max_score_diff:.6f}")
    print(f"NMS Discrepancy Count:           {nms_discrepancies}")

    mean_err_val = float(np.mean(overall_mean_tensor_err))
    assert overall_max_tensor_err < 0.10, f"Tensor parity failed: {overall_max_tensor_err} >= 0.10"
    assert mean_err_val < 0.001, f"Mean tensor parity failed: {mean_err_val} >= 0.001"
    assert overall_max_coord_diff < 0.01, f"Box coord parity failed: {overall_max_coord_diff} >= 0.01 px"
    assert overall_max_score_diff < 0.001, f"Box score parity failed: {overall_max_score_diff} >= 0.001"
    assert nms_discrepancies == 0, f"Post-NMS parity failed with {nms_discrepancies} discrepancies"

    receipt = {
        'exportDate': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'candidateWeightsSha256': compute_sha256(CANDIDATE_WEIGHTS),
        'candidateOnnxSha256': onnx_sha,
        'candidateOnnxSizeBytes': onnx_size,
        'realPhotoTilesEvaluated': len(real_tile_results),
        'realPhotoTiles': real_tile_results,
        'maxAbsTensorError': round(overall_max_tensor_err, 6),
        'meanAbsTensorError': round(float(np.mean(overall_mean_tensor_err)), 6),
        'boxDecoderMaxCoordDiff': round(overall_max_coord_diff, 6),
        'boxDecoderMaxScoreDiff': round(overall_max_score_diff, 6),
        'postNmsDiscrepancyCount': nms_discrepancies,
        'parityCheckPassed': True,
        'tensorParityVerified': True,
        'boxDecoderParityVerified': True,
        'postNmsParityVerified': True,
        'coldStartLatencyMs': round(cold_seconds * 1000.0, 2),
        'warmStepLatencyMs': round(warm_mean_ms, 2),
        'inputShape': [1, 3, 384, 384],
        'outputShape': list(onnx_out.shape),
        'opsetVersion': 17
    }

    with open(RECEIPT_PATH, 'w', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2)

    print(f"Export receipt successfully updated: {RECEIPT_PATH}")


if __name__ == '__main__':
    main()
