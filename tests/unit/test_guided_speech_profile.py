"""Fixed Microsoft vision streaming contract; separate exact mental and vision profiles.
Replaces the superseded Coral profile assertion, preserving chunks and cleanup.
"""
import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
import main,vision_speech
from fastapi.testclient import TestClient

def test_speech_preserves_transport_chunks_and_closes(monkeypatch,tmp_path):
    monkeypatch.setattr(vision_speech,'FIXED_BANK',tmp_path)
    calls=[];closed=[]
    class Communicate:
        def __init__(self,text,voice,rate,pitch,connect_timeout,receive_timeout):
            assert (connect_timeout,receive_timeout)==(5,15)
            calls.append((text,voice,rate,pitch))
        async def stream(self):
            try:
                yield {'type':'audio','data':b'first'}
                yield {'type':'audio','data':b'second'}
            finally:closed.append(True)
    monkeypatch.setattr(vision_speech,'_catalogue',(time.monotonic(),frozenset([vision_speech.VOICE])))
    monkeypatch.setattr(vision_speech.edge_tts,'Communicate',Communicate)
    monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False)
    response=TestClient(main.app).post('/api/vision/speech',json={'text':'right','cloudConsent':True})
    assert response.status_code==200 and response.content==b'firstsecond'
    assert closed==[True] and len(calls)==1
    assert calls[0]==(vision_speech.PROMPTS['right'],'tr-TR-AhmetNeural','-10%','-10Hz')
    assert 'harf alanına bakın' in calls[0][0].lower() and 'veya örtün' in calls[0][0]
    assert 'kameraya bakın' not in calls[0][0].lower()
    assert 'harfi ve yönünü söyleyin' in vision_speech.PROMPTS['repeat'].lower()
    assert response.headers['cache-control']=='no-store'


def test_emel_exact_profile_preserves_chunks_and_cleanup(monkeypatch):
    calls=[];closed=[]
    class Communicate:
        def __init__(self,text,voice,rate,pitch,connect_timeout,receive_timeout):
            assert (connect_timeout,receive_timeout)==(5,15)
            calls.append((text,voice,rate,pitch))
        async def stream(self):
            try:
                yield {'type':'audio','data':b'one'}
                yield {'type':'audio','data':b'two'}
            finally:closed.append(True)
    monkeypatch.setattr(vision_speech,'_catalogue',(time.monotonic(),frozenset(['tr-TR-EmelNeural'])))
    monkeypatch.setattr(vision_speech.edge_tts,'Communicate',Communicate)
    monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False)
    response=TestClient(main.app).post('/api/mental/speech',json={'text':'Kişisel olmayan deneme.','cloudConsent':True})
    assert response.content==b'onetwo' and response.status_code==200
    assert calls==[('Kişisel olmayan deneme.','tr-TR-EmelNeural','-10%','-10Hz')] and closed==[True]

def test_missing_exact_voice_has_no_fallback_dispatch(monkeypatch,tmp_path):
    monkeypatch.setattr(vision_speech,'FIXED_BANK',tmp_path)
    monkeypatch.setattr(vision_speech,'_catalogue',(time.monotonic(),frozenset(['it-IT-IsabellaNeural'])))
    monkeypatch.setattr(vision_speech.edge_tts,'Communicate',lambda *_a,**_kw:(_ for _ in ()).throw(AssertionError('Fallback dispatch')))
    monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False)
    for route,text,voice in [('vision','right','tr-TR-AhmetNeural'),('mental','Deneme','tr-TR-EmelNeural')]:
        response=TestClient(main.app).post('/api/'+route+'/speech',json={'text':text,'cloudConsent':True})
        assert response.status_code==503 and response.json()['detail']=='EXACT_MICROSOFT_VOICE_UNAVAILABLE:'+voice
