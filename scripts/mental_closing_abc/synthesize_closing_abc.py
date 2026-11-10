#!/usr/bin/env python3
"""Synthesize the 45 closing A/B/C clips once, with the approved female-calm-v1 profile.

Runs on the speech host with its existing pinned runtime (Chatterbox 0.1.7, source
5de7a54...), model bundle and approved reference audio. Nothing here changes the
model, the reference, the generation settings or the watermark: every clip goes
through the same ``mental_neural_worker.synthesize`` function the product uses.

* One model load (resident mode), one deterministic seed per asset id.
* Exclusive file creation: an existing file is never overwritten.
* Integrity of the six model files and the reference is checked before and after.
* No network, provider, user text or credentials are involved.

The output is a technical preview. Owner listening approval is a separate step.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import sys
import time
import wave
from array import array

EXPECTED_REFERENCE_SHA256 = '4d2bd83ff0f7fe33491b03193abdf623f1b4cc2d8103972b33638d3607d86dc5'
EXPECTED_GENERATION = {'exaggeration': 0.35, 'cfg_weight': 0.0, 'temperature': 0.8}
EXPECTED_SOURCE_REVISION = '5de7a54aa4e5e2baadb0182dde554908b48b85c2'
EXPECTED_MODEL_REVISION = '5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18'
EXPECTED_PACKAGE_VERSION = '0.1.7'


def seed_for(asset_id):
    """Same rule as scripts/mental_audio_batch.py: first 32 bits of SHA-256(asset id)."""
    return int(hashlib.sha256(asset_id.encode()).hexdigest()[:8], 16)


def pcm_metrics(raw):
    """Same definitions as scripts/validate_mental_audio.py (20 ms windows, RMS > 196)."""
    with wave.open(io.BytesIO(raw), 'rb') as w:
        fmt = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype())
        count = w.getnframes()
        frames = w.readframes(count)
    if fmt != (1, 2, 24000, 'NONE') or len(frames) != count * 2 or not count:
        raise ValueError('INVALID_PCM')
    samples = array('h', frames)
    if sys.byteorder != 'little':
        samples.byteswap()
    window = 480
    active = [sum(s * s for s in samples[i:i + window]) / len(samples[i:i + window]) > 196 ** 2
              for i in range(0, len(samples), window)]
    voiced = [i for i, a in enumerate(active) if a]
    return {
        'channels': fmt[0], 'sampleWidthBytes': fmt[1], 'sampleRate': fmt[2], 'frames': count,
        'durationMs': round(count / 24), 'durationSeconds': count / 24000, 'bytes': len(raw),
        'peak': max(abs(s) for s in samples) / 32768,
        'rms': (sum(s * s for s in samples) / len(samples)) ** .5 / 32768,
        'clippedSamples': sum(abs(s) >= 32760 for s in samples),
        'leadingSilenceMs': voiced[0] * 20 if voiced else round(count / 24),
        'trailingSilenceMs': max(0, len(active) - 1 - voiced[-1]) * 20 if voiced else round(count / 24),
    }


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def integrity(config_path):
    """Hash the model files and reference named by the verified configuration."""
    config = json.loads(Path(config_path).read_text('utf-8'))
    root = Path(config_path).resolve().parent
    items = {**config['model']['files'], 'reference': config['referenceAudio']}
    return {name: file_sha256(root / item['path']) == item['sha256'] for name, item in items.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Directory holding services/core-api and shared/')
    parser.add_argument('--config', required=True, help='Existing female-calm-v1 runtime configuration')
    parser.add_argument('--catalog', required=True)
    parser.add_argument('--out', required=True, help='New directory; must not exist')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(Path(args.source) / 'services/core-api'))
    from importlib.metadata import version
    from mental_neural_tts import load_configuration, verify_runtime_source, worker_progress, SOURCE_REVISION
    from mental_neural_worker import synthesize

    catalog = json.loads(Path(args.catalog).read_text('utf-8'))
    rows = catalog['rows']
    if len(rows) != 45 or catalog['speakerProfile'] != 'female-calm-v1':
        raise SystemExit('CATALOG_SHAPE')
    for language in ('tr', 'en', 'de'):
        for group in 'ABC':
            if sum(r['language'] == language and r['group'] == group for r in rows) != 5:
                raise SystemExit('CATALOG_GROUP_SHAPE')

    # Verify before any inference: pinned source, model files, reference and settings.
    if SOURCE_REVISION != EXPECTED_SOURCE_REVISION:
        raise SystemExit('SOURCE_REVISION_MISMATCH')
    source = verify_runtime_source()
    profiles = {}
    for language in ('tr', 'en', 'de'):
        config, _directory, reference, profile = load_configuration(args.config, language)
        if (profile['id'] != 'female-calm-v1' or profile['referenceSha256'] != EXPECTED_REFERENCE_SHA256
                or profile['generation'] != EXPECTED_GENERATION or file_sha256(reference) != EXPECTED_REFERENCE_SHA256
                or config['model']['revision'] != EXPECTED_MODEL_REVISION
                or config['model']['sourceRevision'] != EXPECTED_SOURCE_REVISION):
            raise SystemExit('PROFILE_MISMATCH')
        profiles[language] = profile
    before = integrity(args.config)
    if not all(before.values()):
        raise SystemExit('INTEGRITY_BEFORE')

    progress = out / 'worker-progress.json'
    os.environ['ATTUNE_MENTAL_TTS_PROGRESS'] = str(progress)
    runtime = {}
    record = {
        'schema': 'attune-mental-closing-abc-synthesis-v1',
        'scope': 'Technical synthesis of the 45 closing A/B/C clips; not an owner listening approval.',
        'speakerProfile': 'female-calm-v1', 'referenceSha256': EXPECTED_REFERENCE_SHA256,
        'generation': EXPECTED_GENERATION, 'modelRevision': EXPECTED_MODEL_REVISION,
        'sourceRevision': source['sourceRevision'], 'packageVersion': source['version'],
        'sourceFilesVerified': source['filesVerified'],
        'runtime': {'python': sys.version.split()[0], 'torch': version('torch'), 'torchaudio': version('torchaudio'),
                    'transformers': version('transformers'), 'chatterbox-tts': version('chatterbox-tts'),
                    'threads': os.environ.get('ATTUNE_MENTAL_TTS_THREADS'), 'cpuCount': os.cpu_count(),
                    'machine': platform.machine()},
        'workerMode': 'resident-model-v1', 'seedRule': 'int(sha256(assetId).hexdigest()[:8], 16)',
        'postProcessing': 'PCM16 encoding by the product worker only; upstream watermark retained; no pitch/rate/silence edits',
        'integrityBefore': before, 'warmup': None, 'rows': [],
    }
    if source['version'] != EXPECTED_PACKAGE_VERSION:
        raise SystemExit('PACKAGE_VERSION_MISMATCH')

    def save():
        (out / 'synthesis.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', 'utf-8')

    # Warm-up: model construction and first inference, kept out of every clip timing.
    started = time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr):
        warm = synthesize({'config': args.config, 'language': 'en', 'text': 'Hello.', 'seed': 0}, runtime)
    record['warmup'] = {'seconds': round(time.perf_counter() - started, 3), 'sha256': hashlib.sha256(warm).hexdigest(),
                        'phases': worker_progress(progress), 'savedAsAsset': False}
    save()
    for row in rows:
        seed = seed_for(row['assetId'])
        target = out / row['language'] / row['group'] / row['fileName']
        target.parent.mkdir(parents=True, exist_ok=True)
        load = os.getloadavg()
        started = time.perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            raw = synthesize({'config': args.config, 'language': row['language'], 'text': row['exactText'], 'seed': seed}, runtime)
        seconds = time.perf_counter() - started
        metrics = pcm_metrics(raw)
        with target.open('xb') as stream:  # never overwrite
            stream.write(raw)
        record['rows'].append({
            'assetId': row['assetId'], 'language': row['language'], 'group': row['group'], 'variantId': row['variantId'],
            'fileName': row['fileName'], 'textSha256': hashlib.sha256(row['exactText'].encode()).hexdigest(),
            'seed': seed, 'sha256': hashlib.sha256(raw).hexdigest(), 'synthesisSeconds': round(seconds, 3),
            'realTimeFactor': round(seconds / metrics['durationSeconds'], 3), 'metrics': metrics,
            'phases': worker_progress(progress), 'hostLoadBefore': [round(x, 2) for x in load],
            'createdAtUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        })
        save()
        print(json.dumps({'file': row['fileName'], 'seconds': round(seconds, 2), 'audio': metrics['durationSeconds']}), flush=True)
    record['integrityAfter'] = integrity(args.config)
    record['complete'] = all(record['integrityAfter'].values()) and len(record['rows']) == 45
    save()
    if not record['complete']:
        raise SystemExit('INTEGRITY_AFTER')


if __name__ == '__main__':
    main()
