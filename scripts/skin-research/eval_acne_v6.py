"""Acne v6 label-independent evaluation = the v5 product-preprocessing evaluator plus false candidates on frozen, reviewed clean-skin
ROIs of POSITIVE DEV photos (product-like negative regions), reported separately from the Clear negative photos.

Inference is unchanged (eval_acne_v5_independent.plan/run_photo: product decode limits -> MediaPipe -> replayed gates (eyewear UNKNOWN)
-> product crop -> native tiles -> conf .30 / NMS .30 -> product masks -> staging filter). Annotations and ROIs are read only in metrics().

Sets:
  dev     v4 DEV (95 positive + 15 Clear) - the v5 set; ROIs frozen in audit-results/acne-v6/dev17/frozen.json
  devext  additional VALIDATION-role DEV photos (audit-results/acne-v6/devext/manifest.json); ROIs frozen in acne-v6/devext/frozen.json
Phases: landmarks | replay | infer --model NAME | metrics --model NAME   (all with --set) | combined --model NAME (dev + devext pooled)
"""
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import eval_acne_v5_independent as v5

V6 = CODE / 'audit-results/acne-v6'
SETS = dict(dev=dict(out=V6 / 'eval/dev', roi=V6 / 'dev17', v5out=v5.OUT), devext=dict(out=V6 / 'eval/devext', roi=V6 / 'devext', v5out=None))
WEIGHTS = dict(v5.WEIGHTS, **{'v5-step150': CODE / 'audit-results/acne-v5-runs/main-150/model.safetensors'})


def photos(name):
    if name == 'dev':
        return [dict(p, file=str(v5.D / p['file']), mask=str(v5.D / p['mask']) if p.get('mask') else None) for p in v5.photos()]
    m = json.loads((V6 / 'devext/manifest.json').read_text()); return m['photos']


def roi_masks(name):
    import cv2
    if name == 'both':
        a, fa = roi_masks('dev'); b, fb = roi_masks('devext')
        return {**a, **b}, dict(decisionsSHA256=[fa['decisionsSHA256'], fb['decisionsSHA256']])
    fz = SETS[name]['roi'] / 'frozen.json'
    if not fz.exists(): return {}, None
    F = json.loads(fz.read_text()); out = {}
    for r in F['masks']:
        f = SETS[name]['roi'] / r['mask']; import hashlib
        assert hashlib.sha256(f.read_bytes()).hexdigest() == r['maskSHA256'], 'FROZEN ROI CHANGED'
        out[r['sha256']] = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE) > 0
    return out, F


def centre_hits(final, m):
    c = 0
    for f in final:
        cx, cy = int((f[0] + f[2]) / 2), int((f[1] + f[3]) / 2)
        if 0 <= cy < m.shape[0] and 0 <= cx < m.shape[1] and m[cy, cx]: c += 1
    return c


