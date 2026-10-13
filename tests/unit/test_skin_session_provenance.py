"""Real local ORT session identity and explicit not-loaded/not-used failure states."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import skin_models as M

@pytest.fixture
def pinned_model(tmp_path,monkeypatch):
    source=M.FOLDER/'skin-focused-degrees.onnx';data=source.read_bytes();digest=hashlib.sha256(data).hexdigest()
    (tmp_path/'degree.onnx').write_bytes(data)
    manifest=dict(classOrder=M.CLASSES,preprocessing={'RGB':True,'size':[224,224],'mean':[.485,.456,.406],'std':[.229,.224,.225],'cropVersion':'camera-crop-v1'},models={'degrees':dict(accepted=True,file='degree.onnx',sha256=digest,version='test-local-degree',targets=['redness'],acceptedTargets=['redness'])})
    path=tmp_path/'skin-focused.json';path.write_text(json.dumps(manifest),'utf8')
    monkeypatch.setattr(M,'FOLDER',tmp_path);monkeypatch.setattr(M,'MANIFEST',path)
    monkeypatch.setattr(M,'infer_hosted_type',lambda *a:dict(value=None,quality='insufficient',confidence=None,methodVersion='unit-consent-denied',providerModelId='unit',inferenceMs=0.,limitationCode='CONSENT_REQUIRED'))
    cached_load=M.load;cached_load.cache_clear();M._SESSION_STATE.clear()
    yield data,digest,manifest
    cached_load.cache_clear();M._SESSION_STATE.clear()

def photo():
    return np.full((500,1000,3),100,np.uint8),[{'x':.3,'y':.2} if i%2 else {'x':.7,'y':.8} for i in range(468)]

def test_session_receives_exact_hashed_bytes_and_response_uses_session_identity(pinned_model,monkeypatch):
    data,digest,_=pinned_model
    import onnxruntime as ort
    original=ort.InferenceSession;received=[]
    def create(model,*a,**kw):received.append(model);return original(model,*a,**kw)
    monkeypatch.setattr(ort,'InferenceSession',create)
    loaded=M.load();assert received==[data]
    item=loaded['sessions']['degrees'];assert item['sessionMetadata']['modelHash']==digest
    # Changing a mutable manifest-derived field cannot change the session identity.
    item['metadata']['sha256']='not-the-loaded-file'
    result=M.infer(*photo(),True)
    runtime=result['modelRuntime']['degrees']
    assert runtime['fileHashVerified'] and runtime['sessionLoaded'] and runtime['usedInResponse']
    assert runtime['loadedModelHash']==result['models']['degrees']['modelHash']==result['degrees']['redness']['modelHash']==digest
    assert runtime['status']=='used'
    with pytest.raises(TypeError):item['sessionMetadata']['modelHash']='tampered'
    manifest=json.loads(M.MANIFEST.read_text('utf8'));manifest['models']['degrees']['sha256']='0'*64
    M.MANIFEST.write_text(json.dumps(manifest),'utf8')
    changed=M.infer(*photo(),True)['modelRuntime']['degrees']
    assert changed['sessionLoaded'] and changed['usedInResponse'] and changed['loadedModelHash']==digest
    assert changed['matchesConfiguredHash'] is False

def test_loaded_session_is_not_used_for_ineligible_quality(pinned_model,monkeypatch):
    _,digest,_=pinned_model;M.load()
    monkeypatch.setattr(M,'load',lambda:pytest.fail('Quality-rejected inference must not load/run a model'))
    result=M.infer(*photo(),False,type_quality_valid=False);row=result['modelRuntime']['degrees']
    assert row['sessionLoaded'] and row['loadedModelHash']==digest
    assert not row['usedInResponse'] and row['status']=='not-used'
    assert result['models']=={} and result['degrees']=={}

def test_failed_load_and_failed_run_are_not_reported_as_used(pinned_model):
    _,digest,manifest=pinned_model
    manifest['models']['degrees']['sha256']='0'*64;M.MANIFEST.write_text(json.dumps(manifest),'utf8')
    result=M.infer(*photo(),True);row=result['modelRuntime']['degrees']
    assert not row['fileHashVerified'] and not row['sessionLoaded'] and row['loadedModelHash'] is None and not row['usedInResponse']
    assert result['failure']=='ACCEPTED_MODEL_UNAVAILABLE' and result['unavailableTargets']==['redness']
    manifest['models']['degrees']['sha256']=digest;M.MANIFEST.write_text(json.dumps(manifest),'utf8');loaded=M.load()
    class Nonfinite:
        def run(self,*args):return [np.array([[np.nan]],np.float32)]
    loaded['sessions']['degrees']['session']=Nonfinite()
    result=M.infer(*photo(),True);row=result['modelRuntime']['degrees']
    assert row['fileHashVerified'] and row['sessionLoaded'] and row['loadedModelHash']==digest
    assert not row['usedInResponse'] and result['degrees']=={}
