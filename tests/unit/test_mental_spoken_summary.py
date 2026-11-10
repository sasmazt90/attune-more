"""Normal-conversation short spoken summary: same single analysis call, enforced bounds, no truncation (mocked provider)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
from mental_analysis import validate_spoken_summary  # noqa: E402
from mental_provider import OpenAICompatibleSessionAnalyzer  # noqa: E402
from localization import request_language  # noqa: E402

USER = {
    'tr': [{'role': 'user', 'content': 'İş yerinde baskı çok fazla ve uykularım bozuldu.'}],
    'en': [{'role': 'user', 'content': 'There is a lot of pressure at work and my sleep is disrupted.'}],
    'de': [{'role': 'user', 'content': 'Bei der Arbeit ist viel Druck und mein Schlaf ist gestört.'}],
}


@pytest.mark.parametrize('language,text', [
    ('tr', 'İş baskısından ve bozulan uykunuzdan söz ettiniz.'),
    ('en', 'You talked about pressure at work and disrupted sleep.'),
    ('de', 'Sie sprachen über Druck bei der Arbeit und gestörten Schlaf.'),
])
def test_valid_short_lines(language, text):
    assert validate_spoken_summary(text, language, USER[language]) == (text, None)


@pytest.mark.parametrize('language,text,reason', [
    ('en', None, 'missing'),
    ('en', '   ', 'empty'),
    ('en', 'You talked about pressure at work, disrupted sleep, evening walks, family and also your weekend plans.', 'too-many-characters'),
    ('en', 'You talked about pressure at work and sleep and walks and plans too.', 'too-many-words'),
    ('en', 'You talked about work. Sleep was hard.', 'more-than-one-sentence'),
    ('en', 'Thank you, you talked about pressure at work.', 'repeats-bridge-phrase'),
    ('en', 'Here is a summary of pressure at work.', 'repeats-bridge-phrase'),
    ('tr', 'Paylaştıklarınız için teşekkür ederim, iş baskısı konuştuk.', 'repeats-bridge-phrase'),
    ('tr', 'Görüşmemizin sonuna geldik, iş baskısından söz ettiniz.', 'repeats-bridge-phrase'),
    ('de', 'Vielen Dank, Sie sprachen über Druck bei der Arbeit.', 'repeats-bridge-phrase'),
    ('de', 'Du hast über Druck bei der Arbeit gesprochen.', 'informal-address'),
    ('tr', 'Sen iş baskısından söz ettin.', 'informal-address'),
    ('en', 'You talked about pressure at work and gestörten sleep.', 'wrong-language'),
    ('de', 'Sie sprachen über İş baskısı.', 'wrong-language'),
    ('en', 'You mentioned your vacation plans for next summer.', 'not-grounded-in-user-words'),
    # Lines a live provider returned on 2026-11-10: reassurance, evaluation or a suggestion instead of a recap.
    ('en', "It's normal to feel pressure at work and disrupted sleep.", 'advice-or-evaluation'),
    ('en', 'You are managing pressure at work and sleep effectively.', 'advice-or-evaluation'),
    ('en', 'You should talk about pressure at work with someone.', 'advice-or-evaluation'),
    ('tr', 'İş baskısı zorlayıcı olabilir, destek almayı düşünebilirsiniz.', 'advice-or-evaluation'),
    ('de', 'Es ist normal, bei der Arbeit Druck zu spüren.', 'advice-or-evaluation'),
    ('de', 'Sie sollten über Druck bei der Arbeit sprechen.', 'advice-or-evaluation'),
])
def test_rejected_lines_are_dropped_not_shortened(language, text, reason):
    assert validate_spoken_summary(text, language, USER[language]) == (None, reason)


def test_whitespace_is_normalized_but_words_are_never_cut():
    text = 'You talked about pressure at work   and disrupted\nsleep.'
    assert validate_spoken_summary(text, 'en', USER['en'])[0] == 'You talked about pressure at work and disrupted sleep.'


def _analyzer(monkeypatch, payload, language='en', spoken=True):
    import mental_provider
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
    monkeypatch.setattr(mental_provider, 'get_openai_client', lambda *a: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    analyzer = OpenAICompatibleSessionAnalyzer('mock')
    if spoken:
        analyzer.spoken_summary = True
    token = request_language.set(language)
    try:
        return analyzer.analyze_session(USER[language]), calls
    finally:
        request_language.reset(token)


BASE = {'summaryText': 'You described a lot of pressure at work over several weeks and that your sleep is disrupted.',
        'themes': [], 'moodTrend': 'STRESSED', 'professionalSupportSuggested': False, 'professionalSupportReason': None}


@pytest.mark.parametrize('language', ['tr', 'en', 'de'])
def test_one_call_requests_and_validates_spoken_line(monkeypatch, language):
    line = {'tr': 'İş baskısından ve bozulan uykunuzdan söz ettiniz.', 'en': 'You talked about pressure at work and disrupted sleep.',
            'de': 'Sie sprachen über Druck bei der Arbeit und gestörten Schlaf.'}[language]
    result, calls = _analyzer(monkeypatch, {**BASE, 'spokenSummary': line}, language)
    assert len(calls) == 1, 'no second provider call'
    prompt = calls[0]['messages'][-1]['content']
    assert 'Also return spokenSummary' in prompt and 'At most 12 words and 100 characters' in prompt
    assert 'Do not thank the user' in prompt and 'Ground it only in what the user actually said' in prompt
    # The key is in the JSON template itself and the rule precedes the conversation: a live provider ignored a
    # trailing instruction for a key the template did not list.
    template = prompt[prompt.index('JSON formatı'):prompt.index('}')]
    assert '"spokenSummary"' in template
    assert prompt.index('spokenSummary is required') < prompt.index('Konuşma Geçmişi')
    assert {'tr': 'söz ettiniz', 'en': 'You talked about', 'de': 'Sie sprachen über'}[language] in prompt
    assert 'No evaluation, reassurance, advice or suggestion' in prompt
    assert result['spokenSummary'] == line and result['spokenSummaryStatus'] == 'valid'
    assert result['summaryText'] == BASE['summaryText']


def test_invalid_provider_line_keeps_written_summary_and_is_not_trimmed(monkeypatch):
    long_line = 'You talked about pressure at work, disrupted sleep and many other topics during the evening.'
    result, calls = _analyzer(monkeypatch, {**BASE, 'spokenSummary': long_line})
    assert len(calls) == 1
    assert result['spokenSummary'] is None and result['spokenSummaryStatus'] in ('too-many-words', 'too-many-characters')
    assert result['summaryText'] == BASE['summaryText'] and result['providerType'] == 'LIVE_OPENAI'


def test_not_requested_leaves_the_normal_prompt_and_response_unchanged(monkeypatch):
    result, calls = _analyzer(monkeypatch, dict(BASE), spoken=False)
    assert 'spokenSummary' not in calls[0]['messages'][-1]['content']
    assert '"professionalSupportReason": null\n}' in calls[0]['messages'][-1]['content']
    assert 'spokenSummary' not in result and 'spokenSummaryStatus' not in result


def test_api_flag_is_opt_in_and_legacy_only(monkeypatch):
    from fastapi.testclient import TestClient
    import main
    seen = []

    class Analyzer:
        def analyze_session(self, messages):
            seen.append(getattr(self, 'spoken_summary', False))
            return {**BASE, 'providerType': 'LIVE_OPENAI'}
    monkeypatch.setattr(main, 'get_active_session_analyzer', lambda: Analyzer())
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder')
    client = TestClient(main.app)
    body = {'messages': [{'role': 'user', 'content': 'Synthetic statement.'}], 'cloudConsent': True}
    for extra in ({}, {'spokenSummary': True}, {'spokenSummary': True, 'engine': 'structured-v1'}):
        assert client.post('/api/mental/analyze-session', json={**body, **extra}).status_code == 200
    assert seen == [False, True, False]
    assert client.post('/api/mental/analyze-session', json={**body, 'spokenSummary': 'yes'}).status_code == 422
