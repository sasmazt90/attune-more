"""No model downloads/inference: official asset provenance and benchmark math."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_score_math_and_reject_incomplete_semantic_snapshot(tmp_path):
    benchmark=load('mental_classifier_benchmark')
    result=benchmark.scores([{'B02'}],[{'B02','B03'}]);assert result['precision']==.5 and result['recall']==1
    (tmp_path/'verified-model.json').write_text(json.dumps({'repository':'intfloat/multilingual-e5-small','revision':'a'*40,'files':{}}))
    with pytest.raises(ValueError,match='COMPLETE_VERIFIED'):benchmark.SemanticObjectives(tmp_path,[])


def test_official_provisioning_uses_immutable_hashes_and_refuses_changed_file(tmp_path,monkeypatch):
    provision=load('provision_mental_semantic_models')
    payloads={name:('Synthetic fixture, not model data: '+name).encode() for name in provision.FILES}
    siblings=[]
    for name,data in payloads.items():
        row={'rfilename':name}
        if name=='model.safetensors':row['lfs']={'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}
        else:row['blobId']=hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
        siblings.append(row)
    metadata={'sha':'a'*40,'cardData':{'license':'apache-2.0'},'siblings':siblings};requests=[]
    class Response:
        status_code=200
        def __init__(self,data=None):self.data=data
        def json(self):return metadata
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def iter_content(self,size):yield self.data
    class Session:
        def get(self,url,**kwargs):
            requests.append(url);assert url.startswith('https://huggingface.co/')
            if '/api/models/' in url:return Response()
            assert '/resolve/'+'a'*40+'/' in url
            return Response(payloads[url.rsplit('/',1)[1]])
        def close(self):pass
    monkeypatch.setattr(provision.requests,'Session',Session)
    path=Path(provision.provision('minilm',tmp_path))
    record=json.loads((path/'verified-model.json').read_text())
    assert record['paidServices'] is False and record['revision']=='a'*40
    assert set(record['files'])==set(provision.FILES)
    weight=path/'model.safetensors';weight.write_bytes(b'invalid fixture bytes')
    with pytest.raises(ValueError,match='OFFICIAL_LFS_HASH_MISMATCH'):provision.provision('minilm',tmp_path)
    assert weight.read_bytes()==b'invalid fixture bytes'  # Never silently replaces mismatched assets.
