"""Actual worker control flow with explicit fake ML modules; NEVER neural evidence."""
import contextlib
from pathlib import Path
import socket
import sys
from types import ModuleType
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import mental_neural_worker as worker
import mental_neural_tts as boundary


@pytest.mark.parametrize('language', ['tr', 'en', 'de'])
@pytest.mark.parametrize('has_conditioning', [True, False])
@pytest.mark.parametrize('reference_profile', [False, True])
def test_explicit_v3_conditioning_uses_only_verified_configuration(monkeypatch, tmp_path, language, has_conditioning, reference_profile):
    progress = tmp_path / 'worker-timing.json'
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_PROGRESS', str(progress))
    reference = tmp_path / 'authorized-fixture.wav' if reference_profile else None
    generation = {'exaggeration': .35, 'cfg_weight': 0., 'temperature': .8}
    monkeypatch.setattr(worker, 'load_configuration', lambda *a: ({'device': 'cpu'}, tmp_path, reference, {'generation': generation}))
    monkeypatch.setattr(worker, 'verify_runtime_source', lambda: {'fixture': 'explicit fake ML source'})
    versions = {'torch': '2.6.0+cpu', 'torchaudio': '2.6.0+cpu', 'transformers': '5.2.0', 'safetensors': '0.5.3'}
    monkeypatch.setattr(worker, 'version', versions.__getitem__)
    # Ensure the worker's socket assignments are restored by pytest teardown.
    for method in ('connect', 'connect_ex', 'sendto'):
        monkeypatch.setattr(socket.socket, method, getattr(socket.socket, method))
    torch = ModuleType('torch')
    torch.set_num_threads = lambda n: None
    torch.inference_mode = contextlib.nullcontext
    calls = []
    class Tensor:
        def detach(self): return self
        def cpu(self): return self
        def numpy(self): return np.array([0, .25, -.25, 0], dtype=np.float32)
    class Model:
        sr = 24000
        conds = object() if has_conditioning else None
        @classmethod
        def from_local(cls, *a, **kw):
            calls.append(('load', a, kw))
            return cls()
        def generate(self, *a, **kw):
            calls.append(('generate', a, kw))
            return Tensor()
    mtl = ModuleType('chatterbox.mtl_tts')
    mtl.ChatterboxMultilingualTTS = Model
    mapping = ModuleType('chatterbox.models.tokenizers.tokenizer')
    tokenizers = ModuleType('chatterbox.models.tokenizers')
    tokenizers.tokenizer = mapping
    for name, module in [('torch', torch), ('chatterbox', ModuleType('chatterbox')),
                         ('chatterbox.mtl_tts', mtl), ('chatterbox.models', ModuleType('chatterbox.models')),
                         ('chatterbox.models.tokenizers', tokenizers)]:
        monkeypatch.setitem(sys.modules, name, module)
    payload = {'config': 'fixture', 'language': language, 'text': 'Explicit nonpersonal ML fixture'}
    if has_conditioning:
        boundary.validate_wave(worker.synthesize(payload))
        options = {'audio_prompt_path': str(reference), **generation} if reference_profile else {}
        assert calls[1] == ('generate', (payload['text'],), {'language_id': language, **options})
        rows = boundary.worker_progress(progress)
        assert [row['phase'] for row in rows] == list(boundary.WORKER_PHASES)
        assert payload['text'] not in progress.read_text()
    else:
        with pytest.raises(ValueError, match='OFFICIAL_DEFAULT_CONDITIONING_MISSING'):
            worker.synthesize(payload)
        assert len(calls) == 1
    assert calls[0] == ('load', (str(tmp_path), 'cpu'), {'t3_model': 'v3'})
    assert mapping.hf_hub_download(repo_id='ResembleAI/chatterbox', filename='Cangjie5_TC.json') == str(tmp_path / 'Cangjie5_TC.json')
    with pytest.raises(OSError, match='UNAPPROVED_AUXILIARY'):
        mapping.hf_hub_download(repo_id='another/model', filename='Cangjie5_TC.json')
