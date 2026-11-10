"""Catalog closing (shared/mental/closing-catalog/v1): the provider names catalog lines with the source user message and
the user's exact words; the server checks every candidate and speaks only the fixed, reviewed line. Mocked provider,
no network. A quote or one keyword is never treated as proof of meaning: the checks below each refuse a quote that
carries the cue word but not the meaning."""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import mental_closing_catalog as cc  # noqa: E402
from localization import request_language  # noqa: E402
from mental_provider import OpenAICompatibleSessionAnalyzer  # noqa: E402

COMPARISON = ROOT / 'docs/mental-structured/closing-abc-v1/comparison'


def user(*texts):
    return [{'role': 'user', 'content': t} for t in texts]


def cand(pid, quote, index=0):
    return {'id': pid, 'messageIndex': index, 'quote': quote}


def test_catalog_has_33_meanings_in_three_languages_within_limits_and_one_address():
    cat = cc.catalog()
    pats = cat['patterns']
    assert [p['id'] for p in pats] == [f'C{i:02d}' for i in range(1, 34)]
    for p in pats:
        assert set(p['text']) == {'tr', 'en', 'de'} and p['condition'] and p['falseMatches']
        assert set(p['cues']) == {'tr', 'en', 'de'} and all(p['cues'][lang] for lang in ('tr', 'en', 'de'))
        for lang, text in p['text'].items():
            assert len(text) <= 100 and len(text.split()) <= 12, (p['id'], lang)
        assert p['text']['tr'].endswith('ttin.') and 'siz' not in p['text']['tr'].lower().split()
        assert p['text']['en'].startswith('You ') and p['text']['de'].startswith('Sie ')
    assert cat['address'] == {'tr': 'sen', 'en': 'you', 'de': 'Sie'}


def test_every_declared_false_match_is_refused():
    for p in cc.catalog()['patterns']:
        for f in p['falseMatches']:
            msgs = user(f['user'])
            assert cc.check(cand(p['id'], f['user'].rstrip('.')), f['language'], msgs) is not None, (p['id'], f['user'])


@pytest.mark.parametrize('language,text,pid,reason', [
    # negation, third person, past, "no longer"
    ('en', 'I am not stressed', 'C02', 'negated'),
    ('tr', 'Stresli değilim', 'C02', 'negated'),
    ('de', 'Ich bin nicht gestresst', 'C02', 'negated'),
    ('en', 'My friend is stressed', 'C02', 'not-about-the-user'),
    ('tr', 'Arkadaşım çok stresli', 'C02', 'not-about-the-user'),
    ('de', 'Mein Freund ist gestresst', 'C02', 'not-about-the-user'),
    ('en', 'I used to be stressed, but not anymore', 'C02', 'past'),
    ('tr', 'Eskiden stresliydim, artık değilim', 'C02', 'past'),
    ('de', 'Früher war ich gestresst, jetzt nicht mehr', 'C02', 'past'),
    # no automatic inference
    ('tr', 'Yalnız yaşıyorum', 'C17', 'no-cue-in-quote'),
    ('en', 'I live alone', 'C17', 'no-cue-in-quote'),
    ('tr', 'Çok sorumluluğum var', 'C14', 'no-cue-in-quote'),
    ('en', 'I have a lot of responsibilities', 'C14', 'no-cue-in-quote'),
    ('tr', 'Annem beni dinlemiyor', 'C03', 'no-cue-in-quote'),
    # resting is not being listened to, and the reverse
    ('tr', 'Annem beni dinlemiyor', 'C04', 'no-cue-in-quote'),
    ('tr', 'Hiç dinlenemiyorum', 'C07', 'no-cue-in-quote'),
    # someone else's state, also with the user as object or possessor
    ('en', "My mother is very worried about my father's health", 'C11', 'not-about-the-user'),
    ('en', 'My mother is worried about me', 'C11', 'not-about-the-user'),
    ('en', 'My brother passed his exam and I am so proud of him', 'C33', 'excluded-use'),
    ('tr', 'Kardeşim sınavı kazandı, onunla gurur duyuyorum', 'C33', 'excluded-use'),
    ('de', 'Ich bin so stolz auf ihn', 'C33', 'excluded-use'),
    ('en', 'My sister is proud of me', 'C33', 'not-about-the-user'),
])
def test_cue_word_without_the_meaning_is_refused(language, text, pid, reason):
    msgs = user(text)
    quote = cc._norm(text, language)
    assert cc.check(cand(pid, quote), language, msgs) == reason


