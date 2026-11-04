#!/usr/bin/env python
"""Controlled runtime-option experiments on the exact worker path, one process per variant.

Options are applied from outside the product code, so a variant is proven before any
source changes. Reports per-pose time, memory, page faults and per-field output digests.

    python runtime_variant.py --runtime-config FILE --request-dir DIR --out DIR --variant NAME --options JSON
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

REPOSITORY = Path(__file__).resolve().parents[3]
CORE_API = REPOSITORY / 'services' / 'core-api'
TIMING_KEYS = ('timing', 'elapsed', 'latency', 'duration', 'seconds', 'profile', 'loadms', 'inferencems')


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if not any(t in k.lower() for t in TIMING_KEYS) and not k.lower().endswith('ms')}
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def apply_options(options):
    import onnxruntime as ort
    original = ort.InferenceSession
    report = []

    def session(source, sess_options=None, *args, **kwargs):
        name = Path(source).name if isinstance(source, (str, os.PathLike)) else f'<{len(source)} bytes>'
        encoder = name == 'encoder.onnx'
        scope = options.get('encoder' if encoder else 'others', {})
        if sess_options is not None:
            if 'arena' in scope:
                sess_options.enable_cpu_mem_arena = scope['arena']
            if 'pattern' in scope:
                sess_options.enable_mem_pattern = scope['pattern']
            if 'spin' in scope:
                sess_options.add_session_config_entry('session.intra_op.allow_spinning', '1' if scope['spin'] else '0')
            if 'intra' in scope:
                sess_options.intra_op_num_threads = scope['intra']
            report.append(dict(model=name, arena=sess_options.enable_cpu_mem_arena, pattern=sess_options.enable_mem_pattern, intra=sess_options.intra_op_num_threads))
        return original(source, sess_options, *args, **kwargs)

    ort.InferenceSession = session
    if 'batch' in options:
        import material_component_features as material
        init = material.OnnxMaterialEncoder.__init__

        def patched(self, path, receipt, intra_op_threads=1, batch_limit=16, cpu_mem_arena=True):
            init(self, path, receipt, intra_op_threads, options['batch'], cpu_mem_arena)

        material.OnnxMaterialEncoder.__init__ = patched
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-config', required=True, type=Path)
    parser.add_argument('--request-dir', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--variant', required=True)
    parser.add_argument('--options', default='{}')
    parser.add_argument('--sequence', default='FRONT,FRONT,RIGHT,LEFT')
    arguments = parser.parse_args()
    options = json.loads(arguments.options)
    config = json.loads(arguments.runtime_config.read_text('utf8'))
    os.environ.update(ATTUNE_LOAD_LOCAL_ENV='0', ATTUNE_EXPERIMENTAL_ACNE_V5='1', ATTUNE_ACNE_V5_MODEL_DIR=config['acneV5Dir'], ATTUNE_REGIONAL_V3_DIR=config['regionalDir'],
                      ATTUNE_DINOV2_DIR=config['dinov2Dir'], HF_HOME=config['hfHome'], HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
    os.environ.update(options.get('env', {}))
    sys.path[:0] = [str(CORE_API), config['pythonOverlay']]
    os.chdir(CORE_API)
    import psutil
    process = psutil.Process()
    report = dict(variant=arguments.variant, options=options, prepare=[], poses=[], started=time.time())
    arguments.out.mkdir(parents=True, exist_ok=True)
    path = arguments.out / (arguments.variant + '.variant.json')

    def save():
        path.write_text(json.dumps(report, indent=1), 'utf8')

    peak = dict(rss=0, private=0, minAvailable=1 << 60)

    def sampler():
        while True:
            memory = process.memory_info()
            peak['rss'] = max(peak['rss'], memory.rss)
            peak['private'] = max(peak['private'], memory.private)
            peak['minAvailable'] = min(peak['minAvailable'], psutil.virtual_memory().available)
            time.sleep(.5)

    threading.Thread(target=sampler, daemon=True).start()
    import local_native_worker as worker
    # After import: the product assigns its own lanes at module load.
    for key, value in options.get('env', {}).items():
        os.environ[key] = value
    sessions = apply_options(options)
    began = time.perf_counter()
    for step in (*worker.SKIN_PREPARATION_STEPS, 'complete'):
        worker.prepare_skin_step(step)
    report['prepareSeconds'] = round(time.perf_counter() - began, 2)
    report['afterPrepare'] = dict(rssMiB=round(process.memory_info().rss / 2**20), privateMiB=round(process.memory_info().private / 2**20))
    import torch
    if 'torchThreads' in options:
        torch.set_num_threads(options['torchThreads'])
    report['torchThreads'] = torch.get_num_threads()
    report['sessions'] = sessions
    save()
    for pose in arguments.sequence.split(','):
        value = json.loads((arguments.request_dir / (pose + '.json')).read_bytes())
        before = process.memory_info().num_page_faults
        cpu = process.cpu_times()
        began = time.perf_counter()
        _, result = worker.skin_analysis(value)
        seconds = time.perf_counter() - began
        used = process.cpu_times()
        clean = stable(result)
        report['poses'].append(dict(pose=pose, seconds=round(seconds, 2), cpuUser=round(used.user - cpu.user, 2), cpuKernel=round(used.system - cpu.system, 2), pageFaults=process.memory_info().num_page_faults - before,
                                    peakRssMiB=round(peak['rss'] / 2**20), peakPrivateMiB=round(peak['private'] / 2**20), minAvailableMiB=round(peak['minAvailable'] / 2**20), stableSHA256=digest(clean), fields={k: digest(v) for k, v in clean.items()}))
        row = report['poses'][-1]
        print(json.dumps({k: row[k] for k in ('pose', 'seconds', 'cpuUser', 'cpuKernel', 'pageFaults', 'peakRssMiB', 'peakPrivateMiB', 'minAvailableMiB')} | dict(variant=arguments.variant, sha=row['stableSHA256'][:12])), flush=True)
        save()


if __name__ == '__main__':
    main()
