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
    # Either no recording yet (the page keeps the catalog off) or whole languages of 33, each with its own file and hash.
    languages = sorted({e['language'] for e in entries})
    assert len(entries) == 33 * len(languages)
    if not entries:
        assert manifest['approval']['status'] == 'not-generated'
        return
    assert {(e['language'], e['patternId']) for e in entries} == {(lang, pid) for lang in languages for pid in texts}
    assert sorted(set(('tr', 'en', 'de')) - set(languages)) == sorted(manifest['languagesLeftOut'])
    approval = json.loads((ROOT / 'docs/mental-structured/closing-abc-v1/OWNER-APPROVAL-20261111.json').read_text('utf-8'))
    assert manifest['approval']['status'] == 'approved'
    assert manifest['approval']['ownerApprovedAt'] == approval['recordedAtUtc']
    for e in entries:
        assert e['exactText'] == texts[e['patternId']][e['language']]
        assert e['textSha256'] == hashlib.sha256(e['exactText'].encode()).hexdigest()
        path = ROOT / 'apps/vehicle-app/public' / e['audioPath'].lstrip('/')
        data = path.read_bytes()
        assert len(data) == e['bytes'] and hashlib.sha256(data).hexdigest() == e['sha256']
        assert e['approvalStatus'] == 'approved' and e['ownerApprovedAt'] == approval['recordedAtUtc']


def _fake_synthesis(tmp, languages=('tr', 'en', 'de')):
    """A synthesis record and WAV tree in the format of synthesize_closing_catalog.py (silent PCM, no inference)."""
    import hashlib
    import io
    import wave
    sys.path.insert(0, str(ROOT / 'scripts/mental_closing_abc'))
    import synthesize_closing_catalog as syn
    abc = json.loads((ROOT / 'apps/vehicle-app/public/audio/mental/closing-abc/v1/manifest.json').read_text('utf-8'))
    catalog_bytes = (ROOT / 'shared/mental/closing-catalog/v1/catalog.json').read_bytes()
    rows = []
    for row in syn.rows_of(json.loads(catalog_bytes)):
        if row['language'] not in languages:
            continue
        frames = 24000 * 2 + len(row['patternId']) * 240
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b'\x10\x00' * frames)
        raw = buffer.getvalue()
        (tmp / row['language']).mkdir(exist_ok=True)
        (tmp / row['language'] / row['fileName']).write_bytes(raw)
        rows.append({'assetId': row['assetId'], 'language': row['language'], 'patternId': row['patternId'], 'fileName': row['fileName'],
                     'textSha256': hashlib.sha256(row['exactText'].encode()).hexdigest(), 'seed': syn.seed_for(row['assetId']),
                     'sha256': hashlib.sha256(raw).hexdigest(), 'synthesisSeconds': 1.0,
                     'metrics': {**syn.pcm_metrics(raw)}, 'technicalFindings': [], 'createdAtUtc': '2026-11-10T00:00:00Z'})
    record = {'catalogSha256': hashlib.sha256(catalog_bytes).hexdigest(), 'integrityBefore': {'m': True}, 'integrityAfter': {'m': True},
              'referenceSha256': abc['referenceSha256'], 'generation': abc['generation'], 'speakerProfile': 'female-calm-v1',
              'sourceRevision': abc['model']['sourceRevision'], 'modelRevision': abc['model']['revision'], 'workerMode': 'resident-model-v1',
              'runtime': {'python': 'test'}, 'rows': rows}
    (tmp / 'synthesis.json').write_text(json.dumps(record), 'utf-8')
    return record


