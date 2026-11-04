"""Opt-in resident worker for the live speech endpoint. Same synthesis path as the one-shot worker.

One request per line on stdin, one JSON reply per line on stdout. The parent kills this process to
cancel inference, so a cancelled request leaves nothing behind. Text is never logged.
"""
import base64
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile

from mental_neural_worker import synthesize

WARM_TEXT = {'tr': 'Merhaba.', 'en': 'Hello.', 'de': 'Hallo.'}
MAX_LINE = 32768


def serve(lines, reply):
    """A model belongs to its configuration, because a reference voice changes its conditioning."""
    models = {}
    runtimes = {}
    scratch = tempfile.TemporaryDirectory(prefix='attune-tts-')
    progress = Path(scratch.name) / 'progress.json'
    os.environ['ATTUNE_MENTAL_TTS_PROGRESS'] = str(progress)
    for raw in lines:
        if len(raw) > MAX_LINE or not raw.endswith(b'\n'):
            raise ValueError('INPUT_TOO_LARGE')
        request = json.loads(raw)
        config, language = request['config'], request['language']
        warm = request.get('warm') is True
        runtime = runtimes.setdefault((config, language), {})
        loaded = config in models
        if loaded:
            runtime['model'] = models[config]
        job = {'config': config, 'language': language, 'text': WARM_TEXT[language] if warm else request['text']}
        if request.get('speakerProfile'):
            job['speakerProfile'] = request['speakerProfile']
        try:
            with contextlib.redirect_stdout(sys.stderr):
                audio = synthesize(job, runtime)
        except Exception:
            # No message crosses this boundary: it could contain user text or local paths.
            reply({'error': True})
            continue
        models[config] = runtime['model']
        phases = json.loads(progress.read_text('utf-8')) if progress.exists() else []
        out = {'start': 'warm' if loaded else 'cold', 'phases': phases}
        if not warm:
            out['wav'] = base64.b64encode(audio).decode('ascii')
        reply(out)


def main():
    # Libraries can write to file descriptor 1. Only this private copy carries the protocol.
    protocol = os.fdopen(os.dup(1), 'wb')
    os.dup2(2, 1)

    def reply(value):
        protocol.write(json.dumps(value).encode() + b'\n')
        protocol.flush()

    serve(iter(lambda: sys.stdin.buffer.readline(MAX_LINE + 1), b''), reply)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        sys.exit(1)
