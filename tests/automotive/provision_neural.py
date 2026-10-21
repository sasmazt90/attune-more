"""Private Drive import into a disposable runner, never an artifact/cache upload.

No inference here. The immutable owner ZIP is the same bundle verified in Cloud.
Only a Drive service account explicitly granted reader access can download it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = Path(__file__).with_name('neural-runtime')
POLICY = json.loads((POLICY_DIR / 'assets.json').read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    if not name or '\\' in name or p.is_absolute() or '..' in p.parts or ':' in name:
        raise ValueError('UNSAFE_ARCHIVE_PATH')
    return p


def extract_verified(archive, destination, policy=POLICY):
    if archive.stat().st_size != policy['zip_bytes'] or sha(archive) != policy['zip_sha256']:
        raise ValueError('OWNER_ZIP_INTEGRITY_MISMATCH')
    expected = {row['path']: row for row in policy['files']}
    with zipfile.ZipFile(archive) as z:
        files = z.infolist()
        names = [i.filename for i in files]
        if len(names) != len(set(names)) or set(names) != set(expected) | {'manifest.json'}:
            raise ValueError('OWNER_ZIP_FILE_SET_MISMATCH')
        for item in files:
            safe_name(item.filename)
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode) or item.is_dir() or item.file_size > 3 * 1024**3:
                raise ValueError('UNSAFE_ARCHIVE_MEMBER')
            if item.filename in expected and item.file_size != expected[item.filename]['bytes']:
                raise ValueError('OWNER_MEMBER_SIZE_MISMATCH')
            if item.filename == 'manifest.json' and item.file_size > 128 * 1024:
                raise ValueError('MANIFEST_TOO_LARGE')
        for item in files:
            target = destination / item.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(item) as source, target.open('xb') as sink:
                shutil.copyfileobj(source, sink, 1024 * 1024)
            if item.filename in expected and sha(target) != expected[item.filename]['sha256']:
                raise ValueError('OWNER_MEMBER_HASH_MISMATCH')
    return len(expected)


def credentials(raw, file_id):
    if not raw or not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', file_id or ''):
        raise ValueError('PRIVATE_DRIVE_CONFIGURATION_MISSING')
    value = json.loads(raw)
    # Fixed Google token endpoint, never a credential-selected destination.
    if value.get('type') != 'service_account' or value.get('token_uri') != 'https://oauth2.googleapis.com/token':
        raise ValueError('PRIVATE_DRIVE_CREDENTIAL_TYPE_INVALID')
    if not value.get('private_key') or not value.get('client_email', '').endswith('.iam.gserviceaccount.com'):
        raise ValueError('PRIVATE_DRIVE_CREDENTIAL_FIELDS_MISSING')
    return value


def download(destination, info, file_id, deadline):
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession
    session = AuthorizedSession(Credentials.from_service_account_info(
        info, scopes=['https://www.googleapis.com/auth/drive.readonly']), max_refresh_attempts=0)
    url = 'https://www.googleapis.com/drive/v3/files/' + file_id
    try:
        metadata = session.get(url, params={'fields': 'name,size,trashed,capabilities(canDownload)'}, timeout=30)
        metadata.raise_for_status()
        m = metadata.json()
        if (m.get('name') != POLICY['zip_name'] or int(m.get('size', 0)) != POLICY['zip_bytes']
                or m.get('trashed') or not m.get('capabilities', {}).get('canDownload')):
            raise ValueError('PRIVATE_DRIVE_FILE_NOT_APPROVED')
        # No public-link fallback, retries, redirects to unapproved destinations,
        # cookies from an owner's browser, or Drive permission changes.
        with session.get(url, params={'alt': 'media'}, stream=True, timeout=(15, 30), allow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError('PRIVATE_DRIVE_DOWNLOAD_BLOCKED')
            size = 0
            with destination.open('xb') as stream:
                for chunk in response.iter_content(1024 * 1024):
                    if time.monotonic() >= deadline:
                        raise TimeoutError('PRIVATE_IMPORT_TIME_BUDGET_EXCEEDED')
                    size += len(chunk)
                    if size > POLICY['zip_bytes']:
                        raise ValueError('PRIVATE_DRIVE_DOWNLOAD_OVERSIZE')
                    stream.write(chunk)
    finally:
        session.close()


def install(runtime, deadline):
    def run(args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('PRIVATE_IMPORT_TIME_BUDGET_EXCEEDED')
        # No inherited Drive key or backend secret in pip/build subprocesses.
        env = {k: v for k, v in os.environ.items() if k not in ('ATTUNE_AAOS_DRIVE_SERVICE_ACCOUNT_JSON', 'ATTUNE_MENTAL_TTS_TOKEN')}
        env['PATH'] = str(runtime / 'venv/bin') + os.pathsep + env.get('PATH', '')
        subprocess.run(args, check=True, timeout=remaining, env=env)
    run([sys.executable, '-m', 'venv', str(runtime / 'venv')])
    python = str(runtime / 'venv/bin/python')
    run([python, '-m', 'pip', 'install', '--no-cache-dir', '--only-binary=:all:', '--no-deps', '--require-hashes', '--retries', '0',
         '--index-url', 'https://download.pytorch.org/whl/cpu', '-r', str(POLICY_DIR / 'cpu-requirements.txt')])
    run([python, '-m', 'pip', 'install', '--no-cache-dir', '--only-binary=:all:', '--no-deps', '--require-hashes', '--retries', '0',
         '-r', str(POLICY_DIR / 'requirements.txt')])
    source = runtime / 'bundle/provenance'
    perth = source / 'dependency-source/Perth'
    for name in ('pyproject.toml', 'README.md'):
        shutil.copyfile(POLICY_DIR / ('perth-' + name), perth / name)
    for package in (perth, source / 'official-source'):
        run([python, '-m', 'pip', 'install', '--no-cache-dir', '--no-index', '--no-deps', '--no-build-isolation', str(package)])
    run([python, '-m', 'pip', 'check'])
    # Preserve watermark and segmenter assets; no network-loading fallback.
    target = runtime / 'venv/lib/python3.11/site-packages/perth/perth_net/pretrained/implicit'
    target.mkdir(parents=True, exist_ok=True)
    for asset in (runtime / 'bundle/dependency-assets/Perth/src/perth/perth_net/pretrained/implicit').iterdir():
        shutil.copyfile(asset, target / asset.name)
    cache = runtime / 'pkuseg-cache'
    cache.mkdir()
    shutil.copyfile(runtime / 'bundle/dependency-assets/pkuseg/spacy_ontonotes.zip', cache / 'spacy_ontonotes.zip')
    with zipfile.ZipFile(cache / 'spacy_ontonotes.zip') as archive:
        for name in ('features.msgpack', 'weights.npz'):
            target = cache / 'spacy_ontonotes' / name
            target.parent.mkdir(exist_ok=True)
            with archive.open(name) as source, target.open('xb') as sink:
                shutil.copyfileobj(source, sink)
    shutil.copyfile(POLICY_DIR / 'config.json', runtime / 'config.json')
    shutil.copyfile(POLICY_DIR / 'official-model-metadata.txt', runtime / 'official-model-metadata.txt')
    return python


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials-only', action='store_true')
    args = parser.parse_args()
    info = credentials(os.environ.get('ATTUNE_AAOS_DRIVE_SERVICE_ACCOUNT_JSON'), os.environ.get('ATTUNE_AAOS_TTS_BUNDLE_FILE_ID'))
    if args.credentials_only:
        print('PASS: credential shape and private file selector present; download authorization remains unverified')
        return
    if not os.environ.get('RUNNER_TEMP') or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise ValueError('DISPOSABLE_STANDARD_RUNNER_REQUIRED')
    runtime = Path(os.environ['RUNNER_TEMP']) / 'attune-neural-private'
    # Refuse reuse and insufficient space before transferring 3.28 GB.
    if shutil.disk_usage(runtime.parent).free < 20 * 1024**3:
        raise ValueError('NEURAL_IMPORT_REQUIRES_20_GIB_FREE')
    runtime.mkdir(mode=0o700)
    started = time.monotonic()
    deadline = started + 480
    archive = runtime / 'owner-bundle.zip'
    download(archive, info, os.environ['ATTUNE_AAOS_TTS_BUNDLE_FILE_ID'], deadline)
    extract_verified(archive, runtime / 'bundle')
    archive.unlink()  # Only this disposable download; Cloud/Drive originals untouched.
    python = install(runtime, deadline)
    token = secrets.token_urlsafe(48)
    print('::add-mask::' + token)
    values = {'ATTUNE_MENTAL_TTS_CONFIG': str(runtime / 'config.json'), 'ATTUNE_MENTAL_TTS_PYTHON': python,
              'ATTUNE_MENTAL_TTS_TOKEN': token, 'PKUSEG_HOME': str(runtime / 'pkuseg-cache'),
              'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    with open(os.environ['GITHUB_ENV'], 'a') as env:
        for key, value in values.items():
            env.write(key + '=' + value + '\n')
    out = Path(os.environ['ATTUNE_AAOS_EVIDENCE'])
    (out / 'neural-provision.json').write_text(json.dumps({
        'status': 'PASS', 'zipBytes': POLICY['zip_bytes'], 'zipSHA256': POLICY['zip_sha256'],
        'membersVerified': len(POLICY['files']), 'pipCheck': 'PASS',
        'seconds': round(time.monotonic() - started, 3), 'inference': 'NOT_EXECUTED',
        'delivery': 'authenticated Google Drive read-only service account',
    }, indent=2) + '\n')
    print('PASS: 117 private assets verified; pinned isolated runtime installed; no inference claimed')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Transport/library messages can contain private URLs or credential data.
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[A-Z0-9_]+', str(error)) else type(error).__name__
        if os.environ.get('ATTUNE_AAOS_EVIDENCE'):
            out = Path(os.environ['ATTUNE_AAOS_EVIDENCE'])
            out.mkdir(parents=True, exist_ok=True)
            (out / 'neural-provision.json').write_text(json.dumps({'status': 'BLOCKED', 'reason': reason, 'inference': 'NOT_EXECUTED'}) + '\n')
        print('BLOCKED: private neural provisioning (' + reason + '); no emulator launch', file=sys.stderr)
        sys.exit(69)
