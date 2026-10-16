"""Offline local photo evaluation: Step0 + old box filter (A) and A + frozen candidate verifier (B) on one or more photos.
No network, no product activation (acne stays accepted:false, file:null in the product; this is a research command).

Usage:
  acne_verifier_photo.py --out DIR PHOTO [PHOTO ...] [--replay FILE.jsonl ...] [--model docs/acne-verifier-model-20261016.json]
Input needs a product replay row (landmarks + snapshot). If no --replay file holds a row for the photo's sha256, the row is made
locally: MediaPipe FaceLandmarker with the product face_landmarker.task (separate venv ~/envmp) -> frontend TypeScript replay
(node). Writes DIR/<sha12>.json (A and B points, probabilities, timings) and DIR/<sha12>-before-after.jpg (legend image).
"""
import argparse, hashlib, json, subprocess, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; TOGG = CODE.parent
sys.path[:0] = [str(HERE)]
MODEL_SHA = 'b6fa6c05b48a092623f7780200c07440ebaf934989ab66518ee21b23fa304f8a'
TASK = TOGG / 'attune-live-test/audit-results/skin-capabilities-20261008/scin/face_landmarker.task'


def replay_rows(files):
    rp = {}
    for f in files or []:
        for l in Path(f).read_text('utf8').splitlines():
            if l.strip(): r = json.loads(l); rp.setdefault(r['sha256'], r)
    return rp


def make_replay(photos, work):
    """Landmarks + product frontend replay for photos without a stored row (local, offline)."""
    import prepare_acne_data_v2 as prep
    work.mkdir(parents=True, exist_ok=True); items = work / 'items.json'; lm = work / 'landmarks.jsonl'; out = work / 'replay.jsonl'
    items.write_text(json.dumps([dict(sha256=s, path=str(p)) for s, p in photos.items()]))
    subprocess.run([str(Path.home() / 'envmp/bin/python'), str(HERE / 'acne_landmarks_v2.py'), '--task', str(TASK), '--items', str(items), '--out', str(lm)], check=True)
    prep.run_replay(CODE, lm, photos, TOGG, out)
    return replay_rows([out])


def param_digest(net):
    h = hashlib.sha256()
    for k, v in net.state_dict().items(): h.update(k.encode()); h.update(v.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def legend_image(bgr, A, keep, proba, path):
    import cv2
    img = bgr.copy(); s = max(1, round(max(img.shape[:2]) / 900))
    for b, k, p in zip(A, keep, proba):
        c = (int((b[0] + b[2]) / 2), int((b[1] + b[3]) / 2))
        if k: cv2.circle(img, c, 6 * s, (0, 200, 0), 2 * s)                                   # kept by verifier (A and B)
        else: cv2.drawMarker(img, c, (0, 0, 255), cv2.MARKER_TILTED_CROSS, 14 * s, 2 * s); cv2.putText(img, f'{p:.2f}', (c[0] + 8 * s, c[1]), 0, .45 * s, (0, 0, 255), s)
    pad = 26 * s; h = np.full((pad * 3, img.shape[1], 3), 255, np.uint8)
    cv2.circle(h, (12 * s, pad // 2), 6 * s, (0, 200, 0), 2 * s); cv2.putText(h, 'A and B: Step0 + old box filter point kept by verifier', (24 * s, pad // 2 + 5 * s), 0, .5 * s, (0, 0, 0), s)
    cv2.drawMarker(h, (12 * s, pad + pad // 2), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 14 * s, 2 * s)
    cv2.putText(h, 'A only: removed by verifier (number = probability)', (24 * s, pad + pad // 2 + 5 * s), 0, .5 * s, (0, 0, 0), s)
    cv2.putText(h, f'A {len(A)} points -> B {int(sum(keep))} points. Research only; not a diagnosis.', (6 * s, 2 * pad + pad // 2 + 5 * s), 0, .5 * s, (0, 0, 0), s)
    cv2.imwrite(str(path), np.vstack([img, h]))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('photos', nargs='+'); ap.add_argument('--out', required=True); ap.add_argument('--replay', nargs='*')
    ap.add_argument('--model', default=str(CODE / 'docs/acne-verifier-model-20261016.json')); ap.add_argument('--no-image', action='store_true')
    a = ap.parse_args(argv); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if hashlib.sha256(Path(a.model).read_bytes()).hexdigest() != MODEL_SHA: raise SystemExit('VERIFIER_MODEL_HASH_MISMATCH')
    import eval_acne_v5_independent as v5, acne_candidate_verifier as V, cv2, torch, resource
    v2 = v5.setup(); torch.set_num_threads(2)
    photos = {hashlib.sha256(Path(p).read_bytes()).hexdigest(): Path(p) for p in a.photos}
    rp = replay_rows(a.replay); missing = {s: p for s, p in photos.items() if s not in rp}
    if missing: rp.update(make_replay(missing, out / '_replay'))
    net = v2.build_net(v5.TOGG); net.eval(); before = param_digest(net); ver = V.Verifier(a.model); res = {}
    for s, p in photos.items():
        bgr = cv2.imread(str(p)); t = time.perf_counter(); r = V.run_chain_with_features(net, bgr, rp[s]); F = r['features']
        proba = ver.proba(F) if len(F) else np.zeros(0); keep = proba >= ver.threshold; dt = time.perf_counter() - t
        rec = dict(photo=s[:12], sha256=s, replaySource='stored' if s not in missing else 'local-mediapipe-replay', status=r['status'],
                   A=[[round(x, 2) for x in b[:4]] + [b[4]] for b in r['final']], B=[[round(x, 2) for x in b[:4]] + [b[4]] for b, k in zip(r['final'], keep) if k],
                   proba=proba.tolist(), keep=keep.tolist(), totalSec=dt, chainSec=r.get('chainSec'), featureSec=r.get('featureSec'), featureBytes=r.get('featureBytes'),
                   maxRssMiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, verifierModel=MODEL_SHA, threshold=ver.threshold)
        np.savez_compressed(out / f'{s[:12]}-features.npz', features=F)
        (out / f'{s[:12]}.json').write_text(json.dumps(rec)); res[s[:12]] = rec
        if not a.no_image: legend_image(bgr, r['final'], keep, proba, out / f'{s[:12]}-before-after.jpg')
        print(s[:12], r['status'], 'A', len(rec['A']), 'B', len(rec['B']), round(dt, 2), 's', flush=True)
    assert param_digest(net) == before, 'STEP0_PARAMETERS_CHANGED'
    return res


if __name__ == '__main__': main()
