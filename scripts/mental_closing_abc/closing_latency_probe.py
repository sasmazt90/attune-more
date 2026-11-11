#!/usr/bin/env python3
"""Measure the dynamic closing-summary speech path with synthetic, non-personal texts.

Drives the product's resident worker loop (``mental_neural_resident.serve``) in the
same order the live service sees it: the official-default model is warmed first, as at
service start, then female-calm-v1 summary parts arrive. The first female request
therefore includes loading the female model, exactly like the first closing after boot.

Texts are split with the same rule as ``speechParts`` in mentalNeuralSpeech.ts. No seed
is passed, as in the live endpoint. Nothing is cached or written outside ``--out``.
This measures synthesis on this host only; it does not measure browser playback.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import wave

SUMMARIES = {
    'tr': 'İş yerindeki yoğun tempodan ve son haftalarda bozulan uyku düzeninden söz ettiniz. '
          'Akşamları kısa yürüyüşlerin size iyi geldiğini belirttiniz.',
    'en': 'You talked about the heavy pace at work and your sleep being disrupted in recent weeks. '
          'You mentioned that short evening walks help you.',
    'de': 'Sie haben über das hohe Arbeitstempo und Ihren in den letzten Wochen gestörten Schlaf gesprochen. '
          'Sie erwähnten, dass Ihnen kurze Abendspaziergänge guttun.',
}
FIRST_PART_MIN_WORDS = 6


def speech_parts(text):
    """Port of speechParts(): first sentence(s) up to >= 6 words, then the rest."""
    sentences = [s for s in re.split(r'(?<=[.!?…])\s+|(?<=[.!?…]["\'”’)])\s+', text.strip()) if s]
    at, first = 1, sentences[0] if sentences else ''
    while at < len(sentences) and len(first.split()) < FIRST_PART_MIN_WORDS:
        first += ' ' + sentences[at]
        at += 1
    rest = ' '.join(sentences[at:])
    return [first, rest] if rest else [text]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--official-config', required=True)
    parser.add_argument('--female-config', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(Path(args.source) / 'services/core-api'))
    from mental_neural_tts import load_configuration
    import mental_neural_resident

    # Per-request integrity cost of the female path (verify_speaker re-hashes the bundle).
    verify = []
    for language in ('tr', 'en', 'de'):
        started = time.perf_counter()
        load_configuration(args.female_config, language)
        verify.append({'language': language, 'seconds': round(time.perf_counter() - started, 3)})

    plan = [{'label': 'official-warm', 'config': args.official_config, 'language': 'en', 'warm': True}]
    for language in ('tr', 'en', 'de'):
        for index, part in enumerate(speech_parts(SUMMARIES[language])):
            plan.append({'label': f'{language}-part{index}', 'config': args.female_config, 'language': language,
                         'text': part, 'speakerProfile': 'female-calm-v1'})
    for language in ('tr', 'en', 'de'):  # second pass: all-warm first part
        plan.append({'label': f'{language}-part0-repeat', 'config': args.female_config, 'language': language,
                     'text': speech_parts(SUMMARIES[language])[0], 'speakerProfile': 'female-calm-v1'})
    rows = []
    sent = {}

    def lines():
        for job in plan:
            sent['at'] = time.perf_counter()
            sent['load'] = [round(x, 2) for x in os.getloadavg()]
            sent['job'] = job
            request = {k: v for k, v in job.items() if k != 'label'}
            yield json.dumps(request, ensure_ascii=False).encode() + b'\n'

    def reply(value):
        job = sent['job']
        row = {'label': job['label'], 'language': job['language'], 'profile': job.get('speakerProfile', 'official-default'),
               'seconds': round(time.perf_counter() - sent['at'], 3), 'start': value.get('start'),
               'error': bool(value.get('error')), 'phases': value.get('phases'), 'hostLoadBefore': sent['load']}
        if 'text' in job:
            row['text'] = job['text']
            row['textSha256'] = hashlib.sha256(job['text'].encode()).hexdigest()
        if 'wav' in value:
            import base64
            audio = base64.b64decode(value['wav'])
            with wave.open(io.BytesIO(audio)) as w:
                row['audioSeconds'] = w.getnframes() / w.getframerate()
            row['sha256'] = hashlib.sha256(audio).hexdigest()
            row['bytes'] = len(audio)
            (out / (job['label'] + '.wav')).write_bytes(audio)
        rows.append(row)
        (out / 'latency.json').write_text(json.dumps({
            'schema': 'attune-mental-closing-latency-probe-v1',
            'scope': 'Product resident worker loop, synthetic non-personal summaries, this host; no browser/provider/ASR.',
            'threads': os.environ.get('ATTUNE_MENTAL_TTS_THREADS'), 'summaries': SUMMARIES,
            'parts': {k: speech_parts(v) for k, v in SUMMARIES.items()},
            'perRequestVerifySeconds': verify, 'rows': rows}, ensure_ascii=False, indent=2) + '\n', 'utf-8')
        print(json.dumps({k: row.get(k) for k in ('label', 'seconds', 'start', 'audioSeconds', 'error')}), flush=True)

    mental_neural_resident.serve(lines(), reply)


if __name__ == '__main__':
    main()
