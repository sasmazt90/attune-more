"""A = Step0 + old box filter, B = A + verifier v1, C = A + verifier v2 on the same 108 targets, layer 1, masks, r = .03 fw, matching."""
import json, sys
import numpy as np, cv2
import relabel_compare as RC, common_scope_compare as CS
CL = ['false', 'duplicate', 'onUncertain', 'onOther', 'nearOutOfScopeTarget', 'unreviewedInOval', 'nonSkin', 'unreviewedPhoto']
def key(b): return tuple(round(float(v), 3) for v in b[:4])
D1, D2 = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])); P = json.load(open('point-filter-raw.json'))['photos']
L1 = json.load(open('acne-point-relabel-layer1-20261016.json'))['photos']; man = {m['sha256'][:12]: m for m in json.load(open('pack/manifest.json'))}
lm = {}
for f in ('lm-dev.jsonl', 'lm-devext.jsonl'):
    for l in open(f): r = json.loads(l); lm[r['sha256'][:12]] = r
photos = sorted(L1); S = {'A': {}, 'B': {}, 'C': {}}; rej = {'B': {}, 'C': {}}
for ph in photos:
    d1, d2 = D1['photos'][ph], D2['photos'][ph]; fa = [b[:4] for b in d1['final']]
    assert [key(b) for b in d2['final']] == [key(b) for b in d1['final']]
    assert sorted(map(key, fa)) == sorted(key(a['box']) for a in P[ph]['step0']['boxAccepted']), ('A_PARITY', ph)
    S['A'][ph] = fa
    for n, d in (('B', d1), ('C', d2)):
        S[n][ph] = [b for b, k in zip(fa, d['keep']) if k]; rej[n][ph] = [(b, p) for b, k, p in zip(fa, d['keep'], d['proba']) if not k]
res = {n: {ph: CS.classify(L1[ph], S[n][ph], cv2.imread(f'layer1/masks/{ph}.png', cv2.IMREAD_GRAYSCALE) > 0,
                            RC.oval_mask(lm[ph], lm[ph]['width'], lm[ph]['height']), .03 * L1[ph]['faceWidthPx']) for ph in photos} for n in S}
tab = {n: dict(found=sum(len(R[p]['hitIds']) for p in photos), of=sum(len(R[p]['inScope']) for p in photos), points=sum(len(R[p]['classes']) for p in photos),
               **{c: sum(R[p]['classes'].count(c) for p in photos) for c in CL}) for n, R in res.items()}
assert (tab['A']['found'], tab['A']['false'], tab['A']['duplicate']) == (71, 96, 48) and (tab['B']['found'], tab['B']['false'], tab['B']['duplicate']) == (70, 78, 42), tab
ids = {n: {(p, h) for p in photos for h in res[n][p]['hitIds']} for n in S}
fmt = lambda s: sorted(f'{a}#{b}' for a, b in s)
removed = {}
for n in ('B', 'C'):
    for ph in photos:
        cl = dict(zip(map(key, S['A'][ph]), res['A'][ph]['classes']))
        for b, p in rej[n][ph]: removed.setdefault(n, {}).setdefault(cl[key(b)], []).append(dict(photo=ph, box=[round(v, 1) for v in b], proba=round(p, 4)))
per = {ph: dict(set=man[ph]['set'], **{n: dict(found=len(res[n][ph]['hitIds']), points=len(S[n][ph]), false=res[n][ph]['classes'].count('false'),
                                                duplicate=res[n][ph]['classes'].count('duplicate'), onUncertain=res[n][ph]['classes'].count('onUncertain')) for n in S}) for ph in photos}
rng = np.random.default_rng(20261016)
def bs(a, b, k):
    d = np.array([per[p][b][k] - per[p][a][k] for p in photos]); return [float(x) for x in np.percentile([d[rng.integers(0, len(d), len(d))].sum() for _ in range(10000)], [2.5, 97.5])]
both = {}
for ph in photos:
    for b, p in rej['C'][ph]:
        both.setdefault('removedByC_alsoByB', 0); both['removedByC_alsoByB'] += any(key(b) == key(x) for x, _ in rej['B'][ph])
negs = [ph for ph, v in D2['photos'].items() if v['kind'] == 'negative-photo']
out = dict(table=tab, targets=dict(lostCvsA=fmt(ids['A'] - ids['C']), gainedCvsA=fmt(ids['C'] - ids['A']), lostCvsB=fmt(ids['B'] - ids['C']), gainedCvsB=fmt(ids['C'] - ids['B']), lostBvsA=fmt(ids['A'] - ids['B'])),
           removedByClassUnderA={n: {k: len(v) for k, v in r.items()} for n, r in removed.items()}, removed=removed, overlap=dict(**both, removedByC=sum(len(v) for v in rej['C'].values()), removedByB=sum(len(v) for v in rej['B'].values())),
           CI95=dict(falseCminusA=bs('A', 'C', 'false'), falseCminusB=bs('B', 'C', 'false'), foundCminusA=bs('A', 'C', 'found'), foundCminusB=bs('B', 'C', 'found')),
           perPhoto=per, clear=dict(photos=len(negs), pointsA=sum(len(D2['photos'][p]['final']) for p in negs)),
           bySet={s: {n: sum(per[p][n]['found'] for p in photos if per[p]['set'] == s) for n in S} for s in ('dev', 'devext')},
           photo_0a8a14a662a5=per['0a8a14a662a5'])
json.dump(out, open(sys.argv[3], 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ('perPhoto', 'removed')}, indent=1))
