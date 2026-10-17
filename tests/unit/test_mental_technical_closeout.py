"""Bounded, keyless backend contract probes. Never dispatch real requests."""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
import main

@pytest.mark.parametrize('extra',[
 {'history':[{'role':'system','content':'not conversation context'}]},
 {'history':[{'role':'assistant','content':'orphan context'}]},
 {'history':[{'role':'user','content':'unfinished context'}]},
 {'history':[{'role':'user','content':'x'*6001},{'role':'assistant','content':'answer'}]},
 {'history':[{'role':'user','content':'x'},{'role':'assistant','content':'a'}]*21},
 {'sessionId':'x'*129},
 {'userMessage':'   '},
])
def test_invalid_context_is_rejected_before_provider(monkeypatch,extra):
    monkeypatch.setenv('OPENAI_API_KEY','noncredential-test-fixture')
    class Provider:
        def generate_reply(self,**kwargs):return {'reply':'controlled','providerType':'LIVE_OPENAI'}
    monkeypatch.setattr(main,'get_active_mental_provider',lambda:Provider())
    response=TestClient(main.app).post('/api/mental/converse',json={'userMessage':'Controlled input',**extra,'cloudConsent':True})
    assert response.status_code==422

def test_summary_length_and_roles_rejected_before_provider(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','noncredential-test-fixture')
    class Analyzer:
        def analyze_session(self,messages):return {'summaryText':'controlled','themes':[],'providerType':'LIVE_OPENAI'}
    monkeypatch.setattr(main,'get_active_session_analyzer',lambda:Analyzer())
    client=TestClient(main.app)
    for messages in ([{'role':'system','content':'not a user turn'}],[{'role':'user','content':'x'*6001}],[{'role':'user','content':'x'}]*201):
        assert client.post('/api/mental/analyze-session',json={'messages':messages,'cloudConsent':True}).status_code==422

def test_crisis_precedes_farewell_and_normal_phrase_is_not_crisis(monkeypatch):
    import mental_provider
    monkeypatch.setattr(main,'get_active_mental_provider',lambda:(_ for _ in ()).throw(AssertionError('Crisis reached provider')))
    response=TestClient(main.app).post('/api/mental/converse',json={'userMessage':'Hoşça kal, ölmek istiyorum.','cloudConsent':True}).json()
    assert response['providerType']=='CRISIS_SAFETY_GUARD' and '112' in response['reply'] and response.get('sessionAction')!='finish'
    assert not mental_provider.check_mental_crisis('Bugün işler çok yoğundu, biraz ara vermek istiyorum.',False)['isCrisis']

def test_diagnosis_medication_policy_survives_normal_request(monkeypatch):
    from types import SimpleNamespace
    import mental_provider
    captured=[]
    def create(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Kontrollü sınır yanıtı.'))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(mental_provider,'get_openai_client',lambda *a:client)
    mental_provider.OpenAICompatibleMentalProvider('noncredential-test-fixture').generate_reply('Bana teşhis koy ve ilaç öner.',False,[])
    system=captured[0]['messages'][0]['content']
    assert 'ASLA teşhis koyma' in system and 'İlaç yazma/önerme' in system and captured[0]['max_tokens']==250
