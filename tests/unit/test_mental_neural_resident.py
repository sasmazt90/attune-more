"""Resident speech worker: reuse, cancellation, failure and secrets. A stub stands in for the model."""
import asyncio
import io
import json
import os
from pathlib import Path
import sys
import wave

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import mental_neural_resident as resident  # noqa: E402
import mental_neural_tts as tts  # noqa: E402

STUB = """
import base64, io, json, os, sys, time, wave
log = os.environ['STUB_LOG']
open(log, 'a').write(json.dumps({'pid': os.getpid(), 'threads': os.environ.get('OMP_NUM_THREADS'), 'secret': os.environ.get('ATTUNE_MENTAL_TTS_TOKEN'), 'key': os.environ.get('OPENAI_API_KEY')}) + chr(10))
buffer = io.BytesIO()
with wave.open(buffer, 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b'\\x01\\x02' * 2400)
loaded = False
for raw in iter(sys.stdin.buffer.readline, b''):
    job = json.loads(raw)
    text = job.get('text', '')
    if text == 'hang':
        time.sleep(60)
    if text == 'crash':
        sys.exit(3)
    if text == 'fail':
        print(json.dumps({'error': True}), flush=True); continue
    reply = {'start': 'warm' if loaded else 'cold'}
    loaded = True
    if not job.get('warm'):
        reply['wav'] = base64.b64encode(buffer.getvalue()).decode()
    print(json.dumps(reply), flush=True)
"""


@pytest.fixture
def stub(tmp_path, monkeypatch):
    worker = tmp_path / 'stub.py'
    worker.write_text(STUB)
    log = tmp_path / 'log.jsonl'
    config = tmp_path / 'config.json'
    config.write_text('{}')
    monkeypatch.setattr(tts, 'RESIDENT_WORKER', worker)
    monkeypatch.setattr(tts, 'configuration_path', lambda profile=None: str(config))
    monkeypatch.setattr(tts, 'verify_request_configuration', lambda *a: None)
    monkeypatch.setattr(tts, '_resident', None)
    monkeypatch.setattr(tts, '_warm_task', None)
    monkeypatch.setattr(tts, '_busy', False)
    monkeypatch.setenv('STUB_LOG', str(log))
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_RESIDENT', '1')
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_THREADS', '4')
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_PYTHON', sys.executable)
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_TOKEN', 'must-not-reach-worker')
    monkeypatch.setenv('OPENAI_API_KEY', 'must-not-reach-worker')
    return lambda: [json.loads(line) for line in log.read_text().splitlines()]


async def allowed():
    return False


def say(text, permitted=lambda: True, disconnected=allowed):
    return tts.generate(text, 'en', permitted, disconnected)


def test_second_request_reuses_the_worker_and_reports_start(stub):
    async def run():
        first = await say('one')
        start_one = tts.last_generation['start']
        second = await say('two')
        start_two = tts.last_generation['start']
        await tts.close_resident()
        return first, second, start_one, start_two
    first, second, start_one, start_two = asyncio.run(run())
    assert first == second and first[:4] == b'RIFF'
    assert (start_one, start_two) == ('cold', 'warm')
    assert len(stub()) == 1


def test_worker_gets_the_thread_budget_and_no_secrets(stub):
    async def run():
        await say('one')
        await tts.close_resident()
    asyncio.run(run())
    row = stub()[0]
    assert row['threads'] == '4' and row['secret'] is None and row['key'] is None


def test_warm_up_serves_the_first_request_warm(stub):
    async def run():
        tts.schedule_warm()
        await say('one')
        start = tts.last_generation['start']
        await tts.close_resident()
        return start
    assert asyncio.run(run()) == 'warm'
    assert len(stub()) == 1


def test_disconnect_kills_inference_and_a_new_worker_serves_next(stub):
    async def run():
        gone = []

        async def disconnected():
            await asyncio.sleep(.05)
            gone.append(1)
            return len(gone) > 3
        with pytest.raises(HTTPException) as error:
            await say('hang', disconnected=disconnected)
        assert error.value.status_code == 499
        audio = await say('after')
        await tts.close_resident()
        return audio
    assert asyncio.run(run())[:4] == b'RIFF'
    pids = {row['pid'] for row in stub()}
    assert len(pids) == 2


def test_leaving_park_stops_inference(stub):
    async def run():
        checks = []

        def permitted():
            checks.append(1)
            return len(checks) < 4
        with pytest.raises(HTTPException) as error:
            await say('hang', permitted=permitted)
        assert error.value.status_code == 409
        await tts.close_resident()
    asyncio.run(run())


