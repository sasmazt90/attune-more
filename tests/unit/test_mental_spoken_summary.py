"""Normal-conversation short spoken summary: same single analysis call, enforced bounds, no truncation (mocked provider).

The validator's checks are formal (form, language, address, first person, listed markers, lexical grounding per
coordinated part, negation parity). Content quality is
labelled separately in fixtures/mental_spoken_summary_cases.json; formally valid lines with wrong content must be
declared there as known limitations, so a passing test never claims meaning was verified."""
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
    ('tr', 'İş yerindeki baskıdan ve bozulan uykularından söz ettin.'),
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
    ('tr', 'Paylaştıkların için teşekkür ederim, iş baskısı konuştuk.', 'repeats-bridge-phrase'),
    ('tr', 'Görüşmemizin sonuna geldik, iş baskısından söz ettin.', 'repeats-bridge-phrase'),
    ('de', 'Vielen Dank, Sie sprachen über Druck bei der Arbeit.', 'repeats-bridge-phrase'),
    ('de', 'Du hast über Druck bei der Arbeit gesprochen.', 'address-mismatch'),
    ('tr', 'İş baskısından ve bozulan uykunuzdan söz ettiniz.', 'address-mismatch'),
    ('en', 'You talked about pressure at work and gestörten sleep.', 'wrong-language'),
    ('de', 'Sie sprachen über İş baskısı.', 'wrong-language'),
    ('de', 'You talked about pressure at work.', 'wrong-language'),
    ('en', 'You mentioned your vacation plans for next summer.', 'not-recap-form'),
    ('en', 'You talked about your vacation plans for next summer.', 'not-grounded-in-user-words'),
    # Lines a live provider returned on 2026-11-10: reassurance, evaluation or a suggestion instead of a recap.
    ('en', "It's normal to feel pressure at work and disrupted sleep.", 'advice-or-evaluation'),
    ('en', 'You are managing pressure at work and sleep effectively.', 'advice-or-evaluation'),
    ('en', 'You should talk about pressure at work with someone.', 'advice-or-evaluation'),
    ('tr', 'İş baskısı zorlayıcı olabilir, destek almayı düşünebilirsin.', 'advice-or-evaluation'),
    ('de', 'Es ist normal, bei der Arbeit Druck zu spüren.', 'advice-or-evaluation'),
    ('de', 'Sie sollten über Druck bei der Arbeit sprechen.', 'advice-or-evaluation'),
    # A live Turkish line with a grammar error (no ablative before the verb).
    ('tr', 'Yeni bir düzen kurmak ve arkadaşlardan uzaklaşmak söz ettin.', 'tr-ablative-required'),
])
def test_rejected_lines_are_dropped_not_shortened(language, text, reason):
    assert validate_spoken_summary(text, language, USER[language]) == (None, reason)


CORPUS = json.loads((Path(__file__).parent / 'fixtures/mental_spoken_summary_cases.json').read_text('utf-8'))


def _corpus_result(case):
    messages = [{'role': 'user', 'content': text} for text in CORPUS['users'][case['user']]]
    text, reason = validate_spoken_summary(case['candidate'], case['language'], messages)
    return 'valid' if text else reason


@pytest.mark.parametrize('case', CORPUS['cases'], ids=[c['id'] for c in CORPUS['cases']])
def test_corpus_formal_result(case):
    """Formal acceptance only: the validator's decision for each synthetic TR/EN/DE case."""
    assert _corpus_result(case) == case['formal']


def test_corpus_formally_valid_but_wrong_content_is_declared():
    """Content quality is not what the validator checks. Every accepted line whose content label is not 'correct'
    must be listed as a known limitation (a negation on the wrong topic or out of reach, one added word inside a part,
    swapped roles); a test that expects 'valid' for such a line documents a gap, it does not close it."""
    accepted_wrong = {c['id'] for c in CORPUS['cases'] if _corpus_result(c) == 'valid' and c['content'] != 'correct'}
    declared = {c['id'] for c in CORPUS['cases'] if c.get('knownLimitation')}
    assert accepted_wrong == declared
    assert {c['content'] for c in CORPUS['cases'] if c.get('knownLimitation')} == {'added-fact', 'wrong-person'}


