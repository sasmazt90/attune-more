"""Bounded death-wish grammar, production consumer parity and keyless routing."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import main
from mental_provider import check_mental_crisis
from mental_text_rules import english_crisis_context


CASES = [
    ('I wish I were dead.', 'CURRENT_RISK_SIGNAL'),
    ('I wish I was dead.', 'CURRENT_RISK_SIGNAL'),
    ("I'd rather be dead.", 'CURRENT_RISK_SIGNAL'),
    ('I would rather be dead.', 'CURRENT_RISK_SIGNAL'),
    ('I’d rather be dead.', 'CURRENT_RISK_SIGNAL'),
    ('I WISH I WERE DEAD!', 'CURRENT_RISK_SIGNAL'),
    ('I wish I were dead right now.', 'CURRENT_RISK_SIGNAL'),
    ('I keep thinking "I wish I were dead".', 'CURRENT_RISK_SIGNAL'),
    ("I feel like I'd rather be dead.", 'CURRENT_RISK_SIGNAL'),
    ("I don't wish I were dead.", 'REASSURANCE'),
    ('I do not wish I was dead.', 'REASSURANCE'),
    ('I never wish I were dead.', 'REASSURANCE'),
    ('I no longer wish I was dead.', 'REASSURANCE'),
    ("I wouldn't rather be dead.", 'REASSURANCE'),
    ('I would not rather be dead.', 'REASSURANCE'),
    ("I'd rather not be dead.", 'REASSURANCE'),
    ('I would rather not be dead.', 'REASSURANCE'),
    ('I used to wish I were dead.', 'HISTORICAL'),
    ('I wished I was dead years ago.', 'HISTORICAL'),
    ("I used to think I'd rather be dead.", 'HISTORICAL'),
    ('I used to feel that I would rather be dead.', 'HISTORICAL'),
    ("I thought I'd rather be dead last year.", 'HISTORICAL'),
    ('I used to say "I wish I were dead".', 'HISTORICAL'),
    ('The phrase "I wish I were dead" appears in a book.', 'UNCERTAIN'),
    ('The sentence “I wish I was dead” is quoted here.', 'UNCERTAIN'),
    ('My friend said "I wish I were dead".', 'UNCERTAIN'),
    ("She said, 'I'd rather be dead'.", 'UNCERTAIN'),
    ('He says I wish I was dead.', 'UNCERTAIN'),
    ("I read \"I'd rather be dead\" in a novel.", 'UNCERTAIN'),
    ('"I wish I were dead"', 'UNCERTAIN'),
    ('"I wish I were dead."', 'UNCERTAIN'),
    ('“I wish I was dead.”', 'UNCERTAIN'),
    ("'I'd rather be dead'", 'UNCERTAIN'),
    ('What does "I wish I were dead" mean?', 'UNCERTAIN'),
    ('I never said "I wish I was dead".', 'UNCERTAIN'),
    ("I don't think I wish I were dead.", 'UNCERTAIN'),
    ('I do not believe I would rather be dead.', 'UNCERTAIN'),
    ("I no longer think I'd rather be dead.", 'UNCERTAIN'),
    ("I don't wish I were dead unless I lose my job.", 'UNCERTAIN'),
    ("My friend would rather be dead.", 'UNCERTAIN'),
    ('You wish I were dead.', 'UNCERTAIN'),
    ('She wishes she was dead.', 'NONE'),
    ('I wish I were at home.', 'NONE'),
    ('I would rather be asleep.', 'NONE'),
    ('An unrelated deathwishword is not a disclosure.', 'NONE'),
    ("I don't wish I were dead, but I wish I was dead now.", 'CURRENT_RISK_SIGNAL'),
    ('I used to wish I were dead, but I would rather be dead now.', 'CURRENT_RISK_SIGNAL'),
    ('I used to say "I wish I were dead", but I wish I was dead now.', 'CURRENT_RISK_SIGNAL'),
    ('The phrase "I wish I were dead" is quoted, but I want to die.', 'CURRENT_RISK_SIGNAL'),
    ('My friend said "I wish I were dead", but I wish I was dead.', 'CURRENT_RISK_SIGNAL'),
    ('I want to die, but the phrase "I wish I were dead" is quoted.', 'CURRENT_RISK_SIGNAL'),
    ('The phrase "I wish I were dead" and the phrase "I wish I was dead" are quotes; I might hurt myself.', 'CURRENT_RISK_SIGNAL'),
    ("I no longer wish I were dead, but I still do.", 'CONTINUING_RISK_SIGNAL'),
]


def expected_risk(context):
    return context in ('CURRENT_RISK_SIGNAL', 'CONTINUING_RISK_SIGNAL')


@pytest.mark.parametrize('text,context', CASES)
def test_death_wish_context_and_existing_routing(text, context):
    assert english_crisis_context(text) == {'signal': expected_risk(context), 'context': context}
    for moving in (False, True):
        result = check_mental_crisis(text, moving)
        assert result['isCrisis'] is expected_risk(context)
        assert result['needsEmergencyEscalation'] is expected_risk(context)
        if expected_risk(context):
            assert '112' in result['reply'] and '182' not in result['reply']
            assert not moving or 'ekrana bakmayın' in result['reply']
        else:
            assert result['riskLevel'] == ('UNCERTAIN' if context in ('HISTORICAL', 'UNCERTAIN') else 'NONE')


def test_actual_frontend_backend_parity():
    script = """require('./tests/unit/ts_loader.js');
    const d=require('./packages/safety/crisisDetector.ts');
    console.log(JSON.stringify(JSON.parse(process.argv[1]).map(text=>({context:d.englishCrisisContext(text),park:d.checkCrisisTrigger(text),moving:d.checkCrisisTrigger(text,true)}))));"""
    result = subprocess.run(['node', '-e', script, json.dumps([text for text, _ in CASES])],
                            cwd=ROOT, capture_output=True, text=True, timeout=25, check=True)
    for (text, context), observed in zip(CASES, json.loads(result.stdout), strict=True):
        assert observed['context'] == english_crisis_context(text)
        for mode in ('park', 'moving'):
            assert observed[mode]['isCrisis'] is expected_risk(context)
            if expected_risk(context):
                assert '112' in observed[mode]['emergencyResponseTr']
                assert mode != 'moving' or 'ekrana bakmayın' in observed[mode]['emergencyResponseTr']
            else:
                assert observed[mode]['riskLevel'] == check_mental_crisis(text, mode == 'moving')['riskLevel']


@pytest.mark.parametrize('text,context', CASES)
def test_actual_keyless_api_never_calls_live_provider(monkeypatch, text, context):
    monkeypatch.setitem(main.vehicle_state, 'vehicleMoving', False)
    monkeypatch.setattr(main, 'get_active_mental_provider', lambda: pytest.fail('No live provider permitted'))
    with TestClient(main.app) as client:
        response = client.post('/api/mental/converse?language=en', json={'userMessage': text, 'cloudConsent': False})
    assert response.status_code == 200 and response.headers['content-language'] == 'en-US'
    result = response.json()
    assert bool(result.get('isCrisis')) is expected_risk(context)
    assert result['providerType'] == ('CRISIS_SAFETY_GUARD' if expected_risk(context) else 'LOCAL_DEMO')
    if expected_risk(context):
        assert '112' in result['reply'] and '182' not in result['reply']
        assert result['riskLevel'] == 'IMMINENT' and '112' in result['emergencyContact']
