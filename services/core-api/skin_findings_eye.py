"""Saved eye-area finding classifiers (models/<bundle>/findings-v2/{darkCircles,hoodedEyelids,downturnedCorners}.json),
re-fitted with the exact research recipes by v2/export_eye.py (research/skin-findings/scripts/eye_grid3.py and
eye_fair3.py; see CODEX_HANDOFF.md section 6). FRONT photo only; region 'periorbital' for all three.

Features (same computation as research, ported to numpy + cv2):
* darkCircles   - light-corrected colour comparison (research light.py + eye_pose.py): per eye, the under-eye band
                  (below the lower lid) vs the same-side cheek in the lighting-corrected image, Lab; the darkest 40 % of
                  the band. [log(Lc / (Lc - dL)), da, db] averaged over the eyes that can be read, + pose one-hot
                  [front=1, side=0]. Needs the MediaPipe z coordinate (surface normals); without z -> no score.
* hoodedEyelids - 7 roll-normalised landmark geometry values (research sag_geo.py) + mean of the DINOv2 lid_L / lid_R
                  crop embeddings (CLS + mean patch, 768).
* downturnedCorners - same geometry + mean of the DINOv2 corner_L / corner_R crop embeddings.
Model = StandardScaler [+ PCA(20)] + LogisticRegression, stored as plain numbers; probability computed in numpy.
Decision: 'seen' when probability >= the saved threshold (thr_prev rule, see the JSON), otherwise 'notSeen'."""
from __future__ import annotations
import glob, hashlib, json, os, threading
import numpy as np

FINDINGS = ('darkCircles', 'hoodedEyelids', 'downturnedCorners')
VERSION_PREFIX = 'skin-findings-v2-eye'
REGION = 'periorbital'

# crop indices / padding (fraction of face width): research/skin-findings/scripts/finding_clf.py CROPS
CROPS = {
    'under_L': ([33, 7, 163, 144, 145, 153, 154, 155, 133, 128, 121, 120, 119, 118, 117, 111, 226], .03),
    'under_R': ([263, 249, 390, 373, 374, 380, 381, 382, 362, 357, 350, 349, 348, 347, 346, 340, 446], .03),
    'lid_L': ([70, 63, 105, 66, 107, 33, 246, 161, 160, 159, 158, 157, 173, 133], .02),
    'lid_R': ([300, 293, 334, 296, 336, 263, 466, 388, 387, 386, 385, 384, 398, 362], .02),
    'corner_L': ([33, 130, 226, 247, 113, 225, 46, 70, 124, 35], .05),
    'corner_R': ([263, 359, 446, 467, 342, 445, 276, 300, 353, 265], .05),
}
# geometry: research sag_geo.py
EYE = {'L': dict(inner=133, outer=33, up=159, lo=145, brow=105, crease=27),
       'R': dict(inner=362, outer=263, up=386, lo=374, brow=334, crease=257)}
GEO_ORDER = ('tilt', 'aperture', 'brow_lid', 'crease_lid', 'mouth_corner_drop', 'cheek_low', 'jaw_width_ratio')
# colour: research light.py SKIN polygons + eye_pose.py lower-lid band
SKIN = {'forehead': [54, 103, 67, 109, 10, 338, 297, 332, 284, 293, 334, 296, 336, 9, 107, 66, 105, 63],
        'nose': [168, 193, 245, 188, 174, 236, 198, 209, 49, 48, 64, 98, 97, 2, 326, 327, 294, 278, 279, 429, 420, 456, 399, 412, 465, 417],
        'cheek_imgL': [116, 117, 118, 119, 100, 142, 203, 206, 216, 212, 214, 192, 213, 147, 123],
        'cheek_imgR': [345, 346, 347, 348, 329, 371, 423, 426, 436, 432, 434, 416, 433, 376, 352],
        'chin': [43, 106, 182, 83, 18, 313, 406, 335, 273, 422, 430, 394, 395, 369, 396, 175, 171, 140, 170, 169, 210, 202]}
LID = {'L': [33, 7, 163, 144, 145, 153, 154, 155, 133], 'R': [263, 249, 390, 373, 374, 380, 381, 382, 362]}
CHEEK = {'L': 'cheek_imgL', 'R': 'cheek_imgR'}

_lock = threading.Lock(); _cache: dict = {}