@pytest.mark.parametrize('languages,left_out', [(('tr', 'en', 'de'), []), (('tr', 'en'), ['de'])])
def test_manifest_builder_publishes_whole_languages_only_and_never_approves(tmp_path, monkeypatch, languages, left_out):
    import shutil
    sys.path.insert(0, str(ROOT / 'scripts/mental_closing_abc'))
    import build_closing_catalog_manifest as build
    synthesis, public = tmp_path / 'synthesis', tmp_path / 'public'
    synthesis.mkdir()
    target = public / 'audio/mental/closing-catalog/v1'
    target.mkdir(parents=True)
    shutil.copy(CATALOG_MANIFEST, target / 'manifest.json')
    record = _fake_synthesis(synthesis, languages)
    monkeypatch.setattr(build, 'PUBLIC', public)
    monkeypatch.setattr(build, 'TARGET', target)
    monkeypatch.setattr(sys, 'argv', ['build', '--synthesis', str(synthesis)])
    assert build.main() == 0
    manifest = json.loads((target / 'manifest.json').read_text('utf-8'))
    assert len(manifest['entries']) == 33 * len(languages) and manifest['languagesLeftOut'] == left_out
    assert {e['approvalStatus'] for e in manifest['entries']} == {'technical-preview-awaiting-owner-listening'}
    assert all(e['ownerApprovedAt'] is None for e in manifest['entries'])
    for e in manifest['entries']:
        assert (public / e['audioPath'].lstrip('/')).read_bytes() == (synthesis / e['language'] / e['fileName']).read_bytes()
    # A changed recording is refused, and an existing different file is never overwritten.
    record['rows'][0]['sha256'] = '0' * 64
    (synthesis / 'synthesis.json').write_text(json.dumps(record), 'utf-8')
    with pytest.raises(SystemExit, match='ASSET_VERIFICATION_FAILED'):
        build.main()


def test_one_take_per_line_and_findings_are_only_recorded():
    sys.path.insert(0, str(ROOT / 'scripts/mental_closing_abc'))
    import synthesize_closing_catalog as syn
    rows = syn.rows_of(cc.catalog())
    assert len(rows) == 99 and len({r['assetId'] for r in rows}) == 99
    assert [r['language'] for r in rows[:33]] == ['tr'] * 33 and rows[33]['language'] == 'en', 'language by language'
    assert syn.findings({'clippedSamples': 2, 'leadingSilenceMs': 100, 'trailingSilenceMs': 300, 'durationSeconds': 3.0}, 'a b c d e f') == ['clipped-samples:2']
    assert syn.findings({'clippedSamples': 0, 'leadingSilenceMs': 100, 'trailingSilenceMs': 300, 'durationSeconds': 9.0}, 'a b c') == ['seconds-per-word:3.00']


@pytest.mark.parametrize('language,pid,text,accepted', [
    # A negation inside the cue's own match is the user's when the cue holds without it ...
    ('tr', 'C09', 'Uykum hiç bölünmüyor.', False),
    ('en', 'C09', 'My sleep is not disrupted.', False),
    ('de', 'C09', 'Mein Schlaf wird nicht unterbrochen.', False),
    ('tr', 'C13', 'Karar vermekte zorlanmıyorum.', False),
    # ... and part of the line's meaning when the cue needs it (an intensifier around it is emphasis).
    ('tr', 'C09', 'Hiç uyuyamıyorum.', True),
    ('en', 'C09', "I can't sleep at night.", True),
    ('de', 'C09', 'Ich kann nachts nicht schlafen.', True),
    ('tr', 'C19', 'Kimse beni anlamıyor.', True),
    ('tr', 'C07', 'Kimse beni dinlemiyor.', True),
    ('tr', 'C09', 'En çok uykusuzluk beni zorluyor.', True),
    # Words between the parts of a cue ("sık sık", "hiç").
    ('tr', 'C09', 'Son haftalarda işte tempo çok yoğun ve uykum sık sık bölünüyor.', True),
    ('tr', 'C16', 'Kendime hiç zaman ayıramıyorum.', True),
])
def test_negation_inside_the_cue(language, pid, text, accepted):
    sys.path.insert(0, str(ROOT / 'scripts/mental_closing_abc'))
    import closing_catalog_eval as ev
    msgs = user(text)
    assert (cc.check(ev.oracle_candidate(pid, language, msgs), language, msgs) is None) == accepted


