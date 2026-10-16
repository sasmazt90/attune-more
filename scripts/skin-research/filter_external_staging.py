"""Offline staging: stored detector boxes through the CURRENT Step0 post-processing (product mask prelude + staging filter).
No model inference. Protocol docs/acne-external-filter-protocol-20261016.json.
For each of the 42 pack photos (28 positive + 14 replay-pass Clear): build the same payload as eval_acne_v5_independent.infer
(photo, landmarks, snapshot meshes/exclusions, qualityValid), run current_product_masks, then principled_accepted_boxes on
  - Step0 recorded NMS boxes (positives only; parity vs stored finals) and
  - the stored external final boxes (Dewiin anyacne/tiles, tristan-gray/tiles, carsten12/tiles), adapter = [x1,y1,x2,y2,score].
Also checks the recomputed masks against the stored Step0-trace masks. Writes audit-results/acne-external-filter/results.json.
"""
import base64, hashlib, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import eval_acne_v6 as v6, eval_acne_v5_independent as v5

MODELS = ['dewiin-anyacne/tiles', 'tristan-gray/tiles', 'carsten12/tiles']


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    v5.setup(); import cv2
    import acne_takeover_support as ats
    from acne_box_support_staging import principled_accepted_boxes
    rows = json.load(open(CODE / 'audit-results/acne-relabel/acne-external-stored-rows-regen-20261016.json'))
    want = {r['sha'] for r in rows[MODELS[0]]}
    items = {}
    for s in ('dev', 'devext'):
        rp = {json.loads(l)['sha256']: json.loads(l) for l in (v6.SETS[s]['out'] / 'replay.jsonl').read_text().splitlines()}
        for p in v6.photos(s):
            if p['sha256'] not in want: continue
            f = p['file']; i = f.find('/mnt/TOGG/')
            if i >= 0: f = str(Path.home() / 'mnt') + f[i + 4:]
            assert sha(f) == p['sha256'], 'INPUT_HASH'
            items[p['sha256']] = (p['kind'], f, rp[p['sha256']])
    assert len(items) == 42, len(items)
    by = {k: {r['sha']: r['final'] for r in rows[k]} for k in MODELS}
    TR = CODE / 'audit-results/acne-step0-trace'; out = {}
    for s256, (kind, f, rp) in sorted(items.items()):
        ph = s256[:12]; bgr = cv2.imread(f); snap = rp['snapshot']
        pid = hashlib.sha256(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA).tobytes()).hexdigest(); ok, png = cv2.imencode('.png', bgr)
        payload = dict(photo='data:image/png;base64,' + base64.b64encode(png.tobytes()).decode(), photoId=pid, landmarks=rp['landmarks'], meshes=snap['meshes'],
                       exclusions=snap['exclusions'], qualityValid=rp['quality']['isValid'], conditions=dict(yaw=0, pitch=0, roll=0, scaleRatio=0))
        m = ats.current_product_masks(payload)
        run = lambda boxes: principled_accepted_boxes([list(map(float, b[:4])) + [float(b[4]) if len(b) > 4 and b[4] is not None else None] for b in boxes],
                                                      m['acne_envelopes'], m['acne_skin'], m['hair'], m['acne_exclusion'], pid, m['scale'], m['origin'],
                                                      visible_regions=list(snap['meshes']), landmarks=rp['landmarks'], source_shape=bgr.shape[:2], bgr=bgr)
        rec = dict(photo=ph, sha256=s256, kind=kind, visibleRegions=list(snap['meshes']), scale=float(m['scale']), origin=[float(v) for v in m['origin']])
        if (TR / f'{ph}.json').exists():
            t = json.loads((TR / f'{ph}.json').read_text()); z = np.load(TR / f'{ph}-masks.npz')
            same = all(np.array_equal(np.asarray(m[k]) > 0, z[k]) for k in ('acne_skin', 'hair', 'acne_exclusion', 'face_support')) and \
                   set('env_' + k for k in m['acne_envelopes']) == {k for k in z.files if k.startswith('env_')} and \
                   all(np.array_equal(np.asarray(v) > 0, z['env_' + k]) for k, v in m['acne_envelopes'].items())
            a, r = run(t['nms']); fin = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for v in a.values() for b in v]
            rec['step0'] = dict(masksEqualTrace=bool(same), finalEqualsStored=[[round(x, 3) for x in b] for b in fin] == [[round(x, 3) for x in b[:4]] for b in t['final']])
        for k in MODELS:
            a, r = run(by[k][s256])
            rec[k] = dict(before=[b[:5] for b in by[k][s256]], assigned=[dict(box=[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height'], b['confidence']], region=b['region'],
                          reason=b['assignmentReason']) for v in a.values() for b in v], rejected=r)
        out[ph] = rec; print(ph, kind, rec.get('step0'), {k: (len(rec[k]['before']), len(rec[k]['assigned'])) for k in MODELS}, flush=True)
    o = CODE / 'audit-results/acne-external-filter'; o.mkdir(parents=True, exist_ok=True)
    (o / 'results.json').write_text(json.dumps(dict(photos=out, hashes=dict(staging=sha(CODE / 'services/core-api/acne_box_support_staging.py'),
        appearance=sha(CODE / 'services/core-api/appearance_analysis.py'), takeover=sha(HERE / 'acne_takeover_support.py'), script=sha(__file__),
        rows=sha(CODE / 'audit-results/acne-relabel/acne-external-stored-rows-regen-20261016.json')))))
    print('complete')


if __name__ == '__main__': main()
