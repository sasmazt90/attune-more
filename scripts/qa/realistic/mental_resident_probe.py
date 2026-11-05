"""Equivalent synthetic speech probes; no provider calls, altered weights or saved user data."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import sys
import time
import wave

p = argparse.ArgumentParser()
p.add_argument('--source', default='/opt/attune/services/core-api')
p.add_argument('--config', required=True)
p.add_argument('--out', required=True)
p.add_argument('--repetitions', type=int, default=2)
args = p.parse_args()
out = Path(args.out)
out.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, args.source)
from mental_neural_worker import synthesize
from mental_neural_tts import worker_progress

texts = {
    'en': ['That sounds like a difficult day for you.', 'What would feel most useful to discuss right now?'],
    'de': ['Das klingt nach einem schwierigen Tag für Sie.', 'Was wäre für Sie jetzt besonders hilfreich zu besprechen?'],
    'tr': ['Bugün sizin için zor bir gün olmuş gibi görünüyor.', 'Şu anda konuşmak size hangi konuda yardımcı olur?'],
}
progress = out / 'worker-progress.json'
os.environ['ATTUNE_MENTAL_TTS_PROGRESS'] = str(progress)
runtime = {}
rows = []
subphases = {}


def timed(owner, name, label):
    original = getattr(owner, name)
    def call(*a, **kw):
        start = time.perf_counter()
        try:
            return original(*a, **kw)
        finally:
            subphases[label] = subphases.get(label, 0) + time.perf_counter() - start
    setattr(owner, name, call)


def say(language, text, label, seed):
    subphases.clear()
    start = time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr):
        audio = synthesize({'config': args.config, 'language': language, 'text': text, 'seed': seed}, runtime)
    elapsed = time.perf_counter() - start
    with wave.open(io.BytesIO(audio)) as wav:
        duration = wav.getnframes() / wav.getframerate()
    (out / (label + '.wav')).write_bytes(audio)
    row = {'label': label, 'language': language, 'seed': seed, 'textSha256': hashlib.sha256(text.encode()).hexdigest(),
           'seconds': elapsed, 'audioSeconds': duration, 'realTimeFactor': elapsed / duration,
           'audioSha256': hashlib.sha256(audio).hexdigest(), 'phases': worker_progress(progress),
           'subphasesSeconds': dict(subphases), 'peakRSSKiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    rows.append(row)
    (out / 'results.json').write_text(json.dumps({'scope': 'Same pinned worker, synthetic text, numerical wrappers only; no subjective acceptance',
        'threads': os.environ.get('ATTUNE_MENTAL_TTS_THREADS'), 'rows': rows}, indent=2) + '\n')
    print(json.dumps({k: row[k] for k in ('label', 'seconds', 'audioSeconds', 'subphasesSeconds')}), flush=True)


say('en', 'Hello.', 'warmup', 42)
model = runtime['model']
timed(model.t3, 'inference', 'speechTokens')
timed(model.s3gen, 'inference', 'waveDecoder')
timed(model.watermarker, 'apply_watermark', 'watermark')
timed(model, 'prepare_conditionals', 'conditioning')
for repeat in range(args.repetitions):
    for language, parts in texts.items():
        for part, text in enumerate(parts):
            say(language, text, language + '-' + str(repeat) + '-' + str(part), 42 + repeat)
