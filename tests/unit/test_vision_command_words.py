"""Focused production parser regression; no camera/microphone/provider access."""
from pathlib import Path
import subprocess


def test_multilingual_command_words():
    result = subprocess.run(
        ['node', 'tests/unit/vision_command_words_runtime.cjs'],
        cwd=Path(__file__).resolve().parents[2], capture_output=True,
        text=True, timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
