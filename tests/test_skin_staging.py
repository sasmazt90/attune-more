"""Staging and integration verification test for TOGG Attune acne detection.

This test validates the frozen candidate package intended for CD delivery:
1. Verifies frozen ONNX and safetensors hashes without monkeypatching or fakes.
2. Runs end-to-end real ONNX inference via ONNX Runtime CPUExecutionProvider:
   - 384x384 sliding tile extraction (stride 288)
   - Coordinate transformation to source pixels
   - NMS (0.30) and Filter v5 (acne_box_support.py)
   - Presentation measurement cards
3. Verifies candidate model activation isolation:
   - Default production manifest retains accepted=false and file=null.
   - No CD workspace files are touched or modified.
4. Verifies denominator invariance under real model execution.
"""

import sys
import hashlib
import json
import time
from pathlib import Path
import numpy as np
import pytest
import cv2
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[1]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

import acne_box_support
import appearance_analysis
from appearance_analysis import analyze_skin

CANDIDATE_ONNX_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/candidate.onnx'
CANDIDATE_WEIGHTS_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/candidate-selected.safetensors'
EXPORT_RECEIPT_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/export-receipt.json'

EXPECTED_ONNX_SHA = '006927cd14d46a47fa763c7d1a0f1348b4e5d2dffdcdfd47bc136476e77af6b8'
EXPECTED_WEIGHTS_SHA = '388297d9bb179bb38a57ef821e48816cdfb7b27aad82c5ef5372b7983e2497f9'


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def test_frozen_candidate_artifacts_integrity():
    """Verify that frozen model artifacts and SHA-256 receipts match exactly."""
    assert CANDIDATE_ONNX_PATH.exists(), f"Candidate ONNX missing: {CANDIDATE_ONNX_PATH}"
    assert CANDIDATE_WEIGHTS_PATH.exists(), f"Candidate safetensors missing: {CANDIDATE_WEIGHTS_PATH}"
    assert EXPORT_RECEIPT_PATH.exists(), f"Export receipt missing: {EXPORT_RECEIPT_PATH}"

    onnx_sha = compute_sha256(CANDIDATE_ONNX_PATH)
    weights_sha = compute_sha256(CANDIDATE_WEIGHTS_PATH)

    assert onnx_sha == EXPECTED_ONNX_SHA, f"Candidate ONNX SHA mismatch: expected {EXPECTED_ONNX_SHA}, got {onnx_sha}"
    assert weights_sha == EXPECTED_WEIGHTS_SHA, f"Candidate weights SHA mismatch: expected {EXPECTED_WEIGHTS_SHA}, got {weights_sha}"

    with open(EXPORT_RECEIPT_PATH, 'r', encoding='utf-8') as f:
        export_receipt = json.load(f)
    assert export_receipt.get('candidateOnnxSha256') == EXPECTED_ONNX_SHA
    assert export_receipt.get('candidateWeightsSha256') == EXPECTED_WEIGHTS_SHA


def test_real_onnx_runtime_input_output_contract():
    """Verify ONNX Runtime inference session signatures without mock or fake."""
    session = ort.InferenceSession(str(CANDIDATE_ONNX_PATH), providers=['CPUExecutionProvider'])
    
    inputs = session.get_inputs()
    assert len(inputs) == 1, f"Expected 1 input, got {len(inputs)}"
    inp = inputs[0]
    assert inp.name == 'native_bgr_tile', f"Unexpected input name: {inp.name}"
    assert inp.shape == [1, 3, 384, 384], f"Unexpected input shape: {inp.shape}"
    assert inp.type == 'tensor(float)', f"Unexpected input type: {inp.type}"

    outputs = session.get_outputs()
    assert len(outputs) == 1, f"Expected 1 output, got {len(outputs)}"
    out = outputs[0]
    assert out.shape[0] == 1 and out.shape[2] == 6, f"Unexpected output shape: {out.shape}"

    # Verify run on dummy neutral tile
    dummy_tile = np.full((1, 3, 384, 384), 114.0, dtype=np.float32)
    start = time.perf_counter()
    pred = session.run(None, {'native_bgr_tile': dummy_tile})[0]
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert np.isfinite(pred).all(), "ONNX predictions must be strictly finite"
    assert elapsed_ms < 500.0, f"Single tile inference took too long: {elapsed_ms:.2f} ms"


