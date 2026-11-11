#!/usr/bin/env python3
"""Assemble the closing A/B/C review package from already-synthesized parts. Nothing is synthesized here.

* Copies the 45 clips into TR|EN|DE/A|B|C/ (byte-identical, hash-checked).
* Listening samples: A_i -> B_i -> C_i (i = 1..5, so every clip is heard once in context), followed by the
  synthetic dynamic summary recorded on the host with the same profile. Joins use the app's configured pause;
  nothing is pitch/rate shifted or resynthesized. The summary transition shown is the best case (speech ready).
* Combination statistics for all 125 A/B/C choices per language, from clip durations plus the configured join
  pause and, when given, the measured browser transition overhead.
"""
import argparse
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path
import shutil
import statistics
import wave

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'apps/vehicle-app/public'
MANIFEST = PUBLIC / 'audio/mental/closing-abc/v1/manifest.json'


def frames(path):
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype()) == (1, 2, 24000, 'NONE')
        return w.readframes(w.getnframes())


def write_wav(path, pcm):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    path.write_bytes(buf.getvalue())
    return buf.getvalue()


def silence(ms):
    return b'\0\0' * round(24000 * ms / 1000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--latency', required=True, type=Path, help='Host latency probe output (latency.json + WAVs)')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--browser-gap-ms', type=float, default=None, help='Measured median browser ended->playing overhead')
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text('utf-8'))
    latency = json.loads((args.latency / 'latency.json').read_text('utf-8'))
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    join = manifest['joinSilenceMs']
    by = {(e['language'], e['variantId']): e for e in manifest['entries']}
    # 1. Byte-identical clip copies in the review layout.
    for e in manifest['entries']:
        source = PUBLIC / e['audioPath'].lstrip('/')
        target = out / e['language'].upper() / e['group'] / e['fileName']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == e['sha256']
    # 2. Listening samples.
    samples = out / 'Listening-Samples'
    samples.mkdir()
    sample_rows = []
    rows = {r['label']: r for r in latency['rows']}
    for language in ('tr', 'en', 'de'):
        summary_parts = [args.latency / f'{language}-part{i}.wav' for i in range(2) if (args.latency / f'{language}-part{i}.wav').exists()]
        summary_pcm = b''.join(frames(p) for p in summary_parts)
        for i in range(1, 6):
            clips = [by[(language, f'{g}{i}')] for g in 'ABC']
            pcm = b''
            for n, clip in enumerate(clips):
                pcm += frames(PUBLIC / clip['audioPath'].lstrip('/'))
                pcm += silence(join)
            name = f'{language.upper()}_A{i}-B{i}-C{i}_then-summary.wav'
            data = write_wav(samples / name, pcm + summary_pcm)
            sample_rows.append({'file': name, 'language': language, 'clips': [c['fileName'] for c in clips],
                                'bridgeSeconds': round(sum(c['durationSeconds'] for c in clips) + 2 * join / 1000, 3),
                                'joinPauseMs': join, 'transitionToSummaryMs': join,
                                'summaryParts': [p.name for p in summary_parts],
                                'summaryText': ' '.join(latency['parts'][language]),
                                'summarySeconds': round(len(summary_pcm) / 2 / 24000, 3),
                                'seconds': round(len(data[44:]) / 2 / 24000, 3), 'bytes': len(data),
                                'sha256': hashlib.sha256(data).hexdigest(),
                                'approvalStatus': 'awaiting-owner-listening'})
    # 3. Text and duration catalog.
    reports = out / 'Reports'
    reports.mkdir()
    shutil.copyfile(MANIFEST, reports / 'manifest.json')
    with (reports / 'closing-abc-catalog.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['language', 'group', 'variantId', 'fileName', 'exactText', 'durationSeconds', 'leadingSilenceMs',
                         'trailingSilenceMs', 'peak', 'clippedSamples', 'bytes', 'sha256', 'seed', 'synthesisSeconds', 'approvalStatus'])
        for e in manifest['entries']:
            q = e['qualityMetrics']
            writer.writerow([e['language'], e['group'], e['variantId'], e['fileName'], e['exactText'], e['durationSeconds'],
                             q['leadingSilenceMs'], q['trailingSilenceMs'], round(q['peak'], 4), q['clippedSamples'],
                             e['bytes'], e['sha256'], e['seed'], e['synthesisSeconds'], e['approvalStatus']])
    # 4. 125 combinations per language.
    overhead = args.browser_gap_ms or 0.0
    combos = {}
    for language in ('tr', 'en', 'de'):
        groups = [[e for e in manifest['entries'] if e['language'] == language and e['group'] == g] for g in 'ABC']
        totals = []
        for a, b, c in itertools.product(*groups):
            audio = a['durationSeconds'] + b['durationSeconds'] + c['durationSeconds']
            totals.append({'combination': f"{a['variantId']}-{b['variantId']}-{c['variantId']}", 'audioSeconds': round(audio, 3),
                           'withConfiguredJoins': round(audio + 2 * join / 1000, 3),
                           'withMeasuredTransitions': round(audio + 2 * (join + overhead) / 1000, 3)})
        assert len(totals) == 125

        def stats(key):
            values = [t[key] for t in totals]
            return {'min': min(values), 'median': round(statistics.median(values), 3), 'max': max(values)}
        combos[language] = {'count': 125, 'audioOnly': stats('audioSeconds'), 'withConfiguredJoins': stats('withConfiguredJoins'),
                            'withMeasuredTransitions': stats('withMeasuredTransitions'),
                            'shortest': min(totals, key=lambda t: t['withMeasuredTransitions'])['combination'],
                            'longest': max(totals, key=lambda t: t['withMeasuredTransitions'])['combination'],
                            'within8to9s': sum(8 <= t['withMeasuredTransitions'] <= 9 for t in totals),
                            'over9s': sum(t['withMeasuredTransitions'] > 9 for t in totals),
                            'under8s': sum(t['withMeasuredTransitions'] < 8 for t in totals), 'rows': totals}
    summary = {'schema': 'attune-mental-closing-abc-combinations-v1', 'joinPauseMs': join,
               'measuredBrowserTransitionOverheadMs': args.browser_gap_ms,
               'method': 'Sum of the three clip durations plus two transitions (configured join pause plus measured browser ended->playing overhead). Calculation only; not a listening approval.',
               'languages': combos, 'listeningSamples': sample_rows}
    (reports / 'combinations-and-samples.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps({k: {x: v[x] for x in ('audioOnly', 'withMeasuredTransitions', 'within8to9s', 'over9s', 'under8s')} for k, v in combos.items()}, indent=1))


if __name__ == '__main__':
    main()
