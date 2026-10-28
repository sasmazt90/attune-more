"""Actual sequential controller regressions with explicit platform adapters."""
from pathlib import Path
import subprocess

def test_sequential_vision_conversation():
    result=subprocess.run(['node','tests/unit/vision_conversation_runtime.cjs'],
                          cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
