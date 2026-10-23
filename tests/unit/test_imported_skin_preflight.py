"""The preflight must reject altered labels, splits, geometry and source pixels."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile
import pytest
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('verify_imported_boxes',ROOT/'scripts/skin-research/verify_imported_boxes.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


@pytest.mark.parametrize('change,problem',[(None,None),('split','SOURCE_SPLIT_CHANGED'),('label','CLASS_ANNOTATION_COUNTS_CHANGED'),('geometry','BOX_GEOMETRY_CHANGED_OVER_ONE_PIXEL'),('pixels','SOURCE_PIXELS_DIFFER'),('empty','UNANNOTATED_IMAGE')])
def test_actual_export_is_checked_against_prepared_source(tmp_path,change,problem):
    image=Image.new('RGB',(20,20),(100,130,150));buf=io.BytesIO();image.save(buf,format='PNG');raw=buf.getvalue()
    identity=hashlib.sha256(b'20x20:'+image.tobytes()).hexdigest()
    def write(path,split,filename,data,box,label,empty=False):
        coco=dict(images=[dict(id=1,file_name=filename,width=20,height=20)],categories=[dict(id=1,name=label)],annotations=[] if empty else [dict(id=1,image_id=1,category_id=1,bbox=box)])
        with zipfile.ZipFile(path,'w') as z:
            z.writestr(split+'/'+filename,data);z.writestr(split+'/_annotations.coco.json',json.dumps(coco))
    prepared=tmp_path/'prepared.zip';exported=tmp_path/'exported.zip';manifest=tmp_path/'manifest.json'
    write(prepared,'train',identity+'.jpg',raw,[2,2,8,8],'Akne')
    manifest.write_text(json.dumps(dict(summary=dict(archiveSHA256=hashlib.sha256(prepared.read_bytes()).hexdigest()),images=[dict(decodedSHA256=identity,split='train',group=identity)])))
    if change=='pixels':
        b=io.BytesIO();Image.new('RGB',(20,20),'white').save(b,format='PNG');raw=b.getvalue()
    write(exported,'test' if change=='split' else 'train',identity+'_jpg.rf.export.jpg',raw,[4,2,8,8] if change=='geometry' else [2.5,2,8,8],'Kuru Cilt' if change=='label' else 'Akne',change=='empty')
    result=module.verify(prepared,manifest,exported)
    assert result['passed']==(problem is None)
    if problem:assert problem in result['issues']
    else:assert result['splits']['train']['unannotated']==0
