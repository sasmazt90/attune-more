from pathlib import Path
import subprocess


def test_end_during_pending_reply_keeps_completed_exchanges():
    result=subprocess.run(['node','tests/unit/mental_pending_end_runtime.cjs'],
                          cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
