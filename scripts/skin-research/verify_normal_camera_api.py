"""One licensed current-browser snapshot through unchanged normal skin API."""
import os
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[key]='1'
import hashlib,json,sys,time,threading
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-closeout-20261013'
sys.path.insert(0,str(ROOT/'services/core-api'))
with HeavyJobLease('CDC-current-camera-normal-api',peak_mib=400,minimum_available_mib=800) as lease:
    import cv2,httpx,uvicorn
    from fastapi import FastAPI
    import local_health as L
    cv2.setNumThreads(1)
    # Only isolated parked-state wiring. Real payload, geometry, analyzer and config.
    L.parked=lambda:True
    app=FastAPI();app.include_router(L.router)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=18015,log_level='error'))
    thread=threading.Thread(target=server.run);thread.start();deadline=time.monotonic()+15
    try:
        while not server.started:
            if time.monotonic()>deadline:raise RuntimeError('Own API did not start')
            time.sleep(.05)
        path=OUT/'camera-native-payload.json';payload=json.loads(path.read_text('utf8'))
        assert payload['hostedProcessingConsent'] is False
        lease.check();start=time.monotonic()
        with httpx.Client(timeout=45) as client:response=client.post('http://127.0.0.1:18015/api/local-health/skin',json=payload)
        seconds=time.monotonic()-start;lease.check();assert response.status_code==200
        result=response.json();assert result['photoId']==payload['photoId'] and not L._busy.locked()
        (OUT/'camera-normal-api.json').write_text(json.dumps(result),'utf8')
        rows={region:{r['id']:dict(value=r['value'],normalization=r.get('normalizationVersion'),limitation=r.get('limitationCode')) for r in values} for region,values in result['measurements'].items()}
        receipt=dict(actualHTTP=True,normalAnalyzeSkinUnpatched=True,status=response.status_code,httpSeconds=seconds,within45Seconds=seconds<=45,payloadSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),photoId=result['photoId'],cameraCapture=json.loads((OUT/'camera-native-capture.json').read_text('utf8')),measurements=rows,hostedCallsPermitted=False,normalUserRecordsWritten=False,sourceHash=hashlib.sha256((ROOT/'services/core-api/appearance_analysis.py').read_bytes()).hexdigest(),resource=lease.receipt())
        (OUT/'camera-normal-api-receipt.json').write_text(json.dumps(receipt,indent=2),'utf8')
        print(json.dumps(dict(status=response.status_code,httpSeconds=seconds,photoId=result['photoId'],normalAnalyzeSkinUnpatched=True)),flush=True)
    finally:
        server.should_exit=True;thread.join(10);assert not thread.is_alive()
