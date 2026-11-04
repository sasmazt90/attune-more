#!/usr/bin/env python3
"""Measures Mental speech generation through the real API on the host. Prints timings only.

Three cases, kept apart: cold (first request after the API restarts), normal (model already loaded),
and failure (a request cancelled mid-generation, then the next request). Needs the API's service
token in the environment, which it never prints. Generates audio locally; no provider is called.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
import urllib.error
import urllib.request

API = 'http://127.0.0.1:{}/api/mental/neural-speech'
TEXTS = {
    'en': ['I hear you. That sounds like a lot to carry today.', 'What feels heaviest right now?', 'Thank you for telling me. Would you like to say more about that?',
           'It makes sense that you feel tired after a week like this.', 'Let us take this slowly. What would help you most this evening?'],
    'tr': ['Sizi duyuyorum. Bugün taşıdığınız çok şey var gibi görünüyor.', 'Şu anda en çok ne zorluyor?'],
    'de': ['Ich höre Ihnen zu. Das klingt nach sehr viel für heute.', 'Was belastet Sie gerade am meisten?'],
}


def speak(port, text, language, timeout=620):
    request = urllib.request.Request(API.format(port) + '?language=' + language, method='POST', data=json.dumps({'text': text, 'language': language, 'speechConsent': True}).encode(),
                                     headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['ATTUNE_MENTAL_TTS_TOKEN']})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return {'status': response.status, 'seconds': round(time.monotonic() - started, 2), 'workerSeconds': response.headers.get('x-tts-seconds'), 'start': response.headers.get('x-tts-start'), 'bytes': len(body), 'audioSeconds': round((len(body) - 44) / 48000, 2), 'language': language}
    except urllib.error.HTTPError as error:
        return {'status': error.code, 'seconds': round(time.monotonic() - started, 2), 'language': language, 'detail': error.read()[:120].decode('utf8', 'replace')}


def summary(rows):
    values = sorted(r['seconds'] for r in rows if r.get('status') == 200)
    ratios = [r['seconds'] / r['audioSeconds'] for r in rows if r.get('status') == 200 and r.get('audioSeconds')]
    if not values:
        return {'count': 0}
    return {'count': len(values), 'minSeconds': values[0], 'medianSeconds': statistics.median(values), 'maxSeconds': values[-1], 'medianSecondsPerAudioSecond': round(statistics.median(ratios), 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--unit', default='attune-api@web')
    parser.add_argument('--normal', type=int, default=10)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    report = {'boundary': 'Generation through the real API on this host. Excludes speech recognition, the language model and browser playback.', 'cases': {}}
    # Cold: restart the API, then ask at once. The request waits for the warm-up.
    subprocess.check_call(['systemctl', 'restart', args.unit])
    started = time.monotonic()
    for _ in range(90):
        try:
            urllib.request.urlopen('http://127.0.0.1:{}/api/health'.format(args.port), timeout=2)
            break
        except Exception:
            time.sleep(1)
    report['apiUpSeconds'] = round(time.monotonic() - started, 1)
    cold = speak(args.port, TEXTS['en'][0], 'en')
    cold['sinceRestartSeconds'] = round(time.monotonic() - started, 1)
    report['cases']['cold'] = {'rows': [cold], 'summary': summary([cold])}
    Path(args.out).write_text(json.dumps(report, indent=1))
    rows = []
    for i in range(args.normal):
        text = TEXTS['en'][i % len(TEXTS['en'])]
        rows.append(speak(args.port, text, 'en'))
        print(rows[-1], flush=True)
    for language in ('tr', 'de'):
        for text in TEXTS[language]:
            rows.append(speak(args.port, text, language))
            print(rows[-1], flush=True)
    report['cases']['normal'] = {'rows': rows, 'summary': summary(rows), 'byLanguage': {lang: summary([r for r in rows if r['language'] == lang]) for lang in TEXTS}}
    Path(args.out).write_text(json.dumps(report, indent=1))
    # Failure: abandon a request mid-generation. The worker is killed; the next request is timed.
    cancelled = {'status': 'cancelled'}
    try:
        speak(args.port, TEXTS['en'][3], 'en', timeout=3)
    except Exception as error:
        cancelled['client'] = type(error).__name__
    after_started = time.monotonic()
    after = None
    for _ in range(60):
        after = speak(args.port, TEXTS['en'][1], 'en')
        if after['status'] != 429:
            break
        time.sleep(1)
    after['sinceCancelSeconds'] = round(time.monotonic() - after_started, 1)
    report['cases']['failure'] = {'rows': [cancelled, after], 'summary': summary([after])}
    (Path(args.out)).write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v['summary'] for k, v in report['cases'].items()}))


if __name__ == '__main__':
    main()
