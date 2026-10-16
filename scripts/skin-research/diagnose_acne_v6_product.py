"""Acne v6 diagnostic: Step0 / V5 step-150 / V6 pilot step-150 on the UNCHANGED v2 product chain (saved rows only; no inference here).

Groups exactly as compare_acne_v4_product.py: Scope B positives (14 targets), product-valid controls (29), held-out development
group (unusedEval; 95 targets; replay pass with the eyewear gate UNKNOWN - not a full product preflight pass), reviewed negatives
(Scope B photos with 0 targets; clean-mask false candidates). trainProbe rows are TRAIN photos and are not reported.
Truth = source labels of the v2 evaluator (DEV targets were NOT engineering-reviewed). Unlabeled candidates are reported in their own
column and are never counted as right or wrong.

Loss breakdown (V6 misses at IoU .50), from the label-free intermediate outputs recorded during the single V6 run
(v3prod-v6pilot-step-000150-raw.jsonl), first matching category wins:
  matched-elsewhere   a final box has IoU >= .50 with the target but one-to-one gave it to another target
  final-misplaced     best final box IoU in [.30, .50)  (area ratio recorded)
  filter-removed      an NMS-selected box has IoU >= .50 but did not survive the anatomical/staging filter
  nms-suppressed      a >= .30 confidence candidate has IoU >= .50 but was not NMS-selected
  below-score         a raw head box (obj*cls in [.01, .30)) has IoU >= .50
  raw-misplaced       best box at any stage has IoU in [.30, .50) only (too large / badly placed)
  no-box              no box at any stage with IoU >= .30 (raw boxes below .01 are not recorded)
"""
import json, statistics as st, sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parent)]
import compare_acne_v3_product as C
A = C.out
MODELS = {'Step0': 'v3prod-step0', 'V5 step-150': 'v3prod-v5main-step-000150', 'V6 pilot step-150': 'v3prod-v6pilot-step-000150'}
side = lambda b: max(b[2] - b[0], b[3] - b[1]); area = lambda b: max(1e-6, (b[2] - b[0]) * (b[3] - b[1]))


def load(fn, raw=False):
    rows = [json.loads(l) for l in (A / f'evaluation-{fn}.jsonl').read_text().splitlines()]
    boxes = [json.loads(l) for l in (A / f'{fn}-boxes.jsonl').read_text().splitlines()]
    raws = [json.loads(l) for l in (A / f'{fn}-raw.jsonl').read_text().splitlines()] if raw else None
    res, k = {}, 0
    for r in rows:
        setn = r['set']; ran = 'candidates' in r; b = boxes[k] if ran else None; rw = raws[k] if (ran and raws) else None; k += ran
        if ran: assert len(b['boxes']) == r['candidates'], 'ALIGN'
        T = C.truth(r, setn) if ran else []
        res[(setn, r['sha256'])] = dict(cohort=r.get('cohort', setn), ran=ran, valid=r.get('valid', True), T=T, pairs=r.get('pairs', []),
                                        m50=set(r['matched']) if ran else set(), m30=C.o2o(T, b['boxes'], .30) if ran else set(), P=b['boxes'] if b else [],
                                        cleanFP=r.get('cleanFP', 0), unknown=r.get('unknownCandidates', 0), cand=r.get('candidates', 0),
                                        sec=b['totalSec'] if b else None, infer=b.get('inferSec') if b else None, raw=rw, neg=setn == 'development' and r['targets'] == 0,
                                        ids=r.get('targetIds'))
    assert k == len(boxes)
    return res


GROUPS = {'Scope B positives': lambda k, a: a['cohort'] == 'scopeB' and not a['neg'], 'Product controls': lambda k, a: a['cohort'] == 'controls',
          'Held-out development (eyewear UNKNOWN)': lambda k, a: k[0] == 'unusedEval', 'Reviewed negatives': lambda k, a: a['cohort'] == 'scopeB' and a['neg']}


def placement(R, keys):
    """Median predicted/target area ratio and centre offset (in target sides) over one-to-one matches at IoU .30."""
    ar, off = [], []
    for k in keys:
        a = R[k]; T, P = a['T'], a['P']
        pr = sorted(((C.iou(t, p), i, j) for i, t in enumerate(T) for j, p in enumerate(P)), reverse=True); ut, up = set(), set()
        for v, i, j in pr:
            if v < .3: break
            if i in ut or j in up: continue
            ut.add(i); up.add(j); t, p = T[i], P[j]; ar.append(area(p) / area(t))
            off.append(((((p[0] + p[2]) - (t[0] + t[2])) / 2) ** 2 + (((p[1] + p[3]) - (t[1] + t[3])) / 2) ** 2) ** .5 / max(1e-6, side(t)))
    return dict(n=len(ar), medianAreaRatio=round(st.median(ar), 3) if ar else None, shareAreaRatioAbove1_5=round(sum(x > 1.5 for x in ar) / len(ar), 2) if ar else None,
                medianCentreOffsetSides=round(st.median(off), 3) if off else None)