@pytest.mark.parametrize('language,text,pid', [
    ('tr', 'Bu aralar çok stresliyim', 'C02'),
    ('en', "I'm really stressed at the moment", 'C02'),
    ('de', 'Ich bin gerade sehr gestresst', 'C02'),
    ('tr', 'Hiç dinlenemiyorum', 'C04'),
    ('en', 'Nobody listens to me in meetings', 'C07'),
    ('de', 'In Besprechungen hört mir niemand zu', 'C07'),
    ('tr', 'Kendimle gurur duyuyorum', 'C33'),
    ('en', "I'm struggling to decide between two job offers", 'C13'),
    ('de', 'Ich kann mich nicht zwischen zwei Jobangeboten entscheiden', 'C13'),
])
def test_said_about_oneself_now_is_accepted(language, text, pid):
    assert cc.check(cand(pid, cc._norm(text, language)), language, user(text)) is None


def test_source_message_and_quote_are_verified_on_the_server():
    msgs = [{'role': 'assistant', 'content': 'Maybe you feel lonely?'}, {'role': 'user', 'content': 'I am not sure.'}]
    assert cc.check(cand('C17', 'maybe you feel lonely', 0), 'en', msgs) == 'not-a-user-message'
    assert cc.check(cand('C17', 'i feel lonely', 1), 'en', msgs) == 'quote-not-in-message'
    assert cc.check(cand('C17', 'i feel lonely', 5), 'en', msgs) == 'unknown-message'
    assert cc.check(cand('C99', 'i am not sure', 1), 'en', msgs) == 'unknown-id'
    assert cc.check({'id': 'C17', 'messageIndex': True, 'quote': 'i am not sure'}, 'en', msgs) == 'unknown-message'
    assert cc.check('C17', 'en', msgs) == 'malformed'


def test_later_correction_is_respected():
    msgs = user("I've been really tired lately.", "Actually I'm not tired, I'm just bored.")
    assert cc.check(cand('C08', "i've been really tired lately"), 'en', msgs) == 'corrected-later'
    msgs = user('Son zamanlarda çok yorgunum.', 'Aslında yorgun değilim, sadece canım sıkılıyor.')
    assert cc.check(cand('C08', 'son zamanlarda çok yorgunum'), 'tr', msgs) == 'corrected-later'


def test_positive_conversation_gets_no_problem_line():
    msgs = user('Kendimi yalnız hissetmiyorum, ailem hep yanımda.')
    assert cc.check(cand('C17', 'kendimi yalnız hissetmiyorum'), 'tr', msgs) == 'negated'
    assert cc.check(cand('C28', 'ailem hep yanımda'), 'tr', msgs) is None


def test_selection_prefers_the_topic_the_user_stressed_and_abstains_without_a_checked_match():
    msgs = user('I am a bit tired.', 'But above all I am really worried about my exam, it worries me every day.')
    chosen, status, checks = cc.select([cand('C08', 'i am a bit tired', 0), cand('C11', 'i am really worried about my exam', 1)], 'en', msgs)
    assert (chosen, status) == ('C11', 'catalog') and [c['result'] for c in checks] == ['accepted', 'accepted']
    assert cc.select([], 'en', msgs)[:2] == (None, 'no-candidate')
    assert cc.select(None, 'en', msgs)[:2] == (None, 'no-candidate')
    chosen, status, checks = cc.select([cand('C17', 'i am a bit tired', 0)], 'en', msgs)
    assert (chosen, status) == (None, 'no-reliable-match') and checks == [{'id': 'C17', 'result': 'no-cue-in-quote'}]
    # Never more than three candidates are considered.
    many = [cand('C17', 'x y z', 0)] * 3 + [cand('C08', 'i am a bit tired', 0)]
    assert cc.select(many, 'en', msgs)[0] is None and len(cc.select(many, 'en', msgs)[2]) == 3


