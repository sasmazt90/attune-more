"""Synthetic file-integrity fixtures; no ML loading, downloads or acceptance claim."""
import hashlib,importlib.util,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('skin_bundle_preflight',ROOT/'tests/e2e/skin_bundle_preflight.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

@pytest.fixture
def bundle(tmp_path,monkeypatch):
 root=tmp_path/'repo';(root/'research/skin-findings/export').mkdir(parents=True)
 data=b'synthetic bytes only';entry=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 (root/'research/skin-findings/export/FINDINGS_V2_MANIFEST.json').write_text(json.dumps({'files':{'findings-v2/test.json':entry}}))
 (root/'research/skin-findings/MODEL_MANIFEST.json').write_text(json.dumps({'models':[dict(runtimeName='findings.pt',sizeBytes=len(data),sha256=entry['sha256'])]}))
 target=tmp_path/'bundle';target.mkdir()
 for name in ('findings-v2/test.json','findings.pt','params.json','k_classifier.json','dinov2-small/config.json','dinov2-small/model.safetensors'):
  p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 monkeypatch.setattr(M,'ROOT',root)
 return target

def test_valid_fixture_is_integrity_only_not_inference(bundle):
 report=M.verify(bundle)
 assert report['status']=='PASS' and report['verifiedManifestFiles']==2
 assert not report['modelsLoaded'] and not report['inferenceExecuted']

def test_reports_all_missing_files_before_model_start(bundle):
 (bundle/'findings.pt').unlink();(bundle/'findings-v2/test.json').unlink();(bundle/'k_classifier.json').unlink()
 r=M.verify(bundle);assert r['status']=='BLOCKED' and len(r['issues'])==3 and r['verifiedManifestFiles']==0

def test_size_and_hash_are_checked_independently(bundle):
 (bundle/'findings.pt').write_bytes(b'x');p=bundle/'findings-v2/test.json';p.write_bytes(b'x'*p.stat().st_size)
 r=M.verify(bundle);assert any('byte-size mismatch' in s for s in r['issues']) and any('SHA-256 mismatch' in s for s in r['issues'])

def test_external_symlink_is_never_loaded(bundle,tmp_path):
 p=bundle/'findings.pt';data=p.read_bytes();p.unlink();outside=tmp_path/'outside';outside.write_bytes(data);p.symlink_to(outside)
 assert any('unsafe path' in s for s in M.verify(bundle)['issues'])
