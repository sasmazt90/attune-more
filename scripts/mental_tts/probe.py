"""Explicit offline, nonpersonal model probe; not vehicle or human listening acceptance."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
from mental_neural_tts import load_configuration,generate,digest
parser=argparse.ArgumentParser();parser.add_argument('--config',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
if args.output.exists():raise SystemExit('Use a NEW evidence directory; never overwrite originals')
args.output.mkdir(parents=True);os.environ['ATTUNE_MENTAL_TTS_CONFIG']=str(args.config.resolve())
phrases={
 'tr':'Merhaba, bugün kendinizi nasıl hissediyorsunuz? İsterseniz sizi dinleyebilirim. Aklınızdan geçenleri birlikte konuşabiliriz.',
 'en':"Hello, how are you feeling today? I'm here to listen if you'd like to talk. We can take some time to discuss what's on your mind.",
 'de':'Hallo, wie geht es Ihnen heute? Wenn Sie möchten, können Sie mir erzählen, was Sie gerade beschäftigt. Ich höre Ihnen gerne zu.'}

async def disconnected():return False
async def run():
    rows=[]
    for language,text in phrases.items():
        started=perf_counter()
        try:
            _,_,_,profile=load_configuration(args.config,language)
            raw=await generate(text,language,lambda:True,disconnected)
            path=args.output/(language+'.wav');path.write_bytes(raw)
            rows.append({'language':language,'status':'PASS','profile':profile['id'],'seconds':perf_counter()-started,'format':'PCM16 mono 24000 Hz WAV','bytes':len(raw),'sha256':digest(path),'text':text,'browserPlayback':'UNVERIFIED','conditioning':'official-default','voiceGender':'not constrained'})
        except Exception:
            rows.append({'language':language,'status':'BLOCKED','seconds':perf_counter()-started,'reason':'Configuration or offline model inference unavailable; no success inferred','browserPlayback':'NOT_EXECUTED'})
        (args.output/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    return all(x['status']=='PASS' for x in rows)
sys.exit(0 if asyncio.run(run()) else 69)
