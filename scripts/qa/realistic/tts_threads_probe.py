#!/usr/bin/env python3
"""Compares ways to run the same Chatterbox voice on this host's CPU. Prints timings only. No provider is called.

Run with the API's environment on the WEB host, while nothing else is using the CPU. It starts its own resident workers,
so the running service is not touched. Sentences come from real replies recorded in the Mental journey.
"""
import base64
import io
import json
import os
import subprocess
import sys
import threading
import time
import wave

WORKER = '/opt/attune/services/core-api/mental_neural_resident.py'
FIRST = "It's completely normal to feel anxious about that conversation."
SECOND = "Maybe you could start by sharing your progress and the challenges you're facing."
WHOLE = FIRST + ' ' + SECOND


class Worker:
    def __init__(self, threads):
        env = {**os.environ, 'OMP_NUM_THREADS': str(threads), 'MKL_NUM_THREADS': str(threads), 'ATTUNE_MENTAL_TTS_THREADS': str(threads), 'HF_HUB_DISABLE_TELEMETRY': '1'}
        self.process = subprocess.Popen([os.environ.get('ATTUNE_MENTAL_TTS_PYTHON') or sys.executable, WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, cwd=os.path.dirname(WORKER))
        started = time.monotonic()
        self.ask({'warm': True})
        self.warm = round(time.monotonic() - started, 1)

    def ask(self, extra):
        job = {'config': os.environ['ATTUNE_MENTAL_TTS_CONFIG'], 'language': 'en', **extra}
        self.process.stdin.write((json.dumps(job, ensure_ascii=False) + '\n').encode())
        self.process.stdin.flush()
        return json.loads(self.process.stdout.readline())

    def say(self, text):
        started = time.monotonic()
        reply = self.ask({'text': text})
        seconds = round(time.monotonic() - started, 1)
        with wave.open(io.BytesIO(base64.b64decode(reply['wav']))) as w:
            audio = round(w.getnframes() / w.getframerate(), 1)
        return {'generateSeconds': seconds, 'audioSeconds': audio, 'perAudioSecond': round(seconds / audio, 2)}

    def close(self):
        self.process.kill()
        self.process.wait()


def rss_mb(pid):
    with open('/proc/{}/status'.format(pid)) as status:
        return next(int(line.split()[1]) // 1024 for line in status if line.startswith('VmRSS'))


results = {}
for threads in (4, 8):
    worker = Worker(threads)
    results['one worker, {} threads'.format(threads)] = {'warmSeconds': worker.warm, 'memoryMb': rss_mb(worker.process.pid), 'whole': [worker.say(WHOLE) for _ in range(2)], 'first': worker.say(FIRST), 'second': worker.say(SECOND)}
    worker.close()

for threads in (4,):
    a, b = Worker(threads), Worker(threads)
    outcome = {}
    started = time.monotonic()

    def run(name, worker, text):
        outcome[name] = {**worker.say(text), 'doneAt': round(time.monotonic() - started, 1)}
    jobs = [threading.Thread(target=run, args=('first', a, FIRST)), threading.Thread(target=run, args=('second', b, SECOND))]
    for job in jobs:
        job.start()
    for job in jobs:
        job.join()
    outcome['memoryMbEach'] = rss_mb(a.process.pid)
    results['two workers at once, {} threads each'.format(threads)] = outcome
    a.close()
    b.close()
print(json.dumps(results, indent=1))