# Round 7: the independent review's C02 false accepts (provider candidate: C02, message 0, the whole message quoted).
# The cue word is there, the user's own current stress is not: a topic, a condition, a past state set against now.
REVIEW_C02 = [
    ('tr', 'Stres hakkında bir kitap okuyorum.', 'topic-only'),
    ('tr', 'Stresli olursam sana söylerim.', 'conditional'),
    ('tr', 'Stresliydim ama artık iyiyim.', 'past-then-now'),
    ('en', 'I am reading a book about stress.', 'topic-only'),
    ('en', 'If I feel stressed, I will tell you.', 'conditional'),
    ('en', 'I was stressed, but now I feel fine.', 'past-then-now'),
    ('de', 'Ich lese ein Buch über Stress.', 'topic-only'),
    ('de', 'Falls ich gestresst bin, sage ich Bescheid.', 'conditional'),
    ('de', 'Ich war gestresst, aber jetzt geht es mir gut.', 'past-then-now'),
]


@pytest.mark.parametrize('language,text,reason', REVIEW_C02)
def test_review_c02_candidates_without_a_present_self_statement_are_refused(language, text, reason):
    msgs = user(text)
    assert cc.check(cand('C02', text), language, msgs) == reason
    chosen, status, checks = cc.select([cand('C02', text)], language, msgs)
    assert (chosen, status) == (None, 'no-reliable-match') and checks == [{'id': 'C02', 'result': reason}]
    # The clause quote the oracle builds is refused for the same reason.
    sys.path.insert(0, str(ROOT / 'scripts/mental_closing_abc'))
    import closing_catalog_eval as ev
    assert cc.check(ev.oracle_candidate('C02', language, msgs), language, msgs) == reason


@pytest.mark.parametrize('language,text', [
    ('tr', 'Çok stresliyim.'), ('en', 'I am very stressed.'), ('de', 'Ich bin sehr gestresst.'),
])
def test_present_self_statement_of_stress_is_still_selected(language, text):
    assert cc.select([cand('C02', text)], language, user(text))[:2] == ('C02', 'catalog')


@pytest.mark.parametrize('language,pid,text,result', [
    # The user's own words in the topic phrase make it theirs; a pronoun object ends the topic phrase.
    ('tr', 'C02', 'Stresim hakkında konuşmak istiyorum.', None),
    ('en', 'C27', 'Talking about it helps me.', None),
    ('en', 'C27', 'Reading about stress management helps me.', None),
    ('en', 'C02', 'I am reading a book about anxiety and stress.', 'topic-only'),
    ('tr', 'C02', 'Stres ve kaygı hakkında bir kitap okuyorum.', 'topic-only'),
    # A condition after the statement does not make the statement conditional.
    ('en', 'C02', 'I get stressed when my boss calls.', None),
    ('de', 'C02', 'Ich bin gestresst, wenn mein Chef anruft.', None),
    ('tr', 'C02', 'Stresli olduğumda sana söylerim.', 'conditional'),
    ('de', 'C02', 'Wenn ich gestresst bin, sage ich Bescheid.', 'conditional'),
    # A later "now" that repeats the cue keeps it current; a past state alone is still the user's statement.
    ('en', 'C02', 'I was stressed and now I am even more stressed.', None),
    ('en', 'C02', 'I was stressed all week and I still am.', None),
    ('tr', 'C09', 'Dün gece uyuyamadım.', None),
    ('tr', 'C02', 'Stresliydim, şimdi iyiyim.', 'past-then-now'),
    ('de', 'C02', 'Ich war letzte Woche gestresst. Jetzt geht es mir gut.', 'past-then-now'),
])
def test_topic_condition_and_past_then_now_read_the_construction_not_a_word(language, pid, text, result):
    assert cc.check(cand(pid, text), language, user(text)) == result
