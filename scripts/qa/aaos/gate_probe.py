#!/usr/bin/env python
"""Watches the AAOS WebView while the host runs other work. The native gate closing removes
the page target (for example on vehicle data older than 2.5 s) and reopening creates a new
one. A request that merely timed out on the busy host is counted apart and is not a closure.

    python gate_probe.py --config aaos-config.json --out probe.json --stop-file FILE
"""
import argparse
import json
from pathlib import Path
import time
import urllib.request


def page_target(port):
    """The page's target id, '' when the WebView reports no page, None when unanswered."""
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=2) as response:
            pages = [t for t in json.load(response) if t.get('url', '').startswith('http://localhost:3000')]
            return pages[0].get('id', '') if pages else ''
    except (OSError, ValueError):
        return None


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
    unanswered = 0
    transitions = []
    last = None
    while not arguments.stop_file.exists() and time.time() - began < arguments.max_seconds:
        target = page_target(port)
        samples += 1
        if target is None:
            unanswered += 1
        else:
            absent += target == ''
            if target != last:
                transitions.append(dict(at=round(time.time() - began, 1), target=target))
                last = target
        time.sleep(1)
    arguments.out.write_text(json.dumps(dict(seconds=round(time.time() - began, 1), samples=samples, absentSamples=absent, unansweredSamples=unanswered, transitions=transitions), indent=1), 'utf8')


if __name__ == '__main__':
    main()
