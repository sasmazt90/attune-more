"""Focused real translation/record adapter checks; all records are synthetic."""
from pathlib import Path
import subprocess
import pytest


@pytest.mark.parametrize('language', ['tr', 'en', 'de'])
def test_measured_share_composition_and_preserved_storage(language):
    result = subprocess.run(['node', 'tests/unit/health_share_composition_runtime.cjs', language],
                            cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
