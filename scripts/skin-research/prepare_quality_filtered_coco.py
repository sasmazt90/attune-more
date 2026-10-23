"""Filter degraded train variants only, retaining frozen validation/test bytes.

Quality scores are a deterministic pixel screen, not medical label approval.
No photos, masks, boxes or group assignments are synthesized or corrected.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import zipfile


def prepare(source_archive, source_manifest, quality_audit, output, threshold=.01):
    manifest = json.loads(Path(source_manifest).read_text())
    audit = json.loads(Path(quality_audit).read_text())
    if hashlib.sha256(Path(source_archive).read_bytes()).hexdigest() != manifest['outputArchiveSHA256']:
        raise ValueError('Source archive differs from the frozen manifest')
    training = [r for r in audit['rows'] if r['split'] == 'train']
    scores = {r['filename'][:64]: r['impulse'] for r in training}
    if len(scores) != len(training) or not 0 <= threshold <= 1 or any(
            not math.isfinite(v) or not 0 <= v <= 1 for v in scores.values()):
        raise ValueError('Invalid or duplicate training quality measurements')
    expected = {r['rawSHA256'] for r in manifest['images'] if r['split'] == 'train'}
    if set(scores) != expected:
        raise ValueError('Quality audit does not cover exactly the frozen training images')
    removed = {key for key, score in scores.items() if score > threshold}
    retained = [r for r in manifest['images'] if r['rawSHA256'] not in removed]
    old_groups = {r['sourceGroup'] for r in manifest['images'] if r['split'] == 'train'}
    new_groups = {r['sourceGroup'] for r in retained if r['split'] == 'train'}
    if old_groups != new_groups:
        raise ValueError('Quality filtering would remove an entire source group')
    partial = Path(str(output)+'.partial'); hashes = {}; splits = {}
    with zipfile.ZipFile(source_archive) as source, zipfile.ZipFile(partial,'w',zipfile.ZIP_DEFLATED) as dest:
        def write(name, raw):
            info = zipfile.ZipInfo(name,(1980,1,1,0,0,0))
            dest.writestr(info,raw,compress_type=zipfile.ZIP_DEFLATED)
        for split in ('train','valid','test'):
            name = split+'/_annotations.coco.json'; raw = source.read(name); doc = json.loads(raw)
            if split == 'train':
                doc['images'] = [im for im in doc['images'] if im['file_name'][:64] not in removed]
                ids = {im['id'] for im in doc['images']}
                doc['annotations'] = [a for a in doc['annotations'] if a['image_id'] in ids]
                raw = json.dumps(doc).encode()
            else:
                hashes[split] = hashlib.sha256(raw).hexdigest()
            write(name,raw)
            for im in doc['images']:
                member=split+'/'+im['file_name'];write(member,source.read(member))
            splits[split] = dict(images=len(doc['images']), annotations=len(doc['annotations']),
                sourceGroups=len({r['sourceGroup'] for r in retained if r['split']==split}),
                byClass=dict(collections.Counter(a['category_id'] for a in doc['annotations'])))
    partial.replace(output)
    manifest.update(outputArchiveSHA256=hashlib.sha256(Path(output).read_bytes()).hexdigest(),
        images=retained,splits=splits,qualityFilter=dict(onlySplit='train',
        metric=audit['metric'],threshold=threshold,excludedImages=len(removed),
        excludedRawSHA256=sorted(removed),sourceTrainingGroupsPreserved=True,
        qualityAuditSHA256=hashlib.sha256(Path(quality_audit).read_bytes()).hexdigest(),
        sourcePreparedArchiveSHA256=hashlib.sha256(Path(source_archive).read_bytes()).hexdigest(),
        unchangedValidTestAnnotationSHA256=hashes,medicalLabelsReviewed=False))
    return manifest


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source_archive','source_manifest','quality_audit','output'):p.add_argument(name,type=Path)
    p.add_argument('--threshold',type=float,default=.01)
    a=p.parse_args();result=prepare(a.source_archive,a.source_manifest,a.quality_audit,a.output,a.threshold)
    a.output.with_suffix('.manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(splits=result['splits'],excludedImages=result['qualityFilter']['excludedImages'],sha256=result['outputArchiveSHA256']),indent=2))
