"""Single DEV application of the frozen verifier (docs/acne-verifier-model-20261016.json) to the cached DEV Step0 candidates.
Writes audit-results/acne-verifier/dev-decisions.json (photo ids, boxes, probabilities, keep flags; no pixels). Run once."""
import hashlib, json, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import acne_candidate_verifier as V

MODEL = CODE / 'docs/acne-verifier-model-20261016.json'; FROZEN = 'b6fa6c05b48a092623f7780200c07440ebaf934989ab66518ee21b23fa304f8a'


def main():
    o = CODE / 'audit-results/acne-verifier'; out = o / 'dev-decisions.json'
    assert not out.exists(), 'DEV_ALREADY_MEASURED'
    assert hashlib.sha256(MODEL.read_bytes()).hexdigest() == FROZEN, 'MODEL_CHANGED'
    ver = V.Verifier(MODEL); res = {}
    for j in sorted((o / 'dev').glob('*.json')):
        rec = json.loads(j.read_text()); F = np.load(j.with_suffix('.npz'))['features']
        t = time.perf_counter(); p = ver.proba(F) if len(F) else np.zeros(0); k = p >= ver.threshold; dt = time.perf_counter() - t
        res[rec['photo']] = dict(kind=rec['kind'], final=rec['final'], proba=p.tolist(), keep=k.tolist(), finalEqualsStored=rec.get('finalEqualsStored'),
                                 chainSec=rec['chainSec'], featureSec=rec['featureSec'], verifierSec=dt, featureBytes=rec['featureBytes'], maxRssMiB=rec['maxRssMiB'])
    out.write_text(json.dumps(dict(model=FROZEN, threshold=ver.threshold, photos=res)))
    print(len(res), sum(len(v['final']) for v in res.values()), sum(sum(v['keep']) for v in res.values()), hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == '__main__': main()
