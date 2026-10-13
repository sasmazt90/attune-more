"""Only available genuine current-browser snapshots; never force a pose."""
import json,sys,time,hashlib
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-camera-scope-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
with HeavyJobLease('CD-source-bound-neutral-contour',peak_mib=500,minimum_available_mib=900) as lease:
    import cv2
    from contour_appearance import analyze_contour
    cv2.setNumThreads(1);rows=[]
    selection=json.loads((OUT/'contour-probe-selection.json').read_text('utf8'))
    for source in selection:
        lease.check();path=OUT/f"{source['sha256'][:8]}-current-capture-payload.json"
        if not path.exists():
            rows.append(dict(source=source['sha256'],status='NOT_CAPTURED_RESOURCE_GUARD',neutralProminenceGroundTruth=False));continue
        payload=json.loads(path.read_text('utf8'));start=time.monotonic();result=analyze_contour(payload,check=lease.check);elapsed=time.monotonic()-start
        (OUT/f"{source['sha256'][:8]}-current-contour-result.json").write_text(json.dumps(result),'utf8')
        rows.append(dict(source=source['sha256'],group=source['group'],payloadSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),photoId=payload['photoId'],conditions=payload['conditions'],expressionObservation=payload['expressionObservation'],status='CURRENT_BROWSER_SOURCE_MEASURED',elapsed=elapsed,neutralProminenceGroundTruth=False,rows={k:{a:b for a,b in v.items() if a!='trace'} for k,v in result['measurements'].items()}));del payload,result
    receipt=dict(rows=rows,resource=lease.receipt(),ageAsLabel=False,ordinaryFoldAsLabel=False,interiorFoldAsExteriorTarget=False,normalProductEnabled=False,remainingInventoryUnreviewed=True)
    (OUT/'neutral-contour-probe.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True)
