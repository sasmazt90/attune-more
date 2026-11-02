#!/usr/bin/env python
"""Real Skin HTTP path without a browser: prepare steps -> poses -> regional fusion.

Hits the same bounded endpoints and the same 90 s server deadline as the product,
and records a stable digest per pose so timing runs double as output-equivalence
evidence. Request files stay local; only counters and digests reach the report.

    python skin_api_bench.py --request-dir DIR --out report.json --tag warm
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

PREPARE_STEPS = ('dryness', 'skinmap', 'findings', 'acnes', 'regional', 'wrinkles', 'classifier', 'type', 'complete')
POSES = ('FRONT', 'RIGHT', 'LEFT')
VOLATILE = ('timing', 'elapsed', 'latency', 'duration')


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items()
                if not any(t in k.lower() for t in VOLATILE) and not k.lower().endswith(('ms', 'seconds'))}
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def post(base, path, body, timeout):
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=raw, headers={'Content-Type': 'application/json'}, method='POST')
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
        try:
            payload = json.loads(error.read())
        except ValueError:
            payload = {}
    except (urllib.error.URLError, TimeoutError) as error:
        status = 0
        payload = {'detail': type(error).__name__}
    return status, payload, started, time.time()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    parser.add_argument('--request-dir', required=True, type=Path, help='Holds FRONT.json, RIGHT.json, LEFT.json')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--no-prepare', action='store_true')
    parser.add_argument('--no-fuse', action='store_true')
    parser.add_argument('--poses', default=','.join(POSES))
    parser.add_argument('--transport-seconds', type=float, default=95.0)
    arguments = parser.parse_args()

    report = dict(tag=arguments.tag, started=time.time(), steps=[], outcome='RUNNING')

    def save():
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_text(json.dumps(report, indent=1), 'utf8')

    def run(label, path, body, timeout):
        status, payload, started, finished = post(arguments.base, path, body, timeout)
        row = dict(label=label, status=status, started=round(started, 2), finished=round(finished, 2), seconds=round(finished - started, 2))
        if status != 200:
            row['detail'] = payload.get('detail')
        report['steps'].append(row)
        save()
        print(json.dumps(row), flush=True)
        return status, payload, row

    maps = {}
    try:
        if not arguments.no_prepare:
            for step in PREPARE_STEPS:
                status, _, _ = run('prepare.' + step, '/api/local-health/skin/prepare', dict(processingConsent=True, step=step), arguments.transport_seconds)
                if status != 200:
                    report['outcome'] = 'FAIL_PREPARE'
                    return
        for pose in arguments.poses.split(','):
            raw = (arguments.request_dir / (pose + '.json')).read_bytes()
            status, payload, row = run('skin.' + pose, '/api/local-health/skin', raw, arguments.transport_seconds)
            if status != 200:
                report['outcome'] = 'FAIL_' + pose
                return
            row['requestSHA256'] = hashlib.sha256(raw).hexdigest()
            row['photoId'] = payload.get('photoId')
            row['stableSHA256'] = digest(stable(payload))
            row['fields'] = {k: digest(v) for k, v in stable(payload).items()}
            regional = (payload.get('general') or {}).get('regionalSkinMap') or payload.get('regionalSkinMap')
            if regional is not None:
                maps[pose] = regional
            save()
        if not arguments.no_fuse and maps:
            status, payload, row = run('fuse', '/api/local-health/skin/regional-fuse', dict(processingConsent=True, maps=maps), 35.0)
            if status != 200:
                report['outcome'] = 'FAIL_FUSE'
                return
            row['stableSHA256'] = digest(stable(payload))
        report['outcome'] = 'PASS'
    finally:
        report['finished'] = time.time()
        save()
        print(json.dumps(dict(tag=arguments.tag, outcome=report['outcome'])), flush=True)


if __name__ == '__main__':
    main()
