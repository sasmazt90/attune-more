"""Compile the new runner without a credential, external request or old-ledger write."""
import importlib.util,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load():
    spec=importlib.util.spec_from_file_location('final_acceptance',ROOT/'scripts/final-provider-acceptance.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def test_new_preparation_preserves_old_evidence_and_archives_failure(tmp_path):
    runner=load();before=runner.historical_hashes();runner.prepare(tmp_path)
    assert before==runner.historical_hashes()
    for name in ['backend.py','ui.py']:
        code=(tmp_path/name).read_text(encoding='utf-8');compile(code,name,'exec')
        assert 'normalizer = subprocess.Popen' in code
        assert 'assert normalized_reply' in code
    ui=(tmp_path/'ui.py').read_text(encoding='utf-8')
    assert "playing['time']<transfer['bodyCompleteAt']" not in ui
    final=ui[ui.index(' finally:'):]
    for key in ['productionTiming','sendStarts','speechStarts','speechHeaders','transferEvents','uiPhases']:
        assert key in final
    assert 'max_retries' in (tmp_path/'backend.py').read_text(encoding='utf-8')
def test_no_approval_refuses_execution_before_writing():
    result=subprocess.run([sys.executable,str(ROOT/'scripts/final-provider-acceptance.py'),'--run-id','guided-final-no-approval-unit'],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode!=0 and 'zero provider dispatch' in result.stdout+result.stderr
    assert not (ROOT/'audit-results/live-provider/guided-final-no-approval-unit').exists()
