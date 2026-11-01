"""Version-bound import metadata; never caches frames, model outputs or weights.

Transformers builds its lazy model registry by reading every model source file.
Persist that deterministic registry once for this installed distribution. Keep
all backend requirements and exports identical, and fall back on any mismatch.
The hook is confined to the private native worker and does not modify packages.
"""
import hashlib,json
from importlib.metadata import distribution
from pathlib import Path

CACHE=Path(__file__).with_name('models')/'transformers-import-structure.json'
_installed=False

def identity():
    import transformers
    from transformers.utils import import_utils
    root=Path(transformers.__file__).parent
    dist=distribution('transformers')
    return {'version':dist.version,'registryInitSHA256':hashlib.sha256((root/'models/__init__.py').read_bytes()).hexdigest(),
            'importUtilitySHA256':hashlib.sha256(Path(import_utils.__file__).read_bytes()).hexdigest(),
            'distributionRecordSHA256':hashlib.sha256((dist.read_text('RECORD') or '').encode()).hexdigest()},root,import_utils

def encode(structure):
    return [{'backends':sorted(backends),'modules':{k:sorted(v) for k,v in sorted(modules.items())}}
            for backends,modules in sorted(structure.items(),key=lambda item:sorted(item[0]))]

def decode(rows,prefix=None):
    return {frozenset(row['backends']):{(f'{prefix}.{k}' if prefix is not None else k):set(v)
            for k,v in row['modules'].items()} for row in rows}

def install():
    global _installed
    if _installed:return True
    try:
        value=json.loads(CACHE.read_text('utf8'))
        current,root,utility=identity()
        if value.get('schema')!=1 or value['identity']!=current:return False
        rows=value['structure']
        if hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=value['structureSHA256']:return False
        target=(root/'models/__init__.py').resolve()
        original=utility.define_import_structure
        def cached(module_path,prefix=None):
            if Path(module_path).resolve()==target:return decode(rows,prefix)
            return original(module_path,prefix)
        # Preserve the original public cache-management surface.
        cached.cache_clear=original.cache_clear
        cached.cache_info=original.cache_info
        utility.define_import_structure=cached
        _installed=True
        return True
    except (OSError,ValueError,KeyError,TypeError):return False

def generate():
    current,root,utility=identity()
    structure=utility.define_import_structure(str(root/'models/__init__.py'))
    rows=encode(structure)
    assert decode(rows)==structure,'Import registry round-trip changed exports/backends'
    value={'schema':1,'identity':current,'structure':rows,'structureSHA256':hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    CACHE.write_text(json.dumps(value,separators=(',',':')),encoding='utf8')
    return {'cache':str(CACHE),'bytes':CACHE.stat().st_size,'backends':len(structure),'modules':sum(len(v) for v in structure.values()),'exactRegistryParity':True}

if __name__=='__main__':print(json.dumps(generate()))
