"""Strict transfer test: train only on automated characters (K>30), test on the user's hand-made K-001..K-030."""
import numpy as np, collections
exec(open('/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad/rf/k_train.py').read().split("C = ['dry'")[0])
from sklearn.linear_model import LogisticRegression; from sklearn.preprocessing import StandardScaler; from sklearn.pipeline import make_pipeline
C = ['dry', 'normal', 'oily']; old = np.array([int(g[2:]) <= 30 for g in G])
m = make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=3000, class_weight='balanced')).fit(X[~old], Y[~old])
p = m.predict_proba(X[old]); idx = np.where(old)[0]; agg = collections.defaultdict(list)
for j, i in enumerate(idx): agg[(rows[i]['kid'], rows[i]['app'])].append(j)
P = np.array([p[v].mean(0) for v in agg.values()]); Yt = np.array([Y[idx[v[0]]] for v in agg.values()]); pred = np.array(C)[P.argmax(1)]
print('train=otomatik', (~old).sum(), 'satır | test=eski 30: n', len(Yt), 'acc', round((pred == Yt).mean(), 2))
for t in (0.4, 0.6, 0.7, 0.8):
    k = P.max(1) >= t; s = f' t={t} cov={k.mean():.2f} acc={(pred[k]==Yt[k]).mean():.2f}'
    for c in C: kk = k & (pred == c); s += f' {c}:P={(Yt[kk]==c).mean() if kk.sum() else 0:.2f}(n={kk.sum()})'
    print(s)
print(collections.Counter(zip(Yt, pred)))
