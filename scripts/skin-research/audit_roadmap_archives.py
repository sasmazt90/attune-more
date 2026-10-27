"""Read-only COCO ZIP audit before training or claiming a locked holdout.

No archive extraction, annotation repair, inference, or split mutation. Hashes and
geometry are evidence about files, never expert labels or person identities.
Pillow is used only for decoding, exact pixel hashes and perceptual candidates.
"""
import argparse
import collections
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import zipfile

from PIL import Image

VERSION = 'skin-roadmap-coco-audit-v1'
SPLITS = {'train', 'valid', 'validation', 'test'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('UNSAFE_ARCHIVE_MEMBER')
    return path


def finite_numbers(values):
    return all(isinstance(x, (int, float)) and not isinstance(x, bool)
               and math.isfinite(x) for x in values)


def geometry(annotation, width, height):
    """Conservative mask admission; rectangle polygons are box supervision only.

    RLE is recorded unsupported rather than accepted without a COCO decoder.
    Degenerate/self-touching/crossing polygons are rejected, never repaired.
    """
    box = annotation.get('bbox', [])
    valid_box = (isinstance(box, list) and len(box) == 4 and finite_numbers(box)
                 and box[0] >= 0 and box[1] >= 0 and box[2] > 0 and box[3] > 0
                 and box[0] + box[2] <= width + .01
                 and box[1] + box[3] <= height + .01)
    result = {'validBox': bool(valid_box), 'kind': 'box', 'validMask': False}
    seg = annotation.get('segmentation')
    if seg is None or seg == []:
        return result
    if isinstance(seg, dict):
        return {**result, 'kind': 'rle', 'maskReason': 'RLE_DECODER_REQUIRED'}
    if not isinstance(seg, list):
        return {**result, 'kind': 'invalid-polygon', 'maskReason': 'INVALID_POLYGON'}
    rectangles = []
    for polygon in seg:
        if (not isinstance(polygon, list) or len(polygon) < 6
                or len(polygon) % 2 or not finite_numbers(polygon)):
            return {**result, 'kind': 'invalid-polygon', 'maskReason': 'INVALID_POLYGON'}
        points = list(zip(polygon[::2], polygon[1::2]))
        if points[-1] == points[0]:
            points.pop()  # COCO permits an explicit closing point.
        if (len(set(points)) != len(points) or len(points) < 3
                or any(not (0 <= x <= width and 0 <= y <= height) for x, y in points)):
            return {**result, 'kind': 'invalid-polygon', 'maskReason': 'INVALID_OR_OUT_OF_FRAME'}
        area = abs(sum(a[0] * b[1] - a[1] * b[0]
                       for a, b in zip(points, points[1:] + points[:1]))) / 2
        if area < 1:
            return {**result, 'kind': 'invalid-polygon', 'maskReason': 'DEGENERATE_POLYGON'}
        edges = list(zip(points, points[1:] + points[:1]))
        for i, (a, b) in enumerate(edges):
            for j in range(i + 2, len(edges)):
                if i == 0 and j == len(edges) - 1:
                    continue
                if segments_intersect(a, b, *edges[j]):
                    return {**result, 'kind': 'invalid-polygon', 'maskReason': 'SELF_INTERSECTION'}
        rectangles.append(len(points) == 4 and len({x for x, _ in points}) == 2
                          and len({y for _, y in points}) == 2)
    # A mixture containing a rectangle is not claimed to be an exact mask.
    rectangle = any(rectangles)
    return {**result, 'kind': 'rectangle-polygon' if rectangle else 'polygon',
            'validMask': not rectangle}


def segments_intersect(a, b, c, d):
    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    def on(p, q, r):
        return (min(p[0], q[0]) <= r[0] <= max(p[0], q[0])
                and min(p[1], q[1]) <= r[1] <= max(p[1], q[1]))
    v = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
    if v[0] * v[1] < 0 and v[2] * v[3] < 0:
        return True
    return any(abs(k) < 1e-9 and on(p, q, r) for k, p, q, r in
               [(v[0], a, b, c), (v[1], a, b, d), (v[2], c, d, a), (v[3], c, d, b)])


def fingerprints(data):
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        rgb = image.convert('RGB')
        size = rgb.size
        pixels = digest(f'RGB:{size[0]}:{size[1]}:'.encode() + rgb.tobytes())
        thumb = rgb.convert('L').resize((9, 8), Image.Resampling.BICUBIC)
        small = [thumb.getpixel((x, y)) for y in range(8) for x in range(9)]
        bits = ''.join('1' if small[y * 9 + x] > small[y * 9 + x + 1] else '0'
                       for y in range(8) for x in range(8))
        return size, pixels, f'{int(bits, 2):016x}'


def duplicate_groups(rows):
    """Exact bytes/pixels join photos; perceptual proximity only queues review."""
    parents = list(range(len(rows)))
    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    seen = {}
    for i, row in enumerate(rows):
        for field in ('sha256', 'decodedSHA256'):
            key = field, row[field]
            if key in seen:
                parents[find(i)] = find(seen[key])
            else:
                seen[key] = i
    groups = collections.defaultdict(list)
    for i, row in enumerate(rows):
        groups[find(i)].append(row)
    exact = []
    for members in groups.values():
        group = min(r['sha256'] for r in members)
        for row in members:
            row['exactGroup'] = group
        if len(members) > 1:
            splits = sorted({r['split'] for r in members})
            exact.append({'group': group, 'members': [r['key'] for r in members],
                          'splits': splits, 'crossSplit': len(splits) > 1})
    candidates = []
    buckets = collections.defaultdict(list)
    for i, row in enumerate(rows):
        value = int(row['dhash'], 16)
        possible = set()
        for band in range(8):
            possible.update(buckets[(band, value >> (8 * band) & 255)])
        for j in sorted(possible):
            other = rows[j]
            distance = (value ^ int(other['dhash'], 16)).bit_count()
            if row['exactGroup'] != other['exactGroup'] and distance <= 6:
                candidates.append({'left': other['key'], 'right': row['key'],
                                   'distance': distance, 'crossSplit': row['split'] != other['split']})
        for band in range(8):
            buckets[(band, value >> (8 * band) & 255)].append(i)
    return exact, candidates


def filename_candidates(rows):
    """Queue export-name/crop hints; do not join photos or infer identities."""
    groups = collections.defaultdict(list)
    for row in rows:
        name = Path(row['path']).stem.split('.rf.')[0].lower()
        name = re.sub(r'_(jpg|jpeg|png|webp)$', '', name)
        # DC EB-style original crop names retain a numeric parent after an
        # eight-hex upload prefix. Left/right hints alone never prove identity.
        crop = re.fullmatch(r'(?:[a-f0-9]{8}-)?(\d{5,})_(left|right)', name)
        hint = crop[1] if crop else name
        if not crop and len(re.sub('[^a-z0-9]', '', hint)) < 8:
            continue  # e.g. '-', 'i', short generic names cannot group photos.
        groups[(row['source'], hint)].append(row)
    return [{'source': source, 'filenameHint': hint,
             'members': [r['key'] for r in members],
             'splits': sorted({r['split'] for r in members}),
             'crossSplit': len({r['split'] for r in members}) > 1,
             'samePhotoConfirmed': False}
            for (source, hint), members in sorted(groups.items()) if len(members) > 1]


def audit_archive(path, source):
    rows, issues, classes, geometry_counts, readmes = [], [], {}, collections.Counter(), {}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('DUPLICATE_ZIP_MEMBER')
        for name in names:
            safe_member(name)
            if re.search(r'README.*\.txt$', name, re.I):
                readmes[name] = archive.read(name).decode('utf-8-sig')
        annotation_files = sorted(n for n in names if n.endswith('.coco.json'))
        if not annotation_files:
            raise ValueError('NO_COCO_ANNOTATIONS')
        for name in annotation_files:
            folder = PurePosixPath(name).parent
            split = folder.name
            if split not in SPLITS:
                raise ValueError('UNKNOWN_SPLIT:' + split)
            split = 'valid' if split == 'validation' else split
            data = json.loads(archive.read(name))
            images, categories, ids = {}, {}, set()
            for category in data['categories']:
                if category['id'] in categories:
                    raise ValueError('DUPLICATE_CATEGORY_ID')
                categories[category['id']] = category['name']
            for image in data['images']:
                if image['id'] in images:
                    raise ValueError('DUPLICATE_IMAGE_ID')
                image_path = str(folder / safe_member(image['file_name']))
                payload = archive.read(image_path)
                size, decoded, dhash = fingerprints(payload)
                if size != (image['width'], image['height']):
                    issues.append({'image': image_path, 'reason': 'DIMENSION_MISMATCH'})
                row = {'key': source + ':' + image_path, 'source': source, 'path': image_path,
                       'split': split, 'imageId': image['id'], 'width': size[0], 'height': size[1],
                       'sha256': digest(payload), 'decodedSHA256': decoded, 'dhash': dhash,
                       'annotations': 0}
                images[image['id']] = row
                rows.append(row)
            for annotation in data['annotations']:
                if annotation['id'] in ids:
                    raise ValueError('DUPLICATE_ANNOTATION_ID')
                ids.add(annotation['id'])
                row = images[annotation['image_id']]
                label = categories[annotation['category_id']]
                row['annotations'] += 1
                classes.setdefault(label, collections.Counter())[split] += 1
                shape = geometry(annotation, row['width'], row['height'])
                geometry_counts[(label, shape['kind'], shape['validBox'], shape['validMask'])] += 1
                if not shape['validBox'] or shape['kind'] in ('invalid-polygon', 'rle'):
                    issues.append({'image': row['path'], 'annotationId': annotation['id'],
                                   'class': label, **shape})
    return {'source': source, 'archive': Path(path).name, 'archiveSHA256': file_digest(path),
            'images': len(rows), 'splits': dict(collections.Counter(r['split'] for r in rows)),
            'classes': {k: dict(v) for k, v in sorted(classes.items())},
            'geometry': [{'class': label, 'kind': kind, 'validBox': box,
                          'validMask': mask, 'count': count}
                         for (label, kind, box, mask), count in sorted(geometry_counts.items())],
            'issues': issues, 'readmes': readmes, 'rows': rows}


def audit_sources(sources):
    results = [audit_archive(path, source) for source, path in sorted(sources.items())]
    rows = [row for result in results for row in result.pop('rows')]
    exact, candidates = duplicate_groups(rows)
    filenames = filename_candidates(rows)
    cross_exact = sum(group['crossSplit'] for group in exact)
    cross_candidates = sum(pair['crossSplit'] for pair in candidates)
    return {'schemaVersion': 1, 'methodVersion': VERSION, 'archives': results,
            'exactGroups': exact, 'perceptualCandidates': candidates,
            'filenameCandidates': filenames, 'images': rows,
            'summary': {'images': len(rows), 'exactDuplicateGroups': len(exact),
                        'crossSplitExactGroups': cross_exact,
                        'perceptualCandidatePairs': len(candidates),
                        'crossSplitPerceptualCandidatePairs': cross_candidates,
                        'filenameCandidateGroups': len(filenames),
                        'crossSplitFilenameCandidateGroups': sum(g['crossSplit'] for g in filenames),
                        'geometryIssueCount': sum(len(r['issues']) for r in results)},
            'acceptance': {'trainingAuthorizedByThisAudit': False, 'personIndependent': False,
                           'lockedTestAccepted': False, 'thresholdsSelected': False,
                           'sourceArchivesMutated': False, 'expertReviewed': False},
            'limitations': ['Exact groups establish matching files/pixels, not person identity.',
                            'dHash proximity is a review candidate, never ground truth or an automatic merge.',
                            'Export-name/left-right crop hints are candidates only, not photo or person identities.',
                            'Crops, mirrors, collages and different photos of a person may escape this audit.',
                            'Publisher README licences do not establish individual-photo rights.',
                            'Archive splits do not prove previous review/training exposure is absent.',
                            'No missing annotation is inferred to be normal/negative skin.',
                            'COCO geometric validity does not prove annotation semantics or completeness.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append', required=True, metavar='ID=ZIP')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    sources = {}
    for item in args.source:
        key, value = item.split('=', 1)
        if key in sources:
            parser.error('Duplicate source ID')
        sources[key] = value
    # Never overwrite an earlier audit. Caller must choose a new receipt name.
    result = audit_sources(sources)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write('\n')
    print(json.dumps(result['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
