"""One frozen component fit, followed by whole-object optical comparison.

The model is an isolated diagnostic. Probability never becomes severity.
"""
import hashlib,json,sys,time
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-dry-scale-20261013'
sys.path.insert(0,str(ROOT/'services/core-api'))
import component_flake_gate as C
from native_flake_support import proposal_tile
from trial_region_flake_proposal import measure
cv2.setNumThreads(1)

def described(image,metric,density=1.):
    field=proposal_tile(image,metric,pixel_density=density);original=C.proposal;C.proposal=lambda g:field
    try:raw,ids,rows=C.components(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY))
    finally:C.proposal=original
    for row in rows:row['features'][0]=float(np.log1p(row['sourcePixels']/(metric*metric)))
    return raw,ids,rows

def main():
    target=OUT/'native-gate-model.json';assert not target.exists(),'Single frozen fit; do not repeat'
    reviewed=json.loads((OUT/'native-gate-unreviewed.json').read_text('utf8'))
    # Both component sheets were visually inspected before this fit. Labels
    # remain assignments from existing polygons; no outside area is negative.
    for row in reviewed['rows']:row['reviewed']=True
    reviewed.update(reviewedBeforeFit=True,reviewMethod='native-gate-review-0/1 visual component inspection',modelFitted=False)
    file=OUT/'native-gate-reviewed.json';assert not file.exists();file.write_text(json.dumps(reviewed,indent=2),'utf8')
    train=[r for r in reviewed['rows'] if r['split']=='train'];val=[r for r in reviewed['rows'] if r['split']=='validation']
    assert not {r['group'] for r in train}&{r['group'] for r in val}
    X=np.array([r['features'] for r in train]);y=np.array([r['label'] for r in train]);mean=X.mean(0);std=np.maximum(X.std(0),1e-6)
    X=np.c_[np.ones(len(X)),(X-mean)/std];weights=np.array([len(y)/(2*np.sum(y==v)) for v in y]);beta=np.zeros(X.shape[1]);reg=np.ones(len(beta));reg[0]=0;start=time.monotonic()
    for iteration in range(60):
        p=1/(1+np.exp(-np.clip(X@beta,-40,40)));gradient=X.T@(weights*(p-y))+reg*beta
        hessian=(X.T*(weights*p*(1-p)))@X+np.diag(reg+1e-8);delta=np.linalg.solve(hessian,gradient);beta-=delta
        if np.linalg.norm(delta)<1e-7:break
    model=dict(version='isolated-native-material-component-v1',accepted=False,features=C.FEATURES,mean=mean.tolist(),std=std.tolist(),coefficients=beta.tolist(),threshold=.5,regularization=1.,iterations=iteration+1,reviewedFeaturesSHA256=hashlib.sha256(file.read_bytes()).hexdigest(),protocolSHA256=hashlib.sha256((OUT/'native-gate-protocol.json').read_bytes()).hexdigest())
    target.write_text(json.dumps(model,indent=2),'utf8')
    matrix=np.zeros((2,2),int)
    for r in val:matrix[r['label'],int(C.predict(r['features'],model)>=.5)]+=1
    labels=json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json').read_text('utf8'))
    comparisons=json.loads((OUT/'independent-v3-comparison.json').read_text('utf8'))['rows'];results=[]
    for control,comparison in zip(labels['controls'],comparisons):
        source=cv2.imread(control['sourcePath']);a,b=comparison['cropOrigin'];x,y,w,h=control['roi'];metric=comparison['referenceSpan']/640;pad=max(64,int(np.ceil(40*metric)))
        crop=source[b:min(source.shape[0],y+h+pad),a:min(source.shape[1],x+w+pad)];known,objects=C.masks(source.shape[:2],control)
        for factor in list(dict.fromkeys([1.,.5,min(1.,320/comparison['referenceSpan'])])):
            image=crop if factor==1 else cv2.resize(crop,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA)
            raw,ids,components=described(image,metric*factor,factor);allowed=np.zeros(int(ids.max())+1,bool)
            for r in components:
                if C.predict(r['features'],model)>=.5:allowed[r['nativeComponentId']]=True
            gated=raw*allowed[ids];records=[]
            def local(mask):
                m=mask[b:b+crop.shape[0],a:a+crop.shape[1]]>0
                return m if factor==1 else cv2.resize(m.astype(np.uint8),(image.shape[1],image.shape[0]),interpolation=cv2.INTER_NEAREST)>0
            for obj in objects:records.append(dict(index=obj['index'],label=obj['label'],proposal=measure(raw,local(obj['mask']),factor),gated=measure(gated,local(obj['mask']),factor)))
            results.append(dict(controlIndex=control['controlIndex'],sourceSHA256=control['sourceSHA256'],split=control['split'],kind=control['kind'],factor=factor,objects=records,negative=measure(gated,local(known['reviewed-non-flake']),factor),proposalNegative=measure(raw,local(known['reviewed-non-flake']),factor)))
    summaries=[]
    for factor in [1.,.5]:
        for split in ['train','validation']:
            rows=[r for r in results if r['factor']==factor and r['split']==split];obj=[o for r in rows for o in r['objects'] if o['label']=='visible-material']
            summaries.append(dict(factor=factor,split=split,objects=len(obj),proposalHits=sum(o['proposal']['objectHit'] for o in obj),gatedHits=sum(o['gated']['objectHit'] for o in obj),negativeSourcePixels=sum(r['negative']['activeSourcePixels'] for r in rows),proposalNegativeSourcePixels=sum(r['proposalNegative']['activeSourcePixels'] for r in rows)))
    receipt=dict(seconds=time.monotonic()-start,trainComponents=len(train),familiarValidationComponents=len(val),componentConfusionMatrix=matrix.tolist(),summary=summaries,rows=results,normalProductEnabled=False,independentFinalTest=False,featureScaleContract='area reference normalized; original eight-descriptor ring kernel fixed at native seven pixels; experimental only')
    (OUT/'native-gate-comparison.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps({k:v for k,v in receipt.items() if k!='rows'}))

if __name__=='__main__':main()
