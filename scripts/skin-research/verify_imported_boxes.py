"""Verify an actual Roboflow export against the prepared source archive before training.

Image identity uses the original SHA in the retained filename, dimensions and
pixel similarity: Roboflow JPEG re-encoding need not preserve decoded hashes.
No uploads, training or source mutation. Output contains aggregate evidence only.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
import numpy as np
from PIL import Image
from scipy.optimize import linear_sum_assignment


def records(z):
    out = []
    for path in sorted(n for n in z.namelist() if n.endswith('_annotations.coco.json')):
        split = path.rsplit('/', 1)[0]
        d = json.loads(z.read(path)); cats = {c['id']: c['name'] for c in d['categories']}
        annotations = defaultdict(list)
        for a in d['annotations']:
            annotations[a['image_id']].append((cats[a['category_id']], a['bbox']))
        for image in d['images']:
            match = re.match(r'^([a-f0-9]{64})(?:\.jpg|_jpg\.)', image['file_name'])
            if not match:
                raise ValueError('SOURCE_IDENTITY_MISSING')
            out.append(dict(identity=match[1], split=split, image=image,
                            path=split+'/'+image['file_name'], annotations=annotations[image['id']]))
    return out


def verify(prepared, manifest, exported):
    provenance = json.loads(manifest.read_text())
    expected_rows = {r['decodedSHA256']: r for r in provenance['images']}
    issues, counts, groups, hashes = [], defaultdict(Counter), defaultdict(set), defaultdict(set)
    prepared_hash=hashlib.file_digest(prepared.open('rb'),'sha256').hexdigest()
    if prepared_hash != provenance['summary']['archiveSHA256']:
        issues.append('SOURCE_ARCHIVE_HASH_MISMATCH')
    labels, class_images, max_pixel_difference, max_geometry_difference, geometry_changed = Counter(), defaultdict(Counter), 0., 0., 0
    seen, recoded = set(), 0
    with zipfile.ZipFile(prepared) as original, zipfile.ZipFile(exported) as actual:
        originals = {r['identity']: r for r in records(original)}
        for row in records(actual):
            identity, split = row['identity'], row['split']
            if identity in seen or identity not in expected_rows:
                issues.append('DUPLICATE_OR_UNKNOWN_SOURCE'); continue
            seen.add(identity); reference = originals[identity]
            if split != expected_rows[identity]['split']:
                issues.append('SOURCE_SPLIT_CHANGED')
            groups[split].add(expected_rows[identity]['group'])
            pixels = np.array(Image.open(io.BytesIO(actual.read(row['path']))).convert('RGB'))
            source = np.array(Image.open(io.BytesIO(original.read(reference['path']))).convert('RGB'))
            h, w = pixels.shape[:2]
            if pixels.shape != source.shape or (w,h) != (row['image']['width'],row['image']['height']):
                issues.append('SOURCE_DIMENSIONS_CHANGED'); continue
            difference = float(np.mean(np.abs(pixels.astype(float)-source.astype(float))))
            max_pixel_difference = max(max_pixel_difference, difference)
            if difference > 8:
                issues.append('SOURCE_PIXELS_DIFFER')
            recoded += int(not np.array_equal(source,pixels))
            hashes[split].add(hashlib.sha256(pixels.tobytes()).hexdigest())
            counts[split]['images'] += 1
            counts[split]['annotated' if row['annotations'] else 'unannotated'] += 1
            counts[split]['annotations'] += len(row['annotations'])
            current, previous = defaultdict(list), defaultdict(list)
            for label,box in row['annotations']:
                labels[label] += 1; current[label].append(box)
                b = np.asarray(box,dtype=float)
                if len(b)!=4 or not np.isfinite(b).all() or min(b[:2])<0 or min(b[2:])<=0 or b[0]+b[2]>w+.001 or b[1]+b[3]>h+.001:
                    issues.append('INVALID_BOX')
            for label in current:class_images[label][split]+=1
            for label,box in reference['annotations']: previous[label].append(box)
            if {k:len(v) for k,v in current.items()} != {k:len(v) for k,v in previous.items()}:
                issues.append('CLASS_ANNOTATION_COUNTS_CHANGED'); continue
            changed = False
            for label,boxes in current.items():
                a,b = np.asarray(boxes),np.asarray(previous[label])
                delta=np.max(np.abs(a[:,None,:]-b[None,:,:]),axis=2)
                ri,ci=linear_sum_assignment(delta)
                maximum=float(delta[ri,ci].max())
                max_geometry_difference=max(max_geometry_difference,maximum)
                changed |= maximum>0
                if maximum>1.01:issues.append('BOX_GEOMETRY_CHANGED_OVER_ONE_PIXEL')
            geometry_changed += int(changed)
    overlaps = {a+'-'+b:len(hashes[a]&hashes[b]) for a in hashes for b in hashes if a<b}
    group_overlaps = {a+'-'+b:len(groups[a]&groups[b]) for a in groups for b in groups if a<b}
    if seen != set(expected_rows):issues.append('SOURCE_SET_CHANGED')
    if any(overlaps.values()) or any(group_overlaps.values()):issues.append('SPLIT_LEAKAGE')
    if any(v.get('unannotated',0) for v in counts.values()):issues.append('UNANNOTATED_IMAGE')
    for value in counts.values():value.setdefault('unannotated',0)
    return dict(passed=not issues,preparedArchiveSHA256=prepared_hash,
                actualExportSHA256=hashlib.file_digest(exported.open('rb'),'sha256').hexdigest(),
                splits=dict(counts),classes=dict(labels),classPositiveImages=dict(class_images),exactImageOverlaps=overlaps,groupOverlaps=group_overlaps,
                jpegRecodedImages=recoded,maxMeanAbsolutePixelDifference=max_pixel_difference,
                imagesWithAdjustedBoxGeometry=geometry_changed,maxBoxCoordinateDifferencePixels=max_geometry_difference,
                boxTolerancePixels=1.01,pixelDifferenceLimit=8,issues=dict(Counter(issues)))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('prepared',type=Path);p.add_argument('manifest',type=Path)
    p.add_argument('exported',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    result=verify(args.prepared,args.manifest,args.exported)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
