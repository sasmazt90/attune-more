"""Label-independent acne evaluation (v5) on the real product preprocessing contract.

Model input is decided ONLY from pixels: MediaPipe (product face_landmarker.task, <=640 analysis canvas) -> replayed frontend
alignment/quality/pose/snapshot (node, repo TypeScript; eyewear gate NOT replayed = UNKNOWN) -> product photo_input crop ->
native 384/288 tiles (product tile_rectangles, budget 64) -> infer_tiles (conf .30, product NMS .30) -> production prelude masks
-> principled staging filter. No rescaling: model-input pixels == source pixels. Annotations are read only by metrics().
Photos: v4 DEV positives (95) and DEV negatives (15 Clear) from manifest-v4.json; status per photo:
  replay-pass (eyewear UNKNOWN) | gate-fail:<reasons> | no-face | tile-budget | crop-invalid   (only replay-pass enters denominators)
Phases: landmarks | replay | infer --model NAME | metrics --model NAME
"""
import argparse, base64, hashlib, json, subprocess, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; TOGG = CODE.parent
D = CODE / 'audit-results/acne-v4-data'; OUT = CODE / 'audit-results/acne-v5-eval'
TASK = TOGG / 'attune-live-test/audit-results/skin-capabilities-20261008/scin/face_landmarker.task'
WEIGHTS = {'step0': None, 'v4-step1000': CODE / 'audit-results/acne-v3-20261015/v3/v4main-step-001000/model.safetensors'}


def photos():
    m = json.loads((D / 'manifest-v4.json').read_text())
    return [p for p in m['photos'] if p['role'] == 'DEV']


def setup():
    sys.path[:0] = [str(HERE)]
    import run_acne_v2_pilot as v2
    v2.setup_paths(CODE, TOGG); return v2


def plan(bgr, rp):
    """Label-free preprocessing plan. Inputs: pixels + replay row only."""
    from acne_takeover_support import tile_rectangles
    h, w = bgr.shape[:2]
    if not (16 <= w <= 4096 and 16 <= h <= 4096 and w * h <= 8_400_000): return dict(status='product-reject:PHOTO_LIMIT', rects=[])   # appearance_analysis.decode_photo
    if not rp.get('faceDetected') or not rp.get('landmarks'): return dict(status='no-face', rects=[])
    if not rp.get('gatePassedWithoutEyewear'): status = 'gate-fail:' + ','.join(rp.get('reasons') or [])
    else: status = 'replay-pass (eyewear UNKNOWN)'
    try: rects = tile_rectangles(bgr, rp['landmarks'])
    except ValueError as e: return dict(status=('tile-budget' if 'BUDGET' in str(e) else 'crop-invalid') + (' / ' + status if status.startswith('gate') else ''), rects=[])
    return dict(status=status, rects=rects)


def infer(net, bgr, rp, pl):
    """Label-free inference through the product chain. Returns final boxes (source px) and counts."""
    import cv2
    from acne_takeover_support import infer_tiles, current_product_masks
    from acne_box_support_staging import principled_accepted_boxes
    t0 = time.perf_counter(); raw, trace = infer_tiles(net, bgr, pl['rects']); t1 = time.perf_counter()
    snap = rp['snapshot']; pid = hashlib.sha256(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA).tobytes()).hexdigest(); ok, png = cv2.imencode('.png', bgr)
    payload = dict(photo='data:image/png;base64,' + base64.b64encode(png.tobytes()).decode(), photoId=pid, landmarks=rp['landmarks'], meshes=snap['meshes'],
                   exclusions=snap['exclusions'], qualityValid=rp['quality']['isValid'], conditions=dict(yaw=0, pitch=0, roll=0, scaleRatio=0))
    masks = current_product_masks(payload)
    assigned, _ = principled_accepted_boxes(raw, masks['acne_envelopes'], masks['acne_skin'], masks['hair'], masks['acne_exclusion'], pid, masks['scale'], masks['origin'],
                                            visible_regions=list(snap['meshes']), landmarks=rp['landmarks'], source_shape=bgr.shape[:2], bgr=bgr)
    final = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height'], b.get('confidence')] for v in assigned.values() for b in v]
    return dict(final=final, rawAfterNMS=len(raw), confidenceCandidates=len(trace['confidenceCandidates']), tiles=len(pl['rects']),
                inferSec=round(t1 - t0, 3), totalSec=round(time.perf_counter() - t0, 3))


def run_photo(net, p, rp):
    """One photo through the label-free chain. `p` may carry annotations; only its file path and kind are read."""
    import cv2
    bgr = cv2.imread(str(D / p['file'])); pl = plan(bgr, rp)
    row = dict(sha256=p['sha256'], kind=p['kind'], status=pl['status'], tiles=len(pl['rects']), rects=pl['rects'], final=[])
    if pl['rects'] and rp.get('snapshot'): row.update(infer(net, bgr, rp, pl))
    elif pl['rects']: row['status'] += ' / no-snapshot'
    return row


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.


def o2o(T, P, thr):
    pr = sorted(((iou(t, p), i, j) for i, t in enumerate(T) for j, p in enumerate(P)), reverse=True); ut, up, m = set(), set(), []
    for v, i, j in pr:
        if v < thr: break
        if i in ut or j in up: continue
        ut.add(i); up.add(j); m.append((i, j))
    return m


