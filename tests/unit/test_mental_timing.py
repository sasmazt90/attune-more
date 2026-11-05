"""Numerical telemetry must be bounded, private, and isolated between requests."""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import mental_timing as timing
from mental_neural_tts import safe_worker_phases


def test_interleaved_requests_do_not_share_measurements():
    async def request(seconds):
        timing.begin()
        timing.record('verify', seconds)
        await asyncio.sleep(0)
        timing.record('total', seconds + 1)
        return timing.server_timing()
    async def run():
        return await asyncio.gather(request(1), request(2))
    assert asyncio.run(run()) == ['tts-total;dur=2000, tts-verify;dur=1000', 'tts-total;dur=3000, tts-verify;dur=2000']


def test_worker_phases_strip_private_data_and_reject_invalid_numbers():
    timing.begin()
    rows = [{'phase': phase, 'elapsedSeconds': seconds, 'cpuSeconds': 0, 'peakRSSKiB': 10, 'text': 'private'}
            for phase, seconds in [('inference', 2), ('encode-wav', 5), ('complete', 5.1)]]
    timing.phases(safe_worker_phases(rows))
    assert timing.server_timing() == 'tts-worker-inference;dur=3000, tts-worker-encode-wav;dur=100.0'
    for value in (float('nan'), float('inf'), -1, True, 'private'):
        timing.record('total', value)
    timing.record('private', 1)
    assert 'private' not in timing.server_timing() and 'total' not in timing.server_timing()
    rows[0]['elapsedSeconds'] = float('nan')
    assert safe_worker_phases(rows) == []
    timing.begin()
    assert timing.server_timing() == ''
