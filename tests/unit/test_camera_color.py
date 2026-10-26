"""Raw camera frame conversion, vehicle camera profile and chart calibration (no models, no network)."""
import base64, hashlib, json, sys
from pathlib import Path
import cv2, numpy as np, pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import camera_color as CC
import camera_calibration as CAL


def face_like(h=96, w=128, seed=1):
    rng = np.random.default_rng(seed)
    base = np.zeros((h, w, 3), np.float32); base[:] = (120, 150, 200)  # BGR skin-ish
    base += cv2.GaussianBlur(rng.normal(0, 25, (h, w, 3)).astype(np.float32), (0, 0), 3)
    return base.clip(0, 255).astype(np.uint8)


def raw_of(bgr, fmt='I420', pad=0, tag=None):
    h, w = bgr.shape[:2]
    i420 = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV_I420).ravel()
    Y, U, V = i420[:w * h].reshape(h, w), i420[w * h:w * h * 5 // 4].reshape(h // 2, w // 2), i420[w * h * 5 // 4:].reshape(h // 2, w // 2)
    def padded(p, extra): return np.hstack([p, np.zeros((p.shape[0], extra), np.uint8)]) if extra else p
    if fmt == 'I420':
        planes = [padded(Y, pad), padded(U, pad // 2), padded(V, pad // 2)]
    else:
        planes = [padded(Y, pad), padded(np.stack([U, V], -1).reshape(h // 2, w), pad)]
    layout, off, chunks = [], 0, []
    for p in planes:
        layout.append({'offset': off, 'stride': p.shape[1]}); chunks.append(p.ravel()); off += p.size
    return {'format': fmt, 'codedWidth': w, 'codedHeight': h, 'visibleRect': {'x': 0, 'y': 0, 'width': w, 'height': h}, 'layout': layout,
            'colorSpace': {'matrix': tag, 'fullRange': False if tag else None, 'primaries': tag, 'transfer': tag},
            'data': base64.b64encode(np.concatenate(chunks).tobytes()).decode()}


def png(bgr):
    ok, enc = cv2.imencode('.png', bgr); assert ok
    return 'data:image/png;base64,' + base64.b64encode(enc.tobytes()).decode(), hashlib.sha256(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()


@pytest.mark.parametrize('fmt,pad', [('I420', 0), ('NV12', 0), ('I420', 32), ('NV12', 16)])
def test_raw_planes_convert_exactly_like_opencv_bt601(fmt, pad):
    bgr = face_like(); truth = cv2.cvtColor(cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV_I420), cv2.COLOR_YUV2BGR_I420)
    out, info = CC.raw_frame_bgr(raw_of(bgr, fmt, pad), None)
    assert info['matrix'] == 'bt601' and info['matrixSource'] == 'default-bt601'
    assert np.array_equal(out, truth)


def test_profile_matrix_overrides_a_wrong_frame_tag():
    """The observed fault: BT.601 data tagged BT.709. The tag alone reproduces the browser's shift; the profile fixes it."""
    bgr = face_like(); truth = cv2.cvtColor(cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV_I420), cv2.COLOR_YUV2BGR_I420)
    raw = raw_of(bgr, 'NV12', tag='bt709')
    tagged, info = CC.raw_frame_bgr(raw, None)
    assert info['matrixSource'] == 'frame-tag' and info['matrix'] == 'bt709'
    assert np.abs(tagged.astype(int) - truth).mean() > 1.5           # the colour shift seen in the browser path
    fixed, info = CC.raw_frame_bgr(raw, {'profileId': 'p', 'yuv': {'matrix': 'bt601', 'fullRange': False}})
    assert info['matrixSource'] == 'camera-profile' and np.array_equal(fixed, truth)


def test_generic_formula_matches_opencv_for_bt601_within_rounding():
    bgr = face_like(); i420 = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV_I420).ravel(); h, w = bgr.shape[:2]
    Y, U, V = i420[:w * h].reshape(h, w), i420[w * h:w * h * 5 // 4].reshape(h // 2, w // 2), i420[w * h * 5 // 4:].reshape(h // 2, w // 2)
    truth = cv2.cvtColor(i420.reshape(h * 3 // 2, w), cv2.COLOR_YUV2BGR_I420).astype(int)
    d = np.abs(CC.generic_yuv_to_bgr(Y, U, V, 'bt601', False).astype(int) - truth)
    assert d.mean() < 1.0 and d.max() <= 12        # differs only by chroma upsampling/rounding
    d709 = np.abs(CC.generic_yuv_to_bgr(Y, U, V, 'bt709', False).astype(int) - truth)
    assert d709.mean() > d.mean() + 0.5             # a wrong matrix is visibly different


def test_bad_raw_frames_are_rejected():
    raw = raw_of(face_like())
    with pytest.raises(CC.CameraColorError): CC.raw_frame_bgr({**raw, 'format': 'RGBA'}, None)
    with pytest.raises(CC.CameraColorError): CC.raw_frame_bgr({**raw, 'layout': raw['layout'][:2]}, None)
    with pytest.raises(CC.CameraColorError): CC.raw_frame_bgr({**raw, 'data': base64.b64encode(b'x' * 100).decode()}, None)
    with pytest.raises(CC.CameraColorError): CC.raw_frame_bgr({**raw, 'visibleRect': {'x': 1, 'y': 0, 'width': 64, 'height': 64}}, None)


def test_prepare_swaps_pixels_and_restore_keeps_the_client_identity():
    bgr = face_like(); photo, pid = png(bgr)
    value = {'photo': photo, 'photoId': pid, 'rawFrame': raw_of(bgr), 'expressionObservation': {'photoId': pid, 'version': 'v'}, 'landmarks': []}
    out, info, client, new = CC.prepare(value, None)
    assert client == pid and new != pid and out['photoId'] == new and out['expressionObservation']['photoId'] == new and 'rawFrame' not in out
    assert info['source'] == 'raw-yuv' and info['browserMeanAbsDiff'] >= 0 and info['colorCorrection'] is None
    res = CC.restore({'photoId': new, 'maps': {'a': {'photoId': new}}}, info, client, new)
    assert res['photoId'] == pid and res['maps']['a']['photoId'] == pid and res['cameraColor']['analyzedPhotoSHA256'] == new
    with pytest.raises(ValueError): CC.prepare({**value, 'photoId': '0' * 64}, None)                       # PNG identity first
    with pytest.raises(CC.CameraColorError): CC.prepare({**value, 'rawFrame': raw_of(face_like(64, 64))}, None)  # other frame size
    same, info, c, n = CC.prepare({'photo': photo, 'photoId': pid}, None)                                   # no raw, no profile: untouched
    assert same['photo'] == photo and c is None and info['source'] == 'browser-rgb'


def test_profile_loading_and_ccm(tmp_path):
    p = tmp_path / 'p.json'
    good = {'schema': CC.SCHEMA, 'profileId': 'x', 'yuv': {'matrix': 'bt601', 'fullRange': False}, 'ccm': np.eye(3).tolist(), 'offset': [0, 0, 0]}
    p.write_text(json.dumps(good)); prof = CC.load_profile(str(p))
    assert prof['profileId'] == 'x' and len(prof['sha256']) == 64
    bgr = face_like(); assert np.abs(CC.apply_ccm(bgr, prof).astype(int) - bgr).max() <= 1   # identity correction
    for bad in ({**good, 'schema': 'other'}, {**good, 'ccm': [[1, 0], [0, 1]]}, {**good, 'ccm': (np.eye(3) * 9).tolist()}, {**good, 'yuv': {'matrix': 'bt999', 'fullRange': False}}):
        p.write_text(json.dumps(bad))
        with pytest.raises(CC.CameraProfileUnavailable): CC.load_profile(str(p))
    with pytest.raises(CC.CameraProfileUnavailable): CC.load_profile(str(tmp_path / 'missing.json'))


def synthetic_chart_photo(D, gain=0.92, offset=(.004, .003, .006), noise=1.5, seed=0):
    chart = CAL.render_chart(px_per_mm=4); h, w = chart.shape[:2]
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), np.float32([[520, 230], [1430, 280], [1390, 900], [560, 860]]))
    scene = cv2.warpPerspective(chart, M, (1920, 1080), borderValue=(70, 70, 70))
    lin = CC.srgb_to_linear(scene[..., ::-1] / 255.) @ np.asarray(D).T * gain + np.asarray(offset)
    return (CC.linear_to_srgb(lin) * 255 + np.random.default_rng(seed).normal(0, noise, lin.shape)).clip(0, 255).astype(np.uint8)[..., ::-1]


def test_chart_fit_recovers_a_camera_colour_distortion(tmp_path):
    D = np.array([[1.08, .06, -.02], [.03, .95, .04], [-.04, .08, .86]])
    m = CAL.measure_chart(synthetic_chart_photo(D))
    assert m['ok'] and m['reprojectionErrorPx'] < 2 and sum(p['usable'] for p in m['patches']) == 24
    prof, rep = CAL.fit_profile([m], 'veh-test', yuv={'matrix': 'bt601', 'fullRange': False})
    assert rep['status'] == 'ACCEPTED' and rep['fit']['deltaE00After']['mean'] < 1 < rep['fit']['deltaE00Before']['mean']
    assert np.abs(np.asarray(prof['ccm']) - np.linalg.inv(D * 0.92)).max() < 0.03
    path = tmp_path / 'profile.json'; CAL.write_profile(prof, str(path))
    loaded = CC.load_profile(str(path)); assert loaded['profileId'] == 'veh-test'


def test_calibration_gates_reject_unusable_photos():
    _, rep = CAL.fit_profile([CAL.measure_chart(np.full((720, 1280, 3), 128, np.uint8))], 'x')
    assert rep['status'] == 'REJECTED' and rep['reason'] == 'NO_CHART_FOUND'
    over = synthetic_chart_photo(np.eye(3), gain=3.0)    # heavy overexposure: most patches clip
    _, rep = CAL.fit_profile([CAL.measure_chart(over)], 'x')
    assert rep['status'] == 'REJECTED' and rep['reason'] == 'TOO_FEW_USABLE_PATCHES'


def test_calibration_endpoint_is_disabled_by_default(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    monkeypatch.delenv('ATTUNE_CAMERA_CALIBRATION', raising=False)
    r = TestClient(app).post('/api/local-health/skin/camera-calibration', json={'processingConsent': True})
    assert r.status_code == 403 and r.json()['detail'] == 'CAMERA_CALIBRATION_DISABLED'
