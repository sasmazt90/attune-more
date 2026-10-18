"""Adult product population scope, not raw model accuracy."""
import copy,json,subprocess,sys
from pathlib import Path
import numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import dental_analysis as D

def candidate(code):return dict(classCode=code,confidence=.81,bounds=dict(x=10,y=10,width=12,height=10))
def result(codes,valid=True):
 return dict(methodVersion='camera-v1',sourceType='camera',views=[dict(photoId='a'*64,pose='FRONT',sourceWidth=100,sourceHeight=80,quality=dict(valid=valid),caries=dict(methodVersion='raw-v1',modelVersion='model',quality='valid' if valid else 'insufficient',value=len(codes) if valid else None,unit='candidate-count',decisionThreshold=.35,modelHash='b'*64,candidates=[candidate(c) for c in codes]),accumulation=dict(value=None,candidates=[],quality='insufficient',methodVersion='border-v2'),alignment=dict(value=None,contours=[],rows=None))])

@pytest.mark.parametrize('codes',[['D','d'],['d'],['D'],[]])
def test_one_adult_list_count_bounds_record_and_no_raw_mutation(codes):
 raw=result(codes);before=copy.deepcopy(raw);adult=D.adult_product_result(raw)
 expected=[c for c in raw['views'][0]['caries']['candidates'] if c['classCode']=='D']
 assert adult['views'][0]['caries']['candidates']==expected
 assert adult['views'][0]['caries']['value']==len(expected)
 assert raw==before and D.adult_product_result(adult)==adult
 assert adult['views'][0]['accumulation']==raw['views'][0]['accumulation']
 assert adult['views'][0]['caries']['modelHash']==raw['views'][0]['caries']['modelHash']
 assert adult['views'][0]['caries']['methodVersion']=='raw-v1+'+D.ADULT_POLICY

def test_quality_failure_is_not_zero():
 r=D.adult_product_result(result([],False));assert r['views'][0]['caries']['value'] is None and r['views'][0]['caries']['quality']=='insufficient'

def test_controlled_raw_D_d_decodes_then_same_adult_boundary(monkeypatch):
 class Session:
  def run(self,*_):
   raw=np.zeros((1,2100,7),np.float32)
   raw[0,0]=[80,80,40,40,.9,.9,.01];raw[0,1]=[220,220,40,40,.9,.01,.9]
   return [raw]
 monkeypatch.setattr(D,'_session',Session());monkeypatch.setattr(D,'_model_identity',None)
 monkeypatch.setattr(D,'_manifest',json.loads((D.ROOT/'models/dental-yolox-s.json').read_text()))
 mouth=np.zeros((200,300),bool);mouth[50:150,100:200]=True
 decoded,meta=D.model_candidates(np.full((200,300,3),150,np.uint8),mouth)
 assert {c['classCode'] for c in decoded}=={'D','d'}
 r=result([]);r['views'][0]['caries'].update(**meta,value=len(decoded),candidates=decoded)
 adult=D.adult_product_result(r)['views'][0]['caries']
 assert adult['candidates']==[c for c in decoded if c['classCode']=='D'] and adult['value']==1
@pytest.mark.parametrize('change',[lambda r:r['views'][0]['caries'].update(candidates=None),lambda r:r['views'][0]['caries'].update(candidates=[None]),lambda r:r['views'][0]['caries'].update(value=None),lambda r:r['views'][0]['caries']['candidates'][0].update(classCode='unknown'),lambda r:r['views'][0]['quality'].update(valid=False)])
def test_invalid_product_cannot_become_healthy_empty(change):
 r=result(['D']);change(r)
 with pytest.raises(D.DentalModelError):D.adult_product_result(r)

def test_camera_and_upload_share_boundary_and_model_errors_propagate(monkeypatch):
 import dental_upload as U
 image=np.full((100,100,3),140,np.uint8);mouth=np.ones((100,100),bool);empty=np.zeros_like(mouth)
 monkeypatch.setattr(D,'decode_photo',lambda _: (image,'a'*64));monkeypatch.setattr(D,'dental_quality',lambda *_:dict(valid=True))
 monkeypatch.setattr(D,'mouth_geometry',lambda *_:(mouth,100,.3,np.zeros((478,2))))
 monkeypatch.setattr(D,'dental_pixels',lambda *_,**kw:(mouth,empty,empty,empty,np.zeros((100,100))))
 monkeypatch.setattr(D,'calculus_candidates',lambda *_:([],200))
 meta=dict(quality='valid',methodVersion='raw-v1',decisionThreshold=.35,modelHash='b'*64,modelVersion='model')
 monkeypatch.setattr(D,'model_candidates',lambda *_:([candidate('D'),candidate('d')],meta))
 monkeypatch.setattr(U,'decode_upload',lambda _:(image,'a'*64,'data:image/png;base64,unused',{}))
 monkeypatch.setattr(U,'upload_roi',lambda *_:(mouth,empty,empty,dict(valid=True,geometrySource='control',roi=dict(x=0,y=0,width=100,height=100))))
 payload=dict(captures=[dict(photo='control',photoId='a'*64,pose='FRONT',landmarks=[])])
 for r in [D.analyze_dental(payload),U.analyze_upload(dict(photo='control'))]:
  assert r['candidatePolicyVersion']==D.ADULT_POLICY and r['views'][0]['caries']['value']==1
  assert [c['classCode'] for c in r['views'][0]['caries']['candidates']]==['D']
 def fail(*_):raise D.DentalModelError('MODEL_INFERENCE_FAILED')
 monkeypatch.setattr(D,'model_candidates',fail)
 for call in [lambda:D.analyze_dental(payload),lambda:U.analyze_upload(dict(photo='control'))]:
  with pytest.raises(D.DentalModelError):call()

def test_new_numeric_record_and_legacy_history_stay_distinct():
 raw=result(['D','d']);adult=D.adult_product_result(raw)
 code=r'''
require('./tests/unit/ts_loader.js');const fs=require('fs'),a=require('assert/strict'),R=require('./apps/vehicle-app/src/utils/dentalResult.ts'),H=require('./apps/vehicle-app/src/utils/healthHistorySeries.ts');
const {raw,adult}=JSON.parse(fs.readFileSync(0,'utf8'));const before=JSON.stringify(raw);
R.validateDentalView(raw.views[0]);a.throws(()=>R.dentalRecordMeasurements(raw));
const rows=R.dentalRecordMeasurements(adult);a.equal(rows[0].caries.value,1);a.deepEqual(rows[0].caries.candidates.map(c=>c.classCode),['D']);
const bad=structuredClone(adult.views[0]);bad.caries.candidates=[...raw.views[0].caries.candidates];bad.caries.value=2;a.throws(()=>R.validateDentalView(bad));
const records=[{id:'legacy',timestamp:'2026-10-17T01:00:00Z',sourceType:'camera',measurements:raw.views},{id:'adult',timestamp:'2026-10-17T02:00:00Z',sourceType:'camera',measurements:rows}];
const snapshot=JSON.stringify(records),series=H.buildHistorySeries('dental',records);a.equal(series.filter(s=>s.criterion==='caries').length,2);a.equal(JSON.stringify(records),snapshot);a.equal(JSON.stringify(raw),before);a.equal(R.DENTAL_ACCUMULATION_LABEL,'Diş taşı birikimi');a(series.filter(s=>s.criterion==='accumulation').every(s=>s.label===R.DENTAL_ACCUMULATION_LABEL));
'''
 p=subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps(dict(raw=raw,adult=adult)),text=True,capture_output=True)
 assert p.returncode==0,p.stdout+p.stderr
