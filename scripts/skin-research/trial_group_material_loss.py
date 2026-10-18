"""One source-group loss change on existing native TRAIN; no encoder run.

Existing feature cache is explicitly OFFLINE research only, never camera speed
evidence. Reconstructed cache identity and old optical results must agree first.
"""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import json,sys,hashlib
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-closeout-20261013';OUT.mkdir(exist_ok=True);OLD=ROOT/'audit-results/native-material-contour-20261013';CASE=ROOT/'audit-results/native-camera-scope-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
def read(p):return json.loads(p.read_text('utf8'))
protocol=OUT/'group-loss-protocol.json'
if not protocol.exists():protocol.write_text(json.dumps(dict(variable='equal total loss per TRAIN source-group within each binary class; 63 rows, 15 groups, scaler/encoder/crop/proposal and C1 threshold0.5 unchanged',originalHeadSHA256=hashlib.sha256((OLD/'encoder-material-balanced-head.json').read_bytes()).hexdigest(),oneFit=True,validationInFit=False,unknownNegative=False,acceptance=dict(nativeHitsAtLeast=12,seenValidationHitsAtLeast=7,negativeNativePixelsAtMost=30,preservedOldHitsAtLeast=6,eyewearPixelsRequired=0,bothCorrectedMaterialLocationsRequired=True,fullCameraBudgetSeconds=45),normalProductEnabled=False),indent=2),'utf8')
assert not (OUT/'source-group-head.json').exists(),'Completed group fit must not be repeated'
with HeavyJobLease('CDC-one-source-group-loss-fit',peak_mib=230,minimum_available_mib=630) as lease:
    import numpy as np,cv2
    import material_component_features as M
    from component_flake_gate import masks
    from trial_region_flake_proposal import measure
    cv2.setNumThreads(1);controls=read(ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json')['controls'];review=read(OLD/'added-components-reviewed.json')['rows'];sources=read(OLD/'added-train-source-selection.json');prior=read(ROOT/'audit-results/native-dry-scale-20261013/native-gate-reviewed.json')['rows'];scale=read(ROOT/'audit-results/native-dry-scale-20261013/independent-v3-comparison.json')['rows'];optical=read(CASE/'single-crop-comparison.json')['rows'];baseline=read(OLD/'material-encoder-balanced-comparison.json');records=[];cases=[];case_index=0
    def collect(meta,metric,density,labeled):
        global case_index
        lease.check();path=CASE/f'conditioned-case-{case_index:02d}.npz'
        with np.load(path) as f:ids=f['ids'];component_ids=f['componentIds'];geometry=f['X'][:,-12:].copy()
        _,_,stats,_=cv2.connectedComponentsWithStats((ids>0).astype(np.uint8),8);indices=[]
        for j,cid in enumerate(component_ids):
            row=dict(componentId=int(cid),rect=stats[cid,:4].astype(int).tolist(),geometry=geometry[j].tolist());indices.append(len(records));records.append(dict(**meta,**row,cropBoxes=M.component_crop_boxes(row,metric,density),**labeled.get(int(cid),dict(label=None,**{'class':'UNKNOWN'}))))
        cases.append(dict(**meta,path=str(path),indices=indices));case_index+=1
    for si,source in enumerate(sources):
        picked=[r for r in review if r['sourceIndex']==si and r['label'] is not None]
        if picked:collect(dict(scope='added',sourceSHA256=source['sha256'],group=picked[0]['group'],split='train',factor=1.,sourceIndex=si),picked[0]['coordinateScale'],1.,{r['componentId']:{k:r[k] for k in ['label','class']} for r in picked})
    for c in controls:
        s=scale[c['controlIndex']]['referenceSpan']/640
        labeled={r['nativeComponentId']:dict(label=r['label'],**{'class':'material' if r['label']==1 else 'reviewed-non-flake'}) for r in prior if r['controlIndex']==c['controlIndex']}
        for factor in [1.,.5]:collect(dict(scope='preserved',sourceSHA256=c['sourceSHA256'],group=c['group'],split=c['split'],factor=factor,controlIndex=c['controlIndex'],kind=c['kind']),s*factor,factor,labeled if factor==1 else {})
    signature=hashlib.sha256(json.dumps([(r['sourceSHA256'],r['factor'],r['rect'],r['cropBoxes']) for r in records],sort_keys=True).encode()).hexdigest();assert baseline['cacheFile'].startswith(signature[:16]),'Cached encoder row/window identity mismatch'
    with np.load(OLD/baseline['cacheFile']) as f:features=f['features'].copy()
    assert features.shape==(len(records),2560);X=np.c_[features,np.array([r['geometry'] for r in records])];train=[i for i,r in enumerate(records) if r['split']=='train' and r['factor']==1 and r['label'] is not None];assert len(train)==63 and len({records[i]['group'] for i in train})==15
    assert not {records[i]['group'] for i in train}&{r['group'] for r in records if r['split']=='validation'}
    old_head=read(OLD/'encoder-material-balanced-head.json');old_p=M.predict(X,old_head)
    def evaluate(p):
        rows=[]
        for case in cases:
            if case['scope']!='preserved':continue
            lease.check();c=controls[case['controlIndex']];meta=next(r for r in optical if r['control']==case['controlIndex'] and r['factor']==case['factor']);a,b=meta['origin'];w,h=meta['cropShape'];local_control={**c,'roi':[c['roi'][0]-a,c['roi'][1]-b,*c['roi'][2:]]};known,objects=masks((h,w),local_control)
            with np.load(case['path']) as f:ids=f['ids'];field=f['field'];component_ids=f['componentIds'];allowed=np.zeros(int(ids.max())+1,bool);allowed[component_ids]=p[case['indices']]>=.5;field=field*allowed[ids]
            def local(mask):return mask>0 if case['factor']==1 else cv2.resize(mask,(field.shape[1],field.shape[0]),interpolation=cv2.INTER_NEAREST)>0
            rows.append(dict(control=case['controlIndex'],source=c['sourceSHA256'],split=case['split'],factor=case['factor'],kind=case['kind'],objects=[dict(index=o['index'],label=o['label'],measure=measure(field,local(o['mask']),case['factor'])) for o in objects],negative=measure(field,local(known['reviewed-non-flake']),case['factor'])))
        return rows
    before=evaluate(old_p)
    for r in before:
        expected=next(v for v in baseline['rows'] if v['controlIndex']==r['control'] and v['factor']==r['factor']);assert r['negative']==expected['negative']['encoder']
        for o in r['objects']:assert o['measure']==next(v for v in expected['objects'] if v['index']==o['index'])['fields']['encoder']
    lease.check();head=M.fit_classifier(X[train],[records[i]['label'] for i in train],[records[i]['group'] for i in train],feature_group_sizes=[1280,1280,12],group_balanced_loss=True)
    assert np.allclose(head['mean'],old_head['mean'],atol=1e-9) and np.allclose(head['std'],old_head['std'],atol=1e-9)
    head.update(lossVersion='source-group-balanced-v1',featureGroupSizes=[1280,1280,12],encoderSHA256=M.ENCODER_SHA,accepted=False,normalProductEnabled=False,fitCount=1);(OUT/'source-group-head.json').write_text(json.dumps(head),'utf8');after=evaluate(M.predict(X,head));summary=[]
    for factor in [1.,.5]:
        for split in ['train','validation']:
            summary.append(dict(factor=factor,split=split,**{name:dict(hits=sum(o['measure']['objectHit'] for r in rows if r['factor']==factor and r['split']==split for o in r['objects'] if o['label']=='visible-material'),negativeSourcePixels=sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==factor and r['split']==split)) for name,rows in [('before',before),('after',after)]}))
    receipt=dict(summary=summary,before=before,after=after,trainRows=63,trainGroups=15,fitCount=1,cacheRowIdentitySHA256=signature,oldAll32MetricsReconstructedExactly=True,cachedFeatureScope='OFFLINE_RESEARCH_ONLY; never camera runtime',validationIndependentFinal=False,normalProductEnabled=False,resource=lease.receipt());(OUT/'group-loss-comparison.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(dict(summary=summary,resource=receipt['resource'])),flush=True)
