"""Development calibration comparison (separate from the score-vs-discrimination check, whose AUC verdict stays NOT computable).

Frozen BEFORE any development output at the new thresholds:
  Step0 (18e94a95...) at conf .001 and corrected step-300 (5644d62c...) at conf .005, chosen by the TRAIN-only procedure of
  acne-v3-calibration-preregistration-20261016.json. No per-photo threshold, no score normalisation, no new sweep.
Chain: the unchanged v2 evaluator (crop, native 384/288 tiles, BGR, product _nms .30, prelude masks/exclusions, principled
staging filter with region ownership, one-to-one IoU>=.50). infer_tiles is copied verbatim; only the confidence literal is a
parameter, checked equal to the saved conf .30 rows first. IoU .50 primary, .30 secondary; low-threshold candidates outside
reviewed clean masks stay UNKNOWN, never true acne.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; TOGG = CODE.parent
OUT = CODE / 'audit-results/acne-v3-calib-dev-20261016'
W = {'step0': None, 'fix300': CODE / 'audit-results/acne-v3-20261015/v3/fix-step-000300/model.safetensors'}
RUNS = {'step0-c0.001': ('step0', .001), 'fix300-c0.005': ('fix300', .005), 'step0-c0.30-parity': ('step0', .30)}
SAVED30 = {'step0': 'v3prod-step0', 'fix300': 'v3prod-fix-step-000300'}


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def infer_tiles_conf(conf):
    def infer_tiles(net, bgr, rects, check=lambda: None):   # verbatim copy of acne_takeover_support.infer_tiles except '>=conf'
        import numpy as np, torch
        from skin_models import _nms
        boxes = []; scores = []; metadata = []
        with torch.inference_mode():
            for tile_id, (a, b, c, d) in enumerate(rects):
                check(); tile = np.full((384, 384, 3), 114, np.uint8); patch = bgr[b:d, a:c]; tile[:patch.shape[0], :patch.shape[1]] = patch
                out = net(torch.from_numpy(tile.transpose(2, 0, 1).copy()).float()[None])[0]; score = out[:, 4] * out[:, 5]; indices = torch.where(score >= conf)[0]; pred = out[indices]; score = score[indices]
                for index, p, s in zip(indices.tolist(), pred.tolist(), score.tolist()):
                    cx, cy, bw, bh = p[:4]; box = [max(a, cx + a - bw / 2), max(b, cy + b - bh / 2), min(c, cx + a + bw / 2), min(d, cy + b + bh / 2)]
                    if box[2] <= box[0] or box[3] <= box[1]: continue
                    box = [float(v) for v in box]; boxes.append(box); scores.append(s); metadata.append(dict(tile=tile_id, rect=[a, b, c, d], anchor=index, objectness=p[4], classProbability=p[5], confidence=s, box=box))
        if not boxes: return [], dict(tiles=len(rects), confidenceCandidates=[], nmsCandidates=[])
        selected = _nms([b + [s] for b, s in zip(boxes, scores)], threshold=.30)
        lookup = {tuple(v['box'] + [v['confidence']]): v for v in metadata}
        return selected, dict(tilingContract='current-skin-models-photo-input-camera-crop-v1', tiles=len(rects), confidenceCandidates=metadata, nmsCandidates=[lookup[tuple(v)] for v in selected])
    return infer_tiles


def run(name, max_seconds):
    sys.path[:0] = [str(HERE)]
    import run_acne_v2_pilot as v2
    v2.setup_paths(CODE, TOGG)
    import acne_takeover_support as ats, acne_box_support_staging as abs_
    from safetensors.torch import load_file
    pre = json.loads((OUT / 'preregistration.json').read_text())
    model, conf = RUNS[name]
    if pre['weights'][model] != (sha(W[model]) if W[model] else v2.STEP0_SHA256): raise RuntimeError('WEIGHTS_CHANGED')
    if W[model]:
        base = v2.build_net
        def build(t):
            net = base(t); net.load_state_dict(load_file(str(W[model])), strict=True); return net
        v2.build_net = build
    side = (OUT / f'{name}-boxes.jsonl').open('a'); clock = {}
    orig = ats.infer_tiles; ref = infer_tiles_conf(conf); flt0 = abs_.principled_accepted_boxes
    def infer(*x, **k):
        clock['t0'] = time.perf_counter(); r = ref(*x, **k); clock['raw'] = len(r[1]['confidenceCandidates']); clock['nms'] = len(r[0]); return r
    def filt(*x, **k):
        r = flt0(*x, **k); now = time.perf_counter()
        boxes = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for v in r[0].values() for b in v]
        side.write(json.dumps(dict(boxes=boxes, rawCandidates=clock['raw'], afterNMS=clock['nms'], totalSec=now - clock['t0'])) + '\n'); side.flush(); return r
    ats.infer_tiles, abs_.principled_accepted_boxes = infer, filt
    man = v2.read_json(CODE / 'docs/acne-data-v2-manifest-20261015.json')
    from heavy_job_lease import HeavyJobLease
    with HeavyJobLease('CLAUDE-acne-v3-calib-dev-' + name, peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
        try: v2.evaluate(name, man, OUT, TOGG, CODE, lease, max_seconds); print('complete')
        except TimeoutError: print('partial')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase'); ap.add_argument('--run'); ap.add_argument('--max-seconds', type=float, default=110)
    a = ap.parse_args(); OUT.mkdir(parents=True, exist_ok=True)
    if a.phase == 'register':
        p = OUT / 'preregistration.json'
        if p.exists(): raise SystemExit('FROZEN')
        calib = CODE / 'docs/acne-v3-calibration-analysis-20261016.json'; an = json.loads(calib.read_text())
        assert an['models']['step0']['calibratedThreshold'] == .001 and an['models']['fix300']['calibratedThreshold'] == .005
        p.write_text(json.dumps(dict(
            purpose='Do the TRAIN-chosen fixed thresholds help on the real product chain? Separate from the score-vs-discrimination check; its AUC verdict stays NOT_COMPUTABLE and is not claimed as PRESERVED.',
            thresholds=dict(step0=.001, fix300=.005), source=dict(file=calib.name, sha256=sha(calib), rule='smallest grid t with <= 1 clean-negative candidate per TRAIN negative photo'),
            weights=dict(step0='18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655', fix300=sha(W['fix300'])),
            groups=dict(scopeBPositive='3 photos / 14 targets', reviewedNegatives='the same 7 product-valid reviewed negative photos (2 not product-valid excluded)',
                        controls='3 product-valid controls / 29 targets', heldOut20='20 replay-pass photos / 95 targets: separate development group; eyewear UNKNOWN; not full product pass, not an independent final test'),
            baselines='saved conf .30 rows (v3prod-step0, v3prod-fix-step-000300) are kept and reused, not invalidated',
            parity='before using the conf copy: Step0 at conf .30 through the copy must equal the saved Step0 .30 rows (matched, cleanFP, candidates) on every row',
            unchanged='crop, native tiles, BGR channel order, product _nms .30, anatomical support, exclusions, region ownership, one-to-one matching (a box serves one target); IoU .50 primary, .30 secondary',
            reading='raw anchor availability is not product capture; low-threshold candidates outside reviewed clean masks are UNKNOWN, never true acne; no threshold change after development results; '
                    'no activation, acceptance unchanged (acceptance.json 90dc84fa...)',
            limits='if resources stop a run: report it; no silent candidate truncation and no rule change',
            codeSHA256=sha(__file__)), indent=1)); print(sha(p))
    elif a.phase == 'run': run(a.run, a.max_seconds)
