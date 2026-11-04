#!/usr/bin/env python
"""Condition F: the reserve guard on the real worker path, without exhausting the host.

Only the available-RAM reading is replaced, for a bounded part of one real analysis. The
worker's own error mapping then has to produce the 503 code, and the same worker has to
complete the identical request once the reading is real again.

    python guard_probe.py --runtime-config FILE --request-dir DIR --out report.json
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

REPOSITORY = Path(__file__).resolve().parents[3]
CORE_API = REPOSITORY / 'services' / 'core-api'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-config', required=True, type=Path)
    parser.add_argument('--request-dir', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    arguments = parser.parse_args()
    config = json.loads(arguments.runtime_config.read_text('utf-8-sig'))
    os.environ.update(ATTUNE_LOAD_LOCAL_ENV='0', ATTUNE_EXPERIMENTAL_ACNE_V5='1', ATTUNE_ACNE_V5_MODEL_DIR=config['acneV5Dir'], ATTUNE_REGIONAL_V3_DIR=config['regionalDir'],
                      ATTUNE_DINOV2_DIR=config['dinov2Dir'], HF_HOME=config['hfHome'], HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
    sys.path[:0] = [str(CORE_API), config['pythonOverlay']]
    os.chdir(CORE_API)
    import psutil
    import local_native_worker as worker
    for step in (*worker.SKIN_PREPARATION_STEPS, 'complete'):
        worker.prepare_skin_step(step)
    value = json.loads((arguments.request_dir / 'RIGHT.json').read_bytes())
    report = dict(mode='Real worker path; only psutil.virtual_memory().available is replaced during the guarded run.', cases=[])
    real = psutil.virtual_memory

    def attempt(label, available_mib):
        psutil.virtual_memory = (lambda: SimpleNamespace(available=available_mib * 2**20)) if available_mib is not None else real
        began = time.perf_counter()
        try:
            worker.execute('skin', value)
            outcome = dict(status=200, code=None)
        except Exception as error:  # noqa: BLE001 - the mapping under test receives any exception
            status, code = worker.failure_response(error)
            outcome = dict(status=status, code=code)
        finally:
            psutil.virtual_memory = real
        report['cases'].append(dict(label=label, availableMiB=available_mib, seconds=round(time.perf_counter() - began, 1), **outcome))
        print(json.dumps(report['cases'][-1]), flush=True)
        return outcome

    below = attempt('399 MiB: below the 400 MiB reserve', 399)
    above = attempt('401 MiB: just above the reserve', 401)
    recovered = attempt('Real host reading, same worker', None)
    report['pass'] = below == dict(status=503, code='LOCAL_MEMORY_RESERVE') and above['status'] == 200 and recovered['status'] == 200
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(report, indent=1), 'utf8')
    print(json.dumps(dict(passed=report['pass'])), flush=True)
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
