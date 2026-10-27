"""Bind prepared recordings and dynamic closure to one verified conditioning profile."""
import os
import json
from pathlib import Path
from fastapi import HTTPException
from mental_neural_tts import load_configuration, digest

ROOT=Path(__file__).resolve().parents[2]

def verify_speaker(language, speaker_profile='official-default'):
    try:
        if speaker_profile not in ('official-default','female-calm-v1'):
            raise ValueError('UNKNOWN_SPEAKER')
        name='manifest.json' if speaker_profile=='official-default' else 'female-calm-v1-manifest.json'
        manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/mental/v1'/name).read_text('utf-8'))
        _,directory,reference,profile=load_configuration(os.environ['ATTUNE_MENTAL_TTS_CONFIG'],language)
        if profile['id']!=speaker_profile or manifest['speakerProfile']!=speaker_profile or digest(reference or directory/'conds.pt')!=manifest['conditioningSha256']:
            raise ValueError('SPEAKER_MISMATCH')
        if profile.get('generation')!=manifest.get('generation'):
            raise ValueError('GENERATION_PROFILE_MISMATCH')
        if speaker_profile=='female-calm-v1' and (not manifest.get('sampleApproval',{}).get('ownerApprovedAt') or len(manifest['entries'])!=9 or any(e['approvalStatus']!='approved' for e in manifest['entries'])):
            raise ValueError('OWNER_LISTENING_APPROVAL_REQUIRED')
    except (OSError,ValueError,KeyError):
        raise HTTPException(503,'STRUCTURED_SPEAKER_UNAVAILABLE') from None
