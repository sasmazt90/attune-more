"""Create an isolated research dataset from explicit source boxes only.

Unannotated photos are excluded, not treated as negatives. Exact and very
similar dHash candidates are conservatively kept in the same partition.
This grouping does not establish person independence or expert label validity.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import zipfile


def prepare(archive, audit, output):
    receipts = {r['path']: r for r in json.loads(audit.read_text())['images']}
    excluded_classes = {'Mantar', 'Sigil'}
    images = []
    with zipfile.ZipFile(archive) as source:
        for name in sorted(n for n in source.namelist() if n.endswith('_annotations.coco.json')):
            data = json.loads(source.read(name))
            categories = {c['id']: c['name'] for c in data['categories']}
            by_image = collections.defaultdict(list)
            for annotation in data['annotations']:
                if categories[annotation['category_id']] not in excluded_classes:
                    by_image[annotation['image_id']].append(annotation)
            for image in data['images']:
                if not by_image[image['id']]:
                    continue
                path = name.rsplit('/', 1)[0] + '/' + image['file_name']
                images.append(dict(meta=image, annotations=by_image[image['id']], receipt=receipts[path]))
        # Conservative co-partitioning, not an assertion of identical identity.
        parent = list(range(len(images)))
        def root(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        near_pairs = 0
        hashes = [int(v['receipt']['dhash'], 16) for v in images]
        for i in range(len(images)):
            for j in range(i):
                if images[i]['receipt']['decodedSHA256'] == images[j]['receipt']['decodedSHA256'] or (hashes[i] ^ hashes[j]).bit_count() <= 3:
                    parent[root(i)] = root(j)
                    near_pairs += 1
        components = collections.defaultdict(list)
        for i, image in enumerate(images):
            components[root(i)].append(image)
        splits = {s: dict(images=[], annotations=[], categories=[c for c in data['categories'] if c['name'] not in excluded_classes and c['name'] != 'objects']) for s in ('train', 'valid', 'test')}
        selected, seen_hashes = [], set()
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as target:
            for component in components.values():
                key = min(v['receipt']['decodedSHA256'] for v in component)
                bucket = int(hashlib.sha256(('attune-boxes-r1:'+key).encode()).hexdigest()[:8], 16) % 100
                split = 'train' if bucket < 70 else 'valid' if bucket < 85 else 'test'
                for image in component:
                    receipt = image['receipt']
                    if receipt['decodedSHA256'] in seen_hashes:
                        continue
                    seen_hashes.add(receipt['decodedSHA256'])
                    dataset = splits[split]
                    identifier = len(dataset['images'])
                    filename = receipt['decodedSHA256'] + '.jpg'
                    target.writestr(split+'/'+filename, source.read(receipt['path']))
                    dataset['images'].append({**image['meta'], 'id': identifier, 'file_name': filename})
                    for annotation in image['annotations']:
                        # Preserve category and exact source geometry. No pseudo masks.
                        dataset['annotations'].append({**annotation, 'id': len(dataset['annotations'])+1, 'image_id': identifier})
                    selected.append(dict(sourcePath=receipt['path'], decodedSHA256=receipt['decodedSHA256'], split=split, group=key))
            for split, dataset in splits.items():
                target.writestr(split+'/_annotations.coco.json', json.dumps(dataset))
            for name in ('README.dataset.txt', 'README.roboflow.txt'):
                if name in source.namelist():
                    target.writestr('source/'+name, source.read(name))
        counts = {}
        for split, dataset in splits.items():
            counts[split] = dict(images=len(dataset['images']), annotations=len(dataset['annotations']), classes=dict(collections.Counter(categories[a['category_id']] for a in dataset['annotations'])))
        summary = dict(source='zgr-mjbpf/dermatoloji_tespit_yz-cxlee/5', sourceArchiveSHA256=hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest(), archiveSHA256=hashlib.file_digest(output.open('rb'), 'sha256').hexdigest(), excludedClasses=sorted(excluded_classes), unannotatedImagesExcluded=True, nearDuplicateGrouping='dHash distance <=3 co-partitioned, no identity assertion', nearCandidatePairs=near_pairs, groups=len(components), splits=counts, annotationSemantics='publisher labels, not expert-verified', clinicalOutputEnabled=False, personIndependent=False)
        output.with_suffix('.manifest.json').write_text(json.dumps(dict(summary=summary, images=selected), ensure_ascii=False, indent=2)+'\n')
        return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('archive', type=Path)
    p.add_argument('audit', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    print(json.dumps(prepare(a.archive, a.audit, a.output), ensure_ascii=False, indent=2))
