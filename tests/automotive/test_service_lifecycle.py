"""Real Linux processes/sockets; HTTP fixtures are NOT neural/Android evidence."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import psutil
import pytest

import neural_readiness as readiness
import run_emulator as runner
import service_lifecycle as lifecycle
import validate_emulator as harness

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux AAOS runner lifecycle')

HTTP_FIXTURE = r'''
import json,os,sys
from http.server import HTTPServer,BaseHTTPRequestHandler
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  raw=json.dumps({'vehicleParked':True}).encode()
  self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  if sys.argv[2]=='frontend':code=409
  elif self.path=='/api/vehicle/speed':code=200
  elif self.headers.get('Authorization')!='Bearer '+os.environ['ATTUNE_MENTAL_TTS_TOKEN']:code=401
  elif not data['speechConsent']:code=200 if os.getenv('FIXTURE_BAD_CONSENT') else 403
  else:code=503
  self.send_response(code);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}')
HTTPServer.allow_reuse_address=True
HTTPServer(('127.0.0.1',int(sys.argv[1])),Handler).serve_forever()
'''


def unused_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


@pytest.fixture
def fixture_services(monkeypatch):
    original = subprocess.Popen
    owned = []
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_TOKEN', 'not-a-credential-' * 4)
    monkeypatch.setenv('ATTUNE_LOAD_LOCAL_ENV', '0')

    def spawn(command, **kwargs):
        assert kwargs['start_new_session'] is True
        assert kwargs['cwd'] == readiness.ROOT
        backend = '--app-dir' in command
        port = int(command[command.index('--port' if backend else '-p') + 1]) if backend or '-p' in command else 3000
        process = original([sys.executable, '-c', HTTP_FIXTURE, str(port), 'backend' if backend else 'frontend'], **kwargs)
        owned.append(process)
        return process

    monkeypatch.setattr(readiness.subprocess, 'Popen', spawn)
    try:
        yield owned
    finally:
        # Cleanup only this test's own records even if an assertion fails.
        lifecycle.stop_owned_services(owned, seconds=.2)


def assert_clean(owned, ports):
    for process in owned:
        assert process.returncode is not None
        assert not lifecycle.group_running(process.pid)
    for port in ports:
        runner.free_port(port)


def test_successful_readiness_releases_8000_for_harness_backend(fixture_services, tmp_path):
    """Real HTTP fixtures exercise actual readiness/harness process control."""
    frontend = unused_port()
    result = readiness.verify_services(backend_port=8000, frontend_port=frontend)
    assert (result['backendUnauthenticated'], result['backendNoConsent'], result['authenticatedFrontendProxyMoving']) == (401, 403, 409)
    assert result['temporaryServicesCleaned'] is True
    assert set(result['portsReleased']) == {8000, frontend}
    assert_clean(fixture_services, (8000, frontend))
    assessment = harness.Assessment(tmp_path)
    backend = assessment.start_service('backend')
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                assert readiness.request('http://127.0.0.1:8000/api/health')[0] == 200
                break
            except OSError:
                assert backend.poll() is None
                assert time.monotonic() < deadline
                time.sleep(.05)
    finally:
        assessment.stop_service('backend')
    assert_clean(fixture_services, (8000, frontend))


@pytest.mark.parametrize('failure', ['consent-check', 'second-spawn', 'termination'])
def test_readiness_failure_releases_owned_services(monkeypatch, fixture_services, failure):
    backend, frontend = unused_port(), unused_port()
    if failure == 'consent-check':
        monkeypatch.setenv('FIXTURE_BAD_CONSENT', '1')
    else:
        original = readiness.subprocess.Popen
        def spawn(command, **kwargs):
            if len(fixture_services) == 1:
                if failure == 'termination':
                    raise SystemExit(128 + signal.SIGTERM)
                raise OSError('Explicit second-service spawn failure')
            return original(command, **kwargs)
        monkeypatch.setattr(readiness.subprocess, 'Popen', spawn)
    with pytest.raises((ValueError, OSError, SystemExit)):
        readiness.verify_services(backend_port=backend, frontend_port=frontend)
    assert_clean(fixture_services, (backend, frontend))


def test_time_wait_is_not_a_listener_but_live_listener_is_blocked():
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 0)); server.listen(1)
    port = server.getsockname()[1]
    with pytest.raises(OSError):
        runner.free_port(port)
    # The existing listener remains open; no PID is selected or killed by port.
    client = socket.create_connection(('127.0.0.1', port))
    connection, _ = server.accept()
    connection.shutdown(socket.SHUT_WR)
    assert client.recv(1) == b''
    connection.close(); client.close(); server.close()
    rows = lifecycle.port_observations([port])
    assert any(row['state'] == 'TIME_WAIT' and row['pid'] is None for row in rows)
    with socket.socket() as old_probe, pytest.raises(OSError):
        old_probe.bind(('127.0.0.1', port))
    assert lifecycle.wait_free_ports([port], seconds=.2) == [port]
    runner.free_port(port)
    with pytest.raises(OSError):
        lifecycle.free_port(port, reuse=False)


def test_bounded_wait_never_terminates_an_unrelated_listener():
    with socket.socket() as other:
        other.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        other.bind(('127.0.0.1', 0)); other.listen(1)
        port = other.getsockname()[1]
        with pytest.raises(ValueError, match='SERVICE_PORTS_NOT_RELEASED'):
            lifecycle.wait_free_ports([port], seconds=.1)
        client = socket.create_connection(('127.0.0.1', port))
        accepted, _ = other.accept(); accepted.close(); client.close()


def test_exited_leader_does_not_leave_its_child_running(tmp_path):
    child_code = "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print('ready',flush=True);time.sleep(30)"
    leader_code = ('import subprocess,sys,json;child=subprocess.Popen([sys.executable,"-c",' + repr(child_code) + '],stdout=subprocess.PIPE,text=True);'
                   'assert child.stdout.readline().strip()=="ready";print(child.pid,flush=True)')
    leader = subprocess.Popen([sys.executable, '-c', leader_code], stdout=subprocess.PIPE, text=True, start_new_session=True)
    child_pid = int(leader.stdout.readline())
    leader.wait(timeout=5)
    try:
        assert lifecycle.group_running(leader.pid)
        result = lifecycle.stop_owned_services([leader], seconds=.1)
        assert result[0]['groupStopped'] is True
        assert not lifecycle.group_running(leader.pid)
        try:
            assert psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            pass
    finally:
        lifecycle.stop_owned_services([leader], seconds=.1)


def test_old_pass_without_cleanup_receipt_blocks_before_sdk_or_emulator(monkeypatch, tmp_path):
    (tmp_path / 'neural-readiness.json').write_text(json.dumps({'status': 'PASS'}))
    monkeypatch.setenv('ATTUNE_AAOS_REQUIRE_NEURAL', '1')
    monkeypatch.setenv('ATTUNE_AAOS_EVIDENCE', str(tmp_path))
    monkeypatch.setenv('ANDROID_HOME', '/never-used-sdk')
    monkeypatch.setattr(runner, 'audit', lambda *a: pytest.fail('Must block before SDK/emulator'))
    assert runner.run() == 69
