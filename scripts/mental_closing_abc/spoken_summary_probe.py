#!/usr/bin/env python3
"""Acceptance of the normal closing's short spoken line with the real provider (WEB host, synthetic conversations).

Runs the branch's analyzer in process with the product API's environment (read in memory from the running
attune-api@web process, never written or printed) and the same prompt as /api/mental/analyze-session with
spokenSummary=true: one provider call per analysis. The provider's raw line is captured before server validation so
that rejected lines can be reviewed; the result keeps the validation status and the line the API would return.
Usage: /opt/attune-venv/bin/python spoken_summary_probe.py --source <checkout> --out <file.json> [--repeats 5]
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from closing_realpath_probe import CONVERSATIONS, product_api_environment  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    env, _ = product_api_environment(8000)
    os.environ.update(env)
    sys.path.insert(0, str(Path(args.source) / 'services/core-api'))
    import mental_analysis
    from mental_provider import get_active_session_analyzer
    from localization import request_language
    raw = []
    original = mental_analysis.validate_spoken_summary

    def capture(value, language, messages):
        raw.append(value)
        return original(value, language, messages)
    mental_analysis.validate_spoken_summary = capture
    rows = []
    for language, conversations in CONVERSATIONS.items():
        for n, turns in enumerate(conversations, 1):
            messages = [{'role': role, 'content': text} for role, text in turns]
            for repeat in range(args.repeats):
                analyzer = get_active_session_analyzer()
                analyzer.spoken_summary = True
                token = request_language.set(language)
                started = time.perf_counter()
                try:
                    result = analyzer.analyze_session(messages)
                    error = None
                except Exception as exc:  # provider failure is a result, not a crash
                    result, error = {}, type(exc).__name__ + ':' + str(getattr(exc, 'detail', ''))[:80]
                finally:
                    request_language.reset(token)
                line = raw[-1] if raw else None
                rows.append({'language': language, 'conversation': f'{language}-c{n}', 'repeat': repeat, 'seconds': round(time.perf_counter() - started, 3),
                             'providerLine': line, 'providerWords': len(line.split()) if isinstance(line, str) else None,
                             'status': result.get('spokenSummaryStatus'), 'spokenSummary': result.get('spokenSummary'),
                             'summaryWords': len((result.get('summaryText') or '').split()), 'error': error})
                raw.clear()
                Path(args.out).write_text(json.dumps({'schema': 'attune-mental-spoken-summary-acceptance-v1', 'model': analyzer.model if hasattr(analyzer, 'model') else None,
                                                      'rows': rows}, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    total = {}
    for row in rows:
        total.setdefault(row['language'], {}).setdefault(row['status'] or row['error'], 0)
        total[row['language']][row['status'] or row['error']] += 1
    print(json.dumps(total, ensure_ascii=False))


if __name__ == '__main__':
    main()
