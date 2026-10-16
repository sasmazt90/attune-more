"""Score external rows before/after the Step0 staging filter on the unchanged common scope (108 in-scope targets, r = 0.03 fw)
and on the 14 Clear photos (reviewed Clear masks). Uses common_scope_compare.classify; no inference."""
import json, sys, collections
from pathlib import Path
import numpy as np, cv2
import relabel_compare as RC, common_scope_compare as CS

MODELS = ['dewiin-anyacne/tiles', 'tristan-gray/tiles', 'carsten12/tiles']


def main(W, F):
    W = Path(W); FR = json.load(open(F)); P = FR['photos']
    L1 = json.load(open(W / 'acne-point-relabel-layer1-20261016.json'))['photos']
    man = {m['sha256'][:12]: m for m in json.load(open(W / 'pack/manifest.json'))}
    lm = {}
    for f in ('lm-dev.jsonl', 'lm-devext.jsonl'):
        for l in open(W / f): r = json.loads(l); lm[r['sha256'][:12]] = r
    step0 = {}
    for f in ('step0/dev.jsonl', 'step0/devext.jsonl'):
        for l in open(W / f): r = json.loads(l); step0[r['sha256'][:12]] = r['final']
    assert all(P[ph]['step0']['masksEqualTrace'] and P[ph]['step0']['finalEqualsStored'] for ph in L1), 'STEP0_PARITY'
    masks = {ph: cv2.imread(str(W / 'layer1/masks' / f'{ph}.png'), cv2.IMREAD_GRAYSCALE) > 0 for ph in L1}
    ovals = {ph: RC.oval_mask(lm[ph], lm[ph]['width'], lm[ph]['height']) for ph in L1}
    rows = {'step0-final': {ph: [b[:4] for b in step0[ph]] for ph in L1}}
    for k in MODELS:
        rows[k + ' before'] = {ph: [b[:4] for b in P[ph][k]['before']] for ph in L1}
        rows[k + ' after'] = {ph: [a['box'][:4] for a in P[ph][k]['assigned']] for ph in L1}
    res = {k: {ph: CS.classify(L1[ph], v[ph], masks[ph], ovals[ph], 0.03 * L1[ph]['faceWidthPx']) for ph in L1} for k, v in rows.items()}
    photos = sorted(L1); base = {(p, h) for p in photos for h in res['step0-final'][p]['hitIds']}
    CL = ['false', 'duplicate', 'onUncertain', 'onOther', 'nearOutOfScopeTarget', 'unreviewedInOval', 'nonSkin', 'unreviewedPhoto']
    table = {}
    for k, R in res.items():
        ids = {(p, h) for p in photos for h in R[p]['hitIds']}
        table[k] = dict(found=len(ids), of=sum(len(R[p]['inScope']) for p in photos), points=sum(len(R[p]['classes']) for p in photos),
                        **{c: sum(R[p]['classes'].count(c) for p in photos) for c in CL},
                        gainedVsStep0=len(ids - base), lostVsStep0=len(base - ids),
                        bySet={s: sum(len(R[p]['hitIds']) for p in photos if man[p]['set'] == s) for s in ('dev', 'devext')},
                        falseBySet={s: sum(R[p]['classes'].count('false') for p in photos if man[p]['set'] == s) for s in ('dev', 'devext')})
    # targets lost by the filter, with the reasons of the near pre-filter boxes; box side of every rejection
    lost = {}; rejstats = {}
    for k in MODELS:
        b, a = res[k + ' before'], res[k + ' after']; L = []
        for ph in photos:
            r = 0.03 * L1[ph]['faceWidthPx']; rej = P[ph][k]['rejected']
            for tid in sorted(set(b[ph]['hitIds']) - set(a[ph]['hitIds'])):
                t = next(p for p in L1[ph]['points'] if p['id'] == tid)
                near = [j for j in rej if np.hypot((j['box'][0] + j['box'][2]) / 2 - t['x'], (j['box'][1] + j['box'][3]) / 2 - t['y']) <= r]
                L.append(dict(target=f'{ph}#{tid}', reasons=sorted({j['reason'] for j in near}),
                              boxSideOverFaceWidth=[round(max(j['box'][2] - j['box'][0], j['box'][3] - j['box'][1]) / L1[ph]['faceWidthPx'], 4) for j in near],
                              sizeDependentRule=any(j['reason'] in ('ANATOMICAL_HAIR_DENSE', 'INSUFFICIENT_SKIN_SUPPORT') or (j['reason'] == 'ANATOMICAL_HOLE' and j.get('excl_frac', 0) > .25) for j in near),
                              outsideRaster=any(j['reason'] == 'OUTSIDE_SOURCE_SUPPORT' for j in near)))
            for j in rej: rejstats.setdefault(k, collections.Counter())[j['reason']] += 1
        lost[k] = L
    # Clear photos (14): false = point inside reviewed Clear mask
    clear = {}
    negs = [ph for ph, v in P.items() if v['kind'] == 'negative-photo']
    for k in MODELS:
        bf = af = 0; px = 0
        for ph in negs:
            m = cv2.imread(str(W / 'pack' / man[ph]['negMask']), cv2.IMREAD_GRAYSCALE) > 0; px += int(m.sum())
            cnt = lambda boxes: sum(1 for b in boxes if RC.inside(m, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)))
            bf += cnt(P[ph][k]['before']); af += cnt([a['box'] for a in P[ph][k]['assigned']])
        clear[k] = dict(photos=len(negs), maskPx=px, falseBefore=bf, falseAfter=af,
                        pointsBefore=sum(len(P[ph][k]['before']) for ph in negs), pointsAfter=sum(len(P[ph][k]['assigned']) for ph in negs))
    return dict(table=table, lostByFilter=lost, rejectionReasons={k: dict(v) for k, v in rejstats.items()}, clear=clear,
                perPhoto={k: {p: dict(targets=len(R[p]['inScope']), found=len(R[p]['hitIds']), false=R[p]['classes'].count('false')) for p in photos} for k, R in res.items()},
                perPhotoClasses=res, inputs=FR['hashes'])


if __name__ == '__main__':
    o = main(sys.argv[1], sys.argv[2]); json.dump(o, open(sys.argv[3], 'w'))
    for k, t in o['table'].items(): print(f"{k:28s} {t['found']}/{t['of']} false {t['false']} dup {t['duplicate']} unc {t['onUncertain']} nonSkin {t['nonSkin']} unrevOval {t['unreviewedInOval']} unrevPh {t['unreviewedPhoto']} +{t['gainedVsStep0']}/-{t['lostVsStep0']} sets {t['bySet']} fs {t['falseBySet']}")
    for k, L in o['lostByFilter'].items(): print(k, len(L), [(x['target'], x['reasons'], x['boxSideOverFaceWidth']) for x in L])
    print(o['rejectionReasons']); print(o['clear'])
