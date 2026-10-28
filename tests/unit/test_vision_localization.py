"""Vision display text across all locales, without camera/ASR/score changes."""
from pathlib import Path
import subprocess


def test_complete_vision_localization():
    result = subprocess.run(
        ['node', 'tests/unit/vision_localization_runtime.cjs'],
        cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
