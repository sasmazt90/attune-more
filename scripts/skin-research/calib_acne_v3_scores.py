"""Score-vs-discrimination check for Step0 and the corrected step-300 (no training).

Phases
  register  freeze the sample, the discrimination rule and the calibration procedure BEFORE any raw score is computed
  raw       raw (pre-confidence) anchors on the frozen TRAIN sample: 20 positive photos (first 20 of the v2 trainProbe rule)
            and the 9 reviewed TRAIN negative photos with known clean pixels (their 41 product tiles); resumable per photo
  analyse   ranking, per-target loss stage at conf .30, discrimination verdict, TRAIN-only threshold per the frozen procedure
  dev       ONLY if discrimination is preserved: unchanged v2 product chain on the development set (Scope B + controls) with
            the frozen calibrated threshold (infer_tiles copied verbatim except the confidence literal; parity checked at .30)
Unlabeled skin is never negative: negative candidates count only with their centre inside the reviewed clean mask.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; TOGG = CODE.parent
OUT = CODE / 'audit-results/acne-v3-20261015/calibration'
MODELS = {'step0': None, 'fix300': CODE / 'audit-results/acne-v3-20261015/v3/fix-step-000300/model.safetensors'}
FLOOR, NMS_T = .001, .30
GRID = [.001, .002, .005, .01, .02, .03, .05, .07, .1, .15, .2, .3]
RULES = dict(
    sample='positives: first 20 photos of the v2 trainProbe rule (first distinct TRAIN photos of pilotOrder with a replay snapshot); '
           'negatives: the 9 reviewed TRAIN negative photos with known clean pixels (41 product tiles). TRAIN only; fixed before any raw score.',
    raw='every anchor of every product tile, obj*cls >= .001 kept, boxes mapped to source pixels exactly as infer_tiles',
    negatives='product _nms(.30) over clean-photo candidates; a candidate is negative only if its centre lies in the reviewed strict clean mask; elsewhere ignored',
    targetScore='per target: best IoU of any kept anchor; best obj*cls among anchors with IoU>=.50 (and >=.30), with its obj, cls and IoU',
    lossStage='at conf .30 for targets missed by the saved final product output: localization (no kept anchor IoU>=.50) | score (IoU>=.50 anchor exists, best score <.30) | '
              'NMS (>=.30 anchor with IoU>=.50 exists but none survives product _nms .30) | filter (survives NMS, absent from final product boxes)',
    discrimination='AUC(target best score @IoU>=.50, 0 if none, vs negative candidate scores); localization capacity = share of targets with a kept anchor IoU>=.50. '
                   'PRESERVED iff AUC_fix300 >= AUC_step0 - .05 AND capacity_fix300 >= capacity_step0 - .05',
    calibration='same for both models, TRAIN only: smallest t in GRID with mean negative candidates per negative photo (score>=t) <= 1.0 '
                '(the frozen CDC gate limit); none -> .30. No per-photo thresholds, no score normalisation.',
    dev='only if PRESERVED: Scope B + product-valid controls through the unchanged v2 chain at each model\'s frozen t; IoU .50 primary, .30 separate; '
        'the .30 confidence results stay as recorded; no re-tuning after seeing development results',
    unchanged='IoU rules, acceptance (acceptance.json 90dc84fa..., 2026-10-10), production accepted:false, sealed Skin care v5 test')


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def setup():
    sys.path[:0] = [str(HERE)]
    import run_acne_v2_pilot as v2
    v2.setup_paths(CODE, TOGG); return v2


def net_for(v2, name):
    from safetensors.torch import load_file
    net = v2.build_net(TOGG)
    if MODELS[name] is not None: net.load_state_dict(load_file(str(MODELS[name])), strict=True)
    return net.eval()


def sample(v2):
    man = v2.read_json(CODE / 'docs/acne-data-v2-manifest-20261015.json')
    replay = {json.loads(l)['sha256']: json.loads(l) for l in (CODE / 'audit-results/acne-data-v2-20261015/replay.jsonl').read_text('utf8').splitlines() if l.strip()}
    photos = {p['sha256']: p for p in man['photos']}; seen, probe = set(), []
    for k in man['pilotOrder']:
        s = man['tiles'][k]['sha256']
        if s in seen or s not in photos: continue
        seen.add(s)
        if replay.get(s, {}).get('snapshot'): probe.append(s)
        if len(probe) == 40: break
    pos = probe[:20]
    negs = sorted({t['sha256'] for t in man['tiles'] if t['kind'] == 'negative'})
    return man, pos, negs


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.


def raw_tiles(net, bgr, rects):
    import torch
    rows = []
    with torch.inference_mode():
        for (a, b, c, d) in rects:
            tile = np.full((384, 384, 3), 114, np.uint8); patch = bgr[b:d, a:c]; tile[:patch.shape[0], :patch.shape[1]] = patch
            out = net(torch.from_numpy(tile.transpose(2, 0, 1).copy()).float()[None])[0].numpy()
            sc = out[:, 4] * out[:, 5]
            for i in np.where(sc >= FLOOR)[0]:
                cx, cy, bw, bh, ob, cl = out[i].tolist()
                box = [max(a, cx + a - bw / 2), max(b, cy + b - bh / 2), min(c, cx + a + bw / 2), min(d, cy + b + bh / 2)]
                if box[2] > box[0] and box[3] > box[1]: rows.append(box + [float(sc[i]), ob, cl])
    return rows


def phase_raw(v2, max_seconds):
    import cv2
    from acne_takeover_support import strict_clean_mask
    from skin_models import _nms
    from prepare_acne_data_v2 import map_windows
    man, pos, negs = sample(v2); pre = v2.read_json(OUT / 'calibration-preregistration.json')
    if pre['positives'] != pos or pre['negatives'] != negs: raise RuntimeError('SAMPLE_CHANGED')
    inv = v2.read_json(CODE.parent / 'attune-claude-acne-audit/audit-results/acne-data-v2-20261015/inventory.json')
    paths = {i['sha256']: map_windows(i['absolutePath'], TOGG) for i in inv['items'] + inv['negatives']}
    live = TOGG / 'attune-live-test' / v2.TAKEOVER
    ledger = {r['sha256']: r for r in v2.read_json(live / 'inputs/original-reviewed-detector-data.json')['rows']}
    photos = {p['sha256']: p for p in man['photos']}
    rects = {}
    for t in man['tiles']: rects.setdefault(t['sha256'], []).append(t['rect'])
    t0 = time.monotonic()
    for name in MODELS:
        sink_p = OUT / f'raw-{name}.jsonl'; done = {json.loads(l)['sha256'] for l in sink_p.read_text().splitlines()} if sink_p.exists() else set()
        todo = [s for s in pos + negs if s not in done]
        if not todo: continue
        net = net_for(v2, name)
        with sink_p.open('a') as sink:
            for s in todo:
                if time.monotonic() - t0 > max_seconds: return False
                bgr = cv2.imread(str(paths[s])); raw = raw_tiles(net, bgr, rects[s])
                if s in pos:
                    truth = [t['box'] for t in photos[s]['targets']]; tg = []
                    for T in truth:
                        best = max((iou(T, r[:4]) for r in raw), default=0.)
                        rec = dict(bestIoU=round(best, 4))
                        for thr in (.5, .3):
                            m = [r for r in raw if iou(T, r[:4]) >= thr]
                            if m:
                                r = max(m, key=lambda r: r[4]); rec[f'iou{int(thr*100)}'] = dict(score=r[4], obj=r[5], cls=r[6], iou=round(iou(T, r[:4]), 4))
                        tg.append(rec)
                    hi = [r for r in raw if r[4] >= .30]
                    kept = _nms([r[:5] for r in hi], threshold=NMS_T) if hi else []
                    for T, rec in zip(truth, tg): rec['survivesNMS30'] = any(iou(T, k[:4]) >= .5 for k in kept)
                    sink.write(json.dumps(dict(sha256=s, kind='positive', targets=tg, rawKept=len(raw))) + '\n')
                else:
                    sup = cv2.imread(str(live / 'train-clean-support' / (s + '.png')), cv2.IMREAD_GRAYSCALE)
                    mask, _ = strict_clean_mask(ledger[s], bgr, reviewed_support=sup)
                    sel = _nms([r[:5] for r in raw], threshold=NMS_T) if raw else []
                    look = {tuple(r[:5]): r for r in raw}; neg = []
                    for k in sel:
                        cx, cy = int((k[0] + k[2]) / 2), int((k[1] + k[3]) / 2)
                        if 0 <= cy < mask.shape[0] and 0 <= cx < mask.shape[1] and mask[cy, cx] > 0:
                            r = look[tuple(k)]; neg.append(dict(score=r[4], obj=r[5], cls=r[6], side=round(max(r[2] - r[0], r[3] - r[1]), 1)))
                    sink.write(json.dumps(dict(sha256=s, kind='negative', candidates=neg, rawKept=len(raw), cleanPixels=int((mask > 0).sum()))) + '\n')
                sink.flush(); print(name, s[:8], flush=True)
    return True


def auc(p, n):
    if not p or not n: return None
    n = np.sort(np.asarray(n)); tot = 0.
    for x in p: tot += np.searchsorted(n, x, 'left') + .5 * (np.searchsorted(n, x, 'right') - np.searchsorted(n, x, 'left'))
    return float(tot / (len(p) * len(n)))


def phase_analyse(v2):
    import collections
    pre = v2.read_json(OUT / 'calibration-preregistration.json')
    final = {}
    for name, fn in (('step0', 'v3prod-step0'), ('fix300', 'v3prod-fix-step-000300')):  # saved final product outputs (trainProbe)
        rows = [json.loads(l) for l in (CODE / f'audit-results/acne-v3-20261015/evaluation-{fn}.jsonl').read_text().splitlines()]
        final[name] = {r['sha256']: set(r.get('matched', [])) for r in rows if r['set'] == 'trainProbe'}
    res = {}
    for name in MODELS:
        rows = [json.loads(l) for l in (OUT / f'raw-{name}.jsonl').read_text().splitlines()]
        P = [r for r in rows if r['kind'] == 'positive']; N = [r for r in rows if r['kind'] == 'negative']
        assert sorted(r['sha256'] for r in P) == sorted(pre['positives']) and sorted(r['sha256'] for r in N) == sorted(pre['negatives'])
        tscore = [t.get('iou50', {}).get('score', 0.) for r in P for t in r['targets']]
        nscore = [c['score'] for r in N for c in r['candidates']]
        stage = collections.Counter()
        for r in P:
            got = final[name][r['sha256']]
            for i, t in enumerate(r['targets']):
                if i in got: stage['found'] += 1
                elif 'iou50' not in t: stage['localization'] += 1
                elif t['iou50']['score'] < .30: stage['score'] += 1
                elif not t['survivesNMS30']: stage['NMS'] += 1
                else: stage['filter'] += 1
        q = lambda v, x: round(float(np.percentile(v, x)), 4) if v else None
        m50 = [t['iou50'] for r in P for t in r['targets'] if 'iou50' in t]
        res[name] = dict(
            targets=len(tscore), negativePhotos=len(N), negativeCandidates=len(nscore),
            localizationCapacity=round(sum(1 for r in P for t in r['targets'] if 'iou50' in t) / len(tscore), 4),
            AUC=(round(auc(tscore, nscore), 4) if nscore else None),  # None: no negative candidate >= floor inside clean masks
            targetBestScoreIoU50=dict(median=q(tscore, 50), p25=q(tscore, 25), p75=q(tscore, 75)),
            matchedAnchorObj=dict(median=q([m['obj'] for m in m50], 50)), matchedAnchorCls=dict(median=q([m['cls'] for m in m50], 50)),
            matchedAnchorIoU=dict(median=q([m['iou'] for m in m50], 50)),
            targetsBelow30WithIoU50Anchor=sum(1 for s, r in ((t.get('iou50', {}).get('score'), t) for p in P for t in p['targets']) if s is not None and s < .30),
            negativeScore=dict(max=round(max(nscore), 4) if nscore else None, p99=q(nscore, 99), p90=q(nscore, 90), median=q(nscore, 50)),
            targetsAboveMaxNegative=sum(1 for s in tscore if nscore and s > max(nscore)),
            lossStageAt30=stage)
        curve = []
        for t in GRID:
            fp = sum(1 for s in nscore if s >= t) / len(N); rec = sum(1 for s in tscore if s >= t) / len(tscore)
            curve.append(dict(t=t, negPerPhoto=round(fp, 3), targetRecallIoU50=round(rec, 4)))
        ok = [c for c in curve if c['negPerPhoto'] <= 1.0]
        res[name]['trainCurve'] = curve; res[name]['calibratedThreshold'] = min(c['t'] for c in ok) if ok else .30
    a, b = res['step0'], res['fix300']
    if a['AUC'] is None or b['AUC'] is None:
        verdict = 'NOT_COMPUTABLE_UNDER_REGISTERED_RULE (AUC undefined: ' + ','.join(n for n, v in res.items() if v['AUC'] is None) + ' has no negative candidate >= floor)'
    else:
        verdict = 'PRESERVED' if (b['AUC'] >= a['AUC'] - .05 and b['localizationCapacity'] >= a['localizationCapacity'] - .05) else 'DEGRADED'
    out = dict(rulesSHA256=sha(OUT / 'calibration-preregistration.json'), discrimination=verdict, models=res)
    (OUT / 'analysis.json').write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase'); ap.add_argument('--max-seconds', type=float, default=110)
    a = ap.parse_args(); v2 = setup(); OUT.mkdir(parents=True, exist_ok=True)
    if a.phase == 'register':
        p = OUT / 'calibration-preregistration.json'
        if p.exists(): raise SystemExit('FROZEN')
        man, pos, negs = sample(v2)
        p.write_text(json.dumps(dict(rules=RULES, grid=GRID, floor=FLOOR, positives=pos, negatives=negs, codeSHA256=sha(__file__),
                                     models={k: (sha(v) if v else v2.STEP0_SHA256) for k, v in MODELS.items()}), indent=1)); print(sha(p), len(pos), len(negs))
    elif a.phase == 'raw':
        from heavy_job_lease import HeavyJobLease
        with HeavyJobLease('CLAUDE-acne-v3-calib-raw', peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
            print('complete' if phase_raw(v2, a.max_seconds) else 'partial')
    elif a.phase == 'analyse': phase_analyse(v2)
