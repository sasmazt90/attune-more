"""ONE inference per evaluated unused-test photo: fixed Step0 chain + old box filter + frozen features (run once), then the SAME
candidates/features to frozen v1 and v3. Labels are not read. Cached per photo; Step0 parameter digest checked before/after.
Writes audit-results/acne-unused-test/infer/<ph>.json/.npz and infer-summary.json (photo-free)."""
import hashlib, json, resource, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import acne_verifier_photo as P

O = CODE / 'audit-results/acne-unused-test'


def main():
    import eval_acne_v5_independent as v5, acne_candidate_verifier as V, cv2, torch
    from heavy_job_lease import HeavyJobLease
    el = json.loads((O / 'eligibility.json').read_text()); rp = {json.loads(l)['sha256']: json.loads(l) for l in open(O / 'replay.jsonl')}
    vers = {}
    for k in ('v1', 'v3'):
        f, sha = P.MODELS[k]; assert hashlib.sha256(f.read_bytes()).hexdigest() == sha; vers[k] = V.Verifier(f)
    out = O / 'infer'; out.mkdir(exist_ok=True)
    with HeavyJobLease('CLAUDE-acne-unused-test', peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
        v2 = v5.setup(); torch.set_num_threads(2); net = v2.build_net(v5.TOGG); net.eval(); before = P.param_digest(net)
        for s in el['evaluated']:
            ph = s[:12]
            if (out / f'{ph}.json').exists(): continue
            lease.check(); f = O / 'photos' / (s[:16] + '.jpg'); assert hashlib.sha256(f.read_bytes()).hexdigest() == s
            bgr = cv2.imread(str(f)); t0 = time.perf_counter(); r = V.run_chain_with_features(net, bgr, rp[s]); t1 = time.perf_counter(); F = r['features']
            rec = dict(photo=ph, sha256=s, status=r['status'], final=[[round(x, 3) for x in b[:4]] + [b[4]] for b in r['final']], chainSec=r.get('chainSec'), featureSec=r.get('featureSec'),
                       featureBytes=r.get('featureBytes'), totalChainSec=t1 - t0, maxRssMiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, verifiers={})
            for k, ver in vers.items():
                t = time.perf_counter(); p = ver.proba(F) if len(F) else np.zeros(0)
                rec['verifiers'][k] = dict(proba=p.tolist(), keep=(p >= ver.threshold).tolist(), sec=time.perf_counter() - t)
            np.savez_compressed(out / f'{ph}.npz', features=F); (out / f'{ph}.json').write_text(json.dumps(rec))
            print(ph, len(rec['final']), {k: sum(v['keep']) for k, v in rec['verifiers'].items()}, round(t1 - t0, 2), flush=True)
        assert P.param_digest(net) == before, 'STEP0_PARAMETERS_CHANGED'
    print('complete', before)


if __name__ == '__main__': main()
