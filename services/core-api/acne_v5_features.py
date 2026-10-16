"""Frozen 1920 feature contract, selected from research cb0948fa; NumPy only."""
import math
import numpy as np
STRIDES=(4,8,16,32)
CTX=2
VERSION="acne-candidate-verifier-features-v1"

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
