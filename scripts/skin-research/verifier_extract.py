"""Extract Step0 candidates + frozen features once (cached) for TRAIN (manifest-v6 photos with a replay row) or DEV (28 positive
pack photos + 14 replay-pass DEV Clear photos). Resumable per photo; one heavy process under HeavyJobLease.
Usage: verifier_extract.py train|dev [max_seconds]. Output: audit-results/acne-verifier/<set>/<photo>.npz/.json
Parity: DEV finals must equal the stored infer-step0 rows; TRAIN: the first 3 photos are also run without hooks and must agree."""
import hashlib, json, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import eval_acne_v6 as v6, eval_acne_v5_independent as v5

OUT = CODE / 'audit-results/acne-verifier'


def remap(f):
    i = f.find('/mnt/TOGG/'); return str(Path.home() / 'mnt') + f[i + 4:] if i >= 0 else f


def items(which):
    if which == 'train':
        man = json.load(open(CODE / 'audit-results/acne-v6-data/manifest-v6.json'))['photos']; rp = {}
        for f in ('audit-results/acne-v6/trainext/replay.jsonl', 'audit-results/acne-data-v2-20261015/replay.jsonl'):
            for l in open(CODE / f):
                r = json.loads(l)
                if r.get('snapshot') and r.get('landmarks'): rp.setdefault(r['sha256'], r)
        return [(p['sha256'], p['kind'], str(CODE / 'audit-results/acne-v6-data' / p['file']), rp[p['sha256']], None) for p in man if p['sha256'] in rp]
    rows = json.load(open(CODE / 'audit-results/acne-relabel/acne-external-stored-rows-regen-20261016.json'))
    want = {r['sha'] for r in rows['carsten12/tiles']}; out = []
    for s in ('dev', 'devext'):
        rp = {json.loads(l)['sha256']: json.loads(l) for l in (v6.SETS[s]['out'] / 'replay.jsonl').read_text().splitlines()}
        st = {json.loads(l)['sha256']: json.loads(l) for l in (v6.SETS[s]['out'] / 'infer-step0.jsonl').read_text().splitlines()}
        for p in v6.photos(s):
            if p['sha256'] in want: out.append((p['sha256'], p['kind'], remap(p['file']), rp[p['sha256']], st[p['sha256']]['final']))
    return out


def main(which, max_seconds):
    v2 = v5.setup(); import cv2, torch, resource
    import acne_candidate_verifier as V
    from heavy_job_lease import HeavyJobLease
    o = OUT / which; o.mkdir(parents=True, exist_ok=True); its = items(which); print(which, len(its), 'photos', flush=True)
    with HeavyJobLease('CLAUDE-acne-verifier-extract', peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
        torch.set_num_threads(2); net = v2.build_net(v5.TOGG); net.eval(); t0 = time.monotonic(); v5.D = Path('/')
        for n, (s256, kind, f, rp, stored) in enumerate(its):
            ph = s256[:12]
            if (o / f'{ph}.json').exists(): continue
            if time.monotonic() - t0 > max_seconds: print('partial'); return
            lease.check(); assert hashlib.sha256(Path(f).read_bytes()).hexdigest() == s256, 'INPUT_HASH'
            bgr = cv2.imread(f); r = V.run_chain_with_features(net, bgr, rp)
            rec = dict(photo=ph, sha256=s256, kind=kind, status=r['status'], final=r['final'], tiles=r['tiles'], inferSec=r.get('inferSec'), chainSec=r.get('chainSec'),
                       featureSec=r.get('featureSec'), featureBytes=r.get('featureBytes'), maxRssMiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
            rk = lambda L: [[round(x, 3) for x in b[:4]] for b in L]
            if stored is not None: rec['finalEqualsStored'] = rk(r['final']) == rk(stored)
            if which == 'train' and n < 3:
                plain = v5.run_photo(net, dict(sha256=s256, kind=kind, file=f), rp); rec['finalEqualsNoHook'] = rk(plain['final']) == rk(r['final'])
            np.savez_compressed(o / f'{ph}.npz', features=r['features'])
            (o / f'{ph}.json').write_text(json.dumps(rec)); print(ph, kind, len(r['final']), rec.get('finalEqualsStored', rec.get('finalEqualsNoHook')), round(r.get('chainSec') or 0, 2), round(r.get('featureSec') or 0, 3), flush=True)
    print('complete')


if __name__ == '__main__': main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 140)
