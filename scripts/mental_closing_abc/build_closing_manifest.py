#!/usr/bin/env python3
"""Verify synthesized closing A/B/C clips and publish them as app static assets with a manifest.

Input: the host's synthesis.json and WAV tree. Every WAV is re-read: SHA-256, size and PCM
format must match the synthesis record, and text/seed must match the catalog. Files are
copied with exclusive creation (never overwritten) to the app's public audio tree, which
the app serves itself; Drive is only the review archive.

Approval: entries are marked 'technical-preview-awaiting-owner-listening'. Only the owner's
listening approval may change that; this script never writes 'approved'.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'shared/mental/closing-abc/v1/catalog.json'
PUBLIC = ROOT / 'apps/vehicle-app/public'
TARGET = PUBLIC / 'audio/mental/closing-abc/v1'
FEMALE_MANIFEST = PUBLIC / 'audio/mental/v1/female-calm-v1-manifest.json'
PREVIEW = 'technical-preview-awaiting-owner-listening'
JOIN_SILENCE_MS = 120  # Same calibrated join pause as the approved prepared-recording joins.


def seed_for(asset_id):
    return int(hashlib.sha256(asset_id.encode()).hexdigest()[:8], 16)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthesis', required=True, type=Path, help='Host output directory (assets/)')
    args = parser.parse_args()
    record = json.loads((args.synthesis / 'synthesis.json').read_text('utf-8'))
    catalog = json.loads(CATALOG.read_text('utf-8'))
    female = json.loads(FEMALE_MANIFEST.read_text('utf-8'))
    if not record.get('complete') or not all(record['integrityAfter'].values()) or not all(record['integrityBefore'].values()):
        raise SystemExit('SYNTHESIS_INCOMPLETE_OR_INTEGRITY')
    if (record['referenceSha256'] != female['conditioningSha256'] or record['generation'] != female['generation']
            or record['speakerProfile'] != female['speakerProfile']):
        raise SystemExit('PROFILE_MISMATCH_WITH_APPROVED_FEMALE_MANIFEST')
    rows = {r['assetId']: r for r in record['rows']}
    if set(rows) != {r['assetId'] for r in catalog['rows']}:
        raise SystemExit('ASSET_SET_MISMATCH')
    entries = []
    for item in catalog['rows']:
        made = rows[item['assetId']]
        raw = (args.synthesis / item['language'] / item['group'] / item['fileName']).read_bytes()
        with wave.open(io.BytesIO(raw)) as w:
            fmt = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype())
        sha = hashlib.sha256(raw).hexdigest()
        if (sha != made['sha256'] or len(raw) != made['metrics']['bytes'] or fmt[:2] != (1, 2) or fmt[2] != 24000
                or fmt[3] != made['metrics']['frames'] or fmt[4] != 'NONE'
                or made['seed'] != seed_for(item['assetId'])
                or made['textSha256'] != hashlib.sha256(item['exactText'].encode()).hexdigest()):
            raise SystemExit('ASSET_VERIFICATION_FAILED ' + item['assetId'])
        path = f"/audio/mental/closing-abc/v1/{item['language']}/female-calm-v1/{item['group']}/{item['fileName']}"
        target = PUBLIC / path.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                raise SystemExit('EXISTING_ASSET_DIFFERS_NO_OVERWRITE ' + path)
        else:
            with target.open('xb') as stream:
                stream.write(raw)
        metrics = made['metrics']
        entries.append({
            'assetId': item['assetId'], 'language': item['language'], 'group': item['group'],
            'groupPurpose': item['groupPurpose'], 'variantId': item['variantId'], 'exactText': item['exactText'],
            'textSha256': item['textSha256'], 'fileName': item['fileName'], 'audioPath': path,
            'speakerProfile': 'female-calm-v1', 'model': {
                'repository': 'ResembleAI/chatterbox', 'revision': record['modelRevision'],
                'file': 't3_mtl23ls_v3.safetensors', 'package': 'chatterbox-tts', 'packageVersion': record['packageVersion'],
                'sourceRevision': record['sourceRevision']},
            'referenceSha256': record['referenceSha256'], 'generation': record['generation'], 'seed': made['seed'],
            'workerMode': record['workerMode'], 'codec': 'pcm_s16le', 'sampleRate': fmt[2], 'channels': fmt[0],
            'sampleWidthBytes': fmt[1], 'frames': fmt[3], 'durationMs': metrics['durationMs'],
            'durationSeconds': round(fmt[3] / fmt[2], 6), 'bytes': len(raw), 'sha256': sha,
            'createdAtUtc': made['createdAtUtc'],
            'qualityMetrics': {k: metrics[k] for k in ('peak', 'rms', 'clippedSamples', 'leadingSilenceMs', 'trailingSilenceMs')},
            'synthesisSeconds': made['synthesisSeconds'],
            'approvalStatus': PREVIEW, 'ownerApprovedAt': None,
        })
    manifest = {
        'schema': 'attune-mental-closing-abc-manifest-v1', 'contentVersion': 'v1', 'speakerProfile': 'female-calm-v1',
        'referenceSha256': record['referenceSha256'], 'generation': record['generation'],
        'model': entries[0]['model'], 'runtime': record['runtime'], 'seedRule': record['seedRule'],
        'postProcessing': record['postProcessing'], 'playbackOrder': ['A', 'B', 'C'], 'variantsPerGroup': 5,
        'joinSilenceMs': JOIN_SILENCE_MS,
        'approval': {'status': PREVIEW, 'ownerApprovedAt': None,
                     'note': 'Technically verified only. The reference profile approval does not cover these 45 new '
                             'recordings or their joins; the owner must listen before production use.'},
        'entries': entries,
    }
    out = TARGET / 'manifest.json'
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps({'entries': len(entries), 'manifest': str(out.relative_to(ROOT))}))


if __name__ == '__main__':
    sys.exit(main())
