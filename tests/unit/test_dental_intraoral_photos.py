"""Real licensed pixels and real pinned ONNX; no fabricated landmarks/results."""
import base64
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
from dental_upload import analyze_upload, upload_roi, UploadError
from dental_intraoral import intraoral_region

FIXTURES = ROOT / 'tests/fixtures/dental-intraoral'
MANIFEST = {v['file']: v for v in json.loads((FIXTURES / 'manifest.json').read_text())}


def photo(name):
    raw = (FIXTURES / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST[name]['sha256']
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def payload(image):
    ok, raw = cv2.imencode('.png', image)
    assert ok
    return {'photo': 'data:image/png;base64,' + base64.b64encode(raw).decode()}


@pytest.mark.parametrize('name', ['cdc-19464.jpg', 'cdc-19465.jpg', 'cdc-19466.jpg'])
def test_real_partial_intraoral_photo_to_actual_pinned_model_result(name):
    image = photo(name)
    request = payload(image)
    assert 'photoLandmarks' not in request
    result = analyze_upload(request)  # Actual decode, anatomy, quality and ONNX.
    view = result['views'][0]
    assert result['sourceType'] == 'upload'
    assert result['clinicalValidation'] is False
    assert view['quality']['geometrySource'] == 'verified-intraoral-crowns'
    assert view['quality']['fullFaceRequired'] is False
    assert view['quality']['motionGateApplied'] is False
    assert view['quality']['anatomicalEvidence']['crownCount'] >= 3
    metric = view['caries']
    assert metric['quality'] == 'valid'
    assert metric['modelHash'] == 'eafaca8139e4447b1aa64375156aa47764affd91cf0594392b896ea78463bf03'
    assert metric['decisionThreshold'] == .35
    assert metric['value'] == len(metric['candidates'])
    mouth, _ = intraoral_region(image)
    h, w = image.shape[:2]
    assert (view['sourceWidth'], view['sourceHeight']) == (w, h)
    for candidate in metric['candidates']:
        b = candidate['bounds']
        assert 0 <= b['x'] < w and 0 <= b['y'] < h
        assert b['x'] + b['width'] <= w and b['y'] + b['height'] <= h
        assert mouth[min(h-1, int(b['y']+b['height']/2)), min(w-1, int(b['x']+b['width']/2))]
    normalized = cv2.imdecode(np.frombuffer(base64.b64decode(result['normalizedPhoto'].split(',')[1]), np.uint8), cv2.IMREAD_COLOR)
    assert np.array_equal(normalized, image)  # Original source pixels preserved.


@pytest.mark.parametrize('name,box', [
    ('astronaut.png', (150, 15, 305, 80)),  # Real hair, no mouth.
    ('astronaut.png', (170, 65, 280, 100)),  # Forehead/hairline, no mouth.
    ('astronaut.png', (320, 0, 512, 300)),  # Bright rocket/background.
    ('coffee.png', None),  # Bright curved porcelain/foam beside brown tissue-like colours.
    ('chelsea.png', None),  # Textured fur, highlights and dark boundaries.
    ('brick.png', None),
])
def test_real_nonmouth_photographs_rejected_before_detector(name, box, monkeypatch):
    image = photo(name)
    if box:
        x0, y0, x1, y1 = box
        image = image[y0:y1, x0:x1].copy()
    import dental_analysis
    def forbidden(*args, **kwargs):
        pytest.fail('Non-mouth photograph reached the trained detector')
    monkeypatch.setattr(dental_analysis, 'model_candidates', forbidden)
    with pytest.raises(UploadError, match='MOUTH_ANATOMY_UNVERIFIED'):
        analyze_upload(payload(image))


def test_real_anatomy_does_not_waive_existing_glare_limit():
    image = photo('cdc-19463.jpg')
    assert intraoral_region(image) is not None
    with pytest.raises(UploadError, match='SALIVA_OR_GLARE'):
        upload_roi(image)


def test_real_crop_without_independent_crowns_is_not_assumed_to_be_a_mouth():
    image = photo('cdc-19465.jpg')[120:180, 250:300].copy()
    with pytest.raises(UploadError, match='MOUTH_ANATOMY_UNVERIFIED'):
        analyze_upload(payload(image))
