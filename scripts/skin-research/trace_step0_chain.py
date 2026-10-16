"""Step0 stage trace on the 28 positive DEV photos of the frozen point relabelling (no training, no new model/mode/threshold).

Runs the UNCHANGED label-free chain of eval_acne_v5_independent.run_photo (plan -> infer_tiles -> current_product_masks ->
principled_accepted_boxes) with Step0 and only OBSERVES its intermediate results:
  raw head outputs (obj*cls >= .01, top 400 per tile; tile-local -> source px exactly as infer_tiles), the >= .30 confidence
  candidates, the NMS-selected boxes, the filter's assigned and rejected boxes with reasons, and the product masks
  (acne_skin, hair, acne_exclusion, envelopes, face_support; analysis space with scale/origin).
Writes audit-results/acne-step0-trace/<photo>.json + <photo>-masks.npz (resumable per photo) and checks that the final boxes
equal the stored product-chain rows (infer-step0.jsonl). Annotations are never read here.
"""
import hashlib, json, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import eval_acne_v6 as v6
import eval_acne_v5_independent as v5

OUT = CODE / 'audit-results/acne-step0-trace'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(photo_ids, max_seconds=150):
    v2 = v5.setup(); import torch, cv2
    import acne_takeover_support as ats, acne_box_support_staging as abs_
    from skin_models import photo_input
    from heavy_job_lease import HeavyJobLease
    OUT.mkdir(parents=True, exist_ok=True)
    want = set(photo_ids)
    sets = {}
    for s in ('dev', 'devext'):
        rp = {json.loads(l)['sha256']: json.loads(l) for l in (v6.SETS[s]['out'] / 'replay.jsonl').read_text().splitlines()}
        st = {json.loads(l)['sha256']: json.loads(l) for l in (v6.SETS[s]['out'] / 'infer-step0.jsonl').read_text().splitlines()}
        for p in v6.photos(s):
            if p['sha256'][:12] not in want: continue
            f = p['file']; i = f.find('/mnt/TOGG/')
            if i >= 0: f = str(Path.home() / 'mnt') + f[i + 4:]          # session home changes between desktop sessions
            assert sha(f) == p['sha256'], ('INPUT_HASH', p['sha256'][:12])
            sets[p['sha256'][:12]] = (s, dict(p, file=f), rp[p['sha256']], st[p['sha256']])
    cap = {}
    inf0, msk0, flt0 = ats.infer_tiles, ats.current_product_masks, abs_.principled_accepted_boxes

    def infer(net, bgr, rects, *x, **k):
        tiles = []; h = net.register_forward_hook(lambda m, i, o: tiles.append(o[0].detach()))
        try: r = inf0(net, bgr, rects, *x, **k)
        finally: h.remove()
        raw = []
        for t, ((ra, rb, rc, rd), o) in enumerate(zip(rects, tiles)):
            s = o[:, 4] * o[:, 5]; idx = (s >= .01).nonzero().flatten(); idx = idx[s[idx].argsort(descending=True)][:400]
            for p, sc in zip(o[idx].tolist(), s[idx].tolist()):
                cx, cy, bw, bh = p[:4]; b = [max(ra, cx + ra - bw / 2), max(rb, cy + rb - bh / 2), min(rc, cx + ra + bw / 2), min(rd, cy + rb + bh / 2)]
                if b[2] > b[0] and b[3] > b[1]: raw.append([round(v, 2) for v in b] + [round(p[4], 4), round(p[5], 4), round(sc, 4), t])
        cap['raw'] = raw; cap['conf'] = [v['box'] + [v['confidence'], v['tile']] for v in r[1]['confidenceCandidates']]; cap['nms'] = [list(v) for v in r[0]]
        return r

    def masks(payload):
        m = msk0(payload); cap['masks'] = m; return m

    def filt(*a, **k):
        r = flt0(*a, **k); cap['assigned'] = [dict(b) for v in r[0].values() for b in v]; cap['rejected'] = r[1]; return r
    ats.infer_tiles, ats.current_product_masks, abs_.principled_accepted_boxes = infer, masks, filt
    v5.D = Path('/')
    with HeavyJobLease('CLAUDE-acne-step0-trace', peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
        torch.set_num_threads(2); net = v2.build_net(v5.TOGG); net.eval(); t0 = time.monotonic()
        for ph in sorted(sets):
            if (OUT / f'{ph}.json').exists(): continue
            if time.monotonic() - t0 > max_seconds: print('partial'); return
            lease.check(); s, p, rp, stored = sets[ph]; cap.clear()
            bgr = cv2.imread(p['file']); _, crop = photo_input(bgr, rp['landmarks'])
            row = v5.run_photo(net, p, rp)
            m = cap['masks']; env = m['acne_envelopes']
            np.savez_compressed(OUT / f'{ph}-masks.npz', acne_skin=np.asarray(m['acne_skin']) > 0, hair=np.asarray(m['hair']) > 0,
                                acne_exclusion=np.asarray(m['acne_exclusion']) > 0, face_support=np.asarray(m['face_support']) > 0,
                                **{'env_' + k: np.asarray(v) > 0 for k, v in env.items()})
            same = [[round(v, 3) for v in b[:4]] for b in row['final']] == [[round(v, 3) for v in b[:4]] for b in stored['final']]
            rec = dict(photo=ph, sha256=p['sha256'], set=s, status=row['status'], width=bgr.shape[1], height=bgr.shape[0], crop=crop, rects=row['rects'],
                       visibleRegions=list(rp['snapshot']['meshes']), scale=float(m['scale']), origin=[float(v) for v in m['origin']],
                       maskShape=list(np.asarray(m['acne_skin']).shape), raw=cap['raw'], conf=cap['conf'], nms=cap['nms'], assigned=cap['assigned'],
                       rejected=cap['rejected'], final=row['final'], finalEqualsStored=same, inferSec=row.get('inferSec'), totalSec=row.get('totalSec'))
            (OUT / f'{ph}.json').write_text(json.dumps(rec)); print(ph, 'final', len(row['final']), 'equalsStored', same, flush=True)
    print('complete')


if __name__ == '__main__':
    main(sys.argv[1].split(','), float(sys.argv[2]) if len(sys.argv) > 2 else 150)
