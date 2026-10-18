"""Keyless UI lifecycle fixture. NEVER evidence of live OpenAI chat/TTS.

Real API validation, consent, crisis, driving and storage code still run.
Only generation is replaced with deterministic synthetic replies. Normal speech
is deliberately unavailable; audio lifecycle suites explicitly supply their transport fixture.
"""
import os
import sys
from pathlib import Path

assert os.getenv('ATTUNE_LOAD_LOCAL_ENV') == '0'
assert not os.getenv('OPENAI_API_KEY')
os.environ['OPENAI_API_KEY'] = 'attune-ui-contract-fixture-not-a-credential'
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import main
from mental_provider import LocalFallbackMentalProvider, LocalFallbackSessionAnalyzer

class ConversationFixture(LocalFallbackMentalProvider):
    def generate_reply(self, *args, **kwargs):
        result = super().generate_reply(*args, **kwargs)
        result.update(providerType='LIVE_OPENAI', controlledTestFixture=True)
        return result

class SummaryFixture(LocalFallbackSessionAnalyzer):
    def analyze_session(self, *args, **kwargs):
        result = super().analyze_session(*args, **kwargs)
        result.update(providerType='LIVE_OPENAI', controlledTestFixture=True)
        return result

main.get_active_mental_provider = lambda: ConversationFixture()
main.get_active_session_analyzer = lambda: SummaryFixture()

def forbidden_client(*_args, **_kwargs):
    raise RuntimeError('Network provider dispatch forbidden in keyless UI fixture')

main.get_openai_client = forbidden_client

async def speech_unavailable(*_args, **_kwargs):
    from fastapi import HTTPException
    raise HTTPException(status_code=503, detail='KEYLESS_AUDIO_FIXTURE_UNAVAILABLE')

main.edge_mental_speech = speech_unavailable
main.fixed_vision_speech = speech_unavailable

if __name__ == '__main__':
    import uvicorn
    print('KEYLESS UI CONTRACT FIXTURE; LIVE ACCEPTANCE FALSE', flush=True)
    uvicorn.run(main.app, host='127.0.0.1', port=8000)
