"""Finite real-source controls; no fit, split change, hosted call or dry score."""
import sys,json,base64,hashlib,time
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-closeout-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
CASES=[('9bab7ab2','audit-results/dry-sag-component-followup-20261013/product/9bab7ab2/9bab7ab2-automatic-payload.json',True),('NASA','audit-results/material-closeout-20261013/camera-native-payload.json',False),('24031977','audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json',False),('29cc4ba7','audit-results/native-camera-scope-20261013/29cc4ba7-current-capture-payload.json',False),('4d05d72b','audit-results/material-closeout-20261013/4d05d72b-payload.json',False)]
with HeavyJobLease('CDC-small-eyewear-control',peak_mib=250,minimum_available_mib=650) as lease:
    import cv2,numpy as np
    from skin_eyewear import classify_source
    cv2.setNumThreads(1);rows=[]
    for name,path,label in CASES:
        lease.check();file=ROOT/path;p=json.loads(file.read_text('utf8'));im=cv2.imdecode(np.frombuffer(base64.b64decode(p['photo'].split(',')[1]),np.uint8),1);h,w=im.shape[:2]
        start=time.monotonic();r=classify_source(im,p['landmarks'])
        row=dict(source=name,actualEyewear=label,detected=r['status']=='EYEWEAR_PRESENT',seconds=time.monotonic()-start,sourceSize=[w,h],payloadSHA256=hashlib.sha256(file.read_bytes()).hexdigest(),**r)
        rows.append(row);print(json.dumps(row),flush=True);del im,p
    (OUT/'eyewear-model-comparison.json').write_text(json.dumps(dict(rows=rows,resource=lease.receipt(),threshold=.5,clearMaximum=.3,noFit=True,smallEngineeringScope=True,oneUniqueGlassesPositive=True,clinicalAccuracyClaim=False)),'utf8')
