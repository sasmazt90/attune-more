"""Verify a class-filtered COCO import without altering source or target ZIPs."""
import argparse
import collections
import json
from pathlib import Path
import zipfile

from audit_roadmap_archives import file_digest, safe_member


def verify(source, filtered, classes):
    checks, removed = [], collections.Counter()
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(filtered) as target:
        for archive in (original, target):
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError('DUPLICATE_ZIP_MEMBER')
            for name in names:
                safe_member(name)
        def pictures(archive):
            return {name for name in archive.namelist()
                    if Path(name).suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp')}
        names = pictures(original)
        if names != pictures(target):
            raise ValueError('IMAGE_SET_CHANGED')
        for name in sorted(names):
            if original.read(name) != target.read(name):
                raise ValueError('IMAGE_BYTES_CHANGED:' + name)
        coco = {n for n in original.namelist() if n.endswith('.coco.json')}
        if not coco or coco != {n for n in target.namelist() if n.endswith('.coco.json')}:
            raise ValueError('ANNOTATION_FILE_SET_CHANGED')
        for name in sorted(coco):
            old, new = json.loads(original.read(name)), json.loads(target.read(name))
            categories = {row['id']: row['name'] for row in old['categories']}
            if old['images'] != new['images']:
                raise ValueError('IMAGE_METADATA_CHANGED')
            if [row for row in old['categories'] if row['name'] in classes] != new['categories']:
                raise ValueError('CATEGORY_MAPPING_CHANGED')
            expected = [row for row in old['annotations'] if categories[row['category_id']] in classes]
            if expected != new['annotations']:
                raise ValueError('TARGET_ANNOTATIONS_CHANGED')
            removed.update(categories[row['category_id']] for row in old['annotations']
                           if categories[row['category_id']] not in classes)
            checks.append({'split': Path(name).parent.name, 'images': len(old['images']),
                           'retainedAnnotations': len(expected), 'imageRecordsIdentical': True,
                           'retainedAnnotationsIdentical': True})
    return {'schemaVersion': 1, 'sourceArchive': Path(source).name,
            'sourceSHA256': file_digest(source), 'filteredArchive': Path(filtered).name,
            'filteredSHA256': file_digest(filtered), 'imageFiles': len(names),
            'allImageBytesIdentical': True, 'splits': checks, 'keptClasses': sorted(classes),
            'removedConfounderAnnotations': dict(removed), 'confounderSourcePreserved': True,
            'trainingVersionByteIdentityVerified': False,
            'note': 'Verifies local import archive derivation. Original confounder annotations '
                    'remain available for evaluation. Remote generated training preprocessing '
                    'and image identity still need export verification.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--filtered', required=True, type=Path)
    parser.add_argument('--classes', required=True, nargs='+')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.source, args.filtered, set(args.classes))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write('\n')
    print('PASS: source images and retained annotations unchanged')
