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
@pytest.mark.parametrize('resident', [False, True])
def test_explicit_v3_conditioning_uses_only_verified_configuration(monkeypatch, tmp_path, language, has_conditioning, reference_profile, resident):
    progress = tmp_path / 'worker-timing.json'
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_PROGRESS', str(progress))
    reference = tmp_path / 'authorized-fixture.wav' if reference_profile else None
    generation = {'exaggeration': .35, 'cfg_weight': 0., 'temperature': .8}
    monkeypatch.setattr(worker, 'load_configuration', lambda *a, **kw: ({'device': 'cpu'}, tmp_path, reference, {'generation': generation}))
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
    runtime = {} if resident else None
    if has_conditioning:
        boundary.validate_wave(worker.synthesize(payload, runtime))
        options = {'audio_prompt_path': str(reference), **generation} if reference_profile else {}
        assert calls[1] == ('generate', (payload['text'],), {'language_id': language, **options})
        rows = boundary.worker_progress(progress)
        assert [row['phase'] for row in rows] == list(boundary.WORKER_PHASES)
        assert payload['text'] not in progress.read_text()
        if resident:
            boundary.validate_wave(worker.synthesize(payload, runtime))
            assert [c[0] for c in calls]==['load','generate','generate']
            generation['cfg_weight']=.9
            with pytest.raises(ValueError,match='BATCH_CONFIGURATION_CHANGED'):worker.synthesize(payload,runtime)
            assert [c[0] for c in calls]==['load','generate','generate']
    else:
        with pytest.raises(ValueError, match='OFFICIAL_DEFAULT_CONDITIONING_MISSING'):
            worker.synthesize(payload, runtime)
        assert len(calls) == 1
    assert calls[0] == ('load', (str(tmp_path), 'cpu'), {'t3_model': 'v3'})
    assert mapping.hf_hub_download(repo_id='ResembleAI/chatterbox', filename='Cangjie5_TC.json') == str(tmp_path / 'Cangjie5_TC.json')
    with pytest.raises(OSError, match='UNAPPROVED_AUXILIARY'):
        mapping.hf_hub_download(repo_id='another/model', filename='Cangjie5_TC.json')


def test_worker_refuses_requested_profile_mismatch_before_model_import(monkeypatch,tmp_path):
    monkeypatch.setattr(worker,'load_configuration',lambda *a,**kw:({},tmp_path,None,{'id':'official-default'}))
    with pytest.raises(ValueError,match='REQUESTED_SPEAKER_PROFILE_MISMATCH'):
        worker.synthesize({'config':'explicit-fixture','language':'en','text':'Nonpersonal closing fixture','speakerProfile':'female-calm-v1'})


def fake_reference_runtime(monkeypatch, tmp_path, reference, generation, fail_conditioning=None):
    """Explicit fake ML modules; records the upstream calls the worker makes."""
    monkeypatch.setattr(worker, 'load_configuration', lambda *a, **kw: (
        {'device': 'cpu'}, tmp_path, reference,
        {'id': 'female-calm-v1', 'generation': generation, 'referenceSha256': 'a' * 64} if reference else {'id': 'official-default'}))
    monkeypatch.setattr(worker, 'verify_runtime_source', lambda: {'fixture': 'explicit fake ML source'})
    versions = {'torch': '2.6.0+cpu', 'torchaudio': '2.6.0+cpu', 'transformers': '5.2.0', 'safetensors': '0.5.3'}
    monkeypatch.setattr(worker, 'version', versions.__getitem__)
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
        def __init__(self):
            self.conds = ('builtin',)
        @classmethod
        def from_local(cls, *a, **kw):
            calls.append(('load',))
            return cls()
        def prepare_conditionals(self, path, exaggeration=.5):
            calls.append(('prepare', path, exaggeration))
            if fail_conditioning and fail_conditioning.pop():
                raise RuntimeError('fixture conditioning failure')
            self.conds = ('reference', path, exaggeration, len(calls))
        def generate(self, *a, **kw):
            calls.append(('generate', a, kw, self.conds))
            return Tensor()
    mtl = ModuleType('chatterbox.mtl_tts')
    mtl.ChatterboxMultilingualTTS = Model
    tokenizers = ModuleType('chatterbox.models.tokenizers')
    tokenizers.tokenizer = ModuleType('chatterbox.models.tokenizers.tokenizer')
    for name, module in [('torch', torch), ('chatterbox', ModuleType('chatterbox')),
                         ('chatterbox.mtl_tts', mtl), ('chatterbox.models', ModuleType('chatterbox.models')),
                         ('chatterbox.models.tokenizers', tokenizers)]:
        monkeypatch.setitem(sys.modules, name, module)
    return calls


GENERATION = {'exaggeration': .35, 'cfg_weight': 0., 'temperature': .8}


