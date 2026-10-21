"""Isolated, offline-only inference. ML dependencies are optional and never imported by API startup."""
import contextlib
import io
import json
import socket
from importlib.metadata import version
import sys
import wave
from mental_neural_tts import load_configuration, MAX_SECONDS, verify_runtime_source


def synthesize(payload):
    config, directory, _, _ = load_configuration(payload['config'], payload['language'])
    text = payload['text']
    if not isinstance(text, str) or not text.strip() or len(text) > 4096:
        raise ValueError('INVALID_TEXT')
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
    import torch
    import numpy as np
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
    model = ChatterboxMultilingualTTS.from_local(str(directory), device, t3_model='v3')
    # Keep the official internal default conditioning and upstream watermark.
    if model.conds is None:
        raise ValueError('OFFICIAL_DEFAULT_CONDITIONING_MISSING')
    with torch.inference_mode():
        audio = model.generate(text, language_id=payload['language'])
    samples = audio.detach().cpu().numpy().reshape(-1)
    if model.sr != 24000 or not 0 < len(samples) <= model.sr * MAX_SECONDS or not np.isfinite(samples).all():
        raise ValueError('INVALID_MODEL_OUTPUT')
    pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(model.sr); wav.writeframes(pcm)
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
