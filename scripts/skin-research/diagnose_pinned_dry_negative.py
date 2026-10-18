"""Fresh encoder proof for C04 false support and C08 recovery; no model fitting."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import json,sys,time,hashlib
from pathlib import Path
from heavy_job_lease import HeavyJobLease
from pinned_dry_contract import contract
CONTRACT=contract()
ROOT=Path(__file__).resolve().parents[2];OUT=CONTRACT['out'];OLD=ROOT/'audit-results/native-material-contour-20261013';CASE=ROOT/'audit-results/native-camera-scope-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
def read(path):return json.loads(path.read_text('utf8'))
with HeavyJobLease('CDC-fresh-encoder-C04-C08-admission',peak_mib=400,minimum_available_mib=900) as lease:
    import cv2,numpy as np,material_component_features as M
    from component_flake_gate import masks
    cv2.setNumThreads(1);controls=read(ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json')['controls'];review=read(OLD/'added-components-reviewed.json')['rows'];added=read(OLD/'added-train-source-selection.json')
    start_case=sum(any(r['sourceIndex']==i and r['label'] is not None for r in review) for i in range(len(added)))
    baseline=read(OLD/'material-encoder-balanced-comparison.json');optical=read(CASE/'single-crop-comparison.json')['rows'];scales=read(ROOT/'audit-results/native-dry-scale-20261013/independent-v3-comparison.json')['rows'];head_path=OUT/'delivery-snapshot/dryness/calibrated-source-group-head.json';head=read(head_path)
    head_hash=hashlib.sha256(head_path.read_bytes()).hexdigest();assert head_hash==CONTRACT['hashes']['dryness/calibrated-source-group-head.json']
    encoder_path=ROOT/'audit-results/material-runtime-followup-20261013/material-encoder.onnx';receipt=ROOT/'audit-results/material-runtime-followup-20261013/encoder-parity.json';load_start=time.monotonic();encoder=M.OnnxMaterialEncoder(encoder_path,receipt,intra_op_threads=1,batch_limit=4,cpu_mem_arena=False);load_seconds=time.monotonic()-load_start
    weights=ROOT/'audit-results/focused-skin-20261010/pretrained/efficientnet_b0_rwightman-7f5810bc.pth.safetensors';assert hashlib.sha256(weights.read_bytes()).hexdigest()==M.ENCODER_SHA
    with np.load(OLD/baseline['cacheFile']) as f:cache=f['features'].copy()
    rows=[]
    for index in [4,8]:
        lease.check();c=controls[index];case_index=start_case+2*index;offset=0
        for i in range(case_index):
            with np.load(CASE/f'conditioned-case-{i:02d}.npz') as f:offset+=len(f['componentIds'])
        with np.load(CASE/f'conditioned-case-{case_index:02d}.npz') as f:ids=f['ids'].copy();field=f['field'].copy();component_ids=f['componentIds'].copy();geometry=f['X'][:,-12:].copy()
        source=Path(c['sourcePath']);assert hashlib.sha256(source.read_bytes()).hexdigest()==c['sourceSHA256'];image=cv2.imread(str(source));meta=next(r for r in optical if r['control']==index and r['factor']==1);a,b=meta['origin'];w,h=meta['cropShape'];image=image[b:b+h,a:a+w];assert image.shape[:2]==field.shape
        known,objects=masks((h,w),{**c,'roi':[c['roi'][0]-a,c['roi'][1]-b,*c['roi'][2:]]});target=known['reviewed-non-flake']>0 if index==4 else next(o['mask'] for o in objects if o['index']==0)>0
        _,_,stats,_=cv2.connectedComponentsWithStats((ids>0).astype(np.uint8),8);metric=scales[index]['referenceSpan']/640
        cached_p=M.predict(np.c_[cache[offset:offset+len(component_ids)],geometry],head)
        selected=[j for j,cid in enumerate(component_ids) if int(cid)==({4:29,8:50}[index])]
        assert selected,'Expected selected reviewed support not found'
        overlay=image.copy();overlay[target]=(.5*overlay[target]+.5*np.array([0,0,255])).astype(np.uint8)
        for j in selected:
            cid=int(component_ids[j]);row=dict(componentId=cid,rect=stats[cid,:4].tolist(),geometry=geometry[j].tolist());crops,boxes=M.component_crops(image,row,metric);t=time.monotonic();fresh=encoder.extract(crops,4).reshape(1,2560);seconds=time.monotonic()-t;lease.check()
            p=float(M.predict(np.c_[fresh,geometry[j][None]],head)[0]);error=float(np.max(np.abs(fresh[0]-cache[offset+j])));assert error<1e-3 and abs(p-float(cached_p[j]))<1e-3
            proposal_active=(ids==cid)&target&(field>0);active=proposal_active&(p>=head['threshold']);overlay[active]=[255,255,0];x,y,ww,hh=row['rect']
            rows.append(dict(control=index,sourceSHA256=c['sourceSHA256'],split=c['split'],sourceKind='processed-clahe' if source.name.startswith('clahed_') else c['kind'],target='reviewed-non-flake' if index==4 else 'visible-material-object-0',componentId=cid,componentSourceBox=[x+a,y+b,ww,hh],reviewedProposalSourcePixels=int(proposal_active.sum()),reviewedActiveSourcePixels=int(active.sum()),freshProbability=p,cachedProbability=float(cached_p[j]),freshFeatureMaxAbsDifference=error,encoderSeconds=seconds,sourceCropOrigin=[a,b],cropBoxes=boxes,accepted=p>=head['threshold']))
        cv2.imwrite(str(OUT/f'C{index:02d}-reviewed-target-and-accepted-support.png'),overlay)
    result=dict(headSHA256=head_hash,sourceEncoderSHA256=M.ENCODER_SHA,onnxSHA256=encoder.hash,encoderLoadSeconds=load_seconds,rows=rows,threshold=head['threshold'],freshEncoderParityPassed=True,sourceCoordinatesVerified=True,newFit=False,normalSelectorChanged=False,resource=lease.receipt())
    (OUT/'C04-C08-fresh-encoder-diagnosis.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(dict(loadSeconds=load_seconds,rows=rows)),flush=True)