def classify(a, i):
    t = a['T'][i]; rw = a['raw']; best = lambda L: max((C.iou(t, b[:4]) for b in L), default=0.)
    if best(a['P']) >= .5: return 'matched-elsewhere', None
    bf = best(a['P'])
    if bf >= .3:
        p = max(a['P'], key=lambda b: C.iou(t, b)); return 'final-misplaced', round(area(p) / area(t), 2)
    if best(rw['nmsSelected']) >= .5: return 'filter-removed', None
    if best(rw['confCandidates']) >= .5: return 'nms-suppressed', None
    if best(rw['raw']) >= .5: return 'below-score', round(max(b[4] for b in rw['raw'] if C.iou(t, b[:4]) >= .5), 3)
    allb = rw['raw'] + rw['confCandidates'] + rw['nmsSelected']
    if best(allb) >= .3:
        p = max(allb, key=lambda b: C.iou(t, b[:4])); return 'raw-misplaced', round(area(p) / area(t), 2)
    return 'no-box', None


def main():
    R = {m: load(fn, raw=(m.startswith('V6'))) for m, fn in MODELS.items()}
    S = R['Step0']; out = dict(groups={}, gainedLost={}, lossBreakdown={}, notes=__doc__)
    for g, f in GROUPS.items():
        keys = [k for k, a in S.items() if f(k, a) and a['ran'] and a['valid']]; row = dict(photos=len(keys))
        for m, Rm in R.items():
            sm = [(k, i) for k in keys for i, t in enumerate(Rm[k]['T']) if side(t) < 16]; md = [(k, i) for k in keys for i, t in enumerate(Rm[k]['T']) if side(t) >= 16]
            row[m] = dict(targets=sum(len(Rm[k]['T']) for k in keys), hit50=sum(len(Rm[k]['m50']) for k in keys), hit30=sum(len(Rm[k]['m30']) for k in keys),
                          small50=f"{sum(i in Rm[k]['m50'] for k, i in sm)}/{len(sm)}", medium50=f"{sum(i in Rm[k]['m50'] for k, i in md)}/{len(md)}",
                          small30=f"{sum(i in Rm[k]['m30'] for k, i in sm)}/{len(sm)}", medium30=f"{sum(i in Rm[k]['m30'] for k, i in md)}/{len(md)}",
                          reviewedNegFP=sum(Rm[k]['cleanFP'] for k in keys), fpPerPhoto=[Rm[k]['cleanFP'] for k in keys] if g == 'Reviewed negatives' else None,
                          unlabeledCandidates=sum(Rm[k]['unknown'] for k in keys), finalCandidates=sum(Rm[k]['cand'] for k in keys),
                          placement=placement(Rm, keys) if g != 'Reviewed negatives' else None,
                          medianTotalSec=round(st.median([Rm[k]['sec'] for k in keys]), 2), medianInferSec=round(st.median([Rm[k]['infer'] for k in keys]), 2))
        out['groups'][g] = row
        if g == 'Reviewed negatives': continue
        for m in ('V5 step-150', 'V6 pilot step-150'):
            for thr in ('m50', 'm30'):
                gl = dict(gained=[], lost=[])
                for k in keys:
                    ids = S[k]['ids'] or list(range(len(S[k]['T'])))
                    for i in range(len(S[k]['T'])):
                        tid = f"{k[1][:12]}#{ids[i]}"
                        if i in R[m][k][thr] and i not in S[k][thr]: gl['gained'].append(tid)
                        if i in S[k][thr] and i not in R[m][k][thr]: gl['lost'].append(tid)
                out['gainedLost'].setdefault(g, {}).setdefault(m, {})[thr.replace('m', 'IoU.')] = gl
        V = R['V6 pilot step-150']; lb = dict(allMisses={}, lostVsStep0={}, details=[])
        for k in keys:
            ids = S[k]['ids'] or list(range(len(S[k]['T'])))
            for i in range(len(V[k]['T'])):
                if i in V[k]['m50']: continue
                c, x = classify(V[k], i); lost = i in S[k]['m50']
                lb['allMisses'][c] = lb['allMisses'].get(c, 0) + 1
                if lost: lb['lostVsStep0'][c] = lb['lostVsStep0'].get(c, 0) + 1
                lb['details'].append(dict(target=f"{k[1][:12]}#{ids[i]}", sidePx=round(side(V[k]['T'][i]), 1), category=c, value=x, lostVsStep0=lost))
        out['lossBreakdown'][g] = lb
    tot = lambda m: sum(out['groups'][g][m]['hit50'] for g in GROUPS if g != 'Reviewed negatives')
    out['registeredProductRuleForReference'] = {m: dict(hit50=tot(m), reviewedNegFP=out['groups']['Reviewed negatives'][m]['reviewedNegFP']) for m in R}
    (A / 'diagnosis-v6-product.json').write_text(json.dumps(out, indent=1)); print(json.dumps({g: {m: {k: v for k, v in r[m].items() if k != 'placement'} | {'placement': r[m]['placement']} for m in R} for g, r in out['groups'].items()}))
    print(json.dumps({g: {k: v for k, v in d.items() if k != 'details'} for g, d in out['lossBreakdown'].items()}))
    print(json.dumps(out['registeredProductRuleForReference']))


if __name__ == '__main__': main()
