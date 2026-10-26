"""Three-pose skin photo storage (actual store + AST-extracted page code); see skin_photo_three_pose_storage.cjs."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_three_pose_photo_storage_and_record_loader():
    r = subprocess.run(['node', 'tests/unit/skin_photo_three_pose_storage.cjs'], cwd=ROOT, text=True, capture_output=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert '"passed": 9' in r.stdout, r.stdout
