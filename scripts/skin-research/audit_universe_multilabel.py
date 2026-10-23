"""Audit a folder-format multi-label export without treating label combinations as classes.

Usage: python scripts/skin-research/audit_universe_multilabel.py ARCHIVE OUTPUT --compare-coco-audit PRIVATE_JSON
Writes per-image receipts privately to OUTPUT, and aggregate counts separately.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile
from PIL import Image

LABELS = ('Acne', 'Blackheads', 'Dark Spots', 'Dry Skin', 'Eye bags', 'Normal Skin', 'Oily Skin', 'Pores', 'Skin Redness', 'Wrinkles')


def audit(archive, output, compare=None):
    previous = json.loads(compare.read_text())['images'] if compare else []
    previous_hashes = {r['decodedSHA256'] for r in previous}
    rows, counts, groups = [], defaultdict(Counter), defaultdict(list)
    with zipfile.ZipFile(archive) as source:
        for name in sorted(source.namelist()):
            path = PurePosixPath(name)
            if path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
                continue
            if len(path.parts) != 3 or path.parts[0] not in ('train', 'valid', 'test'):
                raise ValueError('Unexpected image hierarchy: ' + name)
            split, folder = path.parts[:2]
            # Remove the longest known labels first; unknown folder text fails closed.
            remainder, labels = folder, []
            for label in sorted(LABELS, key=len, reverse=True):
                if label in remainder:
                    labels.append(label)
                    remainder = remainder.replace(label, '', 1)
            if remainder.strip() or not labels:
                raise ValueError('Unknown multi-label folder: ' + folder)
            raw = source.read(name)
            image = Image.open(io.BytesIO(raw)).convert('RGB')
            w, h = image.size
            digest = hashlib.sha256(f'{w}x{h}:'.encode() + image.tobytes()).hexdigest()
            row = dict(path=name, split=split, labels=sorted(labels), decodedSHA256=digest,
                       sha256=hashlib.sha256(raw).hexdigest(), dimensions=[w, h])
            rows.append(row); groups[digest].append(row)
            for label in labels:
                counts[label][split] += 1
    duplicates = [r for r in groups.values() if len(r) > 1]
    summary = dict(source='parin-kittipongdaja-vwmn3/skin-problem-multilabel/1',
                   archiveSHA256=hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest(),
                   images=len(rows), uniqueDecodedImages=len(groups), exactDuplicateGroups=len(duplicates),
                   crossSplitExactGroups=sum(len({v['split'] for v in r}) > 1 for r in duplicates),
                   exactCrossSourceMatches=len(set(groups) & previous_hashes), classes=dict(sorted(counts.items())),
                   task='whole-image multilabel classification; no box/pixel coordinates',
                   publisherReportedAccuracy=.971, personIndependent=False)
    output.mkdir(parents=True, exist_ok=True)
    (output/'multilabel-audit-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (output/'multilabel-audit-private.json').write_text(json.dumps(dict(summary=summary, images=rows), indent=2)+'\n')
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('archive', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--compare-coco-audit', type=Path)
    args = p.parse_args()
    print(json.dumps(audit(args.archive, args.output, args.compare_coco_audit), indent=2))
