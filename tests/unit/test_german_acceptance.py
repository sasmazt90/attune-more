"""Requested synthetic transcripts: actual API/TS rules, never microphone or live AI proof."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
import main
from conversation_control import conversation_control
from mental_provider import check_mental_crisis

SCENARIOS={
 'stress':'Ich hatte heute einen stressigen Arbeitstag und möchte kurz darüber sprechen.',
 'fatigue':'Ich bin heute müde und kann mich nicht besonders gut konzentrieren.',
 'finish':'Ich möchte das Gespräch jetzt beenden.',
 'safety':'Ich fühle mich gerade nicht sicher und brauche dringend Hilfe.',
}

@pytest.mark.parametrize('case',SCENARIOS)
def test_requested_german_transcript_scenarios(monkeypatch,case):
    monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False)
    monkeypatch.setattr(main,'get_active_mental_provider',lambda:(_ for _ in ()).throw(AssertionError('No live provider permitted')))
    with TestClient(main.app) as client:
        response=client.post('/api/mental/converse?language=de',json={'userMessage':SCENARIOS[case],'cloudConsent':False})
    assert response.status_code==200
    data=response.json();assert response.headers['content-language']=='de-DE'
    assert 'Sizi dinliyorum' not in data['reply'] and 'I am listening' not in data['reply']
    # Themes are stable wire/storage keys; German labels translate at display time.
    if case=='stress':assert data['providerType']=='LOCAL_DEMO' and 'iş stresi' in data['detectedThemes']
    if case=='fatigue':assert data['providerType']=='LOCAL_DEMO' and 'fiziksel yorgunluk' in data['detectedThemes']
    if case=='finish':assert data['providerType']=='CONVERSATION_CONTROL' and data['sessionAction']=='finish' and 'beende' in data['reply'].lower()
    if case=='safety':
        assert data['providerType']=='CRISIS_SAFETY_GUARD' and data['isCrisis'] is True
        assert data['riskLevel']=='URGENT_SAFETY' and '112' in data['reply'] and '182' not in data['reply']
        assert 'ich habe angerufen' not in data['reply'].lower()

@pytest.mark.parametrize('text',[
 'Ich bin nicht sicher, ob ich heute darüber sprechen möchte.',
 'Ich fühle mich sicher und brauche keine dringende Hilfe.',
 'I do not feel safe using this app.',
 'Kendimi güvende hissetmiyorum ama acil yardım istemiyorum.',
])
def test_uncertainty_and_negated_urgent_help_are_not_emergency(text):
    # Negation of an urgent-help request must not satisfy the paired rule.
    assert check_mental_crisis(text,False)['isCrisis'] is False

def test_urgent_safety_is_not_a_self_harm_diagnosis_and_driving_wording_stays_safe():
    result=check_mental_crisis(SCENARIOS['safety'],True)
    assert result['isCrisis'] and result['selfHarmSignal'] is False
    assert result['drivingModeResponse'] and '112' in result['reply'] and 'ekrana bakmayın' in result['reply']
    combined=check_mental_crisis(SCENARIOS['safety']+' Ich will sterben.',False)
    assert combined['selfHarmSignal'] is True and combined['riskLevel']=='IMMINENT'
    assert conversation_control('Ich möchte das Gespräch jetzt nicht beenden.') is None
    assert conversation_control('Ich bin unsicher, ob ich das Gespräch beenden möchte.') is None

def test_frontend_and_backend_urgent_safety_rules_agree():
    texts=[SCENARIOS['safety'],'Ich bin nicht sicher, ob ich das möchte.','Ich fühle mich sicher und brauche keine dringende Hilfe.']
    script="""require('./tests/unit/ts_loader.js');const {checkCrisisTrigger}=require('./packages/safety/crisisDetector.ts');console.log(JSON.stringify(JSON.parse(process.argv[1]).map(t=>checkCrisisTrigger(t).isCrisis)));"""
    result=subprocess.run(['node','-e',script,json.dumps(texts)],cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout)==[check_mental_crisis(text,False)['isCrisis'] for text in texts]

def test_actual_frontend_crisis_precedes_unavailable_context():
    result=subprocess.run(['node','tests/unit/mental_crisis_priority.cjs'],cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
