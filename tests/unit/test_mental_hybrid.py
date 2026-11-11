"""Targeted hybrid regression. Provider/clock fixtures are not performance evidence."""
import os
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from mental_hybrid import candidate,personalize
from mental_structured import FlowState, content
from fastapi import HTTPException

@pytest.mark.parametrize('language,text',[('tr','Dün işimi kaybettim ve çok üzgünüm.'),('en','I lost my job and feel sad.'),('de','Ich habe meinen Job verloren und bin traurig.')])
def test_candidate_is_provisional_and_heard_question_advances_only_selected_state(language,text):
    before=FlowState(language=language); snapshot=before.model_dump()
    prepared=candidate(text,language,before)
    assert before.model_dump()==snapshot
    provider=SimpleNamespace(generate_reply=lambda *args:{'reply':'I hear you.','providerType':'LIVE_OPENAI'})
    personal=personalize(provider,text,[],prepared,before)
    assert before.model_dump()==snapshot and prepared['structuredState']['aHistory']
    assert personal['structuredState']['aHistory']==[]
    assert personal['structuredState']['selections'][-1].startswith('personal:')
    question=next(row['exactText'] for row in content()['rows'] if row['audioAssetId']==prepared['audioAssetIds'][-1])
    assert personal['reply'].endswith(question)
    selected=FlowState(**prepared['structuredState'])
    next_turn=candidate({'tr':'Her gün odaklanamıyorum.','en':'Every day I cannot concentrate.','de':'Jeden Tag kann ich mich nicht konzentrieren.'}[language],language,selected)
    assert selected.model_dump()==prepared['structuredState']
    assert next_turn['structuredState']['lastNode']!=selected.lastNode

@pytest.mark.parametrize('reply',['Another question?',' '.join(['word']*13),'# heading',''])
def test_invalid_personal_candidate_cannot_be_played(reply):
    prepared=candidate('I feel sad','en',FlowState(language='en'))
    with pytest.raises(HTTPException):personalize(SimpleNamespace(generate_reply=lambda *a:{'reply':reply,'providerType':'LIVE_OPENAI'}),'I feel sad',[],prepared,None)

def test_hybrid_api_safety_precedes_generation(monkeypatch):
    import main
    monkeypatch.setenv('ATTUNE_MENTAL_HYBRID_ENABLED','1')
    monkeypatch.setitem(main.vehicle_state,'vehicleMoving',True)
    with pytest.raises(HTTPException) as err:main.converse_mental_assistant(main.ConversePayload(userMessage='I feel tired',engine='hybrid-personal-v1'))
    assert err.value.status_code==409
    crisis=main.converse_mental_assistant(main.ConversePayload(userMessage='I want to kill myself',engine='hybrid-personal-v1'))
    assert crisis['isCrisis'] and crisis['providerType']=='CRISIS_SAFETY_GUARD'
    monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False)
    monkeypatch.setitem(main.vehicle_state,'vehicleParked',False)
    with pytest.raises(HTTPException):main.converse_mental_assistant(main.ConversePayload(userMessage='I feel tired',engine='hybrid-prepared-v1'))
    monkeypatch.setitem(main.vehicle_state,'vehicleParked',True)
    monkeypatch.setitem(main.vehicle_state,'driverAuthenticated',False)
    with pytest.raises(HTTPException):main.converse_mental_assistant(main.ConversePayload(userMessage='I feel tired',engine='hybrid-prepared-v1'))

@pytest.mark.parametrize('script',['mental_hybrid_race_runtime.cjs','mental_hybrid_lifecycle_runtime.cjs','mental_hybrid_audio_runtime.cjs'])
def test_hybrid_browser_runtime(script):
    subprocess.run(['node',str(ROOT/'tests/unit'/script)],cwd=ROOT,check=True,timeout=40)