# ----------------------------------------------------------------------------------------------- model files
def specs(model_dir: str) -> dict:
    with _lock:
        if model_dir not in _cache:
            out = {}
            for fid in FINDINGS:
                p = os.path.join(model_dir, 'findings-v2', f'{fid}.json')
                if os.path.exists(p):
                    s = json.load(open(p))
                    if str(s.get('version', '')).startswith(VERSION_PREFIX):
                        out[fid] = s
            _cache[model_dir] = out
        return _cache[model_dir]


SEVERITY_FILES = ('severity_geo/downturnedCorners.json',)


def manifest(model_dir: str) -> dict:
    names = [f'{fid}.json' for fid in FINDINGS] + list(SEVERITY_FILES)
    return {f'findings-v2/{n}': hashlib.sha256(open(os.path.join(model_dir, 'findings-v2', n), 'rb').read()).hexdigest()
            for n in names if os.path.exists(os.path.join(model_dir, 'findings-v2', n))}


def _severity_geo(model_dir: str):
    with _lock:
        key = ('sev', model_dir)
        if key not in _cache:
            p = os.path.join(model_dir, 'findings-v2', 'severity_geo', 'downturnedCorners.json')
            _cache[key] = json.load(open(p)) if os.path.exists(p) else None
        return _cache[key]


