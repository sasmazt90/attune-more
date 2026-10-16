"""Compare stored model predictions with the frozen layer-1 point labels (protocol acne-point-relabel-protocol-1, scoring).

Inputs (all verified by sha256 before use): layer-1 JSON, layer-1 reviewed masks, MediaPipe landmarks (face oval), the DEV
pack manifest (source boxes, only for the label-agreement table), and stored final boxes: Step0 product-chain rows and the
36 third-party model/mode rows. Point = final box centre in source px. No inference here.

Scoring (fixed in the protocol before the review):
  r = 0.03 x face width (sensitivity 0.02 / 0.05); one-to-one TARGET vs prediction points, feasible if distance <= r,
  maximum cardinality then minimum total distance (linear_sum_assignment).
  Unmatched prediction -> first matching class: duplicate (within r of a matched TARGET) / other category (within r of
  MOLE, SCAR_PIGMENT, BLACKHEAD, PORE, OTHER) / uncertain (within r of UNCERTAIN) / false point on reviewed skin (inside the
  reviewed mask) / unreviewed (inside face oval, outside mask) / outside face oval.
  Declared handling (layer-1 deviation 1-2): on the 6 photos with an EMPTY reviewed mask (collage, close-up, blurred) the
  face oval does not describe the reviewed skin, so their unmatched points are reported as 'unreviewed photo', not as
  outside-oval/non-skin; their TARGET points still count.
"""
import json, hashlib, sys
from pathlib import Path
import numpy as np, cv2
from scipy.optimize import linear_sum_assignment

OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
OTHER = ('MOLE', 'SCAR_PIGMENT', 'BLACKHEAD', 'PORE', 'OTHER')
BIG = 1e6
CLASSES = ['duplicate', 'onOther', 'onUncertain', 'falseReviewed', 'unreviewedInOval', 'outsideOval', 'unreviewedPhoto']


def match(T, P, r):
    """One-to-one: maximum number of pairs with distance <= r, then minimum total distance. Returns [(ti, pj, d)]."""
    if not T or not P: return []
    T = np.asarray(T, float); P = np.asarray(P, float)
    D = np.hypot(T[:, None, 0] - P[None, :, 0], T[:, None, 1] - P[None, :, 1]); ok = D <= r
    C = np.where(ok, D - BIG, 0.)
    ri, ci = linear_sum_assignment(C)
    return [(int(i), int(j), float(D[i, j])) for i, j in zip(ri, ci) if ok[i, j]]


def near(p, pts, r):
    return any(np.hypot(p[0] - q[0], p[1] - q[1]) <= r for q in pts)


def inside(mask, p):
    x, y = int(p[0]), int(p[1])
    return mask is not None and 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1] and bool(mask[y, x])


def oval_mask(lm, w, h):
    P = np.array([[l['x'] * w, l['y'] * h] for l in lm['landmarks']], np.float32)
    m = np.zeros((h, w), np.uint8); cv2.fillPoly(m, [np.round(P[OVAL]).astype(np.int32)], 255); return m > 0


def score_photo(lab, preds, mask, oval, r):
    pts = lab['points']; T = [(p['x'], p['y']) for p in pts if p['cat'] == 'TARGET']; tid = [p['id'] for p in pts if p['cat'] == 'TARGET']
    U = [(p['x'], p['y']) for p in pts if p['cat'] == 'UNCERTAIN']
    O = {c: [(p['x'], p['y']) for p in pts if p['cat'] == c] for c in OTHER}
    P = [((b[0] + b[2]) / 2., (b[1] + b[3]) / 2.) for b in preds]
    m = match(T, P, r); used = {j for _, j, _ in m}; hitT = {i for i, _, _ in m}
    empty = mask is None or not mask.any()
    cls = []
    for j, p in enumerate(P):
        if j in used: cls.append('matched'); continue
        if near(p, [T[i] for i in hitT], r): cls.append('duplicate'); continue
        oc = next((c for c in OTHER if near(p, O[c], r)), None)
        if oc: cls.append('onOther:' + oc); continue
        if near(p, U, r): cls.append('onUncertain'); continue
        if empty: cls.append('unreviewedPhoto'); continue
        if inside(mask, p): cls.append('falseReviewed'); continue
        cls.append('unreviewedInOval' if inside(oval, p) else 'outsideOval')
    return dict(targets=len(T), hits=len(m), hitIds=[tid[i] for i in sorted(hitT)], dist=[d for _, _, d in m], classes=cls, points=P)


def summarize(per, r_key):
    s = dict(targets=0, hits=0, preds=0, **{c: 0 for c in CLASSES}, onOtherByCat={})
    for ph, v in per.items():
        x = v[r_key]; s['targets'] += x['targets']; s['hits'] += x['hits']; s['preds'] += len(x['classes'])
        for c in x['classes']:
            if c == 'matched': continue
            if c.startswith('onOther:'):
                s['onOther'] += 1; k = c.split(':')[1]; s['onOtherByCat'][k] = s['onOtherByCat'].get(k, 0) + 1
            else: s[c] += 1
    return s


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(layer1_path, mask_dir, landmark_files, records, layer1_sha):
    assert sha(layer1_path) == layer1_sha, 'LAYER1_HASH'
    L1 = json.load(open(layer1_path))['photos']; lm = {}
    for f in landmark_files:
        for l in open(f): r = json.loads(l); lm[r['sha256']] = r
    masks, ovals = {}, {}
    for ph, v in L1.items():
        f = Path(mask_dir) / f'{ph}.png'; assert sha(f) == v['mask']['sha256'], ('MASK_HASH', ph)
        mk = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE) > 0; masks[ph] = mk
        r = lm[v['sha256']]; ovals[ph] = oval_mask(r, r['width'], r['height']); assert ovals[ph].shape == mk.shape
    out = {}
    for key, rows in records.items():
        by = {r['sha']: r for r in rows}; per = {}
        for ph, v in L1.items():
            preds = [b[:4] for b in by[v['sha256']]['final']]; fw = v['faceWidthPx']
            per[ph] = {f'r{k}': score_photo(v, preds, masks[ph], ovals[ph], k / 100. * fw) for k in (2, 3, 5)}
        out[key] = dict(perPhoto=per, summary={k: summarize(per, k) for k in ('r2', 'r3', 'r5')})
    return out, L1, masks, ovals
