"""Focused live-RAM/lease boundary tests; no shared production lock or model."""
import ctypes
import json
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
import physical_memory as M
import heavy_job_lease as H

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Real Windows ABI required')


@pytest.fixture(autouse=True)
def isolated_binding():
    M._windows_binding.cache_clear()
    yield
    M._windows_binding.cache_clear()


@pytest.fixture
def locks(tmp_path, monkeypatch):
    paths = [tmp_path / 'cdc.json', tmp_path / 'ag.lock']
    monkeypatch.setattr(H, 'LOCK', paths[0])
    monkeypatch.setattr(H, 'AG_LOCK', paths[1])
    monkeypatch.setattr(H, 'ag_workers', lambda: [])
    monkeypatch.setattr(H.HeavyJobLease, 'start_owner_observer',
        lambda self: setattr(self, 'observer_state',
            dict(ok=True, workers=[], observedAt=time.monotonic())))
    return paths


def fake_query(monkeypatch, **updates):
    def query(pointer, cb):
        row = pointer._obj
        assert cb == ctypes.sizeof(M._PerformanceInformation) == row.cb
        row.PhysicalTotal = 2**22
        row.PhysicalAvailable = 2**19
        row.PageSize = 4096
        for key, value in updates.items():
            setattr(row, key, value)
        return 1
    monkeypatch.setattr(M, '_windows_binding', lambda: (None, query))


def test_native_abi_and_real_system32_query():
    size = ctypes.sizeof(ctypes.c_size_t)
    expected = {4: (56, 20, 40, 44), 8: (104, 40, 80, 88)}[size]
    assert ctypes.sizeof(M._PerformanceInformation) == expected[0]
    assert M._PerformanceInformation.PhysicalAvailable.offset == expected[1]
    assert M._PerformanceInformation.PageSize.offset == expected[2]
    assert M._PerformanceInformation.HandleCount.offset == expected[3]
    assert M._PerformanceInformation.ThreadCount.offset == expected[3] + 8
    dll, query = M._windows_binding()
    assert isinstance(dll, ctypes.WinDLL)
    assert not query._flags_ & ctypes._FUNCFLAG_PYTHONAPI
    assert query.argtypes == [ctypes.POINTER(M._PerformanceInformation), ctypes.c_uint32]
    assert query.restype is ctypes.c_int32
    row = M._PerformanceInformation()
    row.cb = ctypes.sizeof(row)
    assert query(ctypes.byref(row), row.cb)
    # Availability can change between calls; do not demand byte equality.
    available = H.available_physical_mib() * 2**20
    assert 0 <= available <= row.PhysicalTotal * row.PageSize
    assert available % row.PageSize == 0
    print(json.dumps(dict(evidence='real-native-ram', pointerBytes=size,
        structureBytes=ctypes.sizeof(row), pageBytes=row.PageSize,
        physicalTotalPages=row.PhysicalTotal, availableBytes=available)))


def test_loader_search_signature_and_no_observation_cache(monkeypatch):
    calls = []
    class Query:
        def __call__(self, pointer, cb):
            row = pointer._obj
            row.PageSize = 8192
            row.PhysicalTotal = 2**21
            row.PhysicalAvailable = 3 + len(calls)
            calls.append(('query', cb))
            return 1
    query = Query()
    def load(name, **kwargs):
        calls.append(('load', name, kwargs))
        return SimpleNamespace(GetPerformanceInfo=query)
    monkeypatch.setattr(M.ctypes, 'WinDLL', load)
    first = H.available_physical_mib()
    second = H.available_physical_mib()
    assert second > first
    assert calls[0] == ('load', 'psapi.dll', {'use_last_error': True, 'winmode': 0x800})
    assert sum(row[0] == 'load' for row in calls) == 1
    assert sum(row[0] == 'query' for row in calls) == 2
    assert query.argtypes == [ctypes.POINTER(M._PerformanceInformation), ctypes.c_uint32]


