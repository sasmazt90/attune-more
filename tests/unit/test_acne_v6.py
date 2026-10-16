"""Acne v6 checks: clean-ROI candidates never touch annotated boxes, ROI false candidates are counted from frozen masks only,
frozen ROIs are hash-checked, and the v6 TRAIN manifest holds no DEV / DEV-EXT / 941 / failed-evaluation photo or group."""
import hashlib, json, sys
from pathlib import Path
import numpy as np, pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/skin-research')]
A = ROOT / 'audit-results'


def _landmarks():
    rng = np.random.default_rng(0); pts = rng.uniform(.25, .75, (478, 2))
    import build_acne_roi_v6 as b
    for name, poly in b.REG.items():                    # make each region a convex-ish patch on a plain face
        cx, cy = dict(cheekL=(.3, .6), cheekR=(.7, .6), forehead=(.5, .25))[name]
        for k, i in enumerate(poly):
            a = 2 * np.pi * k / len(poly); pts[i] = (cx + .12 * np.cos(a), cy + .08 * np.sin(a))
    return [dict(x=float(x), y=float(y)) for x, y in pts]


def test_roi_candidates_exclude_dilated_boxes():
    cv2 = pytest.importorskip('cv2')
    import build_acne_roi_v6 as b
    img = np.full((800, 800, 3), (150, 170, 210), np.uint8)
    boxes = [[220, 460, 236, 476], [540, 470, 560, 490], [390, 190, 402, 202]]
    out = b.candidate_masks(img, _landmarks(), boxes)
    assert any(m is not None for m in out.values())
    for m in out.values():
        if m is None: continue
        for bx in boxes:
            g = max(10, max(bx[2] - bx[0], bx[3] - bx[1]))
            assert not m[int(bx[1] - g):int(bx[3] + g), int(bx[0] - g):int(bx[2] + g)].any()


def test_roi_false_candidates_use_frozen_masks_only(tmp_path, monkeypatch):
    cv2 = pytest.importorskip('cv2')
    import eval_acne_v6 as e
    m = np.zeros((100, 100), np.uint8); m[10:40, 10:40] = 255; f = tmp_path / 'frozen'; f.mkdir(); cv2.imwrite(str(f / 'x.png'), m)
    sha = hashlib.sha256((f / 'x.png').read_bytes()).hexdigest()
    (tmp_path / 'frozen.json').write_text(json.dumps(dict(decisionsSHA256='d', masks=[dict(sha256='s' * 64, mask='frozen/x.png', pixels=900, maskSHA256=sha)])))
    monkeypatch.setitem(e.SETS, 'tmp', dict(out=tmp_path, roi=tmp_path, v5out=None))
    rois, F = e.roi_masks('tmp')
    assert e.centre_hits([[20, 20, 24, 24, .9], [60, 60, 64, 64, .9], [36, 36, 40, 40, .8]], rois['s' * 64]) == 2
    m[50:60, 50:60] = 255; cv2.imwrite(str(f / 'x.png'), m)          # any change after freezing must be refused
    with pytest.raises(AssertionError): e.roi_masks('tmp')


def test_v6_train_manifest_has_no_dev_or_excluded_photo():
    mf = A / 'acne-v6-data/manifest-v6.json'
    if not mf.exists(): pytest.skip('v6 data not prepared on this machine')
    man = json.loads(mf.read_text()); S = {p['sha256'] for p in man['photos']}; G = {p['researchGroup'] for p in man['photos']}
    m4 = json.loads((A / 'acne-v4-data/manifest-v4.json').read_text())['photos']; dx = json.loads((A / 'acne-v6/devext/manifest.json').read_text())['photos']
    dev = {p['sha256'] for p in m4 if p['role'] == 'DEV'} | {p['sha256'] for p in dx}
    devg = {p['researchGroup'] for p in m4 if p['role'] == 'DEV'} | {p['researchGroup'] for p in dx}
    other = {r['sha256'] for r in json.loads((A / 'acne-v4-data/photoselection/manifest.json').read_text()) if r['cohort'] != 'acne'}
    assert not S & dev and not G & devg and not S & other
    for p in man['photos']:
        if p.get('extension') == 'v6-trainext':
            assert p['positive'] or p.get('mask')                    # every added photo carries a reviewed signal
        if p['kind'] == 'positive-photo':
            assert all('review' in b for b in p['positive'])          # only reviewed boxes are positives
