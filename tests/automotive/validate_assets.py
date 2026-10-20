"""Read-only source packaging gate; never generates/substitutes approved audio."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def inspect_guidance(public):
    public = public.resolve()
    manifest = json.loads((public / 'audio/guidance/manifest.json').read_text())
    rows, errors = [], []
    for name, entry in manifest['entries'].items():
        url, expected = entry['url'], entry['sha256']
        path = (public / url.lstrip('/')).resolve()
        reason, actual = None, None
        if not url.startswith('/audio/guidance/') or not path.is_relative_to(public / 'audio/guidance'):
            reason = 'URL escapes the approved guidance directory'
        elif not path.is_file():
            reason = 'Approved recording absent from source package'
        else:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                reason = 'Recording differs from the approved manifest hash'
        rows.append({'id': name, 'url': url, 'expected_sha256': expected,
                     'actual_sha256': actual, 'status': 'BLOCKED' if reason else 'PASS'})
        if reason:
            errors.append(f'{name}: {reason}; URL={url}; required SHA-256={expected}')
    return {'scope': 'source packaging only; no auditory or Android acceptance',
            'errors': errors, 'assets': rows}


def inspect_localized(public):
    """Check every original byte before downloading any emulator dependency."""
    public = public.resolve()
    folder = public / 'audio/user-approved/tr-en-de-20261020-v1'
    manifest = json.loads((folder / 'manifest.json').read_text())
    rows, errors = [], []
    recordings = manifest['recordings']
    if len(recordings) != 194 or len({r['recordingId'] for r in recordings}) != 194:
        errors.append('Expected exactly 194 distinct approved recording IDs')
    if manifest.get('approvalStatus') != 'USER_APPROVED_FOR_INTEGRATION':
        errors.append('Original recording integration approval missing')
    for entry in recordings:
        url, expected = entry['url'], entry['sha256']
        path = (public / url.lstrip('/')).resolve()
        reason, actual, size = None, None, None
        if not url.startswith('/audio/user-approved/tr-en-de-20261020-v1/') or not path.is_relative_to(folder):
            reason = 'URL escapes the approved original directory'
        elif not path.is_file():
            reason = 'Approved original absent from source package'
        else:
            size = path.stat().st_size
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if size != entry['bytes'] or actual != expected:
                reason = 'Original differs from approved byte count or SHA-256'
        rows.append({'id': entry['recordingId'], 'url': url, 'expected_sha256': expected,
                     'actual_sha256': actual, 'bytes': size, 'status': 'BLOCKED' if reason else 'PASS'})
        if reason:
            errors.append(f"{entry['recordingId']}: {reason}; required SHA-256={expected}")
    return {'scope': 'all 194 original files; source integrity only, not Android playback',
            'errors': errors, 'assets': rows}


def main():
    out = Path(os.environ['ATTUNE_AAOS_EVIDENCE'])
    out.mkdir(parents=True, exist_ok=True)
    report = inspect_guidance(ROOT / 'apps/vehicle-app/public')
    localized = inspect_localized(ROOT / 'apps/vehicle-app/public')
    report['assets'] += localized['assets']
    report['errors'] += localized['errors']
    (out / 'asset-preflight.json').write_text(json.dumps(report, indent=2))
    for error in report['errors']:
        print('BLOCKED: ' + error)
    if report['errors']:
        print('Restore the exact approved asset; do not substitute audio, alter its hash, or suppress the 404.')
        return 69
    print(f"PASS: {len(report['assets'])} approved guidance recordings present with matching hashes")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
