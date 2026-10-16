"""Acne candidate verifier (offline research/staging; not connected to the product; acne stays accepted:false, file:null).

Second stage on FIXED Step0 candidates: Step0 weights, BatchNorm, detector scores, candidate generation (product photo_input
crop, native tiles, conf .30, NMS .30, current product masks, unchanged staging box filter) are untouched. Features are read
from the frozen PAFPN outputs of the same tile forward pass that produced each candidate; a standardised L2 logistic
regression decides keep/reject. Protocol: docs/acne-verifier-protocol-20261016.json.

Feature vector (frozen, 1920 dims): for each PAFPN level (strides 4, 8, 16, 32; 64/128/256/512 channels) the bilinear sample at
the candidate centre in tile coordinates (cell centres at (i + .5) * stride) and the mean over cells within +-2 cells of the
nearest cell (clipped to the map). No detector score, no box size, no colour statistic.
"""
import base64, hashlib, json, math, time
from pathlib import Path
import numpy as np

STRIDES = (4, 8, 16, 32)
CTX = 2
VERSION = 'acne-candidate-verifier-features-v1'


def level_features(fmap, u, v, stride):
    """fmap: (C, H, W) float32 numpy; (u, v): tile-local source px. Returns centre bilinear sample and +-CTX cell mean."""
    C, H, W = fmap.shape
    gx, gy = u / stride - .5, v / stride - .5
    gx = min(max(gx, 0.), W - 1.); gy = min(max(gy, 0.), H - 1.)
    x0, y0 = int(math.floor(gx)), int(math.floor(gy)); x1, y1 = min(x0 + 1, W - 1), min(y0 + 1, H - 1); ax, ay = gx - x0, gy - y0
    centre = (fmap[:, y0, x0] * (1 - ax) * (1 - ay) + fmap[:, y0, x1] * ax * (1 - ay) + fmap[:, y1, x0] * (1 - ax) * ay + fmap[:, y1, x1] * ax * ay)
    cx, cy = int(round(gx)), int(round(gy))
    ctx = fmap[:, max(0, cy - CTX):min(H, cy + CTX + 1), max(0, cx - CTX):min(W, cx + CTX + 1)].mean(axis=(1, 2))
    return np.concatenate([centre, ctx]).astype(np.float32)


def candidate_features(maps, u, v):
    return np.concatenate([level_features(m, u, v, s) for m, s in zip(maps, STRIDES)])


def run_chain_with_features(net, bgr, rp):
    """Exactly eval_acne_v5_independent.plan + infer (same calls and order), observing the PAFPN outputs per tile.
    Returns dict(status, rects, final[[x1,y1,x2,y2,score]], tiles[i], features (N, 1920), timings)."""
    import cv2, torch
    import eval_acne_v5_independent as v5
    from acne_takeover_support import infer_tiles, current_product_masks
    from acne_box_support_staging import principled_accepted_boxes
    pl = v5.plan(bgr, rp); out = dict(status=pl['status'], rects=pl['rects'], final=[], tiles=[], features=np.zeros((0, 1920), np.float32))
    if not pl['rects'] or not rp.get('snapshot'): return out
    maps = []; h = net.backbone.register_forward_hook(lambda m, i, o: maps.append([t[0].detach().numpy().copy() for t in o]))
    t0 = time.perf_counter()
    try: raw, trace = infer_tiles(net, bgr, pl['rects'])
    finally: h.remove()
    t1 = time.perf_counter()
    snap = rp['snapshot']; pid = hashlib.sha256(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA).tobytes()).hexdigest(); ok, png = cv2.imencode('.png', bgr)
    payload = dict(photo='data:image/png;base64,' + base64.b64encode(png.tobytes()).decode(), photoId=pid, landmarks=rp['landmarks'], meshes=snap['meshes'],
                   exclusions=snap['exclusions'], qualityValid=rp['quality']['isValid'], conditions=dict(yaw=0, pitch=0, roll=0, scaleRatio=0))
    masks = current_product_masks(payload)
    assigned, _ = principled_accepted_boxes(raw, masks['acne_envelopes'], masks['acne_skin'], masks['hair'], masks['acne_exclusion'], pid, masks['scale'], masks['origin'],
                                            visible_regions=list(snap['meshes']), landmarks=rp['landmarks'], source_shape=bgr.shape[:2], bgr=bgr)
    final = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height'], b.get('confidence')] for v in assigned.values() for b in v]
    t2 = time.perf_counter()
    tile_of = {tuple(round(x, 4) for x in c['box']) + (round(c['confidence'], 6),): c['tile'] for c in trace['confidenceCandidates']}
    feats, tiles = [], []
    for b in final:
        k = tuple(round(x, 4) for x in b[:4]) + (round(b[4], 6),); t = tile_of[k]; a, bb = pl['rects'][t][:2]
        feats.append(candidate_features(maps[t], (b[0] + b[2]) / 2 - a, (b[1] + b[3]) / 2 - bb)); tiles.append(t)
    t3 = time.perf_counter()
    out.update(final=final, tiles=tiles, features=np.stack(feats) if feats else out['features'], inferSec=t1 - t0, chainSec=t2 - t0, featureSec=t3 - t2,
               featureBytes=int(sum(m.nbytes for mm in maps for m in mm)))
    return out


class Verifier:
    """Frozen standardiser + logistic regression + threshold, loaded from verifier.json (no pickle)."""
    def __init__(self, path):
        d = json.loads(Path(path).read_text()); self.meta = d
        self.mean = np.asarray(d['standardizer']['mean'], np.float64); self.scale = np.asarray(d['standardizer']['scale'], np.float64)
        self.coef = np.asarray(d['model']['coef'], np.float64); self.intercept = float(d['model']['intercept']); self.threshold = float(d['threshold'])
        assert d['featureVersion'] == VERSION and self.coef.shape[0] == 1920

    def proba(self, X):
        z = ((np.asarray(X, np.float64) - self.mean) / self.scale) @ self.coef + self.intercept
        return 1. / (1. + np.exp(-z))

    def keep(self, X):
        return self.proba(X) >= self.threshold if len(X) else np.zeros(0, bool)
