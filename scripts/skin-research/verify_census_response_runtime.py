"""Final normal-backend used/not-used receipts, actual saved browser payloads."""
import json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-source-census-20261013'
receipts=[]
for prefix,wanted in [('f90e68f8',True),('40d781eb',False)]:
    folder=OUT/'product'/prefix;payload=json.loads((folder/(prefix+'-automatic-payload.json')).read_text('utf8'))
    assert payload['hostedProcessingConsent'] is False
    request=urllib.request.Request('http://localhost:8000/api/local-health/skin',json.dumps(payload).encode(),{'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=45) as response:result=json.load(response)
    assert result['photoId']==payload['photoId']
    row=result['modelRuntime']['degrees'];model=result['general']['modelInference'].get('degrees')
    assert row['fileHashVerified'] and row['sessionLoaded'] and row['loadedModelHash']=='65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3'
    assert row['usedInResponse']==wanted
    assert bool(model)==wanted
    if wanted:assert model['modelHash']==row['loadedModelHash'] and row['status']=='used'
    else:assert row['status']=='not-used'
    (folder/(prefix+'-delivery-api.json')).write_text(json.dumps(result,ensure_ascii=False),'utf8')
    receipts.append(dict(source=prefix,photoId=result['photoId'],fileHashVerified=row['fileHashVerified'],sessionLoaded=row['sessionLoaded'],loadedModelHash=row['loadedModelHash'],usedInResponse=row['usedInResponse'],status=row['status'],modelInferenceHash=model['modelHash'] if model else None))
(OUT/'final-response-runtime.json').write_text(json.dumps(receipts,indent=2),'utf8');print(json.dumps(receipts))
