"""Diagnostic collection is observational and excludes app content from CDP events."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('aaos_diagnostics', ROOT / 'scripts/qa/realistic/aaos_target_diagnostics.py')
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)


def test_snapshot_is_read_only_and_filters_vehicle_identity(monkeypatch, tmp_path):
    monitor = diagnostics.TargetDiagnostics(tmp_path / 'new-evidence')
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        assert kwargs['timeout'] == 8
        return SimpleNamespace(returncode=0, stdout='topResumedActivity=fixture\n')
    monkeypatch.setattr(diagnostics.subprocess, 'run', run)
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit):
            assert limit == 65537
            return json.dumps({'vehicleParked': True, 'driverName': 'private identity'}).encode()
    monkeypatch.setattr(diagnostics.urllib.request, 'urlopen', lambda url, timeout: Response())
    monitor.snapshot()
    data = (monitor.out / 'events.jsonl').read_text()
    assert 'vehicleParked' in data and 'private identity' not in data
    assert all(command[:3] == diagnostics.ADB and command[3] == 'shell' for command in commands)
    assert {command[4] for command in commands} <= {'pidof', 'dumpsys', 'cat', 'ps'}
    with pytest.raises(FileExistsError):
        diagnostics.TargetDiagnostics(monitor.out)


def test_cdp_reports_closure_without_reopening_or_retrying(tmp_path):
    callbacks = {}
    class Endpoint:
        def on(self, name, callback): callbacks[name] = callback
        def send(self, name): assert name == 'Inspector.enable'
    session = Endpoint()
    page = Endpoint()
    page.context = SimpleNamespace(new_cdp_session=lambda page: session)
    monitor = diagnostics.TargetDiagnostics(tmp_path / 'new-evidence')
    monitor.attach(page, Endpoint())
    callbacks['close']()
    callbacks['Inspector.targetCrashed']({'private': 'not persisted'})
    callbacks['disconnected']()
    data = (monitor.out / 'events.jsonl').read_text()
    assert 'cdp-page-close' in data and 'cdp-target-crashed' in data and 'cdp-browser-disconnected' in data
    assert 'not persisted' not in data
