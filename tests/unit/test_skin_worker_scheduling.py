"""The measured Skin deadline contract: scheduling, thread waiting and the memory reserve code."""
import asyncio
import os
from pathlib import Path
import re
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
import local_native_process as P

SESSION_SOURCES=('material_component_features.py','experimental_acne_v5.py','skin_models.py','skin_eyewear.py','local_skin_type.py','dental_analysis.py')

def test_worker_assigns_its_lanes_regardless_of_the_launcher_environment():
    # Thread count changes Skin numeric output, so no launcher may decide it.
    code=("import os;os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='ACTIVE',KMP_BLOCKTIME='200');"
          "import local_native_worker;print(*(os.environ[k] for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','OMP_WAIT_POLICY','KMP_BLOCKTIME')))")
    output=subprocess.run([sys.executable,'-c',code],cwd=ROOT/'services/core-api',capture_output=True,text=True,check=True).stdout.split()
    assert output==['2','2','2','PASSIVE','0']

def test_worker_module_sets_lanes_before_any_native_import():
    source=(ROOT/'services/core-api/local_native_worker.py').read_text('utf8')
    head=source[:source.index('def prepare_skin_step')]
    assert not re.search(r'^\s*(import|from)\s+(numpy|torch|onnxruntime|cv2)',head,re.M)

@pytest.mark.parametrize('name',SESSION_SOURCES)
def test_inference_sessions_do_not_spin_while_waiting(name):
    source=(ROOT/'services/core-api'/name).read_text('utf8')
    created=len(re.findall(r'ort\.InferenceSession\(',source))
    assert created>=1 and source.count("add_session_config_entry('session.intra_op.allow_spinning'")>=1
    assert "allow_spinning','1'" not in source

def test_ort_accepts_the_spinning_option():
    ort=pytest.importorskip('onnxruntime')
    options=ort.SessionOptions();options.add_session_config_entry('session.intra_op.allow_spinning','0')
    assert options.get_session_config_entry('session.intra_op.allow_spinning')=='0'

def test_worker_priority_is_requested_on_windows_only(monkeypatch):
    captured={}
    class Stop(Exception):pass
    async def spawn(*args,**kwargs):
        captured.update(kwargs);raise Stop()
    monkeypatch.setattr(P.asyncio,'create_subprocess_exec',spawn)
    with pytest.raises(Stop):asyncio.run(P.NativeAnalysisProcess().exchange('skin',{}))
    assert captured['creationflags']==(subprocess.ABOVE_NORMAL_PRIORITY_CLASS if os.name=='nt' else 0)

def test_worker_deadline_is_unchanged():
    import local_health
    assert local_health.skin_analysis_seconds()==90.

def test_memory_reserve_keeps_its_own_code_and_other_failures_stay_generic():
    import local_native_worker as W
    from product_dryness import DrynessModelUnavailable
    assert W.failure_response(DrynessModelUnavailable('LOCAL_MEMORY_RESERVE'))==(503,'LOCAL_MEMORY_RESERVE')
    assert W.failure_response(DrynessModelUnavailable('DRYNESS_MODEL_UNAVAILABLE'))==(503,'LOCAL_MODEL_OR_RESOURCE_UNAVAILABLE')
    assert W.failure_response(OSError('private path'))==(503,'LOCAL_MODEL_OR_RESOURCE_UNAVAILABLE')
    assert W.failure_response(ValueError('private detail'))==(422,'INVALID_LOCAL_GEOMETRY_OR_PHOTO')
    assert W.failure_response(RuntimeError('private detail'))==(503,'LOCAL_ANALYSIS_WORKER_FAILED')

def test_memory_reserve_threshold_is_not_weakened():
    source=(ROOT/'services/core-api/dry_dualscale_runtime_staging.py').read_text('utf8')
    assert "available<400*2**20:raise DrynessModelUnavailable('LOCAL_MEMORY_RESERVE')" in source
