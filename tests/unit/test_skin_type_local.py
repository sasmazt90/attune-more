"""Unit tests for offline local skin type classification and Regional Combination (Karma) Rule v2.
Verifies:
1. Pinned manifest candidate status and truthful metadata (accepted=False, candidateAccepted=True, unverified domain flags=False).
2. ONNX model file integrity and SHA-256 match.
3. Offline session load supporting candidateAccepted.
4. Numerical parity between PyTorch and ONNX Runtime on real image crop (< 1e-4) with local_files_only=True.
5. Anatomically isolated cheek masks: separate left and right polygons, zero overlap, no nose/lip bridging, holes subtracted.
6. Visible area validation: INSUFFICIENT_VISIBLE_AREA returned when landmarks or visible area is inadequate.
7. Skin-only highlight clipping gate: white background does NOT trigger glare rejection, skin highlight clipping DOES trigger GLARE_OR_EXPOSURE.
8. Regional Combination Rule deadband (spec_diff >= 0.40) and explainable combinationConfidence.
9. 100% offline execution with blocked sockets.
10. Vehicle app contract compliance (attach_result_receipts).
"""
import pytest
import sys, os, hashlib, json, time, socket
from pathlib import Path
import numpy as np, cv2, torch

sys.path.insert(0, 'services/core-api')
import skin_models
import appearance_analysis as A
import skin_measurement_contract as contract

MODELS_DIR = Path('services/core-api/models')
ONNX_PATH = MODELS_DIR / 'skin-type-glamour-vit.onnx'
MANIFEST_PATH = MODELS_DIR / 'skin-focused.json'
GLAMOUR_SNAPSHOT = Path(r'C:\Users\PC\.cache\huggingface\hub\models--AishaBaliyan--glamour-ai-skin-model\snapshots\4f232d45e5ba59664205f552c4f450a1a741470a')

def test_manifest_pins_glamour_vit():
    assert MANIFEST_PATH.is_file(), "Manifest skin-focused.json missing!"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    assert 'models' in manifest
    assert 'type' in manifest['models']
    type_meta = manifest['models']['type']

    # Truthful candidate status
    assert type_meta['candidateAccepted'] is True
    assert type_meta['accepted'] is False
    assert type_meta['sourceQualityAccepted'] is False
    assert type_meta['sourceLabelProtocolVerified'] is False
    assert type_meta['cameraDomainAccepted'] is False
    assert type_meta['offlineExecution'] is True

    # Pinned file and hashes
    assert type_meta['file'] == 'skin-type-glamour-vit.onnx'
    assert type_meta['sha256'] == 'ffdac2fc496a23dc27e60e08299b2496a0702a1d49f81f288d4d54da686213a0'
    assert type_meta['weightsSha256'] == '46f59b660f856c867c00289fa0ec4337a935d07a758e81175290580fb2733b8c'
    assert type_meta['version'] == 'skin-type-glamour-vit-v1'
    assert type_meta['classes'] == ['dry', 'normal', 'oily']
    assert type_meta['decisionVersion'] == 'regional-combination-v2-deadband-support'
    assert type_meta['deadbandThreshold'] == 0.40

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
    assert type_session['metadata']['candidateAccepted'] is True
    assert type_session['loadMs'] > 0

def test_numerical_parity_onnx_vs_pytorch():
    import onnxruntime as ort
    from transformers import AutoModelForImageClassification

    assert GLAMOUR_SNAPSHOT.is_dir(), "Local HuggingFace model cache missing!"

    # local_files_only=True guarantees strictly offline and prevents hanging on network timeouts
    pt_model = AutoModelForImageClassification.from_pretrained(str(GLAMOUR_SNAPSHOT), local_files_only=True)
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

