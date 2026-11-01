"""Preparation preserves optional model fallback without hiding required failures."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
from local_native_worker import execute
import local_native_worker as worker


def test_staged_preparation_requires_all_steps_and_does_not_reload(monkeypatch):
    called=[]
    monkeypatch.setattr(worker,'_prepared_steps',set())
    monkeypatch.setattr(worker,'_regional_preparation_failed',False)
    monkeypatch.setitem(sys.modules,'product_dryness',SimpleNamespace(runtime=lambda check:called.append('dryness')))
    monkeypatch.setitem(sys.modules,'regional_skin_v3',SimpleNamespace(prepare_component=lambda step:called.append(step),load_runtime=lambda:None,model_manifest=lambda:{'weights':'verified'}))
    monkeypatch.setitem(sys.modules,'local_skin_type',SimpleNamespace(load=lambda:called.append('type')))
    with pytest.raises(ValueError,match='INCOMPLETE_SKIN_PREPARATION'):
        execute('prepare-skin-step',{'step':'complete'})
    for step in worker.SKIN_PREPARATION_STEPS:
        assert execute('prepare-skin-step',{'step':step})=={'ready':False,'step':step}
        execute('prepare-skin-step',{'step':step})
    assert called==list(worker.SKIN_PREPARATION_STEPS)
    assert execute('prepare-skin-step',{'step':'complete'})=={'ready':True,'step':'complete','models':{'weights':'verified'}}
    with pytest.raises(ValueError,match='INVALID_SKIN_PREPARATION_STEP'):
        execute('prepare-skin-step',{'step':'../../anything'})


def test_staged_required_failure_never_completes(monkeypatch):
    monkeypatch.setattr(worker,'_prepared_steps',set())
    def fail(check):raise RuntimeError('required model unavailable')
    monkeypatch.setitem(sys.modules,'product_dryness',SimpleNamespace(runtime=fail))
    with pytest.raises(RuntimeError,match='required model unavailable'):
        execute('prepare-skin-step',{'step':'dryness'})
    assert not worker._prepared_steps


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
