"""Remote camera transport lifecycle only; no inference or clinical acceptance."""
from pathlib import Path
import subprocess


def test_remote_camera_consumer_stop_and_source_failure():
    result = subprocess.run(
        ['node', 'tests/unit/demo_camera_lifecycle.cjs'],
        cwd=Path(__file__).resolve().parents[2], text=True,
        capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
