"""Exact consumer Edge profiles; no alternate provider or voice fallback.

The -10 Hz offset is provisional until auditory comparison of 0/-10/-20 Hz.
It is not a verified mapping of Clipchamp Low.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class SpeechProfile:
    voice: str
    rate: str
    pitch: str

VISION_TTS_PROFILE = SpeechProfile('tr-TR-AhmetNeural', '-10%', '-10Hz')
MENTAL_WELLBEING_TTS_PROFILE = SpeechProfile('tr-TR-EmelNeural', '-10%', '-10Hz')
