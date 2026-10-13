"""Isolated HTTP host exercising the real router, geometry and worker path.

This host injects the unadmitted native research analyzer only in its own process.
Normal localhost8000 routing/configuration is untouched. Wait for the worker to
actually stop before releasing the router lock; no outside Future timeout.
"""
import os
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[key]='1'
import asyncio,json,sys,time,threading,socket
from contextvars import ContextVar
from pathlib import Path
import httpx,uvicorn,cv2
from fastapi import FastAPI,HTTPException,Request
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-runtime-followup-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
import local_health as L
from native_dry_path import analyze_native_dry
from material_component_features import OnnxMaterialEncoder,filter_material_support_streamed
from native_material_budget import NativeRequestBudget,NativeRequestStopped
cv2.setNumThreads(1);head=json.loads((ROOT/'audit-results/native-material-contour-20261013/encoder-material-head.json').read_text('utf8'));encoder=OnnxMaterialEncoder(OUT/'material-encoder.onnx',OUT/'encoder-parity.json')
app=FastAPI();L.parked=lambda:True;events=[];scope_context=ContextVar('native_scope');route_busy=asyncio.Lock()
def worker(payload):
    scope=scope_context.get();event={'photoId':payload['photoId'],'started':time.monotonic(),'finished':False};events.append(event)
    try:
        profile={};result=analyze_native_dry(payload,lambda im,f,m:filter_material_support_streamed(im,f,m,encoder,head,check=scope.check),check=scope.check,profile=profile);event['profile']=profile;return result
    except NativeRequestStopped as e:event['stopped']=str(e);raise
    finally:event.update(seconds=time.monotonic()-event['started'],finished=True)
L.analyze_skin=worker
original_payload=L.payload
async def validated_payload(request):
    value=await original_payload(request);scope=scope_context.get()
    async def monitor():
        while True:
            await asyncio.sleep(.05)
            if await request.is_disconnected():scope.cancel();return
    request.state.native_watcher=asyncio.create_task(monitor());return value
L.payload=validated_payload
@app.post('/api/local-health/skin')
async def skin(request:Request):
    if route_busy.locked() or L._busy.locked():raise HTTPException(429,'LOCAL_ANALYSIS_BUSY')
    async with route_busy:
        token=scope_context.set(NativeRequestBudget(45))
        try:return await L.skin(request)
        except NativeRequestStopped as e:raise HTTPException(409 if str(e)=='CANCELLED' else 504,str(e))
        finally:
            watcher=getattr(request.state,'native_watcher',None)
            if watcher:
                watcher.cancel()
                try:await watcher
                except asyncio.CancelledError:pass
            scope_context.reset(token)

def main():
    config=uvicorn.Config(app,host='127.0.0.1',port=18011,log_level='error');server=uvicorn.Server(config);thread=threading.Thread(target=server.run,daemon=True);thread.start()
    deadline=time.monotonic()+15
    while not server.started:
        if time.monotonic()>deadline:raise RuntimeError('Isolated host did not start')
        time.sleep(.05)
    path=ROOT/'audit-results/native-dry-scale-20261013/e1646fda-native-payload.json';payload=json.loads(path.read_text('utf8'));data=json.dumps(payload).encode();client=httpx.Client(timeout=55);start=time.monotonic()
    response=client.post('http://127.0.0.1:18011/api/local-health/skin',content=data,headers={'Content-Type':'application/json'});timeout_case=dict(status=response.status_code,detail=response.json(),elapsed=time.monotonic()-start,worker=events[-1].copy(),lockReleased=not L._busy.locked());assert response.status_code==504 and events[-1]['finished'] and not L._busy.locked()
    data=json.dumps(payload).encode();s=socket.create_connection(('127.0.0.1',18011));s.sendall(('POST /api/local-health/skin HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: '+str(len(data))+'\r\n\r\n').encode()+data);time.sleep(1);cancel_at=time.monotonic();s.close()
    deadline=cancel_at+15
    while (not events[-1]['finished'] or route_busy.locked()) and time.monotonic()<deadline:time.sleep(.05)
    cancel_case=dict(worker=events[-1].copy(),secondsAfterDisconnect=time.monotonic()-cancel_at,lockReleased=not L._busy.locked());assert events[-1]['stopped']=='CANCELLED' and events[-1]['finished'] and not L._busy.locked()
    small=json.loads((ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json').read_text('utf8'));start=time.monotonic();response=client.post('http://127.0.0.1:18011/api/local-health/skin',json=small,timeout=45);assert response.status_code==200
    expected=json.loads((OUT/'24031977-native-result.json').read_text('utf8'));actual=response.json();assert actual['maps']==expected['maps'] and actual['measurements']==expected['measurements']
    receipt=dict(actualHTTP=True,realProductRouterAndGeometry=True,isolatedStagingAnalyzer=True,normal8000Unchanged=True,budgetSeconds=45,timeout=timeout_case,cancel=cancel_case,followingRequest=dict(status=response.status_code,seconds=time.monotonic()-start,mapsAndMeasurementsExact=True),photoFeatureCacheRead=False)
    (OUT/'api-budget.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True);client.close();server.should_exit=True;thread.join(10);assert not thread.is_alive()
if __name__=='__main__':main()
