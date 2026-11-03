#!/usr/bin/env python3
"""Install the recovered, pinned TTS runtime offline; never synthesize or start a service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'tests/automotive/neural-runtime'


def install(runtime, wheels):
    if sys.version_info[:2] != (3, 11):
        raise ValueError('PYTHON_311_REQUIRED')
    runtime = runtime.resolve(strict=True)
    wheels = wheels.resolve(strict=True)
    assets = json.loads((POLICY / 'assets.json').read_text())
    for entry in assets['files']:
        p = runtime / 'bundle' / entry['path']
        with p.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if p.stat().st_size != entry['bytes'] or digest != entry['sha256']:
            raise ValueError('BUNDLE_INTEGRITY_MISMATCH')
    subprocess.run([sys.executable, '-m', 'venv', str(runtime / 'venv')], check=True)
    python = str(runtime / 'venv/bin/python')
    # uv-build resolves its executable through PATH during the offline Perth build.
    env = dict(os.environ, PATH=str(runtime / 'venv/bin') + os.pathsep + os.environ.get('PATH', ''))
    pip = [python, '-m', 'pip', 'install', '--no-index', '--no-cache-dir']
    subprocess.run(pip + ['--find-links', str(wheels), '--no-deps', '--require-hashes',
                         '-r', str(POLICY / 'cpu-requirements.txt'),
                         '-r', str(POLICY / 'requirements.txt'),
                         '-r', str(ROOT / 'infra/aws/tts-support-requirements.txt')], check=True)
    source = runtime / 'bundle/provenance'
    perth = source / 'dependency-source/Perth'
    for entry in json.loads((POLICY / 'packaging-provenance.json').read_text()):
        p = POLICY / entry['file']
        if hashlib.sha256(p.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('PACKAGING_INTEGRITY_MISMATCH')
        shutil.copyfile(p, perth / entry['file'].removeprefix('perth-'))
    for package in (perth, source / 'official-source'):
        subprocess.run(pip + ['--no-deps', '--no-build-isolation', str(package)], check=True, env=env)
    subprocess.run([python, '-m', 'pip', 'check'], check=True)
    target = runtime / 'venv/lib/python3.11/site-packages/perth/perth_net/pretrained/implicit'
    target.mkdir(parents=True, exist_ok=True)
    for p in (runtime / 'bundle/dependency-assets/Perth/src/perth/perth_net/pretrained/implicit').iterdir():
        shutil.copyfile(p, target / p.name)
    cache = runtime / 'pkuseg-cache'
    cache.mkdir(exist_ok=True)
    shutil.copyfile(runtime / 'bundle/dependency-assets/pkuseg/spacy_ontonotes.zip', cache / 'spacy_ontonotes.zip')
    with zipfile.ZipFile(cache / 'spacy_ontonotes.zip') as archive:
        for name in ('features.msgpack', 'weights.npz'):
            target = cache / 'spacy_ontonotes' / name
            target.parent.mkdir(exist_ok=True)
            with archive.open(name) as source, target.open('wb') as sink:
                shutil.copyfileobj(source, sink)
    # Recovered config files are preserved byte-for-byte, including generation settings.
    subprocess.run([python, str(ROOT / 'scripts/mental_tts/preflight.py'),
                    '--config', str(runtime / 'config.json'),
                    '--output', str(runtime / 'preflight.json')], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--wheelhouse', type=Path, required=True)
    args = parser.parse_args()
    install(args.runtime, args.wheelhouse)
