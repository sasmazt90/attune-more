"""Offline evaluation of pinned hosted predictions against a frozen COCO split.

Thresholds are selected on valid only, then locked for test. Uses pycocotools for
AP, and explicit class-aware confidence-ordered one-to-one matching for operating
points at IoU .5. This never enables a model or claims person/camera independence.
"""
import argparse
import collections
import contextlib
import hashlib
import gzip
import io
import json
import math
from pathlib import Path
import zipfile

import numpy as np

CLASSES = ('Pigmentation', 'Pimple', 'Post acne')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def iou(a, b):
    x = max(a[0], b[0]); y = max(a[1], b[1])
    w = max(0., min(a[0] + a[2], b[0] + b[2]) - x)
    h = max(0., min(a[1] + a[3], b[1] + b[3]) - y)
    intersection = w * h
    union = a[2] * a[3] + b[2] * b[3] - intersection
    return intersection / union if union > 0 else 0.


def match_events(truth, predictions, label):
    events = []; total = 0
    for image_id, rows in truth.items():
        boxes = [r['bbox'] for r in rows if r['class'] == label]
        total += len(boxes); used = set()
        ps = sorted((p for p in predictions[image_id] if p['class'] == label),
                    key=lambda p: -p['confidence'])
        for p in ps:
            candidates = [(iou(p['bbox'], b), k) for k, b in enumerate(boxes) if k not in used]
            overlap, idx = max(candidates, default=(0., -1))
            matched = overlap >= .5
            if matched: used.add(idx)
            events.append((p['confidence'], matched))
    return events, total


def point(events, total, threshold):
    found = [is_tp for score, is_tp in events if score >= threshold]
    tp = sum(found); fp = len(found) - tp; fn = total - tp
    precision = tp / (tp + fp) if tp + fp else 0.
    recall = tp / total if total else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    return dict(threshold=threshold, tp=tp, fp=fp, fn=fn,
                precision=precision, recall=recall, f1=f1)


def operating_points(truth, predictions, split, locked=None):
    if split == 'test' and locked is None:
        raise ValueError('TEST_REQUIRES_VALIDATION_LOCKED_THRESHOLDS')
    if split != 'valid' and split != 'test':
        raise ValueError('ONLY_VALID_AND_TEST_SUPPORTED')
    output = {}
    for label in CLASSES:
        events, total = match_events(truth, predictions, label)
        if split == 'valid':
            candidates = [point(events, total, k / 20) for k in range(1, 20)]
            selected = max(candidates, key=lambda p: (p['f1'] or 0., p['threshold']))
        else:
            threshold = locked.get(label)
            if not finite(threshold) or not .05 <= threshold <= .95:
                raise ValueError('INVALID_LOCKED_THRESHOLD')
            selected = point(events, total, threshold)
        output[label] = dict(**selected, groundTruthCount=total)
    return output


def read_snapshot(archive, folder, split):
    with zipfile.ZipFile(archive) as z:
        data = json.loads(z.read(split + '/_annotations.coco.json'))
    categories = {c['id']: c['name'] for c in data['categories']}
    truth = {im['id']: [] for im in data['images']}
    for a in data['annotations']:
        label = categories[a['category_id']]
        if label not in CLASSES: raise ValueError('UNEXPECTED_GROUND_TRUTH_CLASS')
        truth[a['image_id']].append(dict(class_=label, **a))
        truth[a['image_id']][-1]['class'] = label
    images = {im['id']: im for im in data['images']}
    predictions = {}; receipts = []; model_ids = set(); packages = set()
    snapshot_digest = hashlib.sha256()
    location = Path(folder)
    if location.is_file():
        bundle = json.loads(gzip.decompress(location.read_bytes()))
        records = [(r['name'], r['rawJSON'].encode('utf8')) for r in bundle['records'] if r['split'] == split]
        if any(Path(name).name != name for name, _ in records): raise ValueError('INVALID_SNAPSHOT_NAME')
        records.sort()
    else:
        records = [(p.name, p.read_bytes()) for p in sorted(location.glob('*.json'))]
    for name, raw in records:
        row = json.loads(raw)
        if row.get('split') != split: raise ValueError('SNAPSHOT_SPLIT_MISMATCH')
        if row.get('status') != 'ok': raise ValueError('INFERENCE_FAILED:' + name)
        source = row['source']; image_id = source['cocoImageId']
        if image_id in predictions: raise ValueError('DUPLICATE_IMAGE_PREDICTIONS')
        im = images[image_id]
        if row['image'] != dict(width=im['width'], height=im['height']):
            raise ValueError('SOURCE_DIMENSION_MISMATCH')
        if row['resolvedModel']['model_id'] != row['requestedModel']:
            raise ValueError('RESOLVED_MODEL_MISMATCH')
        if row['confidenceFloor'] != .05: raise ValueError('PREDICTION_FLOOR_MISMATCH')
        model_ids.add(row['requestedModel']); packages.add(row['resolvedModel']['model_package_id'])
        predictions[image_id] = []
        for p in row['predictions']:
            if (p['class'] not in CLASSES or not all(finite(p.get(k)) for k in
                ['x', 'y', 'width', 'height', 'confidence']) or p['width'] <= 0
                or p['height'] <= 0 or not 0 <= p['confidence'] <= 1):
                raise ValueError('INVALID_PREDICTION')
            predictions[image_id].append(dict(class_=p['class'], **p,
                bbox=[p['x'] - p['width'] / 2, p['y'] - p['height'] / 2, p['width'], p['height']]))
        snapshot_digest.update(name.encode() + b'\0' + hashlib.sha256(raw).digest())
        receipts.append(dict(id=source['id'], imageId=image_id, inferenceId=row['inferenceId'],
                             predictions=len(row['predictions']), sha256=hashlib.sha256(raw).hexdigest()))
    if set(predictions) != set(images): raise ValueError('INCOMPLETE_SPLIT_PREDICTIONS')
    if len(model_ids) != 1 or len(packages) != 1 or not next(iter(packages)):
        raise ValueError('INCONSISTENT_MODEL_IDENTITY')
    identity = dict(modelId=next(iter(model_ids)), modelPackageId=next(iter(packages)))
    return data, truth, predictions, receipts, identity, snapshot_digest.hexdigest()


