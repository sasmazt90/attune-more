"""Small fail-closed ownership tests; no models, photos or actual shared locks."""
import sys,json,os,time
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/skin-research'))
import heavy_job_lease as H

@pytest.fixture
def locks(tmp_path,monkeypatch):
    paths=[tmp_path/'cdc.json',tmp_path/'ag.lock']
    monkeypatch.setattr(H,'LOCK',paths[0]);monkeypatch.setattr(H,'AG_LOCK',paths[1]);monkeypatch.setattr(H,'ag_workers',lambda:[])
    monkeypatch.setattr(H.HeavyJobLease,'start_owner_observer',lambda self:setattr(self,'observer_state',dict(ok=True,workers=[],observedAt=time.monotonic())))
    return paths

def test_mid_run_observation_stale_or_active_blocks_with_valid_leases(locks):
    with H.HeavyJobLease('CDC-unit',peak_mib=500,minimum_available_mib=0) as lease:
        lease.observer_state['observedAt']=0
        with pytest.raises(H.HeavyJobUnavailable,match='stale'):lease.verify_observation()
        lease.observer_state=dict(ok=True,workers=[{'pid':999}],observedAt=time.monotonic())
        with pytest.raises(H.HeavyJobUnavailable,match='AG worker appeared'):lease.verify_observation()
        lease.observer_state=dict(ok=False,workers=[],observedAt=time.monotonic())
        with pytest.raises(H.HeavyJobUnavailable,match='observer failed'):lease.verify_observation()

def test_both_paths_have_same_real_identity_and_release_only_owned(locks):
    with H.HeavyJobLease('CDC-unit',peak_mib=500,minimum_available_mib=0) as lease:
        a,b=[json.loads(p.read_text()) for p in locks]
        assert a==b and a['pid']==os.getpid() and a['processStarted']==H.psutil.Process().create_time()
        assert Path(a['workspace']).resolve()==Path.cwd().resolve() and a['jobId']=='CDC-unit' and len(a['nonce'])>=16
        lease.check()
    assert not any(p.exists() for p in locks)

@pytest.mark.parametrize('index',[0,1])
@pytest.mark.parametrize('raw',['','{','{"pid":123,"jobId":"legacy"}'])
def test_partial_or_legacy_lock_blocks_without_delete(locks,index,raw):
    locks[index].write_text(raw)
    with pytest.raises(H.HeavyJobUnavailable,match='Unverifiable'):
        with H.HeavyJobLease('CDC-unit',minimum_available_mib=0):pass
    assert locks[index].read_text()==raw and not locks[1-index].exists()

def test_living_foreign_job_preserved(locks):
    row=dict(pid=os.getpid(),processStarted=H.psutil.Process().create_time(),workspace=str(Path.cwd()),jobId='foreign',nonce='foreign-valid-nonce')
    locks[1].write_text(json.dumps(row))
    with pytest.raises(H.HeavyJobUnavailable,match='Existing shared lease'):
        with H.HeavyJobLease('CDC-unit',minimum_available_mib=0):pass
    assert json.loads(locks[1].read_text())==row and not locks[0].exists()

def test_replaced_foreign_lease_not_released(locks):
    with H.HeavyJobLease('CDC-unit',peak_mib=500,minimum_available_mib=0) as lease:
        row=json.loads(locks[1].read_text());row['nonce']='foreign-valid-nonce';locks[1].write_text(json.dumps(row))
        with pytest.raises(H.HeavyJobUnavailable,match='identity changed'):lease.verify_owned()
    assert locks[1].exists() and not locks[0].exists()

def test_pid_reuse_and_access_denied_fail_closed(locks,monkeypatch):
    row=dict(pid=os.getpid(),processStarted=H.psutil.Process().create_time()-1,workspace=str(Path.cwd()),jobId='foreign',nonce='foreign-valid-nonce')
    locks[0].write_text(json.dumps(row))
    with pytest.raises(H.HeavyJobUnavailable,match='creation/workspace mismatch'):
        with H.HeavyJobLease('CDC-unit',minimum_available_mib=0):pass
    class Denied:
        def __init__(self,pid):raise H.psutil.AccessDenied(pid)
    monkeypatch.setattr(H.psutil,'Process',Denied)
    with pytest.raises(H.HeavyJobUnavailable,match='AccessDenied'):H.verify_process_identity(row)
    assert locks[0].exists()

def test_second_create_race_rolls_back_only_own_first(locks,monkeypatch):
    original=H.os.open
    def acquire(path,*args):
        if path==locks[1]:
            path.write_text('{"foreign":"partial"}')
        return original(path,*args)
    monkeypatch.setattr(H.os,'open',acquire)
    with pytest.raises(H.HeavyJobUnavailable,match='Dual acquisition failed'):
        with H.HeavyJobLease('CDC-unit',minimum_available_mib=0):pass
    assert not locks[0].exists() and locks[1].read_text()=='{"foreign":"partial"}'
