"""Finite replay of existing reviewed optical support; no fit or new pool."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import json,sys,hashlib
from pathlib import Path
from heavy_job_lease import HeavyJobLease
from pinned_dry_contract import contract
CONTRACT=contract()
ROOT=Path(__file__).resolve().parents[2];OUT=CONTRACT['out'];OLD=ROOT/'audit-results/native-material-contour-20261013';CASE=ROOT/'audit-results/native-camera-scope-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
def read(path):return json.loads(path.read_text('utf8'))
with HeavyJobLease('CDC-pinned-dry-head-reviewed-replay',peak_mib=250,minimum_available_mib=650) as lease:
    import numpy as np,cv2,material_component_features as M
    from component_flake_gate import masks
    from trial_region_flake_proposal import measure
    cv2.setNumThreads(1)
    controls=read(ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json')['controls'];review=read(OLD/'added-components-reviewed.json')['rows'];sources=read(OLD/'added-train-source-selection.json')
    prior=read(ROOT/'audit-results/native-dry-scale-20261013/native-gate-reviewed.json')['rows'];scale=read(ROOT/'audit-results/native-dry-scale-20261013/independent-v3-comparison.json')['rows'];optical=read(CASE/'single-crop-comparison.json')['rows'];baseline=read(OLD/'material-encoder-balanced-comparison.json');records=[];cases=[]
    def collect(meta,metric,density,labeled):
        lease.check();path=CASE/f'conditioned-case-{len(cases):02d}.npz'
        with np.load(path) as f:ids=f['ids'];component_ids=f['componentIds'];geometry=f['X'][:,-12:].copy()
        _,_,stats,_=cv2.connectedComponentsWithStats((ids>0).astype(np.uint8),8);indices=[]
        for j,cid in enumerate(component_ids):
            row=dict(componentId=int(cid),rect=stats[cid,:4].astype(int).tolist(),geometry=geometry[j].tolist());indices.append(len(records));records.append(dict(**meta,**row,cropBoxes=M.component_crop_boxes(row,metric,density),**labeled.get(int(cid),dict(label=None,**{'class':'UNKNOWN'}))))
        cases.append(dict(**meta,path=str(path),indices=indices))
    for si,source in enumerate(sources):
        picked=[r for r in review if r['sourceIndex']==si and r['label'] is not None]
        if picked:collect(dict(scope='added',sourceSHA256=source['sha256'],group=picked[0]['group'],split='train',factor=1.,sourceIndex=si),picked[0]['coordinateScale'],1.,{r['componentId']:{k:r[k] for k in ['label','class']} for r in picked})
    for c in controls:
        s=scale[c['controlIndex']]['referenceSpan']/640;labeled={r['nativeComponentId']:dict(label=r['label'],**{'class':'material' if r['label']==1 else 'reviewed-non-flake'}) for r in prior if r['controlIndex']==c['controlIndex']}
        for factor in [1.,.5]:collect(dict(scope='preserved',sourceSHA256=c['sourceSHA256'],group=c['group'],split=c['split'],factor=factor,controlIndex=c['controlIndex']),s*factor,factor,labeled if factor==1 else {})
    signature=hashlib.sha256(json.dumps([(r['sourceSHA256'],r['factor'],r['rect'],r['cropBoxes']) for r in records],sort_keys=True).encode()).hexdigest();assert baseline['cacheFile'].startswith(signature[:16])
    with np.load(OLD/baseline['cacheFile']) as f:features=f['features'].copy()
    assert features.shape==(len(records),2560);X=np.c_[features,np.array([r['geometry'] for r in records])]
    head_path=OUT/'delivery-snapshot/dryness/calibrated-source-group-head.json';raw=head_path.read_bytes();identity=hashlib.sha256(raw).hexdigest();assert identity==CONTRACT['hashes']['dryness/calibrated-source-group-head.json']
    head=json.loads(raw);p=M.predict(X,head);rows=[]
    for case in cases:
        if case['scope']!='preserved':continue
        lease.check();c=controls[case['controlIndex']];meta=next(r for r in optical if r['control']==case['controlIndex'] and r['factor']==case['factor']);a,b=meta['origin'];w,h=meta['cropShape'];known,objects=masks((h,w),{**c,'roi':[c['roi'][0]-a,c['roi'][1]-b,*c['roi'][2:]]})
        with np.load(case['path']) as f:ids=f['ids'];field=f['field'];component_ids=f['componentIds'];allowed=np.zeros(int(ids.max())+1,bool);allowed[component_ids]=p[case['indices']]>=head['threshold'];field=field*allowed[ids]
        def local(mask):return mask>0 if case['factor']==1 else cv2.resize(mask,(field.shape[1],field.shape[0]),interpolation=cv2.INTER_NEAREST)>0
        rows.append(dict(control=case['controlIndex'],source=c['sourceSHA256'],split=c['split'],factor=case['factor'],objects=[dict(index=o['index'],label=o['label'],measure=measure(field,local(o['mask']),case['factor'])) for o in objects],negative=measure(field,local(known['reviewed-non-flake']),case['factor'])))
    summary=[dict(factor=f,hits=sum(o['measure']['objectHit'] for r in rows if r['factor']==f for o in r['objects'] if o['label']=='visible-material'),reviewedNegativeSourcePixels=sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==f)) for f in [1.,.5]]
    c08=next(o for r in rows if r['control']==8 and r['factor']==1 for o in r['objects'] if o['index']==0)
    accepted=summary[0]['hits']==14 and summary[1]['hits']==13 and all(r['reviewedNegativeSourcePixels']==0 for r in summary) and c08['measure']['objectHit']
    result=dict(headSHA256=identity,summary=summary,c08Object0=c08,rows=rows,cachedFeatureRowIdentitySHA256=signature,cachedFeaturesOfflineOnly=True,noFit=True,unknownOutsideMasks=False,independentFinalTest=False,acceptancePassed=bool(accepted),resource=lease.receipt())
    (OUT/'reviewed-head-replay.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(dict(summary=summary,c08Object0=c08,accepted=bool(accepted))),flush=True)
    assert accepted,'Pinned optical replay did not pass; normal selector must stay old'
