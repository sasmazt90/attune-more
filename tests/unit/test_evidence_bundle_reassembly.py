import hashlib,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/skin-research'))
from reassemble_evidence_bundle import reassemble


def fixture(tmp):
    original=b'unchanged compressed evidence bytes';parts=[]
    for n,p in enumerate([original[:15],original[15:]]):
        name=f'part-{n}';(tmp/name).write_bytes(p);parts.append(dict(path=name,bytes=len(p),sha256=hashlib.sha256(p).hexdigest()))
    d=dict(format='binary-concatenation-sha256-v1',bytes=len(original),sha256=hashlib.sha256(original).hexdigest(),parts=parts)
    index=tmp/'index.json';index.write_text(json.dumps(d));return index,d,original


def test_lossless_evidence_reassembly(tmp_path):
    i,d,raw=fixture(tmp_path);out=tmp_path/'out.gz';r=reassemble(i,out)
    assert out.read_bytes()==raw and r['parts']==2
    with pytest.raises(FileExistsError):reassemble(i,out)


@pytest.mark.parametrize('bad',['path','part-hash','part-size','bundle-hash','duplicate'])
def test_corrupt_or_unsafe_evidence_never_writes_output(tmp_path,bad):
    i,d,raw=fixture(tmp_path)
    if bad=='path':d['parts'][0]['path']='../escape'
    if bad=='part-hash':d['parts'][0]['sha256']='wrong'
    if bad=='part-size':d['parts'][0]['bytes']+=1
    if bad=='bundle-hash':d['sha256']='wrong'
    if bad=='duplicate':d['parts'].append(d['parts'][0])
    i.write_text(json.dumps(d));out=tmp_path/'output'
    with pytest.raises(ValueError):reassemble(i,out)
    assert not out.exists()
