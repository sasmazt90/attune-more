"""Production React render contracts; synthetic records, not physical listening evidence."""
from pathlib import Path
import subprocess

def test_hearing_results_and_panels_use_selected_record():
 result=subprocess.run(['node','tests/unit/hearing_results_ui.cjs'],cwd=Path(__file__).resolve().parents[2],text=True,capture_output=True,timeout=30)
 assert result.returncode==0,result.stdout+result.stderr
