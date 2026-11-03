#!/usr/bin/env python
"""Start/stop only the QA services this checkout owns. Never touches an occupied
port or an unrelated process: a stop acts on recorded PIDs after re-checking them.

    python scripts/qa/qa_services.py start --workdir DIR --runtime-config FILE
    python scripts/qa/qa_services.py restart-backend --workdir DIR --runtime-config FILE
    python scripts/qa/qa_services.py stop --workdir DIR
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import psutil

REPOSITORY = Path(__file__).resolve().parents[2]
APP = REPOSITORY / 'apps' / 'vehicle-app'
FLAGS = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if os.name == 'nt' else 0


def occupied(port):
    with socket.socket() as probe:
        return probe.connect_ex(('127.0.0.1', port)) == 0


def wait_for(url, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(.5)
    return False


def start_backend(arguments, state):
    if occupied(arguments.api_port):
        raise SystemExit(f'API port {arguments.api_port} is occupied; preserved')
    config = json.loads(arguments.runtime_config.read_text('utf8'))
    stop = arguments.workdir / 'STOP-BACKEND'
    stop.unlink(missing_ok=True)
    log = (arguments.workdir / 'backend.log').open('a', encoding='utf8')
    command = [config['python'], str(REPOSITORY / 'scripts/qa/run_local_backend.py'), '--runtime-config', str(arguments.runtime_config),
               '--data-dir', str(arguments.workdir / 'runtime-data'), '--port', str(arguments.api_port), '--stop-file', str(stop)]
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=FLAGS, env=dict(os.environ, **arguments.extra_env))
    state['backend'] = process.pid
    if not wait_for(f'http://127.0.0.1:{arguments.api_port}/api/health', 120):
        raise SystemExit('Backend did not become healthy; see backend.log')


def start_frontend(arguments, state):
    if occupied(arguments.web_port):
        raise SystemExit(f'Web port {arguments.web_port} is occupied; preserved')
    log = (arguments.workdir / 'frontend.log').open('a', encoding='utf8')
    environment = dict(os.environ, NEXT_TELEMETRY_DISABLED='1', NEXT_PUBLIC_ATTUNE_ACNE_V5='1')
    next_bin = REPOSITORY / 'node_modules/next/dist/bin/next'
    process = subprocess.Popen(['node', str(next_bin), 'start', '--hostname', '127.0.0.1', '--port', str(arguments.web_port)], cwd=APP, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=FLAGS, env=environment)
    state['frontend'] = process.pid
    build = (APP / '.next/BUILD_ID').read_text().strip()
    if not wait_for(f'http://127.0.0.1:{arguments.web_port}/_next/static/{build}/_buildManifest.js', 120):
        raise SystemExit('Frontend did not serve this build; see frontend.log')
    state['build'] = build


def stop_owned(pid, marker):
    try:
        process = psutil.Process(pid)
    except psutil.Error:
        return 'already-stopped'
    if marker not in ' '.join(process.cmdline()):
        return 'pid-reused-preserved'
    for child in process.children(recursive=True):
        child.kill()
    process.kill()
    process.wait(15)
    return 'stopped'


def stop_backend(arguments, state):
    pid = state.pop('backend', None)
    (arguments.workdir / 'STOP-BACKEND').write_text('stop')
    if not pid:
        return
    try:
        psutil.Process(pid).wait(20)
        print('backend stopped by marker')
    except psutil.TimeoutExpired:
        print('backend', stop_owned(pid, 'run_local_backend'))
    except psutil.Error:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'start-backend', 'restart-backend', 'stop', 'stop-backend'))
    parser.add_argument('--workdir', required=True, type=Path)
    parser.add_argument('--runtime-config', type=Path)
    parser.add_argument('--api-port', type=int, default=8000)
    parser.add_argument('--web-port', type=int, default=3000)
    parser.add_argument('--set-env', action='append', default=[], help='NAME=VALUE for the backend process, for controlled experiments')
    arguments = parser.parse_args()
    arguments.extra_env = dict(item.split('=', 1) for item in arguments.set_env)
    arguments.workdir.mkdir(parents=True, exist_ok=True)
    state_file = arguments.workdir / 'services.json'
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    try:
        if arguments.action in ('restart-backend', 'stop-backend', 'stop'):
            stop_backend(arguments, state)
        if arguments.action in ('start', 'start-backend', 'restart-backend'):
            start_backend(arguments, state)
        if arguments.action == 'start':
            start_frontend(arguments, state)
        if arguments.action == 'stop' and 'frontend' in state:
            print('frontend', stop_owned(state.pop('frontend'), 'next'))
    finally:
        state_file.write_text(json.dumps(state))
    print(json.dumps(state))


if __name__ == '__main__':
    sys.exit(main())
