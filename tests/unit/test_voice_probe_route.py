"""Source-executed voice probe scope and cancellation; no device access."""
from pathlib import Path
import subprocess

def test_voice_probe_is_limited_to_cockpit_and_cancels_on_navigation():
    result=subprocess.run(['node','tests/unit/voice_probe_route_runtime.cjs'],cwd=Path(__file__).resolve().parents[2],text=True,capture_output=True,timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