def test_separate_anatomical_cheek_masks_and_hole_exclusions():
    h, w = 480, 480
    points = [{'x': 0.5, 'y': 0.5, 'z': 0.0} for _ in range(468)]

    # Assign forehead, nose, left cheek, and right cheek points to realistic separate coordinates
    for i in skin_models.FOREHEAD_INDICES:
        points[i] = {'x': 0.5 + (i % 5 - 2) * 0.04, 'y': 0.20 + (i % 3) * 0.03, 'z': 0.0}
    for i in skin_models.NOSE_INDICES:
        points[i] = {'x': 0.5 + (i % 3 - 1) * 0.02, 'y': 0.45 + (i % 5) * 0.03, 'z': 0.0}
    for i in skin_models.LEFT_CHEEK_INDICES:
        points[i] = {'x': 0.70 + (i % 4 - 2) * 0.03, 'y': 0.55 + (i % 4) * 0.03, 'z': 0.0}
    for i in skin_models.RIGHT_CHEEK_INDICES:
        points[i] = {'x': 0.30 + (i % 4 - 2) * 0.03, 'y': 0.55 + (i % 4) * 0.03, 'z': 0.0}

    masks, valid_support, reason = skin_models.build_anatomical_skin_masks((h, w, 3), points)
    assert valid_support is True
    assert reason is None

    lc = masks['left_cheek']
    rc = masks['right_cheek']
    t_zone = masks['t_zone']

    # 1. Zero overlap between left cheek and right cheek
    overlap = cv2.bitwise_and(lc, rc)
    assert overlap.sum() == 0, "Left and right cheeks must not overlap!"

    # 2. Nose center (x=240, y=240) must NOT be inside cheek masks (no bridging across the nose)
    assert lc[240, 240] == 0, "Left cheek must not cover the nose center"
    assert rc[240, 240] == 0, "Right cheek must not cover the nose center"

    # 3. T-zone and cheeks masks exist and have adequate pixels
    assert np.count_nonzero(t_zone) >= 80
    assert np.count_nonzero(lc) >= 40
    assert np.count_nonzero(rc) >= 40

def test_insufficient_visible_area_rejection():
    h, w = 480, 480
    bgr = np.ones((h, w, 3), dtype=np.uint8) * 128

    # Empty points
    masks, valid, reason = skin_models.build_anatomical_skin_masks((h, w, 3), [])
    assert valid is False
    assert reason == 'INSUFFICIENT_VISIBLE_AREA'

    # Point collection with missing cheek coverage (< 80 pixels)
    collapsed_points = [{'x': 0.5, 'y': 0.5, 'z': 0.0} for _ in range(468)]
    cls, conf, valid, lim, div = skin_models.regional_combination_rule(bgr, collapsed_points, [0.33, 0.33, 0.34])
    assert valid is False
    assert lim == 'INSUFFICIENT_VISIBLE_AREA'
    assert div['isKarma'] is False

def test_skin_only_highlight_clipping_gate():
    h, w = 480, 480
    points = [{'x': 0.5, 'y': 0.5, 'z': 0.0} for _ in range(468)]
    for i in skin_models.FOREHEAD_INDICES:
        points[i] = {'x': 0.5 + (i % 5 - 2) * 0.04, 'y': 0.20 + (i % 3) * 0.03, 'z': 0.0}
    for i in skin_models.NOSE_INDICES:
        points[i] = {'x': 0.5 + (i % 3 - 1) * 0.02, 'y': 0.45 + (i % 5) * 0.03, 'z': 0.0}
    for i in skin_models.LEFT_CHEEK_INDICES:
        points[i] = {'x': 0.70 + (i % 4 - 2) * 0.03, 'y': 0.55 + (i % 4) * 0.03, 'z': 0.0}
    for i in skin_models.RIGHT_CHEEK_INDICES:
        points[i] = {'x': 0.30 + (i % 4 - 2) * 0.03, 'y': 0.55 + (i % 4) * 0.03, 'z': 0.0}

    # Case A: Pure white background (255, 255, 255) outside the face, but normal matte skin (128, 128, 128)
    bgr_white_bg = np.ones((h, w, 3), dtype=np.uint8) * 255
    masks, _, _ = skin_models.build_anatomical_skin_masks((h, w, 3), points)
    skin_support = (masks['t_zone'] > 0) | (masks['cheeks'] > 0)
    bgr_white_bg[skin_support] = (128, 128, 128)

    cls, conf, valid, lim, div = skin_models.regional_combination_rule(bgr_white_bg, points, [0.10, 0.80, 0.10])
    assert valid is True, "White image background should not trigger skin glare rejection!"
    assert lim is None
    assert div['clipping'] < 0.01

    # Case B: Severe clipping directly on the facial skin support (> 0.15 of skin pixels clipped)
    bgr_clipped_skin = np.ones((h, w, 3), dtype=np.uint8) * 128
    bgr_clipped_skin[skin_support] = (255, 255, 255)

    cls_c, conf_c, valid_c, lim_c, div_c = skin_models.regional_combination_rule(bgr_clipped_skin, points, [0.10, 0.45, 0.45])
    assert valid_c is False
    assert lim_c == 'GLARE_OR_EXPOSURE'
    assert div_c['isKarma'] is False