def test_fixed_comparison_and_holdout_results_are_reproduced():
    sys.path.insert(0, str(ROOT / 'scripts/mental_closing_abc'))
    import closing_catalog_eval as ev
    tuned = ev.run_oracle(json.loads((COMPARISON / 'round6-comparison-inputs.json').read_text('utf-8')))
    assert (tuned['acceptableAccepted'], tuned['forbiddenRefused']) == (51, 54) and tuned['acceptable'] == 51
    h2 = ev.run_oracle(json.loads((COMPARISON / 'round6-holdout2-inputs.json').read_text('utf-8')))
    # Safety on the fresh set: no forbidden line accepted; coverage misses stay visible (8 of 12).
    assert h2['forbiddenRefused'] == h2['forbidden'] == 30 and (h2['acceptableAccepted'], h2['acceptable']) == (8, 12)
    assert all(r['refused'] for r in tuned['legacy'])


BASE = {'summaryText': 'You described a lot of pressure at work and that your sleep is disrupted.',
        'themes': [], 'moodTrend': 'STRESSED', 'professionalSupportSuggested': False, 'professionalSupportReason': None}
CONV = {'tr': user('İş yerinde baskı çok fazla ve uykularım bozuldu.'),
        'en': user('There is a lot of pressure at work and my sleep is disrupted.'),
        'de': user('Bei der Arbeit ist viel Druck und mein Schlaf ist gestört.')}
QUOTE = {'tr': 'uykularım bozuldu', 'en': 'my sleep is disrupted', 'de': 'mein schlaf ist gestört'}


