"""Real product router on an isolated port; no normal selector/profile writes."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import json,sys,time,threading,hashlib,asyncio,faulthandler
from pathlib import Path
from contextvars import ContextVar
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-closeout-20261013';PREV=ROOT/'audit-results/material-runtime-followup-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
with HeavyJobLease('CDC-native-group-head-http-profile',peak_mib=500,minimum_available_mib=900) as lease:
    import numpy as np,cv2,httpx,uvicorn
    from fastapi import FastAPI,HTTPException,Request
    import local_health as L,native_dry_path as N,material_component_features as M
    from native_material_budget import NativeRequestBudget,NativeRequestStopped
    cv2.setNumThreads(1);L.parked=lambda:True;events=[];phases=[];context=ContextVar('native_request');gate=asyncio.Lock();app=FastAPI();head_paths=[ROOT/'audit-results/native-material-contour-20261013/encoder-material-balanced-head.json',OUT/'source-group-head.json'];heads=[json.loads(p.read_text('utf8')) for p in head_paths];encoder=M.OnnxMaterialEncoder(PREV/'material-encoder.onnx',PREV/'encoder-parity.json',intra_op_threads=4,batch_limit=4,cpu_mem_arena=False);current_head=[0]
    def phase(name):
        phases.append(dict(stage=name,at=time.monotonic()));(OUT/'http-phases.json').write_text(json.dumps(phases),'utf8')
    def worker(payload):
        phase('worker-entered');budget=context.get();profile={};event=dict(photoId=payload['photoId'],started=time.monotonic(),finished=False,headSHA256=hashlib.sha256(head_paths[current_head[0]].read_bytes()).hexdigest());events.append(event);details=[]
        def check():budget.check();lease.check();budget.check()
        def classify(im,field,metric):return M.filter_material_support_streamed(im,field,metric,encoder,heads[current_head[0]],check=check,details=details)
        try:
            result=N.analyze_native_dry(payload,classify,check=check,profile=profile);event.update(profile=profile,metadata=result['nativeMetadata']);event['result']=result;event['details']=details;return result
        except NativeRequestStopped as e:event['stopped']=str(e);raise
        except Exception as e:event['failed']=str(e);raise
        finally:event.update(finished=True,seconds=time.monotonic()-event['started'])
    L.analyze_skin=worker;original_payload=L.payload
    async def validated(request):
        phase('body-read-start')
        value=await original_payload(request);scope=context.get()
        phase('body-read-complete')
        async def monitor():
            while True:
                await asyncio.sleep(.05)
                if await request.is_disconnected():scope.cancel();return
        request.state.watcher=asyncio.create_task(monitor());return value
    L.payload=validated
    @app.post('/api/local-health/skin')
    async def skin(request:Request):
        phase('route-entered')
        if gate.locked() or L._busy.locked():raise HTTPException(429,'LOCAL_ANALYSIS_BUSY')
        async with gate:
            token=context.set(NativeRequestBudget(45))
            try:return await L.skin(request)
            except NativeRequestStopped as e:raise HTTPException(409 if str(e)=='CANCELLED' else 504,str(e))
            finally:
                watcher=getattr(request.state,'watcher',None)
                if watcher:
                    watcher.cancel()
                    try:await watcher
                    except asyncio.CancelledError:pass
                context.reset(token)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=18013,log_level='error'));thread=threading.Thread(target=server.run);thread.start();deadline=time.monotonic()+15
    while not server.started:
        if time.monotonic()>deadline:raise RuntimeError('Own isolated API did not start')
        time.sleep(.05)
    try:
        paths=[('9bab7ab2',ROOT/'audit-results/dry-sag-component-followup-20261013/product/9bab7ab2/9bab7ab2-automatic-payload.json'),('24031977',ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json'),('e1646fda',ROOT/'audit-results/native-dry-scale-20261013/e1646fda-native-payload.json')];camera=OUT/'camera-native-payload.json'
        camera_only='--camera-only' in sys.argv
        if camera_only and not camera.exists():raise RuntimeError('No current successful camera snapshot')
        if camera.exists():paths.append(('current-camera',camera))
        rows=[]
        with httpx.Client(timeout=60) as client:
            for head_index,selected in ([(0,[('current-camera',camera)])] if camera_only else [(0,paths[:1])] if '--baseline-only' in sys.argv else [(0,paths[:1]),(1,paths)]):
                current_head[0]=head_index
                for source,path in selected:
                    lease.check();payload=json.loads(path.read_text('utf8'));payload['hostedProcessingConsent']=False;start=time.monotonic();event_count=len(events);phase('client-post-start')
                    with (OUT/'http-stack.txt').open('w',encoding='utf8') as trace:
                        faulthandler.dump_traceback_later(20,file=trace)
                        try:response=client.post('http://127.0.0.1:18013/api/local-health/skin',json=payload)
                        finally:faulthandler.cancel_dump_traceback_later()
                    http_s=time.monotonic()-start
                    # The current capture policy can reject an old eyewear control
                    # before the native analyzer starts. Never reuse a prior worker
                    # event or bypass that policy to reproduce a historical score.
                    if response.status_code in (409,422) and response.json().get('detail') in ('SKIN_EYEWEAR_PRESENT','SKIN_EYEWEAR_CHECK_UNCERTAIN'):
                        rows.append(dict(source=source,headIndex=head_index,status=response.status_code,httpSeconds=http_s,captureRejected=response.json()['detail'],normalProductEnabled=False,newPhotoFeatureCacheRead=False))
                        assert not L._busy.locked()
                        continue
                    if len(events)!=event_count+1:raise RuntimeError('Request did not produce exactly one native worker event; no historical event reused')
                    event=events[-1];result=event.pop('result',None);details=event.pop('details',None);row=dict(source=source,headIndex=head_index,status=response.status_code,httpSeconds=http_s,worker=event,normalProductEnabled=False,newPhotoFeatureCacheRead=False)
                    assert event['finished'] and not L._busy.locked()
                    if response.status_code==200:
                        assert result['photoId']==payload['photoId'];name=f'{source}-head{head_index}';(OUT/f'{name}-result.json').write_text(json.dumps(result),'utf8');(OUT/f'{name}-components.json').write_text(json.dumps(details),'utf8')
                        if head_index==0 and source=='9bab7ab2':
                            expected=json.loads((ROOT/'audit-results/native-camera-scope-20261013/9bab7ab2-optimized-result.json').read_text('utf8'));row['outputConserved']=result['maps']==expected['maps'] and result['measurements']==expected['measurements'] and result['general']==expected['general'];assert row['outputConserved'],'Execution options changed actual support'
                        row.update(sourceImageSize=result['nativeMetadata']['sourceImageSize'],within45Seconds=http_s<=45)
                    else:row.update(partialResultSaved=False,healthyZeroSaved=False,historyRecordSaved=False)
                    rows.append(row);(OUT/('camera-http-profile-progress.json' if camera_only else 'http-profile-progress.json')).write_text(json.dumps(rows,indent=2),'utf8');print(json.dumps({k:v for k,v in row.items() if k!='worker'}),flush=True);del payload,result,details
        receipt=dict(rows=rows,resource=lease.receipt(),actualHTTP=True,realProductRouterAndGeometry=True,isolatedNativeAnalyzer=True,normal8000Unchanged=True,modelOnnxSHA256=encoder.hash,encoderExecution=encoder.execution,photoFeatureCache=False,productionHeadAccepted=False)
        (OUT/('camera-http-profile.json' if camera_only else 'http-profile.json')).write_text(json.dumps(receipt,indent=2),'utf8')
    finally:
        (OUT/('camera-http-final-events.json' if '--camera-only' in sys.argv else 'http-final-events.json')).write_text(json.dumps(dict(phases=phases,events=[{k:v for k,v in event.items() if k not in ['result','details']} for event in events],resource=lease.receipt()),indent=2),'utf8')
        server.should_exit=True;thread.join(10);assert not thread.is_alive()
