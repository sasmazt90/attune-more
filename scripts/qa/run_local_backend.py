#!/usr/bin/env python
"""Source-controlled launcher for the local QA backend.

Replaces the undocumented outputs/run_repair_backend.py. Model locations come
from an explicit machine-local JSON file (see local-runtime.example.json), so a
run never depends on a hard-coded install directory or a deployment manifest.
Only the checkout that contains this script is executed; no install is mutated.

    python scripts/qa/run_local_backend.py --runtime-config C:/path/local-runtime.json --data-dir C:/path/data

Stops when --stop-file appears, or on EOF of stdin without --stop-file.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

REPOSITORY = Path(__file__).resolve().parents[2]
CORE_API = REPOSITORY / 'services' / 'core-api'
# Local QA never needs provider credentials. A mocked provider test injects its own.
SECRET_MARKERS = ('OPENAI_', 'ROBOFLOW', 'TOKEN', 'SECRET', 'PASSWORD', 'API_KEY')
REQUIRED_DIRECTORIES = ('regionalDir', 'dinov2Dir', 'acneV5Dir', 'hfHome', 'pythonOverlay')


def scrub_secrets(environment):
    for key in list(environment):
        if any(marker in key.upper() for marker in SECRET_MARKERS):
            environment.pop(key, None)


def runtime_environment(config, data_dir, origins):
    """Every variable the accepted Skin runtime depends on. Thread lanes stay in
    local_native_worker.py, which applies them before any native library loads."""
    missing = [key for key in REQUIRED_DIRECTORIES if not Path(config.get(key, '')).is_dir()]
    if missing:
        raise SystemExit('Missing runtime directories in config: ' + ', '.join(missing))
    return dict(
        ATTUNE_LOAD_LOCAL_ENV='0',
        ATTUNE_DATA_DIR=str(data_dir),
        ATTUNE_EXPERIMENTAL_ACNE_V5='1',
        ATTUNE_ACNE_V5_MODEL_DIR=config['acneV5Dir'],
        ATTUNE_REGIONAL_V3_DIR=config['regionalDir'],
        ATTUNE_DINOV2_DIR=config['dinov2Dir'],
        ATTUNE_TRUSTED_ORIGINS=origins,
        HF_HOME=config['hfHome'],
        HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1',
        PYTHONDONTWRITEBYTECODE='1',
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-config', required=True, type=Path)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--origins', default='http://localhost:3000,http://127.0.0.1:3000')
    parser.add_argument('--stop-file', type=Path)
    parser.add_argument('--keep-secrets', action='store_true', help='Keep provider variables (explicitly approved live tests only).')
    arguments = parser.parse_args()

    config = json.loads(arguments.runtime_config.read_text('utf8'))
    if not arguments.keep_secrets:
        scrub_secrets(os.environ)
    arguments.data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.update(runtime_environment(config, arguments.data_dir, arguments.origins))
    sys.path[:0] = [str(CORE_API), config['pythonOverlay']]
    os.chdir(CORE_API)

    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', arguments.port)) == 0:
            raise SystemExit(f'Port {arguments.port} is occupied; existing service preserved')

    import uvicorn
    server = uvicorn.Server(uvicorn.Config('main:app', host='127.0.0.1', port=arguments.port, log_level='info', access_log=False))

    def wait_for_stop():
        if arguments.stop_file:
            while not arguments.stop_file.exists():
                time.sleep(.25)
        else:
            sys.stdin.buffer.read()
        server.should_exit = True

    threading.Thread(target=wait_for_stop, daemon=True).start()
    server.run()


if __name__ == '__main__':
    main()
