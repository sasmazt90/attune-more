#!/usr/bin/env python
"""Attribute a browser Skin E2E run: API timeline from evidence.json + resource trace."""
import json
from pathlib import Path
import sys

from run_condition import attribute


def timeline(evidence):
    """Pairs each request with its response by path order, in wall-clock seconds."""
    requests = [r for r in evidence.get('requestTimes', []) if 'capture-check' not in r['path']]
    start = evidence['recordStart'] / 1000
    responses = [r for r in evidence.get('responses', []) if 'capture-check' not in r['path'] and r['path'].startswith('/api/local-health')]
    rows = []
    for request, response in zip(requests, responses):
        began = request['at'] / 1000
        ended = start + response['seconds']
        label = request['path'].rsplit('/', 1)[-1]
        body = response.get('body') or {}
        rows.append(dict(label=f"{label}.{body.get('step')}" if label == 'prepare' else label, status=response['status'], began=began, ended=ended, seconds=round(ended - began, 1), detail=body.get('detail')))
    return rows


def main():
    evidence = json.loads(Path(sys.argv[1]).read_text('utf8'))
    trace = [json.loads(line) for line in Path(sys.argv[2]).read_text('utf8').splitlines() if line.strip()]
    print(json.dumps(dict(status=evidence.get('functionalStatus'), checks=len(evidence.get('checks', [])), error=(evidence.get('error') or '')[:200])))
    for row in timeline(evidence):
        resources = attribute(trace, row['began'], row['ended'])
        groups = resources.get('groups', {})
        worker = groups.get('worker', {})
        print(json.dumps(dict(step=row['label'], status=row['status'], seconds=row['seconds'], detail=row['detail'],
                              availableMiB=resources.get('availableMiB'), cpu=resources.get('cpuPercent', {}).get('mean'),
                              hardFaults=resources.get('hardFaultReadsPerSec', {}).get('mean'),
                              workerRss=worker.get('rssMiB'), workerPrivate=worker.get('privateMiB'), workerCores=worker.get('coresMean'), workerFaults=worker.get('faultsPerSecMean'),
                              browserCores=groups.get('test_browser', {}).get('coresMean'), browserRss=groups.get('test_browser', {}).get('rssMiB'),
                              emulatorCores=groups.get('emulator', {}).get('coresMean'), emulatorRss=groups.get('emulator', {}).get('rssMiB'),
                              userChromeCores=groups.get('user_chrome', {}).get('coresMean'), otherCores=groups.get('other', {}).get('coresMean'))))


if __name__ == '__main__':
    main()
