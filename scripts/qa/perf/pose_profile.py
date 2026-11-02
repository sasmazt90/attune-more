#!/usr/bin/env python
"""Where one pose's analysis time goes, with the exact worker code path and thread lanes.

No HTTP and no deadline: stage timing only. Runs the worker's own prepare + analysis
functions in this process, repeats a pose, and reports the slowest project functions.

    python pose_profile.py --runtime-config FILE --request-dir DIR --out report.json
"""
import argparse
import cProfile
import json
import os
from pathlib import Path
import pstats
import sys
import threading
import time

REPOSITORY = Path(__file__).resolve().parents[3]
CORE_API = REPOSITORY / 'services' / 'core-api'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-config', required=True, type=Path)
    parser.add_argument('--request-dir', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--poses', default='FRONT,RIGHT')
    parser.add_argument('--top', type=int, default=45)
    arguments = parser.parse_args()
    config = json.loads(arguments.runtime_config.read_text('utf8'))
    os.environ.update(ATTUNE_LOAD_LOCAL_ENV='0', ATTUNE_EXPERIMENTAL_ACNE_V5='1', ATTUNE_ACNE_V5_MODEL_DIR=config['acneV5Dir'], ATTUNE_REGIONAL_V3_DIR=config['regionalDir'],
                      ATTUNE_DINOV2_DIR=config['dinov2Dir'], HF_HOME=config['hfHome'], HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
    sys.path[:0] = [str(CORE_API), config['pythonOverlay']]
    os.chdir(CORE_API)
    import psutil
    process = psutil.Process()
    report = dict(prepare=[], poses=[], samples=[])

    def save():
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_text(json.dumps(report, indent=1), 'utf8')

    def sampler():
        while True:
            memory = process.memory_info()
            report['samples'].append(dict(ts=round(time.time(), 2), rssMiB=round(memory.rss / 2**20), privateMiB=round(memory.private / 2**20), availableMiB=round(psutil.virtual_memory().available / 2**20), threads=process.num_threads()))
            time.sleep(1)

    threading.Thread(target=sampler, daemon=True).start()
    # Importing the worker applies the same native thread lanes as production.
    import local_native_worker as worker

    for step in (*worker.SKIN_PREPARATION_STEPS, 'complete'):
        began = time.perf_counter()
        before = process.memory_info()
        worker.prepare_skin_step(step)
        after = process.memory_info()
        report['prepare'].append(dict(step=step, seconds=round(time.perf_counter() - began, 2), rssDeltaMiB=round((after.rss - before.rss) / 2**20), privateDeltaMiB=round((after.private - before.private) / 2**20), rssMiB=round(after.rss / 2**20), privateMiB=round(after.private / 2**20)))
        print(json.dumps(report['prepare'][-1]), flush=True)
    import torch
    report['threads'] = dict(torch=torch.get_num_threads(), interop=torch.get_num_interop_threads(), omp=os.environ.get('OMP_NUM_THREADS'))
    try:
        from threadpoolctl import threadpool_info
        report['threads']['pools'] = [dict(api=p.get('user_api'), library=Path(p.get('filepath', '')).name, threads=p.get('num_threads')) for p in threadpool_info()]
    except ImportError:
        pass
    save()
    for pose in arguments.poses.split(','):
        value = json.loads((arguments.request_dir / (pose + '.json')).read_bytes())
        # The first repetition settles lazy imports; the second is the steady profile.
        for repetition in ('first', 'steady'):
            profile = cProfile.Profile()
            began = time.perf_counter()
            cpu = process.cpu_times()
            faults = process.memory_info().num_page_faults
            profile.enable()
            worker.skin_analysis(value)
            profile.disable()
            seconds = time.perf_counter() - began
            used = process.cpu_times()
            stats = pstats.Stats(profile)
            rows = []
            for (filename, line, name), (_, calls, total, cumulative, _) in stats.stats.items():
                short = Path(filename).name
                if cumulative < .15:
                    continue
                rows.append(dict(function=f'{short}:{line}:{name}', calls=calls, cumulative=round(cumulative, 2), own=round(total, 2)))
            rows.sort(key=lambda row: -row['cumulative'])
            report['poses'].append(dict(pose=pose, repetition=repetition, seconds=round(seconds, 2), cpuUser=round(used.user - cpu.user, 2), cpuKernel=round(used.system - cpu.system, 2), pageFaults=process.memory_info().num_page_faults - faults, top=rows[:arguments.top]))
            print(json.dumps({k: report['poses'][-1][k] for k in ('pose', 'repetition', 'seconds', 'cpuUser', 'cpuKernel', 'pageFaults')}), flush=True)
            save()


if __name__ == '__main__':
    main()