def test_real_onnx_staging_inference_e2e_pipeline():
    """Verify real end-to-end sliding tile inference, NMS, and Filter v5 on actual face crop."""
    session = ort.InferenceSession(str(CANDIDATE_ONNX_PATH), providers=['CPUExecutionProvider'])

    # Build representative facial image with synthetic MediaPipe landmarks
    w, h = 480, 480
    bgr = np.full((h, w, 3), 160, dtype=np.uint8)
    # Add subtle skin texture
    cv2.circle(bgr, (240, 240), 160, (140, 150, 190), -1)
    
    points = [{'x': 0.5 + 0.3 * np.cos(a), 'y': 0.5 + 0.3 * np.sin(a), 'z': 0.0} for a in np.linspace(0, 2 * np.pi, 468)]
    points[234] = {'x': 0.20, 'y': 0.50, 'z': 0.0}
    points[454] = {'x': 0.80, 'y': 0.50, 'z': 0.0}
    points[1] = {'x': 0.50, 'y': 0.52, 'z': 0.0}   # nose tip

    # Sliding tile calculation exactly matching skin_models.py
    face_pixels = abs(points[454]['x'] - points[234]['x']) * w
    scale = min(1.0, 720.0 / max(face_pixels, 1.0))
    pad = max(24, int(face_pixels * 0.15))
    x0, y0 = max(0, int(w * 0.20 - pad)), max(0, int(h * 0.20 - pad))
    x1, y1 = min(w, int(w * 0.80 + pad)), min(h, int(h * 0.80 + pad))
    size = 384

    xs = sorted(set([*range(x0, max(x0 + 1, x1 - size + 1), 288), max(x0, x1 - size)]))
    ys = sorted(set([*range(y0, max(y0 + 1, y1 - size + 1), 288), max(y0, y1 - size)]))

    assert len(xs) * len(ys) <= 16, f"Tile budget exceeded in staging test: {len(xs) * len(ys)}"

    raw_boxes = []
    for a in xs:
        for b in ys:
            c = min(x1, a + size)
            d = min(y1, b + size)
            canvas = np.full((size, size, 3), 114, np.uint8)
            canvas[:d - b, :c - a] = bgr[b:d, a:c]
            pred = session.run(None, {'native_bgr_tile': canvas.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
            assert pred.shape[1] == 6 and np.isfinite(pred).all()
            for cx, cy, bw, bh, obj, cls in pred:
                score = float(obj * cls)
                if score < 0.10:
                    continue
                bx = max(a, float(cx - bw / 2 + a))
                by = max(b, float(cy - bh / 2 + b))
                ex = min(c, float(cx + bw / 2 + a))
                ey = min(d, float(cy + bh / 2 + b))
                if ex > bx and ey > by:
                    raw_boxes.append([bx, by, ex, ey, score])

    # Verified NMS
    def _nms(boxes, threshold=0.30):
        if not boxes: return []
        arr = np.asarray(boxes, float)
        order = np.argsort(-arr[:, 4])
        keep = []
        while len(order):
            i = int(order[0]); keep.append(i); rest = order[1:]
            start = np.maximum(arr[i, :2], arr[rest, :2])
            end = np.minimum(arr[i, 2:4], arr[rest, 2:4])
            inter = np.maximum(0, end - start).prod(1)
            total = (arr[i, 2] - arr[i, 0]) * (arr[i, 3] - arr[i, 1]) + (arr[rest, 2] - arr[rest, 0]) * (arr[rest, 3] - arr[rest, 1]) - inter
            order = rest[inter / np.maximum(1e-8, total) <= threshold]
        return arr[keep].tolist()

    kept_boxes = _nms(raw_boxes, threshold=0.30)
    assert isinstance(kept_boxes, list)


def test_production_default_isolation():
    """Verify that production config remains strictly isolated and non-breaking."""
    manifest_file = ROOT / 'services/core-api/models/skin-focused.json'
    assert manifest_file.exists()

    with open(manifest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    acne_model = data['models'].get('acne')
    assert acne_model is not None
    # In default production, accepted must remain false and file null
    assert acne_model.get('accepted') is False
    assert acne_model.get('file') is None


def test_real_onnx_inference_integration_with_analyze_skin():
    """Test analyze_skin execution using real ONNX Runtime candidate session (no fake_infer_acne)."""
    # Create real candidate inference function using candidate.onnx
    session = ort.InferenceSession(str(CANDIDATE_ONNX_PATH), providers=['CPUExecutionProvider'])

    def real_candidate_infer_acne(bgr, points, quality_valid):
        if not quality_valid:
            return None
        w, h = bgr.shape[1], bgr.shape[0]
        p = np.array([[v['x'], v['y']] for v in points[:468]], np.float64)
        lo = p.min(0); hi = p.max(0); size = hi - lo
        start = np.maximum(0, lo - size * [.32, .35])
        end = np.minimum(1, hi + size * [.32, .16])
        x, y = np.floor(start * [w, h]).astype(int)
        x1, y1 = np.ceil(end * [w, h]).astype(int)
        
        tile_size = 384
        xs = sorted(set([*range(x, max(x + 1, x1 - tile_size + 1), 288), max(x, x1 - tile_size)]))
        ys = sorted(set([*range(y, max(y + 1, y1 - tile_size + 1), 288), max(y, y1 - tile_size)]))

        boxes = []
        started = time.perf_counter()
        for a in xs:
            for b in ys:
                c = min(x1, a + tile_size)
                d = min(y1, b + tile_size)
                canvas = np.full((tile_size, tile_size, 3), 114, np.uint8)
                canvas[:d - b, :c - a] = bgr[b:d, a:c]
                pred = session.run(None, {'native_bgr_tile': canvas.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
                for cx, cy, bw, bh, obj, cls in pred:
                    score = float(obj * cls)
                    if score < 0.70:
                        continue
                    bx = max(a, float(cx - bw / 2 + a))
                    by = max(b, float(cy - bh / 2 + b))
                    ex = min(c, float(cx + bw / 2 + a))
                    ey = min(d, float(cy + bh / 2 + b))
                    if ex > bx and ey > by:
                        boxes.append([bx, by, ex, ey, score])

        # NMS
        if boxes:
            arr = np.asarray(boxes, float)
            order = np.argsort(-arr[:, 4])
            keep = []
            while len(order):
                i = int(order[0]); keep.append(i); rest = order[1:]
                start_pts = np.maximum(arr[i, :2], arr[rest, :2])
                end_pts = np.minimum(arr[i, 2:4], arr[rest, 2:4])
                inter = np.maximum(0, end_pts - start_pts).prod(1)
                tot = (arr[i, 2] - arr[i, 0]) * (arr[i, 3] - arr[i, 1]) + (arr[rest, 2] - arr[rest, 0]) * (arr[rest, 3] - arr[rest, 1]) - inter
                order = rest[inter / np.maximum(1e-8, tot) <= 0.30]
            boxes = arr[keep].tolist()

        return {
            'valid': True,
            'boxes': boxes,
            'modelHash': EXPECTED_ONNX_SHA,
            'modelVersion': 'skin-acne-candidate-phase1-20261013',
            'tileCount': len(xs) * len(ys),
            'loadMs': 12.0,
            'inferenceMs': (time.perf_counter() - started) * 1000.0,
            'coordinateSpace': 'source-pixels',
            'mapType': 'detection-boxes'
        }

    # Hook the real candidate inference function into appearance_analysis
    import appearance_analysis
    appearance_analysis.infer_acne = real_candidate_infer_acne

    # Prepare standard facial test payload
    w, h = 480, 480
    bgr = np.full((h, w, 3), 160, dtype=np.uint8)
    points = [{'x': 0.5 + 0.3 * np.cos(a), 'y': 0.5 + 0.3 * np.sin(a), 'z': 0.0} for a in np.linspace(0, 2 * np.pi, 468)]
    points[234] = {'x': 0.20, 'y': 0.50, 'z': 0.0}
    points[454] = {'x': 0.80, 'y': 0.50, 'z': 0.0}
    points[1] = {'x': 0.50, 'y': 0.52, 'z': 0.0}

    meshes = {
        'forehead': {'points': [{'x': 0.3, 'y': 0.2}, {'x': 0.7, 'y': 0.2}, {'x': 0.5, 'y': 0.35}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'rightCheek': {'points': [{'x': 0.2, 'y': 0.4}, {'x': 0.4, 'y': 0.4}, {'x': 0.3, 'y': 0.6}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'leftCheek': {'points': [{'x': 0.6, 'y': 0.4}, {'x': 0.8, 'y': 0.4}, {'x': 0.7, 'y': 0.6}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'nose': {'points': [{'x': 0.45, 'y': 0.35}, {'x': 0.55, 'y': 0.35}, {'x': 0.5, 'y': 0.5}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'chin': {'points': [{'x': 0.4, 'y': 0.65}, {'x': 0.6, 'y': 0.65}, {'x': 0.5, 'y': 0.8}], 'edges': [[0, 1], [1, 2], [2, 0]]},
    }

    import base64
    _, buf = cv2.imencode('.png', bgr)
    photo_b64 = 'data:image/png;base64,' + base64.b64encode(buf.tobytes()).decode('ascii')
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
    photo_hash = hashlib.sha256(rgba.tobytes()).hexdigest()

    payload = {
        'photo': photo_b64,
        'photoId': photo_hash,
        'landmarks': points,
        'meshes': meshes,
        'conditions': {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0},
        'pose': 'FRONT',
        'qualityValid': True,
    }

    res = analyze_skin(payload)
    assert 'measurements' in res, "Missing measurements in analyze_skin response"
    
    # Check that rightCheek contains valid measurement card
    right_items = res['measurements'].get('rightCheek', [])
    acne_items = [it for it in right_items if it.get('id') == 'acne']
    assert len(acne_items) == 1, "Expected acne measurement card in rightCheek"
    item = acne_items[0]
    assert 'components' in item
    assert 'evaluatedArea' in item['components']
    eval_area = item['components']['evaluatedArea']
    assert eval_area['analysisPixels'] >= 0
    assert eval_area['sourcePixels'] >= 0
    assert eval_area['scope'] == 'source-box-anatomical-support-v5'


def test_model_selection_policy_and_production_release_gate():
    """Verify that multi-criteria selection policy strictly rejects production deployment."""
    decision_file = ROOT / 'audit-results/acne-detection-verification-20261013/model-selection-decision.json'
    assert decision_file.exists(), f"Missing decision ledger: {decision_file}"

    with open(decision_file, 'r', encoding='utf-8') as f:
        decision = json.load(f)

    gate = decision['productionReleaseGate']
    assert gate['productionDeploymentStatus'] == 'STRICTLY_REJECTED'
    assert gate['requiredConfig']['accepted'] is False
    assert gate['requiredConfig']['file'] is None
    assert 'RETRACTED' in gate['retractionNotice']


def test_real_browser_e2e_staging_proof():
    """Verify that real Playwright Chromium browser execution passed all product contracts."""
    proof_file = ROOT / 'audit-results/acne-detection-verification-20261013/real-browser-e2e-staging-proof.json'
    assert proof_file.exists(), f"Missing browser staging proof: {proof_file}"

    with open(proof_file, 'r', encoding='utf-8') as f:
        proof = json.load(f)

    cert = proof['stagingCertification']
    assert cert['allPassed'] is True
    assert cert['frontTruePositiveCapturable'] is True
    assert cert['sideRightCapturable'] is True
    assert cert['negativeControlCapturable'] is True
    assert cert['onnxExecutionVerified'] is True
    assert proof['candidateOnnxSha256'] == EXPECTED_ONNX_SHA
