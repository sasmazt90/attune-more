"""Label TRAIN candidates (protocol rules), group/split, fit the one L2 logistic regression, calibrate the threshold on the TRAIN
calibration groups, apply the DEV gate. Writes audit-results/acne-verifier/{labels.json, verifier.json, calibration.json, crops/}.
No DEV data is read except DEV image hashes/dHash for the leakage check."""
import hashlib, json, random, sys
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import acne_candidate_verifier as V
import verifier_extract as X

O = CODE / 'audit-results/acne-verifier'; SEED = 20261016


def dhash(f, n=8):
    g = cv2.cvtColor(cv2.imread(str(f)), cv2.COLOR_BGR2GRAY); g = cv2.resize(g, (n + 1, n), interpolation=cv2.INTER_AREA)
    return (g[:, 1:] > g[:, :-1]).flatten()


def label(p, rp, final, W, H):
    L = rp['landmarks']; fw = float(np.hypot((L[234]['x'] - L[454]['x']) * W, (L[234]['y'] - L[454]['y']) * H)); r = .03 * fw
    kept = [b['box'] for b in p.get('positive', [])]; ign = [b['box'] for b in p.get('ignore', [])]; conf = [b['box'] for b in p.get('negativeBoxes', [])]
    m = cv2.imread(str(CODE / 'audit-results/acne-v6-data' / p['mask']), cv2.IMREAD_GRAYSCALE) > 0 if p.get('mask') else None
    ctr = lambda b: ((b[0] + b[2]) / 2., (b[1] + b[3]) / 2.)
    out = []
    for b in final:
        c = ctr(b); dk = min([np.hypot(c[0] - ctr(k)[0], c[1] - ctr(k)[1]) for k in kept], default=1e9)
        di = min([np.hypot(c[0] - ctr(k)[0], c[1] - ctr(k)[1]) for k in ign], default=1e9)
        inside = lambda bb: bb[0] <= c[0] <= bb[2] and bb[1] <= c[1] <= bb[3]
        if dk <= r and not (di < dk and any(inside(k) for k in ign)): out.append((1, 'positive: within r of a kept box centre'))
        elif dk <= r or di <= r or any(inside(k) for k in kept + ign): out.append((None, 'excluded: near/inside a kept or ignore box'))
        elif any(inside(k) for k in conf): out.append((0, 'negative: inside a kept confounder box'))
        elif m is not None and 0 <= int(c[1]) < m.shape[0] and 0 <= int(c[0]) < m.shape[1] and m[int(c[1]), int(c[0])]:
            out.append((0, 'negative: inside reviewed clean ROI' if p['kind'] == 'positive-photo' else 'negative: inside reviewed negative-photo mask'))
        else: out.append((None, 'excluded: unlabelled area'))
    return out, fw


