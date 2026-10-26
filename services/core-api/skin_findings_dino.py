"""Saved DINOv2-crop finding classifiers (models/<bundle>/findings-v2/*.json, exported by
research/skin-findings/export/export_dino.py with the exact research recipes; see that file and CODEX_HANDOFF.md).

Per photo: landmark crops (same indices and padding as research/skin-findings/scripts/finding_clf.py), 224x224 RGB,
DINOv2-small CLS + mean patch token (768), fold-ensemble of StandardScaler+LogisticRegression -> probability per crop.
A side photo contributes only the crops of the side that faces the camera (research SIDE_OK rule).
Embedding parity with the research cache was checked (max |diff| 0.0 on all 25 crops of a 3-pose person)."""
from __future__ import annotations
import glob, json, os, threading
import numpy as np

CROPS = {
    'under_L': ([33, 7, 163, 144, 145, 153, 154, 155, 133, 128, 121, 120, 119, 118, 117, 111, 226], .03),
    'under_R': ([263, 249, 390, 373, 374, 380, 381, 382, 362, 357, 350, 349, 348, 347, 346, 340, 446], .03),
    'lid_L': ([70, 63, 105, 66, 107, 33, 246, 161, 160, 159, 158, 157, 173, 133], .02),
    'lid_R': ([300, 293, 334, 296, 336, 263, 466, 388, 387, 386, 385, 384, 398, 362], .02),
    'corner_L': ([33, 130, 226, 247, 113, 225, 46, 70, 124, 35], .05),
    'corner_R': ([263, 359, 446, 467, 342, 445, 276, 300, 353, 265], .05),
    'lip': ([61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146], .04),
    'cheek_L': ([116, 117, 118, 119, 100, 142, 203, 206, 216, 212, 214, 192, 213, 147, 123], .01),
    'cheek_R': ([345, 346, 347, 348, 329, 371, 423, 426, 436, 432, 434, 416, 433, 376, 352], .01),
    'jaw': ([172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 397, 288, 58, 132, 361], .03),
    'forehead': ([54, 103, 67, 109, 10, 338, 297, 332, 284, 293, 334, 296, 336, 9, 107, 66, 105, 63], .01),
}
SIDE_OK = {'front': lambda n: True, 'pos': lambda n: not n.endswith('_R'), 'neg': lambda n: not n.endswith('_L')}
_lock = threading.Lock(); _specs = None


def specs(model_dir: str) -> dict:
    global _specs
    with _lock:
        if _specs is None:
            _specs = {}
            for p in sorted(glob.glob(os.path.join(model_dir, 'findings-v2', '*.json'))):
                if os.path.basename(p) == 'REPORT.json':
                    continue
                s = json.load(open(p))
                if str(s.get('version', '')).startswith('skin-findings-v2-dino'):   # other families have their own modules
                    _specs[s['id']] = s
        return _specs


def crops_of(bgr: np.ndarray, landmarks_norm: list, view: str, needed: set) -> dict:
    import cv2
    h, w = bgr.shape[:2]; P = np.array([[p['x'] * w, p['y'] * h] for p in landmarks_norm], np.float64)
    fw = P[:, 0].max() - P[:, 0].min(); out = {}
    for name, (idx, pad) in CROPS.items():
        if name not in needed or not SIDE_OK[view](name) or max(idx) >= len(P):
            continue
        x0, y0 = P[idx].min(0) - pad * fw; x1, y1 = P[idx].max(0) + pad * fw
        c = bgr[int(max(0, y0)):int(y1), int(max(0, x0)):int(x1)]
        if c.size:
            out[name] = cv2.cvtColor(cv2.resize(c, (224, 224)), cv2.COLOR_BGR2RGB)
    return out


def _prob(folds: list, x: np.ndarray) -> float:
    ps = []
    for f in folds:
        z = (x - np.asarray(f['mean'])) / np.asarray(f['scale'])
        ps.append(1 / (1 + np.exp(-(float(np.asarray(f['coef']) @ z) + f['intercept']))))
    return float(np.mean(ps))


def photo_scores(bgr: np.ndarray, landmarks_norm: list, view: str, embedder, model_dir: str, check=lambda: None) -> dict:
    """{finding id: {crop: probability}} for this photo (numbers only)."""
    sp = specs(model_dir)
    if not sp or embedder is None:
        return {}
    needed = {c for s in sp.values() for c in s['crops']}
    crops = crops_of(bgr, landmarks_norm, view, needed)
    if not crops:
        return {}
    check(); names = list(crops); emb = dict(zip(names, embedder.embed([crops[n] for n in names])))
    return {fid: {c: round(_prob(s['folds'], emb[c]), 4) for c in s['crops'] if c in emb} for fid, s in sp.items()}


def manifest(model_dir: str) -> dict:
    import hashlib
    return {os.path.relpath(p, model_dir): hashlib.sha256(open(p, 'rb').read()).hexdigest()
            for p in sorted(glob.glob(os.path.join(model_dir, 'findings-v2', '**', '*.json'), recursive=True))
            if os.path.basename(p) != 'REPORT.json'}
