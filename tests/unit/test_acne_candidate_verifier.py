"""Focused checks for the acne candidate verifier (research staging; not connected to the product).
Pure checks (always run): feature sampling geometry, feature size, verifier formula, verifier can only remove.
Data checks (skip when local caches/weights are absent): train/runtime feature parity, fixed Step0 weights, frozen model hash,
duplicate leakage between TRAIN and DEV, learn/calibration group separation.
"""
import hashlib, json, sys
from pathlib import Path
import numpy as np, pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/skin-research'), str(ROOT / 'services/core-api')]
import acne_candidate_verifier as V

VER = ROOT / 'audit-results/acne-verifier'; MODEL = ROOT / 'docs/acne-verifier-model-20261016.json'


def ramp(C, H, W):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32); return np.repeat((x + 10 * y)[None], C, 0)


def test_level_features_sample_cell_centres_bilinearly():
    f = ramp(3, 20, 20); u, v, s = 37., 51., 4                          # cell centres at (i + .5) * stride
    out = V.level_features(f, u, v, s); gx, gy = u / s - .5, v / s - .5
    assert np.allclose(out[:3], gx + 10 * gy, atol=1e-4)
    cx, cy = round(gx), round(gy); assert np.allclose(out[3:], cx + 10 * cy, atol=1e-4)   # symmetric +-2 window mean of a ramp
    edge = V.level_features(f, -50., -50., s); assert np.allclose(edge[:3], 0.)              # clamped to the map, no wrap-around


def test_candidate_features_are_1920_dims_in_level_order():
    maps = [np.full((c, 384 // s, 384 // s), i, np.float32) for i, (c, s) in enumerate(zip((64, 128, 256, 512), V.STRIDES))]
    f = V.candidate_features(maps, 100., 200.); assert f.shape == (1920,)
    assert (f[:128] == 0).all() and (f[128:384] == 1).all() and (f[384:896] == 2).all() and (f[896:] == 3).all()


def test_verifier_formula_and_only_removes(tmp_path):
    rng = np.random.default_rng(0); d = dict(featureVersion=V.VERSION, standardizer=dict(mean=rng.normal(size=1920).tolist(), scale=(1 + rng.random(1920)).tolist()),
                                             model=dict(coef=(rng.normal(size=1920) / 40).tolist(), intercept=.3), threshold=.5)
    p = tmp_path / 'v.json'; p.write_text(json.dumps(d)); ver = V.Verifier(p); X = rng.normal(size=(7, 1920))
    z = ((X - d['standardizer']['mean']) / d['standardizer']['scale']) @ d['model']['coef'] + .3
    assert np.allclose(ver.proba(X), 1 / (1 + np.exp(-z))); k = ver.keep(X); assert k.dtype == bool and k.shape == (7,)
    assert ver.keep(np.zeros((0, 1920))).shape == (0,)


def need(*paths):
    for p in paths:
        if not Path(p).exists(): pytest.skip(f'local data absent: {p}')


def test_frozen_model_hash_and_step0_weight_hash():
    need(MODEL); import run_acne_v2_pilot as v2
    assert hashlib.sha256(MODEL.read_bytes()).hexdigest() == 'b6fa6c05b48a092623f7780200c07440ebaf934989ab66518ee21b23fa304f8a'
    assert v2.STEP0_SHA256.startswith('18e94a95')
    w = ROOT.parent / 'attune-live-test' / v2.TAKEOVER / 'models/step0.safetensors'; need(w)
    assert hashlib.sha256(w.read_bytes()).hexdigest() == v2.STEP0_SHA256


def test_no_duplicate_leak_and_disjoint_splits():
    need(VER / 'labels.json', VER / 'dev'); import cv2, verifier_extract as X, verifier_train as T
    L = json.loads((VER / 'labels.json').read_text()); rows = L['rows']; grp = L['groups']
    used = {r['photo'] for r in rows}; tr = {s[:12]: f for s, k, f, rp, _ in X.items('train')}; dv = {s[:12]: f for s, k, f, rp, _ in X.items('dev')}
    assert not used & set(dv), 'DEV photo in TRAIN'
    hd = {p: T.dhash(f) for p, f in dv.items()}
    for p in used:
        h = T.dhash(tr[p]); assert min(int((h != x).sum()) for x in hd.values()) > 10, ('near-duplicate of DEV in TRAIN', p)
    split = {}
    for r in rows:
        if r['split']: split.setdefault(grp[r['photo']], set()).add(r['split'])
    assert all(len(s) == 1 for s in split.values()), 'a photo group is in both learn and calibration'


def test_train_runtime_feature_parity_and_fixed_step0():
    """Runtime path (photo command) reproduces cached TRAIN features and Step0 boxes exactly and leaves Step0 parameters untouched."""
    need(VER / 'labels.json', MODEL); pytest.importorskip('torch'); import verifier_extract as X, acne_verifier_photo as P
    its = X.items('train'); rows = json.loads((VER / 'labels.json').read_text())['rows']
    ph = [r['photo'] for r in rows if r['label'] is not None][:1] + [r['photo'] for r in rows if r['label'] == 0][:1]
    sel = [it for it in its if it[0][:12] in ph]; out = Path(VER / '_parity'); out.mkdir(exist_ok=True)
    rp = out / 'rp.jsonl'; rp.write_text('\n'.join(json.dumps(it[3]) for it in sel))
    res = P.main(['--out', str(out), '--replay', str(rp), '--no-image'] + [it[2] for it in sel])     # asserts STEP0_PARAMETERS_CHANGED internally
    for it in sel:
        p = it[0][:12]; cached = np.load(VER / 'train' / f'{p}.npz')['features']; now = np.load(out / f'{p}-features.npz')['features']
        rec = json.loads((VER / 'train' / f'{p}.json').read_text())
        assert [[round(x, 2) for x in b[:4]] for b in rec['final']] == [b[:4] for b in res[p]['A']]
        assert cached.shape == now.shape and np.allclose(cached, now, atol=1e-5)
