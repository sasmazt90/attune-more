from pathlib import Path
import subprocess

def test_new_speech_processor_requires_explicit_renewed_consent():
    result=subprocess.run(['node','tests/unit/mental_speech_consent_runtime.cjs'],cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
