import base64
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import speech_transcription as speech


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv('ATTUNE_CLOUD_ASR_ENABLED', '1')
    monkeypatch.setenv('ATTUNE_TRUSTED_ORIGINS', 'http://localhost:3000')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-not-a-key')
    app=FastAPI();app.include_router(speech.router)
    return TestClient(app)


def payload(**extra):
    return dict(audio=base64.b64encode(b'RIFF'+b'\x00'*4+b'WAVE'+b'\x00'*100).decode(),
                consent=True,service='mental',language='tr',**extra)


def post(api, body=None, origin='http://localhost:3000'):
    return api.post('/api/speech/transcribe',json=body or payload(),headers={'origin':origin} if origin else {})


@pytest.mark.parametrize('origin',[None,'https://example.com','null'])
def test_origin_is_mandatory(api,origin):
    assert post(api,origin=origin).status_code==403


def test_default_disabled(api,monkeypatch):
    monkeypatch.delenv('ATTUNE_CLOUD_ASR_ENABLED')
    assert post(api).status_code==404


@pytest.mark.parametrize('change,status',[
    ({'consent':False},403),({'consent':'true'},403),({'language':'xx'},422),
    ({'service':'skin'},422),({'audio':'not base64'},422),
    ({'audio':base64.b64encode(b'x'*200).decode()},415),
    ({'audio':base64.b64encode(b'RIFF'+b'\x00'*2_000_000).decode()},413),
])
def test_invalid_input_never_reaches_provider(api,monkeypatch,change,status):
    monkeypatch.setattr(speech,'transcribe',lambda *args:pytest.fail('Provider must not run'))
    body=payload();body.update(change)
    assert post(api,body).status_code==status


def test_request_bytes_bounded(api,monkeypatch):
    response=api.post('/api/speech/transcribe',content=b'x'*(speech.MAX_BODY+1),headers={'origin':'http://localhost:3000','content-type':'application/json'})
    assert response.status_code==413


def test_actual_audio_forwarded_and_confidence_not_invented(api,monkeypatch):
    calls=[]
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text='Bugün sakin hissediyorum.')
    monkeypatch.setattr(speech,'get_openai_client',lambda key:SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create))))
    response=post(api)
    assert response.status_code==200
    assert response.json()['text']=='Bugün sakin hissediyorum.'
    assert response.json()['confidence']==0
    assert response.headers['cache-control']=='no-store'
    assert calls[0]['file'][1]==base64.b64decode(payload()['audio'])
    assert calls[0]['extra_body']=={'languages':['tr']}


def test_provider_failure_redacted_and_slot_released(api,monkeypatch):
    def fail(key):raise RuntimeError('sensitive provider body')
    monkeypatch.setattr(speech,'get_openai_client',fail)
    response=post(api)
    assert response.status_code==502
    assert 'sensitive' not in response.text
    assert speech._slot.acquire(blocking=False)
    speech._slot.release()


def test_busy_rejected(api):
    assert speech._slot.acquire(blocking=False)
    try:assert post(api).status_code==429
    finally:speech._slot.release()


def test_frontend_microphone_consent_and_abort_lifecycle():
    result=subprocess.run(['node','tests/unit/cloud_speech_runtime.cjs'],cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
