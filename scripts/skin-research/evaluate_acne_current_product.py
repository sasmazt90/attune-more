"""Fixed-threshold current-product staging evaluation; one image/tile at a time."""
import argparse,base64,hashlib,json,time
from pathlib import Path
from acne_takeover_support import ROOT,AG,OUT,read,digest,current_product_masks,tile_rectangles,infer_tiles,one_to_one,strict_clean_mask
from heavy_job_lease import HeavyJobLease

MODELS={
 'step0':(OUT/'models/step0.safetensors','18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'),
 'control_iou':(OUT/'models/control_iou.safetensors','d7085eb29cbee913f5e1fd9c267f6525f13cce2566e8d38a2fc31b6c1df9d75c'),
 'candidate_giou':(OUT/'models/candidate_giou.safetensors','825d2956bc37495746a94113816ba16c7236caa1e028844ded89d76bee8472e2')}
SCOPE_POS=['55d380f7','695ed248','4a1762ee']
SCOPE_NEG=['36e4010b','20031f35','02386f86','0597e811','0560bfd8','0f3354ae','0d891a03','33da7a52','02413bf9']

def aggregate(rows):
    result=dict(photos=len(rows),targets=sum(r['targetCount'] for r in rows),matched=sum(len(r['pairs']) for r in rows),verifiedCleanFP=sum(r['cleanFP'] for r in rows),verifiedCleanArea80FP=sum(v['cleanAreaFraction']>=.8 for r in rows for v in r['verifiedCleanFalseCandidates']),reviewedNegativePhotos=sum(r.get('verifiedCleanPixels',0)>0 for r in rows),scale={})
    for name in ['micro','small','medium']:
        result['scale'][name]=dict(targets=sum(r['scale'][name]['targets'] for r in rows),matched=sum(r['scale'][name]['matched'] for r in rows))
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',choices=[*MODELS,'control','hard-negative','objectness-features'],required=True);parser.add_argument('--scope-and-train-only',action='store_true');args=parser.parse_args()
    if args.model in MODELS:path,expected=MODELS[args.model]
    elif args.model=='objectness-features':
        path=OUT.parent/'acne-learnability-20261015/model.safetensors';feature_receipt=read(path.parent/'receipt.json');expected=feature_receipt['modelSHA256']
    else:path=OUT/('clean-pilot-'+args.model)/'model.safetensors';expected=read(path.parent/'receipt.json')['checkpointSHA256']
    assert digest(path)==expected
    pre=read(OUT/'browser-preflight.json');original=read(OUT/'inputs/original-reviewed-detector-data.json');bysha={r['sha256']:r for r in original['rows']}
    manifest=read(OUT/'inputs/annotation-scope-manifest.json');scope={r['sha256']:r for r in manifest['images']};output=OUT/('evaluation-'+args.model);output.mkdir(exist_ok=True)
    support_rows={r['sha256']:r for r in read(OUT/'train-clean-support/manifest.json')['rows']} if (OUT/'train-clean-support/manifest.json').exists() else {}
    with HeavyJobLease('CDC-acne-current-product-eval-'+args.model,peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        import cv2,numpy as np,torch
        from safetensors.torch import load_file
        from yolox_p2 import build_yolox_p2_model
        from skin_eyewear import classify_source,classify_roi
        from acne_box_support_staging import principled_accepted_boxes
        from acne_box_support import accepted_boxes
        torch.set_num_threads(4)
        if args.model=='objectness-features':
            from acne_objectness_features import build_feature_model,VERSION
            assert feature_receipt['graphVersion']==VERSION
            net=build_feature_model()
        else:net=build_yolox_p2_model()
        net.load_state_dict(load_file(str(path)),strict=True);net.eval();results=[];start=time.monotonic()
        for a in pre['rows']:
            if args.scope_and_train_only and a['cohort']=='heldout-train':continue
            if a['cohort']=='scope-B-development' and a['sha256'][:8] not in SCOPE_POS+SCOPE_NEG:continue
            photo_started=time.monotonic()
            lease.check();s=a['sha256'];r=bysha[s]
            if a['cohort']=='pilot-train-diagnosis' and r.get('annotations'):continue
            dest=OUT/'product-inputs'/s;snap=a.get('snapshot');image=cv2.imread(str(dest/'snapshot.png')) if snap else cv2.imread(a['path']);assert image is not None
            assert image.shape[1]==a['width'] and image.shape[0]==a['height'],'SOURCE_COORDINATE_DIMENSIONS'
            points=a['alignment'].get('landmarks',[]);eye_front=None;eye_back=None
            if a.get('eyePhoto'):
                eye=cv2.imdecode(np.frombuffer(base64.b64decode(a['eyePhoto'].split(',',1)[1]),np.uint8),cv2.IMREAD_COLOR);eye_front=classify_roi(cv2.cvtColor(eye,cv2.COLOR_BGR2RGB));eye_back=classify_source(image,points)
            clear=bool(eye_front and eye_back and eye_front['status']==eye_back['status']=='CLEAR')
            valid=bool(snap and a['qualityPoseEligible'] and clear)
            pose_rejected=not a['poseEligible'];blur_rejected=a['quality']['status']=='BLURRY'
            raw,trace=infer_tiles(net,image,tile_rectangles(image,points,r.get('crop')),lease.check)
            assigned={};rejected=[];old={};masks=None
            if snap:
                photo='data:image/png;base64,'+base64.b64encode((dest/'snapshot.png').read_bytes()).decode();pixel_id=hashlib.sha256(cv2.cvtColor(image,cv2.COLOR_BGR2RGBA).tobytes()).hexdigest();payload=dict(photo=photo,photoId=pixel_id,landmarks=points,meshes=snap['meshes'],exclusions=snap['exclusions'],qualityValid=a['quality']['isValid'],conditions=dict(yaw=a['alignment']['yaw'],pitch=a['alignment']['pitch'],roll=a['alignment']['roll'],scaleRatio=a['alignment']['scaleRatio']))
                masks=current_product_masks(payload);allowed=list(snap['meshes'])
                assigned,rejected=principled_accepted_boxes(raw,masks['acne_envelopes'],masks['acne_skin'],masks['hair'],masks['acne_exclusion'],pixel_id,masks['scale'],masks['origin'],visible_regions=allowed,landmarks=points,source_shape=image.shape[:2],bgr=image)
                old,_=accepted_boxes(raw,masks['acne_envelopes'],masks['acne_skin'],masks['hair'],masks['acne_exclusion'],s,masks['scale'],masks['origin'])
            final=[b for v in assigned.values() for b in v];pred=[[b['x'],b['y'],b['x']+b['width'],b['y']+b['height']] for b in final]
            # Only original real box labels; photometric pseudo annotations excluded.
            anns=r.get('annotations',[])
            if s in scope:anns=[v for v in scope[s]['annotations'] if v['scopeCategory']=='IN_SCOPE_VISIBLE_REGION']
            truth=[v['box'] for v in anns];pairs=one_to_one(truth,pred);matched={p[0] for p in pairs};clean=np.zeros(image.shape[:2],np.uint8)
            if r['split']=='train':
                support=None
                if s in support_rows:
                    support_path=OUT/'train-clean-support'/(s+'.png');assert digest(support_path)==support_rows[s]['maskSHA256'];support=cv2.imread(str(support_path),cv2.IMREAD_GRAYSCALE)
                clean,_=strict_clean_mask(r,image,reviewed_support=support)
            elif r.get('negativeROI') and not r.get('annotations'):
                # Evaluation only: existing explicit criterion-specific clean review.
                from source_skin_support import known_skin_scope
                if points:clean=known_skin_scope({**r,'landmarks':points},image)
            fps=[];unknown=[];paired_pred={p[1] for p in pairs}
            for i,b in enumerate(pred):
                if i in paired_pred:continue
                x,y,ex,ey=[int(round(v)) for v in b];x=max(0,x);y=max(0,y);ex=min(image.shape[1],ex);ey=min(image.shape[0],ey);area=clean[y:ey,x:ex]
                # Keep historical center metric and stricter area evidence separately.
                cx=int((x+ex)/2);cy=int((y+ey)/2);center=bool(0<=cx<clean.shape[1] and 0<=cy<clean.shape[0] and clean[cy,cx])
                (fps if center else unknown).append(dict(index=i,box=b,cleanAreaFraction=float(area.mean()) if area.size else 0,confidence=final[i]['confidence']))
            scales={name:dict(targets=0,matched=0) for name in ['micro','small','medium']}
            for i,b in enumerate(truth):
                dim=max(b[2]-b[0],b[3]-b[1]);name='micro' if dim<8 else 'small' if dim<16 else 'medium';scales[name]['targets']+=1;scales[name]['matched']+=i in matched
            visible=[]
            if masks:
                union=np.logical_or.reduce(list(masks['acne_envelopes'].values()))
                for i,(x,y,ex,ey) in enumerate(truth):
                    cx=int(((x+ex)/2-masks['origin'][0])*masks['scale']);cy=int(((y+ey)/2-masks['origin'][1])*masks['scale'])
                    if 0<=cx<union.shape[1] and 0<=cy<union.shape[0] and union[cy,cx]:visible.append(i)
            result=dict(sha256=s,cohort=a['cohort'],split=r['split'],group=r['group'],fullStaticProductPass=valid,temporalCameraStabilityVerified=False,quality=a['quality'],poseRejected=pose_rejected,blurRejected=blur_rejected,angle=a['matchedAngle'],eyewearFrontend=eye_front,eyewearBackend=eye_back,targetCount=len(truth),truth=truth,pairs=pairs,anatomicalEnvelopeCenterTargets=visible,anatomicalEnvelopeCenterPairs=[v for v in pairs if v[0] in visible],fixedTargetDenominatorRetained=True,cleanFP=len(fps),verifiedCleanPixels=int(clean.sum()),verifiedCleanFalseCandidates=fps,unmatchedUnknown=unknown,scale=scales,finalCandidates=final,rejections=rejected,oldFilterCandidates=[v for boxes in old.values() for v in boxes],trace=trace,stagingSeconds=time.monotonic()-photo_started,sourceTransform=dict(origin=masks['origin'],scale=masks['scale'],maskShape=list(masks['acne_skin'].shape)) if masks else None)
            (output/(s+'.json')).write_text(json.dumps(result),'utf8');results.append(result)
            print(json.dumps(dict(model=args.model,sha=s[:8],passProduct=valid,hit=len(pairs),gt=len(truth),cleanFP=len(fps))),flush=True)
        held=[r for r in results if r['cohort']=='heldout-train'];scope_b=[r for r in results if r['sha256'][:8] in SCOPE_POS+SCOPE_NEG]
        admissible=[r for r in held if r['fullStaticProductPass']]
        report=dict(model=args.model,modelSHA256=expected,tilingContract='current-skin-models-photo-input-camera-crop-v1',confidence=.30,hardNMS=.30,matchIoU=.50,primary='static current browser product admissibility, temporal stability not a physical camera test',preflight=dict(controlPhotos=len(held),controlStaticPass=sum(r['fullStaticProductPass'] for r in held),poseRejected=sum(r['poseRejected'] for r in held),blurRejected=sum(r['blurRejected'] for r in held)),heldoutAdmissible=aggregate(admissible),heldoutAnatomicalEnvelopeCenter=dict(targets=sum(len(r['anatomicalEnvelopeCenterTargets']) for r in admissible),matched=sum(len(r['anatomicalEnvelopeCenterPairs']) for r in admissible)),heldoutRobustness=aggregate(held),scopeBDevelopment=aggregate(scope_b),scopeBProductAdmissible=aggregate([r for r in scope_b if r['fullStaticProductPass']]),rows=results,resource=lease.receipt(),elapsedSeconds=time.monotonic()-start,productionActive=False)
        (output/'summary.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items() if k not in ['rows','resource']}),flush=True)

if __name__=='__main__':main()
