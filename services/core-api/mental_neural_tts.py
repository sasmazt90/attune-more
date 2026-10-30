"""Opt-in local Chatterbox V3 boundary. No downloads, imports of ML, or loading at startup."""
import asyncio
import hashlib
import hmac
import io
from importlib.metadata import distribution
import json
import logging
import os
from pathlib import Path
import re
import sys
import tempfile
from time import monotonic
import wave
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from owned_python_process import OwnedProcessTree

MODEL_REPO = 'ResembleAI/chatterbox'
SOURCE_REVISION = '5de7a54aa4e5e2baadb0182dde554908b48b85c2'
MODEL_FILE = 't3_mtl23ls_v3.safetensors'
REQUIRED_FILES = (MODEL_FILE, 've.pt', 's3gen.pt', 'grapheme_mtl_merged_expanded_v1.json', 'Cangjie5_TC.json', 'conds.pt')
MAX_AUDIO = 8 * 1024 * 1024
LIMITS = json.loads((Path(__file__).resolve().parents[2] / 'shared/localization/neural-tts-limits.json').read_text())
MAX_SECONDS = LIMITS['audioSeconds']
_busy = False
SOURCE_MANIFEST = Path(__file__).resolve().parents[2] / 'shared/localization/chatterbox-v3-source.json'
VOICE_PROFILE = Path(__file__).resolve().parents[2] / 'shared/mental/voices/female-calm-v1.json'
logger = logging.getLogger('uvicorn.error')
WORKER_PHASES = ('verify-assets', 'verify-source', 'import-runtime', 'load-model', 'inference', 'encode-wav', 'complete')


def worker_progress(path):
    """Only bounded, allowlisted numerical telemetry crosses into service logs."""
    try:
        with Path(path).open('rb') as stream:
            rows = json.loads(stream.read(4097))
        if not isinstance(rows, list) or len(rows) > len(WORKER_PHASES):
            return []
        safe = []
        for row in rows:
            if row['phase'] not in WORKER_PHASES:
                return []
            values = {key: row[key] for key in ('elapsedSeconds', 'cpuSeconds', 'peakRSSKiB')}
            if any(type(value) not in (int, float) or not 0 <= value < 2**40 for value in values.values()):
                return []
            safe.append({'phase': row['phase'], **values})
        return safe
    except (OSError, ValueError, KeyError, TypeError):
        return []


def verify_runtime_source(installed=None):
    """Pin actual installed Python bytes, including offline wheels/directories.

    PEP 610 VCS metadata alone neither supports offline directory installs nor
    detects edited source. These fingerprints come from the pinned official tree.
    """
    package = installed or distribution('chatterbox-tts')
    manifest = json.loads(SOURCE_MANIFEST.read_text('utf-8'))
    if manifest['sourceRevision'] != SOURCE_REVISION or package.version != manifest['packageVersion']:
        raise ValueError('PINNED_OFFICIAL_SOURCE_REQUIRED')
    root = Path(package.locate_file('chatterbox')).resolve(strict=True)
    expected = manifest['files']
    actual = {'chatterbox/' + p.relative_to(root).as_posix() for p in root.rglob('*.py')}
    if actual != set(expected):
        raise ValueError('OFFICIAL_SOURCE_FILE_SET_MISMATCH')
    for name, fingerprint in expected.items():
        path = Path(package.locate_file(name)).resolve(strict=True)
        if not path.is_relative_to(root) or digest(path) != fingerprint:
            raise ValueError('OFFICIAL_SOURCE_HASH_MISMATCH')
    return {'sourceRevision': SOURCE_REVISION, 'version': package.version, 'filesVerified': len(expected)}


