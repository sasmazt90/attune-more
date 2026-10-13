import sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

import appearance_analysis
from appearance_analysis import analyze_skin, NORMALIZATION


def test_acne_denominator_invariance_across_candidate_counts(monkeypatch):
    """Verifies that the measured anatomical denominator (sourcePixels, analysisPixels,
    anatomicalSourcePixels) is strictly invariant whether there are 0 candidates,
    1 candidate, or multiple candidates.
    """
    # Create synthetic test payload
    w, h = 400, 400
    points = [{'x': 0.5 + 0.3 * np.cos(a), 'y': 0.5 + 0.3 * np.sin(a), 'z': 0.0} for a in np.linspace(0, 2 * np.pi, 468)]
    # Landmark 234 and 454 for face pixels
    points[234] = {'x': 0.2, 'y': 0.5, 'z': 0.0}
    points[454] = {'x': 0.8, 'y': 0.5, 'z': 0.0}

    # Synthetic presentation meshes
    meshes = {
        'forehead': {'points': [{'x': 0.3, 'y': 0.2}, {'x': 0.7, 'y': 0.2}, {'x': 0.5, 'y': 0.35}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'rightCheek': {'points': [{'x': 0.2, 'y': 0.4}, {'x': 0.4, 'y': 0.4}, {'x': 0.3, 'y': 0.6}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'leftCheek': {'points': [{'x': 0.6, 'y': 0.4}, {'x': 0.8, 'y': 0.4}, {'x': 0.7, 'y': 0.6}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'nose': {'points': [{'x': 0.45, 'y': 0.35}, {'x': 0.55, 'y': 0.35}, {'x': 0.5, 'y': 0.5}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'chin': {'points': [{'x': 0.4, 'y': 0.65}, {'x': 0.6, 'y': 0.65}, {'x': 0.5, 'y': 0.8}], 'edges': [[0, 1], [1, 2], [2, 0]]},
    }

    import cv2
    import base64
    img = np.full((h, w, 3), 160, dtype=np.uint8)
    _, buf = cv2.imencode('.png', img)
    photo_b64 = 'data:image/png;base64,' + base64.b64encode(buf.tobytes()).decode('ascii')
    rgba = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
    import hashlib
    photo_hash = hashlib.sha256(rgba.tobytes()).hexdigest()

    base_payload = {
        'photo': photo_b64,
        'photoId': photo_hash,
        'landmarks': points,
        'meshes': meshes,
        'conditions': {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0},
        'pose': 'FRONT',
        'qualityValid': True,
    }

    denominators = {}
    for candidate_mode in ['zero', 'one', 'multiple']:
        if candidate_mode == 'zero':
            fake_boxes = []
        elif candidate_mode == 'one':
            fake_boxes = [[100.0, 180.0, 130.0, 210.0, 0.90]]
        else:
            fake_boxes = [
                [100.0, 180.0, 130.0, 210.0, 0.90],
                [120.0, 200.0, 145.0, 225.0, 0.85],
                # One candidate slightly outside the mesh to test fallback
                [70.0, 150.0, 100.0, 180.0, 0.88],
            ]

        def fake_infer_acne(bgr, points, quality_valid):
            return {
                'valid': True,
                'boxes': fake_boxes,
                'modelVersion': 'test-v1',
                'modelHash': 'fake-hash',
                'tileCount': 4,
                'loadMs': 10,
                'inferenceMs': 20
            }

        monkeypatch.setattr(appearance_analysis, 'infer_acne', fake_infer_acne)
        res = analyze_skin(base_payload)
        
        # Check rightCheek acne criterion
        acne_items = [it for it in res['measurements'].get('rightCheek', []) if it['id'] == 'acne']
        assert len(acne_items) == 1, f"Missing acne item in mode {candidate_mode}"
        item = acne_items[0]
        eval_area = item['components']['evaluatedArea']
        denominators[candidate_mode] = {
            'sourcePixels': eval_area['sourcePixels'],
            'analysisPixels': eval_area['analysisPixels'],
            'anatomicalSourcePixels': eval_area['anatomicalSourcePixels'],
            'normalizationVersion': eval_area.get('normalizationVersion'),
        }

    # Verify that the denominators are EXACTLY identical across 0, 1, and multiple candidates
    zero_d = denominators['zero']
    one_d = denominators['one']
    multi_d = denominators['multiple']

    assert zero_d['analysisPixels'] == one_d['analysisPixels'] == multi_d['analysisPixels'], \
        f"Denominator analysisPixels mismatch: zero={zero_d['analysisPixels']}, one={one_d['analysisPixels']}, multi={multi_d['analysisPixels']}"
    assert zero_d['sourcePixels'] == one_d['sourcePixels'] == multi_d['sourcePixels'], \
        f"Denominator sourcePixels mismatch: zero={zero_d['sourcePixels']}, one={one_d['sourcePixels']}, multi={multi_d['sourcePixels']}"
    assert zero_d['anatomicalSourcePixels'] == one_d['anatomicalSourcePixels'] == multi_d['anatomicalSourcePixels'], \
        f"Denominator anatomicalSourcePixels mismatch: zero={zero_d['anatomicalSourcePixels']}, one={one_d['anatomicalSourcePixels']}, multi={multi_d['anatomicalSourcePixels']}"
    assert zero_d['normalizationVersion'] == 'unique-detection-box-anatomical-area-v3'


def test_regional_acne_boxes_to_card_and_map_layer(monkeypatch):
    """Verifies that regional accepted candidate boxes map correctly to:
    1. Regional card metrics (candidateCount, bounds)
    2. Local map layer (res['maps']['<region>:acne']) with valid coverage.
    """
    w, h = 400, 400
    points = [{'x': 0.5, 'y': 0.5, 'z': 0.0} for _ in range(468)]
    oval = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
    for i, idx in enumerate(oval):
        theta = 2 * np.pi * i / len(oval)
        points[idx] = {'x': 0.5 + 0.35 * np.cos(theta), 'y': 0.5 + 0.35 * np.sin(theta), 'z': 0.0}
    points[1] = {'x': 0.5, 'y': 0.5, 'z': 0.0}
    points[234] = {'x': 0.2, 'y': 0.5, 'z': 0.0}
    points[454] = {'x': 0.8, 'y': 0.5, 'z': 0.0}

    meshes = {
        'forehead': {'points': [{'x': 120.0, 'y': 80.0}, {'x': 280.0, 'y': 80.0}, {'x': 200.0, 'y': 140.0}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'rightCheek': {'points': [{'x': 80.0, 'y': 160.0}, {'x': 160.0, 'y': 160.0}, {'x': 120.0, 'y': 240.0}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'leftCheek': {'points': [{'x': 240.0, 'y': 160.0}, {'x': 320.0, 'y': 160.0}, {'x': 280.0, 'y': 240.0}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'nose': {'points': [{'x': 180.0, 'y': 140.0}, {'x': 220.0, 'y': 140.0}, {'x': 200.0, 'y': 200.0}], 'edges': [[0, 1], [1, 2], [2, 0]]},
        'chin': {'points': [{'x': 160.0, 'y': 260.0}, {'x': 240.0, 'y': 260.0}, {'x': 200.0, 'y': 320.0}], 'edges': [[0, 1], [1, 2], [2, 0]]},
    }

    import cv2
    import base64
    import hashlib
    img = np.full((h, w, 3), 160, dtype=np.uint8)
    _, buf = cv2.imencode('.png', img)
    photo_b64 = 'data:image/png;base64,' + base64.b64encode(buf.tobytes()).decode('ascii')
    rgba = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
    photo_hash = hashlib.sha256(rgba.tobytes()).hexdigest()

    base_payload = {
        'photo': photo_b64,
        'photoId': photo_hash,
        'landmarks': points,
        'meshes': meshes,
        'conditions': {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0},
        'pose': 'FRONT',
        'qualityValid': True,
    }

    # Bounded candidate in rightCheek area
    test_boxes = [[100.0, 180.0, 130.0, 210.0, 0.92]]

    def fake_infer_acne(bgr, points, quality_valid):
        return {
            'valid': True,
            'boxes': test_boxes,
            'modelVersion': 'candidate-v2',
            'modelHash': 'test-hash-123',
            'tileCount': 4,
            'loadMs': 5,
            'inferenceMs': 15
        }

    monkeypatch.setattr(appearance_analysis, 'infer_acne', fake_infer_acne)
    res = analyze_skin(base_payload)

    # 1. Verify card metrics
    right_cheek_items = [it for it in res['measurements'].get('rightCheek', []) if it['id'] == 'acne']
    assert len(right_cheek_items) == 1
    acne_item = right_cheek_items[0]
    assert acne_item['components']['candidateCount'] == 1
    assert len(acne_item['components']['bounds']) == 1
    assert acne_item['components']['bounds'][0]['confidence'] == 0.92
    assert acne_item['localMap'] is not None
    assert acne_item['localMap']['key'] == 'rightCheek:acne'

    # 2. Verify map layer in res['maps']
    assert 'rightCheek:acne' in res['maps']
    map_layer = res['maps']['rightCheek:acne']
    assert map_layer['region'] == 'rightCheek'
    assert map_layer['criterion'] == 'acne'
    assert map_layer['dataUrl'].startswith('data:image/png;base64,')
    assert map_layer['validMaskUrl'].startswith('data:image/png;base64,')
    assert map_layer['sampleCount'] > 0

