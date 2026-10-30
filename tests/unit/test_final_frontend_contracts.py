"""Execute new frontend regressions locally and in the normal backend CI job."""
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('script',[
    'skin_worker_lifecycle.cjs',
    'mental_history_permission.cjs',
    'local_analysis_error.cjs',
])
def test_frontend_remediation_contract(script):
    result=subprocess.run(['node',str(ROOT/'tests/unit'/script)],cwd=ROOT,
        capture_output=True,text=True,encoding='utf8',timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