def authorize(header):
    token = os.getenv('ATTUNE_MENTAL_TTS_TOKEN', '')
    if len(token) < 32:
        raise HTTPException(503, 'NEURAL_TTS_AUTH_UNCONFIGURED')
    if not hmac.compare_digest((header or '').encode(), ('Bearer ' + token).encode()):
        raise HTTPException(401, 'NEURAL_TTS_AUTH_REQUIRED')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verified_file(root, item, limit=None):
    if not isinstance(item, dict) or not isinstance(item.get('path'), str):
        raise ValueError('INVALID_FILE_MANIFEST')
    path = (root / item['path']).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('FILE_OUTSIDE_CONFIG_ROOT')
    expected = item.get('sha256', '')
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('UNVERIFIED_FILE_HASH')
    if limit and path.stat().st_size > limit:
        raise ValueError('FILE_TOO_LARGE')
    if digest(path) != expected:
        raise ValueError('FILE_HASH_MISMATCH')
    return path


def load_configuration(config_path, language, verify_models=True):
    if language not in ('tr', 'en', 'de'):
        raise ValueError('UNSUPPORTED_LANGUAGE')
    path = Path(config_path).resolve(strict=True)
    if path.stat().st_size > 65536:
        raise ValueError('CONFIG_TOO_LARGE')
    config = json.loads(path.read_text('utf-8'))
    root = path.parent
    model = config['model']
    revision = model.get('revision', '')
    if (model.get('repository') != MODEL_REPO or model.get('file') != MODEL_FILE
            or len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision)
            or model.get('sourceRevision') != SOURCE_REVISION or model.get('license') != 'MIT'):
        raise ValueError('UNVERIFIED_V3_ARTIFACT')
    # The operator must preserve the exact model repository's license evidence,
    # independently of the code license. A code license alone is insufficient.
    metadata_evidence = model.get('licenseEvidenceKind') == 'hf-repository-metadata'
    allowed_license_urls = (
        (f'https://huggingface.co/{MODEL_REPO}',) if metadata_evidence else (
            f'https://huggingface.co/{MODEL_REPO}/blob/{revision}/LICENSE',
            f'https://huggingface.co/{MODEL_REPO}/blob/{revision}/README.md'))
    if model.get('licenseURL') not in allowed_license_urls:
        raise ValueError('MODEL_LICENSE_EVIDENCE_REQUIRED')
    license_path = verified_file(root, model['licenseEvidence'], 65536)
    license_text = license_path.read_text('utf-8')
    if metadata_evidence:
        # Authenticated Hub metadata is repository-level evidence, not a fetched
        # snapshot README. Snapshot file integrity is checked independently below.
        licensed = (license_text.startswith('# ' + MODEL_REPO + '\n')
                    and re.search(r'^- \*\*License:\*\* mit\s*$', license_text, re.M) is not None)
    else:
        licensed = (('MIT License' in license_text or 'license: mit' in license_text.lower())
                    and 'resemble' in license_text.lower())
    if not licensed:
        raise ValueError('MODEL_MIT_LICENSE_REQUIRED')
    directory = (root / model['directory']).resolve(strict=True)
    if not directory.is_relative_to(root) or not directory.is_dir():
        raise ValueError('INVALID_MODEL_DIRECTORY')
    if verify_models:
        for name in REQUIRED_FILES:
            item = model['files'][name]
            actual = verified_file(root, item)
            if actual != directory / name:
                raise ValueError('MODEL_FILE_PATH_MISMATCH')
    if config.get('conditioning') == 'female-calm-v1':
        profile = json.loads(VOICE_PROFILE.read_text('utf-8'))
        if profile.get('id')!='female-calm-v1':raise ValueError('REFERENCE_PROFILE_ID_MISMATCH')
        reference = verified_file(root, config['referenceAudio'], 2 * 1024 * 1024)
        if config['referenceAudio']['sha256'] != profile['referenceSha256']:
            raise ValueError('REFERENCE_PROFILE_HASH_MISMATCH')
        with wave.open(str(reference), 'rb') as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 22050, 'NONE') or not 5 <= wav.getnframes() / wav.getframerate() <= 15:
                raise ValueError('INVALID_REFERENCE_AUDIO')
            if len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2:
                raise ValueError('TRUNCATED_REFERENCE_AUDIO')
        return config, directory, reference, {'id': profile['id'], 'language': language,
            'generation': profile['generation'], 'referenceSha256': profile['referenceSha256']}
    if config.get('conditioning') != 'official-default':
        raise ValueError('OFFICIAL_DEFAULT_CONDITIONING_REQUIRED')
    # from_local loads this internal tensor bundle. No external reference is used.
    if not (directory / 'conds.pt').is_file():
        raise ValueError('OFFICIAL_DEFAULT_CONDITIONING_MISSING')
    return config, directory, None, {'id':'official-default', 'language':language}



