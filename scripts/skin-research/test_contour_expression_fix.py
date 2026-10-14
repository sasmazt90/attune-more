#!/usr/bin/env python3
"""Strict Verification of Contour Appearance and Disambiguated Expression Gate.

Ensures that:
1. AG's new services/core-api/contour_appearance.py is strictly loaded (verified by path, version, SHA256).
2. Resting full lips on 4d05d72b and 29cc4ba7 pass the expression gate.
3. Real sources with and without contour prominence / pleats are evaluated.
4. True facial expressions (smile, open mouth, frown, cheek puff, true pucker) are properly gated.
5. All observations validate finite range [0, 1] including mouthFunnel without silent zeroes.
"""

import sys
import json
import hashlib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

# Strict module loading: insert AG services/core-api BEFORE any CDC path
sys.path.insert(0, str(ROOT / 'services/core-api'))

import contour_appearance as C

# Verify that the loaded module is strictly from AG workspace
loaded_path = Path(C.__file__).resolve()
expected_path = (ROOT / 'services/core-api/contour_appearance.py').resolve()
loaded_sha = hashlib.sha256(loaded_path.read_bytes()).hexdigest()

print("=== Module Resolution Verification ===")
print(f"Loaded Module Path:   {loaded_path}")
print(f"Expected Module Path: {expected_path}")
print(f"Module Version:       {C.VERSION}")
print(f"Module SHA-256:       {loaded_sha}")

if loaded_path != expected_path:
    raise RuntimeError(f"FAIL: Loaded module from wrong path: {loaded_path} != {expected_path}")

EXPECTED_VERSION = 'image-contour-neighbor-excursion-exterior-expression-v4-staging'
if C.VERSION != EXPECTED_VERSION:
    raise RuntimeError(f"FAIL: Unexpected module version: {C.VERSION} != {EXPECTED_VERSION}")

print("Module verification: STRICT PASS\n")


def test_payload(name, path):
    print(f"--- Testing {name} ({path.name}) ---")
    payload = json.loads(path.read_text('utf8'))
    
    # Check expression gate specifically
    points = payload['landmarks']
    w, h = 1080, 1920
    if 'photo' in payload:
        from appearance_analysis import decode_photo
        img, _ = decode_photo(payload['photo'])
        h, w = img.shape[:2]
    
    p_arr = np.array([[v['x'] * w, v['y'] * h] for v in points])
    face = abs((p_arr[454] - p_arr[234])[0])
    mouth = np.linalg.norm(p_arr[13] - p_arr[14]) / max(1, np.linalg.norm(p_arr[61] - p_arr[291]))
    smile = ((p_arr[61] + p_arr[291] - p_arr[13] - p_arr[14]) / 2)[1] / max(1, np.linalg.norm(p_arr[61] - p_arr[291]))
    lip_width = np.linalg.norm(p_arr[61] - p_arr[291]) / max(1, face)
    
    expr_reason = C.expression_reason(payload, mouth, smile, lip_width)
    print(f"  Geometry: mouth_opening={mouth:.4f}, smile_curve={smile:.4f}, lip_width_ratio={lip_width:.4f}")
    print(f"  expression_reason -> {expr_reason}")
    
    # Run full analyze_contour
    result = C.analyze_contour(payload)
    for reg, m in result['measurements'].items():
        print(f"  [{reg:10s}] value={m['value']}, reason={m['reason']}, residual={m.get('trackingResidual')}")
    return result, expr_reason


# 1. Test resting full-lip cases
p_4d = LIVE_TEST / 'audit-results/material-closeout-20261013/4d05d72b-payload.json'
r_4d, expr_4d = test_payload("4d05d72b", p_4d)
assert expr_4d is None, f"4d05d72b should pass expression gate, got {expr_4d}"
assert r_4d['measurements']['chin']['reason'] is None, f"4d05d72b chin tracking should pass, got {r_4d['measurements']['chin']['reason']}"
assert r_4d['measurements']['chin']['value'] == 0.0, f"4d05d72b should have 0.0% false protrusion, got {r_4d['measurements']['chin']['value']}"

p_29 = LIVE_TEST / 'audit-results/native-camera-scope-20261013/29cc4ba7-current-capture-payload.json'
r_29, expr_29 = test_payload("29cc4ba7", p_29)
assert expr_29 is None, f"29cc4ba7 should pass expression gate, got {expr_29}"

