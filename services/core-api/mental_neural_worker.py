"""Isolated, offline-only inference. ML dependencies are optional and never imported by API startup."""
import contextlib
import io
import json
import os
import socket
from importlib.metadata import version
import sys
import wave
from pathlib import Path
from time import monotonic
from mental_neural_tts import load_configuration, MAX_SECONDS, verify_runtime_source


def synthesize(payload, runtime=None):
    started = monotonic()
    phases = []

    def progress(phase):
        # Private task-owned scratch file; never text, paths, tokens or raw ML logs.
        path = os.getenv('ATTUNE_MENTAL_TTS_PROGRESS')
        if not path:
            return
        cpu = os.times()
        peak = 0
        if sys.platform == 'linux':
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        phases.append({'phase': phase, 'elapsedSeconds': round(monotonic() - started, 3),
                       'cpuSeconds': round(cpu.user + cpu.system, 3), 'peakRSSKiB': peak})
        Path(path).write_text(json.dumps(phases), encoding='utf-8')

    progress('verify-assets')
    config, directory, reference, profile = load_configuration(payload['config'], payload['language'], **({'verify_models': False} if runtime and 'model' in runtime else {}))
    if payload.get('speakerProfile') and payload['speakerProfile']!=profile.get('id'):
        raise ValueError('REQUESTED_SPEAKER_PROFILE_MISMATCH')
    if runtime is not None:
        signature = json.dumps({'config':config,'profile':{key:profile.get(key) for key in ('id','generation','referenceSha256')}},sort_keys=True)
        if runtime.get('signature', signature) != signature:
            raise ValueError('BATCH_CONFIGURATION_CHANGED')
        runtime['signature'] = signature
    text = payload['text']
    if not isinstance(text, str) or not text.strip() or len(text) > 4096:
        raise ValueError('INVALID_TEXT')
    progress('verify-source')
    verify_runtime_source()
    for name, expected in [('torch','2.6.0'),('torchaudio','2.6.0'),('transformers','5.2.0'),('safetensors','0.5.3')]:
        if version(name).split('+')[0] != expected:
            raise ValueError('PINNED_RUNTIME_REQUIRED')
    def offline(*args, **kwargs):
        raise OSError('INFERENCE_NETWORK_DISABLED')
    socket.socket.connect = offline
    socket.socket.connect_ex = offline
    socket.socket.sendto = offline
    # Heavy imports and model construction happen only in this explicit worker.
    progress('import-runtime')
    import torch
    import numpy as np
    if 'seed' in payload:
        seed=payload['seed']
        if type(seed) is not int or not 0<=seed<=2**32-1:raise ValueError('INVALID_SEED')
        import random
        random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    from chatterbox.models.tokenizers import tokenizer as tokenizer_module
    def local_mapping(*args, **kwargs):
        if kwargs.get('repo_id') != 'ResembleAI/chatterbox' or kwargs.get('filename') != 'Cangjie5_TC.json':
            raise OSError('UNAPPROVED_AUXILIARY_ARTIFACT')
        return str(directory / 'Cangjie5_TC.json')
    tokenizer_module.hf_hub_download = local_mapping
    torch.set_num_threads(2)
    device = config.get('device', 'cpu')
    if device not in ('cpu', 'cuda'):
        raise ValueError('UNSUPPORTED_DEVICE')
    progress('load-model')
    if runtime is not None and 'model' in runtime:
        model = runtime['model']
    else:
        model = ChatterboxMultilingualTTS.from_local(str(directory), device, t3_model='v3')
        if runtime is not None:runtime['model'] = model
    if runtime is not None and 'seed' in payload:
        # Resident jobs seed after construction, independent of worker/order.
        # Existing one-shot recipes and all approved bytes remain unchanged.
        random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    # The review profile uses the upstream reference-audio API. Default calls
    # retain the original internal conditioning; all calls retain the watermark.
    if model.conds is None:
        raise ValueError('OFFICIAL_DEFAULT_CONDITIONING_MISSING')
    progress('inference')
    options = {} if reference is None else {'audio_prompt_path': str(reference), **profile['generation']}
    with torch.inference_mode():
        audio = model.generate(text, language_id=payload['language'], **options)
    progress('encode-wav')
    samples = audio.detach().cpu().numpy().reshape(-1)
    if model.sr != 24000 or not 0 < len(samples) <= model.sr * MAX_SECONDS or not np.isfinite(samples).all():
        raise ValueError('INVALID_MODEL_OUTPUT')
    pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(model.sr); wav.writeframes(pcm)
    progress('complete')
    return output.getvalue()


if __name__ == '__main__':
    try:
        data = sys.stdin.buffer.read(32769)
        if len(data) > 32768:
            raise ValueError('INPUT_TOO_LARGE')
        request = json.loads(data)
        # Model libraries can print progress or normalized text. Suppress those
        # messages at the parent; only validated WAV bytes travel over stdout.
        with contextlib.redirect_stdout(sys.stderr):
            result = synthesize(request)
        sys.stdout.buffer.write(result)
    except Exception:
        # Do not emit exception messages containing user text or local paths.
        sys.exit(1)