@pytest.mark.parametrize('updates', [
    {'cb': 0}, {'PageSize': 0}, {'PageSize': 3}, {'PhysicalTotal': 0},
    {'PhysicalAvailable': 2**23}, {'PageSize': 2**31, 'PhysicalTotal': 2**40},
])
def test_malformed_native_data_blocks_actual_entry(locks, monkeypatch, updates):
    fake_query(monkeypatch, **updates)
    with pytest.raises(H.HeavyJobUnavailable, match='Physical RAM unavailable'):
        with H.HeavyJobLease('invalid-native', minimum_available_mib=1600):
            pytest.fail('Invalid data admitted a lease')
    assert not any(path.exists() for path in locks)


def test_false_native_result_last_error_and_no_fallback(locks, monkeypatch):
    def query(*args):
        ctypes.set_last_error(5)
        return 0
    monkeypatch.setattr(M, '_windows_binding', lambda: (None, query))
    with pytest.raises(H.HeavyJobUnavailable) as caught:
        with H.HeavyJobLease('native-failed', minimum_available_mib=1600):
            pytest.fail('Failed native query admitted a lease')
    assert caught.value.__cause__.__cause__.errno == 5
    assert not any(path.exists() for path in locks)


def test_dll_load_failure_blocks_entry(locks, monkeypatch):
    def load(*args, **kwargs):
        raise OSError(126, 'DLL unavailable')
    monkeypatch.setattr(M.ctypes, 'WinDLL', load)
    with pytest.raises(H.HeavyJobUnavailable):
        H.HeavyJobLease('load-failed', minimum_available_mib=1600).__enter__()
    assert not any(path.exists() for path in locks)


