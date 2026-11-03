#!/usr/bin/env python
"""Condition E: a cancelled or vehicle-stopped analysis leaves no orphan and no late result.

Over real HTTP against a running QA backend: disconnects the client during a pose and moves
the vehicle during a pose, observes the worker process at the OS level, then proves the next
analysis completes with the same measurement digests.

    python skin_recovery.py --request-dir DIR --out report.json
"""
import argparse
import json
from pathlib import Path
import socket
import time

import psutil

from skin_api_bench import PREPARE_STEPS, digest, post, stable

BASE = 'http://127.0.0.1:8000'


def workers():
    found = []
    for process in psutil.process_iter(['pid', 'name']):
        try:
            if (process.info['name'] or '').lower().startswith('python') and 'local_native_worker' in ' '.join(process.cmdline()):
                found.append(process.pid)
        except (psutil.Error, OSError):
            pass
    return found


def wait_until(test, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if test():
            return True
        time.sleep(.25)
    return False


def prepare():
    for step in PREPARE_STEPS:
        status, payload, _, _ = post(BASE, '/api/local-health/skin/prepare', dict(processingConsent=True, step=step), 95)
        if status != 200:
            raise SystemExit(f'prepare {step}: {status} {payload}')


def analyse(raw):
    status, payload, began, ended = post(BASE, '/api/local-health/skin', raw, 95)
    return status, payload, round(ended - began, 1)


def disconnect_during_pose(raw, after_seconds):
    """Sends the whole request, then closes the socket without reading the response."""
    head = f'POST /api/local-health/skin HTTP/1.1\r\nHost: 127.0.0.1:8000\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\n\r\n'.encode()
    with socket.create_connection(('127.0.0.1', 8000), timeout=30) as connection:
        connection.sendall(head + raw)
        time.sleep(after_seconds)


def speed(value):
    return post(BASE, '/api/vehicle/speed', dict(speedKmH=value), 10)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request-dir', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    arguments = parser.parse_args()
    raw = (arguments.request_dir / 'RIGHT.json').read_bytes()
    report = dict(started=time.time(), checks=[])

    def check(what, passed, observed=None):
        report['checks'].append(dict(what=what, passed=bool(passed), observed=observed))
        arguments.out.write_text(json.dumps(report, indent=1), 'utf8')
        print(('PASS ' if passed else 'FAIL ') + what, flush=True)

    prepare()
    status, reference, seconds = analyse(raw)
    check('Reference pose completes', status == 200, seconds)
    expected = {k: digest(v) for k, v in stable(reference).items() if k not in ('acneRuntime', 'drynessRuntime')}

    before = workers()
    check('One worker before the disconnect', len(before) == 1, before)
    disconnect_during_pose(raw, 6)
    check('Client disconnect kills the running worker', wait_until(lambda: before[0] not in workers(), 15), workers())
    check('No orphan worker remains', wait_until(lambda: not workers(), 5), workers())

    prepare()
    status, result, seconds = analyse(raw)
    check('Next analysis after the disconnect completes', status == 200, seconds)
    check('Same measurement output after the disconnect', {k: digest(v) for k, v in stable(result).items() if k not in ('acneRuntime', 'drynessRuntime')} == expected)

    before = workers()
    outcome = {}

    def moving():
        time.sleep(5)
        speed(40)

    import threading
    thread = threading.Thread(target=moving)
    thread.start()
    status, payload, seconds = analyse(raw)
    thread.join()
    outcome.update(status=status, detail=payload.get('detail'), seconds=seconds)
    check('DRIVE during a pose stops it: 409, no result', status == 409 and payload.get('detail') == 'CANCELLED', outcome)
    check('DRIVE kills the worker', wait_until(lambda: before[0] not in workers(), 15), workers())
    # The gate answers before reading a body, so a small request is enough.
    status, payload, _, _ = post(BASE, '/api/local-health/skin', dict(processingConsent=True), 20)
    check('Analysis stays refused while moving', status == 409 and payload.get('detail') == 'PARK_REQUIRED', dict(status=status, detail=payload.get('detail')))
    speed(0)
    prepare()
    status, result, seconds = analyse(raw)
    check('After PARK the analysis completes with the same output', status == 200 and {k: digest(v) for k, v in stable(result).items() if k not in ('acneRuntime', 'drynessRuntime')} == expected, seconds)
    report['status'] = 'PASS' if all(row['passed'] for row in report['checks']) else 'FAIL'
    report['finished'] = time.time()
    arguments.out.write_text(json.dumps(report, indent=1), 'utf8')
    print(report['status'], flush=True)


if __name__ == '__main__':
    main()
