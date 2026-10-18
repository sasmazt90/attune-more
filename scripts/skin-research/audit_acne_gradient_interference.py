"""Finite post-freeze TRAIN gradient probe, with zero optimizer updates.

Compare each object's negative gradient with the original Pimple positive
gradient on its actual last four-tile training batch. Local alignment is a
diagnostic, not a proof about the whole optimizer trajectory or generalization.
"""
import gc
import json
from pathlib import Path
from acne_takeover_support import OUT,read,digest,strict_clean_mask,known_cells,one_to_one
from heavy_job_lease import HeavyJobLease

DEST=OUT.parent/'acne-learnability-20261015'


def main():
    receipt=read(DEST/'receipt.json');plan=read(DEST/'preregistration.json');sequence=read(OUT/'clean-pilot-hard-negative/sequence.json');objects=read(OUT/'source-negative-repair-probe.json')['components']
    batches=[]
    for item in objects:
        indices=[]
        for i,row in enumerate(sequence):
            if row['sha256']!=item['sha256']:continue
            a,b,_,_=row['rect'];x,y,ex,ey=item['box']
            if [x-a,y-b,ex-a,ey-b] in row['objectNegatives']:indices.append(i)
        assert indices;batches.append((item,indices[-1]//4))
    with HeavyJobLease('CDC-acne-frozen-gradient-interference',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        # Large ledgers must be allocated inside the monitored memory budget,
        # not before ownership/reserve checks. All guard limits stay unchanged.
        original={r['sha256']:r for r in read(OUT/'inputs/original-reviewed-detector-data.json')['rows'] if r['split']=='train'}
        curated={r['sha256']:r for r in read(OUT/'inputs/train-data-engineering-reviewed-20261013.json')['rows'] if r['split']=='train'}
        supports={r['sha256']:r for r in read(OUT/'train-clean-support/manifest.json')['rows']}
        import cv2
        import numpy as np
        import torch
        from safetensors.torch import load_file
        from yolox_p2 import build_yolox_p2_model
        from acne_objectness_features import install_objectness_features,configure_learnable,frozen_hash,build_feature_model
        from acne_object_negatives import reviewed_object_negative_mask
        from focal_objectness_loss import SigmoidFocalObjectnessLoss
        torch.set_num_threads(4);records=[];state_checks=[];positive_loss_stages=[]
        from torchvision.ops import box_iou
        from skin_models import _nms
        final_measure=read(DEST/'measure-step-000150.json');probe_rows=[next(r for r in sequence if r['sha256']==item['sha256'] and r['rect']==item['selectedTile']['rect']) for item in objects]+plan['positiveProbes']
        class Decomposed(SigmoidFocalObjectnessLoss):
            def forward(self,logits,truth):
                union=torch.zeros_like(truth,dtype=torch.bool);focus=torch.zeros_like(truth,dtype=torch.bool)
                for box,is_focus in self.objects:
                    mask=reviewed_object_negative_mask(self.decoded_boxes,torch.tensor([box]),self.protected)&(truth==0);union|=mask
                    if is_focus:focus|=mask
                self.known=self.known|union;saved=self.boundary_weights;self.boundary_weights=torch.where(union,torch.ones_like(saved),saved)
                result=super().forward(logits,truth);self.boundary_weights=saved
                self.positive=result[truth>0].sum()/max(1,int((truth>0).sum()))/4
                self.negative=(result*focus).sum()*20/max(1,int((self.known&(truth==0)).sum()))/4
                self.has_positive=bool((truth>0).any());self.has_negative=bool(focus.any());self.positive_anchors=int((truth>0).sum());self.negative_anchors=int(focus.sum())
                return result
        for model in ('step0','features-150'):
            if model=='step0':
                net=build_yolox_p2_model();net.load_state_dict(load_file(str(OUT/'models/step0.safetensors')),strict=True);install_objectness_features(net)
            else:
                assert digest(DEST/'model.safetensors')==receipt['modelSHA256'];net=build_feature_model();net.load_state_dict(load_file(str(DEST/'model.safetensors')),strict=True)
            names=configure_learnable(net);params=[p for n,p in net.named_parameters() if n in names];full_before=frozen_hash(net,[]);focal=Decomposed();net.head.obj_focal_loss=focal
            for item,batch in batches:
                lease.check();pos=[torch.zeros_like(p) for p in params];neg=[torch.zeros_like(p) for p in params];p_loss=0.;n_loss=0.;p_count=0;n_count=0
                for row in sequence[batch*4:batch*4+4]:
                    lease.check();source=original[row['sha256']];path=Path(source['absolutePath']);assert digest(path)==row['sha256'];image=cv2.imread(str(path));support=None
                    if row['sha256'] in supports:
                        sp=OUT/'train-clean-support'/(row['sha256']+'.png');assert digest(sp)==supports[row['sha256']]['maskSHA256'];support=cv2.imread(str(sp),cv2.IMREAD_GRAYSCALE)
                    mask,weight=strict_clean_mask(source,image,[r['box'] for r in curated[row['sha256']]['annotations']],reviewed_support=support);focal.known,focal.boundary_weights=known_cells(mask,weight,row['rect']);focal.protected=torch.tensor(row['protectedBoxes']).reshape(-1,4);focal.objects=[]
                    a,b,c,d=row['rect']
                    for obj in objects:
                        if obj['sha256']!=row['sha256']:continue
                        x,y,ex,ey=obj['box'];box=[x-a,y-b,ex-a,ey-b]
                        if box in row['objectNegatives']:focal.objects.append((box,obj['sourceAnnotationId']==item['sourceAnnotationId']))
                    tile=np.full((384,384,3),114,np.uint8);patch=image[b:d,a:c];tile[:patch.shape[0],:patch.shape[1]]=patch;x=torch.from_numpy(tile.transpose(2,0,1).copy()).float()[None];y=torch.zeros((1,max(1,len(row['boxes'])),5))
                    for i,(bx,by,ex,ey) in enumerate(row['boxes']):y[0,i]=torch.tensor([0,(bx+ex)/2,(by+ey)/2,ex-bx,ey-by])
                    net(x,y);p_loss+=float(focal.positive.detach());n_loss+=float(focal.negative.detach());p_count+=focal.positive_anchors;n_count+=focal.negative_anchors
                    if focal.has_positive:
                        gradients=torch.autograd.grad(focal.positive,params,retain_graph=True,allow_unused=True)
                        for total,g in zip(pos,gradients):
                            if g is not None:total.add_(g.detach())
                    if focal.has_negative:
                        gradients=torch.autograd.grad(focal.negative,params,allow_unused=True)
                        for total,g in zip(neg,gradients):
                            if g is not None:total.add_(g.detach())
                    net.zero_grad(set_to_none=True)
                pn=math_norm(pos);nn=math_norm(neg);dot=sum(float((p*n).sum()) for p,n in zip(pos,neg));record=dict(model=model,sourceAnnotationId=item['sourceAnnotationId'],sha256=item['sha256'],actualTrainingOptimizerStep=batch+1,positiveLoss=p_loss,objectNegativeLoss=n_loss,positiveAssignedAnchors=p_count,objectNegativeAnchors=n_count,positiveGradientNorm=pn,negativeGradientNorm=nn,gradientDot=dot,gradientCosine=dot/(pn*nn) if pn and nn else None,scope='local TRAIN gradient diagnostic; zero optimizer updates, not causal proof of entire training')
                for family,prefix in [('feature','head.obj_convs.'),('prediction','head.obj_preds.')]:
                    selected=[i for i,n in enumerate(names) if n.startswith(prefix)];fp=[pos[i] for i in selected];fn=[neg[i] for i in selected];pn_family=math_norm(fp);nn_family=math_norm(fn);fdot=sum(float((p*n).sum()) for p,n in zip(fp,fn));record[family+'GradientCosine']=fdot/(pn_family*nn_family) if pn_family and nn_family else None
                records.append(record);print(json.dumps(record),flush=True);del pos,neg;gc.collect()
            net.eval()
            with torch.inference_mode():
                for key,target_index in final_measure['lostBaselineSourceTargets']:
                    sha,rect_string=key.split(':');rect=list(map(int,rect_string.split(',')));row=next(r for r in probe_rows if r['sha256']==sha and r['rect']==rect);lease.check();path=Path(original[sha]['absolutePath']);assert digest(path)==sha;image=cv2.imread(str(path));a,b,c,d=rect;tile=np.full((384,384,3),114,np.uint8);patch=image[b:d,a:c];tile[:patch.shape[0],:patch.shape[1]]=patch;pred=net(torch.from_numpy(tile.transpose(2,0,1).copy()).float()[None])[0];center=pred[:,:2];size=pred[:,2:4];boxes=torch.cat([center-size/2,center+size/2],1);boxes[:,0::2].clamp_(0,c-a);boxes[:,1::2].clamp_(0,d-b);scores=pred[:,4]*pred[:,5];iou=box_iou(boxes,torch.tensor([row['boxes'][target_index]],dtype=torch.float32))[:,0];ids=torch.where(iou>=.50)[0];best=int(ids[scores[ids].argmax()]) if len(ids) else None
                    candidates=[]
                    for index in torch.where(scores>=.30)[0].tolist():
                        x,y,ex,ey=boxes[index].tolist();box=[max(0,x),max(0,y),min(c-a,ex),min(d-b,ey),float(scores[index])]
                        if box[2]>box[0] and box[3]>box[1]:candidates.append(box)
                    final_boxes=_nms(candidates,threshold=.30) if candidates else [];pairs=one_to_one(row['boxes'],[v[:4] for v in final_boxes]);positive_loss_stages.append(dict(model=model,sha256=sha,tile=rect,localTargetIndex=target_index,sourceBox=[row['boxes'][target_index][0]+a,row['boxes'][target_index][1]+b,row['boxes'][target_index][2]+a,row['boxes'][target_index][3]+b],matchingRawAnchors=len(ids),bestAnchor=best,maxMatchingConfidence=float(scores[best]) if best is not None else None,objectness=float(pred[best,4]) if best is not None else None,classProbability=float(pred[best,5]) if best is not None else None,matchedAfterConfidenceAndNMS=any(p[0]==target_index for p in pairs)))
            state_checks.append(frozen_hash(net,[])==full_before);assert state_checks[-1]
            del net,params;gc.collect()
        payload=dict(optimizerUpdates=0,modelAndBNStateUnchanged=all(state_checks),records=records,positiveLossStages=positive_loss_stages,resource=lease.receipt())
    (DEST/'gradient-interference.json').write_text(json.dumps(payload,indent=2),encoding='utf8')


def math_norm(tensors):
    return sum(float(t.square().sum()) for t in tensors)**.5


if __name__=='__main__':main()
