"""Test infrastructure for the live GPU closing: the remote resident bridge and server carry the unchanged resident line
protocol over TCP, map the API host's configuration path, refuse a wrong handshake and kill the remote worker when the
API cancels. A stub stands in for the model; loopback only."""
import asyncio
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import time

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import mental_neural_tts as tts  # noqa: E402

TOOLS = ROOT / 'scripts/mental_closing_abc'
STUB = """
import base64, io, json, os, sys, time, wave
log = os.environ['STUB_LOG']
buffer = io.BytesIO()
with wave.open(buffer, 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b'\\x01\\x02' * 2400)
loaded = False
for raw in iter(sys.stdin.buffer.readline, b''):
    job = json.loads(raw)
    open(log, 'a').write(json.dumps({'pid': os.getpid(), 'config': job['config'], 'warm': job.get('warm', False)}) + chr(10))
    if job.get('text') == 'hang':
        time.sleep(60)
    reply = {'start': 'warm' if loaded else 'cold'}
    loaded = True
    if not job.get('warm'):
        reply['wav'] = base64.b64encode(buffer.getvalue()).decode()
    print(json.dumps(reply), flush=True)
"""


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture
def remote(tmp_path, monkeypatch):
    worker = tmp_path / 'stub_worker.py'
    worker.write_text(STUB)
    handshake = tmp_path / 'handshake'
    handshake.write_text('a' * 64)
    api_config, gpu_config = tmp_path / 'api-config.json', tmp_path / 'gpu-config.json'
    api_config.write_text('{}')
    gpu_config.write_text('{}')
    mapping = tmp_path / 'map.json'
    mapping.write_text(json.dumps({str(api_config): str(gpu_config)}))
    log, stub_log = tmp_path / 'server.jsonl', tmp_path / 'stub.jsonl'
    port = free_port()
    env = {**os.environ, 'STUB_LOG': str(stub_log)}
    server = subprocess.Popen([sys.executable, str(TOOLS / 'remote_resident_server.py'), '--listen', f'127.0.0.1:{port}',
                               '--handshake-file', str(handshake), '--config-map', str(mapping), '--log', str(log),
                               '--peer', '127.0.0.1', '--cwd', str(tmp_path), sys.executable, str(worker)], env=env)
    for _ in range(100):
        try:
            socket.create_connection(('127.0.0.1', port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.05)
    # Connection probes above count as refused handshakes; the log starts clean for the test.
    launcher = tmp_path / 'bridge.sh'
    launcher.write_text(f'#!/bin/sh\nexec {sys.executable} {TOOLS / "remote_resident_bridge.py"} "$@"\n')
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(tts, 'configuration_path', lambda profile=None: str(api_config))
    monkeypatch.setattr(tts, 'verify_request_configuration', lambda *a: None)
    monkeypatch.setattr(tts, '_resident', None)
    monkeypatch.setattr(tts, '_warm_task', None)
    monkeypatch.setattr(tts, '_busy', False)
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_RESIDENT', '1')
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_PYTHON', str(launcher))
    monkeypatch.setenv('ATTUNE_REMOTE_TTS_ADDRESS', f'127.0.0.1:{port}')
    monkeypatch.setenv('ATTUNE_REMOTE_TTS_HANDSHAKE_FILE', str(handshake))
    yield {'stub': lambda: [json.loads(x) for x in stub_log.read_text().splitlines()] if stub_log.exists() else [],
           'log': lambda: [json.loads(x) for x in log.read_text().splitlines()], 'gpu_config': str(gpu_config),
           'handshake': handshake, 'port': port}
    server.kill()
    server.wait()


async def never():
    return False


def test_remote_worker_serves_the_api_with_the_mapped_configuration(remote):
    async def run():
        first = await tts.generate('one', 'en', lambda: True, never)
        start_one = tts.last_generation['start']
        second = await tts.generate('two', 'en', lambda: True, never)
        start_two = tts.last_generation['start']
        await tts.close_resident()
        return first, second, start_one, start_two
    first, second, start_one, start_two = asyncio.run(run())
    assert first[:4] == b'RIFF' and first == second and (start_one, start_two) == ('cold', 'warm')
    rows = remote['stub']()
    assert [r['config'] for r in rows] == [remote['gpu_config']] * 2 and len({r['pid'] for r in rows}) == 1
    time.sleep(0.3)
    kinds = [r['kind'] for r in remote['log']()]
    assert kinds.count('request') == 2 and kinds.count('reply') == 2 and 'connection-end' in kinds
    assert not any('text' in r for r in remote['log']())


def test_cancelling_the_request_kills_the_remote_worker(remote):
    async def run():
        gone = []

        async def disconnected():
            gone.append(1)
            return len(gone) > 5
        with pytest.raises(HTTPException) as error:
            await tts.generate('hang', 'en', lambda: True, disconnected)
        await tts.close_resident()
        return error.value.status_code
    assert asyncio.run(run()) == 499
    time.sleep(0.5)
    pid = remote['stub']()[-1]['pid']
    assert not Path(f'/proc/{pid}').exists() or 'zombie' in Path(f'/proc/{pid}/status').read_text().lower()
    end = [r for r in remote['log']() if r['kind'] == 'connection-end'][-1]
    assert end['requests'] == 1 and end['replies'] == 0


def test_wrong_handshake_gets_no_worker(remote):
    with socket.create_connection(('127.0.0.1', remote['port'])) as s:
        s.sendall(b'b' * 64 + b'\n')
        s.settimeout(3)
        assert s.recv(10) == b''
    time.sleep(0.2)
    assert remote['log']()[-1]['kind'] == 'handshake-refused' and remote['stub']() == []
