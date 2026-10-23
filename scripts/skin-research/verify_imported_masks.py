"""Extend source-image/box import parity with per-instance native mask parity.

No API calls. Match category names and boxes, then compare source-pixel masks
inside tight crops. A one-pixel rasterization boundary tolerance is explicit.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import zipfile

import cv2
import numpy as np
from pycocotools import mask as masks
from scipy.optimize import linear_sum_assignment

from verify_imported_boxes import verify


def mask_records(archive):
    rows = {}
    with zipfile.ZipFile(archive) as source:
        for name in source.namelist():
            if not name.endswith('_annotations.coco.json'): continue
            data = json.loads(source.read(name)); categories = {c['id']: c['name'] for c in data['categories']}
            annotations = defaultdict(list)
            for a in data['annotations']:
                annotations[a['image_id']].append((categories[a['category_id']], a))
            for im in data['images']:
                match = re.match(r'^[a-f0-9]{64}', im['file_name'])
                if not match: raise ValueError('SOURCE_IDENTITY_MISSING')
                rows[match[0]] = dict(image=im, annotations=annotations[im['id']])
    return rows


def verify_masks(prepared, manifest, exported):
    result = verify(prepared, manifest, exported)
    expected, actual = mask_records(prepared), mask_records(exported)
    issues = Counter(result['issues']); checked, minimum_iou = 0, 1.
    kernel = np.ones((3, 3), np.uint8)
    for key, row in actual.items():
        if key not in expected: continue
        previous = expected[key]; width, height = row['image']['width'], row['image']['height']
        old, new = defaultdict(list), defaultdict(list)
        for category, a in previous['annotations']: old[category].append(a)
        for category, a in row['annotations']: new[category].append(a)
        if {c:len(v) for c,v in old.items()} != {c:len(v) for c,v in new.items()}: continue
        for category, values in new.items():
            reference = old[category]
            box_a = np.array([a['bbox'] for a in values]); box_b = np.array([a['bbox'] for a in reference])
            ri, ci = linear_sum_assignment(np.abs(box_a[:,None,:]-box_b[None,:,:]).max(axis=2))
            for i, j in zip(ri, ci):
                pair = [values[i], reference[j]]
                x = max(0, int(np.floor(min(a['bbox'][0] for a in pair)))-2)
                y = max(0, int(np.floor(min(a['bbox'][1] for a in pair)))-2)
                right = min(width, int(np.ceil(max(a['bbox'][0]+a['bbox'][2] for a in pair)))+2)
                bottom = min(height, int(np.ceil(max(a['bbox'][1]+a['bbox'][3] for a in pair)))+2)
                rendered = []
                for a in pair:
                    if not isinstance(a.get('segmentation'), list) or not a['segmentation']:
                        issues['MISSING_OR_UNSUPPORTED_INSTANCE_MASK'] += 1; break
                    polygons = []
                    for polygon in a['segmentation']:
                        points = np.array(polygon, dtype=float).reshape(-1,2)
                        if not np.isfinite(points).all(): raise ValueError('NONFINITE_MASK')
                        polygons.append((points-np.array([x,y])).reshape(-1).tolist())
                    rendered.append(masks.decode(masks.merge(masks.frPyObjects(polygons, bottom-y, right-x))))
                if len(rendered) != 2: continue
                a, b = rendered
                if not a.any() or not b.any(): issues['EMPTY_INSTANCE_MASK'] += 1; continue
                iou = float(np.logical_and(a,b).sum()/np.logical_or(a,b).sum())
                minimum_iou = min(minimum_iou, iou); checked += 1
                if np.any(a & (1-cv2.dilate(b,kernel))) or np.any(b & (1-cv2.dilate(a,kernel))):
                    issues['INSTANCE_MASK_CHANGED_OVER_ONE_PIXEL'] += 1
    result.update(passed=not issues, issues=dict(issues), nativeInstanceMasksChecked=checked,
                  minimumInstanceRasterIoU=minimum_iou, maskBoundaryTolerancePixels=1)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('prepared','manifest','exported','output'): p.add_argument(name,type=Path)
    args = p.parse_args(); result = verify_masks(args.prepared,args.manifest,args.exported)
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
