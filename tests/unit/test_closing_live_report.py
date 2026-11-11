"""Live closing report (scripts/mental_closing_abc/closing_live_report.py): the criteria fixed before the round-4 run.
With 8 warm closings per language, >= 90 % means 8 of 8 (7 of 8 is 87.5 %); overall >= 90 % of 24 means 22. Blocked or
failed closings are listed, never timed, and count against their criterion. No files or servers are used."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/mental_closing_abc'))
from closing_live_report import closing_row, criteria, stats, summarize  # noqa: E402


def timeline(c_to_personal, ready=6000, c_end=9000, overlap=False, refused=False):
    marks = {'aPlaying': 19, 'cEnded': c_end, 'firstPartReady': None if refused else ready,
             'summaryPlaying': None if refused else c_end + c_to_personal, 'noSpokenLine': 1800 if refused else None}
    return {'language': 'de', 'marks': marks, 'gapsMs': {'aToB': 126, 'bToC': 126, 'cToSummary': None if refused else c_to_personal, 'overlap': overlap},
            'liveResponses': [{'kind': 'analysis', 'spokenSummaryStatus': 'adds-unsaid-content' if refused else 'valid'}]
            + ([] if refused else [{'kind': 'tts', 'profile': 'female-calm-v1', 'status': 200, 'seconds': '3.4',
                                    'serverTiming': 'tts-total;dur=5516.4, tts-verify;dur=2169.8, tts-warm-wait;dur=0.003, tts-worker;dur=3363.2'}]),
            'durationsMs': {'summaryRequest': 2697}, 'userTaps': {'duringClosing': 0}}


def warm_rows(language, passes, refused=0, blocked=0):
    rows = [closing_row(f'{language}-warm-{i + 1}', 'warm', 'measured', {**timeline(126), 'language': language}) for i in range(passes)]
    rows += [closing_row(f'{language}-warm-r{i + 1}', 'warm', 'measured', {**timeline(0, refused=True), 'language': language}) for i in range(refused)]
    rows += [{'label': f'{language}-warm-b{i + 1}', 'kind': 'warm', 'status': 'blocked', 'reason': 'warm-up-timeout', 'language': language,
              'p1Pass': False, 'p4Pass': False} for i in range(blocked)]
    for r in rows:
        r['language'] = language
    return rows


def test_a_closing_passes_only_with_its_personal_line_within_one_second_of_c_and_no_overlap_or_tap():
    assert closing_row('x', 'warm', 'measured', timeline(126))['p1Pass']
    assert not closing_row('x', 'warm', 'measured', timeline(1001))['p1Pass']
    assert not closing_row('x', 'warm', 'measured', timeline(126, overlap=True))['p1Pass']
    refused = closing_row('x', 'warm', 'measured', timeline(0, refused=True))
    assert not refused['p1Pass'] and not refused['p4Pass'] and refused['noSpokenLine'] == 1800
    row = closing_row('x', 'warm', 'measured', timeline(126))
    assert row['readyToPlayMs'] == 126 and row['serverTimingMs']['verify'] == 2169.8


def test_seven_of_eight_in_one_language_fails_p1_even_when_the_overall_share_is_met():
    rows = warm_rows('tr', 8) + warm_rows('en', 8) + warm_rows('de', 7, refused=1)
    p1 = criteria(summarize(rows))['criteria-P1']
    assert p1['warm/tr']['pass'] and p1['warm/en']['pass']
    assert p1['warm/de'] == {'passes': 7, 'of': 8, 'needed': 8, 'pass': False}
    assert p1['warm/all'] == {'passes': 23, 'of': 24, 'needed': 22, 'pass': True}


def test_blocked_closings_count_against_the_criterion_and_never_enter_the_times():
    rows = warm_rows('tr', 8) + warm_rows('en', 8) + warm_rows('de', 6, blocked=2)
    summary = summarize(rows)
    assert summary['warm/de']['samples'] == 8 and summary['warm/de']['measured'] == 6
    assert summary['warm/de']['cToPersonalMs']['n'] == 6
    assert [b[1] for b in summary['warm/de']['blockedOrFailed']] == ['blocked', 'blocked']
    assert criteria(summary)['criteria-P1']['warm/de']['pass'] is False


def test_missing_samples_fail_the_criterion():
    p1 = criteria(summarize(warm_rows('tr', 7) + warm_rows('en', 8) + warm_rows('de', 8)))['criteria-P1']
    assert p1['warm/tr']['pass'] is False and p1['warm/all']['pass'] is False


def test_stats_report_every_sample_and_p95_only_from_twenty():
    assert stats([3, 1, 2]) == {'n': 3, 'median': 2, 'min': 1, 'max': 3}
    assert 'p95' not in stats(range(19)) and stats(range(20))['p95'] == 19
    assert stats([None]) == {'n': 0}
