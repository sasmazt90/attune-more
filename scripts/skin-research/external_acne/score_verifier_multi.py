"""A = Step0 + old box filter and A + each verifier (v1, v2, v3, ...) on the same 108 targets, layer 1, masks, r = .03 fw, one-to-one matching.
Usage: score_verifier_multi.py OUT.json NAME=DECISIONS.json [NAME=DECISIONS.json ...]"""
import json, sys
import numpy as np, cv2
import relabel_compare as RC, common_scope_compare as CS
CL = ['false', 'duplicate', 'onUncertain', 'onOther', 'nearOutOfScopeTarget', 'unreviewedInOval', 'nonSkin', 'unreviewedPhoto']
EXPECT = {'A': (71, 96, 48), 'v1': (70, 78, 42), 'v2': (68, 69, 38)}
def key(b): return tuple(round(float(v), 3) for v in b[:4])
out_path = sys.argv[1]; Ds = dict(a.split('=', 1) for a in sys.argv[2:]); Ds = {n: json.load(open(p)) for n, p in Ds.items()}
P = json.load(open('point-filter-raw.json'))['photos']; L1 = json.load(open('acne-point-relabel-layer1-20261016.json'))['photos']
man = {m['sha256'][:12]: m for m in json.load(open('pack/manifest.json'))}; lm = {}
for f in ('lm-dev.jsonl', 'lm-devext.jsonl'):
    for l in open(f): r = json.loads(l); lm[r['sha256'][:12]] = r
photos = sorted(L1); S = {'A': {}}; rej = {}
first = next(iter(Ds.values()))
for ph in photos:
    fa = [b[:4] for b in first['photos'][ph]['final']]
    assert sorted(map(key, fa)) == sorted(key(a['box']) for a in P[ph]['step0']['boxAccepted']), ('A_PARITY', ph)
    S['A'][ph] = fa
    for n, D in Ds.items():
        d = D['photos'][ph]; assert [key(b) for b in d['final']] == [key(b) for b in fa]
        S.setdefault(n, {})[ph] = [b for b, k in zip(fa, d['keep']) if k]; rej.setdefault(n, {})[ph] = [(b, p) for b, k, p in zip(fa, d['keep'], d['proba']) if not k]
res = {n: {ph: CS.classify(L1[ph], S[n][ph], cv2.imread(f'layer1/masks/{ph}.png', cv2.IMREAD_GRAYSCALE) > 0,
                            RC.oval_mask(lm[ph], lm[ph]['width'], lm[ph]['height']), .03 * L1[ph]['faceWidthPx']) for ph in photos} for n in S}
tab = {n: dict(found=sum(len(R[p]['hitIds']) for p in photos), of=sum(len(R[p]['inScope']) for p in photos), points=sum(len(R[p]['classes']) for p in photos),
               **{c: sum(R[p]['classes'].count(c) for p in photos) for c in CL}) for n, R in res.items()}
for n, e in EXPECT.items():
    if n in tab: assert (tab[n]['found'], tab[n]['false'], tab[n]['duplicate']) == e, ('PARITY', n, tab[n])
ids = {n: {(p, h) for p in photos for h in res[n][p]['hitIds']} for n in S}; fmt = lambda s: sorted(f'{a}#{b}' for a, b in s)
targets = {f'{n} vs {m}': dict(lost=fmt(ids[m] - ids[n]), gained=fmt(ids[n] - ids[m])) for n in S for m in S if n != m and (m in ('A', 'v1'))}
removed = {n: {} for n in rej}
for n in rej:
    for ph in photos:
        cl = dict(zip(map(key, S['A'][ph]), res['A'][ph]['classes']))
        for b, p in rej[n][ph]: removed[n].setdefault(cl[key(b)], []).append(dict(photo=ph, box=[round(v, 1) for v in b], proba=round(p, 4)))
per = {ph: dict(set=man[ph]['set'], **{n: dict(found=len(res[n][ph]['hitIds']), points=len(S[n][ph]), **{c: res[n][ph]['classes'].count(c) for c in ('false', 'duplicate', 'onUncertain', 'nonSkin')},
                                                hitIds=sorted(res[n][ph]['hitIds'])) for n in S}) for ph in photos}
rng = np.random.default_rng(20261016)
def bs(a, b, k):
    d = np.array([per[p][b][k] - per[p][a][k] for p in photos]); return [float(x) for x in np.percentile([d[rng.integers(0, len(d), len(d))].sum() for _ in range(10000)], [2.5, 97.5])]
ci = {f'{n}-{m} {k}': bs(m, n, k) for n in S for m in ('A', 'v1') if n != m and n != 'A' for k in ('false', 'found')}
negs = [ph for ph, v in first['photos'].items() if v['kind'] == 'negative-photo']
out = dict(table=tab, targets=targets, removedByClassUnderA={n: {k: len(v) for k, v in r.items()} for n, r in removed.items()}, removed=removed, CI95=ci, perPhoto=per,
           clear=dict(photos=len(negs), pointsA=sum(len(first['photos'][p]['final']) for p in negs)),
           bySet={s: {n: sum(per[p][n]['found'] for p in photos if per[p]['set'] == s) for n in S} for s in ('dev', 'devext')})
json.dump(out, open(out_path, 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ('perPhoto', 'removed')}, indent=1))
