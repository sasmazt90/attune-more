"""Informational only (does not change the saved models): thr_prev on all-person OOF scores for split seeds 100..109."""
import json, sys, collections, numpy as np
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.argv = ['x', '/dev/null']
src = open(f'{S}/v2/export_eye.py').read().split('summary = {}')[0]
src = src.replace("print(", "(lambda *a, **k: None)(")
exec(src)
from sklearn.model_selection import StratifiedKFold
out = {}
Xd = X
for fid, (lab_, (ca, cb), *_r) in FAIR.items():
    y = np.array([lab_ in st[k]['extras'] for k in ks]); XX = np.array([np.concatenate([geo(k), emb(k, ca, cb)]) for k in ks], float); ts = []
    for seed in range(100, 110):
        oof = np.zeros(len(ks))
        for ia, ib in StratifiedKFold(5, shuffle=True, random_state=seed).split(XX, y):
            oof[ib] = model(XX.shape[1]).fit(XX[ia], y[ia]).predict_proba(XX[ib])[:, 1]
        ts.append(thr_prev(y, oof))
    out[fid] = ts
out['darkCircles'] = [thr_prev(yp, oof_scores(persons, yp, srcs, s)) for s in range(100, 110)]
print(json.dumps({k: [None if t is None else round(t, 3) for t in v] for k, v in out.items()}))
