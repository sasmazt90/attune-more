"""Only available genuine current-browser snapshots; never force a pose."""
import json,sys,time,hashlib
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'audit-results/native-camera-scope-20261013';OUT=ROOT/'audit-results/material-closeout-20261013';OUT.mkdir(exist_ok=True);sys.path.insert(0,str(ROOT/'services/core-api'))
with HeavyJobLease('CDC-source-bound-neutral-contour',peak_mib=400,minimum_available_mib=800) as lease:
    import cv2
    from contour_appearance import analyze_contour
    cv2.setNumThreads(1);rows=[]
    selection=json.loads((SOURCE/'contour-probe-selection.json').read_text('utf8'))
    for source in selection:
        lease.check();prefix=source['sha256'][:8];path=OUT/f"{prefix}-payload.json"
        if not path.exists():path=SOURCE/f"{prefix}-current-capture-payload.json"
        if not path.exists():
            capture=OUT/f'{prefix}-capture.json'
            observed=json.loads(capture.read_text('utf8')) if capture.exists() else None
            rows.append(dict(source=source['sha256'],status='CURRENT_CAPTURE_REJECTED' if observed else 'NOT_CAPTURED_RESOURCE_GUARD',capture=observed,neutralProminenceGroundTruth=False));continue
        existing=OUT/f'{prefix}-current-contour-result.json'
        if existing.exists():
            prior=json.loads((OUT/'neutral-contour-probe.json').read_text('utf8'))
            row=next(r for r in prior['rows'] if r['source']==source['sha256'] and r['status']=='CURRENT_BROWSER_SOURCE_MEASURED');rows.append(row);continue
        payload=json.loads(path.read_text('utf8'));start=time.monotonic();result=analyze_contour(payload,check=lease.check);elapsed=time.monotonic()-start
        (OUT/f"{source['sha256'][:8]}-current-contour-result.json").write_text(json.dumps(result),'utf8')
        rows.append(dict(source=source['sha256'],group=source['group'],payloadSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),photoId=payload['photoId'],conditions=payload['conditions'],expressionObservation=payload['expressionObservation'],status='CURRENT_BROWSER_SOURCE_MEASURED',elapsed=elapsed,neutralProminenceGroundTruth=False,rows={k:{a:b for a,b in v.items() if a!='trace'} for k,v in result['measurements'].items()}));del payload,result
    receipt=dict(rows=rows,resource=lease.receipt(),ageAsLabel=False,ordinaryFoldAsLabel=False,interiorFoldAsExteriorTarget=False,normalProductEnabled=False,remainingInventoryUnreviewed=True)
    (OUT/'neutral-contour-probe.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True)
