"""Common-scope comparison (protocol docs/acne-common-scope-protocol-20261016.json). Stored predictions only; no inference.
In-scope TARGET = layer-1 TARGET inside the frozen reviewed mask. Matching against in-scope TARGETs only (r = 0.03 fw)."""
import json, random, sys
from pathlib import Path
import numpy as np, cv2
import relabel_compare as RC

OTHER = RC.OTHER


def classify(lab, preds, mask, oval, r):
    pts = lab['points']; empty = not mask.any()
    tg = [p for p in pts if p['cat'] == 'TARGET']
    ins = [p for p in tg if not empty and RC.inside(mask, (p['x'], p['y']))]; outs = [p for p in tg if p not in ins]
    T = [(p['x'], p['y']) for p in ins]; U = [(p['x'], p['y']) for p in pts if p['cat'] == 'UNCERTAIN']
    O = [(p['x'], p['y']) for p in pts if p['cat'] in OTHER]; OT = [(p['x'], p['y']) for p in outs]
    P = [((b[0] + b[2]) / 2., (b[1] + b[3]) / 2.) for b in preds]
    m = RC.match(T, P, r); used = {j for _, j, _ in m}; hit = {i for i, _, _ in m}
    cls = []
    for j, p in enumerate(P):
        if j in used: cls.append('matched'); continue
        if RC.near(p, [T[i] for i in hit], r): cls.append('duplicate'); continue
        if RC.near(p, OT, r): cls.append('nearOutOfScopeTarget'); continue
        if RC.near(p, O, r): cls.append('onOther'); continue
        if RC.near(p, U, r): cls.append('onUncertain'); continue
        if empty: cls.append('unreviewedPhoto'); continue
        if RC.inside(mask, p): cls.append('false'); continue
        cls.append('unreviewedInOval' if RC.inside(oval, p) else 'nonSkin')
    return dict(inScope=[p['id'] for p in ins], outOfScope=[p['id'] for p in outs], hitIds=[ins[i]['id'] for i in sorted(hit)], classes=cls)


def boot(a, b, photos, n=5000, seed=0):
    rnd = random.Random(seed); d = []
    for _ in range(n):
        s = [rnd.choice(photos) for _ in photos]; d.append(sum(a[p] for p in s) - sum(b[p] for p in s))
    d.sort(); return [d[int(.025 * n)], d[int(.975 * n) - 1]]


