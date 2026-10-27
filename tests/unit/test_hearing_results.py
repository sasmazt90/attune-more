"""Persisted response-time and chart semantics. Synthetic fixtures, no physical hearing claim."""
from pathlib import Path
import subprocess

def test_selected_record_timing_and_missing_measurements():
 result=subprocess.run(['node','tests/unit/hearing_results.cjs'],cwd=Path(__file__).resolve().parents[2],text=True,capture_output=True,timeout=30)
 assert result.returncode==0,result.stdout+result.stderr
