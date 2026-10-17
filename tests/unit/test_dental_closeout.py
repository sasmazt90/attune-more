import json,sys,time,asyncio
from pathlib import Path
import numpy as np,pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
import dental_analysis as dental

@pytest.mark.parametrize('bad',['negative-probability','above-one','empty','nan','inf'])
def test_invalid_network_output_fails_closed(monkeypatch,bad):
 class Session:
  def run(self,*_):
   a=np.zeros((1,2100,7),np.float32);a[0,0]=[160,160,40,40,.9,.9,.01]
   if bad=='negative-probability':a[0,0,4:6]=-.9
   if bad=='above-one':a[0,0,4:6]=1.2
   if bad=='empty':a=a[:,:0]
   if bad=='nan':a[0,0,0]=np.nan
   if bad=='inf':a[0,0,0]=np.inf
   return [a]
 monkeypatch.setattr(dental,'_session',Session());monkeypatch.setattr(dental,'_model_identity',None)
 monkeypatch.setattr(dental,'_manifest',json.loads((dental.ROOT/'models/dental-yolox-s.json').read_text()))
 with pytest.raises(dental.DentalModelError,match='INVALID_MODEL_OUTPUT'):dental.model_candidates(np.full((100,100,3),150,np.uint8),np.ones((100,100),bool))

def test_crop_origin_clipping_classes_and_degenerate_boxes(monkeypatch):
 class Session:
  def run(self,*_):
   a=np.zeros((1,2100,7),np.float32)
   a[0,0]=[80,80,40,40,.9,.9,.01];a[0,1]=[220,220,40,40,.9,.01,.9]
   a[0,2]=[80,80,-10,40,.9,.9,.01]
   return [a]
 monkeypatch.setattr(dental,'_session',Session());monkeypatch.setattr(dental,'_model_identity',None)
 monkeypatch.setattr(dental,'_manifest',json.loads((dental.ROOT/'models/dental-yolox-s.json').read_text()))
 image=np.full((200,300,3),150,np.uint8);mouth=np.zeros((200,300),bool);mouth[50:150,100:200]=True
 _,ratio,origin=dental.prepare_model_input(image,mouth,320)
 boxes,meta=dental.model_candidates(image,mouth)
 assert {c['classCode'] for c in boxes}=={'D','d'} and len(boxes)==2
 for c,index in zip(boxes,[0,1]):
  center=[80,220][index]/ratio
  assert abs(c['bounds']['x']-(center-20/ratio+origin[0]))<1e-5
  assert c['bounds']['width']>0 and c['confidence']<=1
 assert meta['decisionThreshold']==.35

def test_model_contract_rejects_reversed_classes_before_session(monkeypatch,tmp_path):
 import hashlib
 models=tmp_path/'models';models.mkdir();data=b'only-hash-contract-no-inference';(models/'dental-yolox-s.onnx').write_bytes(data)
 cfg=json.loads((dental.ROOT/'models/dental-yolox-s.json').read_text());cfg.update(modelHash=hashlib.sha256(data).hexdigest(),classes=['d','D']);(models/'dental-yolox-s.json').write_text(json.dumps(cfg))
 monkeypatch.setattr(dental,'ROOT',tmp_path);monkeypatch.setattr(dental,'_session',None)
 with pytest.raises(dental.DentalModelError,match='MODEL_CONTRACT_MISMATCH'):dental.model_candidates(np.zeros((30,30,3),np.uint8),np.ones((30,30),bool))

def test_incomplete_api_camera_is_not_a_scan():
 from test_local_health_boundary import request
 for poses in [['FRONT'],['FRONT','RIGHT','LEFT'],['FRONT','LEFT','RIGHT','BITE']]:
  r=request('/api/local-health/dental',{'processingConsent':True,'captures':[{'pose':p,'landmarks':[{'x':.5,'y':.5}]*478} for p in poses]})
  assert r.status_code==422

def test_cooperative_budget_discards_late_success_and_drains_worker(monkeypatch):
 import local_health as api
 from native_material_budget import NativeRequestBudget
 monkeypatch.setattr(api,'NativeRequestBudget',None,raising=False)
 import native_material_budget
 monkeypatch.setattr(native_material_budget,'NativeRequestBudget',lambda seconds:NativeRequestBudget(.03))
 monkeypatch.setattr(api,'parked',lambda:True)
 class Request:
  async def is_disconnected(self):return False
 def work(value,check):time.sleep(.06);check();return {'must-not-return':True}
 from fastapi import HTTPException
 with pytest.raises(HTTPException) as e:asyncio.run(api.dental_work(Request(),work,{}))
 assert e.value.status_code==408 and not api._busy.locked()
