"""Production frontend/proxy source with labelled non-inference fixtures."""
from pathlib import Path
import subprocess
import pytest

@pytest.mark.parametrize('script',['mental_neural_proxy_runtime.cjs','mental_neural_client_runtime.cjs','mental_neural_conversation_runtime.cjs','mental_cross_tab_settings_runtime.cjs'])
def test_neural_frontend_boundaries(script):
    result=subprocess.run(['node','tests/unit/'+script],cwd=Path(__file__).resolve().parents[2],text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
