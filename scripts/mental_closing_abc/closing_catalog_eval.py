#!/usr/bin/env python3
"""Catalog closing evaluation on the fixed comparison inputs (docs/.../comparison/round6-comparison-inputs.json).

oracle: no provider. For every input, the server check (mental_closing_catalog.check) is given a candidate for each
        acceptable and each forbidden pattern, quoting the user clause that carries the pattern's cue (or the first
        user message when no cue occurs). Acceptable candidates should pass, forbidden ones should be refused.
live:   the product analyzer with the catalog closing (real provider; run where the provider key is configured). Records the chosen line, its status and the written summary, then computes
        the comparison metrics. The legacy bad lines are checked with the legacy free-text validator in both modes.
Usage: closing_catalog_eval.py oracle|live [--repeat N] [--inputs file] > result.json
"""
import argparse
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import mental_closing_catalog as catalog  # noqa: E402
from mental_analysis import validate_spoken_summary  # noqa: E402

INPUTS = ROOT / 'docs/mental-structured/closing-abc-v1/comparison/round6-comparison-inputs.json'


def oracle_candidate(pattern_id, language, messages):
    pattern = catalog.patterns()[pattern_id]
    for index, message in enumerate(messages):
        if message['role'] != 'user':
            continue
        text = catalog._norm(message['content'], language)
        for a, b in catalog._clause_spans(text, language):
            if catalog._cue(pattern, text[a:b], language):
                return {'id': pattern_id, 'messageIndex': index, 'quote': text[a:b].strip()}
    first = next(i for i, m in enumerate(messages) if m['role'] == 'user')
    return {'id': pattern_id, 'messageIndex': first, 'quote': messages[first]['content'].rstrip('.')}


def legacy(spec):
    rows = []
    for line in spec['legacyLines']:
        text, reason = validate_spoken_summary(line['badLine'], line['language'], [{'role': 'user', 'content': u} for u in line['user']])
        rows.append({'id': line['id'], 'refused': text is None, 'reason': reason})
    return rows


def metrics(rows):
    spoken = [r for r in rows if r['spoken']]
    expect_line = [r for r in rows if r['acceptable']]
    expect_none = [r for r in rows if not r['acceptable']]
    salient = [r for r in rows if r['salient']]
    rate = lambda a, b: {'n': b, 'hits': a, 'rate': round(a / b, 3) if b else None}
    return {'contentAccuracy': rate(sum(r['spoken'] in r['acceptable'] for r in spoken), len(spoken)),
            'personalClosingRate': rate(sum(r['spoken'] in r['acceptable'] for r in expect_line), len(expect_line)),
            'safeAbstentionRate': rate(sum(r['spoken'] is None for r in expect_none), len(expect_none)),
            'salience': rate(sum(r['spoken'] == r['salient'] for r in salient), len(salient)),
            'forbiddenSpoken': [r['id'] for r in spoken if r['spoken'] in r['forbidden']],
            'writtenSummaryCoverage': rate(sum(r.get('summaryCovers') is True for r in rows), sum(r.get('summaryCovers') is not None for r in rows))}


def run_oracle(spec):
    rows = []
    for item in spec['inputs']:
        exp = item['expected']
        for pid in exp['acceptablePatterns'] + exp['forbiddenPatterns']:
            cand = oracle_candidate(pid, item['language'], item['conversation'])
            reason = catalog.check(cand, item['language'], item['conversation'])
            rows.append({'input': item['id'], 'pattern': pid, 'expected': 'accept' if pid in exp['acceptablePatterns'] else 'refuse',
                         'result': reason or 'accepted', 'quote': cand['quote']})
    ok = lambda r: (r['result'] == 'accepted') == (r['expected'] == 'accept')
    acc = [r for r in rows if r['expected'] == 'accept']
    ref = [r for r in rows if r['expected'] == 'refuse']
    return {'mode': 'oracle', 'checks': len(rows), 'acceptableAccepted': sum(r['result'] == 'accepted' for r in acc), 'acceptable': len(acc),
            'forbiddenRefused': sum(r['result'] != 'accepted' for r in ref), 'forbidden': len(ref),
            'mismatches': [r for r in rows if not ok(r)], 'rows': rows, 'legacy': legacy(spec)}


def run_live(spec, repeat):
    rows = []
    for item in spec['inputs']:
        for attempt in range(repeat):
            started = time.time()
            try:
                data, error = analyze(item), None
            except Exception as exc:  # recorded, never hidden: a failed analysis is a missing closing
                data, error = {}, getattr(exc, 'detail', type(exc).__name__)
            exp = item['expected']
            summary = (data.get('summaryText') or '').lower()
            covers = all(any(stem.lower() in summary for stem in group) for group in exp['writtenSummaryTopics']) if exp['writtenSummaryTopics'] and not error else None
            rows.append({'id': item['id'], 'attempt': attempt + 1, 'language': item['language'], 'spoken': data.get('spokenCatalogId'),
                         'status': data.get('spokenSummaryStatus') or error, 'checks': data.get('spokenCatalogChecks'),
                         'acceptable': exp['acceptablePatterns'], 'forbidden': exp['forbiddenPatterns'], 'salient': exp['salient'],
                         'summaryText': data.get('summaryText'), 'summaryCovers': covers, 'seconds': round(time.time() - started, 3)})
    return {'mode': 'live', 'repeat': repeat, 'metrics': metrics(rows), 'perLanguage': {l: metrics([r for r in rows if r['language'] == l]) for l in ('tr', 'en', 'de')},
            'rows': rows, 'legacy': legacy(spec)}


def analyze(item):
    """One analysis through the product analyzer (the one the API uses) with the catalog closing, in the input's language."""
    from localization import request_language
    from mental_provider import get_active_session_analyzer
    analyzer = get_active_session_analyzer()
    if type(analyzer).__name__ != 'OpenAICompatibleSessionAnalyzer':
        raise SystemExit('live mode needs the provider (OPENAI_API_KEY); the local fallback has no closing')
    analyzer.spoken_summary = True
    analyzer.closing_catalog = True
    token = request_language.set(item['language'])
    try:
        return analyzer.analyze_session(item['conversation'])
    finally:
        request_language.reset(token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['oracle', 'live'])
    parser.add_argument('--repeat', type=int, default=1)
    parser.add_argument('--inputs', default=str(INPUTS))
    args = parser.parse_args()
    spec = json.loads(Path(args.inputs).read_text('utf-8'))
    out = run_oracle(spec) if args.mode == 'oracle' else run_live(spec, args.repeat)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
