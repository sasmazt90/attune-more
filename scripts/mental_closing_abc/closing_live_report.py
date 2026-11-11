#!/usr/bin/env python3
"""Numbers of a live closing run (closing_live_probe.py output) against the criteria fixed before the run
(docs/mental-structured/closing-abc-v1/GPU-E2E-PLAN-20261110-round4.md, section 6). Only closings with status
'measured' enter timing numbers; blocked and failed ones are listed and count against their criterion.
Every sample is listed; medians with min-max; p95 only for n >= 20.
Usage: closing_live_report.py <live4 dir> > report.json
"""
import json
from pathlib import Path
import re
import statistics
import sys


def timing(header):
    return {m.group(1): float(m.group(2)) for m in re.finditer(r'tts-([\w-]+);dur=([\d.]+)', header or '')}


def stats(values):
    v = sorted(x for x in values if x is not None)
    if not v:
        return {'n': 0}
    out = {'n': len(v), 'median': round(statistics.median(v), 1), 'min': v[0], 'max': v[-1]}
    if len(v) >= 20:
        out['p95'] = v[min(len(v) - 1, int(round(0.95 * len(v) + 0.5)) - 1)]
    return out


def closing_row(label, kind, status, d):
    m, g = d.get('marks') or {}, d.get('gapsMs') or {}
    tts = [r for r in d.get('liveResponses', []) if r.get('kind') == 'tts' and r.get('profile') == 'female-calm-v1']
    analysis = [r for r in d.get('liveResponses', []) if r.get('kind') == 'analysis']
    ready, playing, c_end = m.get('firstPartReady'), m.get('summaryPlaying'), m.get('cEnded')
    ready_to_play = None
    if playing is not None and c_end is not None and ready is not None:
        ready_to_play = playing - max(ready, c_end)
    t = timing(tts[0].get('serverTiming')) if tts else {}
    clips = [x['file'] for x in d.get('fixtureRequests', []) if x.get('kind') == 'clip']
    row = {'label': label, 'kind': kind, 'status': status, 'language': d.get('language'),
           'spokenSummaryStatus': analysis[0].get('spokenSummaryStatus') if analysis else None, 'spokenText': d.get('spokenText'),
           'finishToA': m.get('aPlaying'), 'aToB': g.get('aToB'), 'bToC': g.get('bToC'), 'cToPersonal': g.get('cToSummary'), 'overlap': g.get('overlap'),
           'analysisMs': (d.get('durationsMs') or {}).get('summaryRequest'), 'summaryTextReady': (d.get('msFromTrigger') or {}).get('summaryTextReady'),
           'speechRequestToReadyMs': (d.get('durationsMs') or {}).get('dynamicSpeechPreparation'), 'personalReadyMs': ready, 'cEndedMs': c_end,
           'personalPlayingMs': playing, 'readyToPlayMs': ready_to_play, 'ttsStatus': tts[0].get('status') if tts else None,
           'ttsStart': tts[0].get('start') if tts else None, 'ttsSeconds': float(tts[0]['seconds']) if tts and tts[0].get('seconds') not in (None, '', 'None') else None,
           'serverTimingMs': t, 'gestureRequired': d.get('gestureRequiredEvents'), 'closingTaps': (d.get('userTaps') or {}).get('duringClosing'),
           'audio': [r.get('audio') for r in tts if r.get('audio')], 'clips': clips, 'noSpokenLine': m.get('noSpokenLine')}
    row['p1Pass'] = (row['cToPersonal'] is not None and row['cToPersonal'] <= 1000 and not row['overlap']
                     and not row['gestureRequired'] and not row['closingTaps'])
    row['p4Pass'] = row['readyToPlayMs'] is not None and row['readyToPlayMs'] <= 200
    return row


