"""Product-chain comparison of Step0 and one saved v3 checkpoint with the UNCHANGED v2 evaluator.

The evaluator (run_acne_v2_pilot.evaluate) is called as-is: product photo_input tiles, conf obj*cls >= .30, hard NMS .30,
current production prelude masks (crop, face/region support, exclusions), principled staging filter, one-to-one IoU >= .50.
This wrapper only (a) swaps the weights for a v3 checkpoint, (b) times the stages and (c) records the final filtered boxes
so the same predictions can ALSO be scored at IoU >= .30 (reported separately, never mixed with .50).
No training, no threshold or rule change. Step0 is re-run so both models share one environment and one timing method.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[1]; TOGG = CODE.parent


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--model', required=True); ap.add_argument('--max-seconds', type=float, default=110)
    a = ap.parse_args()
    import run_acne_v2_pilot as v2
    v2.setup_paths(CODE, TOGG)
    import acne_takeover_support as ats, acne_box_support_staging as abs_
    from safetensors.torch import load_file
    out = CODE / 'audit-results/acne-v3-20261015'
    name = 'v3prod-' + a.model
    if a.model != 'step0':
        w = out / 'v3' / a.model / 'model.safetensors'; base = v2.build_net
        def build(t):
            net = base(t); net.load_state_dict(load_file(str(w)), strict=True); return net
        v2.build_net = build
        wsha = hashlib.sha256(w.read_bytes()).hexdigest()
    else: wsha = v2.STEP0_SHA256
    side = (out / f'{name}-boxes.jsonl').open('a'); clock = {}
    inf0, msk0, flt0 = ats.infer_tiles, ats.current_product_masks, abs_.principled_accepted_boxes
    def infer(*x, **k):
        clock['t0'] = time.perf_counter(); r = inf0(*x, **k); clock['infer'] = time.perf_counter() - clock['t0']; return r
    def masks(*x, **k):
        t = time.perf_counter(); r = msk0(*x, **k); clock['masks'] = time.perf_counter() - t; return r
    def filt(*x, **k):
        t = time.perf_counter(); r = flt0(*x, **k); now = time.perf_counter()
        boxes = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for v in r[0].values() for b in v]
        side.write(json.dumps(dict(weights=wsha, boxes=boxes, inferSec=clock['infer'], masksSec=clock['masks'], filterSec=now - t, totalSec=now - clock['t0'])) + '\n'); side.flush()
        return r
    ats.infer_tiles, ats.current_product_masks, abs_.principled_accepted_boxes = infer, masks, filt
    man = v2.read_json(CODE / 'docs/acne-data-v2-manifest-20261015.json')
    from heavy_job_lease import HeavyJobLease
    with HeavyJobLease('CLAUDE-acne-v3-product-' + a.model, peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
        try: v2.evaluate(name, man, out, TOGG, CODE, lease, a.max_seconds); print('complete')
        except TimeoutError: print('partial')


if __name__ == '__main__':
    sys.path.insert(0, str(HERE)); main()
