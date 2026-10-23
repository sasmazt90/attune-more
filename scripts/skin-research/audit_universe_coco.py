"""Read-only audit of a Universe COCO archive; private image receipts stay outside Git.

Usage: python scripts/skin-research/audit_universe_coco.py ARCHIVE OUTPUT_DIRECTORY
No training, uploads, class relabeling, or source archive mutation.
"""
import argparse
import collections
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import zipfile

from PIL import Image, ImageDraw, ImageOps


def audit(archive, output):
    output.mkdir(parents=True, exist_ok=True)
    by_class = collections.defaultdict(lambda: collections.Counter())
    groups = collections.defaultdict(list)
    issues, receipts, preview = [], [], []
    seen_preview = collections.Counter()
    with zipfile.ZipFile(archive) as source:
        for annotation_path in sorted(n for n in source.namelist() if n.endswith('_annotations.coco.json')):
            data = json.loads(source.read(annotation_path))
            parent = PurePosixPath(annotation_path).parent
            split = parent.name
            categories = {v['id']: v['name'] for v in data['categories']}
            annotations = collections.defaultdict(list)
            for item in data['annotations']:
                annotations[item['image_id']].append(item)
            for meta in data['images']:
                name = str(parent / meta['file_name'])
                if '..' in PurePosixPath(name).parts or name.startswith('/'):
                    raise ValueError('Unsafe archive member')
                raw = source.read(name)
                image = Image.open(io.BytesIO(raw)).convert('RGB')
                width, height = image.size
                pixel_hash = hashlib.sha256(f'{width}x{height}:'.encode() + image.tobytes()).hexdigest()
                small = image.resize((9, 8)).convert('L')
                values = list(small.getdata())
                dhash = sum((values[y*9+x] > values[y*9+x+1]) << (y*8+x) for y in range(8) for x in range(8))
                labels = set()
                valid_boxes = []
                if (width, height) != (meta['width'], meta['height']):
                    issues.append(dict(image=name, problem='image-metadata-size-mismatch', actual=[width, height], declared=[meta['width'], meta['height']]))
                for item in annotations[meta['id']]:
                    label = categories[item['category_id']]
                    labels.add(label)
                    by_class[label][split + 'Annotations'] += 1
                    box = item.get('bbox', [])
                    valid = len(box) == 4 and all(isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) for v in box)
                    valid = valid and box[2] > 0 and box[3] > 0 and box[0] >= 0 and box[1] >= 0 and box[0]+box[2] <= width+1 and box[1]+box[3] <= height+1
                    if not valid:
                        issues.append(dict(image=name, annotation=item['id'], label=label, problem='invalid-box'))
                    else:
                        valid_boxes.append((label, box))
                    mask = item.get('segmentation')
                    if isinstance(mask, dict) and mask.get('size') != [height, width]:
                        issues.append(dict(image=name, annotation=item['id'], label=label, problem='rle-size-mismatch'))
                for label in labels:
                    by_class[label][split + 'Images'] += 1
                receipt = dict(path=name, split=split, sha256=hashlib.sha256(raw).hexdigest(), decodedSHA256=pixel_hash, dhash=f'{dhash:016x}', dimensions=[width, height], labels=sorted(labels), annotations=len(annotations[meta['id']]))
                groups[pixel_hash].append(receipt)
                receipts.append(receipt)
                # Training-only visual boards do not open validation/test images.
                for label in sorted(labels):
                    if split != 'train' or seen_preview[label] >= 6:
                        continue
                    seen_preview[label] += 1
                    tile = Image.new('RGB', (300, 330), 'white')
                    marked = image.copy()
                    draw = ImageDraw.Draw(marked)
                    for box_label, box in valid_boxes:
                        if box_label == label:
                            x, y, w, h = box
                            draw.rectangle((x, y, x+w, y+h), outline='#00ffff', width=max(1, width//200))
                    marked.thumbnail((300, 295))
                    tile.paste(marked, (0, 30))
                    ImageDraw.Draw(tile).text((5, 5), f'{label} | {seen_preview[label]}', fill='black')
                    preview.append((label, tile, name))
    duplicates = [rows for rows in groups.values() if len(rows) > 1]
    cross = [rows for rows in duplicates if len({r['split'] for r in rows}) > 1]
    summary = dict(schemaVersion=1, archiveSHA256=hashlib.file_digest(open(archive, 'rb'), 'sha256').hexdigest(), images=len(receipts), uniqueDecodedImages=len(groups), exactDuplicateGroups=len(duplicates), crossSplitExactGroups=len(cross), classes=dict(sorted(by_class.items())), issues=dict(collections.Counter(v['problem'] for v in issues)), personIndependent=False, annotationSemanticsReviewed=False, trainingStarted=False)
    (output/'source-audit-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    (output/'source-audit-private.json').write_text(json.dumps(dict(summary=summary, images=receipts, duplicateGroups=duplicates, geometryIssues=issues), ensure_ascii=False, indent=2)+'\n')
    for label in sorted(seen_preview):
        items = [row for row in preview if row[0] == label]
        board = Image.new('RGB', (900, 660), 'white')
        for i, (_, tile, _) in enumerate(items):
            board.paste(tile, ((i % 3)*300, (i//3)*330))
        board.save(output/(label.replace(' ', '_')+'-train-review.jpg'), quality=90)
    (output/'review-images.json').write_text(json.dumps([dict(label=l, image=n) for l, _, n in preview], ensure_ascii=False, indent=2)+'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.archive, args.output), ensure_ascii=False, indent=2))
