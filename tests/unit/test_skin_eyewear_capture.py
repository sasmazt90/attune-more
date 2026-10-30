"""Skin-only capture boundary, stable release and stale-response regressions."""
import sys,asyncio,json,subprocess
from pathlib import Path
import numpy as np,cv2,httpx
from fastapi import FastAPI
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import local_health as L,skin_eyewear as E

def post(path,data,monkeypatch):
    app=FastAPI();app.include_router(L.router);monkeypatch.setattr(L,'parked',lambda:True)
    async def request():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:return await client.post(path,json=data)
    return asyncio.run(request())

def test_rejected_full_photo_never_runs_analysis_or_returns_zero(monkeypatch):
    import base64
    image=np.full((128,128,3),130,np.uint8);photo='data:image/png;base64,'+base64.b64encode(cv2.imencode('.png',image)[1]).decode()
    from appearance_analysis import decode_photo
    _,identity=decode_photo(photo)
    payload=dict(processingConsent=True,photo=photo,photoId=identity,landmarks=[dict(x=.5,y=.5)]*478,meshes={'forehead':dict(points=[dict(x=1,y=1)]*3,edges=[[0,1]])},conditions={})
    monkeypatch.setattr(E,'classify_source',lambda *args:dict(status='EYEWEAR_PRESENT',version=E.VERSION,modelHash=E.MODEL_HASH));calls=[]
    import appearance_analysis
    from local_native_worker import skin_analysis
    monkeypatch.setattr(appearance_analysis,'analyze_skin',lambda value:calls.append(value))
    # Execute the same worker function in-process so the rejection fixture
    # applies across the new process boundary; no successful model is faked.
    async def boundary(operation,value,*_):
        assert operation=='skin'
        return skin_analysis(value)
    monkeypatch.setattr(L.native_analysis,'run',boundary)
    response=post('/api/local-health/skin',payload,monkeypatch)
    assert response.status_code==409 and response.json()=={'detail':'SKIN_EYEWEAR_PRESENT'} and not calls
    assert not L._busy.locked()

def test_unknown_eye_check_is_not_clear_and_has_no_result(monkeypatch):
    import base64
    photo='data:image/png;base64,'+base64.b64encode(cv2.imencode('.png',np.full((112,112,3),120,np.uint8))[1]).decode()
    monkeypatch.setattr(E,'classify_roi',lambda *args:dict(status='UNCERTAIN',version=E.VERSION,modelHash=E.MODEL_HASH,probability=.4))
    response=post('/api/local-health/skin/capture-check',dict(processingConsent=True,policy=E.VERSION,frameToken='own-frame',eyePhoto=photo),monkeypatch)
    assert response.json()['status']=='UNCERTAIN' and response.json()['frameToken']=='own-frame'
    assert 'measurements' not in response.json() and 'maps' not in response.json()
    # Reject a compact huge-dimension PNG header before image allocation.
    bad=bytearray(__import__('base64').b64decode(photo.split(',')[1]));bad[16:20]=(4096).to_bytes(4,'big')
    response=post('/api/local-health/skin/capture-check',dict(processingConsent=True,policy=E.VERSION,frameToken='own-frame',eyePhoto='data:image/png;base64,'+base64.b64encode(bad).decode()),monkeypatch)
    assert response.status_code==422

def ts(tmp_path,script):
    bootstrap="const fs=require('fs'),assert=require('assert/strict');const load=require('./tests/unit/ts_source_loader.cjs')("+json.dumps(str(tmp_path))+ ");"+script
    result=subprocess.run(['node','-e',bootstrap],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
    assert result.returncode==0,result.stdout+result.stderr

def test_clear_frames_need_stability_and_any_obstruction_resets(tmp_path):
    ts(tmp_path,"""const E=load('skinEyewear'),g=new E.SkinEyewearGate();
assert(!g.observe('CLEAR',0));assert(!g.observe('CLEAR',899));assert(g.observe('CLEAR',900));
assert(!g.observe('EYEWEAR_PRESENT',950));assert(!g.observe('CLEAR',1000));assert(!g.observe('CLEAR',1899));assert(g.observe('CLEAR',1900));
assert(!g.observe('UNCERTAIN',2000));assert(!g.observe('CLEAR',2100));g.reset();assert(!g.observe('CLEAR',3000));
""")

def test_cancelled_eye_response_cannot_release_new_capture(tmp_path):
    ts(tmp_path,"""const E=load('skinEyewear');let complete,body;global.document={createElement:()=>({getContext:()=>({drawImage:()=>{}}),toDataURL:()=> 'data:image/png;base64,fixture'})};
global.fetch=(_url,options)=>{body=JSON.parse(options.body);return new Promise(resolve=>complete=resolve);};
const points=Array.from({length:478},(_,i)=>({x:.3+(i%2)*.4,y:.3+(i%3)*.05}));
const check=new E.SkinEyewearCheck();const request=check.assess({width:640,height:480},{faceDetected:true,isMediaPipeActive:true,landmarks:points},()=>true);
check.cancel();complete({ok:true,json:async()=>({frameToken:body.frameToken,version:E.SKIN_CAPTURE_POLICY,modelHash:E.SKIN_EYEWEAR_MODEL_HASH,status:'CLEAR'})});
request.then(()=>{throw Error('Stale response accepted');},error=>assert.equal(error.message,'STALE_EYEWEAR_FRAME')).catch(error=>{console.error(error);process.exitCode=1;});
""")

def test_old_capture_scope_is_not_same_comparison(tmp_path):
    ts(tmp_path,"""const I=load('skinIndicators');const m={scope:'regional',region:'chin',methodVersion:'appearance-cv-6',modelHash:null,datasetHash:null,evidenceHash:null,target:'dry',unit:'%',validation:'appearance-proxy'};
const old={id:'dry',method:'appearance-cv-6',unit:'%',measurement:m,appearance:{normalizationVersion:'eligible-flake-luma-union-v3',captureConditions:{},components:{samplingSupportVersion:'same'}}};
const now=structuredClone(old);now.appearance.captureConditions.skinCapturePolicy='glasses-free-skin-capture-v1';assert(!I.canCompareIndicator(old,now));assert(I.canCompareIndicator(now,structuredClone(now)));
""")