def metrics(rows, ph, name):
    import cv2
    v5.D = Path('/')                                    # photo paths in `ph` are absolute here
    base = v5.metrics(rows, ph)
    rois, F = roi_masks(name); per = []
    for r in rows:
        if r['kind'] == 'positive-photo' and r['status'].startswith('replay-pass') and r['sha256'] in rois:
            m = rois[r['sha256']]; per.append(dict(sha=r['sha256'][:12], roiPixels=int(m.sum()), fp=centre_hits(r['final'], m)))
    px = sum(p['roiPixels'] for p in per)
    base['posRoi'] = dict(photos=len(per), roiPixels=px, fpTotal=sum(p['fp'] for p in per), fpPerPhoto=[p['fp'] for p in per],
                          fpPerMegapixel=round(sum(p['fp'] for p in per) / (px / 1e6), 2) if px else None, frozenDecisionsSHA256=F and F['decisionsSHA256'],
                          note='positive DEV photos: final candidate centre inside the frozen, reviewed clean-skin ROI (ROI excludes every source box dilated by max(10px, side))')
    base['clearNeg'] = base.pop('neg')
    return base


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase'); ap.add_argument('--set', default='dev'); ap.add_argument('--model'); ap.add_argument('--max-seconds', type=float, default=100)
    a = ap.parse_args(); S = SETS[a.set]; OUT = S['out']; OUT.mkdir(parents=True, exist_ok=True); ph = photos(a.set)
    if a.phase == 'landmarks':
        items = OUT / 'items.json'; items.write_text(json.dumps([dict(sha256=p['sha256'], path=p['file']) for p in ph]))
        subprocess.run([str(Path.home() / 'envmp/bin/python'), str(HERE / 'acne_landmarks_v2.py'), '--task', str(v5.TASK), '--items', str(items), '--out', str(OUT / 'landmarks.jsonl')], check=True)
    elif a.phase == 'replay':
        if a.set == 'dev': shutil.copyfile(v5.OUT / 'replay.jsonl', OUT / 'replay.jsonl'); print('copied v5 replay'); sys.exit(0)
        v5.setup(); import prepare_acne_data_v2 as prep
        prep.run_replay(CODE, OUT / 'landmarks.jsonl', {p['sha256']: Path(p['file']) for p in ph}, v5.TOGG, OUT / 'replay.jsonl')
    elif a.phase == 'infer':
        sink_p = OUT / f'infer-{a.model}.jsonl'
        src = {'v5-step150': 'main-150'}.get(a.model, a.model)
        if S['v5out'] and (S['v5out'] / f'infer-{src}.jsonl').exists() and not sink_p.exists():
            shutil.copyfile(S['v5out'] / f'infer-{src}.jsonl', sink_p); print('reused unchanged v5 inference rows'); sys.exit(0)
        v2 = v5.setup(); import torch
        from safetensors.torch import load_file
        from heavy_job_lease import HeavyJobLease
        rp = {json.loads(l)['sha256']: json.loads(l) for l in (OUT / 'replay.jsonl').read_text().splitlines()}
        done = {json.loads(l)['sha256'] for l in sink_p.read_text().splitlines()} if sink_p.exists() else set()
        with HeavyJobLease('CLAUDE-acne-v6-eval-' + a.model, peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
            torch.set_num_threads(2); net = v2.build_net(v5.TOGG)
            w = WEIGHTS.get(a.model) or CODE / f'audit-results/acne-v6-runs/{a.model}/model.safetensors'
            if a.model != 'step0': net.load_state_dict(load_file(str(w)), strict=True)
            net.eval(); t0 = time.monotonic(); v5.D = Path('/')
            with sink_p.open('a') as sink:
                for p in ph:
                    if p['sha256'] in done: continue
                    if time.monotonic() - t0 > a.max_seconds: print('partial'); sys.exit(0)
                    lease.check(); row = v5.run_photo(net, p, rp[p['sha256']])
                    sink.write(json.dumps(row) + '\n'); sink.flush()
        print('complete')
    elif a.phase == 'combined':                          # dev + devext pooled (one-to-one matching stays per photo)
        rows, ph2 = [], []
        for n in ('dev', 'devext'):
            r = [json.loads(l) for l in (SETS[n]['out'] / f'infer-{a.model}.jsonl').read_text().splitlines()]; p = photos(n)
            assert len(r) == len(p), 'INCOMPLETE ' + n
            rows += r; ph2 += p
        res = metrics(rows, ph2, 'both'); o = V6 / 'eval/combined'; o.mkdir(parents=True, exist_ok=True)
        (o / f'metrics-{a.model}.json').write_text(json.dumps(res, indent=1)); print(json.dumps(res))
    elif a.phase == 'metrics':
        rows = [json.loads(l) for l in (OUT / f'infer-{a.model}.jsonl').read_text().splitlines()]
        assert len(rows) == len(ph), 'INCOMPLETE'
        res = metrics(rows, ph, a.set); (OUT / f'metrics-{a.model}.json').write_text(json.dumps(res, indent=1)); print(json.dumps(res))