def test_corpus_correct_lines_that_are_refused_are_declared():
    """The word-level checks err towards rejection. A correct recap that is refused for grounding or negation parity is
    listed as a conservative reject: nothing is spoken for it (the written summary stays), which is the safe direction."""
    refused_correct = {c['id'] for c in CORPUS['cases'] if c['content'] == 'correct'
                       and _corpus_result(c) in ('adds-unsaid-content', 'negation-not-kept', 'negation-added', 'first-person')}
    assert refused_correct == {c['id'] for c in CORPUS['cases'] if c.get('conservativeReject')}


def test_round_two_false_accepts_are_now_refused():
    """The six lines that round 2 accepted with wrong content (three negation flips, two added topics, one copied
    first person). They are refused now; the remaining accepted-but-wrong shapes are the knownLimitation cases."""
    six = ('tr-negation-flip', 'en-one-added-word', 'en-negation-flip', 'de-negation-flip', 'de-one-added-word', 'tr-live-first-person')
    by_id = {c['id']: c for c in CORPUS['cases']}
    for case_id in six:
        assert _corpus_result(by_id[case_id]) != 'valid' and not by_id[case_id].get('knownLimitation')
    assert {_corpus_result(by_id[i]) for i in six} == {'adds-unsaid-content', 'negation-not-kept', 'first-person'}


def test_round_three_known_limitations_are_now_refused():
    """The five accepted-but-wrong lines of round 3 (one added word inside a part, a negation moved to another topic in
    English and German, a negation further than four words away, swapped Turkish roles) are refused now. The shapes
    still accepted with wrong content are declared as knownLimitation cases, not hidden."""
    five = {'en-added-word-inside-part': 'adds-unsaid-content', 'en-negation-wrong-target': 'negation-moved',
            'de-negation-wrong-target': 'negation-not-kept', 'en-negation-out-of-reach': 'negation-not-kept',
            'tr-role-reversal': 'role-changed'}
    by_id = {c['id']: c for c in CORPUS['cases']}
    for case_id, reason in five.items():
        assert _corpus_result(by_id[case_id]) == reason and not by_id[case_id].get('knownLimitation')
        assert by_id[case_id]['content'] != 'correct'
    still_open = {c['id'] for c in CORPUS['cases'] if c.get('knownLimitation')}
    assert still_open and not still_open & set(five)


def test_round_four_known_limitations_are_now_refused_and_the_rest_stay_declared():
    """Round 5: four of the five accepted-but-wrong shapes of round 4 are refused (an unsaid person as a modifier or in
    a German compound, a three-letter German noun grounded by the stem list, a negation without a negation word). The
    shapes still accepted with wrong content stay declared: swapped roles in English word order and an unsaid
    non-person noun used as a modifier (English, Turkish) or inside a German compound."""
    four = {'en-added-modifier': 'adds-unsaid-content', 'de-added-in-compound': 'adds-unsaid-content',
            'de-variant-false-ground': 'adds-unsaid-content', 'en-negation-without-marker': 'negation-not-kept'}
    by_id = {c['id']: c for c in CORPUS['cases']}
    for case_id, reason in four.items():
        assert _corpus_result(by_id[case_id]) == reason and not by_id[case_id].get('knownLimitation')
    for case_id in ('en-person-modifier-family', 'en-person-short-part', 'en-short-noun-part', 'de-kaum-dropped', 'de-short-noun-added',
                    'tr-person-modifier'):
        assert _corpus_result(by_id[case_id]) != 'valid' and by_id[case_id]['content'] != 'correct'
    assert {c['id'] for c in CORPUS['cases'] if c.get('knownLimitation')} == {
        'en-role-reversal', 'en-added-thing-modifier', 'de-added-thing-in-compound', 'tr-added-thing-modifier'}


