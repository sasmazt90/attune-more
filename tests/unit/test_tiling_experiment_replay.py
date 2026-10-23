import copy,gzip,importlib.util,json,sys
from pathlib import Path
import pytest
SCRIPTS=Path(__file__).resolve().parents[2]/'scripts/skin-research'
sys.path.insert(0,str(SCRIPTS))
import evaluate_tiling_experiment as E


def setup(tmp_path,monkeypatch):
    ids=[26,144,19,34,7,23]
    identity={'modelId':'model','modelPackageId':'package'}
    data={'images':[dict(id=i,width=10,height=10) for i in ids],'annotations':[],'categories':[]}
    monkeypatch.setattr(E,'read_snapshot',lambda *a:(data,{i:[] for i in ids},{i:[] for i in ids},[],identity,'hash'))
    monkeypatch.setattr(E,'coco_metrics',lambda *a:{'fixture':True})
    baseline=tmp_path/'baseline.gz'
    baseline.write_bytes(gzip.compress(json.dumps({'records':[{'split':'valid','rawJSON':json.dumps({'source':{'cocoImageId':i,'filename':str(i)}})} for i in ids]}).encode()))
    rows=[]
    for i in ids:
        for t in E.corner_tiles(10,10):
            rows.append(dict(imageId=i,tile=t,model='model',package='package',sha256='crop-hash',sourceSHA256='source-hash',response={'result':{'resolved_model':{'model_id':'model','model_package_id':'package'},'image':{'width':6,'height':6},'predictions':[],'inference_id':f'{i}-{t}'}}))
    tiles=tmp_path/'tiles.gz'
    lock=dict(modelIdentity=identity,thresholdSelectionSplit='valid',lockedThresholds={k:.3 for k in E.CLASSES})
    return baseline,tiles,rows,lock


def run(baseline,tiles,rows,lock):
    tiles.write_bytes(gzip.compress(json.dumps({'records':rows}).encode()))
    return E.evaluate('unused.zip',baseline,tiles,lock)


def test_pinned_replay_keeps_controls_separate_without_test_or_threshold_fit(tmp_path,monkeypatch):
    b,t,r,lock=setup(tmp_path,monkeypatch);result=run(b,t,r,lock)
    assert result['images']==6 and result['inferences']==24
    assert len(result['groups']['hashControls']['imageIds'])==3
    assert not result['testSplitTouched'] and not result['thresholdsRefitted'] and not result['modelAccepted']


@pytest.mark.parametrize('corruption',['identity','dimensions','duplicate','selection','thresholds'])
def test_replay_rejects_drift_or_incomplete_evidence(tmp_path,monkeypatch,corruption):
    b,t,r,lock=setup(tmp_path,monkeypatch)
    if corruption=='identity':r[0]['response']['result']['resolved_model']['model_package_id']='different'
    if corruption=='dimensions':r[0]['response']['result']['image']['width']=9
    if corruption=='duplicate':r[-1]=copy.deepcopy(r[-2])
    if corruption=='selection':r=[x for x in r if x['imageId']!=26]
    if corruption=='thresholds':lock['thresholdSelectionSplit']='test'
    with pytest.raises(ValueError):run(b,t,r,lock)