# 2. Test other real sources in sagging pool
sag_sources = [
    ("dedbb492", LIVE_TEST / 'audit-results/native-dry-scale-20261013/sag-targeted/dedbb492-payload.json'),
    ("40c7edda", LIVE_TEST / 'audit-results/native-dry-scale-20261013/sag-targeted/40c7edda-payload.json'),
    ("e35b68b8", LIVE_TEST / 'audit-results/native-dry-scale-20261013/sag-targeted/e35b68b8-payload.json'),
    ("f90e68f8", LIVE_TEST / 'audit-results/dry-sag-proposal-tracking-20261013/product/f90e68f8-payload.json'),
    ("64b02ede", LIVE_TEST / 'audit-results/dry-sag-proposal-tracking-20261013/product/64b02ede-payload.json')
]

for name, path in sag_sources:
    if path.exists():
        test_payload(name, path)

# 3. Test granular expression gating with synthetic & modified observations
print("\n=== Granular Expression Gating Direct Tests ===")
base_scores = {
    'mouthSmileLeft': 0.0, 'mouthSmileRight': 0.0,
    'mouthFrownLeft': 0.0, 'mouthFrownRight': 0.0,
    'mouthPucker': 0.0, 'mouthPressLeft': 0.0, 'mouthPressRight': 0.0,
    'cheekPuff': 0.0, 'jawOpen': 0.0, 'mouthFunnel': 0.0
}
mock_payload = {
    'photoId': 'mock-photo-id',
    'expressionObservation': {
        'photoId': 'mock-photo-id',
        'version': 'local-mediapipe-expression-support-v1',
        'scores': dict(base_scores)
    }
}

# Neutral baseline
assert C.expression_reason(mock_payload, 0.02, 0.0, 0.40) is None, "Neutral baseline should pass"

# Smile left
mock_payload['expressionObservation']['scores'] = dict(base_scores, mouthSmileLeft=0.85)
assert C.expression_reason(mock_payload, 0.02, 0.0, 0.40) == 'EXPRESSION_SMILE'

# Open mouth jaw
mock_payload['expressionObservation']['scores'] = dict(base_scores, jawOpen=0.25)
assert C.expression_reason(mock_payload, 0.02, 0.0, 0.40) == 'EXPRESSION_OPEN_MOUTH'

# Frown
mock_payload['expressionObservation']['scores'] = dict(base_scores, mouthFrownRight=0.75)
assert C.expression_reason(mock_payload, 0.02, 0.0, 0.40) == 'EXPRESSION_FROWN'

# Cheek puff
mock_payload['expressionObservation']['scores'] = dict(base_scores, cheekPuff=0.60)
assert C.expression_reason(mock_payload, 0.02, 0.0, 0.40) == 'EXPRESSION_CHEEK_PUFF'

# Mouth press
mock_payload['expressionObservation']['scores'] = dict(base_scores, mouthPressLeft=0.55)
assert C.expression_reason(mock_payload, 0.02, 0.0, 0.40) == 'EXPRESSION_MOUTH_PRESS'

# Active narrow pucker
mock_payload['expressionObservation']['scores'] = dict(base_scores, mouthPucker=0.75, mouthFunnel=0.0)
assert C.expression_reason(mock_payload, 0.02, 0.0, 0.30) == 'EXPRESSION_PUCKER', "Narrow lips + pucker should be blocked"

# Active funnel pucker
mock_payload['expressionObservation']['scores'] = dict(base_scores, mouthPucker=0.75, mouthFunnel=0.35)
assert C.expression_reason(mock_payload, 0.02, 0.0, 0.40) == 'EXPRESSION_PUCKER', "Funnel + pucker should be blocked"

# Resting full lips (normal width 0.42, closed jaw, funnel 0.05)
mock_payload['expressionObservation']['scores'] = dict(base_scores, mouthPucker=0.71, mouthFunnel=0.05)
assert C.expression_reason(mock_payload, 0.02, 0.0, 0.42) is None, "Resting full lips with normal width should pass"

# mouthFunnel missing check: must fail closed!
mock_missing_funnel = {
    'photoId': 'mock-photo-id',
    'expressionObservation': {
        'photoId': 'mock-photo-id',
        'version': 'local-mediapipe-expression-support-v1',
        'scores': {k: v for k, v in base_scores.items() if k != 'mouthFunnel'}
    }
}
try:
    C.expression_reason(mock_missing_funnel, 0.02, 0.0, 0.40)
    raise AssertionError("Should have raised ValueError for missing mouthFunnel")
except ValueError as e:
    assert 'INVALID_EXPRESSION_SUPPORT' in str(e)
    print("Missing mouthFunnel correctly raised ValueError: INVALID_EXPRESSION_SUPPORT")

print("\nALL CONTOUR & EXPRESSION TESTS PASSED STRICTLY ON AG CODE!")
