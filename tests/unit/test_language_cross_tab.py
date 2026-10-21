from pathlib import Path
import subprocess

def test_external_tab_cannot_change_active_assessment_locale():
    result=subprocess.run(['node','tests/unit/language_cross_tab_runtime.cjs'],cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
