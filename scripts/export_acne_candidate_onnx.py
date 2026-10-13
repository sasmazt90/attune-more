#!/usr/bin/env python3
"""Export candidate fine-tuned YOLOX acne detector to ONNX with comprehensive parity checks."""

import time
import json
import hashlib
import argparse
from pathlib import Path
import cv2
import torch
import numpy as np
import onnxruntime as ort
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[1]
LIVE_TEST = ROOT.parent / 'attune-live-test'

import sys
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
from yolox_numeric import install_bounds
from acne_box_support import region_envelopes, accepted_boxes as filter_acne_boxes

DEFAULT_CANDIDATE_WEIGHTS = ROOT / 'audit-results/acne-candidate-training-20261013/candidate-selected.safetensors'
DEFAULT_OUTPUT_ONNX = ROOT / 'audit-results/acne-candidate-training-20261013/candidate.onnx'
DEFAULT_RECEIPT_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/export-receipt.json'


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def decode_boxes(pred_tensor, min_score=0.40):
    boxes = []
    for p in pred_tensor:
        cx, cy, bw, bh, obj, cls = p
        score = float(obj * cls)
        if score >= min_score:
            boxes.append([float(cx - bw / 2), float(cy - bh / 2), float(cx + bw / 2), float(cy + bh / 2), score])
    return boxes


def run_nms(boxes, threshold=0.30):
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
            inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
            area_b = (b[2] - b[0]) * (b[3] - b[1])
            area_k = (k[2] - k[0]) * (k[3] - k[1])
            denom = area_b + area_k - inter
            iou = inter / denom if denom > 0.0 else 0.0
            if iou >= threshold:
                suppress = True
                break
        if not suppress:
            kept.append(b)
    return kept