def downturned_percentile(bgr: np.ndarray, landmarks_norm: list, model_dir: str | None = None, view: str = 'front') -> float | None:
    """Geometry percentile among positives, NOT validated against ratings: midrank percentile of this person's
    downturn (= -sag_geo 'tilt', mean of both eyes) within the saved distribution of persons labelled
    'sarkma: göz dış köşe'; 100 = most downturned. Front photo only; None if unavailable."""
    if view != 'front' or not landmarks_norm or len(landmarks_norm) < 468:
        return None
    if model_dir is None:
        model_dir = os.environ.get('ATTUNE_REGIONAL_V3_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'regional-skin-v3'))
    sp = _severity_geo(model_dir)
    if not sp:
        return None
    h, w = bgr.shape[:2]; d = -float(geometry(landmarks_norm, w, h)[GEO_ORDER.index('tilt')])
    v = np.asarray(sp['sortedDownturn'], np.float64)
    return round(float(100.0 * ((v < d).sum() + 0.5 * (v == d).sum()) / len(v)), 1)


def predict_proba(spec: dict, x: np.ndarray) -> float:
    """StandardScaler -> (PCA) -> LogisticRegression, exactly as sklearn's predict_proba[:, 1]."""
    m = spec['model']; z = (np.asarray(x, np.float64) - np.asarray(m['scaler']['mean'])) / np.asarray(m['scaler']['scale'])
    if m.get('pca'):
        z = (z - np.asarray(m['pca']['mean'])) @ np.asarray(m['pca']['components']).T
    s = float(np.asarray(m['lr']['coef']) @ z + m['lr']['intercept'])
    return float(1.0 / (1.0 + np.exp(-s)))


def decide(prob: float, spec: dict) -> str:
    return 'seen' if float(prob) >= float(spec['threshold']) else 'notSeen'


# ----------------------------------------------------------------------------------------------- features
def _pts(landmarks_norm: list, w: int, h: int) -> np.ndarray:
    return np.array([[p['x'] * w, p['y'] * h] for p in landmarks_norm], np.float64)


def geometry(landmarks_norm: list, w: int, h: int) -> np.ndarray:
    """research sag_geo.py: eye geometry in the roll-normalised frame (both eyes averaged) + 3 midface values."""
    P = _pts(landmarks_norm, w, h)
    c = (P[33] + P[263]) / 2; v = P[263] - P[33]; ang = np.arctan2(v[1], v[0])
    R = np.array([[np.cos(-ang), -np.sin(-ang)], [np.sin(-ang), np.cos(-ang)]]); Q = (P - c) @ R.T
    iod = np.linalg.norm(v); f: dict = {}
    for e in EYE.values():
        ew = abs(Q[e['outer'], 0] - Q[e['inner'], 0])
        f.setdefault('tilt', []).append((Q[e['inner'], 1] - Q[e['outer'], 1]) / ew)
        f.setdefault('aperture', []).append((Q[e['lo'], 1] - Q[e['up'], 1]) / ew)
        f.setdefault('brow_lid', []).append((Q[e['up'], 1] - Q[e['brow'], 1]) / ew)
        f.setdefault('crease_lid', []).append((Q[e['up'], 1] - Q[e['crease'], 1]) / ew)
    f = {k: float(np.mean(v_)) for k, v_ in f.items()}
    f['mouth_corner_drop'] = float(((Q[61, 1] + Q[291, 1]) / 2 - Q[0, 1]) / iod)
    f['cheek_low'] = float(((Q[205, 1] + Q[425, 1]) / 2) / iod)
    f['jaw_width_ratio'] = float(abs(Q[172, 0] - Q[397, 0]) / abs(Q[234, 0] - Q[454, 0]))
    return np.array([f[k] for k in GEO_ORDER])


def crops(bgr: np.ndarray, landmarks_norm: list, names) -> dict:
    """research eye_fair3.py crops: landmark bbox + pad * face width (all points), resized to 224, RGB uint8."""
    import cv2
    h, w = bgr.shape[:2]; P = _pts(landmarks_norm, w, h); fw = P[:, 0].max() - P[:, 0].min(); out = {}
    for n in names:
        idx, pad = CROPS[n]
        x0, y0 = P[idx].min(0) - pad * fw; x1, y1 = P[idx].max(0) + pad * fw
        c = bgr[int(max(0, y0)):int(y1), int(max(0, x0)):int(x1)]
        if c.size:
            out[n] = cv2.cvtColor(cv2.resize(c, (224, 224)), cv2.COLOR_BGR2RGB)
    return out


# --- light correction (research light.py analyze/fit/lab/region_masks), scipy-free -------------------------------
def _delaunay(P2: np.ndarray, W: int, H: int) -> np.ndarray:
    import cv2
    lo = np.floor(P2.min(0)) - 2; hi = np.ceil(P2.max(0)) + 2
    sub = cv2.Subdiv2D((int(lo[0]), int(lo[1]), int(hi[0] - lo[0]), int(hi[1] - lo[1])))
    pf = P2.astype(np.float32); key = {(float(a), float(b)): i for i, (a, b) in enumerate(pf)}
    for a, b in pf:
        sub.insert((float(a), float(b)))
    tris = []
    for t in sub.getTriangleList():
        ids = [key.get((float(np.float32(t[2 * j])), float(np.float32(t[2 * j + 1])))) for j in range(3)]
        if None not in ids:
            tris.append(ids)
    return np.array(_fill_hull(tris, P2), np.int64)


def _fill_hull(tris: list, P2: np.ndarray) -> list:
    """cv2.Subdiv2D can omit thin triangles on the convex hull (its outer virtual vertices sit inside their
    circumcircles). Fill each pocket between a hull edge and the mesh boundary with Delaunay triangles (vertex with
    the largest subtended angle, recursively), which gives the same mesh as scipy/qhull."""
    import cv2
    tris = [list(t) for t in tris]
    hull = cv2.convexHull(P2.astype(np.float32), clockwise=False, returnPoints=False).ravel().tolist()
    cnt: dict = {}
    for t in tris:
        for e in ((t[0], t[1]), (t[1], t[2]), (t[0], t[2])):
            e = tuple(sorted(e)); cnt[e] = cnt.get(e, 0) + 1
    nb: dict = {}
    for (a, b), c in cnt.items():
        if c == 1:
            nb.setdefault(a, []).append(b); nb.setdefault(b, []).append(a)

    def chain(a, b):
        best = None
        for first in nb.get(a, []):
            path = [a, first]; seen = {a, first}
            while path[-1] != b and len(path) < len(P2):
                nxt = [v for v in nb.get(path[-1], []) if v not in seen]
                if not nxt:
                    break
                path.append(nxt[0]); seen.add(nxt[0])
            if path[-1] == b and (best is None or len(path) < len(best)):
                best = path
        return best

    def angle(a, k, b):
        u = P2[a] - P2[k]; v = P2[b] - P2[k]
        return np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-12), -1, 1))

    def fill(ch):
        if len(ch) < 3:
            return
        a, b = ch[0], ch[-1]; i = 1 + int(np.argmax([angle(a, k, b) for k in ch[1:-1]]))
        tris.append([a, ch[i], b]); fill(ch[:i + 1]); fill(ch[i:])

    for a, b in zip(hull, hull[1:] + hull[:1]):
        if tuple(sorted((a, b))) in cnt:
            continue
        ch = chain(a, b)
        if ch is not None:
            fill(ch)
    return tris


