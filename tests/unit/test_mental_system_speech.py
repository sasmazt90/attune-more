"""Supported API dispatch and fail-closed contracts with explicit platform fixtures."""
from pathlib import Path
import subprocess

def test_dynamic_system_speech_contracts():
    result=subprocess.run(['node','tests/unit/mental_system_speech_runtime.cjs'],cwd=Path(__file__).resolve().parents[2],text=True,capture_output=True,timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
