"""Single expanded-data material fit; matched eight-feature reference.

All source/group labels are frozen before fitting. Validation is never used
by the scaler, classifier or threshold selection. Cached features are optical
observations, not annotations. No CNN parameter is trained.
"""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import collections,hashlib,json,sys,time
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-material-contour-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
from native_flake_support import proposal_tile
from material_component_features import describe,component_crops,FrozenMaterialEncoder,fit_classifier,predict,ENCODER_SHA
import component_flake_gate as C
from trial_region_flake_proposal import measure
cv2.setNumThreads(1)
old_root=ROOT/'audit-results/native-dry-scale-20261013'

def main():
    replay='--replay-scale-correction' in sys.argv
    target=OUT/'encoder-material-head.json';assert target.exists() if replay else not target.exists(),'Completed frozen fit must not be repeated'
    protocol=json.loads((OUT/'material-protocol.json').read_text('utf8'));review=json.loads((OUT/'added-components-reviewed.json').read_text('utf8'));assert review['reviewedBeforeFit']
    assert hashlib.sha256((OUT/'added-components-reviewed.json').read_bytes()).hexdigest()==protocol['addedReviewSHA256']
    sources=json.loads((OUT/'added-train-source-selection.json').read_text('utf8'));controls=json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json').read_text('utf8'))['controls']
    previous=json.loads((old_root/'native-gate-reviewed.json').read_text('utf8'))['rows'];comparison=json.loads((old_root/'independent-v3-comparison.json').read_text('utf8'))['rows'];records=[];cases=[];geometry=[]
    def encode_case(image,metric,density,meta,labels=None,observation_mask=None):
        field=proposal_tile(image,metric,pixel_density=density);ids,rows=describe(image,field,metric);indices=[]
        # Existing descriptor contract is retained for the preserved old head.
        original=C.proposal;C.proposal=lambda g:field
        try:_,_,old_rows=C.components(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY))
        finally:C.proposal=original
        old_features={r['nativeComponentId']:[float(np.log1p(r['sourcePixels']/(metric*metric))),*r['features'][1:]] for r in old_rows}
        for row in rows:
            # This is a compute selection for an offline partial-label metric,
            # after label-blind proposal generation. The classifier receives
            # only original crops/geometry. Unscored areas stay UNKNOWN; this
            # selection is never used by actual image inference or product maps.
            if meta['scope']=='added-reviewed-train' and row['componentId'] not in labels:continue
            if observation_mask is not None and not ((ids==row['componentId'])&observation_mask).any():continue
            index=len(records);_,boxes=component_crops(image,row,metric,density);geometry.append(row['geometry']);r={**meta,**row,'recordIndex':index,'caseIndex':len(cases),'cropBoxes':boxes,'oldEight':old_features.get(row['componentId'])}
            if labels and row['componentId'] in labels:r.update(labels[row['componentId']])
            else:r.update(label=None,**{'class':'UNKNOWN'})
            records.append(r);indices.append(index)
        cases.append(dict(meta=meta,field=field,ids=ids,indices=indices,image=image,metric=metric,density=density))
    for si,source in enumerate(sources):
        selected=[r for r in review['rows'] if r['sourceIndex']==si and r['label'] is not None]
        if not selected:continue
        image=cv2.imread(source['absolutePath']);x,y=selected[0]['cropOrigin'];span=min(512,*image.shape[:2]);image=image[y:y+span,x:x+span]
        labels={r['componentId']:{k:r[k] for k in ['label','class','group','split']} for r in selected}
        encode_case(image,selected[0]['coordinateScale'],1.,dict(sourceIndex=si,sourceSHA256=source['sha256'],group=selected[0]['group'],split='train',factor=1.,kind='pul' if source['reviewDomain']=='pul' else 'raw',scope='added-reviewed-train'),labels)
    for control,comp in zip(controls,comparison):
        image=cv2.imread(control['sourcePath']);assert hashlib.sha256(Path(control['sourcePath']).read_bytes()).hexdigest()==control['sourceSHA256'];a,b=comp['cropOrigin'];x,y,w,h=control['roi'];s=comp['referenceSpan']/640;pad=max(64,int(np.ceil(40*s)));crop=image[b:min(image.shape[0],y+h+pad),a:min(image.shape[1],x+w+pad)]
        labeled={r['nativeComponentId']:dict(label=r['label'],**{'class':'material' if r['label']==1 else 'reflection' if control['controlIndex']==7 else 'pore-texture'}) for r in previous if r['controlIndex']==control['controlIndex']}
        known,_=C.masks(image.shape[:2],control);observation=(known['visible-material']|known['reviewed-non-flake']|known['unknown'])[b:b+crop.shape[0],a:a+crop.shape[1]]>0
        for factor in [1.,.5]:
            im=crop if factor==1 else cv2.resize(crop,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA)
            observed=observation if factor==1 else cv2.resize(observation.astype(np.uint8),(im.shape[1],im.shape[0]),interpolation=cv2.INTER_NEAREST)>0
            encode_case(im,s*factor,factor,dict(controlIndex=control['controlIndex'],sourceSHA256=control['sourceSHA256'],group=control['group'],split=control['split'],factor=factor,kind=control['kind'],cropOrigin=[a,b],cropShape=[crop.shape[1],crop.shape[0]],scope='preserved-50-label-optical'),labeled if factor==1 else None,observed)
    signature=hashlib.sha256(json.dumps([(r['sourceSHA256'],r['factor'],r['rect'],r['cropBoxes']) for r in records],sort_keys=True).encode()).hexdigest();cache=OUT/(signature[:16]+'-encoder-features.npz');start=time.monotonic()
    if cache.exists():features=np.load(cache)['features']
    else:
        encoder=FrozenMaterialEncoder(ROOT/'audit-results/focused-skin-20261010/pretrained/efficientnet_b0_rwightman-7f5810bc.pth.safetensors')
        parts=[]
        for offset in range(0,len(records),16):
            crops=[]
            for r in records[offset:offset+16]:
                case=cases[r['caseIndex']];batch_crops,_=component_crops(case['image'],r,case['metric'],case['density']);crops.extend(batch_crops)
            parts.append(encoder.extract(crops,4));print(json.dumps(dict(extractedComponents=min(len(records),offset+16),totalComponents=len(records),maximumResidentCropTensors=32)),flush=True)
        features=np.concatenate(parts).reshape(len(records),2560);del parts,crops;np.savez_compressed(cache,features=features)
    X=np.c_[features,np.asarray(geometry)];G=np.asarray(geometry)[:,:8]
    train=[i for i,r in enumerate(records) if r['label'] is not None and r['split']=='train' and r['factor']==1.];val=[i for i,r in enumerate(records) if r['label'] is not None and r['split']=='validation' and r['factor']==1.]
    train_groups={records[i]['group'] for i in train};assert not train_groups&{records[i]['group'] for i in val}
    y=[records[i]['label'] for i in train];groups=[records[i]['group'] for i in train]
    if replay:
        head=json.loads(target.read_text('utf8'));eight=json.loads((OUT/'expanded-eight-feature-head.json').read_text('utf8'))
        first=json.loads((OUT/'material-encoder-comparison.json').read_text('utf8'));previous_features=np.load(OUT/first['cacheFile'])['features'];assert np.max(np.abs(features[train]-previous_features[train]))<1e-6,'All native TRAIN features must remain unchanged; no second fit permitted'
    else:
        head=fit_classifier(X[train],y,groups);eight=fit_classifier(G[train],y,groups)
        target.write_text(json.dumps(dict(**head,encoderSHA256=ENCODER_SHA,accepted=False,fitCount=1,cacheSHA256=hashlib.sha256(cache.read_bytes()).hexdigest(),reviewSHA256=protocol['addedReviewSHA256'],normalProductEnabled=False)),'utf8')
        (OUT/'expanded-eight-feature-head.json').write_text(json.dumps(eight),'utf8')
    p=predict(X,head);p8=predict(G,eight)
    old_model=json.loads((old_root/'native-gate-model.json').read_text('utf8'));old_pred=np.array([C.predict(r['oldEight'],old_model) if r['oldEight'] else 0. for r in records])
    classified=[]
    for i in val:classified.append(dict(controlIndex=records[i]['controlIndex'],componentId=records[i]['componentId'],label=records[i]['label'],**{'class':records[i]['class']},geometryAccepted=bool(p8[i]>=.5),encoderAccepted=bool(p[i]>=.5),preservedTenAccepted=bool(old_pred[i]>=.5),encoderProbability=float(p[i])))
    results=[]
    for case in cases:
        meta=case['meta'];ids=case['ids'];allowed=np.zeros(int(ids.max())+1,bool);a8=allowed.copy();old=allowed.copy()
        for index in case['indices']:
            c=records[index]['componentId'];allowed[c]=p[index]>=.5;a8[c]=p8[index]>=.5;old[c]=old_pred[index]>=.5
        if meta['scope']!='preserved-50-label-optical':continue
        control=next(c for c in controls if c['controlIndex']==meta['controlIndex']);source=cv2.imread(control['sourcePath']);known,objects=C.masks(source.shape[:2],control);a,b=meta['cropOrigin'];ww,hh=meta['cropShape'];factor=meta['factor']
        def local(mask):
            m=mask[b:b+hh,a:a+ww]>0
            return m if factor==1 else cv2.resize(m.astype(np.uint8),(case['image'].shape[1],case['image'].shape[0]),interpolation=cv2.INTER_NEAREST)>0
        fields={'proposal':case['field'],'encoder':case['field']*allowed[ids],'eightExpanded':case['field']*a8[ids],'tenPreserved':case['field']*old[ids]}
        obj=[dict(index=o['index'],label=o['label'],fields={k:measure(f,local(o['mask']),factor) for k,f in fields.items()}) for o in objects]
        neg={k:measure(f,local(known['reviewed-non-flake']),factor) for k,f in fields.items()};results.append(dict(**meta,objects=obj,negative=neg))
        np.savez_compressed(OUT/f'C{control["controlIndex"]:02d}-scale{factor}-gated-field{"-crop-v2" if replay else ""}.npz',field=fields['encoder'],geometryField=fields['eightExpanded'])
    summary=[]
    for factor in [1.,.5]:
        for split in ['train','validation']:
            rs=[r for r in results if r['factor']==factor and r['split']==split];objs=[o for r in rs for o in r['objects'] if o['label']=='visible-material']
            summary.append(dict(factor=factor,split=split,objects=len(objs),methods={k:dict(hits=sum(o['fields'][k]['objectHit'] for o in objs),negativeSourcePixels=sum(r['negative'][k]['activeSourcePixels'] for r in rs)) for k in ['proposal','encoder','eightExpanded','tenPreserved']}))
    counts=collections.Counter(records[i]['class'] for i in train);group_counts={c:len({records[i]['group'] for i in train if records[i]['class']==c}) for c in counts}
    receipt=dict(trainRows=len(train),trainGroups=len(train_groups),trainClassCounts=dict(counts),classGroupCounts=group_counts,validationRows=len(val),validationIndependentFinal=False,threshold=.5,encoderFrozen=True,featuresShape=list(X.shape),cacheFile=cache.name,featureSeconds=time.monotonic()-start,summary=summary,validationComponents=classified,rows=results,normalProductEnabled=False,computeScope='human-reviewed training components and post-proposal components intersecting existing partial observation regions; out-of-scope field is not a normal product result')
    receipt.update(headRefitted=False if replay else True,trainFeaturesUnchanged=True if replay else None,cropSamplingVersion='density-scaled-native-margins-v2' if replay else 'fixed-native-minimum-context-v1')
    (OUT/('material-encoder-scale-corrected.json' if replay else 'material-encoder-comparison.json')).write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps({k:v for k,v in receipt.items() if k not in ['rows','validationComponents']}),flush=True)

if __name__=='__main__':main()
