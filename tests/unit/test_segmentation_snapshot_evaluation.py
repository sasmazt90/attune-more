import copy,gzip,hashlib,io,json,sys,zipfile
from pathlib import Path
from PIL import Image
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/skin-research'))
import evaluate_segmentation_snapshot as E


def fixture(tmp_path):
    buf=io.BytesIO();Image.new('RGB',(16,16),'white').save(buf,format='PNG');payload=buf.getvalue()
    poly=[2,2,14,2,2,14];data=dict(info={},images=[dict(id=1,width=16,height=16,file_name='source.png')],categories=[dict(id=i+1,name=k) for i,k in enumerate(E.CLASSES)],annotations=[dict(id=1,image_id=1,category_id=1,bbox=[2,2,12,12],area=144,iscrowd=0,segmentation=[poly])])
    archive=tmp_path/'data.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for split in ['valid','test']:
            z.writestr(split+'/_annotations.coco.json',json.dumps(data));z.writestr(split+'/source.png',payload)
    sha=hashlib.sha256(archive.read_bytes()).hexdigest();rows=[]
    for split in ['valid','test']:
        row=dict(status='ok',split=split,source=dict(cocoImageId=1,filename='source.png',archiveSHA256=sha,imageSHA256=hashlib.sha256(payload).hexdigest()),image=dict(width=16,height=16),requestedModel='pinned-model',resolvedModel=dict(model_id='pinned-model',model_package_id='package'),confidenceFloor=.05,inferenceId='inference-'+split,predictions=[dict(confidence=.9,**{'class':'Oily'},points=[dict(x=poly[n],y=poly[n+1]) for n in range(0,len(poly),2)])])
        rows.append(dict(split=split,rawJSON=json.dumps(row)))
    snapshots=tmp_path/'predictions.gz';save(snapshots,rows)
    return archive,snapshots,rows


def save(path,rows):path.write_bytes(gzip.compress(json.dumps({'records':rows}).encode(),mtime=0))


def change(rows,key,value):
    r=json.loads(rows[0]['rawJSON']);r[key]=value;rows[0]['rawJSON']=json.dumps(r)


def test_exact_mask_ap_and_atomic_validation_lock(tmp_path):
    a,p,rows=fixture(tmp_path);v=E.evaluate(a,p,'valid');t=E.evaluate(a,p,'test',v)
    assert v['coco'][0]['map50']==pytest.approx(1)
    assert t['operatingPoints']['Oily']['tp']==1 and t['lockedThresholds']==v['lockedThresholds']
    assert not t['normalRegionsInferred'] and not t['modelAccepted']


def test_equal_enclosing_boxes_do_not_count_as_equal_masks(tmp_path):
    a,p,rows=fixture(tmp_path);r=json.loads(rows[0]['rawJSON']);r['predictions'][0]['points']=[{'x':14,'y':14},{'x':14,'y':2},{'x':2,'y':14}];rows[0]['rawJSON']=json.dumps(r);save(p,rows)
    v=E.evaluate(a,p,'valid')
    assert v['operatingPoints']['Oily']['tp']==0 and v['coco'][0]['map50']==0


def test_box_only_predictions_cannot_become_masks(tmp_path):
    a,p,rows=fixture(tmp_path);r=json.loads(rows[0]['rawJSON']);r['predictions'][0].pop('points');r['predictions'][0].update(x=8,y=8,width=12,height=12);rows[0]['rawJSON']=json.dumps(r);save(p,rows)
    with pytest.raises(ValueError,match='POLYGON_REQUIRED'):E.evaluate(a,p,'valid')


def test_empty_predictions_have_zero_mask_ap(tmp_path):
    a,p,rows=fixture(tmp_path);change(rows,'predictions',[]);save(p,rows)
    v=E.evaluate(a,p,'valid');assert v['coco'][0]['map50']==0 and v['operatingPoints']['Oily']['fn']==1


