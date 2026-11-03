#!/usr/bin/env python
"""Times what the AAOS journey asks the host for while other work runs: an approved audio clip
from the frontend and the vehicle state from the backend. One JSON line per sample.

    python service_latency.py --clip /audio/.../clip.m4a --out FILE --stop-file FILE
"""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


def timed(url, timeout):
    began = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            size = len(response.read())
            return dict(ms=round((time.perf_counter() - began) * 1000), status=response.status, bytes=size)
    except (urllib.error.URLError, OSError) as error:
        return dict(ms=round((time.perf_counter() - began) * 1000), error=type(error).__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--stop-file', required=True, type=Path)
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--timeout', type=float, default=30)
    arguments = parser.parse_args()
    with arguments.out.open('w', encoding='utf8') as output:
        while not arguments.stop_file.exists():
            row = dict(at=time.time(), clip=timed('http://127.0.0.1:3000' + arguments.clip, arguments.timeout), vehicle=timed('http://127.0.0.1:8000/api/vehicle/state', arguments.timeout))
            output.write(json.dumps(row) + '\n')
            output.flush()
            time.sleep(arguments.interval)


if __name__ == '__main__':
    main()