@pytest.mark.parametrize('pages', [0, (1599 * 2**20) // 4096])
def test_low_native_ram_blocks_actual_entry(locks, monkeypatch, pages):
    fake_query(monkeypatch, PhysicalAvailable=pages)
    with pytest.raises(H.HeavyJobUnavailable, match='RESOURCE_OR_AG_BUSY'):
        H.HeavyJobLease('low-ram', minimum_available_mib=1600).__enter__()
    assert not any(path.exists() for path in locks)


@pytest.mark.parametrize('failure', ['low', 'native'])
def test_running_check_stops_on_low_or_failed_native_ram(locks, monkeypatch, failure):
    fake_query(monkeypatch)
    with H.HeavyJobLease('runtime-ram', minimum_available_mib=1600) as lease:
        if failure == 'low':
            fake_query(monkeypatch, PhysicalAvailable=399 * 256)
            expected = 'OWN_MEMORY_OR_RESERVE'
        else:
            monkeypatch.setattr(M, '_windows_binding', lambda: (None, lambda *args: 0))
            expected = 'Physical RAM unavailable'
        with pytest.raises(H.HeavyJobUnavailable, match=expected):
            lease.check()
    assert not any(path.exists() for path in locks)


@pytest.mark.parametrize('state,reason', [
    ('fresh', None), ('stale', 'stale'), ('failed', 'observer failed'),
    ('new-worker', 'AG worker appeared'),
])
def test_observation_outcomes_through_actual_check(locks, monkeypatch, state, reason):
    fake_query(monkeypatch)
    with H.HeavyJobLease('observation', minimum_available_mib=1600) as lease:
        lease.observer_state = dict(ok=state != 'failed',
            workers=[{'pid': 999}] if state == 'new-worker' else [],
            observedAt=0 if state == 'stale' else time.monotonic())
        if reason:
            with pytest.raises(H.HeavyJobUnavailable, match=reason):
                lease.check()
        else:
            lease.check()


@pytest.mark.parametrize('field,value', [
    ('nonce', 'different-valid-nonce'), ('pid', 1),
    ('processStarted', 1.0), ('workspace', 'C:\\different-workspace'),
])
def test_identity_mismatch_still_blocks_check(locks, monkeypatch, field, value):
    fake_query(monkeypatch)
    with H.HeavyJobLease('identity', minimum_available_mib=1600) as lease:
        row = json.loads(locks[1].read_text())
        row[field] = value
        locks[1].write_text(json.dumps(row), encoding='utf8')
        with pytest.raises(H.HeavyJobUnavailable):
            lease.check()
    assert locks[1].exists() and not locks[0].exists()


def test_ag_census_access_denied_stays_fail_closed(monkeypatch):
    monkeypatch.setattr(H, 'process_names', lambda: [(123, 'python.exe')])
    def denied(pid):
        raise H.psutil.AccessDenied(pid)
    monkeypatch.setattr(H.psutil, 'Process', denied)
    with pytest.raises(H.HeavyJobUnavailable, match='AccessDenied'):
        H.ag_workers()


@pytest.mark.parametrize('mode', ['pid-reuse', 'access-denied'])
def test_process_identity_failure_through_check(locks, monkeypatch, mode):
    fake_query(monkeypatch)
    with H.HeavyJobLease('process-identity', minimum_available_mib=1600) as lease:
        class Process:
            def __init__(self, pid):
                if mode == 'access-denied':
                    raise H.psutil.AccessDenied(pid)
            def create_time(self):
                return lease.process.create_time() + 1
        monkeypatch.setattr(H.psutil, 'Process', Process)
        with pytest.raises(H.HeavyJobUnavailable,
                match='AccessDenied' if mode == 'access-denied' else 'creation/workspace mismatch'):
            lease.check()
    assert not any(path.exists() for path in locks)


def test_non_windows_uses_original_psutil_metric(monkeypatch):
    monkeypatch.setattr(M, 'os', SimpleNamespace(name='posix'))
    monkeypatch.setattr(M.psutil, 'virtual_memory', lambda: SimpleNamespace(available=1234567))
    assert H.available_physical_mib() == 1234567 / 2**20


def test_blocking_native_ram_allows_actual_reader_and_monitor(tmp_path, monkeypatch):
    paths = [tmp_path / 'cdc.json', tmp_path / 'ag.lock']
    monkeypatch.setattr(H, 'LOCK', paths[0])
    monkeypatch.setattr(H, 'AG_LOCK', paths[1])
    # No substituted reader, observer state or census in this integration test.
    dll, real_query = M._windows_binding()
    kernel = ctypes.WinDLL('kernel32.dll', use_last_error=True, winmode=0x800)
    sleep = kernel.Sleep
    sleep.argtypes = [ctypes.c_uint32]
    sleep.restype = None
    with H.HeavyJobLease('native-block-reader', peak_mib=350, minimum_available_mib=0) as lease:
        before = lease.observer_state['observedAt']
        monitor_calls = []
        real_rss = lease.rss_mib
        def rss():
            if threading.current_thread() is lease.monitor:
                monitor_calls.append(time.monotonic())
            return real_rss()
        monkeypatch.setattr(lease, 'rss_mib', rss)
        def delayed_query(pointer, cb):
            sleep(1350)  # Bounded native delay; WinDLL, not Python busy waiting.
            return real_query(pointer, cb)
        monkeypatch.setattr(M, '_windows_binding', lambda: (dll, delayed_query))
        start = time.monotonic()
        lease.check()
        elapsed = time.monotonic() - start
        age = time.monotonic() - lease.observer_state['observedAt']
        assert elapsed >= 1.3
        assert lease.observer_state['observedAt'] > before
        assert time.monotonic() - lease.observer_state['observedAt'] <= 1
        assert len(monitor_calls) >= 2
        print(json.dumps(dict(evidence='native-block-reader', blockCheckSeconds=elapsed,
            readerTimestampAdvanceSeconds=lease.observer_state['observedAt'] - before,
            observerAgeSeconds=age, monitorCallsDuringNativeBlock=len(monitor_calls))))
        # Only this verified Popen helper is stopped; ceased updates must fail.
        assert H.psutil.Process(lease.observer.pid).create_time() == lease.observer_birth
        lease.observer.terminate()
        lease.observer.wait(timeout=2)
        monkeypatch.setattr(M, '_windows_binding', lambda: (dll, real_query))
        time.sleep(1.1)
        with pytest.raises(H.HeavyJobUnavailable, match='stale'):
            lease.check()
    assert not any(path.exists() for path in paths)
    assert lease.observer.poll() is not None
