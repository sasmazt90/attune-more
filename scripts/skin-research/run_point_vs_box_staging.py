"""Offline staging comparison: the same recorded pre-filter predictions through (a) the unchanged box filter
principled_accepted_boxes and (b) the point filter acne_point_support_staging.point_accepted, with the same product masks
and geometry (current_product_masks from the same replay landmarks/snapshot). No model inference.
Pre-filter inputs: Step0 recorded NMS boxes (positives; Clear photos have no Step0 records) and the stored external final
boxes (Dewiin anyacne/tiles, tristan-gray/tiles, carsten12/tiles). Writes audit-results/acne-point-filter/results.json."""
import base64, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import eval_acne_v6 as v6, eval_acne_v5_independent as v5

MODELS = ['dewiin-anyacne/tiles', 'tristan-gray/tiles', 'carsten12/tiles']


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    v5.setup(); import cv2
    import acne_takeover_support as ats
    from acne_box_support_staging import principled_accepted_boxes
    from acne_point_support_staging import point_accepted, VERSION
    rows = json.load(open(CODE / 'audit-results/acne-relabel/acne-external-stored-rows-regen-20261016.json'))
    want = {r['sha'] for r in rows[MODELS[0]]}; items = {}
    for s in ('dev', 'devext'):
        rp = {json.loads(l)['sha256']: json.loads(l) for l in (v6.SETS[s]['out'] / 'replay.jsonl').read_text().splitlines()}
        for p in v6.photos(s):
            if p['sha256'] not in want: continue
            f = p['file']; i = f.find('/mnt/TOGG/')
            if i >= 0: f = str(Path.home() / 'mnt') + f[i + 4:]
            assert sha(f) == p['sha256']; items[p['sha256']] = (p['kind'], f, rp[p['sha256']])
    by = {k: {r['sha']: r['final'] for r in rows[k]} for k in MODELS}; TR = CODE / 'audit-results/acne-step0-trace'; out = {}
    for s256, (kind, f, rp) in sorted(items.items()):
        ph = s256[:12]; bgr = cv2.imread(f); snap = rp['snapshot']
        pid = hashlib.sha256(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA).tobytes()).hexdigest(); ok, png = cv2.imencode('.png', bgr)
        m = ats.current_product_masks(dict(photo='data:image/png;base64,' + base64.b64encode(png.tobytes()).decode(), photoId=pid, landmarks=rp['landmarks'],
                                           meshes=snap['meshes'], exclusions=snap['exclusions'], qualityValid=rp['quality']['isValid'], conditions=dict(yaw=0, pitch=0, roll=0, scaleRatio=0)))
        vis = list(snap['meshes']); args = (m['acne_envelopes'], m['acne_skin'], m['hair'], m['acne_exclusion'], pid, m['scale'], m['origin'])
        inputs = {k: [list(map(float, b[:4])) + [float(b[4])] for b in by[k][s256]] for k in MODELS}
        if (TR / f'{ph}.json').exists(): inputs['step0'] = [list(map(float, b[:5])) for b in json.loads((TR / f'{ph}.json').read_text())['nms']]
        rec = dict(photo=ph, kind=kind, visibleRegions=vis)
        for k, boxes in inputs.items():
            a, r = principled_accepted_boxes(boxes, *args, visible_regions=vis, landmarks=rp['landmarks'], source_shape=bgr.shape[:2], bgr=bgr)
            pa, pr = point_accepted(boxes, *args, visible_regions=vis, landmarks=rp['landmarks'], source_shape=bgr.shape[:2])
            rec[k] = dict(before=boxes, boxAccepted=[dict(box=[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height'], b['confidence']], region=b['region'], reason=b['assignmentReason'])
                                                     for v in a.values() for b in v], boxRejected=r, pointAccepted=pa, pointRejected=pr)
        if 'step0' in rec:
            st = json.loads((TR / f'{ph}.json').read_text())['final']
            rec['step0']['boxParity'] = sorted([round(x, 3) for x in d['box'][:4]] for d in rec['step0']['boxAccepted']) == sorted([round(x, 3) for x in b[:4]] for b in st)
        out[ph] = rec; print(ph, kind, {k: (len(rec[k]['before']), len(rec[k]['boxAccepted']), len(rec[k]['pointAccepted'])) for k in inputs}, rec.get('step0', {}).get('boxParity'), flush=True)
    o = CODE / 'audit-results/acne-point-filter'; o.mkdir(parents=True, exist_ok=True)
    (o / 'results.json').write_text(json.dumps(dict(photos=out, pointFilterVersion=VERSION, hashes=dict(
        pointFilter=sha(CODE / 'services/core-api/acne_point_support_staging.py'), boxFilter=sha(CODE / 'services/core-api/acne_box_support_staging.py'),
        appearance=sha(CODE / 'services/core-api/appearance_analysis.py'), takeover=sha(HERE / 'acne_takeover_support.py'), script=sha(__file__),
        externalRows=sha(CODE / 'audit-results/acne-relabel/acne-external-stored-rows-regen-20261016.json'), step0TraceIndex=sha(TR / 'index.json')))))
    print('complete')


if __name__ == '__main__': main()
