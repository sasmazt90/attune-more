#!/usr/bin/env python
"""Runs tagged Skin API benchmarks under the resource monitor, one after another.

    python bench_series.py --out DIR --request-dir DIR tag1 tag2 ...
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--request-dir', required=True, type=Path)
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('tags', nargs='+')
    arguments = parser.parse_args()
    arguments.out.mkdir(parents=True, exist_ok=True)
    exit_code = 0
    for tag in arguments.tags:
        report = arguments.out / (tag + '.bench.json')
        exit_code |= subprocess.call([sys.executable, str(HERE / 'run_condition.py'), '--out', str(arguments.out), '--tag', tag, '--interval', str(arguments.interval), '--bench-report', str(report),
                                      '--', sys.executable, str(HERE / 'skin_api_bench.py'), '--request-dir', str(arguments.request_dir), '--out', str(report), '--tag', tag])
        summary = json.loads((arguments.out / (tag + '.summary.json')).read_text('utf8'))
        for step in summary.get('steps', []):
            resources = step['resources']
            worker = resources.get('groups', {}).get('worker', {})
            print(json.dumps(dict(tag=tag, step=step['label'], status=step['status'], seconds=step['seconds'], detail=step['detail'], sha=(step.get('stableSHA256') or '')[:12],
                                  availMin=(resources.get('availableMiB') or {}).get('min'), cpu=(resources.get('cpuPercent') or {}).get('mean'), hardFaults=(resources.get('hardFaultReadsPerSec') or {}).get('mean'),
                                  rss=(worker.get('rssMiB') or {}).get('max'), private=worker.get('privateMiB'), cores=worker.get('coresMean'), kernel=worker.get('kernelCoresMean'), faults=worker.get('faultsPerSecMean'))), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
