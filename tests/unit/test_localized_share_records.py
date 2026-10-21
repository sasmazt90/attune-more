"""Actual record transaction/selectors. Synthetic storage only."""
from pathlib import Path
import subprocess

def test_mental_timestamp_storage_and_live_locale_selection():
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node','tests/unit/localized_share_runtime.cjs'],cwd=root,text=True,capture_output=True,timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
