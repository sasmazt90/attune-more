"""Synthetic WAV/model/config fixtures only; never real inference or voice acceptance."""
import asyncio
import hashlib
import io
import json
from pathlib import Path
import sys
import wave
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
import main
import mental_neural_tts as neural


def wav_bytes(frames=2400):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\x10\x00'*frames)
    return out.getvalue()

@pytest.fixture
def configuration(tmp_path):
    def item(name,data):
        p=tmp_path/name;p.parent.mkdir(exist_ok=True);p.write_bytes(data)
        return {'path':name,'sha256':hashlib.sha256(data).hexdigest()}
    files={name:item('model/'+name,b'SYNTHETIC WEIGHT FIXTURE') for name in neural.REQUIRED_FILES}
    license_item=item('MODEL-LICENSE',b'MIT License\nResemble AI\nSYNTHETIC TEST EVIDENCE, NOT ACTUAL MODEL RIGHTS')
    evidence=item('REFERENCE-RIGHTS',b'Explicit synthetic unit fixture only; not a real voice or rights grant')
    reference=item('reference.wav',wav_bytes(72000))
    profiles={lang:{'id':'fixture-'+lang,'language':lang,'gender':'female','cloningPermission':True,'sourceURL':'https://example.invalid/synthetic','license':'TEST FIXTURE','rightsExplanation':'synthetic unit fixture only','rightsEvidence':evidence,'audio':reference} for lang in ['tr','en','de']}
    model={'repository':neural.MODEL_REPO,'file':neural.MODEL_FILE,'sourceRevision':neural.SOURCE_REVISION,'revision':'0'*40,'license':'MIT','licenseURL':f'https://huggingface.co/{neural.MODEL_REPO}/blob/'+('0'*40)+'/LICENSE','licenseEvidence':license_item,'directory':'model','files':files}
    path=tmp_path/'config.json';config={'model':model,'profiles':profiles};path.write_text(json.dumps(config));return path,config

@pytest.mark.parametrize('language',['tr','en','de'])
def test_verified_fixture_routing_and_tamper_rejection(configuration,language):
    path,config=configuration
    assert neural.load_configuration(path,language)[3]['id']=='fixture-'+language
    config['profiles'][language]['cloningPermission']=False;path.write_text(json.dumps(config))
    with pytest.raises(ValueError,match='APPROVED_FEMALE'):neural.load_configuration(path,language)

@pytest.mark.parametrize('fault',['weight','version','gender','locale','reference','builtin'])
def test_unverified_resources_never_load(configuration,fault):
    path,c=configuration
    if fault=='weight':(path.parent/'model'/neural.MODEL_FILE).write_bytes(b'tampered')
    if fault=='version':c['model']['file']='t3_mtl23ls_v2.safetensors'
    if fault=='gender':c['profiles']['en']['gender']='unknown'
    if fault=='locale':c['profiles']['en']['language']='de'
    if fault=='reference':(path.parent/'reference.wav').write_bytes(b'tampered')
    if fault=='builtin':(path.parent/'model'/'conds.pt').write_bytes(b'unverified')
    path.write_text(json.dumps(c))
    with pytest.raises(ValueError):neural.load_configuration(path,'en')

@pytest.mark.parametrize('language',['tr','en','de'])
def test_authenticated_actual_api_transports_fixture_wav_without_rewriting_text(monkeypatch,language):
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_TOKEN','x'*40)
    monkeypatch.setitem(main.vehicle_state,'driverAuthenticated',True);monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False);monkeypatch.setitem(main.vehicle_state,'vehicleParked',True)
    calls=[]
    async def generate(text,lang,permitted,disconnected):
        assert permitted();calls.append((text,lang));return wav_bytes()
    monkeypatch.setattr(neural,'generate',generate)
    with TestClient(main.app) as client:
        kwargs={'json':{'text':'Nonpersonal dynamic 1287 Straße İ','language':language,'speechConsent':True}}
        assert client.post('/api/mental/neural-speech?language='+language,**kwargs).status_code==401
        r=client.post('/api/mental/neural-speech?language='+language,headers={'Authorization':'Bearer '+'x'*40},**kwargs)
    assert r.status_code==200 and r.content==wav_bytes();assert r.headers['x-tts-locale']==main.LANGUAGES[language]
    assert r.headers['cache-control']=='no-store';assert len(calls)==1 and calls[0]==(kwargs['json']['text'],language)

@pytest.mark.parametrize('fault,status',[('consent',403),('mismatch',422),('moving',409),('unknownPark',409),('driver',409),('unconfigured',503)])
def test_api_rejects_before_inference(monkeypatch,fault,status):
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_TOKEN','x'*40);monkeypatch.delenv('ATTUNE_MENTAL_TTS_CONFIG',raising=False)
    for key,value in [('driverAuthenticated',True),('vehicleMoving',False),('vehicleParked',True)]:monkeypatch.setitem(main.vehicle_state,key,value)
    if fault=='moving':monkeypatch.setitem(main.vehicle_state,'vehicleMoving',True)
    if fault=='unknownPark':monkeypatch.setitem(main.vehicle_state,'vehicleParked',None)
    if fault=='driver':monkeypatch.setitem(main.vehicle_state,'driverAuthenticated',False)
    payload={'text':'Synthetic nonpersonal','language':'de' if fault=='mismatch' else 'en','speechConsent':fault!='consent'}
    with TestClient(main.app) as client:r=client.post('/api/mental/neural-speech?language=en',json=payload,headers={'Authorization':'Bearer '+'x'*40})
    assert r.status_code==status

@pytest.mark.parametrize('failure',['motion','disconnect','cancel','badAudio','success'])
def test_inference_process_cleanup_and_stale_output(monkeypatch,tmp_path,failure):
    config=tmp_path/'present.json';config.write_text('{}');monkeypatch.setenv('ATTUNE_MENTAL_TTS_CONFIG',str(config));monkeypatch.setenv('OPENAI_API_KEY','must-not-reach-worker');monkeypatch.setenv('ATTUNE_MENTAL_TTS_TOKEN','must-not-reach-worker')
    async def scenario():
        class Process:
            returncode=None;killed=False
            async def communicate(self,payload):
                assert json.loads(payload)['text']=='Nonpersonal dynamic İı'
                if failure in ('success','badAudio'):
                    self.returncode=0;return (wav_bytes() if failure=='success' else b'not WAV'),b''
                await asyncio.Event().wait()
            def kill(self):self.killed=True;self.returncode=-9
            async def wait(self):return self.returncode
        process=Process();checks=0
        async def spawn(*args,**kwargs):
            assert kwargs['env']['HF_HUB_OFFLINE']=='1';assert 'OPENAI_API_KEY' not in kwargs['env'];assert 'ATTUNE_MENTAL_TTS_TOKEN' not in kwargs['env'];return process
        monkeypatch.setattr(neural.asyncio,'create_subprocess_exec',spawn)
        def permitted():
            nonlocal checks
            checks+=1;return failure!='motion' or checks<3
        async def disconnected():return failure=='disconnect'
        task=asyncio.create_task(neural.generate('Nonpersonal dynamic İı','en',permitted,disconnected))
        if failure=='cancel':await asyncio.sleep(.01);task.cancel()
        if failure=='success':assert await task==wav_bytes()
        else:
            with pytest.raises((HTTPException,asyncio.CancelledError)):await task
        if failure in ('motion','disconnect','cancel'):assert process.killed
        assert neural._busy is False
    asyncio.run(scenario())
