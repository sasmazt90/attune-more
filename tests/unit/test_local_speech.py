"""Optional local synthesis: metadata, missing tools and fail-closed restrictions."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import local_speech as S
from localization import request_language

def test_missing_tools_never_advertise_voices(monkeypatch):
    monkeypatch.setattr(S.shutil,'which',lambda _:None)
    assert asyncio.run(S.available_local_voices('en'))==[]
    assert asyncio.run(S.available_local_voices('de'))==[]
    assert asyncio.run(S.available_local_voices('tr'))==[]

@pytest.mark.parametrize('language',['en','de'])
def test_restricted_and_wrong_locale_never_synthesize(monkeypatch,language):
    token=request_language.set(language)
    synth=AsyncMock(side_effect=AssertionError('Must not synthesize'))
    monkeypatch.setattr(S,'mp3_bytes',synth)
    monkeypatch.setattr(S,'available_local_voices',AsyncMock(return_value=[]))
    try:
        with pytest.raises(HTTPException) as error:asyncio.run(S.response('Private text','espeak:en:male',lambda:True))
        assert error.value.status_code==409
        with pytest.raises(HTTPException) as error:asyncio.run(S.response('Private text','espeak:tr:male',lambda:False))
        assert error.value.status_code==503
        assert synth.await_count==0
    finally:request_language.reset(token)

def test_driving_transition_stops_buffered_output(monkeypatch):
    token=request_language.set('en')
    calls=[]
    monkeypatch.setattr(S,'available_local_voices',AsyncMock(return_value=[{'id':'espeak:en:male','gender':'male'}]))
    monkeypatch.setattr(S,'mp3_bytes',AsyncMock(return_value=b'fixed-digital-test-buffer'))
    def moving():
        calls.append(1);return len(calls)>=3
    async def run():
        response=await S.response('Test','espeak:en:male',moving)
        return [chunk async for chunk in response.body_iterator]
    try:assert asyncio.run(run())==[]
    finally:request_language.reset(token)
