"""Same captured production inputs: preserve non-eye methods and lower-face maps.

No network, model selection, training, user records or AG working files.
"""
import json, os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/periorbital-v5-integration-20261012'
BASE=ROOT/'.runtime/ag-periorbital-baseline-20261012/services/core-api'
rows=[]
for prefix in ('20031f35','36e4010b','beda0290','4b13b16a','e0ee9f0c','5bd42346'):
    captured=json.loads((OUT/(prefix+'-browser-api.json')).read_text('utf8'))
    code='import sys,json;sys.path[:0]='+repr([str(BASE),str(ROOT/'services/core-api'),str(ROOT/'.runtime/python-packages')])+';import appearance_analysis as a;print(json.dumps(a.analyze_skin(json.loads(sys.stdin.read()))))'
    env={k:v for k,v in os.environ.items() if k not in ('ATTUNE_ROBOFLOW_API_KEY','ROBOFLOW_API_KEY','ATTUNE_LOAD_LOCAL_ENV')}
    ran=subprocess.run([sys.executable,'-c',code],input=json.dumps(captured['productPayload']),text=True,capture_output=True,cwd=ROOT,env=env,timeout=90)
    assert ran.returncode==0,ran.stderr
    baseline=json.loads(ran.stdout);actual=captured['response'];checked=[]
    for region, measurements in baseline['measurements'].items():
        for old in measurements:
            if region=='periorbital' and old['id'] in ('bags','dark','lines'):continue
            new=next(v for v in actual['measurements'][region] if v['id']==old['id'])
            assert old==new,(prefix,region,old['id'],'measurement drift')
            key=region+':'+old['id']
            assert baseline['maps'].get(key)==actual['maps'].get(key),(prefix,key,'map drift')
            checked.append(key)
    for region in ('rightCheek','leftCheek','chin'):
        assert region+':sag' in checked
    (OUT/(prefix+'-browser-baseline.json')).write_text(json.dumps(baseline,ensure_ascii=False,indent=2),'utf8')
    rows.append(dict(source=prefix,unchangedMeasurementsAndMaps=checked))
    print(json.dumps(dict(source=prefix,unchanged=len(checked))),flush=True)
(OUT/'same-product-input-preservation.json').write_text(json.dumps(dict(status='PASS',baselineCommit='d596873c363a57324d38dc974e5ad65186ea9866',rows=rows,hostedCalls=0,training=False,userRecordsTouched=False),indent=2),'utf8')