def metrics(rows, ph):
    """Annotations enter here only. Size bands: source px and model-input px are recorded separately (equal: scale 1)."""
    import cv2
    byp = {p['sha256']: p for p in ph}; out = dict(status={}, pos={}, neg={})
    for r in rows: out['status'][r['status']] = out['status'].get(r['status'], 0) + 1
    P = [r for r in rows if r['kind'] == 'positive-photo' and r['status'].startswith('replay-pass')]
    N = [r for r in rows if r['kind'] == 'negative-photo' and r['status'].startswith('replay-pass')]
    tot = dict(targets=0, hit50=0, hit30=0, small=0, smallHit50=0, medium=0, mediumHit50=0, unknown=0, final=0); ar = []
    for r in P:
        T = [b['box'] for b in byp[r['sha256']]['positive']]; F = [f[:4] for f in r['final']]
        m50 = o2o(T, F, .5); m30 = o2o(T, F, .3); h50 = {i for i, _ in m50}
        for i, t in enumerate(T):
            side_src = max(t[2] - t[0], t[3] - t[1]); side_model = side_src * 1.0   # product contract: native pixels
            k = 'small' if side_model < 16 else 'medium'; tot[k] += 1; tot[k + 'Hit50'] += i in h50
        tot['targets'] += len(T); tot['hit50'] += len(m50); tot['hit30'] += len(m30)
        ign = [b['box'] for b in byp[r['sha256']].get('ignore', [])]
        tot['unknown'] += len(F) - len({j for _, j in m30}); tot['final'] += len(F)
        ar += [(F[j][2] - F[j][0]) * (F[j][3] - F[j][1]) / max(1e-6, (T[i][2] - T[i][0]) * (T[i][3] - T[i][1])) for i, j in m30]
    fp = []
    for r in N:
        p = byp[r['sha256']]; m = cv2.imread(str(D / p['mask']), cv2.IMREAD_GRAYSCALE) > 0; c = 0
        for f in r['final']:
            cx, cy = int((f[0] + f[2]) / 2), int((f[1] + f[3]) / 2)
            if 0 <= cy < m.shape[0] and 0 <= cx < m.shape[1] and m[cy, cx]: c += 1
        fp.append(c)
    out['pos'] = dict(photos=len(P), **tot, medianAreaRatio=round(float(np.median(ar)), 3) if ar else None, sizeUnit='source px == model-input px (no rescale)',
                      medianTotalSec=round(float(np.median([r['totalSec'] for r in P])), 2) if P else None)
    out['neg'] = dict(photos=len(N), fpInMask=sum(fp), fpPerPhoto=fp, note='only replay-pass negative photos; FP = final candidate centre inside reviewed mask')
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase'); ap.add_argument('--model'); ap.add_argument('--max-seconds', type=float, default=110)
    a = ap.parse_args(); OUT.mkdir(parents=True, exist_ok=True); ph = photos()
    if a.phase == 'landmarks':
        items = OUT / 'items.json'; items.write_text(json.dumps([dict(sha256=p['sha256'], path=str(D / p['file'])) for p in ph]))
        subprocess.run([str(Path.home() / 'envmp/bin/python'), str(HERE / 'acne_landmarks_v2.py'), '--task', str(TASK), '--items', str(items), '--out', str(OUT / 'landmarks.jsonl')], check=True)
    elif a.phase == 'replay':
        v2 = setup()
        import prepare_acne_data_v2 as prep
        prep.run_replay(CODE, OUT / 'landmarks.jsonl', {p['sha256']: D / p['file'] for p in ph}, TOGG, OUT / 'replay.jsonl')
    elif a.phase == 'infer':
        v2 = setup(); import cv2, torch
        from safetensors.torch import load_file
        from heavy_job_lease import HeavyJobLease
        rp = {json.loads(l)['sha256']: json.loads(l) for l in (OUT / 'replay.jsonl').read_text().splitlines()}
        sink_p = OUT / f'infer-{a.model}.jsonl'; done = {json.loads(l)['sha256'] for l in sink_p.read_text().splitlines()} if sink_p.exists() else set()
        with HeavyJobLease('CLAUDE-acne-v5-eval-' + a.model, peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
            torch.set_num_threads(2); net = v2.build_net(TOGG)
            w = WEIGHTS.get(a.model) or CODE / f'audit-results/acne-v5-runs/{a.model}/model.safetensors'
            if a.model != 'step0': net.load_state_dict(load_file(str(w)), strict=True)
            net.eval(); t0 = time.monotonic()
            with sink_p.open('a') as sink:
                for p in ph:
                    if p['sha256'] in done: continue
                    if time.monotonic() - t0 > a.max_seconds: print('partial'); sys.exit(0)
                    lease.check(); row = run_photo(net, p, rp[p['sha256']])
                    sink.write(json.dumps(row) + '\n'); sink.flush()
        print('complete')
    elif a.phase == 'metrics':
        rows = [json.loads(l) for l in (OUT / f'infer-{a.model}.jsonl').read_text().splitlines()]
        assert len(rows) == len(ph), 'INCOMPLETE'
        res = metrics(rows, ph); (OUT / f'metrics-{a.model}.json').write_text(json.dumps(res, indent=1)); print(json.dumps(res))
