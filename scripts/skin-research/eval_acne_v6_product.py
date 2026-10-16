"""Diagnostic product-chain run of one saved checkpoint with the UNCHANGED v2 evaluator (run_acne_v2_pilot.evaluate), as in
eval_acne_v3_product.py, plus a label-free record of the intermediate detector outputs needed for a loss breakdown.

Unchanged: photos and source coordinates, product photo_input crop, native 384/288 tiles, preflight/exclusion masks, conf obj*cls >= .30,
hard NMS .30, principled staging filter, one-to-one IoU >= .50, reviewed-negative clean masks. The wrapper only observes:
  {name}-boxes.jsonl : final filtered boxes + stage timings (same schema as eval_acne_v3_product.py)
  {name}-raw.jsonl   : per photo (aligned with -boxes.jsonl): raw head boxes with obj*cls >= .01 (top 400 per tile, source px, clipped to the
                       tile rect exactly as infer_tiles does), the >= .30 confidence candidates and the NMS-selected boxes.
Annotations are never read here. Use --suffix for a parity run that must not overwrite saved results.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[1]; TOGG = CODE.parent


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--model', required=True); ap.add_argument('--suffix', default='')
    ap.add_argument('--max-seconds', type=float, default=110)
    a = ap.parse_args()
    import run_acne_v2_pilot as v2
    v2.setup_paths(CODE, TOGG)
    import acne_takeover_support as ats, acne_box_support_staging as abs_
    from safetensors.torch import load_file
    out = CODE / 'audit-results/acne-v3-20261015'
    name = 'v3prod-' + a.model + a.suffix
    if a.model != 'step0':
        w = out / 'v3' / a.model / 'model.safetensors'; base = v2.build_net
        def build(t):
            net = base(t); net.load_state_dict(load_file(str(w)), strict=True); return net
        v2.build_net = build
        wsha = hashlib.sha256(w.read_bytes()).hexdigest()
    else: wsha = v2.STEP0_SHA256
    side = (out / f'{name}-boxes.jsonl').open('a'); rawf = (out / f'{name}-raw.jsonl').open('a'); clock = {}; st = {}
    inf0, msk0, flt0 = ats.infer_tiles, ats.current_product_masks, abs_.principled_accepted_boxes

    def infer(net, bgr, rects, *x, **k):
        tiles = []
        h = net.register_forward_hook(lambda m, i, o: tiles.append(o[0].detach()))
        clock['t0'] = time.perf_counter()
        try: r = inf0(net, bgr, rects, *x, **k)
        finally: h.remove()
        clock['infer'] = time.perf_counter() - clock['t0']
        raw = []
        for (ra, rb, rc, rd), o in zip(rects, tiles):
            s = o[:, 4] * o[:, 5]; idx = (s >= .01).nonzero().flatten()
            idx = idx[s[idx].argsort(descending=True)][:400]
            for p, sc in zip(o[idx].tolist(), s[idx].tolist()):
                cx, cy, bw, bh = p[:4]; b = [max(ra, cx + ra - bw / 2), max(rb, cy + rb - bh / 2), min(rc, cx + ra + bw / 2), min(rd, cy + rb + bh / 2)]
                if b[2] > b[0] and b[3] > b[1]: raw.append([round(v, 2) for v in b] + [round(sc, 4)])
        st['raw'] = raw; st['conf'] = [v['box'] + [v['confidence']] for v in r[1]['confidenceCandidates']]; st['nms'] = [list(v) for v in r[0]]
        return r

    def masks(*x, **k):
        t = time.perf_counter(); r = msk0(*x, **k); clock['masks'] = time.perf_counter() - t; return r

    def filt(*x, **k):
        t = time.perf_counter(); r = flt0(*x, **k); now = time.perf_counter()
        boxes = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for v in r[0].values() for b in v]
        side.write(json.dumps(dict(weights=wsha, boxes=boxes, inferSec=clock['infer'], masksSec=clock['masks'], filterSec=now - t, totalSec=now - clock['t0'])) + '\n'); side.flush()
        rawf.write(json.dumps(dict(weights=wsha, raw=st['raw'], confCandidates=st['conf'], nmsSelected=st['nms'])) + '\n'); rawf.flush()
        return r
    ats.infer_tiles, ats.current_product_masks, abs_.principled_accepted_boxes = infer, masks, filt
    man = v2.read_json(CODE / 'docs/acne-data-v2-manifest-20261015.json')
    from heavy_job_lease import HeavyJobLease
    with HeavyJobLease('CLAUDE-acne-v6-product-' + a.model, peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
        try: v2.evaluate(name, man, out, TOGG, CODE, lease, a.max_seconds); print('complete')
        except TimeoutError: print('partial')


if __name__ == '__main__':
    sys.path.insert(0, str(HERE)); main()