def test_reference_conditioning_reuse_is_opt_in_and_preserves_upstream_settings(monkeypatch, tmp_path):
    reference = tmp_path / 'authorized-fixture.wav'
    calls = fake_reference_runtime(monkeypatch, tmp_path, reference, dict(GENERATION))
    monkeypatch.setenv(worker.REUSE_CONDITIONING, '1')
    english, german = {}, {}
    payload = {'config': 'fixture', 'language': 'en', 'text': 'Nonpersonal fixture'}
    for _ in range(3):
        boundary.validate_wave(worker.synthesize(payload, english))
    prepared = [c for c in calls if c[0] == 'prepare']
    generated = [c for c in calls if c[0] == 'generate']
    # Derived once, with the same reference and exaggeration upstream would use.
    assert prepared == [('prepare', str(reference), .35)]
    assert [c[2] for c in generated] == [{'language_id': 'en', **GENERATION}] * 3
    assert len({c[3] for c in generated}) == 1 and generated[0][3][0] == 'reference'
    # A runtime for another language shares the model but derives its own copy once.
    german['model'] = english['model']
    worker.synthesize({**payload, 'language': 'de'}, german)
    worker.synthesize({**payload, 'language': 'de'}, german)
    assert [c[0] for c in calls].count('prepare') == 2


@pytest.mark.parametrize('flag', [None, '0', 'true'])
def test_default_and_unrecognised_flag_keep_per_request_reference_path(monkeypatch, tmp_path, flag):
    reference = tmp_path / 'authorized-fixture.wav'
    calls = fake_reference_runtime(monkeypatch, tmp_path, reference, dict(GENERATION))
    if flag is None:
        monkeypatch.delenv(worker.REUSE_CONDITIONING, raising=False)
    else:
        monkeypatch.setenv(worker.REUSE_CONDITIONING, flag)
    runtime = {}
    for _ in range(2):
        worker.synthesize({'config': 'fixture', 'language': 'tr', 'text': 'Nonpersonal fixture'}, runtime)
    assert [c[0] for c in calls] == ['load', 'generate', 'generate']
    assert all(c[2] == {'language_id': 'tr', 'audio_prompt_path': str(reference), **GENERATION} for c in calls[1:])
    assert 'conditioning' not in runtime


def test_one_shot_and_official_default_ignore_reuse_flag(monkeypatch, tmp_path):
    monkeypatch.setenv(worker.REUSE_CONDITIONING, '1')
    reference = tmp_path / 'authorized-fixture.wav'
    calls = fake_reference_runtime(monkeypatch, tmp_path, reference, dict(GENERATION))
    worker.synthesize({'config': 'fixture', 'language': 'en', 'text': 'Nonpersonal fixture'})
    assert [c[0] for c in calls] == ['load', 'generate']
    assert calls[1][2]['audio_prompt_path'] == str(reference)
    calls = fake_reference_runtime(monkeypatch, tmp_path, None, dict(GENERATION))
    runtime = {}
    for _ in range(2):
        worker.synthesize({'config': 'fixture', 'language': 'en', 'text': 'Nonpersonal fixture'}, runtime)
    assert [c[0] for c in calls] == ['load', 'generate', 'generate']
    assert all(c[2] == {'language_id': 'en'} and c[3] == ('builtin',) for c in calls[1:])


def test_failed_or_changed_conditioning_is_never_reused(monkeypatch, tmp_path):
    monkeypatch.setenv(worker.REUSE_CONDITIONING, '1')
    reference = tmp_path / 'authorized-fixture.wav'
    calls = fake_reference_runtime(monkeypatch, tmp_path, reference, dict(GENERATION), fail_conditioning=[False, True])
    runtime = {}
    payload = {'config': 'fixture', 'language': 'en', 'text': 'Nonpersonal fixture'}
    with pytest.raises(RuntimeError, match='fixture conditioning failure'):
        worker.synthesize(payload, runtime)
    assert 'conditioning' not in runtime and [c[0] for c in calls] == ['load', 'prepare']
    worker.synthesize(payload, runtime)
    assert [c[0] for c in calls] == ['load', 'prepare', 'prepare', 'generate']
    model = runtime['model']
    # A different verified hash or exaggeration, or a replaced model, derives anew.
    profile = {'generation': dict(GENERATION), 'referenceSha256': 'b' * 64}
    assert worker.reference_options(model, runtime, reference, profile) == GENERATION
    assert worker.reference_options(model, runtime, reference, {**profile, 'generation': {**GENERATION, 'exaggeration': .5}})['exaggeration'] == .5
    replacement = type(model)()
    worker.reference_options(replacement, runtime, reference, profile)
    assert [c[0] for c in calls].count('prepare') == 5
    assert runtime['conditioning'][0] is replacement
