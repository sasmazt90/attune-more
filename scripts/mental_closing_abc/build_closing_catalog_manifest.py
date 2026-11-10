#!/usr/bin/env python3
"""Verify the synthesized catalog closing lines and publish them as app static assets with their own manifest.

Input: the WEB host's synthesis.json and WAV tree (synthesize_closing_catalog.py). Every WAV is re-read: SHA-256, size
and PCM format must match the synthesis record, and text, seed and catalog hash must match the committed catalog.
Files are copied with exclusive creation (never overwritten) to apps/vehicle-app/public/audio/mental/closing-catalog/v1.
Only languages with all 33 lines are published (the page never uses a subset); the manifest says which were left out.

Approval: entries are 'technical-preview-awaiting-owner-listening'. Only the owner's listening approval may change
that; this script never writes 'approved'.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'shared/mental/closing-catalog/v1/catalog.json'
PUBLIC = ROOT / 'apps/vehicle-app/public'
TARGET = PUBLIC / 'audio/mental/closing-catalog/v1'
FEMALE_MANIFEST = PUBLIC / 'audio/mental/v1/female-calm-v1-manifest.json'
ABC_MANIFEST = PUBLIC / 'audio/mental/closing-abc/v1/manifest.json'
PREVIEW = 'technical-preview-awaiting-owner-listening'


def seed_for(asset_id):
    return int(hashlib.sha256(asset_id.encode()).hexdigest()[:8], 16)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthesis', required=True, type=Path, help='Host output directory')
    args = parser.parse_args()
    record = json.loads((args.synthesis / 'synthesis.json').read_text('utf-8'))
    catalog_bytes = CATALOG.read_bytes()
    catalog = json.loads(catalog_bytes)
    female = json.loads(FEMALE_MANIFEST.read_text('utf-8'))
    abc = json.loads(ABC_MANIFEST.read_text('utf-8'))
    current = json.loads((TARGET / 'manifest.json').read_text('utf-8'))
    if record['catalogSha256'] != hashlib.sha256(catalog_bytes).hexdigest():
        raise SystemExit('CATALOG_CHANGED_SINCE_SYNTHESIS')
    if not all(record['integrityAfter'].values()) or not all(record['integrityBefore'].values()):
        raise SystemExit('INTEGRITY')
    if (record['referenceSha256'] != female['conditioningSha256'] or record['referenceSha256'] != abc['referenceSha256'] or record['generation'] != female['generation']
            or record['generation'] != abc['generation'] or record['speakerProfile'] != 'female-calm-v1'
            or record['sourceRevision'] != abc['model']['sourceRevision'] or record['modelRevision'] != abc['model']['revision']):
        raise SystemExit('PROFILE_MISMATCH_WITH_THE_CLOSING_VOICE')
    texts = {p['id']: p['text'] for p in catalog['patterns']}
    rows = {r['assetId']: r for r in record['rows']}
    entries, left_out = [], []
    for language in ('tr', 'en', 'de'):
        ids = [f'closing-catalog/v1/{language}/female-calm-v1/{pid}' for pid in texts]
        if not all(i in rows for i in ids):
            left_out.append(language)
            continue
        for pid in texts:
            asset = f'closing-catalog/v1/{language}/female-calm-v1/{pid}'
            made, text = rows[asset], texts[pid][language]
            file_name = f'{language.upper()}_{pid}.wav'
            raw = (args.synthesis / language / file_name).read_bytes()
            with wave.open(io.BytesIO(raw)) as w:
                fmt = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype())
            sha = hashlib.sha256(raw).hexdigest()
            if (sha != made['sha256'] or len(raw) != made['metrics']['bytes'] or fmt[:3] != (1, 2, 24000)
                    or fmt[3] != made['metrics']['frames'] or fmt[4] != 'NONE' or made['seed'] != seed_for(asset)
                    or made['textSha256'] != hashlib.sha256(text.encode()).hexdigest()):
                raise SystemExit('ASSET_VERIFICATION_FAILED ' + asset)
            path = f'/audio/mental/closing-catalog/v1/{language}/female-calm-v1/{file_name}'
            target = PUBLIC / path.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                    raise SystemExit('EXISTING_ASSET_DIFFERS_NO_OVERWRITE ' + path)
            else:
                with target.open('xb') as stream:
                    stream.write(raw)
            m = made['metrics']
            entries.append({
                'assetId': asset, 'language': language, 'patternId': pid, 'exactText': text,
                'textSha256': made['textSha256'], 'condition': next(p['condition'] for p in catalog['patterns'] if p['id'] == pid),
                'fileName': file_name, 'audioPath': path, 'speakerProfile': 'female-calm-v1',
                'referenceSha256': record['referenceSha256'], 'generation': record['generation'], 'seed': made['seed'],
                'workerMode': record['workerMode'], 'codec': 'pcm_s16le', 'sampleRate': fmt[2], 'channels': fmt[0],
                'sampleWidthBytes': fmt[1], 'frames': fmt[3], 'durationMs': m['durationMs'],
                'durationSeconds': round(fmt[3] / fmt[2], 6), 'bytes': len(raw), 'sha256': sha,
                'createdAtUtc': made['createdAtUtc'], 'synthesisSeconds': made['synthesisSeconds'],
                'qualityMetrics': {k: m[k] for k in ('peak', 'rms', 'clippedSamples', 'leadingSilenceMs', 'trailingSilenceMs')},
                'technicalFindings': made['technicalFindings'],
                'approvalStatus': PREVIEW, 'ownerApprovedAt': None,
            })
    manifest = {**current,
                'runtime': record['runtime'], 'synthesisRecordSha256': hashlib.sha256((args.synthesis / 'synthesis.json').read_bytes()).hexdigest(),
                'languagesLeftOut': left_out,
                'approval': {'status': PREVIEW if entries else 'not-generated', 'ownerApprovedAt': None,
                             'note': 'Technically verified only (hashes, format, one take per line). Nobody has listened to '
                                     'these recordings yet; the owner must listen before production use.'},
                'entries': entries}
    (TARGET / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    print(json.dumps({'entries': len(entries), 'languagesLeftOut': left_out}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