def test_test_must_not_fit_its_own_threshold(tmp_path):
    a,p,_=fixture(tmp_path)
    with pytest.raises(ValueError,match='VALIDATION_MASK_LOCK'):E.evaluate(a,p,'test')
    v=E.evaluate(a,p,'valid');v['modelIdentity']['modelPackageId']='different'
    with pytest.raises(ValueError,match='VALIDATION_MASK_LOCK'):E.evaluate(a,p,'test',v)


@pytest.mark.parametrize('bad',['source','filename','dimensions','resolved-model','floor','split','points','duplicate'])
def test_provenance_geometry_or_incomplete_receipts_are_rejected(tmp_path,bad):
    a,p,rows=fixture(tmp_path);r=json.loads(rows[0]['rawJSON'])
    if bad=='source':r['source']['imageSHA256']='wrong'
    if bad=='filename':r['source']['filename']='another.png'
    if bad=='dimensions':r['image']['width']=32
    if bad=='resolved-model':r['resolvedModel']['model_id']='another-model'
    if bad=='floor':r['confidenceFloor']=.4
    if bad=='split':r['split']='test'
    if bad=='points':r['predictions'][0]['points'][0]['x']=float('nan')
    rows[0]['rawJSON']=json.dumps(r)
    if bad=='duplicate':rows.append(copy.deepcopy(rows[0]))
    save(p,rows)
    with pytest.raises(ValueError):E.evaluate(a,p,'valid')


def test_one_prediction_cannot_match_two_source_instances(tmp_path):
    a,p,_=fixture(tmp_path);_,truth,predictions,_,_,_=E.read_snapshot(a,p,'valid');truth[1].append(copy.deepcopy(truth[1][0]))
    events,total=E.matching_events(truth,predictions,'Oily')
    assert total==2 and events==[(.9,True)]


def test_independent_redness_and_oil_masks_may_overlap(tmp_path):
    a,p,_=fixture(tmp_path);_,truth,predictions,_,_,_=E.read_snapshot(a,p,'valid')
    truth[1].append(dict(truth[1][0],label='Redness'));predictions[1].append(dict(predictions[1][0],label='Redness'))
    assert E.matching_events(truth,predictions,'Oily')[0]==[(.9,True)]
    assert E.matching_events(truth,predictions,'Redness')[0]==[(.9,True)]


def test_explicit_empty_contour_counts_as_false_positive_not_box_mask(tmp_path):
    a,p,rows=fixture(tmp_path);r=json.loads(rows[0]['rawJSON']);r['predictions'][0]['points']=[];rows[0]['rawJSON']=json.dumps(r);save(p,rows)
    v=E.evaluate(a,p,'valid')
    assert v['emptyPredictedMasks']==1 and v['operatingPoints']['Oily']['tp']==0
    # F1-optimal tie can exclude the low-quality detection; at a fixed .5
    # threshold its empty geometry must still count as an unmatched prediction.
    _,truth,ps,_,_,_=E.read_snapshot(a,p,'valid')
    events,total=E.matching_events(truth,ps,'Oily');assert events==[(.9,False)]


def test_self_touching_model_contours_are_rasterized_without_truth_repair():
    mask=E.polygon_rle([[1,1,7,1,7,7,4,4,1,7,4,4]],16,16,prediction=True)
    assert E.M.area(mask)>0
    with pytest.raises(ValueError,match='MASK_POLYGON'):
        E.polygon_rle([[1,1,7,1,7,7,4,4,1,7,4,4]],16,16)


def test_class_union_ignores_instance_subdivision_without_making_normal_truth(tmp_path):
    a,p,_=fixture(tmp_path);data,truth,ps,_,_,_=E.read_snapshot(a,p,'valid')
    # Duplicate publisher instances do not double-count the union's pixels.
    truth[1].append(copy.deepcopy(truth[1][0]))
    r=E.union_diagnostics(data,truth,ps,{k:.35 for k in E.CLASSES})
    assert r['perClass']['Oily']['microIoU']==1 and r['perClass']['Oily']['annotationCoverageFraction']==1
    assert r['perClass']['Redness']['microIoU'] is None
    assert r['perClass']['Redness']['imagesWithoutSourceAnnotations']==1 and not r['normalRegionsInferred']
