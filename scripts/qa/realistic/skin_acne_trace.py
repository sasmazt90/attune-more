#!/usr/bin/env python3
"""Traces every acne detection through the same models and rules the product uses. Changes nothing.

For each photo it records what each detector returned before any rule, then what each rule did to it:
below the 0.35 marker score, merged as the same lesion, off the face, given to the nearest region, or in
a region this pose may not read. It also records the per-region classifier decision that decides whether a region is
shown at all. An overlay of each photo lets the boxes be compared with the photograph.

Usage: skin_acne_trace.py --name char49 --front F.png --right R.png --left L.png --out DIR
Run with the API's Python and environment, on the WEB host.
"""
import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np

sys.path.append('/opt/attune/services/core-api')  # PYTHONPATH comes first, so a dry run can trace changed code
import regional_skin_v3 as R  # noqa: E402
import skin_findings_det as SFD  # noqa: E402
import skin_findings_v1 as SF  # noqa: E402

COLORS = {'kept': (60, 220, 60), 'nearest': (255, 0, 255), 'noRegion': (0, 220, 255), 'poseNotRead': (255, 160, 0), 'merged': (200, 200, 200), 'low': (120, 120, 255)}


def source_landmarks(bgr):
    """Python MediaPipe on the source photo. The product gets the same model's points from the browser."""
    points = SFD.crop_landmarks(bgr)
    if points is None:
        raise RuntimeError('No face found')
    return [{'x': float(p.x), 'y': float(p.y)} for p in points]


