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
phrases={'tr':'Bu yeni ve kişisel olmayan örnekte 1287 sayısı var. Kısa bir mola verebilirsiniz.','en':'This new nonpersonal example includes the number 1287. You could take a short break.','de':'Dieses neue, nichtpersönliche Beispiel enthält die Zahl 1287. Sie könnten eine kurze Pause machen.'}
async def disconnected():return False
async def run():
    rows=[]
    for language,text in phrases.items():
        started=perf_counter()
        try:
            _,_,_,profile=load_configuration(args.config,language)
            raw=await generate(text,language,lambda:True,disconnected)
            path=args.output/(language+'.wav');path.write_bytes(raw)
            rows.append({'language':language,'status':'PASS','profile':profile['id'],'seconds':perf_counter()-started,'format':'PCM16 mono 24000 Hz WAV','bytes':len(raw),'sha256':digest(path),'text':text,'browserPlayback':'UNVERIFIED','femaleNaturalness':'UNVERIFIED'})
        except Exception:
            rows.append({'language':language,'status':'BLOCKED','seconds':perf_counter()-started,'reason':'Configuration or offline model inference unavailable; no success inferred','browserPlayback':'NOT_EXECUTED'})
        (args.output/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    return all(x['status']=='PASS' for x in rows)
sys.exit(0 if asyncio.run(run()) else 69)
