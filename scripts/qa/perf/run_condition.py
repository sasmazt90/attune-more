#!/usr/bin/env python
"""One measured condition: monitor + command, then per-step resource attribution.

    python run_condition.py --out DIR --tag warm -- python skin_api_bench.py ...
"""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time



def attribute(samples, started, finished):
    rows = [s for s in samples if started <= s['ts'] <= finished + 1]
    if not rows:
        return {}
    system = lambda key: [r['system'][key] for r in rows if r['system'].get(key) is not None]
    out = dict(samples=len(rows))
    if system('availableMiB'):
        out['availableMiB'] = dict(min=min(system('availableMiB')), max=max(system('availableMiB')))
    for key in ('cpuPercent', 'hardFaultReadsPerSec', 'pagesInputPerSec', 'pagesOutputPerSec', 'demandZeroFaultsPerSec', 'privilegedCpuPercent', 'processorPerformancePercent', 'processorFrequencyMHz', 'processorQueueLength', 'diskSecPerRead'):
        if system(key):
            out[key] = dict(mean=round(statistics.fmean(system(key)), 3), max=round(max(system(key)), 3))
    if system('committedBytes'):
        out['committedGiB'] = round(max(system('committedBytes')) / 2**30, 2)
    groups = {}
    for name in sorted({key for r in rows for key in r['groups']}):
        present = [r['groups'][name] for r in rows if name in r['groups']]
        if present:
            groups[name] = dict(
                rssMiB=dict(min=round(min(p['rssMiB'] for p in present)), max=round(max(p['rssMiB'] for p in present))),
                privateMiB=round(max(p['privateMiB'] for p in present)),
                coresMean=round(statistics.fmean(p['cores'] for p in present), 2),
                coresMax=round(max(p['cores'] for p in present), 2),
                kernelCoresMean=round(statistics.fmean(p.get('kernelCores', 0) for p in present), 2),
                faultsPerSecMean=round(statistics.fmean(p['faultsPerSec'] for p in present)),
                threads=max(p.get('threads', 0) for p in present))
    out['groups'] = groups
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--bench-report', type=Path, help='skin_api_bench report whose steps are attributed')
    parser.add_argument('--interval', type=float, default=2.0)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = arguments.command[1:] if arguments.command[:1] == ['--'] else arguments.command
    arguments.out.mkdir(parents=True, exist_ok=True)
    trace = arguments.out / (arguments.tag + '.resources.jsonl')
    stop = arguments.out / (arguments.tag + '.stop')
    stop.unlink(missing_ok=True)
    trace.unlink(missing_ok=True)
    monitor = subprocess.Popen([sys.executable, str(Path(__file__).with_name('resource_monitor.py')), '--out', str(trace), '--stop-file', str(stop), '--interval', str(arguments.interval)])
    time.sleep(arguments.interval * 2)
    started = time.time()
    try:
        exit_code = subprocess.call(command)
    finally:
        finished = time.time()
        time.sleep(arguments.interval * 1.5)
        stop.write_text('stop')
        monitor.wait(30)
        stop.unlink(missing_ok=True)
    samples = [json.loads(line) for line in trace.read_text('utf8').splitlines() if line.strip()]
    summary = dict(tag=arguments.tag, exitCode=exit_code, started=started, finished=finished, seconds=round(finished - started, 1), overall=attribute(samples, started, finished))
    if arguments.bench_report and arguments.bench_report.exists():
        report = json.loads(arguments.bench_report.read_text('utf8'))
        summary['outcome'] = report.get('outcome')
        summary['steps'] = [dict(label=s['label'], status=s['status'], seconds=s['seconds'], detail=s.get('detail'), stableSHA256=s.get('stableSHA256'), resources=attribute(samples, s['started'], s['finished'])) for s in report['steps']]
    (arguments.out / (arguments.tag + '.summary.json')).write_text(json.dumps(summary, indent=1), 'utf8')
    overall = summary['overall']
    print(json.dumps(dict(tag=arguments.tag, exit=exit_code, outcome=summary.get('outcome'), seconds=summary['seconds'], availableMiB=overall.get('availableMiB'), hardFaults=overall.get('hardFaultReadsPerSec'), cpu=overall.get('cpuPercent'), steps=[(s['label'], s['status'], s['seconds']) for s in summary.get('steps', [])])), flush=True)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
