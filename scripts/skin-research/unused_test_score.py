"""Score Step0 / v1 / v3 on the unused test with the DEV counting rules (common_scope_compare.classify: source-pixel centres, r = .03 fw,
deterministic one-to-one matching). Photo-cluster and person-cluster bootstrap CIs (10,000, seed 20261016). Writes docs JSON (photo-free)."""
import json, sys
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; O = CODE / 'audit-results/acne-unused-test'
sys.path[:0] = [str(HERE / 'external_acne')]
import relabel_compare as RC, common_scope_compare as CS
CL = ['matched', 'false', 'duplicate', 'onUncertain', 'onOther', 'nearOutOfScopeTarget', 'unreviewedInOval', 'nonSkin', 'unreviewedPhoto']
TERT = (588.4, 899.2333333333333)


def main():
    lab = json.loads((O / 'labels-frozen.json').read_text()); rp = {json.loads(l)['sha256']: json.loads(l) for l in open(O / 'replay.jsonl')}
    el = json.loads((O / 'eligibility.json').read_text()); photos = sorted(lab['photos'])
    rec = {ph: json.loads((O / 'infer' / f'{ph}.json').read_text()) for ph in photos}
    preds = {'Step0': {ph: [b[:4] for b in rec[ph]['final']] for ph in photos}}
    for k in ('v1', 'v3'): preds[k] = {ph: [b[:4] for b, kk in zip(rec[ph]['final'], rec[ph]['verifiers'][k]['keep']) if kk] for ph in photos}
    res = {}
    for n, P in preds.items():
        res[n] = {}
        for ph in photos:
            L = lab['photos'][ph]; L['points'] = [dict(p, x=float(p['x']), y=float(p['y'])) for p in L['points']]
            r = rp[L['sha256']]; img_hw = cv2.imread(str(O / 'masks' / f'{ph}.png'), cv2.IMREAD_GRAYSCALE)
            res[n][ph] = CS.classify(L, P[ph], img_hw > 0, RC.oval_mask(r, img_hw.shape[1], img_hw.shape[0]), .03 * L['faceWidthPx'])
    per = {ph: dict(pose=el['status'][lab['photos'][ph]['sha256']]['pose'], faceWidthPx=lab['photos'][ph]['faceWidthPx'],
                    **{n: dict(points=len(preds[n][ph]), **{c: res[n][ph]['classes'].count(c) for c in CL}, found=len(res[n][ph]['hitIds'])) for n in preds}) for ph in photos}
    tab = {}
    for n in preds:
        fp = [per[p][n]['false'] for p in photos]
        tab[n] = dict(photos=len(photos), targets=sum(len(res[n][p]['inScope']) for p in photos), found=sum(per[p][n]['found'] for p in photos),
                      points=sum(per[p][n]['points'] for p in photos), falseTotal=sum(fp), falseMeanPerPhoto=round(float(np.mean(fp)), 3), falseMedianPerPhoto=float(np.median(fp)),
                      **{c: sum(per[p][n][c] for p in photos) for c in CL if c not in ('false',)})
    pc = json.loads((O / 'labels-frozen.json').read_text())['personClusters']['clusters']; pid = {ph: ph for ph in photos}
    for c in pc:
        for ph in c: pid[ph] = c[0]
    rng = np.random.default_rng(20261016)
    def boot(a, b, key, clusters):
        units = sorted(set(clusters.values())); d = {u: sum(per[p][b][key] - per[p][a][key] for p in photos if clusters[p] == u) for u in units}
        arr = np.array([d[u] for u in units]); s = [arr[rng.integers(0, len(arr), len(arr))].sum() for _ in range(10000)]
        return dict(delta=int(arr.sum()), ci95=[float(x) for x in np.percentile(s, [2.5, 97.5])], units=len(units))
    ci = {f'{b}-{a} {k}': dict(photo=boot(a, b, k, {p: p for p in photos}), person=boot(a, b, k, pid)) for a, b in (('Step0', 'v1'), ('Step0', 'v3'), ('v1', 'v3')) for k in ('false', 'points', 'found')}
    sub = {}
    for name, f in (('FRONT', lambda p: per[p]['pose'] == 'FRONT'), ('side (LEFT/RIGHT)', lambda p: per[p]['pose'] != 'FRONT'),
                    ('fw tertile 0 (<588 px)', lambda p: per[p]['faceWidthPx'] < TERT[0]), ('fw tertile 1', lambda p: TERT[0] <= per[p]['faceWidthPx'] < TERT[1]), ('fw tertile 2 (>=899 px)', lambda p: per[p]['faceWidthPx'] >= TERT[1])):
        ps = [p for p in photos if f(p)]
        sub[name] = dict(photos=len(ps), **{n: dict(points=sum(per[p][n]['points'] for p in ps), false=sum(per[p][n]['false'] for p in ps)) for n in preds})
    removed = {}
    for k in ('v1', 'v3'):
        removed[k] = []
        for ph in photos:
            cl = dict(zip([tuple(b[:4]) for b in rec[ph]['final']], res['Step0'][ph]['classes']))
            for b, kk, p in zip(rec[ph]['final'], rec[ph]['verifiers'][k]['keep'], rec[ph]['verifiers'][k]['proba']):
                if not kk: removed[k].append(dict(photo=ph, box=b[:4], proba=round(p, 4), classUnderStep0=cl[tuple(b[:4])]))
    cost = dict(chainSecMedian=float(np.median([rec[p]['chainSec'] for p in photos])), chainSecMax=float(max(rec[p]['chainSec'] for p in photos)),
                verifierSecMax={k: float(max(rec[p]['verifiers'][k]['sec'] for p in photos)) for k in ('v1', 'v3')},
                featureBytesMax=int(max(rec[p]['featureBytes'] or 0 for p in photos)), maxRssMiB=float(max(rec[p]['maxRssMiB'] for p in photos)))
    out = dict(table=tab, targetsV3vsV1=dict(gained=[], lost=[], note='no TARGET exists in this set'), CI95=ci, subgroups=sub, perPhoto=per, removed=removed, cost=cost,
               candidatesPerPhoto={ph: len(rec[ph]['final']) for ph in photos},
               notEvaluated=dict(statusCounts=el['statusCounts'], groups=el['groups'], groupsWithoutEligiblePhoto=len(el['groupsWithoutEligiblePhoto'])))
    (CODE / 'docs/acne-unused-test-results-20261016.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ('perPhoto',)}, indent=1))


if __name__ == '__main__': main()
