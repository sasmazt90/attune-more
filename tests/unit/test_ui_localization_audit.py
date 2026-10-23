"""All-module result/dialog and app-wide UI localization regression."""
from pathlib import Path
import subprocess


def test_ui_results_dialogs_and_support_pages_are_localized():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(['node', 'tests/unit/ui_localization_audit_runtime.cjs'], cwd=root,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
