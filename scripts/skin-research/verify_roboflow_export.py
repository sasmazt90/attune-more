"""Compare an uploaded COCO archive with its frozen Roboflow version export.

IDs, export order, JPEG bytes and Roboflow suffixes can change. Match by original
name, dimensions and full labelled geometry, then report split and pixel drift
separately. Lossy similarity is never called exact photo identity or independence.
"""
import argparse
import collections
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

import numpy as np
from PIL import Image

from audit_roadmap_archives import file_digest, safe_member


def original_name(name):
    stem = PurePosixPath(name).name.split('.rf.')[0]
    return re.sub(r'(?:_(?:jpg|jpeg|png|webp))+$', '', stem, flags=re.I)


def annotations_key(annotations, categories):
    def numeric(value):
        if isinstance(value, list):
            return [numeric(v) for v in value]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return value
    return tuple(sorted(json.dumps(dict(label=categories[a['category_id']],
                                        bbox=numeric(a.get('bbox')),
                                        segmentation=numeric(a.get('segmentation', [])),
                                        iscrowd=a.get('iscrowd', 0)), sort_keys=True)
                        for a in annotations))


def index(archive):
    rows = collections.defaultdict(list)
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError('DUPLICATE_ARCHIVE_MEMBER')
    for name in names:
        safe_member(name)
    for name in sorted(n for n in names if n.endswith('.coco.json')):
        data = json.loads(archive.read(name))
        categories = {c['id']: c['name'] for c in data['categories']}
        anns = collections.defaultdict(list)
        for ann in data['annotations']:
            anns[ann['image_id']].append(ann)
        for image in data['images']:
            path = str(PurePosixPath(name).parent / image['file_name'])
            safe_member(path)
            if path not in names:
                raise ValueError('IMAGE_FILE_MISSING')
            key = (original_name(image['file_name']), image['width'], image['height'],
                   annotations_key(anns[image['id']], categories))
            rows[key].append(dict(path=path, split=PurePosixPath(name).parent.name,
                                  annotationCount=len(anns[image['id']])))
    if not rows:
        raise ValueError('NO_COCO_IMAGES')
    return rows


def compare(local, remote):
    pairs, missing, extra, ambiguous = [], [], [], []
    with zipfile.ZipFile(local) as a, zipfile.ZipFile(remote) as b:
        old, new = index(a), index(b)
        for key in sorted(set(old) | set(new)):
            left, right = old.get(key, []), new.get(key, [])
            if not left:
                extra.extend(right)
                continue
            if not right:
                missing.extend(left)
                continue
            if len(left) != 1 or len(right) != 1:
                ambiguous.append(dict(local=left, remote=right))
                continue
            left, right = left[0], right[0]
            ab, bb = a.read(left['path']), b.read(right['path'])
            with Image.open(io.BytesIO(ab)) as image:
                ap = np.asarray(image.convert('RGB'))
            with Image.open(io.BytesIO(bb)) as image:
                bp = np.asarray(image.convert('RGB'))
            shape_matches = ap.shape == bp.shape and ap.shape[:2] == (key[2], key[1])
            error = np.abs(ap.astype(np.int16) - bp.astype(np.int16)) if shape_matches else None
            pairs.append(dict(local=left['path'], remote=right['path'],
                              splitUnchanged=left['split'] == right['split'],
                              encodedBytesIdentical=ab == bb,
                              decodedPixelsIdentical=bool(shape_matches and np.array_equal(ap, bp)),
                              dimensionsVerified=shape_matches, annotationCount=left['annotationCount'],
                              meanAbsoluteChannelError=float(error.mean()) if shape_matches else None,
                              localSHA256=hashlib.sha256(ab).hexdigest(),
                              remoteSHA256=hashlib.sha256(bb).hexdigest()))
    metadata = not (missing or extra or ambiguous)
    return dict(schemaVersion=1, methodVersion='roboflow-coco-export-comparison-v1',
                localArchive=Path(local).name, localArchiveSHA256=file_digest(local),
                remoteArchive=Path(remote).name, remoteArchiveSHA256=file_digest(remote),
                matchingPolicy='Unique original-name/dimensions/full labelled geometry; exact numeric values, no rounding',
                pairedImages=len(pairs), missing=missing, extra=extra, ambiguous=ambiguous,
                metadataAndGeometryMatched=metadata,
                splitsUnchanged=metadata and all(p['splitUnchanged'] for p in pairs),
                allDimensionsVerified=metadata and all(p['dimensionsVerified'] for p in pairs),
                encodedIdenticalImages=sum(p['encodedBytesIdentical'] for p in pairs),
                decodedIdenticalImages=sum(p['decodedPixelsIdentical'] for p in pairs),
                exactPhotoIdentityVerified=metadata and all(p['decodedPixelsIdentical'] for p in pairs),
                lockedTestAccepted=False, photoRightsVerified=False, rows=pairs,
                limitations=['Lossy pixel differences are measured, never declared exact photo identity.',
                             'Matching metadata does not establish prior exposure or person independence.',
                             'No split, annotation or source archive is changed.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local', required=True, type=Path)
    parser.add_argument('--remote', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = compare(args.local, args.remote)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ['pairedImages', 'metadataAndGeometryMatched',
                     'splitsUnchanged', 'allDimensionsVerified', 'encodedIdenticalImages',
                     'decodedIdenticalImages', 'exactPhotoIdentityVerified']}))
