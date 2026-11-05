"""Exercise real harness finalization with fake browser I/O; no host or app runs."""
import contextlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / 'scripts/qa/realistic'


def load(monkeypatch, name):
    monkeypatch.syspath_prepend(str(HARNESS))
    # Do not require a browser installation to check a runner's failure contract.
    monkeypatch.setitem(sys.modules, 'playwright.sync_api', SimpleNamespace(sync_playwright=contextlib.nullcontext))
    spec = importlib.util.spec_from_file_location(name, HARNESS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Adapter:
    pair = None

    def __init__(self, *args):
        self.finished = False
        self.page = SimpleNamespace(set_default_timeout=lambda *a: None, on=lambda *a: None)

    def open(self, *args):
        return self.page, self.close

    def prepare(self, *args):
        raise RuntimeError('synthetic target closed')

    def close(self):
        self.finished = True

    def finish(self, *args):
        self.close()


@pytest.mark.parametrize('scenario,expected', [('pass', 0), ('failed-check', 1), ('page-error', 1), ('exception', 1), ('empty', 1)])
def test_module_main_exit_matches_saved_report(monkeypatch, tmp_path, scenario, expected):
    module = load(monkeypatch, 'e2e_modules')
    adapter = Adapter()
    monkeypatch.setattr(module, 'Web', lambda *a: adapter)
    def journey(run):
        if scenario == 'exception':
            raise RuntimeError('synthetic target closed')
        run.report['status'] = 'PASS'
        if scenario != 'empty':
            run.check('synthetic check', scenario != 'failed-check')
        if scenario == 'page-error':
            run.report['errors'].append('synthetic page error')
    monkeypatch.setitem(module.JOURNEYS, 'skin', journey)
    monkeypatch.setattr(sys, 'argv', ['e2e_modules.py', '--platform', 'web', '--module', 'skin', '--out', str(tmp_path)])
    assert module.main() == expected
    report = json.loads((tmp_path / 'report.json').read_text())
    assert (report['status'] == 'PASS') == (expected == 0)
    assert adapter.finished


def test_vision_main_propagates_caught_failure_and_preserves_evidence(monkeypatch, tmp_path):
    module = load(monkeypatch, 'vision_realistic')
    adapter = Adapter()
    monkeypatch.setattr(module, 'Web', lambda: adapter)
    monkeypatch.setattr(sys, 'argv', ['vision_realistic.py', '--platform', 'web', '--root', str(ROOT), '--clips', str(tmp_path), '--out', str(tmp_path)])
    assert module.main() == 1
    report = json.loads((tmp_path / 'report.json').read_text())
    assert report['status'] == 'ERROR' and report['failure'] == 'synthetic target closed'
    assert report['finishedAt'] and adapter.finished