def main(W):
    W = Path(W); L1 = json.load(open(W / 'acne-point-relabel-layer1-20261016.json'))['photos']
    man = {m['sha256'][:12]: m for m in json.load(open(W / 'pack/manifest.json'))}
    lm = {}
    for f in ('lm-dev.jsonl', 'lm-devext.jsonl'):
        for l in open(W / f): r = json.loads(l); lm[r['sha256'][:12]] = r
    rows = json.load(open(W / 'regen/all-rows.json')); step0 = {}
    for f in ('step0/dev.jsonl', 'step0/devext.jsonl'):
        for l in open(W / f): r = json.loads(l); step0[r['sha256'][:12]] = r['final']
    tr = {ph: json.load(open(W / 'trace/acne-step0-trace' / f'{ph}.json')) for ph in L1}
    preds = {'step0-final': {ph: [b[:4] for b in step0[ph]] for ph in L1},
             'step0-before-filter': {ph: [b[:4] for b in tr[ph]['nms']] for ph in L1}}
    for k in ('dewiin-anyacne/tiles', 'tristan-gray/tiles', 'carsten12/tiles'):
        by = {r['sha'][:12]: r for r in rows[k]}; preds[k] = {ph: [b[:4] for b in by[ph]['final']] for ph in L1}
    for ph in L1: assert [[round(v, 3) for v in b] for b in preds['step0-final'][ph]] == [[round(v, 3) for v in b[:4]] for b in tr[ph]['final']]
    masks, ovals = {}, {}
    for ph, v in L1.items():
        masks[ph] = cv2.imread(str(W / 'layer1/masks' / f'{ph}.png'), cv2.IMREAD_GRAYSCALE) > 0
        r = lm[ph]; ovals[ph] = RC.oval_mask(r, r['width'], r['height'])
    res = {k: {ph: classify(L1[ph], P[ph], masks[ph], ovals[ph], 0.03 * L1[ph]['faceWidthPx']) for ph in L1} for k, P in preds.items()}
    photos = sorted(L1); rev = [p for p in photos if masks[p].any()]
    base = {p: len(res['step0-final'][p]['hitIds']) for p in photos}; baseIds = {(p, h) for p in photos for h in res['step0-final'][p]['hitIds']}
    CL = ['false', 'duplicate', 'onUncertain', 'onOther', 'nearOutOfScopeTarget', 'unreviewedInOval', 'nonSkin', 'unreviewedPhoto']
    table = {}
    for k, R in res.items():
        hp = {p: len(R[p]['hitIds']) for p in photos}; ids = {(p, h) for p in photos for h in R[p]['hitIds']}
        cnt = {c: sum(R[p]['classes'].count(c) for p in photos) for c in CL}
        sets = {s: [p for p in photos if man[p]['set'] == s] for s in ('dev', 'devext')}
        diffs = {p: hp[p] - base[p] for p in photos}; top = max(photos, key=lambda p: abs(diffs[p]))
        table[k] = dict(inScopeTargets=sum(len(R[p]['inScope']) for p in photos), found=sum(hp.values()), points=sum(len(R[p]['classes']) for p in photos), **cnt,
                        falsePerReviewedPhoto=round(cnt['false'] / len(rev), 2), falsePerReviewedMP=round(cnt['false'] / (sum(int(masks[p].sum()) for p in photos) / 1e6), 2),
                        gainedVsStep0Final=sorted(f'{a}#{b}' for a, b in ids - baseIds), lostVsStep0Final=sorted(f'{a}#{b}' for a, b in baseIds - ids),
                        bySet={s: dict(targets=sum(len(R[p]['inScope']) for p in ps), found=sum(hp[p] for p in ps), false=sum(R[p]['classes'].count('false') for p in ps)) for s, ps in sets.items()},
                        mostInfluentialPhoto=dict(photo=top, diff=diffs[top]), diffVsStep0Final=sum(diffs.values()),
                        diffWithoutMostInfluential=sum(diffs.values()) - diffs[top],
                        boot95=boot(hp, base, photos) if k != 'step0-final' else None,
                        perPhoto={p: dict(targets=len(R[p]['inScope']), found=hp[p], false=R[p]['classes'].count('false'), duplicate=R[p]['classes'].count('duplicate')) for p in photos})
    removed = sorted(f'{p}#{h}' for p in photos for h in set(res['step0-before-filter'][p]['hitIds']) - set(res['step0-final'][p]['hitIds']))
    outscope = {}
    for p in photos:
        for i in res['step0-final'][p]['outOfScope']:
            outscope[f'{p}#{i}'] = 'photo has no reviewed mask (' + ','.join(L1[p]['coverage'].get('flags', [])) + ')' if not masks[p].any() else 'point inside an excluded area of the reviewed mask (hair/shadow/blur/eye-brow-lip margin)'
    trT = {t['target']: t for t in json.load(open(W / 'step0-target-trace.json'))}
    removedDetail = [dict(target=t, filterReasons=trT[t]['S7']['rejected'], inRaster=trT[t]['S3']['inRaster']) for t in removed]
    out = dict(protocolSHA256='8bd3f0c9ae47069f6bf2eb6de05eb95d93cc161bad1e47dfcd403fe04b0586eb', reviewedPhotos=rev, table=table, outOfScopeTargets=outscope,
               foundBeforeFilterRemovedAfter=removedDetail, perPhotoClasses={k: {p: R[p] for p in photos} for k, R in res.items()})
    json.dump(out, open(W / 'common-scope-results.json', 'w'))
    return out


if __name__ == '__main__':
    o = main(sys.argv[1])
    for k, t in o['table'].items():
        print(f"{k:22s} {t['found']}/{t['inScopeTargets']} pts {t['points']} false {t['false']} ({t['falsePerReviewedPhoto']}/ph) dup {t['duplicate']} unc {t['onUncertain']} oth {t['onOther']} nearOut {t['nearOutOfScopeTarget']} unrevOval {t['unreviewedInOval']} nonSkin {t['nonSkin']} unrevPh {t['unreviewedPhoto']} +{len(t['gainedVsStep0Final'])}/-{len(t['lostVsStep0Final'])} diff {t['diffVsStep0Final']} boot {t['boot95']} top {t['mostInfluentialPhoto']} w/o {t['diffWithoutMostInfluential']} sets {t['bySet']}")
    print('out of scope', len(o['outOfScopeTargets'])); import collections; print(collections.Counter(o['outOfScopeTargets'].values()))
    print('removed by filter', o['foundBeforeFilterRemovedAfter'])