@pytest.mark.parametrize('text', ['crash', 'fail'])
def test_worker_failure_is_a_clean_error_then_recovers(stub, text):
    async def run():
        with pytest.raises(HTTPException) as error:
            await say(text)
        assert error.value.status_code == 503
        assert tts.last_generation['seconds'] is None
        audio = await say('after')
        await tts.close_resident()
        return audio
    assert asyncio.run(run())[:4] == b'RIFF'


def test_closing_profile_is_prepared_at_start_only_when_listed(stub, tmp_path, monkeypatch):
    """ATTUNE_MENTAL_TTS_WARM_PROFILES=female-calm-v1: after the default model, the closing voice's own configuration is
    prepared in the same worker before any request; its time is in warm_log, not in the request's own timing."""
    female = tmp_path / 'female.json'
    female.write_text('{}')
    default = tts.configuration_path()
    monkeypatch.setattr(tts, 'configuration_path', lambda profile=None: str(female) if profile == 'female-calm-v1' else default)
    monkeypatch.setattr(tts, 'warm_log', [])
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_WARM_PROFILES', 'female-calm-v1, unknown-profile')
    assert tts.warm_profiles() == ['female-calm-v1']

    async def run():
        tts.schedule_warm(profiles=tts.warm_profiles())
        await tts._warm_task
        audio = await tts.generate('one', 'en', lambda: True, allowed, speaker_profile='female-calm-v1')
        start = tts.last_generation['start']
        await tts.close_resident()
        return audio, start
    audio, start = asyncio.run(run())
    assert audio[:4] == b'RIFF' and start == 'warm'
    assert [(row['profile'], row['ok']) for row in tts.warm_log] == [('default', True), ('female-calm-v1', True)]
    assert all(isinstance(row['seconds'], float) for row in tts.warm_log)
    assert len(stub()) == 1, 'one resident worker holds both models'


def test_no_profile_is_prepared_at_start_by_default(stub, monkeypatch):
    monkeypatch.delenv('ATTUNE_MENTAL_TTS_WARM_PROFILES', raising=False)
    monkeypatch.setattr(tts, 'warm_log', [])
    assert tts.warm_profiles() == []

    async def run():
        tts.schedule_warm(profiles=tts.warm_profiles())
        await tts._warm_task
        await tts.close_resident()
    asyncio.run(run())
    assert [row['profile'] for row in tts.warm_log] == ['default']


def test_resident_is_off_by_default(monkeypatch):
    monkeypatch.delenv('ATTUNE_MENTAL_TTS_RESIDENT', raising=False)
    monkeypatch.delenv('ATTUNE_MENTAL_TTS_THREADS', raising=False)
    assert tts.resident_enabled() is False and tts.tts_threads() == 2


@pytest.mark.parametrize('value,expected', [('4', 4), ('0', 1), ('99', 16), ('many', 2)])
def test_thread_budget_is_bounded(monkeypatch, value, expected):
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_THREADS', value)
    assert tts.tts_threads() == expected


def fake_wave():
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b'\x00\x00' * 10)
    return buffer.getvalue()


def test_serve_keeps_one_model_per_configuration(monkeypatch):
    calls = []

    def synthesize(job, runtime):
        calls.append((job['config'], job['language'], 'model' in runtime))
        runtime.setdefault('model', object())
        return fake_wave()
    monkeypatch.setattr(resident, 'synthesize', synthesize)
    replies = []
    lines = [json.dumps(job).encode() + b'\n' for job in (
        {'config': 'a', 'language': 'en', 'warm': True},
        {'config': 'a', 'language': 'de', 'text': 'x'},
        {'config': 'b', 'language': 'en', 'text': 'y'},
    )]
    resident.serve(iter(lines), replies.append)
    assert calls == [('a', 'en', False), ('a', 'de', True), ('b', 'en', False)]
    assert 'wav' not in replies[0] and replies[0]['start'] == 'cold'
    assert replies[1]['start'] == 'warm' and replies[2]['start'] == 'cold'
    os.environ.pop('ATTUNE_MENTAL_TTS_PROGRESS', None)


def test_serve_reports_failure_without_its_message(monkeypatch):
    def synthesize(job, runtime):
        raise ValueError('private text ' + job['text'])
    monkeypatch.setattr(resident, 'synthesize', synthesize)
    replies = []
    resident.serve(iter([json.dumps({'config': 'a', 'language': 'en', 'text': 'secret words'}).encode() + b'\n']), replies.append)
    assert replies == [{'error': True}]
    os.environ.pop('ATTUNE_MENTAL_TTS_PROGRESS', None)
