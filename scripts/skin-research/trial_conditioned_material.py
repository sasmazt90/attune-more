"""One frozen-encoder single-crop representation trial, streamed sources."""
import os
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[key]='1'
import json,sys,hashlib,time
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-camera-scope-20261013';PREV=ROOT/'audit-results/native-material-contour-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
protocol=OUT/'single-crop-protocol.json'
if not protocol.exists():
    protocol.write_text(json.dumps(dict(changedVariable='one proposal-conditioned source-scaled context crop on non-self ring median instead of two unconditioned crops; frozen encoder/12 geometry features unchanged',trainRows=63,trainGroups=15,fitCount=1,regularizationC=1,threshold=.5,featureBlockSizes=[1280,12],validationInFit=False,unknownAsNegative=False,acceptance=dict(nativeHitsAtLeast=12,seenValidationHitsAtLeast=7,naturalNativeHitsAtLeast=7,naturalHalfHitsAtLeast=4,allPreservedSixHitsRequired=True,eyewearFalsePixelsRequired=0,bothCorrectedCheekLocationsRequired=True,negativeSupportNoWorseThanCurrent30=True,normalCameraBudgetSeconds=45),normalProductEnabled=False,featureCacheIsNotRuntimeProof=True),indent=2),'utf8')
evaluate_only='--evaluate-only' in sys.argv
assert not (OUT/'single-crop-head.json').exists() or evaluate_only,'Do not repeat completed fit'
with HeavyJobLease('CD-single-conditioned-crop-trial',peak_mib=700,minimum_available_mib=1400) as lease:
    import cv2,numpy as np
    import material_component_features as M,native_flake_support as F
    from component_flake_gate import masks
    from trial_region_flake_proposal import measure
    cv2.setNumThreads(1);encoder=M.OnnxMaterialEncoder(ROOT/'audit-results/material-runtime-followup-20261013/material-encoder.onnx',ROOT/'audit-results/material-runtime-followup-20261013/encoder-parity.json')
    review=json.loads((PREV/'added-components-reviewed.json').read_text('utf8'))['rows'];sources=json.loads((PREV/'added-train-source-selection.json').read_text('utf8'));controls=json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json').read_text('utf8'))['controls'];old_labels=json.loads((ROOT/'audit-results/native-dry-scale-20261013/native-gate-reviewed.json').read_text('utf8'))['rows'];old_shape=json.loads((ROOT/'audit-results/native-dry-scale-20261013/independent-v3-comparison.json').read_text('utf8'))['rows'];records=[];case_files=[]
    def extract_case(im,metric,density,meta,labeled,observation=None):
        lease.check();field=F.proposal_tile(im,metric,pixel_density=density,check=lease.check);ids,rows=M.describe(im,field,metric);selected=[r for r in rows if (r['componentId'] in labeled if meta['scope']=='added-reviewed-train' else ((ids==r['componentId'])&observation).any())]
        features=[]
        for offset in range(0,len(selected),16):
            lease.check();current=selected[offset:offset+16];crops=[M.support_conditioned_crop(im,ids,r,metric,density)[0] for r in current];features.append(encoder.extract(crops,16));del crops
        visual=np.concatenate(features) if features else np.empty((0,1280),np.float32);X=np.c_[visual,np.array([r['geometry'] for r in selected]).reshape(len(selected),12)]
        target=OUT/f'conditioned-case-{len(case_files):02d}.npz';np.savez_compressed(target,field=field,ids=ids,X=X,componentIds=np.array([r['componentId'] for r in selected],dtype=np.int64));case_files.append(dict(**meta,path=str(target),rows=len(selected)))
        for i,r in enumerate(selected):records.append({'case':len(case_files)-1,'index':i,**meta,**r,**labeled.get(r['componentId'],dict(label=None,**{'class':'UNKNOWN'}))})
        print(json.dumps(dict(case=len(case_files)-1,components=len(selected),split=meta['split'])),flush=True)
    for si,s in enumerate(sources):
        picked=[r for r in review if r['sourceIndex']==si and r['label'] is not None]
        if not picked:continue
        lease.check();im=cv2.imread(s['absolutePath']);x,y=picked[0]['cropOrigin'];span=min(512,*im.shape[:2]);crop=im[y:y+span,x:x+span].copy();del im
        extract_case(crop,picked[0]['coordinateScale'],1.,dict(scope='added-reviewed-train',group=picked[0]['group'],source=s['sha256'],split='train',factor=1.,sourceIndex=si),{r['componentId']:{k:r[k] for k in ['label','class','group','split']} for r in picked});del crop
    for c,shape in zip(controls,old_shape):
        lease.check();source=cv2.imread(c['sourcePath']);a,b=shape['cropOrigin'];x,y,w,h=c['roi'];s=shape['referenceSpan']/640;pad=max(64,int(__import__('math').ceil(40*s)));crop=source[b:min(source.shape[0],y+h+pad),a:min(source.shape[1],x+w+pad)].copy();known,_=masks(source.shape[:2],c);observation=(known['visible-material']|known['reviewed-non-flake']|known['unknown'])[b:b+crop.shape[0],a:a+crop.shape[1]]>0;del source,known
        labeled={r['nativeComponentId']:dict(label=r['label'],**{'class':'material' if r['label']==1 else 'reviewed-non-flake'}) for r in old_labels if r['controlIndex']==c['controlIndex']}
        for factor in [1.,.5]:
            im=crop if factor==1 else cv2.resize(crop,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA);obs=observation if factor==1 else cv2.resize(observation.astype(np.uint8),(im.shape[1],im.shape[0]),interpolation=cv2.INTER_NEAREST)>0
            extract_case(im,s*factor,factor,dict(scope='preserved-optical',control=c['controlIndex'],group=c['group'],source=c['sourceSHA256'],split=c['split'],factor=factor,origin=[a,b],cropShape=[crop.shape[1],crop.shape[0]],kind=c['kind']),labeled if factor==1 else {},obs)
        del crop,im,observation,obs
    train=[r for r in records if r['split']=='train' and r['factor']==1 and r['label'] is not None];assert len(train)==63 and len({r['group'] for r in train})==15
    matrix=[]
    for r in train:
        with np.load(case_files[r['case']]['path']) as f:matrix.append(f['X'][r['index']].copy())
    assert not {r['group'] for r in train}&{r['group'] for r in records if r['split']=='validation'}
    if evaluate_only:head=json.loads((OUT/'single-crop-head.json').read_text('utf8'))
    else:
        head=M.fit_classifier(matrix,[r['label'] for r in train],[r['group'] for r in train],feature_group_sizes=[1280,12]);head.update(encoderSHA256=M.ENCODER_SHA,representation='proposal-component-on-non-self-ring-v1',accepted=False,fitCount=1)
        (OUT/'single-crop-head.json').write_text(json.dumps(head),'utf8')
    results=[]
    for case in case_files:
        if case['scope']!='preserved-optical':continue
        lease.check();c=controls[case['control']];source=cv2.imread(c['sourcePath']);known,objects=masks(source.shape[:2],c);del source;a,b=case['origin'];w,h=case['cropShape'];factor=case['factor']
        with np.load(case['path']) as data:
            field=data['field'];ids=data['ids'];X=data['X'];component_ids=data['componentIds'];allowed=np.zeros(int(ids.max())+1,bool);allowed[component_ids]=M.predict(X,head)>=.5;accepted=field*allowed[ids]
        def local(mask):
            m=mask[b:b+h,a:a+w]>0
            return m if factor==1 else cv2.resize(m.astype(np.uint8),(field.shape[1],field.shape[0]),interpolation=cv2.INTER_NEAREST)>0
        results.append(dict(**case,objects=[dict(index=o['index'],label=o['label'],proposal=measure(field,local(o['mask']),factor),singleCrop=measure(accepted,local(o['mask']),factor)) for o in objects],negative=measure(accepted,local(known['reviewed-non-flake']),factor)))
    summary=[]
    for factor in [1.,.5]:
        for split in ['train','validation']:
            selected=[r for r in results if r['factor']==factor and r['split']==split];objects=[o for r in selected for o in r['objects'] if o['label']=='visible-material'];summary.append(dict(factor=factor,split=split,objects=len(objects),hits=sum(o['singleCrop']['objectHit'] for o in objects),negativeSourcePixels=sum(r['negative']['activeSourcePixels'] for r in selected)))
    receipt=dict(summary=summary,rows=results,resource=lease.receipt(),trainRows=63,trainGroups=15,headFitCount=1,validationIndependentFinal=False,maximumResidentSources=1,maximumResidentCropTensors=16,normalProductEnabled=False,encoderReExported=False)
    (OUT/'single-crop-comparison.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(summary),flush=True)
