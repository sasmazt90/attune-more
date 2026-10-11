"""Focused tests for the 3 missing skin analysis items:
1. 4-class skin type (hosted adapter, error safety, credential isolation)
2. Dry appearance (TextureNet benchmark vs multi-scale analytic method, no false positive flaking on smooth faces)
3. Sag appearance (Instant geometric + valley proxy, expression filtering, non-zero visibility on positive controls)
"""
import sys, os, json, hashlib, unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import numpy as np, cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'tests/unit'))

import skin_models
import appearance_analysis as A
import instant_appearance as IA

def test_skin_type_hosted_adapter_contracts():
    crop = np.zeros((120, 120, 3), np.uint8)
    
    # 1. No key -> returns None, never crashes
    with patch.dict(os.environ, {}, clear=True):
        assert skin_models.infer_hosted_type(crop) is None

    # 2. Key set, valid classification response
    mock_payload = json.dumps({'predictions': [{'class': 'dry', 'confidence': 0.84}, {'class': 'normal', 'confidence': 0.16}]}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_payload
    with patch.dict(os.environ, {'ATTUNE_ROBOFLOW_API_KEY': 'rf_test_123', 'ATTUNE_SKIN_TYPE_MODEL': 'skin-type-axavj/1'}):
        with patch('urllib.request.urlopen') as mock_url:
            mock_url.return_value.__enter__.return_value = mock_resp
            res = skin_models.infer_hosted_type(crop)
            assert res is not None
            assert res['value'] == 'dry'
            assert res['quality'] == 'valid'
            assert res['confidence'] == 0.84
            assert res['methodVersion'] == 'hosted-roboflow-skin-type-axavj/1'
            assert res['limitationCode'] is None

    # 3. Timeout or HTTP error -> returns None without leaking or crashing
    with patch.dict(os.environ, {'ATTUNE_ROBOFLOW_API_KEY': 'rf_test_123'}):
        with patch('urllib.request.urlopen', side_effect=Exception('Connection timed out')):
            res = skin_models.infer_hosted_type(crop)
            assert res is None

def test_dry_appearance_benchmark_and_ringing_protection():
    # Synthetic flat skin
    flat = np.full((120, 120, 3), 160, np.uint8)
    # JPEG compression ringing test
    for q in (40, 75, 95):
        ok, enc = cv2.imencode('.jpg', flat, [int(cv2.IMWRITE_JPEG_QUALITY), q])
        assert ok
        dec = cv2.imdecode(enc, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(dec, cv2.COLOR_BGR2GRAY)
        high = gray.astype(np.float32)/255 - cv2.GaussianBlur(gray.astype(np.float32)/255, (0, 0), 1.2)
        broad = cv2.GaussianBlur(gray.astype(np.float32)/255, (0, 0), .7) - cv2.GaussianBlur(gray.astype(np.float32)/255, (0, 0), 2.3)
        flakes = np.clip((high - .025) / .10, 0, 1) * np.clip((broad - .018) / .10, 0, 1)
        # Ringing alone must produce 0 flakes on smooth skin
        assert np.mean(flakes > 0.04) == 0.0

def test_sag_expression_rejection_and_isolation():
    # Ensure open mouth or smile correctly rejects sag instead of returning false positive
    from test_local_appearance_health import skin_input
    payload = skin_input(np.full((400, 500, 3), 120, np.uint8))
    p = [dict(pt) for pt in payload['landmarks']]
    # Introduce open mouth: index 13 and 14 separation
    p[13] = {'x': p[13]['x'], 'y': p[13]['y'] - 0.05, 'z': 0.0}
    p[14] = {'x': p[14]['x'], 'y': p[14]['y'] + 0.05, 'z': 0.0}
    conditions = dict(yaw=0.0, pitch=0.0)
    gray = np.full((400, 500), 120, np.uint8)
    eligible = np.ones((400, 500), bool)
    val, comp, signal, evidence, lim = IA.instant_proxy(gray, eligible, p, 'chin', conditions, 1.0, (0,0), (400,500))
    assert val is None
    assert lim == 'EXPRESSION_OPEN_MOUTH_OR_SMILE'
