"""Acne point evaluation (protocol docs/acne-point-eval-protocol-20261016.json, fixed before results).

Uses ONLY stored final boxes (source px): external-results.json rows and the Step0 product-chain rows (infer-step0.jsonl).
Point = box centre. Primary: point inside labelled box, one-to-one, maximum cardinality then minimum total normalized distance.
Secondary: normalized centre distance <= .25 / .50 (same assignment). IoU .50/.30 recomputed with the earlier greedy matcher.
False points only inside reviewed masks (clean ROI on positive photos, Clear mask on negatives); everything else UNKNOWN.
"""
import json, statistics as st
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment

BIG = 1e6


def centre(b): return ((b[0] + b[2]) / 2., (b[1] + b[3]) / 2.)


def dnorm(p, t):
    c = centre(t); diag = max(1e-9, ((t[2] - t[0]) ** 2 + (t[3] - t[1]) ** 2) ** .5)
    return ((p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2) ** .5 / diag


def inside(p, t): return t[0] <= p[0] <= t[2] and t[1] <= p[1] <= t[3]


def assign(T, P, feasible):
    """One-to-one: max number of feasible pairs, then min total normalized distance. Returns [(ti, pj, d)]."""
    if not T or not P: return []
    C = np.zeros((len(T), len(P)))
    ok = np.zeros_like(C, bool)
    for i, t in enumerate(T):
        for j, p in enumerate(P):
            if feasible(p, t): ok[i, j] = True; C[i, j] = dnorm(p, t) - BIG
    r, c = linear_sum_assignment(C)
    return [(int(i), int(j), float(C[i, j] + BIG)) for i, j in zip(r, c) if ok[i, j]]


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i; return i / u if u > 0 else 0.


def o2o_iou(T, F, thr):
    pr = sorted(((iou(t, p), i, j) for i, t in enumerate(T) for j, p in enumerate(F)), reverse=True); ut, up, m = set(), set(), []
    for v, i, j in pr:
        if v < thr: break
        if i in ut or j in up: continue
        ut.add(i); up.add(j); m.append((i, j))
    return m


def evaluate(rows, man, maskdir, read_mask):
    """rows: [{sha, final:[[x1,y1,x2,y2,score],...], sec}] ; man: pack manifest items. Returns summary + per-target + per-photo records."""
    by = {r['sha']: r for r in rows}; S = dict(targets=0, point=0, small=0, smallPoint=0, medium=0, mediumPoint=0, tol25=0, tol50=0, iou50=0, iou30=0,
                                              final=0, unknown=0, duplicates=0, conflicts=0, roiFP=0, roiPx=0, clearFP=0, clearPx=0)
    per_target, roi_pp, clear_pp, dist, gained_vs_iou50 = [], [], [], [], []
    for it in man:
        r = by[it['sha256']]; F = [b[:4] for b in r['final']]; Pts = [centre(b) for b in F]
        if it['kind'] == 'negative-photo':
            m = read_mask(maskdir / it['negMask']); c = sum(1 for p in Pts if 0 <= int(p[1]) < m.shape[0] and 0 <= int(p[0]) < m.shape[1] and m[int(p[1]), int(p[0])])
            S['clearFP'] += c; S['clearPx'] += int(m.sum()); clear_pp.append(dict(photo=it['sha256'][:12], falsePoints=c, points=len(Pts))); continue
        T = it['positive']; S['targets'] += len(T); S['final'] += len(F)
        prim = assign(T, Pts, lambda p, t: inside(p, t)); hit = {i: (j, d) for i, j, d in prim}
        t25 = {i for i, _, _ in assign(T, Pts, lambda p, t: dnorm(p, t) <= .25)}; t50 = {i for i, _, _ in assign(T, Pts, lambda p, t: dnorm(p, t) <= .50)}
        i50 = {i for i, _ in o2o_iou(T, F, .5)}; i30 = {i for i, _ in o2o_iou(T, F, .3)}
        S['point'] += len(prim); S['tol25'] += len(t25); S['tol50'] += len(t50); S['iou50'] += len(i50); S['iou30'] += len(i30)
        used = {j for _, j, _ in prim}
        for i, t in enumerate(T):
            sm = max(t[2] - t[0], t[3] - t[1]) < 16; S['small' if sm else 'medium'] += 1
            if i in hit: S['smallPoint' if sm else 'mediumPoint'] += 1; dist.append(hit[i][1])
            if i in hit and i not in i50: gained_vs_iou50.append(f"{it['sha256'][:12]}#{i}")
            per_target.append(dict(target=f"{it['sha256'][:12]}#{i}", sidePx=round(max(t[2] - t[0], t[3] - t[1]), 1), small=sm, pointHit=i in hit,
                                   pred=hit[i][0] if i in hit else None, dNorm=round(hit[i][1], 3) if i in hit else None, tol25=i in t25, tol50=i in t50, iou50=i in i50, iou30=i in i30))
        m = read_mask(maskdir / it['roiMask']) if 'roiMask' in it else None; fp = 0
        for j, p in enumerate(Pts):
            if j in used: continue
            if any(inside(p, T[i]) for i in hit): S['duplicates'] += 1; continue      # second point on an already found lesion
            inm = m is not None and 0 <= int(p[1]) < m.shape[0] and 0 <= int(p[0]) < m.shape[1] and m[int(p[1]), int(p[0])]
            if inm and any(inside(p, t) for t in T): S['conflicts'] += 1; S['unknown'] += 1; continue
            if inm: fp += 1
            else: S['unknown'] += 1
        if m is not None: S['roiFP'] += fp; S['roiPx'] += int(m.sum()); roi_pp.append(dict(photo=it['sha256'][:12], falsePoints=fp))
    S['medianDNormMatched'] = round(st.median(dist), 3) if dist else None
    S['roiPhotos'] = len(roi_pp); S['clearPhotos'] = len(clear_pp)
    S['roiFPperPhoto'] = round(S['roiFP'] / max(1, len(roi_pp)), 3); S['clearFPperPhoto'] = round(S['clearFP'] / max(1, len(clear_pp)), 3)
    S['medianSec'] = round(st.median(r['sec'] for r in rows), 3)
    return S, per_target, roi_pp, clear_pp, gained_vs_iou50
