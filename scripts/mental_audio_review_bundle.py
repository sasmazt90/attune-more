#!/usr/bin/env python3
"""Build lossless listening previews from the nine generated samples, no TTS.

Never edits source recordings, changes approval, or generates additional speech.
"""
import hashlib
import io
import json
from pathlib import Path
import wave

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'apps/vehicle-app/public'
OUT=ROOT/'docs/mental-structured/listening'


def main():
    manifest=json.loads((PUBLIC/'audio/mental/v1/manifest.json').read_text())
    entries={(e['language'],e['variantId']):e for e in manifest['entries']}
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for language in ('tr','en','de'):
        clips={}
        for variant in ('A-V01','B01-V01','B02-V01'):
            entry=entries[(language,variant)];path=PUBLIC/entry['audioPath'].lstrip('/')
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=entry['sha256'] or entry['approvalStatus']=='pending-generation':raise ValueError('VERIFIED_GENERATED_SAMPLE_REQUIRED')
            with wave.open(io.BytesIO(raw),'rb') as wav:
                if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())!=(1,2,24000):raise ValueError('PCM_FORMAT_MISMATCH')
                clips[variant]=wav.readframes(wav.getnframes())
            rows.append({'language':language,'variantId':variant,'text':entry['exactScript'],'path':str(path.relative_to(ROOT)),
                         'sha256':entry['sha256'],'approvalStatus':entry['approvalStatus'],'speakerProfile':entry['speakerProfile']})
        for question in ('B01-V01','B02-V01'):
            path=OUT/f'{language}-A-V01-{question}.wav'
            buf=io.BytesIO()
            with wave.open(buf,'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000)
                wav.writeframes(clips['A-V01']+b'\0\0'*round(24000*manifest['joinSilenceMs']/1000)+clips[question])
            raw=buf.getvalue()
            if path.exists() and path.read_bytes()!=raw:raise ValueError('EXISTING_REVIEW_PREVIEW_MUST_NOT_BE_OVERWRITTEN')
            if not path.exists():path.write_bytes(raw)
    index={'speakerProfile':manifest['speakerProfile'],'conditioningSha256':manifest['conditioningSha256'],
           'sampleApproval':'pending-owner-listening','generatedSpeechClips':9,'losslessJoinPreviews':6,
           'joinSilenceMs':manifest['joinSilenceMs'],'samples':rows}
    (OUT/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'samples':9,'joinedPreviews':6,'approval':'pending-owner-listening'}))


if __name__=='__main__':main()
