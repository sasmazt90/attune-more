#!/usr/bin/env python3
"""Build scenarios for scripts/qa/mental_closing_bridge_timeline.cjs from recorded measurements.

Each replayed speech part is derived from exactly one measurement row: its WAV is the file that row wrote, its delay
is that row's synthesis time, and the row's label, run id, profile, audio duration, text hash and WAV hash travel with
it. The timeline harness re-checks all of them before a scenario runs, so a WAV can no longer be paired with another
row's timing (the defect in the first timeline, where a repeat row's time was played with the first sample's WAV).

Sources:
  probe     latency.json of scripts/mental_closing_abc/closing_latency_probe.py (resident worker loop on WEB, no HTTP,
            no provider). Long written-summary parts only. The summary delay is an assumption, stated per scenario.
  realpath  realpath.json of scripts/mental_closing_abc/closing_realpath_probe.py (HTTP to a test API process on WEB:
            real provider analysis with spokenSummary, real TTS endpoint, cold and warm).

Usage: mental_closing_bridge_scenarios.py probe|realpath <measurement.json> <out-scenarios.json> [--summary-delay-ms N]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def part(base, out_dir, row, run_id, source, extra_delay=0.0, basis=''):
    wav = base / (row['label'] + '.wav')
    return {'text': row['text'], 'wav': os.path.relpath(wav, out_dir), 'delayMs': round((row['seconds'] + extra_delay) * 1000),
            'delayBasis': basis,
            'row': {'label': row['label'], 'runId': run_id, 'profile': row['profile'], 'audioSeconds': row['audioSeconds'],
                    'textSha256': row['textSha256'], 'sha256': row['sha256'], 'source': source, 'start': row.get('start')}}


def from_probe(measurement, out_dir, summary_delay_ms):
    data = json.loads(measurement.read_text('utf-8'))
    base, run_id = measurement.parent, 'closing-latency-probe:' + sha(measurement)[:12]
    rows = {r['label']: r for r in data['rows'] if r.get('profile') == 'female-calm-v1' and not r.get('error')}
    verify = {v['language']: v['seconds'] for v in data['perRequestVerifySeconds']}
    scenarios = []
    for language in ('tr', 'en', 'de'):
        basis = (f'resident-worker seconds + {verify[language]} s per-request verify_speaker (the API runs it before '
                 'every female request; the probe loop measured it separately)')
        for variant, first in (('sample1', f'{language}-part0'), ('repeat', f'{language}-part0-repeat')):
            parts = [rows[first], rows[f'{language}-part1']]
            scenarios.append({
                'label': f'{language}-long-{variant}', 'language': language, 'mode': 'long',
                'summary': {'summaryText': data['summaries'][language], 'delayMs': summary_delay_ms,
                            'source': f'fixture: {summary_delay_ms} ms assumed; the probe made no provider call'},
                'tts': [part(base, out_dir, r, run_id, 'WEB resident worker probe 2026-11-09 (' + r['start'] + ')',
                             verify[language], basis) for r in parts],
                'note': f'{language}-part1 was measured once; both {language} variants replay that same second part.'})
    return {'description': 'Corrected replay of the 2026-11-09 WEB probe: each part plays the WAV its own row produced.',
            'measurement': {'file': measurement.name, 'sha256': sha(measurement), 'runId': run_id}, 'scenarios': scenarios}


def from_realpath(measurement, out_dir, _summary_delay_ms):
    data = json.loads(measurement.read_text('utf-8'))
    base, run_id = measurement.parent, data['runId']
    tts = {r['label']: r for r in data['tts'] if not r.get('error')}
    scenarios = []
    for conv in data['analyses']:
        if conv.get('error'):
            continue
        language, cid = conv['language'], conv['conversation']
        summary = {'summaryText': conv['summaryText'], 'delayMs': round(conv['seconds'] * 1000),
                   'source': f"real provider via test API {data['host']} ({conv['label']}, {conv['providerType']})"}
        for start in ('cold', 'warm'):
            short = tts.get(f'{cid}-short-{start}')
            if short and conv.get('spokenSummary'):
                scenarios.append({'label': f'{cid}-short-{start}', 'language': language, 'mode': 'short',
                                  'summary': {**summary, 'spokenSummary': conv['spokenSummary']},
                                  'tts': [part(base, out_dir, short, run_id, f'test API TTS endpoint ({start})',
                                               0.0, 'HTTP request time measured at the test API, verify included')]})
            long_parts = [tts.get(f'{cid}-long{i}-{start}') for i in range(len(conv['longParts']))]
            if all(long_parts):
                scenarios.append({'label': f'{cid}-long-{start}', 'language': language, 'mode': 'long',
                                  'summary': summary,
                                  'tts': [part(base, out_dir, r, run_id, f'test API TTS endpoint ({start})',
                                               0.0, 'HTTP request time measured at the test API, verify included')
                                          for r in long_parts]})
    return {'description': 'Replay of real-path measurements: real provider analysis and real TTS endpoint on WEB.',
            'measurement': {'file': measurement.name, 'sha256': sha(measurement), 'runId': run_id}, 'scenarios': scenarios}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', choices=('probe', 'realpath'))
    parser.add_argument('measurement')
    parser.add_argument('out')
    parser.add_argument('--summary-delay-ms', type=int, default=3000)
    args = parser.parse_args()
    measurement, out = Path(args.measurement).resolve(), Path(args.out).resolve()
    build = from_probe if args.source == 'probe' else from_realpath
    spec = build(measurement, out.parent, args.summary_delay_ms)
    for scenario in spec['scenarios']:
        for t in scenario['tts']:
            if sha(out.parent / t['wav']) != t['row']['sha256']:
                raise SystemExit(f"{scenario['label']}: {t['wav']} is not the WAV of {t['row']['label']}")
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    print(json.dumps({'scenarios': [s['label'] for s in spec['scenarios']], 'out': str(out)}))


if __name__ == '__main__':
    main()
