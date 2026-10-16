"""Verifier v2, step 1: deterministic TRAIN review list (budget 300), fixed BEFORE any review. DEV results are not read.
Pools (from v1 TRAIN labels audit-results/acne-verifier/labels.json, Step0 final candidates of the 158 TRAIN photos):
  pos  : v1 positives (within r of a kept box centre)            -> 60 control samples
  neg  : all v1 negatives (6 clean ROI + 65 confounder boxes)      -> 71 (all)
  unl  : v1 'excluded: unlabelled area' candidates                 -> 169
Diversity: photo strata = pose (FRONT / side: LEFT|RIGHT capture) x face-scale tertile (face width px, 234-454, over the 158
photos). Within a pool, candidates are ordered by round (k-th candidate of a photo), then by sha256(seed|pool|photo|idx);
strata are interleaved (one pick per stratum per turn, small strata first exhaust) until the quota is met. Per-photo cap per pool:
pos 2, unl 4. Review ids R001.. are assigned in sha256(seed|review|photo|idx) order so review sheets are blind to the pool.
Writes audit-results/acne-verifier-v2/review-list.json and the photo-free docs/acne-verifier-v2-review-list-20261016.json."""
import hashlib, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import verifier_extract as X

SEED = 20261016; QUOTA = dict(pos=60, neg=71, unl=169); CAP = dict(pos=2, neg=10 ** 6, unl=4)
H = lambda *a: hashlib.sha256('|'.join(map(str, a)).encode()).hexdigest()


def photo_attrs():
    man = {p['sha256']: p for p in json.load(open(CODE / 'audit-results/acne-v6-data/manifest-v6.json'))['photos']}; at = {}
    for s, k, f, rp, _ in X.items('train'):
        p = man[s]; L = rp['landmarks']; fw = float(np.hypot((L[234]['x'] - L[454]['x']) * p['width'], (L[234]['y'] - L[454]['y']) * p['height']))
        at[s[:12]] = dict(pose=rp['matchedAngle'], side=rp['matchedAngle'] != 'FRONT', fwPx=round(fw, 1), scaleRatio=rp['alignment']['scaleRatio'], kind=k)
    t = np.percentile([a['fwPx'] for a in at.values()], [100 / 3, 200 / 3])
    for a in at.values(): a['scaleTertile'] = int(np.searchsorted(t, a['fwPx'], side='right'))
    return at, [float(x) for x in t]


def select(rows, at, pool):
    by = {}
    for r in rows: by.setdefault(r['photo'], []).append(r)
    for ph in by: by[ph].sort(key=lambda r: H(SEED, pool, ph, r['idx']))
    strata = {}
    for ph, L in by.items():
        for k, r in enumerate(L[:CAP[pool]]): strata.setdefault((at[ph]['side'], at[ph]['scaleTertile']), []).append((k, H(SEED, pool, ph), r))
    for s in strata: strata[s].sort(key=lambda x: (x[0], x[1]))
    order = sorted(strata, key=lambda s: (len(strata[s]), str(s))); out = []
    while len(out) < QUOTA[pool] and any(strata.values()):
        for s in order:
            if strata[s] and len(out) < QUOTA[pool]: out.append(strata[s].pop(0)[2])
    return out


def main():
    rows = json.loads((CODE / 'audit-results/acne-verifier/labels.json').read_text())['rows']; at, tert = photo_attrs()
    pools = dict(pos=[r for r in rows if r['label'] == 1], neg=[r for r in rows if r['label'] == 0], unl=[r for r in rows if r['reason'] == 'excluded: unlabelled area'])
    sel = []
    for pool, rs in pools.items():
        for r in select(rs, at, pool): sel.append(dict(photo=r['photo'], idx=r['idx'], box=r['box'], score=r['score'], pool=pool, v1Label=r['label'], v1Reason=r['reason'], **{k: at[r['photo']][k] for k in ('pose', 'fwPx', 'scaleTertile')}))
    sel.sort(key=lambda r: H(SEED, 'review', r['photo'], r['idx']))
    for i, r in enumerate(sel): r['rid'] = f'R{i + 1:03d}'
    dist = dict(photos=len(at), pose={p: sum(1 for a in at.values() if a['pose'] == p) for p in ('FRONT', 'LEFT', 'RIGHT')}, faceWidthTertileEdgesPx=tert,
                faceWidthPx=dict(min=min(a['fwPx'] for a in at.values()), median=float(np.median([a['fwPx'] for a in at.values()])), max=max(a['fwPx'] for a in at.values())),
                candidatesByPoseAndPool={f'{p}/{k}': sum(1 for r in rs if (at[r['photo']]['pose'] != 'FRONT') == (p == 'side')) for k, rs in pools.items() for p in ('FRONT', 'side')})
    rec = dict(seed=SEED, quota=QUOTA, perPhotoCap=CAP, items=sel, trainDistribution=dist,
               selected=dict(byPool={k: sum(1 for r in sel if r['pool'] == k) for k in QUOTA}, photos=len({r['photo'] for r in sel}),
                             byPose={p: sum(1 for r in sel if r['pose'] == p) for p in ('FRONT', 'LEFT', 'RIGHT')}, byScaleTertile={t: sum(1 for r in sel if r['scaleTertile'] == t) for t in range(3)}),
               labelsV1Sha256=hashlib.sha256((CODE / 'audit-results/acne-verifier/labels.json').read_bytes()).hexdigest())
    o = CODE / 'audit-results/acne-verifier-v2'; o.mkdir(exist_ok=True); s = json.dumps(rec, indent=1)
    (o / 'review-list.json').write_text(s); (CODE / 'docs/acne-verifier-v2-review-list-20261016.json').write_text(s)
    print(json.dumps({k: v for k, v in rec.items() if k != 'items'}, indent=1))


if __name__ == '__main__': main()