def _normals_map(P3: np.ndarray, shape) -> tuple:
    """Per-vertex normals of the Delaunay mesh, linearly interpolated per pixel inside the hull (as scipy's
    LinearNDInterpolator on the same triangulation)."""
    H, W = shape; F = _delaunay(P3[:, :2], W, H)
    v0, v1, v2 = P3[F[:, 0]], P3[F[:, 1]], P3[F[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0); fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-9
    fn[fn[:, 2] < 0] *= -1
    vn = np.zeros_like(P3)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-9
    N = np.zeros((H, W, 3)); valid = np.zeros((H, W), bool); xy = P3[:, :2]
    for t in F:
        a, b, c = xy[t]
        x0, x1 = max(0, int(np.ceil(min(a[0], b[0], c[0])))), min(W - 1, int(np.floor(max(a[0], b[0], c[0]))))
        y0, y1 = max(0, int(np.ceil(min(a[1], b[1], c[1])))), min(H - 1, int(np.floor(max(a[1], b[1], c[1]))))
        if x1 < x0 or y1 < y0:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        T = np.array([[a[0] - c[0], b[0] - c[0]], [a[1] - c[1], b[1] - c[1]]]); det = np.linalg.det(T)
        if abs(det) < 1e-12:
            continue
        Ti = np.linalg.inv(T); dx = xs - c[0]; dy = ys - c[1]
        l1 = Ti[0, 0] * dx + Ti[0, 1] * dy; l2 = Ti[1, 0] * dx + Ti[1, 1] * dy; l3 = 1 - l1 - l2
        eps = 1e-10; m = (l1 >= -eps) & (l2 >= -eps) & (l3 >= -eps)
        if not m.any():
            continue
        L = np.stack([l1[m], l2[m], l3[m]], 1)
        N[ys[m], xs[m]] = L @ vn[t]; valid[ys[m], xs[m]] = True
    N[~valid] = 0
    N /= np.linalg.norm(N, axis=-1, keepdims=True) + 1e-9
    return N, valid


def _robust_fit(A, y, iters=8, c=1.5):
    w = np.ones(len(y))
    for _ in range(iters):
        sw = np.sqrt(w); k, *_ = np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)
        r = y - A @ k; s = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-6
        u = np.abs(r) / (c * s); w = np.where(u <= 1, 1.0, 1.0 / u)
    return k


def _lab(rgb_lin):
    import cv2
    srgb = np.where(rgb_lin <= 0.0031308, rgb_lin * 12.92, 1.055 * np.power(np.clip(rgb_lin, 0, 1), 1 / 2.4) - 0.055)
    L = cv2.cvtColor((np.clip(srgb, 0, 1) * 255).astype(np.uint8)[..., ::-1], cv2.COLOR_BGR2LAB).astype(np.float32)
    return L[..., 0] * 100 / 255, L[..., 1] - 128, L[..., 2] - 128


def light_analyze(bgr: np.ndarray, landmarks_norm: list, scale_to: int = 400) -> dict:
    import cv2
    h, w = bgr.shape[:2]
    P = np.array([[q['x'] * w, q['y'] * h, q['z'] * w] for q in landmarks_norm[:468]], np.float64)
    fw = P[:, 0].max() - P[:, 0].min(); sc = scale_to / fw
    x0, y0 = P[:, 0].min() - 0.15 * fw, P[:, 1].min() - 0.15 * fw
    P[:, 0] -= x0; P[:, 1] -= y0; P *= sc
    W = int(P[:, 0].max() + 0.15 * scale_to); H = int(P[:, 1].max() + 0.15 * scale_to)
    M = np.float32([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]])
    im = cv2.warpAffine(bgr, M, (W, H), flags=cv2.INTER_AREA).astype(np.float32) / 255
    lin = np.where(im <= 0.04045, im / 12.92, ((im + 0.055) / 1.055) ** 2.4)
    N, nvalid = _normals_map(P, (H, W))
    sk = np.zeros((H, W), np.uint8)
    for v in SKIN.values():
        cv2.fillPoly(sk, [P[v, :2].astype(np.int32)], 1)
    skin = (sk > 0) & nvalid
    img = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.clip(lin, 0, 1), 1 / 2.4) - 0.055)
    usable = skin & (img.max(-1) < 0.97) & (lin.mean(-1) > 0.01)
    A1 = np.concatenate([np.ones((H, W, 1)), N], -1); A = A1[usable]
    S = np.zeros_like(lin)
    for ch in range(3):
        S[..., ch] = A1 @ _robust_fit(A, lin[..., ch][usable])
    S = np.clip(S, 1e-3, None); ref = np.median(S[usable], 0)
    corr = np.clip(lin / S * ref, 0, 1)
    return dict(img=img, lin=lin, corr=corr, usable=usable, P=P, skin=skin)


