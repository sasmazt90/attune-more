"""P1/P2 actual source/response contracts. All provider output is a labelled fixture."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unicodedata
from unittest.mock import Mock
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import mental_provider
from mental_provider import check_mental_crisis
from mental_text_rules import english_crisis_context, german_crisis_context, professional_support_suggested
from localization import request_language
from fastapi.testclient import TestClient
import main

CASES = [
    ("I don't want to die.", False, 'REASSURANCE'),
    ('I am no longer suicidal.', False, 'REASSURANCE'),
    ('I want to die.', True, 'CURRENT_RISK_SIGNAL'),
    ('I feel suicidal.', True, 'CURRENT_RISK_SIGNAL'),
    ("I don't want to live anymore.", True, 'CURRENT_RISK_SIGNAL'),
    ("I used to feel suicidal, but I don't anymore.", False, 'HISTORICAL'),
    ("I don't want to die, but I'm afraid I might hurt myself.", True, 'CURRENT_RISK_SIGNAL'),
    ("I'm not suicidal.", False, 'REASSURANCE'),
    ('I’m no longer suicidal.', False, 'REASSURANCE'),
    ("I don't think I am suicidal.", False, 'UNCERTAIN'),
    ("I'm not sure whether I'm suicidal.", False, 'UNCERTAIN'),
    ('I read an article about suicide.', False, 'UNCERTAIN'),
    ('The word suicidal worries me.', False, 'UNCERTAIN'),
    ('I used to feel suicidal, and I still do.', True, 'CONTINUING_RISK_SIGNAL'),
    ("I am no longer suicidal, but I want to die tonight.", True, 'CURRENT_RISK_SIGNAL'),
    ("I do not want to die. I might hurt myself.", True, 'CURRENT_RISK_SIGNAL'),
    ("I don't want to die, and I am not safe and need urgent help.", True, 'REASSURANCE'),
    ('I have suicidal thoughts.', True, 'CURRENT_RISK_SIGNAL'),
    ('I have thoughts of suicide.', True, 'CURRENT_RISK_SIGNAL'),
    ('I am having thoughts about suicide.', True, 'CURRENT_RISK_SIGNAL'),
    ('I have no thoughts of suicide.', False, 'REASSURANCE'),
    ("I don't have any thoughts about suicide.", False, 'REASSURANCE'),
    ('I used to have thoughts of suicide.', False, 'HISTORICAL'),
    ('I am not sure whether I have thoughts of suicide.', False, 'UNCERTAIN'),
    ('I have no thoughts of suicide, but I want to die.', True, 'CURRENT_RISK_SIGNAL'),
    ('I am thinking about suicide.', True, 'CURRENT_RISK_SIGNAL'),
    ('I am not thinking about suicide.', False, 'REASSURANCE'),
    ("I won't hurt myself.", False, 'REASSURANCE'),
    ("I won't hurt myself unless I lose my job.", False, 'UNCERTAIN'),
    ("I am not trying to kill myself.", False, 'REASSURANCE'),
    ("I won't kill myself, but I feel suicidal.", True, 'CURRENT_RISK_SIGNAL'),
    ('I never want to live again.', True, 'CURRENT_RISK_SIGNAL'),
    ('I will commit suicide.', True, 'CURRENT_RISK_SIGNAL'),
    ('I have a suicide plan.', True, 'CURRENT_RISK_SIGNAL'),
    ('I have a plan for suicide.', True, 'CURRENT_RISK_SIGNAL'),
    ('I am planning my suicide.', True, 'CURRENT_RISK_SIGNAL'),
    ('I am not planning my suicide.', False, 'REASSURANCE'),
    ("I'm no longer seriously considering suicide.", False, 'REASSURANCE'),
    ('I have no suicide plan.', False, 'UNCERTAIN'),
    ('I do not have a suicide plan.', False, 'UNCERTAIN'),
    ('Suicide is my only option.', True, 'CURRENT_RISK_SIGNAL'),
    ("I don't believe suicide is my only option.", False, 'UNCERTAIN'),
    ('I am writing a suicide note.', True, 'CURRENT_RISK_SIGNAL'),
    ('My suicide plan is ready.', True, 'CURRENT_RISK_SIGNAL'),
    ('My suicide plan is finalized.', True, 'CURRENT_RISK_SIGNAL'),
    ('My suicide note is in my hand.', True, 'CURRENT_RISK_SIGNAL'),
    ("My suicide plan doesn't exist.", False, 'REASSURANCE'),
    ('The title "My suicide note" is in a story.', False, 'UNCERTAIN'),
    ('My suicide note is finished.', True, 'CURRENT_RISK_SIGNAL'),
    ("My suicide plan's ready.", True, 'CURRENT_RISK_SIGNAL'),
    ('I finished my suicide note.', True, 'CURRENT_RISK_SIGNAL'),
    ('I have prepared my suicide plan.', True, 'CURRENT_RISK_SIGNAL'),
    ('My suicide note is being written.', True, 'CURRENT_RISK_SIGNAL'),
    ('My suicide note is not finished yet.', True, 'CURRENT_RISK_SIGNAL'),
    ('My suicide plan is no longer active.', False, 'REASSURANCE'),
    ('My suicide plan is abandoned.', False, 'REASSURANCE'),
    ('My suicide note is from years ago.', False, 'HISTORICAL'),
    ('I found my suicide note from years ago.', False, 'HISTORICAL'),
    ('My suicide plan was abandoned years ago.', False, 'HISTORICAL'),
    ('My suicide plan is no longer active, but I want to die.', True, 'CURRENT_RISK_SIGNAL'),
    ('My suicide plan is no longer active unless I lose my job.', False, 'UNCERTAIN'),
    ('An unrelated presuicidalword is not a self-report.', False, 'NONE'),
    ('Ich fühle mich gerade nicht sicher und brauche dringend Hilfe.', True, 'NONE'),
    ('Ich will sterben.', True, 'NONE'),
    ('Ich möchte das Gespräch jetzt beenden.', False, 'NONE'),
    ('Ich bin nicht sicher, ob ich darüber sprechen möchte.', False, 'NONE'),
    ('İNTİHAR', True, 'NONE'),
    ('INTIHAR', True, 'NONE'),
    (unicodedata.normalize('NFD', 'YAŞAMAK İSTEMİYORUM'), True, 'NONE'),
    ('Güvende değilim ve acil yardıma ihtiyacım var.', True, 'NONE'),
    ('Bugün kendimi iyi hissediyorum.', False, 'NONE'),
]


@pytest.mark.parametrize('text,crisis,context', CASES)
def test_contextual_crisis_classification(text, crisis, context):
    assert english_crisis_context(text)['context'] == context
    for driving in (False, True):
        result = check_mental_crisis(text, driving)
        assert result['isCrisis'] is crisis
        assert result['needsEmergencyEscalation'] is crisis
        if crisis:
            assert '112' in result['reply'] and '182' not in result['reply']
            assert not driving or 'ekrana bakmayın' in result['reply']
        else:
            assert result['riskLevel'] == ('UNCERTAIN' if context in ('HISTORICAL', 'UNCERTAIN') else 'NONE')
            assert result['selfHarmSignal'] is False


def test_all_contexts_match_actual_frontend_including_remaining_danger():
    script = """require('./tests/unit/ts_loader.js');
    const {checkCrisisTrigger,englishCrisisContext}=require('./packages/safety/crisisDetector.ts');
    console.log(JSON.stringify(JSON.parse(process.argv[1]).map(text=>({english:englishCrisisContext(text),park:checkCrisisTrigger(text),moving:checkCrisisTrigger(text,true)}))));"""
    result = subprocess.run(['node', '-e', script, json.dumps([c[0] for c in CASES])], cwd=ROOT,
                            text=True, capture_output=True, timeout=20, check=True)
    for case, observed in zip(CASES, json.loads(result.stdout), strict=True):
        text, crisis, _ = case
        assert observed['english'] == english_crisis_context(text)
        for key in ('park', 'moving'):
            assert observed[key]['isCrisis'] is crisis
            if crisis:
                assert '112' in observed[key]['emergencyResponseTr']
            else:
                assert observed[key]['riskLevel'] == check_mental_crisis(text, key == 'moving')['riskLevel']


@pytest.mark.parametrize('text,crisis,context', [c for c in CASES if c in CASES[:7] or c[0] in ('I have thoughts of suicide.','I am having thoughts about suicide.','I have no thoughts of suicide.','I have no thoughts of suicide, but I want to die.','My suicide plan is ready.','My suicide note is finished.','My suicide plan is no longer active.','My suicide plan is no longer active, but I want to die.')])
def test_requested_english_transcripts_through_actual_keyless_api(monkeypatch, text, crisis, context):
    monkeypatch.setitem(main.vehicle_state, 'vehicleMoving', False)
    monkeypatch.setattr(main, 'get_active_mental_provider', lambda: (_ for _ in ()).throw(AssertionError('No live provider permitted')))
    with TestClient(main.app) as client:
        response = client.post('/api/mental/converse?language=en', json={'userMessage': text, 'cloudConsent': False})
    assert response.status_code == 200 and response.headers['content-language'] == 'en-US'
    result = response.json()
    assert bool(result.get('isCrisis')) is crisis
    assert (result['providerType'] == 'CRISIS_SAFETY_GUARD') is crisis
    if crisis:
        assert '112' in result['reply'] and '182' not in result['reply']
    else:
        assert result['providerType'] == 'LOCAL_DEMO'


GERMAN = [
    ('Ich bin nicht suizidal.', False, 'REASSURANCE'),
    ('Ich möchte sterben.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich will sterben.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich möchte nicht sterben.', False, 'REASSURANCE'),
    ('Ich möchte nicht mehr leben.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich bin suizidal.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich habe Suizidgedanken.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich habe Selbstmordgedanken.', True, 'CURRENT_RISK_SIGNAL'),
    ('ICH HABE SELBSTMORDGEDANKEN.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich habe Suizidpläne.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich habe Selbstmordpläne.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich habe keine Selbstmordgedanken.', False, 'REASSURANCE'),
    ('Ich habe keine Suizidgedanken mehr.', False, 'REASSURANCE'),
    ('Früher hatte ich Selbstmordgedanken.', False, 'HISTORICAL'),
    ('Ich habe keine Selbstmordgedanken, aber ich möchte sterben.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich plane Suizid.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich möchte mich umbringen.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich habe vor, mich umzubringen.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich habe nicht vor, mich umzubringen.', False, 'REASSURANCE'),
    ('Ich bin nicht mehr suizidal, aber ich möchte sterben.', True, 'CURRENT_RISK_SIGNAL'),
    ('Früher war ich suizidal, aber jetzt nicht mehr.', False, 'HISTORICAL'),
    ('Früher war ich suizidal, und ich bin es noch.', True, 'CONTINUING_RISK_SIGNAL'),
    ('Ich weiß nicht, ob ich suizidal bin.', False, 'UNCERTAIN'),
    ('Das Wort Suizid steht im Wörterbuch.', False, 'UNCERTAIN'),
    ('Mein Suizidplan ist fertig.', True, 'CURRENT_RISK_SIGNAL'),
    ('Mein Suizidplan existiert nicht.', False, 'REASSURANCE'),
    ('Der Titel "Mein Suizidplan" steht in einem Roman.', False, 'UNCERTAIN'),
    ('Mein Suizidplan ist bereit.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich habe meinen Suizidplan vorbereitet.', True, 'CURRENT_RISK_SIGNAL'),
    ('Mein Suizidplan ist nicht mehr aktiv.', False, 'REASSURANCE'),
    ('Mein Suizidplan ist von vor Jahren.', False, 'HISTORICAL'),
    ('Mein Suizidplan ist nicht mehr aktiv, aber ich möchte sterben.', True, 'CURRENT_RISK_SIGNAL'),
    ('Mein Suizidplan ist nicht mehr aktiv, falls ich meinen Job behalte.', False, 'UNCERTAIN'),
    ('Ich möchte leben.', False, 'NONE'),
    ('Ich werde Selbstmord begehen.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich möchte Suizid begehen.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich denke über Selbstmord nach.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich habe einen Plan für Suizid.', True, 'CURRENT_RISK_SIGNAL'),
    ('Ich werde keinen Selbstmord begehen.', False, 'REASSURANCE'),
    ('Ich werde Selbstmord nicht begehen.', False, 'REASSURANCE'),
    ('Ich denke nicht über Suizid nach.', False, 'REASSURANCE'),
    ('Ich fühle mich gerade nicht sicher und brauche dringend Hilfe.', True, 'NONE'),
]


@pytest.mark.parametrize('text,crisis,context', GERMAN)
def test_german_context_and_actual_api(monkeypatch, text, crisis, context):
    assert german_crisis_context(text)['context'] == context
    assert check_mental_crisis(text, False)['isCrisis'] is crisis
    assert check_mental_crisis(text, True)['isCrisis'] is crisis
    monkeypatch.setitem(main.vehicle_state, 'vehicleMoving', False)
    with TestClient(main.app) as client:
        result = client.post('/api/mental/converse?language=de', json={'userMessage': text, 'cloudConsent': False})
    assert result.status_code == 200 and result.headers['content-language'] == 'de-DE'
    assert (result.json()['providerType'] == 'CRISIS_SAFETY_GUARD') is crisis
    if crisis:
        assert '112' in result.json()['reply']


def test_german_shared_frontend_backend_rule_parity():
    script = """require('./tests/unit/ts_loader.js');const d=require('./packages/safety/crisisDetector.ts');console.log(JSON.stringify(JSON.parse(process.argv[1]).map(text=>({context:d.germanCrisisContext(text),result:d.checkCrisisTrigger(text)}))));"""
    result = subprocess.run(['node','-e',script,json.dumps([r[0] for r in GERMAN])],cwd=ROOT,text=True,capture_output=True,timeout=20,check=True)
    for case, observed in zip(GERMAN,json.loads(result.stdout),strict=True):
        assert observed['context']==german_crisis_context(case[0])
        assert observed['result']['isCrisis'] is case[1]


SUPPORT = [
    ('en', 'I recommend speaking with a psychologist.', True),
    ('en', 'You could consider psychological support.', True),
    ('en', 'Talk to a psychologist.', True),
    ('en', 'Psychological help may be beneficial.', True),
    ('en', "I don't recommend a psychologist.", False),
    ('en', "A psychologist isn't needed.", False),
    ('en', 'You do not need psychological support.', False),
    ('en', 'Do not seek psychological support.', False),
    ('en', "I wouldn't recommend a psychologist.", False),
    ('en', 'Psychological support will not help.', False),
    ('en', 'I am not a psychologist.', False),
    ('en', 'The word psychologist is a noun.', False),
    ('en', 'A psychologist could be your neighbour.', False),
    ('en', 'What did the psychologist suggest?', False),
    ('en', 'You said "consider a psychologist"; I am quoting your words.', False),
    ('en', "You said 'I suggest psychological support'.", False),
    ('en', "I am not a psychologist, but psychological support could help.", True),
    ('de', 'Ich empfehle einen Psychologen.', True),
    ('de', 'Sie könnten eine Psychologin aufsuchen.', True),
    ('de', 'Psychologische Unterstützung könnte hilfreich sein.', True),
    ('de', 'Eine Psychologin wäre sinnvoll.', True),
    ('de', 'Ich empfehle keinen Psychologen.', False),
    ('de', 'Psychologische Unterstützung ist nicht notwendig.', False),
    ('de', 'Ich bin keine Psychologin.', False),
    ('de', 'Das Wort Psychologe steht im Wörterbuch.', False),
    ('de', 'Ein Psychologe könnte Ihr Nachbar sein.', False),
    ('de', 'Was würde die Psychologin empfehlen?', False),
    ('de', 'Sie sagten “Eine Psychologin wäre hilfreich”.', False),
    ('de', 'Ich bin keine Psychologin, aber psychologische Unterstützung könnte helfen.', True),
    ('tr', 'Bir psikologla görüşmek faydalı olabilir.', True),
    ('tr', 'Psikolojik destek almayı düşünebilirsiniz.', True),
    ('tr', 'Bir klinik psikologla görüşmenizi öneririm.', True),
    ('tr', 'Psikologla görüşmenizi önermiyorum.', False),
    ('tr', 'Psikolojik destek almanız gerekmiyor.', False),
    ('tr', 'Ben psikolog değilim.', False),
    ('tr', 'Psikolog kelimesi burada geçiyor.', False),
    ('tr', '“Psikologla görüşmek faydalı olabilir” dediniz.', False),
    ('tr', 'Ben psikolog değilim ama psikolojik destek faydalı olabilir.', True),
]


@pytest.mark.parametrize('language,text,expected', SUPPORT)
def test_actual_live_provider_reply_support_contract_without_network(monkeypatch, language, text, expected):
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])))))
    monkeypatch.setattr(mental_provider, 'get_openai_client', lambda *args: client)
    token = request_language.set(language)
    try:
        result = mental_provider.OpenAICompatibleMentalProvider('synthetic-not-a-real-key').generate_reply('Neutral synthetic fixture', False, [])
        assert result['reply'] == text and result['providerType'] == 'LIVE_OPENAI'
        assert result['escalationSuggested'] is expected
        assert professional_support_suggested(text, language) is expected
        assert not result.get('isCrisis') and not result.get('needsEmergencyEscalation')
        client.chat.completions.create.assert_called_once()
    finally:
        request_language.reset(token)
