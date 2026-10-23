"""Repartition a private COCO export by source, decoded identity and near hash.

Writes a NEW archive. Source photos, labels and polygon vertices are preserved.
This removes known source-variant split leakage, not unknown person overlap.
Empty annotations are excluded: they are not assumed reviewed healthy negatives.
"""
import argparse
import collections
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import zipfile

import cv2
import numpy as np
from PIL import Image
from pycocotools import mask as masks


def prepare(archive, output, allow_boxes=False, class_map=None, quarantine_invalid=False):
    rows, categories, source_categories = [], None, None
    invalid_rows = []
    def validate_annotations(items, w, h):
        checked = []
        for original in items:
            a = dict(original)
            if class_map:
                source_name = next(c['name'] for c in source_categories if c['id'] == a['category_id'])
                if source_name not in class_map:
                    raise ValueError('Annotated source class missing from explicit mapping')
                a['category_id'] = next(c['id'] for c in categories if c['name'] == class_map[source_name])
            box = a.get('bbox', [])
            if len(box) != 4 or not all(math.isfinite(x) for x in box) or min(box[2:]) <= 0:
                raise ValueError('Invalid source box')
            if min(box[:2]) < 0 or box[0]+box[2] > w+.01 or box[1]+box[3] > h+.01:
                raise ValueError('Box outside original source')
            segmentation = a.get('segmentation')
            if not segmentation and allow_boxes:
                a['area'] = box[2] * box[3]
                checked.append(a)
                continue
            if not isinstance(segmentation, list) or not segmentation:
                raise ValueError('Expected nonempty source instance polygons')
            for polygon in segmentation:
                if len(polygon) < 6 or len(polygon) % 2 or not np.isfinite(polygon).all():
                    raise ValueError('Invalid source polygon')
                if min(polygon) < 0 or max(polygon[::2]) > w or max(polygon[1::2]) > h:
                    raise ValueError('Polygon outside original source')
            # COCO export often writes bounding-box area for polygons.
            # Compute mask area without changing any polygon vertices.
            a['area'] = float(masks.area(masks.merge(masks.frPyObjects(segmentation, h, w))))
            if a['area'] <= 0:
                raise ValueError('Empty instance mask')
            checked.append(a)
        return checked
    with zipfile.ZipFile(archive) as source:
        for member in sorted(n for n in source.namelist() if n.endswith('_annotations.coco.json')):
            split = PurePosixPath(member).parent
            data = json.loads(source.read(member))
            if source_categories is None:
                source_categories = data['categories']
                categories = ([dict(id=i+1, name=name) for i, name in enumerate(sorted(set(class_map.values())))]
                              if class_map else source_categories)
            if source_categories != data['categories']:
                raise ValueError('Category IDs differ across source splits')
            annotations = collections.defaultdict(list)
            for a in data['annotations']:
                annotations[a['image_id']].append(a)
            for im in data['images']:
                path = str(split / im['file_name'])
                if '..' in PurePosixPath(path).parts or path.startswith('/'):
                    raise ValueError('Unsafe archive member')
                raw = source.read(path)
                image = np.asarray(Image.open(io.BytesIO(raw)).convert('RGB'))
                h, w = image.shape[:2]
                if [w, h] != [im['width'], im['height']]:
                    raise ValueError('Image/COCO dimension mismatch')
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
                # D4-normalized pHash catches exact flips/right-angle rotations;
                # arbitrary source rotations are grouped by original filename.
                hashes = []
                for flip in (gray, np.fliplr(gray)):
                    for rotation in range(4):
                        small = cv2.resize(np.rot90(flip, rotation), (32, 32)).astype(np.float32)
                        block = cv2.dct(small)[:8, :8].flatten()
                        bits = block > np.median(block[1:])
                        hashes.append(sum(int(v) << i for i, v in enumerate(bits)))
                try:
                    checked = validate_annotations(annotations[im['id']], w, h)
                except ValueError as error:
                    geometry_errors = {'Invalid source box', 'Box outside original source',
                                       'Expected nonempty source instance polygons', 'Invalid source polygon',
                                       'Polygon outside original source', 'Empty instance mask'}
                    if not quarantine_invalid or str(error) not in geometry_errors:
                        raise
                    invalid_rows.append(dict(member=path, reason=str(error)))
                    continue
                digest = hashlib.sha256(f'{w}x{h}:'.encode() + image.tobytes()).hexdigest()
                rows.append(dict(member=path, image=im, annotations=checked,
                                 source=im.get('extra', {}).get('name', im['file_name'].split('.rf.')[0]),
                                 decoded=digest, rawHash=hashlib.sha256(raw).hexdigest(), phash=min(hashes),
                                 originalSplit=split.name))
        byte_groups = collections.defaultdict(list)
        for row in rows:
            byte_groups[row['decoded']].append(row)
        conflicting = set()
        for key, group in byte_groups.items():
            signatures = {json.dumps(sorted(json.dumps([a['category_id'], a['bbox'], a.get('segmentation')], sort_keys=True)
                                            for a in row['annotations'])) for row in group}
            if len(signatures) > 1:
                conflicting.add(key)
        if conflicting and not quarantine_invalid:
            raise ValueError('Identical decoded pixels have conflicting annotations')
        for row in rows:
            if row['decoded'] in conflicting:
                invalid_rows.append(dict(member=row['member'], reason='Conflicting annotations on identical decoded pixels'))
        rows = [r for r in rows if r['decoded'] not in conflicting]
        parents = list(range(len(rows)))
        def find(i):
            while parents[i] != i:
                parents[i] = parents[parents[i]]; i = parents[i]
            return i
        def union(a, b):
            a, b = find(a), find(b)
            if a != b:
                parents[b] = a
        for key in ('source', 'decoded'):
            seen = {}
            for i, row in enumerate(rows):
                if row[key] in seen: union(i, seen[row[key]])
                else: seen[row[key]] = i
        near = 0
        for i, a in enumerate(rows):
            for j in range(i):
                if (a['phash'] ^ rows[j]['phash']).bit_count() <= 3:
                    union(i, j); near += 1
        groups = collections.defaultdict(list)
        for i, row in enumerate(rows): groups[find(i)].append(row)
        original_cross = sum(len({r['originalSplit'] for r in group}) > 1 for group in groups.values())
        # Deterministic source-group split. Image variants stay in one split;
        # weights balance independent group class presence, not lesion counts.
        active = [g for g in groups.values() if any(r['annotations'] for r in g)]
        class_ids = sorted({a['category_id'] for r in rows for a in r['annotations']})
        signatures = [np.array([int(any(a['category_id'] == c for r in g for a in r['annotations']))
                                for c in class_ids] + [1.]) for g in active]
        totals = sum(signatures); fractions = np.array([.7, .15, .15])
        targets = fractions[:, None] * totals[None, :]
        counts = np.zeros_like(targets)
        order = sorted(range(len(active)), key=lambda i: hashlib.sha256(
            ('attune-source-split-v1:' + min(r['decoded'] for r in active[i])).encode()).hexdigest())
        assignments = {}
        for i in order:
            delta = ((counts + signatures[i] - targets)**2 - (counts - targets)**2) / np.maximum(targets, 1)
            chosen = int(delta.sum(axis=1).argmin()); counts[chosen] += signatures[i]
            for row in active[i]: assignments[row['member']] = ('train', 'valid', 'test')[chosen]
        documents = {s: dict(images=[], annotations=[], categories=categories,
                             licenses=data.get('licenses', [])) for s in ('train', 'valid', 'test')}
        receipts, group_splits = [], collections.defaultdict(set)
        emitted, skipped_duplicates = {}, 0
        partial = Path(str(output) + '.partial')
        with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as destination:
            def write(name, content):
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                destination.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED)
            for row_index, row in enumerate(rows):
                if not row['annotations']: continue
                signature = sorted(json.dumps([a['category_id'], a['bbox'], a.get('segmentation')], sort_keys=True)
                                   for a in row['annotations'])
                if row['decoded'] in emitted:
                    if emitted[row['decoded']] != signature:
                        raise ValueError('Identical decoded pixels have conflicting annotations')
                    skipped_duplicates += 1
                    continue
                emitted[row['decoded']] = signature
                split_name = assignments[row['member']]; doc = documents[split_name]
                name = row['rawHash'] + '.jpg'; im = dict(row['image']); im.update(id=len(doc['images']), file_name=name)
                im['extra'] = dict(im.get('extra', {}), sourceGroup=find(row_index))
                doc['images'].append(im)
                for a in row['annotations']:
                    a = dict(a); a.update(id=len(doc['annotations'])+1, image_id=im['id']);doc['annotations'].append(a)
                write(f'{split_name}/{name}', source.read(row['member']))
                group_splits[find(row_index)].add(split_name)
                receipts.append(dict(member=row['member'], split=split_name, sourceGroup=find(row_index),
                                     decodedSHA256=row['decoded'], rawSHA256=row['rawHash']))
            for split_name, doc in documents.items():
                if not doc['images']: raise ValueError('Empty output split')
                write(f'{split_name}/_annotations.coco.json', json.dumps(doc))
        assert all(len(s) == 1 for s in group_splits.values())
        partial.replace(output)
        result = dict(sourceArchiveSHA256=hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
                      outputArchiveSHA256=hashlib.sha256(Path(output).read_bytes()).hexdigest(),
                      inputImages=len(rows)+len(invalid_rows), validGeometryImages=len(rows),
                      sourceNameGroups=len({r['source'] for r in rows}),
                      groupedSources=len(active), nearHashPairs=near, originalCrossSplitGroups=original_cross,
                      outputCrossSplitGroups=0, excludedUnverifiedEmptyImages=sum(not r['annotations'] for r in rows),
                      identicalPixelDuplicatesSkipped=skipped_duplicates,
                      quarantinedInvalidImages=invalid_rows,
                      boxesOnlyAllowed=allow_boxes,
                      explicitClassMap=class_map,
                      polygonsChanged=False,
                      areaRecomputedFromMask=any(a.get('segmentation') for r in rows for a in r['annotations']),
                      personIndependent=False,
                      classOrder={c['id']: c['name'] for c in categories if c['id'] in class_ids},
                      splits={s: dict(images=len(d['images']), annotations=len(d['annotations']),
                                      sourceGroups=sum(s in v for v in group_splits.values()),
                                      byClass=dict(collections.Counter(a['category_id'] for a in d['annotations'])))
                              for s, d in documents.items()}, images=receipts)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path); parser.add_argument('output', type=Path)
    parser.add_argument('--allow-boxes', action='store_true', help='Preserve detection boxes without inventing masks')
    parser.add_argument('--quarantine-invalid', action='store_true', help='Exclude and report complete images with malformed geometry')
    parser.add_argument('--class-map', type=Path, help='Explicit JSON source-name to target-name mapping')
    args = parser.parse_args()
    report = prepare(args.archive, args.output, args.allow_boxes,
                     json.loads(args.class_map.read_text()) if args.class_map else None, args.quarantine_invalid)
    args.output.with_suffix('.manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'images'}, indent=2))
