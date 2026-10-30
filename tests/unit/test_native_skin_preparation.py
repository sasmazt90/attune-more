"""Preparation preserves optional model fallback without hiding required failures."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
from local_native_worker import execute


@pytest.mark.parametrize('missing', ['regional', 'type', 'both', 'neither'])
def test_optional_preparation_failure_keeps_supported_scan_ready(monkeypatch, missing):
    called = []

    def load(name):
        called.append(name)
        if missing in (name, 'both'):
            raise OSError('missing optional weights')

    monkeypatch.setitem(sys.modules, 'product_dryness', SimpleNamespace(runtime=lambda check: called.append('dryness')))
    monkeypatch.setitem(sys.modules, 'regional_skin_v3', SimpleNamespace(
        load_runtime=lambda: load('regional'), model_manifest=lambda: {'weights': 'verified'}))
    monkeypatch.setitem(sys.modules, 'local_skin_type', SimpleNamespace(load=lambda: load('type')))
    result = execute('warm-skin', {})
    assert result == {'ready': True, 'models': {} if missing in ('regional', 'both') else {'weights': 'verified'}}
    assert called == ['dryness', 'regional', 'type']


def test_required_model_failure_is_not_reported_ready(monkeypatch):
    def required(check):
        raise RuntimeError('required model unavailable')

    monkeypatch.setitem(sys.modules, 'product_dryness', SimpleNamespace(runtime=required))
    with pytest.raises(RuntimeError, match='required model unavailable'):
        execute('warm-skin', {})