def validate_wave(raw):
    if not 44 < len(raw) <= MAX_AUDIO:
        raise ValueError('INVALID_GENERATED_AUDIO_SIZE')
    with wave.open(io.BytesIO(raw), 'rb') as audio:
        if (audio.getnchannels() != 1 or audio.getsampwidth() != 2
                or audio.getframerate() != 24000 or audio.getcomptype() != 'NONE'
                or not 0 < audio.getnframes() <= 24000 * MAX_SECONDS):
            raise ValueError('INVALID_GENERATED_PCM')
        if len(audio.readframes(audio.getnframes())) != audio.getnframes() * 2:
            raise ValueError('TRUNCATED_GENERATED_PCM')
    return raw


def configuration_path(speaker_profile=None):
    if speaker_profile=='female-calm-v1':
        return os.getenv('ATTUNE_MENTAL_TTS_FEMALE_CONFIG') or os.getenv('ATTUNE_MENTAL_TTS_CONFIG', '')
    return os.getenv('ATTUNE_MENTAL_TTS_CONFIG', '')


def verify_request_configuration(path, language, speaker_profile=None):
    # A request omitting speakerProfile must not bypass the female review gate.
    # Offline sample generation calls the worker directly and cannot activate it.
    try:
        with Path(path).open('rb') as stream:
            raw_configuration = stream.read(65537)
        if len(raw_configuration) > 65536:
            raise ValueError('CONFIG_TOO_LARGE')
        configuration = json.loads(raw_configuration)
        if not isinstance(configuration, dict):
            raise ValueError('INVALID_CONFIGURATION')
        if speaker_profile or configuration.get('conditioning') == 'female-calm-v1':
            from mental_audio_identity import verify_speaker
            verify_speaker(language, speaker_profile or 'female-calm-v1')
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'NEURAL_TTS_RUNTIME_UNAVAILABLE') from None


