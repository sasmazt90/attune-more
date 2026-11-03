#!/usr/bin/env python3
"""Restore the reviewed Windows ONNX backup; no download or inference changes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


def fingerprint(path):
    with path.open('rb') as stream:
        return path.stat().st_size, hashlib.file_digest(stream, 'sha256').hexdigest()


def restore(parts, output, manifest):
    entries = [dict(entry, bytes=entry['fileSizeBytes']) for entry in manifest['parts']]
    names = [f'skin-type-local-v1-model.onnx.part-{i:03d}' for i in range(4)]
    step = 'step0-with-features-stable-silu.onnx'
    by_name = {entry['name']: entry for entry in entries}
    if len(entries) != 5 or set(by_name) != set(names + [step]):
        raise ValueError('EXACT_FOUR_PARTS_AND_STEP0_REQUIRED')
    # Validate every input before creating any output. Manifest order is irrelevant.
    for name in names + [step]:
        path = parts / name
        entry = by_name[name]
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'MISSING_OR_LINK: {name}')
        if fingerprint(path) != (entry['bytes'], entry['sha256']):
            raise ValueError(f'INPUT_HASH_OR_SIZE_MISMATCH: {name}')
    combined = manifest['combinedSkinType']
    outputs = [(combined['destination'], combined),
               (manifest['step0Destination'], by_name[step])]
    root = output.resolve()
    for relative, expected in outputs:
        target = root / relative
        if not target.resolve().is_relative_to(root) or target.is_symlink():
            raise ValueError('OUTPUT_ESCAPES_ROOT')
        if target.exists() and fingerprint(target) != (expected['bytes'], expected['sha256']):
            raise ValueError('REFUSE_TO_OVERWRITE_DIFFERENT_ASSET')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.onnx-restore-', dir=output) as tmp:
        tmp = Path(tmp)
        with (tmp / 'combined').open('wb') as dest:
            for name in names:
                with (parts / name).open('rb') as source:
                    shutil.copyfileobj(source, dest)
        if fingerprint(tmp / 'combined') != (combined['bytes'], combined['sha256']):
            raise ValueError('COMBINED_HASH_OR_SIZE_MISMATCH')
        shutil.copyfile(parts / step, tmp / 'step0')
        for (relative, expected), source in zip(outputs, [tmp / 'combined', tmp / 'step0']):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                source.replace(target)
    return {'assets': [{'path': path, 'bytes': item['bytes'], 'sha256': item['sha256'],
                        'status': 'VERIFIED'} for path, item in outputs],
            'partOrder': names, 'inference': 'NOT_RUN'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parts', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    result = restore(args.parts, args.output_root, json.loads(args.manifest.read_text()))
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + '\n')
