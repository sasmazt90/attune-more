"""Pre-emulator real service/configuration checks. Never performs inference."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from service_lifecycle import free_port, port_observations, stop_owned_services, wait_free_ports

ROOT = Path(__file__).resolve().parents[2]


def request(url, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, response.read(8192)
    except urllib.error.HTTPError as error:
        return error.code, error.read(8192)


def verify_services(backend_port=8000, frontend_port=3000, frontend_root=ROOT):
    """Own both services, exercise real auth/proxy denial, then release both ports."""
    token = os.environ.get('ATTUNE_MENTAL_TTS_TOKEN', '')
    if len(token) < 32:
        raise ValueError('NEURAL_TTS_AUTH_UNCONFIGURED')
    for port in (frontend_port, backend_port):
        free_port(port)
    owned = []
    backend_origin = 'http://127.0.0.1:' + str(backend_port)
    frontend_origin = 'http://localhost:' + str(frontend_port)
    env = {**os.environ, 'ATTUNE_MENTAL_TTS_BACKEND_URL': backend_origin,
           'ATTUNE_TRUSTED_ORIGINS': frontend_origin}
    commands = [[sys.executable, '-m', 'uvicorn', 'main:app', '--app-dir', 'services/core-api', '--host', '127.0.0.1', '--port', str(backend_port)],
                ['node', str(ROOT / 'node_modules/next/dist/bin/next'), 'start', str(frontend_root / 'apps/vehicle-app'), '--hostname', '127.0.0.1', '-p', str(frontend_port)]]
    try:
        for command in commands:
            owned.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True))
        deadline = time.monotonic() + 60
        while True:
            try:
                if request(backend_origin + '/api/health')[0] == 200 and request(frontend_origin + '/')[0] == 200:
                    break
            except (OSError, urllib.error.URLError):
                pass
            if time.monotonic() >= deadline or any(p.poll() is not None for p in owned):
                raise ValueError('ISOLATED_SERVICES_UNAVAILABLE')
            time.sleep(.25)
        payload = {'text': 'Nonpersonal preflight.', 'language': 'tr', 'speechConsent': False}
        backend = backend_origin + '/api/mental/neural-speech?language=tr'
        if request(backend, payload)[0] != 401:
            raise ValueError('BACKEND_AUTH_GATE_NOT_OBSERVED')
        if request(backend, payload, {'Authorization': 'Bearer ' + token})[0] != 403:
            raise ValueError('BACKEND_CONSENT_GATE_NOT_OBSERVED')
        if request(backend_origin + '/api/vehicle/speed', {'speedKmH': 75})[0] != 200:
            raise ValueError('ISOLATED_MOVING_STATE_UNAVAILABLE')
        payload['speechConsent'] = True
        status, body = request(frontend_origin + '/api/mental-neural-speech', payload, {'Origin': frontend_origin})
        if status != 409:
            raise ValueError('AUTHENTICATED_PROXY_MOVING_DENIAL_NOT_OBSERVED')
        report = {'backendAvailable': True, 'frontendAvailable': True, 'backendUnauthenticated': 401,
                  'backendNoConsent': 403, 'authenticatedFrontendProxyMoving': status,
                  'inference': 'NOT_EXECUTED', 'playback': 'NOT_EXECUTED'}
    finally:
        cleanup = stop_owned_services(owned)
        released = wait_free_ports((frontend_port, backend_port))
    return {**report, 'temporaryServicesCleaned': True, 'temporaryServices': cleanup,
            'portsReleased': released, 'socketStatesAfterCleanup': port_observations(released)}


def main():
    out = Path(os.environ['ATTUNE_AAOS_EVIDENCE'])
    out.mkdir(parents=True, exist_ok=True)
    try:
        python = os.environ['ATTUNE_MENTAL_TTS_PYTHON']
        subprocess.run([python, str(ROOT / 'scripts/mental_tts/preflight.py'), '--config', os.environ['ATTUNE_MENTAL_TTS_CONFIG'],
                        '--output', str(out / 'neural-assets-readiness.json')], cwd=ROOT, check=True, timeout=90)
        # Check native shared objects/imports too, with all inference network calls
        # disabled. This constructs no model and emits no synthetic audio.
        code = "import socket,inspect; offline=lambda *a,**k: (_ for _ in ()).throw(OSError('OFFLINE')); socket.socket.connect=socket.socket.connect_ex=socket.socket.sendto=offline; import torch,torchaudio; from chatterbox.mtl_tts import ChatterboxMultilingualTTS; import perth; assert 't3_model' in inspect.signature(ChatterboxMultilingualTTS.from_local).parameters"
        subprocess.run([python, '-c', code], cwd=ROOT, check=True, timeout=60)
        report = {'status': 'PASS', **verify_services()}
        import psutil
        memory = psutil.virtual_memory().available
        report['availableMemoryBytesBeforeBoot'] = memory
        if memory < 12 * 1024**3:
            raise ValueError('LESS_THAN_12_GIB_AVAILABLE_FOR_AAOS_AND_NEURAL_WORKER')
        # Reserve 22 minutes for the one boot + finite observer, never expand 40m.
        started = float(os.environ['ATTUNE_AAOS_JOB_STARTED'])
        remaining = 2400 - (time.time() - started)
        if remaining < 1320:
            raise ValueError('LESS_THAN_22_MINUTES_FOR_BOOT_AND_ACCEPTANCE')
        report['remainingJobSeconds'] = round(remaining)
    except Exception as error:
        report = {'status': 'BLOCKED', 'reason': str(error) if isinstance(error, ValueError) else type(error).__name__,
                  'inference': 'NOT_EXECUTED', 'playback': 'NOT_EXECUTED'}
    (out / 'neural-readiness.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return 0 if report['status'] == 'PASS' else 69


if __name__ == '__main__':
    def stop(signum, _frame):
        # Raise through verify_services' finally, including workflow cancellation.
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, stop)
    sys.exit(main())
