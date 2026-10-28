"""Deterministic language, coverage and actual controller regressions; no ASR claim."""
import subprocess
from pathlib import Path

def test_vision_live_test_repairs():
    result = subprocess.run(['node', 'tests/unit/vision_live_test_runtime.cjs'],
                            cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
