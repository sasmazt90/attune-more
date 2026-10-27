"""Shared threshold rule: smallest threshold t such that, at every threshold >= t (with >= 3 positive calls),
the precision expected at an assumed prevalence min(P0, training prevalence) is >= 0.80. Expected precision = TPR*P0 / (TPR*P0 + FPR*(1-P0)),
with TPR/FPR measured on training persons only. Makes the threshold independent of how common the finding happened
to be in the training set."""
import numpy as np
P0 = 0.25
def thr_prev(y, s, p0=P0, target=0.80):
    y = np.asarray(y, bool); s = np.asarray(s, float)
    if y.sum() == 0 or (~y).sum() == 0: return None
    p0 = min(p0, y.mean())   # never assume the finding is more common than observed in training
    ts = np.sort(np.unique(s))
    def prec(t):
        tpr = (s[y] >= t).mean(); fpr = (s[~y] >= t).mean()
        return tpr * p0 / max(tpr * p0 + fpr * (1 - p0), 1e-9)
    for t in ts:
        if (s >= t).sum() >= 3 and all(prec(u) >= target for u in ts[ts >= t] if (s >= u).sum() >= 3):
            return float(t)
    return None
