"""Single DEV application of the frozen v3 verifier (docs/acne-verifier-v3-model-20261016.json) to the same cached DEV Step0 candidates
used for v1. Writes audit-results/acne-verifier-v3/dev-decisions-v3.json (no pixels). Run once; v1 and v2 decisions are not touched."""
import hashlib, json, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import acne_candidate_verifier as V

MODEL = CODE / 'docs/acne-verifier-v3-model-20261016.json'; FROZEN = '94d18abb951c49847371f03513957681fd50392e0ebfb51c233a1db65492ab67'


def main():
    src = CODE / 'audit-results/acne-verifier/dev'; out = CODE / 'audit-results/acne-verifier-v3/dev-decisions-v3.json'
    assert not out.exists(), 'DEV_ALREADY_MEASURED'
    assert hashlib.sha256(MODEL.read_bytes()).hexdigest() == FROZEN, 'MODEL_CHANGED'
    ver = V.Verifier(MODEL); res = {}
    for j in sorted(src.glob('*.json')):
        rec = json.loads(j.read_text()); F = np.load(j.with_suffix('.npz'))['features']
        t = time.perf_counter(); p = ver.proba(F) if len(F) else np.zeros(0); k = p >= ver.threshold; dt = time.perf_counter() - t
        res[rec['photo']] = dict(kind=rec['kind'], final=rec['final'], proba=p.tolist(), keep=k.tolist(), verifierSec=dt)
    out.write_text(json.dumps(dict(model=FROZEN, threshold=ver.threshold, photos=res)))
    print(len(res), sum(len(v['final']) for v in res.values()), sum(sum(v['keep']) for v in res.values()), hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == '__main__': main()
