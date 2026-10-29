"""Execute the actual display-only TS mapper and localization catalog; no camera/inference."""
from pathlib import Path
import subprocess

def test_dental_camera_error_localization():
    result = subprocess.run(['node', '--test', 'tests/unit/dental_camera_error.cjs'],
                            cwd=Path(__file__).resolve().parents[2], text=True,
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
