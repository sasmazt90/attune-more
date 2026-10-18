"""Current source-function contract on preserved licensed natural sources.
This is separate from the subsequently required normal-production API check.
"""
from pathlib import Path
import json,sys,time,psutil
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
from appearance_analysis import analyze_skin,VERSION
SOURCE=ROOT/'audit-results/all-health-20261010/natural-skin';OUT=ROOT/'audit-results/focused-skin-20261010/source-contract';OUT.mkdir(exist_ok=True)
rows=[]
for index in [0,1,3,5]:
    payload=json.loads((SOURCE/f'{index}-payload-private.json').read_text());start=time.perf_counter();result=analyze_skin(payload)
    rows.append(dict(index=index,method=VERSION,photoId=result['photoId'],samePhoto=result['photoId']==payload['photoId'],general=result['general'],regional=result['measurements'],mapMetadata={key:{k:v for k,v in value.items() if k not in ('dataUrl','validMaskUrl')} for key,value in result['maps'].items()},ms=(time.perf_counter()-start)*1000,rss=psutil.Process().memory_info().rss))
    assert len(result['general']['measurements'])==9 and result['photoId']==payload['photoId']
    assert all(x['value'] is None for values in result['measurements'].values() for x in values if x['id']=='acne'),'No failed heuristic or rejected detector in normal source path'
    assert all(key.split(':')[-1]!='acne' for key in result['maps'])
    assert all(x['value'] is None or 0<=x['value']<=100 for x in result['general']['measurements'])
(OUT/'proof.json').write_text(json.dumps(dict(sourceFunctionOnly=True,normalAPIAcceptance=False,physicalUserAcceptance=False,rows=rows),indent=2),'utf8')
print('PASS current-source overview/provenance/null-acne; API build verification remains')