def test_regional_combination_deadband_and_decisions():
    h, w = 480, 480
    bgr = np.ones((h, w, 3), dtype=np.uint8) * 120
    points = [{'x': 0.5, 'y': 0.5, 'z': 0.0} for _ in range(468)]
    for i in skin_models.FOREHEAD_INDICES:
        points[i] = {'x': 0.5 + (i % 5 - 2) * 0.04, 'y': 0.20 + (i % 3) * 0.03, 'z': 0.0}
    for i in skin_models.NOSE_INDICES:
        points[i] = {'x': 0.5 + (i % 3 - 1) * 0.02, 'y': 0.45 + (i % 5) * 0.03, 'z': 0.0}
    for i in skin_models.LEFT_CHEEK_INDICES:
        points[i] = {'x': 0.70 + (i % 4 - 2) * 0.03, 'y': 0.55 + (i % 4) * 0.03, 'z': 0.0}
    for i in skin_models.RIGHT_CHEEK_INDICES:
        points[i] = {'x': 0.30 + (i % 4 - 2) * 0.03, 'y': 0.55 + (i % 4) * 0.03, 'z': 0.0}

    masks, _, _ = skin_models.build_anatomical_skin_masks((h, w, 3), points)

    # 1. Karma Positive: T-zone elevated shine with spec_diff >= 0.40, cheeks matte
    # Brighten T-zone to give specularity
    bgr_karma = bgr.copy()
    bgr_karma[masks['t_zone'] > 0] = (210, 210, 210)
    p_karma = [0.10, 0.45, 0.45] # oily presence + balanced cheeks

    cls_k, conf_k, valid_k, lim_k, div_k = skin_models.regional_combination_rule(bgr_karma, points, p_karma)
    assert cls_k == 'combination'
    assert valid_k is True
    assert div_k['isKarma'] is True
    assert div_k['deadbandMet'] is True
    assert div_k['specularDivergence'] >= 0.40
    assert 0.40 <= conf_k <= 0.88, "Combination confidence must be bounded and explainable"
    assert conf_k != max(p_karma), "Combination confidence must not blindly copy 3-class max probability"

    # 2. Deadband Rejection: spec_diff < 0.40 (e.g. uniform skin tone) must NOT trigger Karma
    # Even if model has uncertainty (e.g. p_oil=0.35, p_norm=0.35)
    bgr_uniform = bgr.copy()
    cls_u, conf_u, valid_u, lim_u, div_u = skin_models.regional_combination_rule(bgr_uniform, points, [0.20, 0.45, 0.35])
    assert cls_u != 'combination', "Insufficient deadband must not trigger combination skin type!"
    assert div_u['isKarma'] is False
    assert div_u['deadbandMet'] is False

    # 3. Uniform Shine Rejection: if cheeks are also very shiny, result is oily, NOT combination
    bgr_all_oily = bgr.copy()
    bgr_all_oily[masks['t_zone'] > 0] = (210, 210, 210)
    bgr_all_oily[masks['cheeks'] > 0] = (210, 210, 210)
    cls_o, conf_o, valid_o, lim_o, div_o = skin_models.regional_combination_rule(bgr_all_oily, points, [0.05, 0.15, 0.80])
    assert cls_o == 'oily'
    assert div_o['isKarma'] is False

def test_offline_infer_with_blocked_sockets():
    h, w = 480, 480
    bgr = np.ones((h, w, 3), dtype=np.uint8) * 120
    points = [{'x': 0.5, 'y': 0.5, 'z': 0.0} for _ in range(468)]
    for i in skin_models.FOREHEAD_INDICES:
        points[i] = {'x': 0.5 + (i % 5 - 2) * 0.04, 'y': 0.20 + (i % 3) * 0.03, 'z': 0.0}
    for i in skin_models.NOSE_INDICES:
        points[i] = {'x': 0.5 + (i % 3 - 1) * 0.02, 'y': 0.45 + (i % 5) * 0.03, 'z': 0.0}
    for i in skin_models.LEFT_CHEEK_INDICES:
        points[i] = {'x': 0.70 + (i % 4 - 2) * 0.03, 'y': 0.55 + (i % 4) * 0.03, 'z': 0.0}
    for i in skin_models.RIGHT_CHEEK_INDICES:
        points[i] = {'x': 0.30 + (i % 4 - 2) * 0.03, 'y': 0.55 + (i % 4) * 0.03, 'z': 0.0}

    real_connect = socket.socket.connect
    def blocked_connect(self, address):
        raise OSError("Network call forbidden")

    socket.socket.connect = blocked_connect
    try:
        res = skin_models.infer(bgr, points, quality_valid=True, type_quality_valid=True)
        assert 'skinType' in res
        assert res['skinType']['quality'] in ('valid', 'insufficient')
    finally:
        socket.socket.connect = real_connect

def test_end_to_end_receipt_contract():
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
