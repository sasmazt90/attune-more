"""Bounded German death-wish policy, real consumer parity and keyless API."""
import json
from pathlib import Path
import subprocess
import sys
import unicodedata

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import main
from mental_provider import check_mental_crisis
from mental_text_rules import german_crisis_context


CASES = [
    ('Ich wäre lieber tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wünschte, ich wäre tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wünschte ich wäre tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wünschte,ich wäre tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wäre am liebsten tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wäre gerne tot.', 'CURRENT_RISK_SIGNAL'),
    ('Gern wäre ich tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wäre jetzt lieber tot.', 'CURRENT_RISK_SIGNAL'),
    ('Am liebsten wäre ich tot.', 'CURRENT_RISK_SIGNAL'),
    ('Lieber wäre ich tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wünsche mir, ich wäre tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wünschte mir, ich wäre tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wünschte, dass ich tot wäre.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wünsche mir, tot zu sein.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wünschte, tot zu sein.', 'CURRENT_RISK_SIGNAL'),
    ('Ich möchte tot sein.', 'CURRENT_RISK_SIGNAL'),
    ('Ich will lieber tot sein.', 'CURRENT_RISK_SIGNAL'),
    ('Ich würde gerne tot sein.', 'CURRENT_RISK_SIGNAL'),
    ('Ich würde lieber tot sein.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wünschte, ich wäre lieber tot.', 'CURRENT_RISK_SIGNAL'),
    ('ICH WÄRE LIEBER TOT!', 'CURRENT_RISK_SIGNAL'),
    ('Ich waere lieber tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wuenschte, ich waere tot.', 'CURRENT_RISK_SIGNAL'),
    (unicodedata.normalize('NFD', 'Ich wünschte, ich wäre tot.'), 'CURRENT_RISK_SIGNAL'),
    ('Ich denke immer: „Ich wäre lieber tot“.', 'CURRENT_RISK_SIGNAL'),
    ('„Ich wäre lieber tot“ beschreibt, wie ich mich fühle.', 'CURRENT_RISK_SIGNAL'),
    ('„Ich wäre lieber tot“ ist in meinem Kopf.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wäre nicht lieber tot.', 'REASSURANCE'),
    ('Ich wäre lieber nicht tot.', 'REASSURANCE'),
    ('Ich wäre gerne nicht tot.', 'REASSURANCE'),
    ('Lieber wäre ich nicht tot.', 'REASSURANCE'),
    ('Ich wäre nicht mehr lieber tot.', 'REASSURANCE'),
    ('Ich wünsche mir nicht, ich wäre tot.', 'REASSURANCE'),
    ('Ich wünsche mir nicht mehr, tot zu sein.', 'REASSURANCE'),
    ('Ich wünschte, ich wäre nicht tot.', 'REASSURANCE'),
    ('Ich wünsche mir, dass ich nicht tot wäre.', 'REASSURANCE'),
    ('Ich wünschte, nicht tot zu sein.', 'REASSURANCE'),
    ('Ich möchte nicht tot sein.', 'REASSURANCE'),
    ('Ich würde nicht gerne tot sein.', 'REASSURANCE'),
    ('Ich würde gerne nicht tot sein.', 'REASSURANCE'),
    ('Ich würde nicht lieber tot sein.', 'REASSURANCE'),
    ('Ich wünsche mir nicht, ich wäre lieber tot.', 'REASSURANCE'),
    ('Früher wünschte ich, ich wäre tot.', 'HISTORICAL'),
    ('Damals wünschte ich mir, tot zu sein.', 'HISTORICAL'),
    ('Ich wünschte mir früher, ich wäre tot.', 'HISTORICAL'),
    ('Ich habe mir früher gewünscht, tot zu sein.', 'HISTORICAL'),
    ('Ich wäre früher lieber tot gewesen.', 'HISTORICAL'),
    ('Früher wäre ich lieber tot gewesen.', 'HISTORICAL'),
    ('Ich wäre lieber tot gewesen.', 'HISTORICAL'),
    ('Ich wünschte, ich wäre tot, als ich ein Kind war.', 'HISTORICAL'),
    ('Letztes Jahr dachte ich: Ich wäre lieber tot.', 'HISTORICAL'),
    ('Ich dachte früher: „Ich wünschte, ich wäre tot“.', 'HISTORICAL'),
    ('„Ich wäre lieber tot“', 'UNCERTAIN'),
    ('„Ich wünschte, ich wäre tot.“', 'UNCERTAIN'),
    ('"Ich wäre lieber tot."', 'UNCERTAIN'),
    ('Der Satz „Ich wäre lieber tot“ steht in einem Buch.', 'UNCERTAIN'),
    ('Was bedeutet „Ich wünschte, ich wäre tot“?', 'UNCERTAIN'),
    ('Mein Freund sagte: „Ich wäre lieber tot“.', 'UNCERTAIN'),
    ('Mein Freund sagte:„Ich wünschte,ich wäre tot“.', 'UNCERTAIN'),
    ('Mein Freund sagte: „Ich wünschte, ich wäre lieber tot“.', 'UNCERTAIN'),
    ('Meine Freundin sagte zu mir: „Ich wünschte, ich wäre tot“.', 'UNCERTAIN'),
    ('Er sagte, ich wäre lieber tot.', 'UNCERTAIN'),
    ('Ich las „Ich wäre lieber tot“ in einem Roman.', 'UNCERTAIN'),
    ('Ich habe nie gesagt: „Ich wäre lieber tot“.', 'UNCERTAIN'),
    ('In einem Buch steht: „Ich wäre lieber tot“.', 'UNCERTAIN'),
    ('„Ich wäre lieber tot“ ist ein Satz aus einem Film.', 'UNCERTAIN'),
    ('„Ich wünschte, ich wäre tot.“ stammt aus einem Buch.', 'UNCERTAIN'),
    ('Mein Freund wäre lieber tot.', 'UNCERTAIN'),
    ('Sie möchte tot sein.', 'UNCERTAIN'),
    ('Er wünscht sich, dass er tot wäre.', 'UNCERTAIN'),
    ('Ich glaube nicht: Ich wäre lieber tot.', 'UNCERTAIN'),
    ('Ich bin nicht sicher, ob ich lieber tot wäre.', 'UNCERTAIN'),
    ('Ich wäre nicht lieber tot, falls ich meinen Job behalte.', 'UNCERTAIN'),
    ('Ich wäre lieber zu Hause.', 'NONE'),
    ('Ich wäre lieber total entspannt.', 'NONE'),
    ('Ich wünschte, ich wäre im Urlaub.', 'NONE'),
    ('Ein Totem ist kein Wunsch.', 'NONE'),
    ('Ich wäre nicht lieber tot, aber ich wünschte, ich wäre tot.', 'CURRENT_RISK_SIGNAL'),
    ('Früher wünschte ich, ich wäre tot, aber ich wäre jetzt lieber tot.', 'CURRENT_RISK_SIGNAL'),
    ('Der Satz „Ich wäre lieber tot“ ist ein Zitat, aber ich möchte sterben.', 'CURRENT_RISK_SIGNAL'),
    ('Mein Freund sagte: „Ich wäre lieber tot“, aber ich wünschte, ich wäre tot.', 'CURRENT_RISK_SIGNAL'),
    ('Ich möchte sterben, aber der Satz „Ich wäre lieber tot“ ist ein Zitat.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wäre lieber tot gewesen, aber ich wäre jetzt lieber tot.', 'CURRENT_RISK_SIGNAL'),
    ('„Ich wäre lieber tot“ ist ein Satz aus einem Film, aber ich will tot sein.', 'CURRENT_RISK_SIGNAL'),
    ('Ich wäre nicht lieber tot, und ich fühle mich immer noch so.', 'CONTINUING_RISK_SIGNAL'),
]


