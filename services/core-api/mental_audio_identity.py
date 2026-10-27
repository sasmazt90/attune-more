"""Bind prepared recordings and dynamic closure to existing default conditioning."""
import os
import json
from pathlib import Path
from fastapi import HTTPException
from mental_neural_tts import load_configuration, digest

ROOT=Path(__file__).resolve().parents[2]

def verify_speaker(language):
    try:
        manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/mental/v1/manifest.json').read_text('utf-8'))
        _,directory,_,profile=load_configuration(os.environ['ATTUNE_MENTAL_TTS_CONFIG'],language)
        if profile['id']!='official-default' or digest(directory/'conds.pt')!=manifest['conditioningSha256']:
            raise ValueError('SPEAKER_MISMATCH')
    except (OSError,ValueError,KeyError):
        raise HTTPException(503,'STRUCTURED_SPEAKER_UNAVAILABLE') from None
