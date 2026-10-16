"""A = Step0 + old box filter vs B = A minus verifier rejections; same 108 targets, layer 1, r = .03 fw, same classify."""
import json, sys
from pathlib import Path
import numpy as np, cv2
import relabel_compare as RC, common_scope_compare as CS
CL = ['false', 'duplicate', 'onUncertain', 'onOther', 'nearOutOfScopeTarget', 'unreviewedInOval', 'nonSkin', 'unreviewedPhoto']
def key(b): return tuple(round(float(v), 3) for v in b[:4])
W = Path('.'); D = json.load(open(sys.argv[1])); P = json.load(open('point-filter-raw.json'))['photos']
L1 = json.load(open('acne-point-relabel-layer1-20261016.json'))['photos']; man = {m['sha256'][:12]: m for m in json.load(open('pack/manifest.json'))}
lm = {}
for f in ('lm-dev.jsonl', 'lm-devext.jsonl'):
    for l in open(f): r = json.loads(l); lm[r['sha256'][:12]] = r
photos = sorted(L1)
A, B, rej = {}, {}, {}
for ph in photos:
    d = D['photos'][ph]; fa = [b[:4] for b in d['final']]
    assert sorted(map(key, fa)) == sorted(key(a['box']) for a in P[ph]['step0']['boxAccepted']), ('A_PARITY', ph)
    A[ph] = fa; B[ph] = [b for b, k in zip(fa, d['keep']) if k]; rej[ph] = [(b, p) for b, k, p in zip(fa, d['keep'], d['proba']) if not k]
res = {}
for name, S in (('A', A), ('B', B)):
    res[name] = {ph: CS.classify(L1[ph], S[ph], cv2.imread(f'layer1/masks/{ph}.png', cv2.IMREAD_GRAYSCALE) > 0,
                                 RC.oval_mask(lm[ph], lm[ph]['width'], lm[ph]['height']), .03 * L1[ph]['faceWidthPx']) for ph in photos}
tab = {}
for name in ('A', 'B'):
    R = res[name]; tab[name] = dict(found=sum(len(R[p]['hitIds']) for p in photos), of=sum(len(R[p]['inScope']) for p in photos), points=sum(len(R[p]['classes']) for p in photos),
                                    **{c: sum(R[p]['classes'].count(c) for p in photos) for c in CL})
ida = {(p, h) for p in photos for h in res['A'][p]['hitIds']}; idb = {(p, h) for p in photos for h in res['B'][p]['hitIds']}
assert (tab['A']['found'], tab['A']['false'], tab['A']['duplicate']) == (71, 96, 48), tab['A']
# class of each removed point under A
removed = {}
for ph in photos:
    cl = dict(zip(map(key, A[ph]), res['A'][ph]['classes']))
    for b, p in rej[ph]: removed.setdefault(cl[key(b)], []).append(dict(photo=ph, box=[round(v, 1) for v in b], proba=round(p, 4)))
per = {ph: dict(set=man[ph]['set'], A=dict(found=len(res['A'][ph]['hitIds']), points=len(A[ph]), false=res['A'][ph]['classes'].count('false')),
                B=dict(found=len(res['B'][ph]['hitIds']), points=len(B[ph]), false=res['B'][ph]['classes'].count('false')),
                lost=sorted(set(res['A'][ph]['hitIds']) - set(res['B'][ph]['hitIds']))) for ph in photos}
# paired photo bootstrap for deltas
rng = np.random.default_rng(20261016); dF = np.array([per[p]['B']['false'] - per[p]['A']['false'] for p in photos]); dT = np.array([per[p]['B']['found'] - per[p]['A']['found'] for p in photos])
bs = lambda d: [float(x) for x in np.percentile([d[rng.integers(0, len(d), len(d))].sum() for _ in range(10000)], [2.5, 97.5])]
negs = [ph for ph, v in D['photos'].items() if v['kind'] == 'negative-photo']; clear = dict(photos=len(negs), A=0, B=0, Afalse=0, Bfalse=0)
for ph in negs:
    m = cv2.imread(str(W / 'pack' / man[ph]['negMask']), cv2.IMREAD_GRAYSCALE) > 0; d = D['photos'][ph]
    for b, k in zip(d['final'], d['keep']):
        f = RC.inside(m, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)); clear['A'] += 1; clear['Afalse'] += f; clear['B'] += k; clear['Bfalse'] += f and k
tm = {k: dict(median=float(np.median([v[k] for v in D['photos'].values()])), max=float(np.max([v[k] for v in D['photos'].values()]))) for k in ('chainSec', 'featureSec', 'verifierSec', 'featureBytes', 'maxRssMiB')}
out = dict(table=tab, lostTargets=sorted(f'{a}#{b}' for a, b in ida - idb), gainedTargets=sorted(f'{a}#{b}' for a, b in idb - ida),
           removedByClassUnderA={k: len(v) for k, v in removed.items()}, removed=removed, deltaFalseCI95=bs(dF), deltaFoundCI95=bs(dT), perPhoto=per, clear=clear, timing=tm,
           bySet={s: dict(A=sum(per[p]['A']['found'] for p in photos if per[p]['set'] == s), B=sum(per[p]['B']['found'] for p in photos if per[p]['set'] == s)) for s in ('dev', 'devext')})
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ('perPhoto', 'removed')}, indent=1))
