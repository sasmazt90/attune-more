#!/usr/bin/env python3
"""Reproducible synthetic routing probes; no provider access or measured API cost."""
import argparse
import json
from pathlib import Path
import resource
import statistics
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/core-api'))
from mental_structured import route,FlowState

PROBES=[
 ('en','I lost my job yesterday and I feel sad.',['B01','B02','B03']),
 ('tr','Dün işimi kaybettim ve çok üzgünüm.',['B01','B02','B03']),
 ('de','Ich habe meinen Job verloren und bin traurig.',['B01','B02','B03']),
 ('en','Every day I cannot sleep and I feel worried.',['B01','B02','B06','B07']),
 ('tr','Her gün uyuyamıyorum ve kaygılı hissediyorum.',['B01','B02','B06','B07']),
 ('de','Ich kann jeden Tag nicht schlafen und fühle mich ängstlich.',['B01','B02','B06','B07']),
 ('en','I thought nobody would help me.',['B01','B05']),
 ('tr','Aklımdan kimse yardım etmez düşüncesi geçti.',['B01','B05']),
 ('de','Ich dachte, niemand würde mir helfen.',['B01','B05']),
 ('en','Talking to my friend helped me.',['B01','B09']),
 ('tr','Arkadaşımla konuşmak yardımcı oldu.',['B01','B09']),
 ('de','Das Gespräch mit meiner Freundin hat mir geholfen.',['B01','B09']),
 ('en','I need some quiet time.',['B01','B10']),
 ('tr','Biraz sessizliğe ihtiyacım var.',['B01','B10']),
 ('de','Ich brauche etwas Ruhe.',['B01','B10']),
 # Deliberately unsupported colloquial/ASR probes measure omissions, too.
 ('en','got the sack yday, proper gutted',['B01','B02','B03']),
 ('tr','işimi kaybetim dün moralim sıfır',['B01','B02','B03']),
 ('de','job weg seit gestern, total geknickt',['B01','B02','B03']),
]


def evaluate(repeats=20):
    route('warm up','en')
    latencies=[];rows=[]
    for lang,text,expected in PROBES:
        for _ in range(repeats):
            start=perf_counter();result=route(text,lang,FlowState(language=lang));latencies.append((perf_counter()-start)*1000)
        supplied=result['structuredState']['fulfilled']
        rows.append({'language':lang,'syntheticInput':text,'expectedFulfilled':expected,'actualFulfilled':supplied,
                     'expectedObjectivesFound':all(n in supplied for n in expected),'nextNode':result['decision']['node']})
    return {'scope':'18 authored development probes, not held-out model accuracy or clinical validation',
            'runs':len(latencies),'probeResults':rows,'probesWithAllExpectedObjectives':sum(r['expectedObjectivesFound'] for r in rows),
            'routingLatencyMs':{'median':round(statistics.median(latencies),3),'p95':round(sorted(latencies)[int(len(latencies)*.95)],3)},
            'processPeakRSSKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'runtime':'Python standard library routing + Pydantic; CPU, warmed content/prototype caches',
            'networkRequestsDuringEvaluation':0,'paidAPICalls':0,'actualAPICost':None,'actualTTSTiming':None,
            'note':'RAM is peak whole evaluation process, not isolated classifier memory. Missing objectives are retained in this report.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=json.dumps(evaluate(),ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(result)
    else:print(result,end='')
