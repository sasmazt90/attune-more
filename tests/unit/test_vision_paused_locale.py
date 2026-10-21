"""Actual component source with explicit capture-free platform fixtures."""
from pathlib import Path
import subprocess

def test_paused_recognition_restarts_only_for_language_changes():
    result=subprocess.run(['node','tests/unit/vision_paused_locale_runtime.cjs'],cwd=Path(__file__).resolve().parents[2],text=True,capture_output=True,timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
