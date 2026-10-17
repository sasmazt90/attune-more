"""Focused launcher ownership/disabled-provider regressions; no external requests."""
import hashlib,json,runpy,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]

def test_hosted_disabled_even_with_photo_consent_and_key(monkeypatch):
 sys.path.insert(0,str(ROOT/'services/core-api'))
 import hosted_skin_type as H
 monkeypatch.setenv('ATTUNE_ROBOFLOW_API_KEY','test-only-not-a-key')
 monkeypatch.setattr(H,'get_inference_client',lambda *a,**kw:pytest.fail('Disabled provider attempted a request'))
 result=H.infer_hosted_type(None,True)
 assert result['limitationCode']=='HOSTED_CONFIG_DISABLED'
 assert result['value'] is None and result['quality']=='insufficient' and result['confidence'] is None
 assert H.infer_hosted_type(None,False)['limitationCode']=='HOSTED_INFERENCE_PERMISSION_DENIED'

def test_second_click_rejects_changed_owner_before_http(monkeypatch):
 module=runpy.run_path(str(ROOT/'scripts/windows-launcher/start_togg.pyw'))
 verify=module['verified_owner'];g=verify.__globals__
 delivery=dict(BUILD_ID='known',sourceCommit='source')
 state=dict(workspace=str(g['ROOT']),BUILD_ID='known',sourceCommit='source',profile=str(g['PROFILE']),url=g['URL'],processes=[dict(pid=123,role='frontend',started=1,cwd='expected',commandSHA256='expected')])
 monkeypatch.setitem(g,'identity',lambda pid,role:dict(pid=pid,role=role,started=2,cwd='foreign',commandSHA256='different'))
 monkeypatch.setitem(g,'fetch',lambda url:pytest.fail('Changed process owner reached HTTP reuse'))
 assert verify(state,delivery) is False

def test_source_hash_tamper_fails_closed(tmp_path,monkeypatch):
 module=runpy.run_path(str(ROOT/'scripts/windows-launcher/start_togg.pyw'))
 verify=module['verify_delivery'];g=verify.__globals__
 (tmp_path/'apps/vehicle-app/.next').mkdir(parents=True)
 (tmp_path/'apps/vehicle-app/.next/BUILD_ID').write_text('known')
 (tmp_path/'file.txt').write_text('tampered')
 descriptor=tmp_path/'deployment.json'
 descriptor.write_text(json.dumps(dict(frontendOrigin=g['URL'],apiPort=8311,BUILD_ID='known',files=[dict(path='file.txt',sha256=hashlib.sha256(b'original').hexdigest())])))
 monkeypatch.setitem(g,'ROOT',tmp_path);monkeypatch.setitem(g,'DELIVERY',descriptor)
 with pytest.raises(RuntimeError,match='identity mismatch'):verify()