def colour(bgr: np.ndarray, landmarks_norm: list):
    """research eye_pose.py colour comparison for the front photo: mean over readable eyes of
    [log(Lc / max(Lc - dL, 1e-3)), da, db]. None if z is missing or no eye can be read."""
    import cv2
    if len(landmarks_norm) < 468 or any(not isinstance(q.get('z'), (int, float)) for q in landmarks_norm[:468]):
        return None
    R = light_analyze(bgr, landmarks_norm); P2 = R['P'][:, :2]; Hh, Ww = R['skin'].shape; fws = P2[:, 0].max() - P2[:, 0].min()
    L_, a_, b_ = _lab(R['corr'][..., ::-1]); rows = []
    for s in ('L', 'R'):
        ck = np.zeros((Hh, Ww), np.uint8); cv2.fillPoly(ck, [P2[SKIN[CHEEK[s]]].astype(np.int32)], 1); ck = (ck > 0) & R['usable']
        lid = P2[LID[s]]; band = np.concatenate([lid + [0, 0.012 * fws], (lid + [0, 0.10 * fws])[::-1]])
        m = np.zeros((Hh, Ww), np.uint8); cv2.fillPoly(m, [band.astype(np.int32)], 1)
        ue = (m > 0) & (R['img'].max(-1) < 0.97) & (R['lin'].mean(-1) > 0.01)
        if ue.sum() < 30 or ck.sum() < 30:
            continue
        Lu = L_[ue]; q = Lu <= np.percentile(Lu, 40); Lc = np.median(L_[ck]); dL = Lc - np.median(Lu[q])
        rows.append([np.log(Lc / max(Lc - dL, 1e-3)), np.median(a_[ue][q]) - np.median(a_[ck]), np.median(b_[ue][q]) - np.median(b_[ck])])
    return np.mean(np.array(rows, np.float64), 0) if rows else None


def features(bgr: np.ndarray, landmarks_norm: list, embedder, need=FINDINGS) -> dict:
    """{finding id: feature vector in the saved order} for the findings that can be computed on this photo."""
    h, w = bgr.shape[:2]; out = {}
    if len(landmarks_norm) < 468:
        return out
    if 'darkCircles' in need:
        c = colour(bgr, landmarks_norm)
        if c is not None:
            out['darkCircles'] = np.concatenate([c, [1.0, 0.0]])          # pose one-hot: front
    dino = {'hoodedEyelids': ('lid_L', 'lid_R'), 'downturnedCorners': ('corner_L', 'corner_R')}
    want = [n for fid, ns in dino.items() if fid in need for n in ns]
    if want and embedder is not None:
        cr = crops(bgr, landmarks_norm, want)
        if all(n in cr for n in want):
            names = list(cr); emb = dict(zip(names, np.asarray(embedder.embed([cr[n] for n in names]), np.float64)))
            g = geometry(landmarks_norm, w, h)
            for fid, (a, b) in dino.items():
                if fid in need:
                    out[fid] = np.concatenate([g, (emb[a] + emb[b]) / 2])
    return out


def photo_scores(bgr: np.ndarray, landmarks_norm: list, view: str, embedder, model_dir: str) -> dict:
    """{finding id: probability} for the FRONT photo; {} for any other view or when the models are missing.
    A finding whose features cannot be computed (no z for darkCircles, no embedder for the DINOv2 ones, eye band too
    small) is omitted, so the caller reports it as unmeasured rather than 'notSeen'."""
    if view != 'front' or not landmarks_norm:
        return {}
    sp = specs(model_dir)
    if not sp:
        return {}
    X = features(bgr, landmarks_norm, embedder, need=tuple(sp))
    return {fid: round(predict_proba(sp[fid], x), 4) for fid, x in X.items()}
