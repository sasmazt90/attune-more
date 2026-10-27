"""Rebuild a private inspection bundle from pinned COCO sources, never training truth.

Original bytes, source annotations and licences survive unchanged. Candidate
selection uses train records only; test/validation pixels are never rendered.
No relabeling, bbox-to-mask conversion, identity inference or network operation.
"""
import argparse
import collections
import copy
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from audit_roadmap_archives import file_digest, geometry, safe_member


def write_member(archive, name, payload):
    """Keep the ZIP replay deterministic; the source bytes remain verbatim."""
    safe_member(name)
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, payload)


def read_json(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf8') as stream:
        return json.load(stream)


def cross_split_keys(audit):
    keys = set()
    for field in ('exactGroups', 'filenameCandidates'):
        for group in audit[field]:
            if group['crossSplit']:
                keys.update(group['members'])
    for pair in audit['perceptualCandidates']:
        if pair['crossSplit']:
            keys.update((pair['left'], pair['right']))
    return keys


def existing_matches(rows, previous):
    index = collections.defaultdict(set)
    for row in previous:
        for field in ('sha256', 'decodedSHA256'):
            index[(field, row[field])].add(row['key'])
    return {row['key']: sorted({key for field in ('sha256', 'decodedSHA256')
                               for key in index.get((field, row[field]), ())})
            for row in rows}


def choose_review_rows(audit, previous, source_annotations, quotas):
    blocked = cross_split_keys(audit)
    matches = existing_matches(audit['images'], previous)
    rows = sorted(audit['images'], key=lambda r: hashlib.sha256(r['key'].encode()).hexdigest())
    selected, seen, shortfalls = [], set(), []
    for source, label, supervision, requested in quotas:
        count = 0
        for row in rows:
            if (row['source'] != source or row['split'] != 'train'
                    or row['key'] in blocked or matches[row['key']]
                    or row['exactGroup'] in seen):
                continue
            annotations = source_annotations[row['key']]
            acceptable = []
            for annotation in annotations:
                if annotation['sourceLabel'] != label:
                    continue
                shape = geometry(annotation['raw'], row['width'], row['height'])
                # Bad geometry remains preserved in the source, but cannot be
                # the reason an image is selected for a particular quota.
                if shape['validBox'] and (shape['validMask'] if supervision == 'mask'
                                           else not shape['validMask']):
                    acceptable.append(annotation['raw']['id'])
            if not acceptable:
                continue
            selected.append({**row, 'selectionTarget': label,
                             'selectionSupervision': supervision,
                             'selectionAnnotationIds': acceptable,
                             'reviewStatus': 'pending', 'expertReviewed': False,
                             'commercialTrainingAccepted': False})
            seen.add(row['exactGroup'])
            count += 1
            if count == requested:
                break
        if count < requested:
            shortfalls.append({'source': source, 'target': label, 'supervision': supervision,
                               'requested': requested, 'availableSelected': count})
    return selected, matches, shortfalls


def build_bundle(audit, source_paths, previous, quotas, metadata, destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('PRESERVE_EXISTING_REVIEW_BUNDLE')
    by_source = {a['source']: a for a in audit['archives']}
    annotations, documents = {}, {}
    for source, path in source_paths.items():
        if file_digest(path) != by_source[source]['archiveSHA256']:
            raise ValueError('SOURCE_ARCHIVE_HASH_MISMATCH:' + source)
        with zipfile.ZipFile(path) as archive:
            # Only source-train annotations are selected, never an aggregate
            # image-level label or absence of an annotation.
            doc = json.loads(archive.read('train/_annotations.coco.json'))
            documents[source] = doc
            cats = {r['id']: r['name'] for r in doc['categories']}
            images = {r['id']: r for r in doc['images']}
            for image in images.values():
                key = source + ':train/' + image['file_name']
                annotations[key] = []
            for ann in doc['annotations']:
                image = images[ann['image_id']]
                key = source + ':train/' + image['file_name']
                annotations[key].append({'sourceLabel': cats[ann['category_id']], 'raw': ann})
    selected, matches, shortfalls = choose_review_rows(audit, previous, annotations, quotas)
    manifest = {
        'schemaVersion': 1, 'purpose': 'source-pair inspection; NOT a training dataset',
        'sources': metadata, 'images': selected, 'shortfalls': shortfalls,
        'originalGeometryPreserved': True, 'imageBytesPreserved': True,
        'reviewSplit': 'source train only', 'personIndependent': False,
        'allLabelsAreUnreviewedSourceClaims': True,
        'commercialTrainingAccepted': False, 'trainingLaunched': False,
        'knownExistingImageMatches': {k: v for k, v in matches.items() if v},
        'excludedCrossSplitCandidateKeys': sorted(cross_split_keys(audit)),
        'selectionCounts': dict(collections.Counter(
            r['source'] + ':' + r['selectionTarget'] + ':' + r['selectionSupervision'] for r in selected)),
        'limitations': [
            'Geometric validity does not establish visible target semantics or annotation completeness.',
            'No prediction or missing annotation establishes regional normal skin.',
            'Exact/near-duplicate filtering does not establish subject-disjoint splits.',
            'Source augmentation and existing image edits are not undone.',
            'Source licence declarations do not establish individual photo permissions.',
            'No facial images or rendered boards belong in the public code repository.'
        ]
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as out:
        for source, path in source_paths.items():
            chosen = [r for r in selected if r['source'] == source]
            ids = {r['imageId'] for r in chosen}
            doc = copy.deepcopy(documents[source])
            doc['images'] = [r for r in doc['images'] if r['id'] in ids]
            doc['annotations'] = [r for r in doc['annotations'] if r['image_id'] in ids]
            # Source IDs, categories, polygon coordinates and boxes are verbatim.
            write_member(out, source + '/train/_annotations.coco.json', json.dumps(doc, ensure_ascii=False))
            with zipfile.ZipFile(path) as archive:
                for row in chosen:
                    safe_member(row['path'])
                    payload = archive.read(row['path'])
                    if hashlib.sha256(payload).hexdigest() != row['sha256']:
                        raise ValueError('SOURCE_IMAGE_HASH_MISMATCH')
                    write_member(out, source + '/' + row['path'], payload)
                for name in archive.namelist():
                    if PurePosixPath(name).name.lower().startswith(('readme', 'license')):
                        safe_member(name)
                        write_member(out, source + '/source-documents/' + name, archive.read(name))
        write_member(out, 'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        write_member(out, 'REVIEW_ONLY.txt', 'Unreviewed source image-annotation pairs. No training, '
                     'product normal labels, subject independence or commercial clearance is established. '
                     'Preserve source attributions and inspect source geometry before any relabeling.\n')
    manifest['bundleSHA256'] = file_digest(destination)
    manifest['bundleBytes'] = destination.stat().st_size
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', required=True)
    parser.add_argument('--source', action='append', required=True, metavar='ID=ZIP')
    parser.add_argument('--previous-audit', action='append', default=[])
    parser.add_argument('--config', required=True, help='Source metadata and target quotas JSON')
    parser.add_argument('--output', required=True)
    parser.add_argument('--manifest', required=True)
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    if manifest_path.exists():
        raise FileExistsError('PRESERVE_EXISTING_REVIEW_MANIFEST')
    previous = [row for p in args.previous_audit for row in read_json(p)['images']]
    config = read_json(args.config)
    result = build_bundle(read_json(args.audit), dict(s.split('=', 1) for s in args.source),
                          previous, config['quotas'], config['sources'], args.output)
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'selectedImages': len(result['images']), 'counts': result['selectionCounts'],
                      'shortfalls': result['shortfalls'], 'bundleSHA256': result['bundleSHA256']}))


if __name__ == '__main__':
    main()
