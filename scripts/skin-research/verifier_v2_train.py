"""Verifier v2, step 3: labels v2 (review layer over v1), protocol split, ONE L2 logistic-regression fit, TRAIN-calibration threshold,
per-negative-type calibration report and gate. Protocol docs/acne-verifier-v2-protocol-20261016.json. DEV is not read.
v1 files (audit-results/acne-verifier/*, docs/acne-verifier-model-20261016.json) are read only."""
import hashlib, json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import acne_candidate_verifier as V

SEED = 20261016; V1 = CODE / 'audit-results/acne-verifier'; O = CODE / 'audit-results/acne-verifier-v2'
TYPE = dict(F='flat', M='mole-mark', P='pore-shine', O='other')
H = lambda *a: hashlib.sha256('|'.join(map(str, a)).encode()).hexdigest()


def wilson(k, n, z=1.96):
    if n == 0: return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def split_groups(groups, fgroups):
    cal = set()
    for G, mn in ((sorted(fgroups), 2), (sorted(set(groups) - set(fgroups)), 0)):
        G = sorted(G, key=lambda g: H(SEED, 'v2split', g)); k = max(mn, int(round(.3 * len(G)))) if G else 0; cal |= set(G[:k])
    return cal


def main():
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    L1 = json.loads((V1 / 'labels.json').read_text()); rows, grp = L1['rows'], L1['groups']
    RL = json.loads((O / 'review-list.json').read_text()); RD = json.loads((O / 'review-decisions.json').read_text())['decisions']
    rev = {(it['photo'], it['idx']): dict(rid=it['rid'], pool=it['pool'], cat=RD[it['rid']], pose=it['pose'], scaleTertile=it['scaleTertile']) for it in RL['items']}
    attrs = {it['photo']: (it['pose'], it['scaleTertile']) for it in RL['items']}
    lab, feats, F = [], [], {}
    for r in rows:
        k = (r['photo'], r['idx'])
        if k in rev:
            c = rev[k]['cat']; y = 1 if c == 'A' else (None if c == 'U' else 0); src = 'review:' + c; t = 'pos' if c == 'A' else TYPE.get(c)
        elif r['label'] == 1: y, src, t = 1, 'v1-positive-unreviewed', 'pos'
        else: y, src, t = None, 'excluded', None
        lab.append(dict(photo=r['photo'], idx=r['idx'], box=r['box'], v1Label=r['label'], v1Reason=r['reason'], label=y, source=src, type=t, rid=rev.get(k, {}).get('rid')))
        if y is not None:
            if r['photo'] not in F: F[r['photo']] = np.load(V1 / 'train' / f"{r['photo']}.npz")['features']
            feats.append(F[r['photo']][r['idx']]); lab[-1]['row'] = len(feats) - 1
    used = [l for l in lab if l['label'] is not None]; y = np.array([l['label'] for l in used]); T = np.array([l['type'] for l in used])
    groups = sorted({grp[l['photo']] for l in used}); fgroups = {grp[l['photo']] for l in used if l['type'] == 'flat'}
    calG = split_groups(groups, fgroups); spl = np.array(['calibration' if grp[l['photo']] in calG else 'learn' for l in used])
    for l in lab: l['split'] = None if l['label'] is None else ('calibration' if grp[l['photo']] in calG else 'learn')
    fl = {s: sorted({l['photo'] for l in used if l['type'] == 'flat' and l['split'] == s}) for s in ('learn', 'calibration')}
    review_tab = {}
    for (ph, ix), v in rev.items(): review_tab.setdefault(v['pool'], {}).setdefault(v['cat'], 0); review_tab[v['pool']][v['cat']] += 1
    rec = dict(protocol='docs/acne-verifier-v2-protocol-20261016.json', reviewByPool=review_tab,
               v1PositiveControlConfirmed=dict(A=review_tab['pos'].get('A', 0), n=sum(review_tab['pos'].values()), ciA=wilson(review_tab['pos'].get('A', 0), sum(review_tab['pos'].values()))),
               labelled=dict(n=int(len(y)), positives=int(y.sum()), byType={t: int((T == t).sum()) for t in ('pos', 'flat', 'mole-mark', 'pore-shine', 'other')},
                             positivesFromReview=sum(1 for l in used if l['source'] == 'review:A'), positivesV1Unreviewed=sum(1 for l in used if l['source'] == 'v1-positive-unreviewed')),
               flatNegativePhotos=dict(learn=len(fl['learn']), calibration=len(fl['calibration'])),
               flatNegativesBySplit={s: int(((T == 'flat') & (spl == s)).sum()) for s in ('learn', 'calibration')},
               reviewedFlatByPose={p: sum(1 for v in rev.values() if v['cat'] == 'F' and v['pose'] == p) for p in ('FRONT', 'LEFT', 'RIGHT')},
               reviewedFlatByScaleTertile={t: sum(1 for v in rev.values() if v['cat'] == 'F' and v['scaleTertile'] == t) for t in range(3)})
    if len(fl['learn']) < 2 or len(fl['calibration']) < 2:
        rec['stopped'] = 'fewer than 2 flat-negative photos in learn or calibration; no fit (protocol)'; (O / 'calibration-v2.json').write_text(json.dumps(rec, indent=1)); print(json.dumps(rec, indent=1)); return
    X = np.stack(feats).astype(np.float64); il = np.where(spl == 'learn')[0]; ic = np.where(spl == 'calibration')[0]
    mean = X[il].mean(0); scale = X[il].std(0); scale[scale < 1e-8] = 1.; Z = (X - mean) / scale
    clf = LogisticRegression(C=.1, penalty='l2', class_weight='balanced', solver='lbfgs', max_iter=2000).fit(Z[il], y[il])
    pl, pc = clf.predict_proba(Z[il])[:, 1], clf.predict_proba(Z[ic])[:, 1]; yc, Tc = y[ic], T[ic]
    pos = np.sort(pc[yc == 1]); k = int(np.floor(.05 * len(pos))); thr = float(pos[k])
    removed = float((pc[yc == 0] < thr).mean()); auc = float(roc_auc_score(yc, pc))
    per = {}
    for t in ('flat', 'mole-mark', 'pore-shine', 'other'):
        m = Tc == t; n = int(m.sum()); kk = int((pc[m] < thr).sum())
        per[t] = dict(n=n, photos=len({used[i]['photo'] for i in ic[m]}), removed=kk, removedFrac=round(kk / n, 3) if n else None, removedCI95=wilson(kk, n),
                      aucVsPositives=round(float(roc_auc_score(np.r_[np.ones((yc == 1).sum()), np.zeros(n)], np.r_[pc[yc == 1], pc[m]])), 3) if n else None)
    gate = auc >= .65 and removed >= .15
    rec.update(learn=dict(n=int(len(il)), pos=int(y[il].sum()), neg=int((y[il] == 0).sum()), groups=len(set(groups) - calG), auc=float(roc_auc_score(y[il], pl)),
                          negByType={t: int((T[il] == t).sum()) for t in ('flat', 'mole-mark', 'pore-shine', 'other')}),
               calibration=dict(n=int(len(ic)), pos=int(yc.sum()), neg=int((yc == 0).sum()), groups=len(calG), auc=auc, threshold=thr,
                                keptPositives=float((pc[yc == 1] >= thr).mean()), removedNegatives=removed, removedNegativesCI95=wilson(int((pc[yc == 0] < thr).sum()), int((yc == 0).sum())), byType=per),
               gate=dict(rule='calibration AUC >= .65 and >= 15% negatives removed (same as v1)', passed=bool(gate)),
               caution='overall AUC does not establish flat-skin separation; see calibration.byType.flat')
    model = dict(featureVersion=V.VERSION, standardizer=dict(mean=mean.tolist(), scale=scale.tolist()), model=dict(family='logistic regression L2', C=.1, classWeight='balanced',
                 coef=clf.coef_[0].tolist(), intercept=float(clf.intercept_[0])), threshold=thr, seed=SEED, version='v2', protocol='docs/acne-verifier-v2-protocol-20261016.json')
    (O / 'labels-v2.json').write_text(json.dumps(dict(rows=lab, calibrationGroups=sorted(calG))))
    (O / 'verifier-v2.json').write_text(json.dumps(model)); (O / 'calibration-v2.json').write_text(json.dumps(rec, indent=1)); print(json.dumps(rec, indent=1))


if __name__ == '__main__': main()