async def generate(text, language, permitted, disconnected, speaker_profile=None):
    """One bounded subprocess; cancellation kills inference and discards all output."""
    global _busy
    if _busy:
        raise HTTPException(429, 'NEURAL_TTS_BUSY')
    if not permitted():
        raise HTTPException(409, 'PARK_AND_AUTHENTICATION_REQUIRED')
    path = configuration_path(speaker_profile)
    if not path or not Path(path).is_file():
        raise HTTPException(503, 'NEURAL_TTS_MODEL_BUNDLE_UNAVAILABLE')
    _busy = True
    process = None
    owned = None
    task = None
    diagnostic = None
    started = monotonic()
    outcome = 'cancelled'
    try:
        # Hashing the complete approved bundle can take seconds on Windows.
        # Keep vehicle-state requests responsive, without skipping integrity or
        # owner approval checks. Hold admission across verification as well.
        await run_in_threadpool(verify_request_configuration, path, language, speaker_profile)
        if not permitted():
            raise HTTPException(409, 'PARK_AND_AUTHENTICATION_REQUIRED')
        if await disconnected():
            raise HTTPException(499, 'NEURAL_TTS_REQUEST_CANCELLED')
        executable = os.getenv('ATTUNE_MENTAL_TTS_PYTHON') or sys.executable
        env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
               'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2', 'HF_HUB_DISABLE_TELEMETRY': '1'}
        # Never pass provider keys or the service bearer secret into the worker.
        for key in list(env):
            if any(word in key.upper() for word in ('TOKEN', 'SECRET', 'API_KEY', 'PASSWORD')):
                env.pop(key, None)
        if os.getenv('ATTUNE_MENTAL_TTS_DIAGNOSTICS') == '1':
            diagnostic = tempfile.TemporaryDirectory(prefix='attune-tts-timing-')
            env['ATTUNE_MENTAL_TTS_PROGRESS'] = str(Path(diagnostic.name) / 'progress.json')
        else:
            env.pop('ATTUNE_MENTAL_TTS_PROGRESS', None)
        worker = Path(__file__).with_name('mental_neural_worker.py')
        process = await asyncio.create_subprocess_exec(executable, str(worker),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env)
        owned = OwnedProcessTree(getattr(process, 'pid', None))
        payload = json.dumps({'config': path, 'language': language, 'text': text, **({'speakerProfile':speaker_profile} if speaker_profile else {})}, ensure_ascii=False).encode()
        task = asyncio.create_task(process.communicate(payload))
        started = monotonic()
        while not task.done():
            if not permitted():
                raise HTTPException(409, 'PARK_AND_AUTHENTICATION_REQUIRED')
            if await disconnected():
                raise HTTPException(499, 'NEURAL_TTS_REQUEST_CANCELLED')
            if monotonic() - started >= LIMITS['workerSeconds']:
                raise HTTPException(504, 'NEURAL_TTS_DEADLINE')
            await asyncio.wait({task}, timeout=.1)
        raw, _ = task.result()
        if process.returncode:
            raise HTTPException(503, 'NEURAL_TTS_RUNTIME_UNAVAILABLE')
        if not permitted():
            raise HTTPException(409, 'PARK_AND_AUTHENTICATION_REQUIRED')
        if await disconnected():
            raise HTTPException(499, 'NEURAL_TTS_REQUEST_CANCELLED')
        try:
            audio = validate_wave(raw)
        except (ValueError, wave.Error, EOFError):
            raise HTTPException(503, 'NEURAL_TTS_INVALID_AUDIO') from None
        outcome = 'success'
        return audio
    except HTTPException as error:
        outcome = 'http-' + str(error.status_code)
        raise
    except (OSError, ValueError):
        outcome = 'runtime-unavailable'
        raise HTTPException(503, 'NEURAL_TTS_RUNTIME_UNAVAILABLE') from None
    finally:
        if process and process.returncode is None:
            if owned and owned.root is not None:
                await run_in_threadpool(owned.terminate)
            else:
                process.kill()
            await process.wait()
        if task:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        try:
            if diagnostic:
                logger.info('Neural worker timing %s', json.dumps({
                    'language': language if language in ('tr', 'en', 'de') else 'unknown',
                    'outcome': outcome, 'elapsedSeconds': round(monotonic() - started, 3),
                    'returncode': process.returncode if process else None,
                    'phases': worker_progress(Path(diagnostic.name) / 'progress.json'),
                }))
        finally:
            if diagnostic:
                diagnostic.cleanup()
            _busy = False


async def generate_for_request(text, language, permitted, request, speaker_profile=None):
    """Observe disconnects after FastAPI has consumed the validated JSON body.

    Request.is_disconnected uses a pre-cancelled receive probe. With the HTTP
    middleware's AnyIO receive stream it can miss a real client disconnect.
    A dedicated pending receive observes that event without that polling race.
    """
    gone = asyncio.Event()

    async def watch():
        try:
            while True:
                if (await request.receive())['type'] == 'http.disconnect':
                    gone.set()
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            gone.set()  # An unreadable connection must never keep inference alive.

    async def disconnected():
        return gone.is_set()

    watcher = asyncio.create_task(watch())
    try:
        return await generate(text, language, permitted, disconnected, **({'speaker_profile':speaker_profile} if speaker_profile else {}))
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
