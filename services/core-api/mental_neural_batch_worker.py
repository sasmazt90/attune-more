"""Task-only offline resident worker. Never used by the live speech endpoint."""
import base64
import contextlib
import json
import sys
from mental_neural_worker import synthesize


def main():
    if len(sys.argv) != 2:raise ValueError('CONFIG_ARGUMENT_REQUIRED')
    runtime = {}
    for _ in range(414):
        raw = sys.stdin.buffer.readline(32769)
        if not raw:return
        if len(raw)>32768 or not raw.endswith(b'\n'):raise ValueError('INPUT_TOO_LARGE')
        request = json.loads(raw)
        if set(request) != {'language', 'text', 'seed'}:raise ValueError('INVALID_REQUEST')
        request['config'] = sys.argv[1]
        with contextlib.redirect_stdout(sys.stderr):
            audio = synthesize(request, runtime)
        sys.stdout.write(json.dumps({'wav':base64.b64encode(audio).decode('ascii')})+'\n')
        sys.stdout.flush()


if __name__=='__main__':
    try:main()
    except Exception:sys.exit(1)