def summarize(rows):
    """Per kind (cold/prepared/warm) and language (tr/en/de/all): every sample counted, blocked and failed ones listed."""
    summary = {}
    for kind in ('cold', 'prepared', 'warm'):
        for language in ('tr', 'en', 'de', 'all'):
            sel = [r for r in rows if r['kind'] == kind and (language == 'all' or r['language'] == language)]
            measured = [r for r in sel if r['status'] == 'measured']
            if not sel:
                continue
            summary[f'{kind}/{language}'] = {
                'samples': len(sel), 'measured': len(measured), 'blockedOrFailed': [(r['label'], r['status'], r.get('reason')) for r in sel if r['status'] != 'measured'],
                'cToPersonalMs': stats(r['cToPersonal'] for r in measured), 'finishToAMs': stats(r['finishToA'] for r in measured),
                'aToBMs': stats(r['aToB'] for r in measured), 'bToCMs': stats(r['bToC'] for r in measured),
                'analysisMs': stats(r['analysisMs'] for r in measured), 'ttsRequestSeconds': stats(r['ttsSeconds'] for r in measured),
                'ttsVerifyMs': stats(r['serverTimingMs'].get('verify') for r in measured), 'ttsWarmWaitMs': stats(r['serverTimingMs'].get('warm-wait') for r in measured),
                'ttsWorkerMs': stats(r['serverTimingMs'].get('worker') for r in measured), 'ttsTotalMs': stats(r['serverTimingMs'].get('total') for r in measured),
                'readyToPlayMs': stats(r['readyToPlayMs'] for r in measured),
                'p1Passes': sum(1 for r in sel if r['p1Pass']), 'p4Passes': sum(1 for r in sel if r['p4Pass']),
                'spokenLineRefused': [r['label'] for r in measured if r.get('noSpokenLine') is not None or (r.get('spokenSummaryStatus') not in (None, 'valid'))]}
    return summary


def criteria(summary):
    """The rules fixed before the run: P1 warm needs 8 of 8 per language (>= 90 % of 8) and 22 of 24 overall, with all
    planned samples present (a blocked or failed sample counts against it); P2 needs 3 of 3 per language and 9 of 9."""
    warm = {k: v for k, v in summary.items() if k.startswith('warm/')}
    return {
        'criteria-P1': {k: {'passes': v['p1Passes'], 'of': v['samples'], 'needed': 22 if k.endswith('/all') else 8,
                            'pass': v['p1Passes'] >= (22 if k.endswith('/all') else 8) and v['samples'] == (24 if k.endswith('/all') else 8)} for k, v in warm.items()},
        'criteria-P2': {k: {'passes': v['p1Passes'], 'of': v['samples'], 'pass': v['p1Passes'] == v['samples'] == (9 if k.endswith('/all') else 3)}
                        for k, v in summary.items() if k.startswith('prepared/')},
        'criteria-P4': {k: {'passes': v['p4Passes'], 'of': v['measured']} for k, v in summary.items() if k.endswith('/all')}}


def main():
    base = Path(sys.argv[1])
    live = json.loads((base / 'live.json').read_text())
    rows = []
    for run in live['runs']:
        status = run.get('status')
        if status != 'measured':
            rows.append({'label': run['label'], 'kind': run['closing'], 'status': status, 'reason': run.get('reason'), 'language': run['label'][:2],
                         'p1Pass': False, 'p4Pass': False})
            continue
        f = base / (run['label'] + '.json')
        results = json.loads(f.read_text())['results'] if f.exists() else []
        if not results or not results[0].get('marks'):
            rows.append({'label': run['label'], 'kind': run['closing'], 'status': 'failed', 'reason': 'no timeline result', 'language': run['label'][:2],
                         'p1Pass': False, 'p4Pass': False, 'stdout': run.get('stdout'), 'stderr': run.get('stderr')})
            continue
        rows.append(closing_row(run['label'], run['closing'], status, results[0]))
    report = {'schema': 'attune-closing-live-report-v1', 'source': str(base), 'criteria': 'GPU-E2E-PLAN-20261110-round4.md section 6', 'rows': rows}
    summary = summarize(rows)
    report.update(criteria(summary))
    report['summary'] = summary
    report['warmUp'] = [{'process': p['process'], 'kind': p['kind'], 'gate': p.get('warmGate'), 'rows': (p.get('warmUp') or {}).get('rows'),
                         'secondsFromStartToWarm': p.get('secondsFromStartToWarm')} for p in live['processes']]
    report['concurrency'] = live.get('concurrency')
    json.dump(report, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