def expected_risk(context):
    return context in ('CURRENT_RISK_SIGNAL', 'CONTINUING_RISK_SIGNAL')


@pytest.mark.parametrize('text,context', CASES)
def test_german_death_wish_context_and_existing_routing(text, context):
    assert german_crisis_context(text) == {'signal': expected_risk(context), 'context': context}
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
    console.log(JSON.stringify(JSON.parse(process.argv[1]).map(text=>({context:d.germanCrisisContext(text),park:d.checkCrisisTrigger(text),moving:d.checkCrisisTrigger(text,true)}))));"""
    result = subprocess.run(['node', '-e', script, json.dumps([text for text, _ in CASES])],
                            cwd=ROOT, capture_output=True, text=True, timeout=25, check=True)
    for (text, context), observed in zip(CASES, json.loads(result.stdout), strict=True):
        assert observed['context'] == german_crisis_context(text)
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
        response = client.post('/api/mental/converse?language=de', json={'userMessage': text, 'cloudConsent': False})
    assert response.status_code == 200 and response.headers['content-language'] == 'de-DE'
    result = response.json()
    assert bool(result.get('isCrisis')) is expected_risk(context)
    assert result['providerType'] == ('CRISIS_SAFETY_GUARD' if expected_risk(context) else 'LOCAL_DEMO')
    if expected_risk(context):
        assert '112' in result['reply'] and '182' not in result['reply']
        assert result['riskLevel'] == 'IMMINENT' and '112' in result['emergencyContact']
