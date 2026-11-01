from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
import dry_dualscale_runtime_staging as D
from product_dryness import DrynessModelUnavailable

def test_memory_sampling_is_bounded_but_permission_check_is_not_skipped(monkeypatch):
    import psutil
    now=[1.0];permissions=[];reads=[]
    monkeypatch.setattr(D.time,'monotonic',lambda:now[0])
    monkeypatch.setattr(psutil,'virtual_memory',lambda:(reads.append(now[0]) or SimpleNamespace(available=500*2**20)))
    check=D._memory_guard(lambda:permissions.append(now[0]))
    for _ in range(100):check()
    assert len(permissions)==100 and len(reads)==1
    now[0]+=0.101;check()
    assert len(permissions)==101 and len(reads)==2
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(available=399*2**20))
    now[0]+=0.101
    with pytest.raises(DrynessModelUnavailable,match='LOCAL_MEMORY_RESERVE'):check()

def test_cancellation_is_immediate_between_memory_samples(monkeypatch):
    import psutil
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(available=500*2**20))
    cancelled=[False]
    def permitted():
        if cancelled[0]:raise RuntimeError('cancelled')
    check=D._memory_guard(permitted);check();cancelled[0]=True
    with pytest.raises(RuntimeError,match='cancelled'):check()
