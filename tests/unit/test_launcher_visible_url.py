"""Visible URL launcher contract; no real browser, services or profile access."""
import hashlib
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load():
    return runpy.run_path(str(ROOT / 'scripts/windows-launcher/start_togg.pyw'))


def test_visible_url_uses_same_profile_without_debugging(monkeypatch):
    module = load()
    monkeypatch.delenv('ATTUNE_LAUNCHER_OBSERVE', raising=False)
    args = module['chrome_args'](module['PROFILE'])
    assert args == [str(module['CHROME']), '--user-data-dir=' + str(module['PROFILE']),
                    '--new-window', module['URL'], '--disable-background-mode',
                    '--no-first-run', '--no-default-browser-check']
    assert not any(arg.startswith(('--app=', '--remote-debugging', '--ignore-')) for arg in args)


@pytest.mark.parametrize('mutation', ['app-mode', 'other-url', 'extra-profile', 'other-profile', 'debug-port'])
def test_forged_complete_record_does_not_allow_different_browser_contract(monkeypatch, mutation):
    module = load()
    args = module['chrome_args'](module['PROFILE'])
    if mutation == 'app-mode':
        args = args[:2] + ['--app=' + module['URL']] + args[4:]
    elif mutation == 'other-url':
        args[3] = 'http://127.0.0.1:9999'
    elif mutation == 'extra-profile':
        args += ['--user-data-dir=foreign']
    elif mutation == 'other-profile':
        args[1] = '--user-data-dir=foreign'
    else:
        args += ['--remote-debugging-port=9222']
    process = SimpleNamespace(pid=123, create_time=lambda: 1., cwd=lambda: 'before',
                              exe=lambda: str(module['CHROME']), cmdline=lambda: args,
                              is_running=lambda: True)
    row = module['identity'](123, 'browser', process)
    monkeypatch.setattr(module['psutil'], 'Process', lambda pid: process)
    assert module['process_matches'](row) is False


@pytest.mark.parametrize('status,foreign', [('running', False), ('stopped', False), ('running', True)])
def test_second_click_reuses_only_verified_owner_and_same_visible_url(tmp_path, monkeypatch, status, foreign):
    module = load()
    g = module['main'].__globals__
    source = tmp_path / 'source'
    (source / 'apps/vehicle-app/.next').mkdir(parents=True)
    (source / 'apps/vehicle-app/.next/BUILD_ID').write_text('build', encoding='utf8')
    delivery = dict(BUILD_ID='build', sourceCommit='commit')
    state = dict(status=status, workspace=str(source), BUILD_ID='build', sourceCommit='commit',
                 profile=str(module['PROFILE']), url=module['URL'], launcher_pid=1,
                 backend_pid=2, frontend_pid=3, browser_pid=4,
                 processes=[dict(pid=i, role=role, started=1., cwd='before', commandSHA256='hash')
                            for i, role in enumerate(('launcher', 'backend', 'frontend', 'browser'), 1)])
    (tmp_path / 'session.json').write_text(json.dumps(state), encoding='utf8')
    monkeypatch.setitem(g, 'HERE', tmp_path)
    monkeypatch.setitem(g, 'ROOT', source)
    monkeypatch.setitem(g, 'verify_delivery', lambda: delivery)
    monkeypatch.setitem(g, 'process_matches', lambda row: not foreign)
    monkeypatch.setitem(g, 'fetch', lambda url: json.dumps(dict(**delivery, hostedSkinTypeEnabled=False)).encode())
    monkeypatch.setattr(module['msvcrt'], 'locking', lambda *a: (_ for _ in ()).throw(OSError('owned lock')))
    monkeypatch.setattr(module['psutil'], 'Process', lambda pid: SimpleNamespace(cwd=lambda: 'observed-browser-cwd'))
    launched = []
    monkeypatch.setattr(module['subprocess'], 'Popen', lambda args, **kw: launched.append(args) or SimpleNamespace(pid=777))
    if status == 'running' and not foreign:
        module['main']()
        assert launched == [module['chrome_args'](module['PROFILE'])]
        receipt = json.loads((tmp_path / 'reuse-receipt.json').read_text('utf8'))
        assert receipt['browserPID'] == 4 and receipt['BUILD_ID'] == 'build'
    else:
        with pytest.raises(RuntimeError, match='ownership differs'):
            module['main']()
        assert launched == []


def test_browser_exit_preserves_existing_backend_drain_job_close_order(tmp_path, monkeypatch):
    module = load()
    g = module['main'].__globals__
    source = tmp_path / 'source'
    (source / 'apps/vehicle-app/.next').mkdir(parents=True)
    (source / 'apps/vehicle-app/.next/BUILD_ID').write_text('build', encoding='utf8')
    events = []

    class Process:
        def __init__(self, pid, role):
            self.pid, self.role, self.done = pid, role, False
            self.stdin = SimpleNamespace(write=lambda b: events.append(('pipe', b)), flush=lambda: None)
        def poll(self):
            return 0 if self.done else None
        def wait(self, timeout):
            events.append(('wait', self.role)); self.done = True; return 0

    backend, frontend, browser = Process(2, 'backend'), Process(3, 'frontend'), Process(4, 'browser')
    class Job:
        def add(self, process):
            events.append(('add', process.role))
        def close(self):
            events.append(('job-close',)); frontend.done = browser.done = True

    monkeypatch.setitem(g, 'HERE', tmp_path)
    monkeypatch.setitem(g, 'ROOT', source)
    monkeypatch.setitem(g, 'verify_delivery', lambda: dict(BUILD_ID='build', sourceCommit='commit'))
    monkeypatch.setitem(g, 'occupied', lambda port: False)
    monkeypatch.setitem(g, 'OwnedJob', Job)
    monkeypatch.setitem(g, 'await_ready', lambda *args: None)
    monkeypatch.setitem(g, 'start_service', lambda job, name, *args: backend if name == 'backend' else frontend)
    monkeypatch.setitem(g, 'identity', lambda pid, role: dict(pid=pid, role=role))
    monkeypatch.setattr(module['psutil'], 'process_iter', lambda *args: [])
    monkeypatch.setattr(module['subprocess'], 'Popen', lambda *args, **kw: browser)
    monkeypatch.setattr(module['time'], 'sleep', lambda delay: setattr(browser, 'done', True))
    module['main']()
    assert events.index(('pipe', b'stop\n')) < events.index(('wait', 'backend')) < events.index(('job-close',))
    assert json.loads((tmp_path / 'session.json').read_text('utf8'))['status'] == 'stopped'
