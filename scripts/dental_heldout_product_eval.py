"""Frozen held-out evaluation of the DEPLOYED dental ONNX through product code.

No training, no threshold search, no split rebuild. Reads the existing
case-capture-v2 split (its SHA-256 must equal the model manifest inventory
hash) and the private test images from --data-root; neither is stored in Git.

Modes, reported separately:
  raw      dental_analysis.model_candidates on the whole intraoral frame
           (all raw classes D/d) - must reproduce the frozen manifest counts.
  upload   dental_upload.analyze_upload without face landmarks, i.e. the
           real product upload path incl. quality gates, ROI crop and the
           adult D-only policy. Rejected photos are counted, never as healthy.

Usage:
  python scripts/dental_heldout_product_eval.py --data-root <private> \
     --split <private>/training/dataset-split.json --out <json>
"""
import argparse, base64, hashlib, json, sys, time
from collections import defaultdict
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/core-api'))


def iou(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1]); x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    return inter / max((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter, 1e-8)


def counts(truth_boxes, predicted, overlap=.5):
    """Same score-ranked greedy same-class matching as the frozen trainer."""
    matched = set(); tp = fp = 0
    for score, box in sorted(predicted, key=lambda v: -v[0]):
        best = max(((iou(box, t), j) for j, t in enumerate(truth_boxes) if j not in matched), default=(0, -1))
        if best[0] >= overlap: matched.add(best[1]); tp += 1
        else: fp += 1
    return tp, fp, len(truth_boxes) - tp


def summarize(tally):
    out = {}
    for code, (tp, fp, fn) in tally.items():
        p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
        out[code] = dict(truePositive=tp, falsePositive=fp, falseNegative=fn, precision=p, recall=r, F1=2 * p * r / max(p + r, 1e-8))
    return out


def view_group(path):
    p = path.replace('\\', '/')
    if 'Frontal' in p or 'Lateral' in p: return 'frontal+lateral'
    if 'Mandibular' in p or 'Maxillary' in p: return 'occlusal'
    return 'other'


def resolve(row, data_root):
    rel = row['path'].replace('\\', '/')
    for marker in ('/dental/Dataset/Dataset/', '/dental/'):
        if marker in rel:
            tail = rel.split(marker, 1)[1]
            for candidate in (data_root / tail, data_root / 'Dataset' / tail):
                if candidate.exists(): return candidate
    if '/combined-health-20261008/' in rel:
        candidate = data_root / rel.split('/combined-health-20261008/', 1)[1]
        if candidate.exists(): return candidate
    raise FileNotFoundError(row['path'])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data-root', required=True); ap.add_argument('--split', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--modes', default='raw,upload'); args = ap.parse_args()
    import dental_analysis as product
    from dental_upload import analyze_upload, UploadError
    manifest = json.loads((ROOT / 'services/core-api/models/dental-yolox-s.json').read_text('utf8'))
    split_bytes = Path(args.split).read_bytes()
    assert hashlib.sha256(split_bytes).hexdigest() == manifest['trainingProvenance']['inventorySHA256'], 'SPLIT_HASH_MISMATCH'
    onnx = ROOT / 'services/core-api/models/dental-yolox-s.onnx'
    assert hashlib.sha256(onnx.read_bytes()).hexdigest() == manifest['modelHash'], 'MODEL_HASH_MISMATCH'
    rows = [r for r in json.loads(split_bytes)['rows'] if r['split'] == 'test']
    data_root = Path(args.data_root); modes = args.modes.split(',')
    classes = manifest['classes']
    raw_tally = {c: [0, 0, 0] for c in classes}; up_tally = {'D': [0, 0, 0]}; up_all_truth_D = 0
    group_tally = defaultdict(lambda: {c: [0, 0, 0] for c in classes})
    rejected = defaultdict(int); per_image = []; started = time.time()
    for n, row in enumerate(rows):
        path = resolve(row, data_root); data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['sha256'], f'SOURCE_HASH {path}'
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        assert (image.shape[1], image.shape[0]) == (row['width'], row['height']), f'LABEL_ORIENTATION {path}'
        truth = {c: [[x, y, x + w, y + h] for k, x, y, w, h in row['boxes'] if k == i] for i, c in enumerate(classes)}
        rec = dict(sha256=row['sha256'], truth={c: len(v) for c, v in truth.items()})
        if 'raw' in modes:
            cands, meta = product.model_candidates(image, np.ones(image.shape[:2], bool))
            assert meta['modelHash'] == manifest['modelHash'] and meta['decisionThreshold'] == manifest['confidenceThreshold']
            group = view_group(row['path']); rec['viewGroup'] = group
            for c in classes:
                pred = [(k['confidence'], [k['bounds']['x'], k['bounds']['y'], k['bounds']['x'] + k['bounds']['width'], k['bounds']['y'] + k['bounds']['height']]) for k in cands if k['classCode'] == c]
                t = counts(truth[c], pred)
                for i in range(3): raw_tally[c][i] += t[i]; group_tally[group][c][i] += t[i]
            rec['raw'] = {c: sum(1 for k in cands if k['classCode'] == c) for c in classes}
        if 'upload' in modes:
            up_all_truth_D += len(truth['D'])
            # Upload path applies EXIF transpose; labels use the training decode.
            # Any orientation disagreement is a hard failure, not a metric.
            url = 'data:image/jpeg;base64,' + base64.b64encode(data).decode()
            try:
                result = analyze_upload({'photo': url, 'processingConsent': True})
                view = result['views'][0]
                assert (view['sourceWidth'], view['sourceHeight']) == (image.shape[1], image.shape[0]), 'ORIENTATION_MISMATCH'
                c = view['caries']
                pred = [(k['confidence'], [k['bounds']['x'], k['bounds']['y'], k['bounds']['x'] + k['bounds']['width'], k['bounds']['y'] + k['bounds']['height']]) for k in c['candidates']]
                t = counts(truth['D'], pred)
                for i in range(3): up_tally['D'][i] += t[i]
                rec['upload'] = dict(accepted=True, D=len(pred), roi=view['quality']['roi'])
            except UploadError as error:
                rejected[str(error)] += 1; rec['upload'] = dict(accepted=False, reason=str(error))
        per_image.append(rec)
        if n % 25 == 0: print('images', n, round(time.time() - started, 1), flush=True)
    report = dict(modelHash=manifest['modelHash'], splitSHA256=hashlib.sha256(split_bytes).hexdigest(), images=len(rows),
                  threshold=manifest['confidenceThreshold'], nmsIoU=.45, matchIoU=.5,
                  frozenManifest={c: {k: v for k, v in e.items() if k in ('truePositive', 'falsePositive', 'falseNegative', 'precision', 'recall', 'F1')} for c, e in zip(classes, manifest['evaluation']['classes'])},
                  patientIndependent=False, clinicalValidation=False,
                  negatives='unannotated images excluded from split; no healthy-specificity measured')
    if 'raw' in modes:
        report['rawProductDecoder'] = summarize(raw_tally)
        # The product camera captures frontal/lateral views; the split is
        # dominated by occlusal mirror photos. Report both, never only the mix.
        report['rawByViewGroup'] = {g: dict(images=sum(1 for r in per_image if r.get('viewGroup') == g), **{c: v for c, v in summarize(t).items()}) for g, t in group_tally.items()}
    if 'upload' in modes:
        accepted = sum(1 for r in per_image if r.get('upload', {}).get('accepted'))
        report['uploadProductPath'] = dict(accepted=accepted, rejected=len(rows) - accepted, rejectionReasons=dict(rejected),
            D_onAccepted=summarize(up_tally)['D'],
            D_recallOverAllTestTruthIncludingRejected=up_tally['D'][0] / max(up_all_truth_D, 1),
            scope='D only (adult policy); rejected photos produce no result and are not counted as negatives')
    report['perImage'] = per_image
    Path(args.out).write_text(json.dumps(report, indent=1), 'utf8')
    print(json.dumps({k: v for k, v in report.items() if k != 'perImage'}, indent=1))


if __name__ == '__main__': main()
