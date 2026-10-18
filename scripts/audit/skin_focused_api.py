"""Actual normal-launcher API with preserved licensed sources; no user history."""
from pathlib import Path
import copy,json,time,urllib.request,urllib.error,psutil
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/focused-skin-20261010/api-final';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'audit-results/all-health-20261010/natural-skin'
registry=json.loads((ROOT/'services/core-api/models/skin-focused.json').read_text('utf8'))
session=json.loads(Path(r'C:\Users\PC\Desktop\YENİ İŞ\Applications\7. TOGG\.launcher\session.json').read_text())
assert session['status']=='running' and not session['verification']
backend=psutil.Process(session['backend_pid']);runs=[]

def request(payload):
    req=urllib.request.Request('http://127.0.0.1:8000/api/local-health/skin',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=90) as response:return json.loads(response.read())

for index in [0,0,1,3,5]:
    payload=json.loads((SOURCE/f'{index}-payload-private.json').read_text('utf8'));before=backend.memory_info().rss;start=time.perf_counter();result=request(payload);elapsed=(time.perf_counter()-start)*1000
    assert result['photoId']==payload['photoId'] and len(result['general']['measurements'])==9
    assert all(v['value'] is None or 0<=v['value']<=100 for values in result['measurements'].values() for v in values)
    assert all(v['normalizationVersion'] and v['scoreDirection']=='higher-is-more-visible' for v in result['general']['measurements'])
    if not registry['models']['acne']['accepted']:
        assert all(v['value'] is None for values in result['measurements'].values() for v in values if v['id']=='acne')
        assert not any(key.endswith(':acne') for key in result['maps'])
    if not registry['models']['type']['accepted']:assert result['general']['skinType']['value'] is None
    for v in result['general']['measurements']:
        if v['type']=='trained_prediction':assert registry['models']['degrees']['accepted'] and v['modelHash']==registry['models']['degrees']['sha256'] and v['id'] in registry['models']['degrees']['acceptedTargets'] and v['id']!='acne'
    runs.append(dict(index=index,repeat=index==0 and bool(runs),ms=elapsed,rssBefore=before,rssAfter=backend.memory_info().rss,photoId=result['photoId'],general=result['general'],regional=result['measurements'],mapMetadata={key:{k:v for k,v in value.items() if k not in ('dataUrl','validMaskUrl')} for key,value in result['maps'].items()}))
    (OUT/'runs-private.json').write_text(json.dumps(runs,indent=2),'utf8')
invalid=json.loads((SOURCE/'0-payload-private.json').read_text('utf8'));invalid['qualityValid']=False;result=request(invalid)
assert all(v['value'] is None and v['quality']!='valid' for values in result['measurements'].values() for v in values)
assert all(v['value'] is None for v in result['general']['measurements']) and result['general']['skinType']['value'] is None
assert not result['maps']
invalid['photoId']='0'*64
try:request(invalid);raise AssertionError('Wrong source hash accepted')
except urllib.error.HTTPError as error:assert error.code in (400,422)
proof=dict(status='PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),sourceVersion='appearance-cv-6',normalLauncherAPI=True,photographicSources=True,physicalUserAcceptance=False,clinicalAcceptance=False,sourceHashNegative=True,qualityNegativeNull=True,firstVsWarmRequestMs=[runs[0]['ms'],runs[1]['ms']],modelRegistry=registry['version'],acceptedModels={k:v['accepted'] for k,v in registry['models'].items()},normalHistoryTouched=False)
(OUT/'proof.json').write_text(json.dumps(proof,indent=2),'utf8');print(json.dumps(proof),flush=True)
