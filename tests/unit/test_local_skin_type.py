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
def test_uncalibrated_visible_proxies_do_not_override_global_argmax(dry,global_value):
 value=T.regional_decision(base(global_value),regions(dry))
 assert value['value']==global_value and value['confidence']==.8 and not value['decisionTrace']['applied']
 assert all(row['state']=='unknown' for row in value['regionalMap']['regions'].values())
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


def product_result(dry=0):
 return dict(general=dict(skinType={**base('oily'),'inferenceKind':'local-onnx'},measurements=[]),measurements=regions(dry),maps={})

def test_final_native_zero_replaces_old_positive_trace_without_reinference(monkeypatch):
 monkeypatch.setattr(T,'infer',lambda *_:pytest.fail('Finalization must not run model'))
 r=product_result(4)
 old=T.regional_decision(r['general']['skinType'],r['measurements'])
 r['general']['skinType']=old
 for rows_ in r['measurements'].values():
  row=next(x for x in rows_ if x['id']=='dry');row.update(value=0,methodVersion='appearance-native-dry-2',normalizationVersion='native-final')
 result=T.finalize_product_type(r);t=result['general']['skinType']
 assert t['value']=='oily' and t['basePrediction']['value']=='oily'
 assert t['decisionTrace']['regions']['rightCheek']['dry']['value']==0
 assert t['decisionTrace']['regions']['rightCheek']['state'] is None
 assert result['general']['regionalSkinMap']['regions']['rightCheek']['fill']=='lightgrey'
 assert t['decisionTrace']['regions']['rightCheek']['dry']['methodVersion']=='appearance-native-dry-2'
 assert t['decisionTrace']['regions']['rightCheek']['dry']['quality']=='valid'
 assert result['activeCriterionMethods']['criteria']['type']['overview']['methodVersion']==t['methodVersion']==t['modelVersion']
 assert t['methodVersion'].count(T.RULE)==1

@pytest.mark.parametrize('failure',['invalid','missing'])
def test_final_invalid_or_missing_retracts_previously_matched_combination(failure):
 r=product_result(4);r['general']['skinType']=T.regional_decision(r['general']['skinType'],r['measurements'])
 if failure=='missing':r['measurements']['leftCheek']=[row for row in r['measurements']['leftCheek'] if row['id']!='dry']
 else:next(row for row in r['measurements']['leftCheek'] if row['id']=='dry').update(value=None,quality='insufficient',methodVersion='appearance-native-dry-2')
 result=T.finalize_product_type(r);t=result['general']['skinType']
 assert t['value']=='oily' and t['confidence']==.8 and not t['decisionTrace']['complete'] and not t['decisionTrace']['applied']
 assert t['decisionTrace']['regions']['leftCheek']['state'] is None
 assert t['decisionTrace']['regions']['leftCheek']['inputs']['dry']==(None if failure=='missing' else {k:next(row for row in r['measurements']['leftCheek'] if row['id']=='dry').get(k) for k in ['value','quality','methodVersion','normalizationVersion','evaluatedArea','limitationCode']})

@pytest.mark.parametrize('dry',[0,4])
def test_product_finalization_is_idempotent_and_preserves_base(dry):
 r=product_result(dry);before=copy.deepcopy(r['measurements'])
 T.finalize_product_type(r);first=copy.deepcopy(r);T.finalize_product_type(r)
 assert r==first and r['general']['skinType']['value']=='oily'
 assert r['general']['skinType']['basePrediction']=={**base('oily'),'inferenceKind':'local-onnx'}
 for region,original in before.items():
  for old,current in zip(original,r['measurements'][region]):
   assert all(current[k]==v for k,v in old.items())

def test_legacy_derived_combination_is_never_treated_as_base_model():
 b={**base('normal'), 'value':'combination','decisionTrace':{'baseValue':'oily'}}
 assert T.regional_decision(b,regions())['value'] is None

def test_normal_endpoint_finalizes_after_all_product_replacements(monkeypatch):
 import asyncio,local_health as L,product_dryness as P,acne_v5_product as A
 monkeypatch.setattr(L,'parked',lambda:True);monkeypatch.setattr(L,'skin_geometry',lambda _:None)
 async def payload(_):return {'experimentalAcneV5':True}
 monkeypatch.setattr(L,'payload',payload);monkeypatch.setattr(L,'skin_capture_preflight',lambda _:dict(version='preserved',modelHash='eyewear'))
 events=[]
 def product(*_):events.append('native-dry');return product_result(0)
 def acne(r,*_):
  events.append('acne');next(row for row in r['measurements']['leftCheek'] if row['id']=='dry').update(value=None,quality='insufficient');return r
 monkeypatch.setattr(P,'analyze_product',product);monkeypatch.setattr(A,'replace_acne',acne)
 class Request:
  async def is_disconnected(self):return False
 async def run():
  L._busy=asyncio.Lock();return await L.skin(Request())
 result=asyncio.run(run())
 assert events==['native-dry','acne']
 assert result['general']['skinType']['value']=='oily' and not result['general']['skinType']['decisionTrace']['complete']
 assert result['activeCriterionMethods']['criteria']['type']['overview']['methodVersion'].endswith(T.RULE)

