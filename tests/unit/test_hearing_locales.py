"""Locale banks and faults through the production loader; no physical listening claim."""
from pathlib import Path
import subprocess

def test_locale_banks_and_failures():
    result=subprocess.run(['node','tests/unit/hearing_locale_runtime.cjs'],cwd=Path(__file__).resolve().parents[2],text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
