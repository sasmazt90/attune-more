#!/usr/bin/env python3
"""Installs one exact, pushed commit on an Attune host. Run as root through SSM.

Source comes from the public GitHub archive of that commit, so the host runs what
the repository records rather than hand patches. Model weights, secrets, node_modules
and the build output are outside the archive and are never touched by the copy step.
Standard library plus curl, tar and rsync.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REPOSITORY = 'sasmazt90/attune-more'
ROOT = Path('/opt/attune')
EVIDENCE = Path('/var/lib/attune/evidence')
# The AWS frontend build flags; see scripts/aws/build_bundle.sh and docs/aws/README.md.
BUILD_ENV = {
    'NEXT_PUBLIC_ATTUNE_SAME_ORIGIN_API': '1',
    'NEXT_PUBLIC_ATTUNE_REMOTE_CAPTURE': '1',
    'NEXT_PUBLIC_ATTUNE_ACNE_V5': '1',
    'NEXT_PUBLIC_ATTUNE_SPEECH_PROVIDER': 'openai',
    'NEXT_PUBLIC_ATTUNE_MEDIAPIPE_DELEGATE': 'CPU',
    'NEXT_TELEMETRY_DISABLED': '1',
}
# Everything else on the AAOS host stays as prepared; it serves no application source.
AAOS_PATHS = ['infra/aws/aaos/', 'scripts/aws/', 'scripts/qa/realistic/']
WEB_RESTARTS = ['attune-api@web', 'attune-api@aaos', 'attune-web@web', 'attune-web@aaos', 'attune-capture']
SKIN_RUNTIME_PACKAGES = ['mediapipe==0.10.32', 'absl-py==2.5.1', 'sounddevice==0.5.6', 'cffi==2.1.1', 'pycparser==3.12']
# Keeps the speech model loaded and gives it 4 of 8 cores. Same model files and voice; no secrets here.
SPEECH_DROP_IN = Path('/etc/systemd/system/attune-api@.service.d/speech.conf')
SPEECH_ENVIRONMENT = '[Service]\nEnvironment=ATTUNE_MENTAL_TTS_RESIDENT=1\nEnvironment=ATTUNE_MENTAL_TTS_THREADS=4\n'
AAOS_RESTARTS = ['attune-audio']


def ensure_skin_runtime():
    """The Skin findings recipe needs Python MediaPipe (CODEX_HANDOFF.md). Without it, acne and redness
    use client landmarks and produce no redness measure. --no-deps is deliberate: its dependency list
    would install a second OpenCV and replace the cv2 every measurement uses."""
    python = '/opt/attune-venv/bin/python'
    before = run(python, '-c', 'import cv2;print(cv2.__version__)').strip()
    run('/opt/attune-venv/bin/pip', 'install', '--no-deps', '--no-cache-dir', *SKIN_RUNTIME_PACKAGES, timeout=300)
    after = run(python, '-c', 'import cv2,mediapipe;from mediapipe.tasks.python import vision;print(cv2.__version__)').strip()
    if before != after:
        raise RuntimeError('OpenCV changed from {} to {}'.format(before, after))


def run(*args, cwd=None, env=None, timeout=900):
    done = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError('{} failed: {}'.format(args[0], (done.stderr or done.stdout).strip()[-400:]))
    return done.stdout


def valid_commit(commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit or ''):
        raise ValueError('A full 40-character commit is required')
    return commit


def fetch(commit, workspace):
    archive = Path(workspace) / 'source.tar.gz'
    url = 'https://codeload.github.com/{}/tar.gz/{}'.format(REPOSITORY, commit)
    run('curl', '-fsSL', '--retry', '3', '--max-time', '300', '-o', str(archive), url)
    run('tar', '-xzf', str(archive), '-C', str(workspace))
    source = next(p for p in Path(workspace).iterdir() if p.is_dir())
    return source, hashlib.sha256(archive.read_bytes()).hexdigest()


def tree_copy(source, target):
    # The trailing slashes copy a folder's contents. Without them rsync nests it inside itself.
    return ['rsync', '-a', str(source).rstrip('/') + '/', str(target).rstrip('/') + '/']


def lock_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def deploy_web(commit):
    with tempfile.TemporaryDirectory(prefix='attune-release-', dir='/opt') as workspace:
        source, archive_sha = fetch(commit, workspace)
        dependencies_changed = lock_digest(source / 'package-lock.json') != lock_digest(ROOT / 'package-lock.json')
        requirements_changed = lock_digest(source / 'services/core-api/requirements.txt') != lock_digest(ROOT / 'services/core-api/requirements.txt')
        if requirements_changed:
            raise RuntimeError('Backend requirements changed; review the wheel set before deploying')
        run('rsync', '-a', '--exclude=node_modules/', '--exclude=apps/vehicle-app/.next/', '--exclude=.git/', str(source) + '/', str(ROOT) + '/')
    (ROOT / 'source-commit.txt').write_text(commit + '\n')
    env = {**os.environ, **BUILD_ENV, 'PATH': '/opt/node/bin:' + os.environ['PATH'], 'HOME': '/root'}
    if dependencies_changed:
        run('npm', 'ci', '--no-audit', '--no-fund', cwd=ROOT, env=env)
    log = run('npm', 'run', 'build', cwd=ROOT, env=env, timeout=1200)
    (EVIDENCE / 'web-release-build.log').write_text(log[-20000:])
    run('chown', '-R', 'root:attune', str(ROOT))
    run('chmod', '-R', 'g+rX,g-w', str(ROOT))
    cache = ROOT / 'apps/vehicle-app/.next/cache'
    cache.mkdir(parents=True, exist_ok=True)
    run('chown', '-R', 'attune:attune', str(cache))
    ensure_skin_runtime()
    SPEECH_DROP_IN.parent.mkdir(parents=True, exist_ok=True)
    SPEECH_DROP_IN.write_text(SPEECH_ENVIRONMENT)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'restart', *WEB_RESTARTS)
    return {'role': 'web', 'commit': commit, 'archiveSha256': archive_sha, 'buildId': (ROOT / 'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),
            'dependenciesReinstalled': dependencies_changed, 'buildFlags': {k: v for k, v in BUILD_ENV.items() if k.startswith('NEXT_PUBLIC')}}


def deploy_aaos(commit):
    with tempfile.TemporaryDirectory(prefix='attune-release-', dir='/opt') as workspace:
        source, archive_sha = fetch(commit, workspace)
        for path in AAOS_PATHS:
            (ROOT / path).mkdir(parents=True, exist_ok=True)
            run(*tree_copy(source / path, ROOT / path))
    (ROOT / 'source-commit.txt').write_text(commit + '\n')
    # Removes the nested copies an earlier version of this script left behind.
    for leftover in ('infra/aws/aaos/aaos', 'scripts/aws/aws'):
        shutil.rmtree(ROOT / leftover, ignore_errors=True)
    run('chown', '-R', 'root:attune', str(ROOT / 'infra'), str(ROOT / 'scripts'))
    run('chmod', '-R', 'g+rX,g-w', str(ROOT / 'infra'), str(ROOT / 'scripts'))
    run('systemctl', 'restart', *AAOS_RESTARTS)
    return {'role': 'aaos', 'commit': commit, 'archiveSha256': archive_sha, 'pathsUpdated': AAOS_PATHS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', choices=['web', 'aaos'], required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    commit = valid_commit(args.commit)
    if not shutil.which('rsync'):
        run('apt-get', 'install', '-y', 'rsync')
    report = deploy_web(commit) if args.role == 'web' else deploy_aaos(commit)
    report['deployedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    (EVIDENCE / 'release-provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    json.dump(report, sys.stdout)


if __name__ == '__main__':
    main()
