#!/usr/bin/env python3
"""Package committed source and the completed WEB build, excluding secrets/caches."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]


def package(output):
    output = output.resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / '.aws-oem'):
        raise ValueError('OUTPUT_MUST_BE_OUTSIDE_SOURCE_OR_IN_IGNORED_STAGING')
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT).strip():
        raise ValueError('COMMIT_SOURCE_BEFORE_PACKAGING')
    build = ROOT / 'apps/vehicle-app/.next'
    if not (build / 'BUILD_ID').is_file():
        raise ValueError('PRODUCTION_BUILD_REQUIRED')
    output.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    (output / 'source-commit.txt').write_text(commit + '\n')
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    archive = output / 'attune-application.tar.gz'
    def include(info):
        relative = Path(info.name)
        if any(p in ('__pycache__', '.cache') for p in relative.parts):
            return None
        if str(relative).startswith('attune/apps/vehicle-app/.next/cache'):
            return None
        return info
    with tarfile.open(archive, 'w:gz', compresslevel=3) as tar:
        for name in names:
            if name:
                tar.add(ROOT / name, arcname='attune/' + name, recursive=False)
        tar.add(output / 'source-commit.txt', arcname='attune/source-commit.txt')
        for name in ('node_modules', 'apps/vehicle-app/.next'):
            tar.add(ROOT / name, arcname='attune/' + name, filter=include)
    with archive.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    receipt = {'sourceCommit': commit, 'packagedAt': time.time(), 'archive': archive.name,
               'bytes': archive.stat().st_size, 'sha256': sha,
               'buildId': (build / 'BUILD_ID').read_text().strip(),
               'modelAssets': 'separate verified model bundle',
               'secretsIncluded': False, 'liveAcceptance': 'NOT_RUN'}
    (output / 'application-bundle.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(package(parser.parse_args().output), indent=2))
