"""Training quality filtering must preserve holdouts and source-group coverage."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('quality_filter',ROOT/'scripts/skin-research/prepare_quality_filtered_coco.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def fixture(tmp_path):
    source=tmp_path/'source.zip';manifest=tmp_path/'source.json';audit=tmp_path/'audit.json'
    rows=[];measurements=[]
    with zipfile.ZipFile(source,'w') as z:
        for split,ids in [('train',[1,2]),('valid',[3]),('test',[4])]:
            images=[];annotations=[]
            for i in ids:
                key=f'{i:064x}';images.append(dict(id=i,file_name=key+'.jpg',width=20,height=20))
                annotations.append(dict(id=i,image_id=i,category_id=1,bbox=[1,1,5,5]))
                z.writestr(split+'/'+key+'.jpg',bytes([i])*20)
                rows.append(dict(rawSHA256=key,sourceGroup=1 if split=='train' else i,split=split))
                measurements.append(dict(filename=key+'.jpg',split=split,impulse=.04 if i in [2,3,4] else 0))
            z.writestr(split+'/_annotations.coco.json',json.dumps(dict(images=images,annotations=annotations,categories=[dict(id=1,name='acne')]),indent=3))
    manifest.write_text(json.dumps(dict(outputArchiveSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),images=rows)))
    audit.write_text(json.dumps(dict(metric='test pixel screen',rows=measurements)))
    return source,manifest,audit


def test_filter_only_changes_train_and_retains_every_source_group(tmp_path):
    source,manifest,audit=fixture(tmp_path);output=tmp_path/'filtered.zip'
    result=module.prepare(source,manifest,audit,output)
    assert result['splits']['train']['images']==1
    assert result['splits']['train']['sourceGroups']==1
    with zipfile.ZipFile(source) as before,zipfile.ZipFile(output) as after:
        for member in before.namelist():
            if member.startswith(('valid/','test/')):assert before.read(member)==after.read(member)


def test_filter_rejects_removing_an_entire_source_group(tmp_path):
    source,manifest,audit=fixture(tmp_path);data=json.loads(audit.read_text())
    for row in data['rows']:row['impulse']=.04
    audit.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='entire source group'):
        module.prepare(source,manifest,audit,tmp_path/'bad.zip')


def test_filter_rejects_incomplete_quality_audit(tmp_path):
    source,manifest,audit=fixture(tmp_path);data=json.loads(audit.read_text());data['rows']=data['rows'][1:]
    audit.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='exactly the frozen training'):
        module.prepare(source,manifest,audit,tmp_path/'bad.zip')
