"""Cacheless requests and preserved stress proposal; no normal selector writes."""
import os
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[key]='1'
import json,sys,time,hashlib
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-camera-scope-20261013';OLD=ROOT/'audit-results/material-runtime-followup-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
with HeavyJobLease('CD-cacheless-preserved-material-scope',peak_mib=600,minimum_available_mib=1000) as lease:
    import cv2,numpy as np
    import native_dry_path as N,material_component_features as M
    from native_material_budget import NativeRequestBudget,NativeRequestStopped
    cv2.setNumThreads(1);rows=[]
    # First test the native stress proposal alone against its stored ORIGINAL
    # output, not a second expensive 2472-crop encoder run.
    stress=ROOT/'audit-results/native-dry-scale-20261013/e1646fda-native-payload.json';payload=json.loads(stress.read_text('utf8'));profile={};start=time.monotonic()
    progress=OUT/'cacheless-profile-progress.json'
    if progress.exists():rows=json.loads(progress.read_text('utf8'))
    if not any(r['source']=='e1646fda' for r in rows):
        result=N.analyze_native_dry(payload,check=lease.check,profile=profile);expected=json.loads((ROOT/'audit-results/native-dry-scale-20261013/e1646fda-native-staging.json').read_text('utf8'))
        exact=result['maps']==expected['maps'] and result['measurements']==expected['measurements'] and result['general']==expected['general'];assert exact
        rows.append(dict(source='e1646fda',scope='stress-native-proposal-only',elapsed=time.monotonic()-start,profile=profile,sourceImageSize=result['nativeMetadata']['sourceImageSize'],metadata=result['nativeMetadata'],mapsAndScoresExact=exact,fullEncoderRequestMeasured=False))
        progress.write_text(json.dumps(rows,indent=2),'utf8');del result,expected
    del payload
    encoder=M.OnnxMaterialEncoder(OLD/'material-encoder.onnx',OLD/'encoder-parity.json');head=json.loads((ROOT/'audit-results/native-material-contour-20261013/encoder-material-balanced-head.json').read_text('utf8'))
    paths=[('9bab7ab2',ROOT/'audit-results/dry-sag-component-followup-20261013/product/9bab7ab2/9bab7ab2-automatic-payload.json'),('24031977',ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json')]
    camera=OUT/'camera-1280-native-payload.json'
    if camera.exists():paths.append(('camera-1280-native',camera))
    for source,path in paths:
        lease.check();payload=json.loads(path.read_text('utf8'));profile={};details=[];budget=NativeRequestBudget(45);start=time.monotonic()
        def check():lease.check();budget.check()
        def classify(im,f,metric):
            filtered,meta=M.filter_material_support_streamed(im,f,metric,encoder,head,check=check,details=details)
            meta['classifierVersion']='frozen-imagenet-two-crop-material-block-balanced-v2-staging';return filtered,meta
        try:
            result=N.analyze_native_dry(payload,classify,check=check,profile=profile)
            previous=OLD/f'{source}-balanced-native-result.json';exact=None
            if previous.exists():
                expected=json.loads(previous.read_text('utf8'));exact=result['maps']==expected['maps'] and result['measurements']==expected['measurements'] and result['general']==expected['general'];assert exact
            row=dict(source=source,status='complete',elapsed=time.monotonic()-start,profile=profile,sourceImageSize=result['nativeMetadata']['sourceImageSize'],sourceFacePixels=next(iter(result['measurements'].values()))['evaluatedArea']['sourceFacePixels'],metadata=result['nativeMetadata'],mapsAndScoresExact=exact,within45Seconds=True,normalProductEnabled=False,photoFeatureCacheRead=False)
            (OUT/f'{source}-optimized-result.json').write_text(json.dumps(result),'utf8');(OUT/f'{source}-optimized-components.json').write_text(json.dumps(details),'utf8')
        except NativeRequestStopped as e:row=dict(source=source,status=str(e),elapsed=time.monotonic()-start,within45Seconds=False,partialResultSaved=False,healthyZeroSaved=False,normalProductEnabled=False)
        rows.append(row);(OUT/'cacheless-profile-progress.json').write_text(json.dumps(rows,indent=2),'utf8');print(json.dumps({k:v for k,v in row.items() if k not in ['metadata']}),flush=True);del payload,details
    receipt=dict(rows=rows,resource=lease.receipt(),sourceImageResize=False,persistentPhotoFeatureCache=False,newEncoderExport=False,normalProductEnabled=False,stressFullPipelineStillUnadmitted=True)
    (OUT/'cacheless-profile.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt['resource']),flush=True)
