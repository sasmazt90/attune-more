import copy,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import local_skin_type as T
def rows(oil=0,dry=0):
 area=dict(sourcePixels=200,analysisPixels=200,foreheadSourcePixels=100,noseSourcePixels=100)
 return [dict(id=k,value=v,quality='valid',methodVersion='preserved',evaluatedArea=area) for k,v in [('oil',oil),('dry',dry)]]
def base(value='normal'):return dict(value=value,quality='valid',confidence=.8,methodVersion='new-local',modelHash='a'*64)
def regions(dry=0):return dict(nose=rows(10),forehead=rows(10),leftCheek=rows(0,dry),rightCheek=rows(0,dry),chin=rows(0,dry))
@pytest.mark.parametrize('dry',[0,4])
@pytest.mark.parametrize('global_value',['normal','dry','oily'])
def test_user_combination_rule_overrides_all_global_argmax(dry,global_value):
 value=T.regional_decision(base(global_value),regions(dry))
 assert value['value']=='combination' and value['confidence'] is None and value['decisionTrace']['applied']
def test_all_face_oily_is_not_combination():
 r=regions();r.update(leftCheek=rows(10),rightCheek=rows(10),chin=rows(10))
 assert T.regional_decision(base('oily'),r)['value']=='oily'
@pytest.mark.parametrize('failure',['missing','invalid','nan','no-area'])
def test_unknown_region_is_not_normal(failure):
 r=regions()
 if failure=='missing':r.pop('leftCheek')
 elif failure=='invalid':r['leftCheek'][0]['quality']='insufficient'
 elif failure=='nan':r['leftCheek'][0]['value']=float('nan')
 else:r['leftCheek'][0]['evaluatedArea']={}
 result=T.regional_decision(base(),r)
 assert result['value']=='normal' and not result['decisionTrace']['complete'] and not result['decisionTrace']['applied']
def test_no_model_is_not_silently_replaced_by_rule():
 assert T.regional_decision(T.unavailable('MISSING'),regions())['value'] is None
def test_no_input_mutation():
 b=base();r=regions();original=copy.deepcopy((b,r));T.regional_decision(b,r);assert (b,r)==original
def test_missing_weights_and_invalid_image_never_network(monkeypatch,tmp_path):
 monkeypatch.setattr(T,'CONFIG',tmp_path/'absent.json')
 result=T.infer(np.zeros((32,32,3),np.uint8));assert result['value'] is None and result['quality']=='insufficient'
 assert T.infer(None)['value'] is None
def test_product_selector_uses_only_local_fallback(monkeypatch):
 import skin_models as M
 monkeypatch.setattr(M,'load',lambda:dict(sessions={}))
 monkeypatch.setattr(M,'infer_local_type',lambda crop:dict(**base('oily'),inferenceMs=1.,inferenceKind='local-onnx',fileHashVerified=True,sessionLoaded=True))
 monkeypatch.setattr(M,'infer_hosted_type',lambda *a,**k:pytest.fail('Hosted branch must not run'))
 p=[dict(x=.2+(i%2)*.6,y=.2+(i%3)*.2) for i in range(468)]
 assert M.infer(np.zeros((320,320,3),np.uint8),p,True,True)['skinType']['value']=='oily'
