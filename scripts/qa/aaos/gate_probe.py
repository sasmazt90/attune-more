#!/usr/bin/env python
"""Watches the AAOS WebView while the host runs other work: any loss of the page target is
the native gate closing it (for example on vehicle data older than 2.5 s).

    python gate_probe.py --config aaos-config.json --out probe.json --stop-file FILE
"""
import argparse
import json
from pathlib import Path
import time
import urllib.request


def page_present(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=2) as response:
            return any(t.get('url', '').startswith('http://localhost:3000') for t in json.load(response))
    except (OSError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--stop-file', required=True, type=Path)
    parser.add_argument('--max-seconds', type=float, default=900)
    arguments = parser.parse_args()
    config = json.loads(arguments.config.read_text('utf-8-sig'))
    port = config.get('devtoolsPort', 19226)
    began = time.time()
    samples = 0
    absent = 0
    transitions = []
    last = None
    while not arguments.stop_file.exists() and time.time() - began < arguments.max_seconds:
        present = page_present(port)
        samples += 1
        absent += not present
        if present != last:
            transitions.append(dict(at=round(time.time() - began, 1), present=present))
            last = present
        time.sleep(1)
    arguments.out.write_text(json.dumps(dict(seconds=round(time.time() - began, 1), samples=samples, absentSamples=absent, transitions=transitions), indent=1), 'utf8')


if __name__ == '__main__':
    main()