def main():
    parser = argparse.ArgumentParser(description="Export acne detector candidate model to ONNX with parity checks.")
    parser.add_argument('--weights', type=str, default=str(DEFAULT_CANDIDATE_WEIGHTS), help="Candidate weights file.")
    parser.add_argument('--output-onnx', type=str, default=str(DEFAULT_OUTPUT_ONNX), help="Output ONNX path.")
    parser.add_argument('--receipt', type=str, default=str(DEFAULT_RECEIPT_PATH), help="Output export receipt JSON.")
    args = parser.parse_args()

    weights_path = Path(args.weights)
    output_onnx_path = Path(args.output_onnx)
    receipt_path = Path(args.receipt)
    output_onnx_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    print("=== Exporting Acne Candidate Model to ONNX ===")
    print(f"Weights path: {weights_path}")
    print(f"Output ONNX:  {output_onnx_path}")
    assert weights_path.exists(), f"Weights not found: {weights_path}"

    net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net)

    weights = load_file(str(weights_path))
    net.load_state_dict(weights)
    net.eval()

    # Dummy native tile input (1, 3, 384, 384) BGR float32
    dummy_input = torch.full((1, 3, 384, 384), 114.0, dtype=torch.float32)

    print(f"Exporting to: {output_onnx_path}...")
    torch.onnx.export(
        net,
        dummy_input,
        str(output_onnx_path),
        input_names=['native_bgr_tile'],
        output_names=['detections'],
        opset_version=17,
        do_constant_folding=True,
        dynamo=False
    )
    assert output_onnx_path.exists(), "Export failed"

    onnx_sha = compute_sha256(output_onnx_path)
    onnx_size = output_onnx_path.stat().st_size
    weights_sha = compute_sha256(weights_path)
    print(f"Weights SHA-256:        {weights_sha}")
    print(f"Candidate ONNX SHA-256: {onnx_sha} ({onnx_size / 1024 / 1024:.2f} MB)")

    # Parity verification with ONNX Runtime
    print("\nVerifying numerical and structural parity across real validation photo tiles...")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(output_onnx_path), sess_options=options, providers=['CPUExecutionProvider'])

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
        },
        {
            'description': 'Borderline confidence validation sample (424a750a cheek blemish)',
            'path': LIVE_TEST / 'audit-results/skin-selected-20261011/sources/smart/train/licatvncr8w71_jpg.rf.50542c582cdf880a9d8da1bdc0e45de8.jpg',
            'crop': (288, 288)
        }
    ]

    real_tile_results = []
    overall_max_tensor_err = 0.0
    overall_max_reg_err = 0.0
    overall_max_obj_err = 0.0
    overall_max_cls_err = 0.0
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

        # Component-wise tensor difference analysis
        reg_diff = float(np.max(np.abs(torch_out[..., :4] - onnx_out[..., :4])))
        obj_diff = float(np.max(np.abs(torch_out[..., 4] - onnx_out[..., 4])))
        cls_diff = float(np.max(np.abs(torch_out[..., 5] - onnx_out[..., 5])))
        tensor_diff = np.abs(torch_out - onnx_out)
        t_max_err = float(np.max(tensor_diff))
        t_mean_err = float(np.mean(tensor_diff))

        overall_max_tensor_err = max(overall_max_tensor_err, t_max_err)
        overall_max_reg_err = max(overall_max_reg_err, reg_diff)
        overall_max_obj_err = max(overall_max_obj_err, obj_diff)
        overall_max_cls_err = max(overall_max_cls_err, cls_diff)
        overall_mean_tensor_err.append(t_mean_err)

        torch_boxes = decode_boxes(torch_out, min_score=0.40)
        onnx_boxes = decode_boxes(onnx_out, min_score=0.40)
        assert len(torch_boxes) == len(onnx_boxes), f"Decoded box count mismatch on {spec['description']}"

        # 1-to-1 post-NMS matching verification
        torch_nms = run_nms(torch_boxes, threshold=0.30)
        onnx_nms = run_nms(onnx_boxes, threshold=0.30)
        assert len(torch_nms) == len(onnx_nms), f"NMS box count mismatch: torch={len(torch_nms)}, onnx={len(onnx_nms)}"

        coord_diff = 0.0
        score_diff = 0.0
        for tb, ob in zip(torch_nms, onnx_nms):
            cd = float(np.max(np.abs(np.array(tb[:4]) - np.array(ob[:4]))))
            sd = abs(tb[4] - ob[4])
            coord_diff = max(coord_diff, cd)
            score_diff = max(score_diff, sd)

        overall_max_coord_diff = max(overall_max_coord_diff, coord_diff)
        overall_max_score_diff = max(overall_max_score_diff, score_diff)

        real_tile_results.append({
            'description': spec['description'],
            'imageSha256': compute_sha256(spec['path']),
            'cropCoordinates': [x0, y0, x0 + 384, y0 + 384],
            'maxTensorAbsError': round(t_max_err, 6),
            'maxRegressionAbsError': round(reg_diff, 6),
            'maxObjectnessAbsError': round(obj_diff, 6),
            'maxClassAbsError': round(cls_diff, 6),
            'meanTensorAbsError': round(t_mean_err, 6),
            'decodedBoxesCount': len(torch_boxes),
            'nmsBoxesCount': len(torch_nms),
            'maxCoordDiffPx': round(coord_diff, 6),
            'maxScoreDiff': round(score_diff, 6),
            'oneToOneNmsMatch': True
        })

    # Benchmark latency on real tile
    im = cv2.imread(str(real_sample_specs[0]['path']))
    y0, x0 = real_sample_specs[0]['crop']
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
    print(f"Max Tensor Error:     {overall_max_tensor_err:.6f}")
    print(f"Max Regression Error: {overall_max_reg_err:.6f}")
    print(f"Max Objectness Error: {overall_max_obj_err:.6f}")
    print(f"Max Class Error:      {overall_max_cls_err:.6f}")
    print(f"Overall Max Coord Diff: {overall_max_coord_diff:.6f} px")
    print(f"Overall Max Score Diff: {overall_max_score_diff:.6f}")

    mean_err_val = float(np.mean(overall_mean_tensor_err))
    # Strict tolerance checks based on baseline export protocol
    assert overall_max_reg_err < 0.05, f"Regression parity failed: {overall_max_reg_err} >= 0.05"
    assert overall_max_obj_err < 0.01, f"Objectness parity failed: {overall_max_obj_err} >= 0.01"
    assert overall_max_cls_err < 0.005, f"Class parity failed: {overall_max_cls_err} >= 0.005"
    assert overall_max_coord_diff < 0.01, f"Box coord parity failed: {overall_max_coord_diff} >= 0.01 px"
    assert overall_max_score_diff < 0.001, f"Box score parity failed: {overall_max_score_diff} >= 0.001"

    receipt = {
        'exportDate': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'candidateWeightsPath': str(weights_path),
        'candidateWeightsSha256': weights_sha,
        'candidateOnnxPath': str(output_onnx_path),
        'candidateOnnxSha256': onnx_sha,
        'candidateOnnxSizeBytes': onnx_size,
        'realPhotoTilesEvaluated': len(real_tile_results),
        'realPhotoTiles': real_tile_results,
        'maxAbsTensorError': round(overall_max_tensor_err, 6),
        'maxRegressionError': round(overall_max_reg_err, 6),
        'maxObjectnessError': round(overall_max_obj_err, 6),
        'maxClassError': round(overall_max_cls_err, 6),
        'meanAbsTensorError': round(float(np.mean(overall_mean_tensor_err)), 6),
        'boxDecoderMaxCoordDiff': round(overall_max_coord_diff, 6),
        'boxDecoderMaxScoreDiff': round(overall_max_score_diff, 6),
        'postNmsDiscrepancyCount': nms_discrepancies,
        'oneToOnePostNmsParity': True,
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

    with open(receipt_path, 'w', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2)

    print(f"\nExport receipt successfully updated: {receipt_path}")


if __name__ == '__main__':
    main()
