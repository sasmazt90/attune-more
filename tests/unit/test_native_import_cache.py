"""A stale cache must never change Transformers' lazy dependency/export registry."""
import hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
import native_import_cache as cache

@pytest.fixture
def registry(tmp_path,monkeypatch):
    structure={frozenset({'torch'}):{'dinov2.modeling_dinov2':{'Dinov2Model'}},frozenset():{'auto.configuration_auto':{'AutoConfig'}}}
    calls=[]
    def original(path,prefix=None):calls.append((path,prefix));return 'original'
    original.cache_clear=lambda:None
    original.cache_info=lambda:None
    utility=SimpleNamespace(define_import_structure=original)
    identity={'version':'test','digest':'unchanged'}
    rows=cache.encode(structure)
    value={'schema':1,'identity':identity,'structure':rows,'structureSHA256':hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    target=tmp_path/'cache.json';target.write_text(json.dumps(value))
    monkeypatch.setattr(cache,'CACHE',target)
    monkeypatch.setattr(cache,'_installed',False)
    monkeypatch.setattr(cache,'identity',lambda:(identity,tmp_path,utility))
    return structure,calls,utility,value,target,tmp_path,original

def test_backend_guards_exports_prefix_and_other_registries_are_preserved(registry):
    structure,calls,utility,value,target,root,original=registry
    assert cache.install()
    assert utility.define_import_structure(root/'models/__init__.py')==structure
    prefixed=utility.define_import_structure(root/'models/__init__.py','models')
    assert prefixed=={k:{'models.'+name:exports for name,exports in modules.items()} for k,modules in structure.items()}
    assert not calls
    assert utility.define_import_structure(root/'other.py','x')=='original'
    assert calls==[(root/'other.py','x')]

@pytest.mark.parametrize('change',['identity','checksum','missing','invalid'])
def test_stale_or_damaged_registry_falls_back_without_hooking(registry,change):
    structure,calls,utility,value,target,root,original=registry
    if change=='identity':value['identity']={'version':'different'}
    if change=='checksum':value['structureSHA256']='wrong'
    target.write_text(json.dumps(value))
    if change=='missing':target.unlink()
    if change=='invalid':target.write_text('{')
    assert not cache.install()
    assert utility.define_import_structure is original
