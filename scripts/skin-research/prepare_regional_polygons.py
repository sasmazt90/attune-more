"""Prepare a reversible Oily/Redness polygon pilot from selected v11 source.

Only original valid polygons are retained. Suspected cross-split relations are
quarantined conservatively, not asserted to be duplicate people/photos. A bad,
box-only or unverified RLE target annotation quarantines its whole image, rather
than silently turning that target into background. Background never means normal.
"""
import argparse
import collections
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from audit_roadmap_archives import file_digest, geometry, safe_member

TARGETS = {'Oily', 'Redness'}


def quarantine_keys(audit):
    """Flag candidates for isolation without promoting them to identity truth."""
    keys = set()
    for pair in audit['perceptualCandidates']:
        if pair['crossSplit']: keys.update([pair['left'], pair['right']])
    for group in audit['filenameCandidates'] + audit['exactGroups']:
        if group['crossSplit']: keys.update(group['members'])
    return keys


def select(data, split, source, quarantine):
    """Preserve source IDs, boxes and polygons exactly; create no normal labels."""
    labels = {row['id']: row['name'] for row in data['categories']}
    anns = collections.defaultdict(list)
    for annotation in data['annotations']:
        if labels[annotation['category_id']] in TARGETS:
            anns[annotation['image_id']].append(annotation)
    images = []; annotations = []; excluded = []
    for image in data['images']:
        name = str(PurePosixPath(split) / image['file_name']); safe_member(name)
        reasons = []
        if source + ':' + name in quarantine: reasons.append('CROSS_SPLIT_CANDIDATE_QUARANTINE')
        rows = anns[image['id']]
        if not rows: reasons.append('NO_TARGET_POSITIVES_NOT_NORMAL_TRUTH')
        shapes = [geometry(a, image['width'], image['height']) for a in rows]
        if any(not shape['validMask'] or not shape['validBox'] for shape in shapes):
            reasons.append('UNSUPPORTED_TARGET_GEOMETRY')
        if reasons:
            excluded.append(dict(path=name, reasons=reasons)); continue
        images.append(copy.deepcopy(image)); annotations.extend(copy.deepcopy(rows))
    return dict(data, images=images, annotations=annotations,
                categories=[copy.deepcopy(c) for c in data['categories'] if c['name'] in TARGETS]), excluded


def prepare(archive, audit, output, source='v11'):
    """Write a new pilot ZIP and provenance; never change source or remote data."""
    if audit['archives'][0]['archiveSHA256'] != file_digest(archive):
        raise ValueError('AUDIT_SOURCE_HASH_MISMATCH')
    quarantined = quarantine_keys(audit)
    counts = {}; rows = []; excluded = []; selected_annotations = 0
    with zipfile.ZipFile(archive) as original, zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as target:
        names = original.namelist()
        if len(names) != len(set(names)): raise ValueError('DUPLICATE_ARCHIVE_MEMBER')
        for name in names: safe_member(name)
        for name in sorted(n for n in names if n.endswith('.coco.json')):
            split = PurePosixPath(name).parent.name
            data = json.loads(original.read(name))
            selected, skipped = select(data, split, source, quarantined)
            labels = {c['id']: c['name'] for c in selected['categories']}
            counts[split] = dict(images=len(selected['images']),
                                 annotations=dict(collections.Counter(labels[a['category_id']] for a in selected['annotations'])))
            selected_annotations += len(selected['annotations']); excluded.extend(skipped)
            target.writestr(name, json.dumps(selected))
            for image in selected['images']:
                path = str(PurePosixPath(split) / image['file_name'])
                raw = original.read(path); target.writestr(path, raw)
                rows.append(dict(path=path, sourceImageId=image['id'], imageSHA256=hashlib.sha256(raw).hexdigest()))
        for name in names:
            if PurePosixPath(name).name.startswith('README'):
                target.writestr(name, original.read(name))
        target.writestr('README.attune.txt', 'Research Oily/Redness polygon subset. Background is unreviewed, never normal truth. Original source and original split names preserved. Candidate relations and unsupported target geometries quarantined. Not an independent camera benchmark; not expert annotation.\n')
    return dict(schemaVersion=1, source=source, sourceArchiveSHA256=file_digest(archive),
                outputArchive=output.name, outputArchiveSHA256=file_digest(output),
                classes=sorted(TARGETS), splits=counts, images=len(rows), annotations=selected_annotations,
                sourceImageBytesUnchanged=True, targetPolygonsUnchanged=True,
                wholeImageLabelsExpandedToRegions=False, normalTruthCreated=False,
                quarantineCandidateKeys=sorted(quarantined), excluded=excluded, imageRows=rows,
                sourceArchivesMutated=False, expertReviewed=False, lockedTestAccepted=False,
                trainingLaunched=False, remoteUploadPerformed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.archive, json.loads(args.audit.read_text()), args.output)
    with args.receipt.open('x') as stream: json.dump(result, stream, indent=2)
    print(json.dumps({k: result[k] for k in ['images', 'annotations', 'splits', 'classes']}))
