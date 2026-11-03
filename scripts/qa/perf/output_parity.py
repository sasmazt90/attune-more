#!/usr/bin/env python
"""Output equivalence of the worker path between two checkouts, field by field.

Runs each pose twice in one process per checkout and stores every leaf value. A leaf that
differs between two runs of the same checkout is run-local telemetry; it is reported, and
only a difference across checkouts in any other leaf counts as an output change.

    python output_parity.py capture --checkout DIR --runtime-config FILE --request-dir DIR --out a.json
    python output_parity.py compare a.json b.json --out report.json
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys


# Clocks and process memory reported beside the result. A difference here is not a measurement.
TELEMETRY = re.compile(r'(Ms|Seconds|Bytes)$|\.(timing|timings|profile|resources)\.|nonAcnePreservation\.(after|before)SHA256$')


def flatten(value, prefix=''):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from flatten(item, f'{prefix}.{key}' if prefix else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from flatten(item, f'{prefix}[{index}]')
    else:
        yield prefix, value


def capture_worker(arguments):
    config = json.loads(arguments.runtime_config.read_text('utf8'))
    core = arguments.checkout / 'services' / 'core-api'
    os.environ.update(ATTUNE_LOAD_LOCAL_ENV='0', ATTUNE_EXPERIMENTAL_ACNE_V5='1', ATTUNE_ACNE_V5_MODEL_DIR=config['acneV5Dir'], ATTUNE_REGIONAL_V3_DIR=config['regionalDir'],
                      ATTUNE_DINOV2_DIR=config['dinov2Dir'], HF_HOME=config['hfHome'], HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
    sys.path[:0] = [str(core), config['pythonOverlay']]
    os.chdir(core)
    import local_native_worker as worker
    for step in (*worker.SKIN_PREPARATION_STEPS, 'complete'):
        worker.prepare_skin_step(step)
    runs = {}
    maps = {}
    for pose in ('FRONT', 'RIGHT', 'LEFT'):
        value = json.loads((arguments.request_dir / (pose + '.json')).read_bytes())
        rows = []
        for _ in range(2):
            _, result = worker.skin_analysis(value)
            rows.append(dict(flatten(result)))
        runs[pose] = rows
        regional = (result.get('general') or {}).get('regionalSkinMap') or result.get('regionalSkinMap')
        if regional is not None:
            maps[pose] = regional
    from regional_attach import fuse_regional
    fused = dict(flatten(fuse_regional(maps)))
    arguments.out.write_text(json.dumps(dict(checkout=str(arguments.checkout), runs=runs, fused=fused)), 'utf8')


def compare(arguments):
    first, second = (json.loads(path.read_text('utf8')) for path in (arguments.a, arguments.b))
    report = dict(a=first['checkout'], b=second['checkout'], poses={})
    equal = True
    for pose in first['runs']:
        a1, a2 = first['runs'][pose]
        b1, b2 = second['runs'][pose]
        volatile = {key for key in set(a1) | set(b1) if a1.get(key) != a2.get(key) or b1.get(key) != b2.get(key)}
        changed = sorted(key for key in set(a1) | set(b1) if key not in volatile and a1.get(key) != b1.get(key))
        telemetry = [key for key in changed if TELEMETRY.search(key)]
        measured = [key for key in changed if not TELEMETRY.search(key)]
        unexplained = sorted(key for key in volatile if not TELEMETRY.search(key))
        report['poses'][pose] = dict(leaves=len(a1), runLocalCount=len(volatile), runLocalNotTelemetry=unexplained[:40], telemetryDifferences=telemetry[:40], changedLeaves=measured[:80], changedCount=len(measured))
        equal &= not measured and not unexplained
    fused = sorted(key for key in set(first['fused']) | set(second['fused']) if first['fused'].get(key) != second['fused'].get(key))
    report['fusion'] = dict(leaves=len(first['fused']), changedLeaves=fused[:80], changedCount=len(fused))
    report['identical'] = equal and not fused
    arguments.out.write_text(json.dumps(report, indent=1), 'utf8')
    print(json.dumps(dict(identical=report['identical'], poses={k: dict(leaves=v['leaves'], runLocal=v['runLocalCount'], unexplainedRunLocal=len(v['runLocalNotTelemetry']), telemetry=len(v['telemetryDifferences']), changed=v['changedCount']) for k, v in report['poses'].items()}, fusion=report['fusion']['changedCount'])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    capture = sub.add_parser('capture')
    capture.add_argument('--checkout', required=True, type=Path)
    capture.add_argument('--runtime-config', required=True, type=Path)
    capture.add_argument('--request-dir', required=True, type=Path)
    capture.add_argument('--out', required=True, type=Path)
    versus = sub.add_parser('compare')
    versus.add_argument('a', type=Path)
    versus.add_argument('b', type=Path)
    versus.add_argument('--out', required=True, type=Path)
    arguments = parser.parse_args()
    (capture_worker if arguments.action == 'capture' else compare)(arguments)


if __name__ == '__main__':
    main()