def coco_metrics(data, predictions, max_detections=100):
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
    data = dict(data, info=data.get('info', {}))
    categories = {c['name']: c['id'] for c in data['categories'] if c['name'] in CLASSES}
    ps = [dict(image_id=image_id, category_id=categories[p['class']], bbox=p['bbox'],
               score=p['confidence']) for image_id, rows in predictions.items() for p in rows]
    with contextlib.redirect_stdout(io.StringIO()):
        truth = COCO(); truth.dataset = data; truth.createIndex()
        if ps:
            guessed = truth.loadRes(ps)
        else:
            guessed = COCO(); guessed.dataset = dict(images=data['images'], categories=data['categories'], annotations=[]); guessed.createIndex()
        evaluation = COCOeval(truth, guessed, 'bbox')
        evaluation.params.imgIds = sorted(predictions)
        evaluation.params.catIds = sorted(categories.values())
        evaluation.params.maxDets = [1, 10, max_detections]
        evaluation.evaluate(); evaluation.accumulate()
    precision = evaluation.eval['precision']
    mean = lambda a: float(a[a >= 0].mean()) if (a >= 0).any() else None
    class_names = {v: k for k, v in categories.items()}
    per_class = {class_names[c]: dict(map50=mean(precision[0, :, k, 0, -1]),
                                     map50_95=mean(precision[:, :, k, 0, -1]))
                 for k, c in enumerate(evaluation.params.catIds)}
    return dict(maxDetectionsPerImage=max_detections, map50=mean(precision[0, :, :, 0, -1]),
                map50_95=mean(precision[:, :, :, 0, -1]), perClass=per_class)


def evaluate(archive, folder, split, locked=None):
    data, truth, predictions, receipts, identity, snapshot_sha = read_snapshot(archive, folder, split)
    if split == 'test' and (not locked or locked.get('thresholdSelectionSplit') != 'valid'
                           or locked.get('modelIdentity') != identity):
        raise ValueError('TEST_REQUIRES_MATCHING_VALIDATION_LOCK')
    thresholds = locked.get('lockedThresholds') if locked else None
    points = operating_points(truth, predictions, split, thresholds)
    return dict(schemaVersion=1, methodVersion='pinned-coco-detection-evaluation-v1', split=split,
                modelIdentity=identity, images=len(truth), annotationCount=sum(map(len, truth.values())),
                coco=[coco_metrics(data, predictions, cap) for cap in [100, 300]],
                operatingPoints=points, thresholdSelectionSplit='valid',
                lockedThresholds={k: v['threshold'] for k, v in points.items()},
                matchingIoU=.5, confidenceFloor=.05, predictedBoxesClipped=False,
                predictionLimitObserved=max(len(p) for p in predictions.values()),
                imagesAt300Predictions=sum(len(p) == 300 for p in predictions.values()),
                snapshotSHA256=snapshot_sha, sourceArchiveSHA256=hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
                imageReceipts=receipts, modelAccepted=False, lockedTestIndependent=False,
                limitations=['Existing source splits remain provisional due to exposure/duplicate candidates.',
                             'Source image pairing uses unique filename plus exact per-class counts; dimensions checked.',
                             'Prediction floor and 300-output ceiling can limit AP; no below-floor predictions invented.',
                             'Synthetic tests validate evaluator logic, not model or real-camera accuracy.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--split', choices=['valid', 'test'], required=True)
    parser.add_argument('--locked-validation', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    locked = json.loads(args.locked_validation.read_text()) if args.locked_validation else None
    result = evaluate(args.archive, args.snapshots, args.split, locked)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({k: result[k] for k in ['images', 'split', 'coco', 'operatingPoints', 'lockedThresholds']}))
