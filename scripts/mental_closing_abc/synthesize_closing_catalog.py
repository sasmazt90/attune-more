#!/usr/bin/env python3
"""Synthesize the 99 catalog closing lines (33 x TR/EN/DE) once, with the female-calm-v1 profile of the 45 A/B/C clips.

Runs on the WEB host with its existing pinned runtime (Chatterbox 0.1.7, source 5de7a54...), model bundle and approved
reference audio, through the same ``mental_neural_worker.synthesize`` function the product uses; the checks and
settings are those of synthesize_closing_abc.py (imported, not copied): pinned source, six model files and reference
hashed before and after, generation settings exaggeration 0.35 / cfg_weight 0.0 / temperature 0.8, one deterministic
seed per asset id (first 32 bits of SHA-256), PCM16 by the product worker, upstream watermark kept, no edits.

* One take per line: nothing is regenerated or picked from several takes. Technical findings (clipping, long silence,
  an implausible length) are recorded per row for review; they never trigger a new take.
* Language by language (TR, EN, DE): the page uses a language's catalog only when all 33 of its lines exist, so a
  deadline (--stop-at, epoch seconds) ends the run between clips and leaves whole languages; the record says so.
* Exclusive file creation (never overwrites); no network, provider, user text or credentials.

The output is a technical preview; owner listening approval is a separate step.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synthesize_closing_abc import (EXPECTED_GENERATION, EXPECTED_MODEL_REVISION, EXPECTED_PACKAGE_VERSION,  # noqa: E402
                                    EXPECTED_REFERENCE_SHA256, EXPECTED_SOURCE_REVISION, file_sha256, integrity,
                                    pcm_metrics, seed_for)

LANGUAGES = ('tr', 'en', 'de')
LINES = 33


def rows_of(catalog):
    if len(catalog['patterns']) != LINES:
        raise SystemExit('CATALOG_SHAPE')
    rows = []
    for language in LANGUAGES:
        for p in catalog['patterns']:
            asset = f"closing-catalog/v1/{language}/female-calm-v1/{p['id']}"
            rows.append({'assetId': asset, 'language': language, 'patternId': p['id'], 'exactText': p['text'][language],
                         'fileName': f"{language.upper()}_{p['id']}.wav"})
    return rows


def findings(metrics, text):
    """Technical observations only (no listening judgement); recorded, never used to pick or redo a take."""
    out = []
    if metrics['clippedSamples']:
        out.append(f"clipped-samples:{metrics['clippedSamples']}")
    if metrics['leadingSilenceMs'] > 400:
        out.append(f"leading-silence-ms:{metrics['leadingSilenceMs']}")
    if metrics['trailingSilenceMs'] > 900:
        out.append(f"trailing-silence-ms:{metrics['trailingSilenceMs']}")
    words = len(text.split())
    per_word = metrics['durationSeconds'] / words
    if not 0.2 <= per_word <= 0.9:
        out.append(f'seconds-per-word:{per_word:.2f}')
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Directory holding services/core-api and shared/')
    parser.add_argument('--config', required=True, help='Existing female-calm-v1 runtime configuration')
    parser.add_argument('--catalog', required=True, help='shared/mental/closing-catalog/v1/catalog.json')
    parser.add_argument('--out', required=True, help='New directory; must not exist')
    parser.add_argument('--stop-at', type=float, default=None, help='Epoch seconds: no clip is started after this')
    parser.add_argument('--clip-budget-seconds', type=float, default=40.0, help='Assumed upper bound of one clip')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(Path(args.source) / 'services/core-api'))
    from importlib.metadata import version
    from mental_neural_tts import load_configuration, verify_runtime_source, worker_progress, SOURCE_REVISION
    from mental_neural_worker import synthesize

    catalog_bytes = Path(args.catalog).read_bytes()
    rows = rows_of(json.loads(catalog_bytes))
    if SOURCE_REVISION != EXPECTED_SOURCE_REVISION:
        raise SystemExit('SOURCE_REVISION_MISMATCH')
    source = verify_runtime_source()
    for language in LANGUAGES:
        config, _directory, reference, profile = load_configuration(args.config, language)
        if (profile['id'] != 'female-calm-v1' or profile['referenceSha256'] != EXPECTED_REFERENCE_SHA256
                or profile['generation'] != EXPECTED_GENERATION or file_sha256(reference) != EXPECTED_REFERENCE_SHA256
                or config['model']['revision'] != EXPECTED_MODEL_REVISION
                or config['model']['sourceRevision'] != EXPECTED_SOURCE_REVISION):
            raise SystemExit('PROFILE_MISMATCH')
    if source['version'] != EXPECTED_PACKAGE_VERSION:
        raise SystemExit('PACKAGE_VERSION_MISMATCH')
    before = integrity(args.config)
    if not all(before.values()):
        raise SystemExit('INTEGRITY_BEFORE')

    progress = out / 'worker-progress.json'
    os.environ['ATTUNE_MENTAL_TTS_PROGRESS'] = str(progress)
    runtime = {}
    record = {
        'schema': 'attune-mental-closing-catalog-synthesis-v1',
        'scope': 'Technical synthesis of the 99 catalog closing lines; one take each; not an owner listening approval.',
        'catalogSha256': hashlib.sha256(catalog_bytes).hexdigest(),
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
        'takesPerLine': 1, 'stopAt': args.stop_at, 'integrityBefore': before, 'warmup': None, 'rows': [], 'notStarted': [],
    }

    def save():
        (out / 'synthesis.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', 'utf-8')

    started = time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr):
        warm = synthesize({'config': args.config, 'language': 'en', 'text': 'Hello.', 'seed': 0}, runtime)
    record['warmup'] = {'seconds': round(time.perf_counter() - started, 3), 'sha256': hashlib.sha256(warm).hexdigest(),
                        'phases': worker_progress(progress), 'savedAsAsset': False}
    save()
    for row in rows:
        if args.stop_at and time.time() + args.clip_budget_seconds > args.stop_at:
            record['notStarted'].append(row['assetId'])
            continue
        seed = seed_for(row['assetId'])
        target = out / row['language'] / row['fileName']
        target.parent.mkdir(parents=True, exist_ok=True)
        load = os.getloadavg()
        started = time.perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            raw = synthesize({'config': args.config, 'language': row['language'], 'text': row['exactText'], 'seed': seed}, runtime)
        seconds = time.perf_counter() - started
        metrics = pcm_metrics(raw)
        with target.open('xb') as stream:
            stream.write(raw)
        record['rows'].append({
            'assetId': row['assetId'], 'language': row['language'], 'patternId': row['patternId'], 'fileName': row['fileName'],
            'textSha256': hashlib.sha256(row['exactText'].encode()).hexdigest(), 'seed': seed,
            'sha256': hashlib.sha256(raw).hexdigest(), 'synthesisSeconds': round(seconds, 3),
            'realTimeFactor': round(seconds / metrics['durationSeconds'], 3), 'metrics': metrics,
            'technicalFindings': findings(metrics, row['exactText']),
            'phases': worker_progress(progress), 'hostLoadBefore': [round(x, 2) for x in load],
            'createdAtUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        })
        save()
        print(json.dumps({'file': row['fileName'], 'seconds': round(seconds, 2), 'audio': metrics['durationSeconds']}), flush=True)
    record['integrityAfter'] = integrity(args.config)
    made = {r['language'] for r in record['rows']}
    record['completeLanguages'] = [lang for lang in LANGUAGES if sum(r['language'] == lang for r in record['rows']) == LINES]
    record['complete'] = all(record['integrityAfter'].values()) and len(record['rows']) == len(rows)
    record['partial'] = sorted(made - set(record['completeLanguages']))
    save()
    if not all(record['integrityAfter'].values()):
        raise SystemExit('INTEGRITY_AFTER')
    return 0 if record['complete'] else 3


if __name__ == '__main__':
    sys.exit(main())
