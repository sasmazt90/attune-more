"""Opt-in local Chatterbox V3 boundary. No downloads, imports of ML, or loading at startup."""
import asyncio
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import sys
from time import monotonic
import wave
from fastapi import HTTPException

MODEL_REPO = 'ResembleAI/chatterbox'
SOURCE_REVISION = '5de7a54aa4e5e2baadb0182dde554908b48b85c2'
MODEL_FILE = 't3_mtl23ls_v3.safetensors'
REQUIRED_FILES = (MODEL_FILE, 've.pt', 's3gen.pt', 'grapheme_mtl_merged_expanded_v1.json', 'Cangjie5_TC.json')
MAX_AUDIO = 8 * 1024 * 1024
MAX_SECONDS = 60
_busy = False


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
    if model.get('licenseURL') not in (
            f'https://huggingface.co/{MODEL_REPO}/blob/{revision}/LICENSE',
            f'https://huggingface.co/{MODEL_REPO}/blob/{revision}/README.md'):
        raise ValueError('MODEL_LICENSE_EVIDENCE_REQUIRED')
    license_path = verified_file(root, model['licenseEvidence'], 65536)
    license_text = license_path.read_text('utf-8')
    if not ('MIT License' in license_text or 'license: mit' in license_text.lower()) or 'resemble' not in license_text.lower():
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
        # from_local auto-loads conds.pt; prohibit unapproved builtin conditioning.
        if (directory / 'conds.pt').exists():
            raise ValueError('UNAPPROVED_BUILTIN_CONDITIONING')
    profile = config['profiles'][language]
    if (profile.get('language') != language or profile.get('gender') != 'female'
            or profile.get('cloningPermission') is not True
            or not profile.get('id') or not profile.get('sourceURL')
            or not profile.get('license') or not profile.get('rightsExplanation')):
        raise ValueError('APPROVED_FEMALE_REFERENCE_REQUIRED')
    reference = verified_file(root, profile['audio'], 4 * 1024 * 1024)
    verified_file(root, profile['rightsEvidence'], 65536)
    with wave.open(str(reference), 'rb') as audio:
        duration = audio.getnframes() / audio.getframerate()
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or not 3 <= duration <= 15:
            raise ValueError('REFERENCE_PCM_MONO_3_TO_15_SECONDS_REQUIRED')
    return config, directory, reference, profile


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


async def generate(text, language, permitted, disconnected):
    """One bounded subprocess; cancellation kills inference and discards all output."""
    global _busy
    if _busy:
        raise HTTPException(429, 'NEURAL_TTS_BUSY')
    if not permitted():
        raise HTTPException(409, 'PARK_AND_AUTHENTICATION_REQUIRED')
    path = os.getenv('ATTUNE_MENTAL_TTS_CONFIG', '')
    if not path or not Path(path).is_file():
        raise HTTPException(503, 'NEURAL_TTS_MODEL_AND_PROFILES_UNAVAILABLE')
    _busy = True
    process = None
    task = None
    try:
        executable = os.getenv('ATTUNE_MENTAL_TTS_PYTHON') or sys.executable
        env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
               'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2', 'HF_HUB_DISABLE_TELEMETRY': '1'}
        # Never pass provider keys or the service bearer secret into the worker.
        for key in list(env):
            if any(word in key.upper() for word in ('TOKEN', 'SECRET', 'API_KEY', 'PASSWORD')):
                env.pop(key, None)
        worker = Path(__file__).with_name('mental_neural_worker.py')
        process = await asyncio.create_subprocess_exec(executable, str(worker),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env)
        payload = json.dumps({'config': path, 'language': language, 'text': text}, ensure_ascii=False).encode()
        task = asyncio.create_task(process.communicate(payload))
        started = monotonic()
        while not task.done():
            if not permitted():
                raise HTTPException(409, 'PARK_AND_AUTHENTICATION_REQUIRED')
            if await disconnected():
                raise HTTPException(499, 'NEURAL_TTS_REQUEST_CANCELLED')
            if monotonic() - started >= 90:
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
            return validate_wave(raw)
        except (ValueError, wave.Error, EOFError):
            raise HTTPException(503, 'NEURAL_TTS_INVALID_AUDIO') from None
    except (OSError, ValueError):
        raise HTTPException(503, 'NEURAL_TTS_RUNTIME_UNAVAILABLE') from None
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        if task:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        _busy = False
