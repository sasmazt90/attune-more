"""Source identity, measurement state and navigation contract regression."""
import subprocess
from pathlib import Path

def test_skin_dental_restoration_contract():
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run(['node','tests/unit/skin_dental_repair.cjs'],cwd=root,capture_output=True,text=True,encoding='utf8',timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
