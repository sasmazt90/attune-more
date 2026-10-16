"""Verifier v3: training set = reviewed TRAIN candidates only (v2 review 300 + v3 review 373). A -> positive, F/M/P/O -> negative
(subtype kept), U and conflicts excluded; no automatic v1 label is used. Same split rule, model family, settings, threshold rule and gate
as v2. Protocol docs/acne-verifier-v3-protocol-20261016.json. DEV is not read; v1/v2 files are read only."""
import hashlib, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import acne_candidate_verifier as V
import verifier_v2_train as T2

SEED = 20261016; V1 = CODE / 'audit-results/acne-verifier'; V2 = CODE / 'audit-results/acne-verifier-v2'; O = CODE / 'audit-results/acne-verifier-v3'
TYPE = dict(F='flat', M='mole-mark', P='pore-shine', O='other')
NEG_TYPES = ('flat', 'mole-mark', 'pore-shine', 'other')


def main():
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    L1 = json.loads((V1 / 'labels.json').read_text()); rows, grp = L1['rows'], L1['groups']
    rl2 = json.loads((V2 / 'review-list.json').read_text())['items']; d2 = json.loads((V2 / 'review-decisions.json').read_text())
    rl3 = json.loads((O / 'review-list.json').read_text())['items']; d3 = json.loads((O / 'review-decisions-v3.json').read_text())
    rev = {}
    for it in rl2:
        c = d2['decisions'][it['rid']]; rev[(it['photo'], it['idx'])] = dict(rid=it['rid'], round='v2', cat=c, reason='v2 category: ' + d2['categories'][c], pose=it['pose'], fw=it['fwPx'], tert=it['scaleTertile'])
    for it in rl3:
        k = (it['photo'], it['idx']); assert k not in rev, 'v2 decision redone'
        c = d3['decisions'][it['rid']]; rev[k] = dict(rid=it['rid'], round='v3', cat=c['cat'], reason=c['reason'], pose=it['pose'], fw=it['fwPx'], tert=it['scaleTertile'])
    box = {(r['photo'], r['idx']): r['box'] for r in rows}
    # conflicts: same photo, centres within r = .03 fw, one A and the other F/M/P/O
    ctr = lambda b: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2); conflicts = []; byph = {}
    for k, v in rev.items(): byph.setdefault(k[0], []).append(k)
    for ph, ks in byph.items():
        for i, a in enumerate(ks):
            for b in ks[i + 1:]:
                ca, cb = rev[a]['cat'], rev[b]['cat']
                if {ca == 'A', cb == 'A'} == {True, False} and 'U' not in (ca, cb):
                    (xa, ya), (xb, yb) = ctr(box[a]), ctr(box[b])
                    if np.hypot(xa - xb, ya - yb) <= .03 * rev[a]['fw']:
                        conflicts.append(dict(photo=ph, a=dict(rid=rev[a]['rid'], cat=ca, reason=rev[a]['reason']), b=dict(rid=rev[b]['rid'], cat=cb, reason=rev[b]['reason']),
                                              distancePx=round(float(np.hypot(xa - xb, ya - yb)), 1), rPx=round(.03 * rev[a]['fw'], 1),
                                              why='same location judged acne-like on one candidate and not acne on the other; both excluded, not forced into a class'))
    cset = {(c['photo'], c[s]['rid']) for c in conflicts for s in ('a', 'b')}
    lab, feats, F = [], [], {}
    for r in rows:
        k = (r['photo'], r['idx']); v = rev.get(k)
        if v is None: y, t, src = None, None, 'unreviewed-excluded'
        elif (k[0], v['rid']) in cset: y, t, src = None, None, 'conflict-excluded'
        elif v['cat'] == 'U': y, t, src = None, None, 'uncertain-excluded'
        else: y = 1 if v['cat'] == 'A' else 0; t = 'pos' if y else TYPE[v['cat']]; src = f"review-{v['round']}:{v['cat']}"
        lab.append(dict(photo=r['photo'], idx=r['idx'], box=r['box'], v1Label=r['label'], label=y, type=t, source=src, rid=v and v['rid'], reason=v and v['reason']))
        if y is not None:
            if r['photo'] not in F: F[r['photo']] = np.load(V1 / 'train' / f"{r['photo']}.npz")['features']
            feats.append(F[r['photo']][r['idx']]); lab[-1]['row'] = len(feats) - 1
    used = [l for l in lab if l['label'] is not None]; y = np.array([l['label'] for l in used]); Ty = np.array([l['type'] for l in used])
    groups = sorted({grp[l['photo']] for l in used}); fgroups = {grp[l['photo']] for l in used if l['type'] == 'flat'}
    calG = T2.split_groups(groups, fgroups); spl = np.array(['calibration' if grp[l['photo']] in calG else 'learn' for l in used])
    for l in lab: l['split'] = None if l['label'] is None else ('calibration' if grp[l['photo']] in calG else 'learn')
    cov = {s: {t: dict(n=int(((Ty == t) & (spl == s)).sum()), photos=len({u['photo'] for u, tt, ss in zip(used, Ty, spl) if tt == t and ss == s})) for t in ('pos',) + NEG_TYPES} for s in ('learn', 'calibration')}
    insufficient = sorted({t for s in cov for t in cov[s] if cov[s][t]['photos'] < 2})
    revcat = {}
    for v in rev.values(): revcat.setdefault(v['round'], {}).setdefault(v['cat'], 0); revcat[v['round']][v['cat']] += 1
    usedPose = {p: sum(1 for l in used if rev[(l['photo'], l['idx'])]['pose'] == p) for p in ('FRONT', 'LEFT', 'RIGHT')}
    usedTert = {t: sum(1 for l in used if rev[(l['photo'], l['idx'])]['tert'] == t) for t in range(3)}
    rec = dict(protocol='docs/acne-verifier-v3-protocol-20261016.json', reviewedTotal=len(rev), reviewByRound=revcat, conflicts=len(conflicts),
               labelled=dict(n=int(len(y)), positives=int(y.sum()), byType={t: int((Ty == t).sum()) for t in ('pos',) + NEG_TYPES}, photos=len({l['photo'] for l in used})),
               excluded=dict(uncertain=sum(1 for l in lab if l['source'] == 'uncertain-excluded'), conflict=sum(1 for l in lab if l['source'] == 'conflict-excluded'), unreviewed=sum(1 for l in lab if l['source'] == 'unreviewed-excluded')),
               coverage=cov, insufficientCategories=insufficient, usedByPose=usedPose, usedByFaceWidthTertile=usedTert)
    X = np.stack(feats).astype(np.float64); il = np.where(spl == 'learn')[0]; ic = np.where(spl == 'calibration')[0]
    mean = X[il].mean(0); scale = X[il].std(0); scale[scale < 1e-8] = 1.; Z = (X - mean) / scale
    clf = LogisticRegression(C=.1, penalty='l2', class_weight='balanced', solver='lbfgs', max_iter=2000).fit(Z[il], y[il])
    pl, pc = clf.predict_proba(Z[il])[:, 1], clf.predict_proba(Z[ic])[:, 1]; yc, Tc = y[ic], Ty[ic]
    pos = np.sort(pc[yc == 1]); k = int(np.floor(.05 * len(pos))); thr = float(pos[k])
    removed = float((pc[yc == 0] < thr).mean()); auc = float(roc_auc_score(yc, pc)); per = {}
    for t in NEG_TYPES:
        m = Tc == t; n = int(m.sum()); kk = int((pc[m] < thr).sum())
        per[t] = dict(n=n, photos=len({used[i]['photo'] for i in ic[m]}), removed=kk, removedFrac=round(kk / n, 3) if n else None, removedCI95=T2.wilson(kk, n),
                      aucVsPositives=round(float(roc_auc_score(np.r_[np.ones((yc == 1).sum()), np.zeros(n)], np.r_[pc[yc == 1], pc[m]])), 3) if n else None)
    gate = auc >= .65 and removed >= .15
    rec.update(learn=dict(n=int(len(il)), pos=int(y[il].sum()), neg=int((y[il] == 0).sum()), auc=float(roc_auc_score(y[il], pl))),
               calibration=dict(n=int(len(ic)), pos=int(yc.sum()), neg=int((yc == 0).sum()), groups=len(calG), auc=auc, threshold=thr, keptPositives=float((pc[yc == 1] >= thr).mean()),
                                removedNegatives=removed, removedNegativesCI95=T2.wilson(int((pc[yc == 0] < thr).sum()), int((yc == 0).sum())), byType=per),
               gate=dict(rule='calibration AUC >= .65 and >= 15% negatives removed', passed=bool(gate)), caution='learn AUC and overall AUC are not success criteria; see byType')
    model = dict(featureVersion=V.VERSION, standardizer=dict(mean=mean.tolist(), scale=scale.tolist()), model=dict(family='logistic regression L2', C=.1, classWeight='balanced',
                 coef=clf.coef_[0].tolist(), intercept=float(clf.intercept_[0])), threshold=thr, seed=SEED, version='v3', protocol='docs/acne-verifier-v3-protocol-20261016.json')
    (O / 'labels-v3.json').write_text(json.dumps(dict(rows=lab, calibrationGroups=sorted(calG)))); (O / 'conflicts-v3.json').write_text(json.dumps(conflicts, indent=1))
    (O / 'calibration-v3.json').write_text(json.dumps(rec, indent=1))
    if gate: (O / 'verifier-v3.json').write_text(json.dumps(model))
    print(json.dumps(rec, indent=1))


if __name__ == '__main__': main()
