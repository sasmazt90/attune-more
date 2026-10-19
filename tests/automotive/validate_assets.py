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


def main():
    out = Path(os.environ['ATTUNE_AAOS_EVIDENCE'])
    out.mkdir(parents=True, exist_ok=True)
    report = inspect_guidance(ROOT / 'apps/vehicle-app/public')
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