def _analyze(monkeypatch, payload, language):
    import mental_provider
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
    monkeypatch.setattr(mental_provider, 'get_openai_client', lambda *a: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    analyzer = OpenAICompatibleSessionAnalyzer('mock')
    analyzer.spoken_summary = True
    analyzer.closing_catalog = True
    token = request_language.set(language)
    try:
        return analyzer.analyze_session(CONV[language]), calls
    finally:
        request_language.reset(token)


@pytest.mark.parametrize('language', ['tr', 'en', 'de'])
def test_one_call_returns_the_checked_catalog_line(monkeypatch, language):
    result, calls = _analyze(monkeypatch, {**BASE, 'closingCandidates': [cand('C09', QUOTE[language])]}, language)
    assert len(calls) == 1
    prompt = calls[0]['messages'][-1]['content']
    template = prompt[prompt.index('JSON formatı'):prompt.index('}\n')]
    assert '"closingCandidates"' in template and '"spokenSummary"' not in template
    assert prompt.index('closingCandidates is required') < prompt.index('Konuşma Geçmişi')
    assert '[0] user: ' in prompt and 'C33:' in prompt and 'living alone is not loneliness' in prompt
    assert result['spokenCatalogId'] == 'C09' and result['spokenSummaryStatus'] == 'catalog'
    assert result['spokenSummary'] == cc.spoken_text('C09', language) and result['spokenCatalogVersion'] == cc.catalog_version()
    assert 'closingCandidates' not in result and result['summaryText'] == BASE['summaryText']


def test_unchecked_candidates_speak_nothing_and_keep_the_written_summary(monkeypatch):
    bad = [cand('C17', 'my sleep is disrupted'), cand('C09', 'my sleep is not disrupted'), {'id': 'C09', 'messageIndex': 3, 'quote': 'x'}]
    result, _ = _analyze(monkeypatch, {**BASE, 'closingCandidates': bad}, 'en')
    assert result['spokenSummary'] is None and result['spokenCatalogId'] is None
    assert result['spokenSummaryStatus'] == 'no-reliable-match'
    assert [c['result'] for c in result['spokenCatalogChecks']] == ['no-cue-in-quote', 'quote-not-in-message', 'unknown-message']
    assert result['summaryText'] == BASE['summaryText']
    result, _ = _analyze(monkeypatch, dict(BASE), 'en')
    assert result['spokenSummary'] is None and result['spokenSummaryStatus'] == 'no-candidate'


def test_checks_carry_no_user_words(monkeypatch):
    result, _ = _analyze(monkeypatch, {**BASE, 'closingCandidates': [cand('C09', QUOTE['en'])]}, 'en')
    assert not re.search('sleep|disrupted', json.dumps(result['spokenCatalogChecks']))


def test_api_catalog_flag_is_opt_in_and_needs_the_spoken_closing(monkeypatch):
    from fastapi.testclient import TestClient
    import main
    seen = []

    class Analyzer:
        def analyze_session(self, messages):
            seen.append((getattr(self, 'spoken_summary', False), getattr(self, 'closing_catalog', False)))
            return {**BASE, 'providerType': 'LIVE_OPENAI'}
    monkeypatch.setattr(main, 'get_active_session_analyzer', lambda: Analyzer())
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder')
    client = TestClient(main.app)
    body = {'messages': [{'role': 'user', 'content': 'Synthetic statement.'}], 'cloudConsent': True}
    for extra in ({}, {'spokenSummary': True}, {'spokenSummary': True, 'spokenCatalog': True}, {'spokenCatalog': True},
                  {'spokenSummary': True, 'spokenCatalog': True, 'engine': 'structured-v1'}):
        assert client.post('/api/mental/analyze-session', json={**body, **extra}).status_code == 200
    assert seen == [(False, False), (True, False), (True, True), (False, False), (False, False)]
    assert client.post('/api/mental/analyze-session', json={**body, 'spokenCatalog': 'yes'}).status_code == 422


CATALOG_MANIFEST = ROOT / 'apps/vehicle-app/public/audio/mental/closing-catalog/v1/manifest.json'


def test_catalog_recordings_manifest_matches_the_catalog_and_the_closing_voice():
    import hashlib
    manifest = json.loads(CATALOG_MANIFEST.read_text('utf-8'))
    abc = json.loads((ROOT / 'apps/vehicle-app/public/audio/mental/closing-abc/v1/manifest.json').read_text('utf-8'))
    texts = {p['id']: p['text'] for p in cc.catalog()['patterns']}
    assert manifest['catalogVersion'] == cc.catalog_version()
    assert manifest['catalogTextsSha256'] == hashlib.sha256(json.dumps(texts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    for key in ('speakerProfile', 'referenceSha256', 'generation', 'model', 'seedRule'):
        assert manifest[key] == abc[key], key
    entries = manifest['entries']
    # Either no recording yet (the page keeps the catalog off) or all 99, each with its own file and hash.
    assert len(entries) in (0, 99)
    if not entries:
        assert manifest['approval']['status'] == 'not-generated'
        return
    assert {(e['language'], e['patternId']) for e in entries} == {(lang, pid) for lang in ('tr', 'en', 'de') for pid in texts}
    for e in entries:
        assert e['exactText'] == texts[e['patternId']][e['language']]
        assert e['textSha256'] == hashlib.sha256(e['exactText'].encode()).hexdigest()
        path = ROOT / 'apps/vehicle-app/public' / e['audioPath'].lstrip('/')
        data = path.read_bytes()
        assert len(data) == e['bytes'] and hashlib.sha256(data).hexdigest() == e['sha256']
        assert e['approvalStatus'] == 'technical-preview-awaiting-owner-listening' and e['ownerApprovedAt'] is None
