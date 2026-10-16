"""Check regenerated third-party rows against the committed records of the earlier point evaluation
(docs/acne-point-eval-results-20261016.json, written from the lost stored rows): every per-target field (point hit, matched
prediction index, normalized distance, d<=.25/.50, IoU .50/.30), the per-model counts (final boxes on positive photos,
UNKNOWN, duplicates, clean-ROI and Clear false points) and the per-photo clean-ROI / Clear records (false points and, on
Clear photos, the number of points). A record is EXACT only if every field is equal."""
import json, sys
from pathlib import Path
import cv2
import point_eval as P

FIELDS = ('pointHit', 'pred', 'dNorm', 'tol25', 'tol50', 'iou50', 'iou30')
SUMF = ('targets', 'point', 'final', 'unknown', 'duplicates', 'roiFP', 'clearFP', 'iou50', 'iou30', 'tol25', 'tol50')


def check(rows, committed, man, pack):
    S, pt, roi_pp, clear_pp, _ = P.evaluate(rows, man, Path(pack), lambda f: cv2.imread(str(f), cv2.IMREAD_GRAYSCALE) > 0)
    old = {t['target']: t for t in committed['perTarget']}
    diffT = [t['target'] for t in pt if any(t[f] != old[t['target']][f] for f in FIELDS)]
    diffS = {f: (committed['summary'][f], S[f]) for f in SUMF if committed['summary'][f] != S[f]}
    diffP = [x for x, y in zip(roi_pp + clear_pp, committed['roiPerPhoto'] + committed['clearPerPhoto']) if x != y]
    return dict(exact=not diffT and not diffS and not diffP, targetsDiffering=diffT, summaryDiffering=diffS, perPhotoMaskDiffering=diffP)


if __name__ == '__main__':
    pack, committed_f, rows_f = sys.argv[1:4]
    man = json.load(open(Path(pack) / 'manifest.json')); C = json.load(open(committed_f))['results']; rows = json.load(open(rows_f))
    rep = {k: check(v, C[k], man, pack) for k, v in rows.items()}
    for k, v in sorted(rep.items()): print(k, 'EXACT' if v['exact'] else f"DIFF targets={len(v['targetsDiffering'])} summary={v['summaryDiffering']}")
    json.dump(rep, open(rows_f.replace('.json', '-verify.json'), 'w'), indent=1)
