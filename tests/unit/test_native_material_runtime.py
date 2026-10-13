"""Request lifetime, exact crop reuse and expression observation provenance."""
import sys
from pathlib import Path
import cv2,numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import material_component_features as M,native_flake_support as F,contour_appearance as C
from native_material_budget import NativeRequestBudget,NativeRequestStopped

def test_cancel_and_deadline_stop_real_proposal_work():
    scope=NativeRequestBudget();scope.cancel()
    with pytest.raises(NativeRequestStopped,match='CANCELLED'):F.native_field(np.zeros((80,80,3),np.uint8),check=scope.check)
    scope=NativeRequestBudget();scope.deadline=0
    with pytest.raises(NativeRequestStopped,match='TIMEOUT'):F.proposal_tile(np.zeros((80,80,3),np.uint8),check=scope.check)
    with pytest.raises(ValueError):NativeRequestBudget(46)

def test_request_crop_reuse_never_reuses_a_different_source(monkeypatch):
    ids=np.zeros((60,60),np.int32);ids[10:13,10:13]=1;ids[40:43,40:43]=2
    rows=[dict(componentId=i,rect=[10,10,3,3],geometry=[0.]*12) for i in [1,2]]
    monkeypatch.setattr(M,'describe',lambda *args:(ids,rows));calls=[]
    class Encoder:
        def extract(self,crops,batch):calls.append(len(crops));return np.zeros((len(crops),1280),np.float32)
    head=dict(mean=np.zeros(2572),std=np.ones(2572),coefficients=np.zeros(2572),intercept=1.,threshold=.5)
    image=np.full((60,60,3),120,np.uint8);field=(ids>0).astype(np.float32)*.5
    output,receipt=M.filter_material_support_streamed(image,field,1.,Encoder(),head)
    assert np.array_equal(output,field) and sum(calls)==2 and receipt['identicalCropsReused']==2
    M.filter_material_support_streamed(image,field,1.,Encoder(),head)
    assert sum(calls)==4 # A new request recomputes; no photo cache.

def test_feature_blocks_are_scaled_after_standardization():
    X=np.array([[1,2,3],[2,3,5],[3,4,7],[4,5,9]],float)
    head=M.fit_classifier(X,[0,0,1,1],['a','a','b','b'],feature_group_sizes=[2,1])
    assert np.allclose(head['std'],X.std(0)*[np.sqrt(2),np.sqrt(2),1])

def test_expression_support_does_not_override_open_mouth_or_quality():
    names=['mouthSmileLeft','mouthSmileRight','mouthFrownLeft','mouthFrownRight','mouthPucker','mouthPressLeft','mouthPressRight','cheekPuff','jawOpen']
    payload={'photoId':'a','expressionObservation':dict(photoId='a',version='local-mediapipe-expression-support-v1',scores={k:0.01 for k in names})}
    assert C.expression_reason(payload,.01,-.12) is None
    assert C.expression_reason(payload,.11,-.12)=='EXPRESSION_OPEN_MOUTH_OR_SMILE'
    payload['expressionObservation']['scores']['mouthSmileLeft']=.8
    assert C.expression_reason(payload,.01,-.12)=='EXPRESSION_OPEN_MOUTH_OR_SMILE'
    payload['expressionObservation']['photoId']='b'
    with pytest.raises(ValueError,match='MISMATCH'):C.expression_reason(payload,.01,-.12)
    assert C.expression_reason({'photoId':'a'},.01,-.12)=='EXPRESSION_OPEN_MOUTH_OR_SMILE'
