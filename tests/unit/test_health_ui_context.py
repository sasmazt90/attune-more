import sys,json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
import mental_context as context
from main import ConversePayload,AnalyzeSessionPayload,CompactContextPayload,compact_mental_context,vehicle_state
from pydantic import ValidationError
from fastapi import HTTPException

def client(quotes):
    def create(**kw):
        assert kw['temperature']==0 and kw['max_tokens']==3000
        return NS(choices=[NS(message=NS(content=json.dumps({'quotes':quotes})))])
    return NS(chat=NS(completions=NS(create=create)))

def test_extractive_memory_retains_prior_and_correction(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','noncredential-test')
    monkeypatch.setattr(context,'get_openai_client',lambda *_:client(['Düzeltme: salı günü.','Önceki yer mavi oda.']))
    value=context.compact_context(['Önceki yer mavi oda.'],[{'role':'user','content':'Düzeltme: salı günü.'},{'role':'assistant','content':'Uydurulmuş yer yeşil oda.'}])
    assert value['memory']==['Önceki yer mavi oda.','Düzeltme: salı günü.']

@pytest.mark.parametrize('quotes',[['Uydurulmuş yer yeşil oda.'],[],['x'*2001]])
def test_uncited_or_empty_or_large_memory_fails_without_mutation(monkeypatch,quotes):
    monkeypatch.setenv('OPENAI_API_KEY','noncredential-test');monkeypatch.setattr(context,'get_openai_client',lambda *_:client(quotes))
    previous=['Gerçek önceki bilgi.']
    with pytest.raises(HTTPException):context.compact_context(previous,[{'role':'assistant','content':'Uydurulmuş yer yeşil oda.'}])
    assert previous==['Gerçek önceki bilgi.']

def test_context_requires_cloud_and_park():
    with pytest.raises(HTTPException) as e:compact_mental_context(CompactContextPayload(messages=[],cloudConsent=False))
    assert e.value.status_code==403
    old=vehicle_state['vehicleMoving'];vehicle_state['vehicleMoving']=True
    try:
        with pytest.raises(HTTPException) as e:compact_mental_context(CompactContextPayload(messages=[],cloudConsent=True))
        assert e.value.status_code==409
    finally:vehicle_state['vehicleMoving']=old

@pytest.mark.parametrize('value',[['x'*2001],['x']*33,['x'*1000]*17])
def test_memory_bounds(value):
    with pytest.raises(ValidationError):ConversePayload(userMessage='test',memory=value)

def test_recent_and_final_limits_stay_bounded():
    with pytest.raises(ValidationError):ConversePayload(userMessage='test',history=[{'role':'user','content':'a'},{'role':'assistant','content':'b'}]*21)
    with pytest.raises(ValidationError):AnalyzeSessionPayload(messages=[{'role':'user','content':'a'}]*201)
    assert AnalyzeSessionPayload(messages=[{'role':'user','content':'a'}],memory=['eski kullanıcı alıntısı']).memory

def test_memory_not_persisted_or_shared_between_provider_instances(monkeypatch):
    from mental_provider import get_active_mental_provider
    monkeypatch.setenv('OPENAI_API_KEY','noncredential-test')
    first=get_active_mental_provider();first.session_memory=['geçici']
    assert not hasattr(get_active_mental_provider(),'session_memory')

def test_provider_receives_memory_as_separate_context(monkeypatch):
    import mental_provider
    calls=[]
    def create(**kw):calls.append(kw);return NS(choices=[NS(message=NS(content='Kısa yanıt.'))])
    monkeypatch.setattr(mental_provider,'get_openai_client',lambda *_:NS(chat=NS(completions=NS(create=create))))
    p=mental_provider.OpenAICompatibleMentalProvider('noncredential-test');p.session_memory=['Mavi oda.']
    p.generate_reply('Son düzeltme.',False,[])
    assert 'Mavi oda.' in calls[0]['messages'][1]['content'] and calls[0]['messages'][-1]['content']=='Son düzeltme.'