def test_live_conservative_rejects_of_round_four_are_grounded_without_accepting_the_inference():
    """Two correct live P9 lines refused in round 4 ("worn out" for "wearing me out", "yorgunluk" for "yoruluyorum") are
    accepted through closed lists (irregular English verbs, Turkish yorgun/yorul); the German line that adds "Vermissen",
    which the user never said, stays refused; correct lines with the new negation markers and short nouns stay valid."""
    by_id = {c['id']: c for c in CORPUS['cases']}
    for case_id in ('en-irregular-form', 'tr-tired-derivation', 'en-hardly-kept', 'de-short-noun-said', 'de-strong-verb-noun'):
        assert _corpus_result(by_id[case_id]) == 'valid' and by_id[case_id]['content'] == 'correct'
    assert _corpus_result(by_id['de-inference-refused']) == 'adds-unsaid-content'
    assert _corpus_result(by_id['tr-negation-flip']) == 'negation-not-kept'


def test_german_paraphrases_refused_in_round_three_are_accepted_without_new_false_accepts():
    """'Umzug' for 'ich ziehe', 'hohen' for 'hoch' (closed stem list), while the added-fact and negation shapes of the
    same languages stay refused; a synonym ('Sorge' for 'Angst') is still refused (conservativeReject)."""
    by_id = {c['id']: c for c in CORPUS['cases']}
    for case_id in ('de-paraphrase-refused', 'de-live-high-pressure', 'de-live-sleep-problems', 'de-strong-verb-noun'):
        assert _corpus_result(by_id[case_id]) == 'valid' and by_id[case_id]['content'] == 'correct'
    for case_id in ('de-added-noun-phrase', 'de-one-added-word', 'de-added-facts', 'de-negation-flip', 'de-negation-wrong-target'):
        assert _corpus_result(by_id[case_id]) != 'valid'
    assert by_id['de-synonym-refused'].get('conservativeReject') and _corpus_result(by_id['de-synonym-refused']) != 'valid'


@pytest.mark.parametrize('language,text', [
    ('en', 'Work has been very intense in recent weeks.'), ('en', 'My parents want me to visit.'),
    ('en', 'It is a different kind of event.'),
])
def test_words_ending_in_nt_are_not_negations(language, text):
    from mental_analysis import _negated_user_words
    plain, negated = _negated_user_words([{'role': 'user', 'content': text}], language)
    assert not negated and plain


@pytest.mark.parametrize('text', ["I don't sleep well.", 'I dont sleep well.', 'I cannot sleep.', "I can't sleep.", 'I never sleep well.'])
def test_contractions_and_negation_words_are_negations(text):
    from mental_analysis import _negated_user_words
    assert 'sleep' in _negated_user_words([{'role': 'user', 'content': text}], 'en')[1]


def test_corpus_covers_the_review_counter_examples_and_all_languages():
    ids = {c['id'] for c in CORPUS['cases']}
    assert {'review-A', 'review-B', 'review-C', 'review-D-sen', 'review-D-siz'} <= ids
    for language in ('tr', 'en', 'de'):
        rows = [c for c in CORPUS['cases'] if c['language'] == language]
        assert len({c['user'] for c in rows}) >= 5 and {'valid', 'adds-unsaid-content'} <= {c['formal'] for c in rows} | {'adds-unsaid-content'}


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
    line = {'tr': 'İş yerindeki baskıdan ve bozulan uykularından söz ettin.', 'en': 'You talked about pressure at work and disrupted sleep.',
            'de': 'Sie sprachen über Druck bei der Arbeit und gestörten Schlaf.'}[language]
    result, calls = _analyzer(monkeypatch, {**BASE, 'spokenSummary': line}, language)
    assert len(calls) == 1, 'no second provider call'
    prompt = calls[0]['messages'][-1]['content']
    assert 'Also return spokenSummary' in prompt and 'never more than 12 words or 100 characters' in prompt
    assert 'Do not thank the user' in prompt and 'Every topic word must be a word the user said' in prompt
    # The key is in the JSON template itself and the rule precedes the conversation: a live provider ignored a
    # trailing instruction for a key the template did not list.
    template = prompt[prompt.index('JSON formatı'):prompt.index('}')]
    assert '"spokenSummary"' in template
    assert prompt.index('spokenSummary is required') < prompt.index('Konuşma Geçmişi')
    assert {'tr': 'söz ettin."', 'en': 'You talked about', 'de': 'Sie sprachen über'}[language] in prompt
    assert 'Turkish informal singular (sen)' in prompt and 'keep negations as the user said them' in prompt
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