def crop(img, b, fw, S=96):
    c = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2); tiles = []
    for half in (max(8, .06 * fw), .2 * fw):
        x0, y0 = int(c[0] - half), int(c[1] - half); n = int(2 * half); can = np.zeros((n, n, 3), np.uint8)
        sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(img.shape[1], x0 + n), min(img.shape[0], y0 + n)
        can[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = img[sy0:sy1, sx0:sx1]; can = cv2.resize(can, (S, S)); cv2.circle(can, (S // 2, S // 2), 10, (0, 255, 255), 1); tiles.append(can)
    return np.hstack(tiles)


def main():
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    man = {p['sha256']: p for p in json.load(open(CODE / 'audit-results/acne-v6-data/manifest-v6.json'))['photos']}
    its = {s: (k, f, rp) for s, k, f, rp, _ in X.items('train')}; dev = X.items('dev')
    devh = {s[:12]: dhash(f) for s, k, f, rp, st in dev}
    rows, feats, labs, groups = [], [], [], {}
    (O / 'crops').mkdir(exist_ok=True)
    leak = []; hashes = {}
    for s256, (kind, f, rp) in sorted(its.items()):
        ph = s256[:12]; rec = json.loads((O / 'train' / f'{ph}.json').read_text()); F = np.load(O / 'train' / f'{ph}.npz')['features']
        img = cv2.imread(f); H, W = img.shape[:2]; hashes[ph] = dhash(f)
        near_dev = [d for d, h in devh.items() if int((h != hashes[ph]).sum()) <= 10]
        if near_dev: leak.append(dict(train=ph, dev=near_dev)); continue
        ls, fw = label(man[s256], rp, rec['final'], W, H)
        for i, (b, (y, why)) in enumerate(zip(rec['final'], ls)):
            rows.append(dict(photo=ph, kind=kind, idx=i, box=[round(v, 2) for v in b[:4]], score=b[4], label=y, reason=why))
            if y is not None:
                feats.append(F[i]); labs.append(y); rows[-1]['row'] = len(labs) - 1
                cv2.imwrite(str(O / 'crops' / f"{'pos' if y else 'neg'}-{ph}-{i}.jpg"), crop(img, b, fw))
    # near-duplicate groups inside TRAIN (union-find on dHash <= 10)
    phs = sorted(hashes); parent = {p: p for p in phs}
    def find(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for i, a in enumerate(phs):
        for b in phs[i + 1:]:
            if int((hashes[a] != hashes[b]).sum()) <= 10: parent[find(a)] = find(b)
    grp = {p: find(p) for p in phs}; G = sorted(set(grp[r['photo']] for r in rows if r['label'] is not None))
    random.Random(SEED).shuffle(G); cut = int(round(.7 * len(G))); learnG = set(G[:cut])
    Xa = np.stack(feats).astype(np.float64); y = np.asarray(labs)
    idx_learn = np.array([i for i, r in enumerate([r for r in rows if r['label'] is not None]) if grp[r['photo']] in learnG]); idx_cal = np.array(sorted(set(range(len(y))) - set(idx_learn)))
    mean = Xa[idx_learn].mean(0); scale = Xa[idx_learn].std(0); scale[scale < 1e-8] = 1.
    Z = (Xa - mean) / scale
    clf = LogisticRegression(C=.1, penalty='l2', class_weight='balanced', solver='lbfgs', max_iter=2000).fit(Z[idx_learn], y[idx_learn])
    p_learn = clf.predict_proba(Z[idx_learn])[:, 1]; p_cal = clf.predict_proba(Z[idx_cal])[:, 1]
    yc = y[idx_cal]; pos = np.sort(p_cal[yc == 1])
    k = int(np.floor(.05 * len(pos)))                     # may drop at most 5% of calibration positives
    thr = float(pos[k]) if len(pos) else 0.               # threshold = k-th lowest positive score -> keeps >= 95%
    kept_pos = float((p_cal[yc == 1] >= thr).mean()); removed_neg = float((p_cal[yc == 0] < thr).mean())
    auc_cal = float(roc_auc_score(yc, p_cal)); auc_learn = float(roc_auc_score(y[idx_learn], p_learn))
    gate = auc_cal >= .65 and removed_neg >= .15
    cal = dict(nLabelled=int(len(y)), positives=int(y.sum()), negatives=int((1 - y).sum()), learn=dict(n=int(len(idx_learn)), pos=int(y[idx_learn].sum()), groups=len(learnG), auc=auc_learn),
               calibration=dict(n=int(len(idx_cal)), pos=int(yc.sum()), neg=int((1 - yc).sum()), groups=len(G) - len(learnG), auc=auc_cal, threshold=thr,
                                keptPositives=kept_pos, removedNegatives=removed_neg),
               gate=dict(rule='AUC >= .65 and removed negatives >= 15% at the threshold', passed=bool(gate)), leakageDroppedTrainPhotos=leak,
               nearDuplicateTrainGroups=sum(1 for g in set(grp.values()) if sum(1 for p in phs if grp[p] == g) > 1),
               labelReasons={k2: sum(1 for r in rows if r['reason'] == k2) for k2 in sorted({r['reason'] for r in rows})}, photosUsed=len(phs))
    model = dict(featureVersion=V.VERSION, standardizer=dict(mean=mean.tolist(), scale=scale.tolist()), model=dict(family='logistic regression L2', C=.1, classWeight='balanced',
                 coef=clf.coef_[0].tolist(), intercept=float(clf.intercept_[0])), threshold=thr, seed=SEED, protocol='docs/acne-verifier-protocol-20261016.json')
    for r in rows: r['split'] = None if r['label'] is None else ('learn' if grp[r['photo']] in learnG else 'calibration')
    (O / 'labels.json').write_text(json.dumps(dict(rows=rows, groups=grp)))
    (O / 'verifier.json').write_text(json.dumps(model)); (O / 'calibration.json').write_text(json.dumps(cal, indent=1))
    print(json.dumps({k2: v for k2, v in cal.items() if k2 != 'leakageDroppedTrainPhotos'}, indent=1), 'leak', leak)


if __name__ == '__main__': main()
