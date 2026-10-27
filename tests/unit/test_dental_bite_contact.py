"""Regression tests for the dental BITE gate and the border-candidate speed fix.

Synthetic geometry only (no photos, no model). Cases mirror
tests/unit/dental_bite_contact_parity.cjs so the client gate and the backend
re-validation stay identical.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import dental_analysis as d  # noqa: E402


def mouth_case(kind, size=(240, 400)):
    """Return (tooth, mouth, p, width) for a frontal mouth.

    kind: 'bite' upper+lower rows touching at the lip midline,
          'wide-bite' same contact but a tall lip aperture (wide smile),
          'open' two rows separated by a dark/tongue band,
          'upper-only' open mouth with only the upper row visible.
    """
    h, w = size
    p = np.zeros((468, 2), np.float32)
    left, right, cx = 100., 300., 200.
    top, bottom = {'bite': (90, 150), 'wide-bite': (60, 180), 'open': (70, 170), 'upper-only': (70, 170)}[kind]
    mid = (top + bottom) / 2
    p[78] = (left, mid); p[308] = (right, mid); p[13] = (cx, top); p[14] = (cx, bottom)
    mouth = np.zeros((h, w), bool)
    cv2.ellipse(mouth.view(np.uint8), (int(cx), int(mid)), (int((right - left) / 2), int((bottom - top) / 2)), 0, 0, 360, 1, -1)
    tooth = np.zeros((h, w), bool)
    if kind in ('bite', 'wide-bite'):
        tooth[int(mid) - 22:int(mid) + 20, 130:270] = True  # rows touch across the midline
        tooth[int(mid) - 1:int(mid) + 1, 130:270:14] = False  # thin incisal lines/embrasures
    elif kind == 'open':
        tooth[int(top) + 4:int(mid) - 14, 130:270] = True
        tooth[int(mid) + 14:int(bottom) - 4, 130:270] = True
    else:
        tooth[int(top) + 4:int(mid) - 8, 130:270] = True
    tooth &= mouth
    return tooth, mouth, p, float(right - left)


def test_contact_confirms_natural_and_wide_smile_bite():
    for kind in ('bite', 'wide-bite'):
        tooth, mouth, p, width = mouth_case(kind)
        result = d.incisal_contact(tooth, mouth, p, width)
        assert result['confirmed'], (kind, result)
        assert result['medianIncisalGapRatio'] <= d.BITE_CONTACT['maxGapRatio']


def test_wide_smile_bite_was_rejected_by_lip_ratio_but_is_a_bite():
    # Documents the replaced proxy: lip aperture/mouth width > .32 for a real bite.
    _, _, p, width = mouth_case('wide-bite')
    assert np.linalg.norm(p[13] - p[14]) / width > .32


def test_open_mouth_is_never_a_bite():
    for kind in ('open', 'upper-only'):
        tooth, mouth, p, width = mouth_case(kind)
        result = d.incisal_contact(tooth, mouth, p, width)
        assert not result['confirmed'], (kind, result)


def test_open_mouth_with_small_lip_ratio_is_not_a_bite():
    # The old rule (opening <= .32) accepted this frame as BITE.
    tooth, mouth, p, width = mouth_case('open')
    assert np.linalg.norm(p[13] - p[14]) / width <= .5
    assert not d.incisal_contact(tooth, mouth, p, width)['confirmed']


def _reference_calculus(image, tooth, gum):
    """The previous full-frame implementation, kept verbatim as an oracle."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    border = tooth & cv2.dilate(gum.astype(np.uint8), np.ones((11, 11), np.uint8)).astype(bool)
    yellow = (hsv[:, :, 0] > 10) & (hsv[:, :, 0] < 40) & (hsv[:, :, 1] > 55) & (hsv[:, :, 1] < 170)
    texture = np.sqrt(np.maximum(0, cv2.GaussianBlur(gray * gray, (0, 0), 1.5) - cv2.GaussianBlur(gray, (0, 0), 1.5) ** 2))
    gradient = np.hypot(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    mask = border & yellow & (texture > .025) & (gradient > .12) & (gray > .15) & (gray < .9)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8)); candidates = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 6 or area > tooth.sum() * .15: continue
        cc, _ = cv2.findContours((labels == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates.append(dict(bounds=dict(x=int(x), y=int(y), width=int(w), height=int(h)), points=max(cc, key=cv2.contourArea)[:, 0, :].tolist(), areaPixels=int(area)))
    return candidates, int(border.sum())


def test_border_candidates_identical_to_previous_implementation():
    rng = np.random.default_rng(20261027)
    for _ in range(3):
        image = rng.integers(0, 255, (180, 260, 3), dtype=np.uint8)
        image[..., 0] = (image[..., 0] * .35).astype(np.uint8)  # yellowish noise -> many components
        image = cv2.GaussianBlur(image, (3, 3), 0)
        tooth = rng.random((180, 260)) > .2
        gum = rng.random((180, 260)) > .85
        assert d.calculus_candidates(image, tooth, gum) == _reference_calculus(image, tooth, gum)


def test_upload_quality_keeps_no_pose_rule():
    # Uploads never had an aperture/contact rejection; pose_check=False keeps that.
    import inspect
    import dental_upload
    assert 'pose_check=False' in inspect.getsource(dental_upload.upload_roi)
