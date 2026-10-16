"""Run the layer-1 comparison for Step0 + all verified third-party records; write photo-free results.
Usage: relabel_run.py <workdir>  (expects pack/, layer1/masks/, lm-*.jsonl, step0/*.jsonl, regen/regen-rows.json,
regen/keras-rows.json, regen/regen-rows-verify.json, acne-point-eval-results-20261016.json)"""
import json, random, sys
from pathlib import Path
import numpy as np
import relabel_compare as RC

LAYER1_SHA = 'fa1be5b4c8e982861e8470dbe3b764ae3e5e4f50cef4a652e5efed05d175cda0'
SAME_WEIGHTS = {'unzelanoor-app': 'unzelanoor'}   # same file, second class mapping: not an independent model
SAME_DATA = {'drpauloreis-onnx': 'tinny-robot'}   # different weights trained on the same Kaggle acneda1 data


def boot_diff(a, b, photos, n=5000, seed=0):
    rnd = random.Random(seed); d = []
    for _ in range(n):
        s = [rnd.choice(photos) for _ in photos]; d.append(sum(a[p] for p in s) - sum(b[p] for p in s))
    d.sort(); return [d[int(.025 * n)], d[int(.975 * n) - 1]]


def main(W):
    W = Path(W)
    step0 = {}
    for f in ('step0/dev.jsonl', 'step0/devext.jsonl'):
        for l in open(W / f): r = json.loads(l); step0[r['sha256']] = dict(sha=r['sha256'], final=r['final'])
    man = json.load(open(W / 'pack/manifest.json'))
    records = {'step0/product-chain': [step0[i['sha256']] for i in man]}
    regen = json.load(open(W / 'regen/regen-rows.json')); keras = json.load(open(W / 'regen/keras-rows.json'))
    regen.update({f'aldinnasrun-kerascv/{m}': r for m, r in keras.items()})
    ver = json.load(open(W / 'regen/regen-rows-verify.json'))
    excluded = {k: v for k, v in ver.items() if not v['exact']}
    for k, v in regen.items():
        if ver[k]['exact']: records[k] = v
    res, L1, masks, ovals = RC.run(W / 'acne-point-relabel-layer1-20261016.json', W / 'layer1/masks', [W / 'lm-dev.jsonl', W / 'lm-devext.jsonl'], records, LAYER1_SHA)
    photos = sorted(L1); reviewed = [p for p in photos if masks[p].any()]
    revPx = int(sum(masks[p].sum() for p in photos))
    base = {p: res['step0/product-chain']['perPhoto'][p]['r3']['hits'] for p in photos}
    old = json.load(open(W / 'acne-point-eval-results-20261016.json'))['results']
    table = {}
    for k, v in res.items():
        s3 = v['summary']['r3']; hp = {p: v['perPhoto'][p]['r3']['hits'] for p in photos}
        fpp = {p: sum(c == 'falseReviewed' for c in v['perPhoto'][p]['r3']['classes']) for p in photos}
        loo = {p: (sum(hp.values()) - hp[p]) - (sum(base.values()) - base[p]) for p in photos}
        diff = sum(hp.values()) - sum(base.values())
        top = max(photos, key=lambda p: abs((hp[p] - base[p])))
        table[k] = dict(model=k.split('/')[0], mode=k.split('/')[1], sameWeightsAs=SAME_WEIGHTS.get(k.split('/')[0]), sameDataAs=SAME_DATA.get(k.split('/')[0]),
                        targets=s3['targets'], hits_r3=s3['hits'], hits_r2=v['summary']['r2']['hits'], hits_r5=v['summary']['r5']['hits'],
                        preds=s3['preds'], falseReviewed=s3['falseReviewed'], falsePerReviewedMP=round(s3['falseReviewed'] / (revPx / 1e6), 2),
                        falsePerReviewedPhoto=round(s3['falseReviewed'] / len(reviewed), 2),
                        duplicates=s3['duplicate'], onUncertain=s3['onUncertain'], onOther=s3['onOther'], onOtherByCat=s3['onOtherByCat'],
                        unreviewedInOval=s3['unreviewedInOval'], outsideOval=s3['outsideOval'], unreviewedPhoto=s3['unreviewedPhoto'],
                        hitsPerPhoto=hp, falsePerPhoto=fpp,
                        diffVsStep0=diff, diffVsStep0_boot95=boot_diff(hp, base, photos) if k != 'step0/product-chain' else None,
                        diffWithoutMostInfluentialPhoto=min(loo.values(), key=lambda x: abs(x)) if k != 'step0/product-chain' else None,
                        mostInfluentialPhoto=dict(photo=top, modelHits=hp[top], step0Hits=base[top], targets=v['perPhoto'][top]['r3']['targets']),
                        leaveOneOutDiffRange=[min(loo.values()), max(loo.values())] if k != 'step0/product-chain' else None,
                        old=dict(pointInSourceBox=old[k]['summary']['point'] if k in old else None, iou50=old[k]['summary']['iou50'] if k in old else None,
                                 iou30=old[k]['summary']['iou30'] if k in old else None, of=201))
    # source-label agreement (layer-1 frozen; source boxes opened only now)
    agree = {}
    for it in man:
        ph = it['sha256'][:12]
        if ph not in L1: continue
        pts = L1[ph]['points']; B = it['positive']; mk = masks[ph]
        box_rows = []
        for i, b in enumerate(B):
            inn = [p for p in pts if b[0] <= p['x'] <= b[2] and b[1] <= p['y'] <= b[3]]
            cats = sorted({p['cat'] for p in inn})
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            if 'TARGET' in cats: c = 'contains TARGET' + (' (x%d)' % sum(p['cat'] == 'TARGET' for p in inn) if sum(p['cat'] == 'TARGET' for p in inn) > 1 else '')
            elif 'UNCERTAIN' in cats: c = 'UNCERTAIN only'
            elif cats: c = 'other category: ' + ','.join(cats)
            elif not mk.any(): c = 'nothing marked; photo has no reviewed mask'
            elif RC.inside(mk, (cx, cy)): c = 'nothing marked; centre in reviewed skin'
            else: c = 'nothing marked; centre outside reviewed skin'
            side = max(b[2] - b[0], b[3] - b[1]); box_rows.append(dict(box=i, sidePx=round(side, 1), sideOverFaceWidth=round(side / L1[ph]['faceWidthPx'], 4), result=c))
        tg = [p for p in pts if p['cat'] == 'TARGET']
        missing = [p['id'] for p in tg if not any(b[0] <= p['x'] <= b[2] and b[1] <= p['y'] <= b[3] for b in B)]
        agree[ph] = dict(set=it['set'], sourceBoxes=len(B), layer1Targets=len(tg), targetsWithoutSourceBox=missing, boxes=box_rows)
    out = dict(protocol='acne-point-relabel-protocol-1', layer1SHA256=LAYER1_SHA, reviewedMaskPx=revPx, reviewedPhotos=reviewed,
               photos=photos, excludedRecords=excluded, table=table, sourceAgreement=agree,
               perPhotoDetail={k: {p: {kk: v['perPhoto'][p]['r3'][kk] for kk in ('targets', 'hits', 'hitIds', 'classes')} for p in photos} for k, v in res.items()})
    json.dump(out, open(W / 'relabel-results.json', 'w'))
    return out, res


if __name__ == '__main__':
    out, _ = main(sys.argv[1])
    for k, t in sorted(out['table'].items(), key=lambda kv: -kv[1]['hits_r3']):
        print(f"{k:28s} hit {t['hits_r3']:3d}/{t['targets']} (r2 {t['hits_r2']}, r5 {t['hits_r5']}) FP {t['falseReviewed']:3d} dup {t['duplicates']:3d} unc {t['onUncertain']:3d} oth {t['onOther']:2d} unrevOval {t['unreviewedInOval']:3d} outOval {t['outsideOval']:3d} unrevPh {t['unreviewedPhoto']:3d} diff {t['diffVsStep0']:+d} {t['diffVsStep0_boot95']} loo {t['leaveOneOutDiffRange']} old {t['old']['pointInSourceBox']}")
    print('excluded', list(out['excludedRecords']))