def trace_photo(bgr, landmarks, pose):
    from PIL import Image
    rt = R.load_runtime()
    h, w = bgr.shape[:2]
    P = np.array([[p['x'] * w, p['y'] * h] for p in landmarks[:468]], np.float64)
    x0, y0 = P.min(0)
    x1, y1 = P.max(0)
    bw, bh = x1 - x0, y1 - y0
    s = max(bw, bh) * 1.35
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - 0.08 * bh
    X0, Y0, S = int(round(cx - s / 2)), int(round(cy - s / 2)), int(round(s))
    pad = cv2.copyMakeBorder(bgr, S, S, S, S, cv2.BORDER_REPLICATE)
    crop = cv2.resize(pad[Y0 + S:Y0 + 2 * S, X0 + S:X0 + 2 * S], (1024, 1024), interpolation=cv2.INTER_AREA)
    k = 1024 / S
    Pc = (P - [X0, Y0]) * k
    polys = R.region_polys(Pc)
    view = R.VIEW_OF_POSE.get(pose, 'front')
    pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    dets, cats = {}, {}
    for name, (model, spec) in rt['models'].items():
        if spec.get('role') == 'wrinkle-mask':
            continue
        d = model.predict(pil, threshold=0.05)
        dets[name] = [(int(c), float(sc), [float(v) for v in b]) for b, sc, c in zip(d.xyxy.tolist(), d.confidence, d.class_id)]
        cats[name] = {int(key): value for key, value in spec['classes'].items()}

    rows = []
    for name in ('findings', 'acnes'):
        for c, score, box in dets.get(name, []):
            cls = cats[name].get(c)
            sub = SF.ACNE_CLASSES.get((name, cls))
            if sub is None:
                continue
            bx, by = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            region = SF.lesion_region(polys, bx, by, Pc)
            strict = next((SF.APP_OF[rk] for rk in SF.APP_OF if rk in polys and SF._point_in(polys[rk], bx, by)), None)
            rows.append({'strictRegion': strict, 'model': name, 'cls': cls, 'type': sub, 'score': round(score, 4), 'box': [round(v, 1) for v in box],
                         'x': round(bx / k + X0, 1), 'y': round(by / k + Y0, 1), 'r': round(max(box[2] - box[0], box[3] - box[1]) / 2 / k, 1),
                         'region': region, 'usable': bool(region and SF._usable(region, view))})

    # The product's rule, applied to the same rows so each outcome can be named.
    kept = []
    for row in sorted(rows, key=lambda r: -r['score']):
        if row['score'] < SF.MARKER_MIN_SCORE:
            row['outcome'] = 'low'
            continue
        cx_, cy_ = (row['box'][0] + row['box'][2]) / 2, (row['box'][1] + row['box'][3]) / 2
        if any(q['box'][0] <= cx_ <= q['box'][2] and q['box'][1] <= cy_ <= q['box'][3] for q in kept):
            row['outcome'] = 'merged'
            continue
        kept.append(row)
        row['outcome'] = 'noRegion' if row['region'] is None else 'poseNotRead' if not row['usable'] else 'nearest' if row['strictRegion'] is None else 'kept'

    overlay = crop.copy()
    for rk, poly in polys.items():
        cv2.polylines(overlay, [np.asarray(poly, np.int32).reshape(-1, 1, 2)], True, (255, 255, 255), 1, cv2.LINE_AA)
        at = np.asarray(poly).mean(0).astype(int)
        cv2.putText(overlay, SF.APP_OF[rk], tuple(int(v) for v in at), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    for row in sorted(rows, key=lambda r: r['score']):
        if row['outcome'] == 'merged' or row['score'] < 0.15:
            continue
        b = [int(v) for v in row['box']]
        cv2.rectangle(overlay, (b[0], b[1]), (b[2], b[3]), COLORS[row['outcome']], 1 if row['outcome'] == 'low' else 2, cv2.LINE_AA)
        cv2.putText(overlay, '{:.2f}'.format(row['score']), (b[0], max(10, b[1] - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLORS[row['outcome']], 1, cv2.LINE_AA)
    return {'pose': pose, 'view': view, 'rows': rows, 'crop': crop, 'overlay': overlay, 'scale': k, 'offset': [X0, Y0]}


def summarize(rows):
    out = {}
    for row in rows:
        out[row['outcome']] = out.get(row['outcome'], 0) + 1
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--front', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    maps, traces = {}, {}
    for pose, path in (('FRONT', args.front), ('RIGHT', args.right), ('LEFT', args.left)):
        bgr = cv2.imread(path)
        landmarks = source_landmarks(bgr)
        trace = trace_photo(bgr, landmarks, pose)
        cv2.imwrite(str(args.out / '{}-{}-overlay.jpg'.format(args.name, pose)), trace['overlay'], [cv2.IMWRITE_JPEG_QUALITY, 88])
        cv2.imwrite(str(args.out / '{}-{}-crop.jpg'.format(args.name, pose)), trace['crop'], [cv2.IMWRITE_JPEG_QUALITY, 92])
        traces[pose] = {'view': trace['view'], 'scale': trace['scale'], 'offset': trace['offset'], 'outcomes': summarize(trace['rows']),
                        'rows': sorted(trace['rows'], key=lambda r: -r['score'])}
        maps[pose] = R.analyze_photo(bgr, landmarks, pose=pose)
    findings = SF.findings_from_maps(maps)
    acne_rows = [f for f in findings['findings'] if f['id'] == 'acne']
    decisions = SFD.decide({p: maps[p]['findingDet'] for p in maps}, list(SFD.specs(R.MODEL_DIR).values()))
    report = {'name': args.name, 'photos': {'FRONT': args.front, 'RIGHT': args.right, 'LEFT': args.left}, 'traces': traces, 'productAcneRows': acne_rows,
              'regionDecision': [d for d in decisions if d['id'] == 'acne'],
              'boxesPerPose': {p: [b for b in maps[p]['findingBoxes'] if b['finding'] == 'acne'] for p in maps}}
    (args.out / '{}-trace.json'.format(args.name)).write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps({'name': args.name, 'decision': report['regionDecision'], 'product': [{k: v for k, v in r.items() if k != 'markers'} for r in acne_rows],
                      'outcomes': {p: traces[p]['outcomes'] for p in traces}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
