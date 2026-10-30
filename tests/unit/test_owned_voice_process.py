"""Real OS descendants, no neural result substitution or acceptance claim."""
import asyncio
import json
import sys
from pathlib import Path
import psutil
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import mental_neural_tts as neural


def test_motion_reaps_real_voice_launcher_and_child(monkeypatch, tmp_path):
    config = tmp_path / 'config.json'
    config.write_text('{}')
    marker = tmp_path / 'child.json'
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_CONFIG', str(config))
    real_spawn = asyncio.create_subprocess_exec
    code = ('import subprocess,sys,time,json;from pathlib import Path;'
            'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);'
            f'Path({str(marker)!r}).write_text(json.dumps(p.pid));time.sleep(60)')
    launched = []

    async def spawn(*args, **kwargs):
        process = await real_spawn(sys._base_executable, '-c', code, **kwargs)
        launched.append(process)
        return process

    monkeypatch.setattr(neural.asyncio, 'create_subprocess_exec', spawn)

    async def scenario():
        async def disconnected():
            return False
        with pytest.raises(HTTPException) as caught:
            await asyncio.wait_for(neural.generate('Synthetic cancellation test', 'en',
                lambda: not marker.exists(), disconnected), timeout=15)
        assert caught.value.status_code == 409
        assert launched[0].returncode is not None
        assert not psutil.pid_exists(json.loads(marker.read_text()))
        assert not neural._busy

    asyncio.run(scenario())
