"""Focused integration boundaries; uses the actual recorded browser geometry."""
import os,sys,json,copy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import experimental_acne_v5 as preview
from appearance_analysis import decode_photo

def request_data():return json.loads((ROOT/'output/playwright/front-browser-api.json').read_text('utf8'))['payload']

def test_default_off_and_normal_manifest(monkeypatch):
 monkeypatch.delenv('ATTUNE_EXPERIMENTAL_ACNE_V5',raising=False)
 assert preview.configuration()['enabled'] is False
 with pytest.raises(preview.PreviewUnavailable,match='DISABLED'):preview.load()
 acne=json.loads((ROOT/'services/core-api/models/skin-focused.json').read_text())['models']['acne']
 assert acne['accepted'] is False and acne['file'] is None

def test_missing_model_is_explicit(monkeypatch,tmp_path):
 monkeypatch.setenv('ATTUNE_EXPERIMENTAL_ACNE_V5','1');monkeypatch.setenv('ATTUNE_ACNE_V5_MODEL_DIR',str(tmp_path))
 assert preview.configuration()['status']=='model-unavailable'
 with pytest.raises(preview.PreviewUnavailable,match='MODEL_UNAVAILABLE'):preview.load()

def test_real_front_pose_and_quality_contract():
 p=request_data();image,_=decode_photo(p['photo']);assert preview.gate(p,image)['pose']=='FRONT'
 p['capturePreflight']['quality']['blurScore']=3.99
 with pytest.raises(preview.PreviewRejected,match='QUALITY_FAILED'):preview.gate(p,image)
 p=request_data();p['pose']='LEFT'
 with pytest.raises(preview.PreviewRejected,match='POSE_FAILED'):preview.gate(p,image)
 p=request_data();del p['meshes']['chin']
 with pytest.raises(preview.PreviewRejected,match='VISIBLE_REGION_MISMATCH'):preview.gate(p,image)

def test_normal_api_missing_and_disabled(monkeypatch,tmp_path):
 from fastapi.testclient import TestClient
 import main
 monkeypatch.setenv('ATTUNE_EXPERIMENTAL_ACNE_V5','1');monkeypatch.setenv('ATTUNE_ACNE_V5_MODEL_DIR',str(tmp_path))
 with TestClient(main.app) as client:
  p=request_data();response=client.post('/api/local-health/skin',json=p)
  assert response.status_code==503 and response.json()=={'detail':'EXPERIMENTAL_ACNE_V5_MODEL_UNAVAILABLE'}
  monkeypatch.delenv('ATTUNE_EXPERIMENTAL_ACNE_V5')
  response=client.post('/api/local-health/skin',json=p)
  assert response.status_code==503 and response.json()=={'detail':'EXPERIMENTAL_ACNE_V5_DISABLED'}
  p['processingConsent']=False;response=client.post('/api/local-health/skin',json=p)
  assert response.status_code==422 and 'candidateCount' not in response.json()

def test_stopped_request_never_starts_detector(monkeypatch):
 from native_material_budget import NativeRequestStopped
 monkeypatch.setenv('ATTUNE_EXPERIMENTAL_ACNE_V5','1')
 def stopped():raise NativeRequestStopped('CANCELLED')
 with pytest.raises(NativeRequestStopped):preview.analyze(request_data(),stopped)
