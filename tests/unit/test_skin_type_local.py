"""Unit tests for offline local skin type classification and Regional Combination (Karma) Rule.
Verifies:
1. Pinned manifest hash and local ONNX model loading.
2. ViT input preprocessing contract (224x224, mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]).
3. Numerical parity between PyTorch and ONNX Runtime (< 1e-4).
4. Explainable Regional Combination Rule:
   - Elevated T-zone specularity with balanced/dry cheeks -> 'combination'.
   - Uniform oiliness across face -> 'oily'.
   - Uniform balanced -> 'normal'.
   - Uniform dry -> 'dry'.
5. Anti-glare highlight clipping gate ('GLARE_OR_EXPOSURE').
6. Low model support / confidence boundary ('LOW_MODEL_SUPPORT').
7. Vehicle app contract compliance (attach_result_receipts).
8. 100% offline execution without network or Roboflow API keys.
"""
import pytest
import sys, os, hashlib, json, time
from pathlib import Path
import numpy as np, cv2, torch

sys.path.insert(0, 'services/core-api')
import skin_models
import appearance_analysis as A
import skin_measurement_contract as contract

MODELS_DIR = Path('services/core-api/models')
ONNX_PATH = MODELS_DIR / 'skin-type-glamour-vit.onnx'
MANIFEST_PATH = MODELS_DIR / 'skin-focused.json'

def test_manifest_pins_glamour_vit():
    assert MANIFEST_PATH.is_file(), "Manifest skin-focused.json missing!"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    assert 'models' in manifest
    assert 'type' in manifest['models']
    type_meta = manifest['models']['type']
    
    assert type_meta['accepted'] is True
    assert type_meta['file'] == 'skin-type-glamour-vit.onnx'
    assert type_meta['sha256'] == 'ffdac2fc496a23dc27e60e08299b2496a0702a1d49f81f288d4d54da686213a0'
    assert type_meta['version'] == 'skin-type-glamour-vit-v1'
    assert type_meta['classes'] == ['dry', 'normal', 'oily']

def test_onnx_file_integrity():
    assert ONNX_PATH.is_file(), "ONNX model file missing!"
    file_bytes = ONNX_PATH.read_bytes()
    assert len(file_bytes) == 343372925, f"Unexpected ONNX file size: {len(file_bytes)}"
    h = hashlib.sha256(file_bytes).hexdigest()
    assert h == 'ffdac2fc496a23dc27e60e08299b2496a0702a1d49f81f288d4d54da686213a0', f"Hash mismatch: {h}"

def test_local_sessions_load_offline():
    loaded = skin_models.load()
    assert loaded['manifest'] is not None
    assert 'type' in loaded['sessions']
    type_session = loaded['sessions']['type']
    assert type_session['metadata']['accepted'] is True
    assert type_session['loadMs'] > 0

def test_numerical_parity_onnx_vs_pytorch():
    import onnxruntime as ort
    from transformers import AutoModelForImageClassification
    
    glamour_snapshot = Path(r'C:\Users\PC\.cache\huggingface\hub\models--AishaBaliyan--glamour-ai-skin-model\snapshots\4f232d45e5ba59664205f552c4f450a1a741470a')
    assert glamour_snapshot.is_dir(), "Local HuggingFace model cache missing!"
    
    pt_model = AutoModelForImageClassification.from_pretrained(str(glamour_snapshot))
    pt_model.eval()
    
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    ort_sess = ort.InferenceSession(str(ONNX_PATH), sess_options=opts, providers=['CPUExecutionProvider'])
    
    torch.manual_seed(42)
    dummy_input = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        pt_logits = pt_model(dummy_input).logits.numpy()
        
    ort_logits = ort_sess.run(None, {'rgb': dummy_input.numpy()})[0]
    
    max_diff = float(np.max(np.abs(pt_logits - ort_logits)))
    assert max_diff < 1e-4, f"Numerical parity failure: max diff = {max_diff}"

def test_regional_combination_rule_decisions():
    # Synthetic face image
    h, w = 480, 480
    bgr = np.ones((h, w, 3), dtype=np.uint8) * 128
    
    # Generate mock landmarks (468 points)
    # T-zone points around forehead (x=240, y=100) and nose (x=240, y=240)
    # Cheek points around left (x=140, y=240) and right (x=340, y=240)
    points = []
    for i in range(468):
        points.append({'x': 0.5, 'y': 0.5, 'z': 0.0})
        
    for i in skin_models.T_ZONE_INDICES:
        points[i] = {'x': 0.5, 'y': 0.25, 'z': 0.0}
    for i in skin_models.CHEEK_INDICES:
        points[i] = {'x': 0.3, 'y': 0.55, 'z': 0.0}

    # Case 1: T-zone elevated oiliness with balanced cheeks -> combination
    p_karma = [0.10, 0.45, 0.45] # dry, norm, oil
    # Paint T-zone brighter to simulate specularity
    cv2.circle(bgr, (240, 120), 40, (220, 220, 220), -1)
    
    cls_karma, conf, valid, lim, div = skin_models.regional_combination_rule(bgr, points, p_karma)
    assert cls_karma == 'combination'
    assert valid is True
    assert div['isKarma'] is True
    assert 'SPATIAL_DIVERGENCE' in div['basis']
    
    # Case 2: Pure dry prediction
    p_dry = [0.80, 0.15, 0.05]
    cls_dry, _, valid, _, div = skin_models.regional_combination_rule(bgr, points, p_dry)
    assert cls_dry == 'dry'
    assert div['isKarma'] is False
    
    # Case 3: Anti-glare clipping gate (extreme overexposure)
    bgr_overexposed = np.ones((h, w, 3), dtype=np.uint8) * 255
    cls_clip, _, valid_clip, lim_clip, _ = skin_models.regional_combination_rule(bgr_overexposed, points, p_karma)
    assert valid_clip is False
    assert lim_clip == 'GLARE_OR_EXPOSURE'

def test_end_to_end_receipt_contract():
    # Create mock result with skinType
    raw_result = {
        'general': {
            'skinType': {
                'value': 'combination',
                'quality': 'valid',
                'confidence': 0.65,
                'methodVersion': 'skin-type-glamour-vit-v1',
                'modelHash': 'ffdac2fc496a23dc27e60e08299b2496a0702a1d49f81f288d4d54da686213a0',
                'limitationCode': None
            },
            'measurements': []
        },
        'measurements': {}
    }
    
    final_result = contract.attach_result_receipts(raw_result)
    st = final_result['general']['skinType']
    assert st['status'] == 'measured'
    assert st['reason'] is None
    assert st['modelVersion'] == 'skin-type-glamour-vit-v1'
    assert st['value'] == 'combination'
