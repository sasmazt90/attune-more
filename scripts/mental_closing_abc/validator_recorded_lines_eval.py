#!/usr/bin/env python3
"""Offline: every recorded real-provider spoken line of the closing reviews through a baseline commit's validator and
the working tree's validator. The lines are round 2's providerAcceptance rows (72 per prompt); round 3 re-validated the
same rows (recordedRealProviderLinesRevalidatedOffline), which is checked here and not counted twice.

No provider call. The user turns come from the synthetic conversations in closing_realpath_probe.CONVERSATIONS and
spoken_summary_probe.DIVERSE. Formal acceptance only: a 'valid' line is not a line whose meaning was verified.
Usage: python3 scripts/mental_closing_abc/validator_recorded_lines_eval.py --baseline e71f39c > out.json
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/mental_closing_abc'))
import mental_analysis as current  # noqa: E402
from closing_realpath_probe import CONVERSATIONS  # noqa: E402
from spoken_summary_probe import DIVERSE  # noqa: E402

DOCS = ROOT / 'docs/mental-structured/closing-abc-v1'


def conversation(cid):
    language, kind = cid.split('-')
    turns = (CONVERSATIONS if kind[0] == 'c' else DIVERSE)[language][int(kind[1:]) - 1]
    return [{'role': role, 'content': text} for role, text in turns]


def recorded_lines():
    from collections import Counter
    lines = []
    round2 = json.loads((DOCS / 'review-20261110-round2.json').read_text('utf-8'))['providerAcceptance']
    names = {'senPrompt': 'earlier prompt (sen)', 'senPrompt6to10Words': 'current prompt (6-10 words)'}
    for prompt in ('senPrompt', 'senPrompt6to10Words'):
        for entry in round2[prompt]:
            for row in entry['rows']:
                lines.append({'source': names[prompt], 'corpus': entry['corpus'], 'conversation': row['conversation'], 'line': row['providerLine']})
    round3 = json.loads((DOCS / 'review-20261110-round3.json').read_text('utf-8'))['validator']['recordedRealProviderLinesRevalidatedOffline']
    for prompt, name in (('currentPrompt', 'current prompt (6-10 words)'), ('earlierPrompt', 'earlier prompt (sen)')):
        same = Counter((r['conversation'], r['line']) for r in round3[prompt]['rows']) == Counter((r['conversation'], r['line']) for r in lines if r['source'] == name)
        if not same:
            raise SystemExit('ROUND3_ROWS_DIFFER_FROM_ROUND2: ' + prompt)
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, help='git revision whose services/core-api/mental_analysis.py is compared')
    args = parser.parse_args()
    source = subprocess.run(['git', 'show', f'{args.baseline}:services/core-api/mental_analysis.py'], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'baseline_mental_analysis.py'
        path.write_text(source, 'utf-8')
        spec = importlib.util.spec_from_file_location('baseline_mental_analysis', path)
        baseline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(baseline)
    rows = []
    for item in recorded_lines():
        language, messages = item['conversation'][:2], conversation(item['conversation'])
        before = baseline.validate_spoken_summary(item['line'], language, messages)
        after = current.validate_spoken_summary(item['line'], language, messages)
        rows.append({**item, 'language': language, 'baseline': 'valid' if before[0] else before[1], 'now': 'valid' if after[0] else after[1]})
    summary = {}
    for source in sorted({r['source'] for r in rows}):
        for language in ('tr', 'en', 'de'):
            subset = [r for r in rows if r['source'] == source and r['language'] == language]
            if subset:
                summary[f'{source}/{language}'] = {'n': len(subset), 'formallyValidBaseline': sum(r['baseline'] == 'valid' for r in subset),
                                                   'formallyValidNow': sum(r['now'] == 'valid' for r in subset)}
    changed = {}
    for r in rows:
        if r['baseline'] != r['now']:
            key = (r['conversation'], r['line'], r['baseline'], r['now'])
            changed[key] = changed.get(key, 0) + 1
    json.dump({'baseline': args.baseline, 'lines': len(rows), 'round3RowsAreTheseRows': True,
               'note': 'formal acceptance only; meaning is not verified by the validator',
               'summary': summary, 'changed': [{'conversation': k[0], 'line': k[1], 'baseline': k[2], 'now': k[3], 'count': v} for k, v in changed.items()],
               'stillRefusedNow': sorted({(r['conversation'], r['line'], r['now']) for r in rows if r['now'] != 'valid'}),
               'rows': rows}, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
