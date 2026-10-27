"""Fit the in-domain regional classifier on all K characters and export it (JSON) for regional_skin_v3.
Per-class paint thresholds are chosen on grouped out-of-fold probabilities (persons held out) so that each
painted colour reaches >= 0.80 precision; separately for a single photo and for the 3-angle average."""
import json, collections, numpy as np, hashlib
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
exec(open(f'{S}/rf/k_train.py').read().split("C = ['dry'")[0])   # rows, X, Y, G, Ys, SCAL
C = ['dry', 'normal', 'oily']; CA = np.array(C)
def fit(Xa, ya):
    sc = StandardScaler().fit(Xa); m = LogisticRegression(C=0.05, max_iter=3000, class_weight='balanced').fit(sc.transform(Xa), ya); return sc, m
oof = np.zeros((len(rows), 3)); oofs = np.zeros(len(rows))
for tr, te in GroupKFold(n_splits=10).split(X, Y, G):
    sc, m = fit(X[tr], Y[tr]); oof[te] = m.predict_proba(sc.transform(X[te]))
    sc2, m2 = fit(X[tr], Ys[tr]); oofs[te] = m2.predict_proba(sc2.transform(X[te]))[:, 1]
def thresholds(mode):
    agg = collections.defaultdict(list)
    for i, r in enumerate(rows):
        if mode == 'single' or True:
            agg[(r['kid'], r['app'], r['view'] if mode == 'single' else 'all')].append(i)
    P = np.array([oof[v].mean(0) for v in agg.values()]); Yt = np.array([rows[v[0]]['y'] for v in agg.values()])
    Ps = np.array([oofs[v].mean() for v in agg.values()]); Yst = np.array([rows[v[0]]['sens'] for v in agg.values()])
    pred = CA[P.argmax(1)]; pm = P.max(1); out = {}; rep = {}
    for c in C:
        for t in np.arange(0.40, 0.951, 0.01):
            k = (pred == c) & (pm >= t)
            if k.sum() >= 20 and (Yt[k] == c).mean() >= 0.80:
                out[c] = round(float(t), 2); rep[c] = dict(precision=round(float((Yt[k] == c).mean()), 3), recall=round(float(k[Yt == c].mean() if False else ((Yt == c) & k).sum() / max((Yt == c).sum(), 1)), 3), n=int(k.sum())); break
    for t in np.arange(0.3, 0.951, 0.01):
        k = Ps >= t
        if (Yst[k]).mean() >= 0.82:
            out['sensitive'] = round(float(t), 2); rep['sensitive'] = dict(precision=round(float(Yst[k].mean()), 3), recall=round(float((k & Yst).sum() / Yst.sum()), 3)); break
    out = {k: (max(v, 0.70) if k != 'sensitive' else v) for k, v in out.items()}
    for c in C:
        k = (pred == c) & (pm >= out[c]); rep[c] = dict(precision=round(float((Yt[k] == c).mean()), 3), recall=round(float(((Yt == c) & k).sum() / max((Yt == c).sum(), 1)), 3), n=int(k.sum()))
    keep = np.array([pm[i] >= out[pred[i]] for i in range(len(pm))]); rep['coverage'] = round(float(keep.mean()), 3); rep['accuracyWhenPainted'] = round(float((pred[keep] == Yt[keep]).mean()), 3)
    return out, rep
FLOOR = 0.70  # never paint a colour below this probability, even if 0.80 precision is reached lower
def floor(T): return {k: (max(v, FLOOR) if k != 'sensitive' else v) for k, v in T.items()}
T1, R1 = thresholds('single'); T3, R3 = thresholds('multi'); T1, T3 = floor(T1), floor(T3)
print('single', T1, R1); print('multi', T3, R3)
sc, m = fit(X, Y); scs, ms = fit(X, Ys)
assert list(m.classes_) == C
exp = dict(version='k-regional-20261025f', features=dict(dino='facebook/dinov2-small CLS+meanpatch on masked region bbox crop (face scaled to 400 px), 768', scalars=SCAL, regionOneHot=['forehead', 'nose', 'chin', 'rightCheek', 'leftCheek']),
           classes=C, type=dict(mean=sc.mean_.tolist(), scale=sc.scale_.tolist(), coef=m.coef_.tolist(), intercept=m.intercept_.tolist()),
           sensitive=dict(mean=scs.mean_.tolist(), scale=scs.scale_.tolist(), coef=ms.coef_[0].tolist(), intercept=float(ms.intercept_[0])),
           thresholds=dict(single=T1, multi=T3),
           validation=dict(note='Synthetic in-car characters (labels = generation intent), grouped by person (10-fold). Not a clinical validation.',
                           persons=int(len(set(G))), single=R1, multi=R3))
s = json.dumps(exp); exp['sha256'] = hashlib.sha256(s.encode()).hexdigest()
json.dump(exp, open(f'{S}/repo/claude-skin/services/core-api/models/regional-skin-v3/k_classifier.json', 'w'))
print('saved', len(s) // 1024, 'KB')
