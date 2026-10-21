"""Approved original asset and exact female live-provider contracts; no live requests."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from localization import request_language
import vision_speech

def test_all_194_original_recordings_and_129_active_mappings():
    manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/user-approved/tr-en-de-20261020-v1/manifest.json').read_text())
    assert len(manifest['recordings'])==194
    assert len(manifest['activeGuidanceMappings'])==129
    ids=set()
    for clip in manifest['recordings']:
        assert clip['recordingId'] not in ids
        ids.add(clip['recordingId'])
        data=(ROOT/'apps/vehicle-app/public'/clip['url'].lstrip('/')).read_bytes()
        assert len(data)==clip['bytes'] and hashlib.sha256(data).hexdigest()==clip['sha256']
        assert hashlib.sha256(clip['exactScript'].encode()).hexdigest()==clip['scriptSHA256']
    result=subprocess.run(['node','tests/unit/approved_audio_runtime.cjs'],cwd=ROOT,text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr

@pytest.mark.parametrize('language,exact',[('tr','tr-TR-EmelNeural'),('en','en-GB-AdaMultilingualNeural')])
def test_dynamic_mental_requires_exact_approved_female(monkeypatch,language,exact):
    token=request_language.set(language)
    speech=AsyncMock(return_value='response')
    monkeypatch.setattr(vision_speech,'speech_response',speech)
    try:
        assert asyncio.run(vision_speech.mental_response('Arbitrary dynamic text',lambda:False))=='response'
        assert speech.call_args.args[0]=='Arbitrary dynamic text'
        assert speech.call_args.args[1].voice==exact
        for wrong in ['espeak:en:male','en-US-AndrewMultilingualNeural','de-DE-KatjaNeural']:
            with pytest.raises(HTTPException) as error:asyncio.run(vision_speech.mental_response('text',lambda:False,wrong))
            assert error.value.status_code==422
        assert speech.await_count==1
    finally:request_language.reset(token)

def test_german_dynamic_voice_unverified_and_moving_fail_closed(monkeypatch):
    token=request_language.set('de')
    speech=AsyncMock(side_effect=AssertionError('Unverified voice must not dispatch'))
    monkeypatch.setattr(vision_speech,'speech_response',speech)
    try:
        with pytest.raises(HTTPException) as error:asyncio.run(vision_speech.mental_response('text',lambda:False))
        assert error.value.status_code==503 and error.value.detail=='EXACT_FEMALE_DYNAMIC_VOICE_UNVERIFIED'
        with pytest.raises(HTTPException) as error:asyncio.run(vision_speech.mental_response('text',lambda:True))
        assert error.value.status_code==409
        assert speech.await_count==0
    finally:request_language.reset(token)
