"""Verify the actual generate boundary yields during slow identity validation."""
import asyncio,time,sys
from pathlib import Path
import pytest
from fastapi import HTTPException
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
import mental_neural_tts as neural

def test_identity_validation_does_not_starve_vehicle_checks(monkeypatch,tmp_path):
    config=tmp_path/'config.json';config.write_text('{}')
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_CONFIG',str(config))
    monkeypatch.setattr(neural,'verify_request_configuration',lambda *_:time.sleep(.25))
    async def scenario():
        ticks=0
        async def disconnected():return True
        task=asyncio.create_task(neural.generate('synthetic','en',lambda:True,disconnected))
        while not task.done():
            ticks+=1;await asyncio.sleep(.01)
        with pytest.raises(HTTPException) as error:await task
        assert error.value.status_code==499
        assert ticks>=10 and neural._busy is False
    asyncio.run(scenario())


def test_api_explicit_speaker_validation_yields_before_worker(monkeypatch,tmp_path):
    import main, mental_audio_identity
    from starlette.requests import Request
    config=tmp_path/'config.json';config.write_text('{"conditioning":"female-calm-v1"}')
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_CONFIG',str(config))
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_TOKEN','f'*40)
    monkeypatch.setattr(main,'current_language',lambda:'en')
    for key,value in [('driverAuthenticated',True),('vehicleMoving',False),('vehicleParked',True)]:
        monkeypatch.setitem(main.vehicle_state,key,value)
    calls=[]
    def verify(*args):
        calls.append(args);time.sleep(.25)
    monkeypatch.setattr(mental_audio_identity,'verify_speaker',verify)
    async def scenario():
        async def receive():return {'type':'http.disconnect'}
        request=Request({'type':'http','headers':[(b'authorization',b'Bearer '+b'f'*40)]},receive)
        payload=main.NeuralSpeechPayload(text='Synthetic closing test',language='en',speechConsent=True,speakerProfile='female-calm-v1')
        task=asyncio.create_task(main.mental_neural_speech(payload,request))
        ticks=0
        while not task.done():ticks+=1;await asyncio.sleep(.01)
        with pytest.raises(HTTPException) as error:await task
        assert error.value.status_code==499
        assert ticks>=10 and calls==[('en','female-calm-v1')] and not neural._busy
    asyncio.run(scenario())
