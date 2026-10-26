"""Preprocessing math and rejected-model boundaries; not camera acceptance."""
from pathlib import Path
import json,sys
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import skin_models as M

def test_native_rgb_crop_matches_training_without_changing_source():
    # Deliberate geometry unit input, never claimed to be a detected face.
    points=[{'x':.3,'y':.2} if i%2 else {'x':.7,'y':.8} for i in range(468)]
    source=np.zeros((500,1000,3),np.uint8);source[:]=(30,60,120);before=source.copy()
    actual,transform=M.photo_input(source,points)
    assert transform==dict(x=172,y=0,width=656,height=448,inputWidth=224,inputHeight=224,RGB=True,cropVersion='camera-crop-v1',coordinateSpace='source-pixels')
    expected=(np.array([120,60,30],np.float32)/255-np.array([.485,.456,.406]))/np.array([.229,.224,.225])
    assert actual.shape==(1,3,224,224) and np.allclose(actual[0,:,0,0],expected,atol=1e-6)
    assert np.array_equal(source,before)

def test_rejected_manifest_cannot_load_model_or_make_zero_scores(tmp_path,monkeypatch):
    file=tmp_path/'skin-focused.json';file.write_text(json.dumps(dict(classOrder=M.CLASSES,preprocessing={'RGB':True,'size':[224,224],'mean':[.485,.456,.406],'std':[.229,.224,.225],'cropVersion':'camera-crop-v1'},models={'type':{'accepted':False,'file':'does-not-exist.onnx'}})))
    monkeypatch.setattr(M,'MANIFEST',file);monkeypatch.setattr(M,'FOLDER',tmp_path);M.load.cache_clear()
    try:
        assert M.load()['sessions']=={}
        value=M.infer(np.zeros((20,20,3),np.uint8),[],True)
        assert value['skinType'] is None and value['degrees']=={}
        assert M.infer_acne(np.zeros((20,20,3),np.uint8),[],True) is None
    finally:M.load.cache_clear()

def test_cross_tile_nms_deduplicates_same_source_focus():
    boxes=M._nms([[100,100,110,110,.8],[101,100,111,110,.7],[180,180,191,191,.6]])
    assert len(boxes)==2 and boxes[0][:4]==[100,100,110,110]

def test_accepted_degree_load_failure_preserves_unavailable_target(tmp_path,monkeypatch):
    file=tmp_path/'skin-focused.json'
    file.write_text(json.dumps(dict(models={'degrees':dict(accepted=True,targets=['redness'],acceptedTargets=['redness'])})))
    monkeypatch.setattr(M,'MANIFEST',file)
    def broken_load():raise RuntimeError('accepted session unavailable')
    monkeypatch.setattr(M,'load',broken_load)
    result=M.infer(np.zeros((20,20,3),np.uint8),[],True)
    assert result['degrees']=={} and result['unavailableTargets']==['redness']
    assert result['failure']=='ACCEPTED_MODEL_UNAVAILABLE'


def test_ort_exception_and_accepted_type_cannot_substitute_analytic_type(tmp_path,monkeypatch):
    # ORT pybind exceptions inherit Exception, not Python RuntimeError.
    from onnxruntime.capi.onnxruntime_pybind11_state import InvalidArgument
    file=tmp_path/'skin-focused.json'
    file.write_text(json.dumps(dict(models={'type':dict(accepted=True,version='accepted-test-v1',sha256='expected-hash')})))
    monkeypatch.setattr(M,'MANIFEST',file)
    def broken_load():raise InvalidArgument('bad accepted ONNX input')
    monkeypatch.setattr(M,'load',broken_load)
    result=M.infer(np.zeros((20,20,3),np.uint8),[],True)
    assert result['skinType']['value'] is None
    assert result['skinType']['limitationCode']=='ACCEPTED_MODEL_UNAVAILABLE'
    assert result['skinType']['modelHash'] is None
    assert result['skinType']['methodVersion']=='accepted-test-v1'
    assert M.infer_bags(np.zeros((20,20,3),np.uint8),[],True)['valid'] is False
