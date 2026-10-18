"""One preregistered <=150-step feature-learning candidate, with per-object proof.

Does not rerun either previous arm. Native TRAIN data are streamed. Product
configuration, AG files, Scope B and held-out sources are never fit inputs.
"""
import gc
import hashlib
import json
import math
import random
import time
from pathlib import Path
from acne_takeover_support import ROOT, OUT, read, digest, strict_clean_mask, known_cells, one_to_one
from heavy_job_lease import HeavyJobLease

DEST = OUT.parent/'acne-learnability-20261015'


def main():
    plan=read(DEST/'preregistration.json')
    assert plan['candidateCount']==1 and plan['steps']==150
    if (DEST/'CURRENT').exists() or (DEST/'model.safetensors').exists():
        raise ValueError('Existing checkpoint preserved; never silently repeat or reset a fitted candidate')
    for name,expected in plan['inputHashes'].items():assert digest(OUT/name)==expected
    sequence=read(OUT/'clean-pilot-hard-negative/sequence.json')
    assert hashlib.sha256(json.dumps(sequence,sort_keys=True).encode()).hexdigest()==plan['sampleSequenceSHA256']
    components=read(OUT/'source-negative-repair-probe.json')['components']
    original={r['sha256']:r for r in read(OUT/'inputs/original-reviewed-detector-data.json')['rows'] if r['split']=='train'}
    curated={r['sha256']:r for r in read(OUT/'inputs/train-data-engineering-reviewed-20261013.json')['rows'] if r['split']=='train'}
    supports={r['sha256']:r for r in read(OUT/'train-clean-support/manifest.json')['rows']}
    object_rows=[]
    for item in components:
        row=next(r for r in sequence if r['sha256']==item['sha256'] and r['rect']==item['selectedTile']['rect'])
        object_rows.append((item,row))
    with HeavyJobLease('CDC-acne-feature-learnability-150',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        import cv2
        import numpy as np
        import torch
        from safetensors.torch import load_file,save_file
        from yolox_p2 import build_yolox_p2_model
        from acne_objectness_features import install_objectness_features,configure_learnable,training_mode,frozen_hash,VERSION
        from acne_object_negatives import reviewed_object_negative_mask
        from focal_objectness_loss import SigmoidFocalObjectnessLoss
        from skin_models import _nms
        torch.set_num_threads(4);torch.manual_seed(plan['seed']);np.random.seed(plan['seed']);random.seed(plan['seed'])
        initial_path=OUT/'models/step0.safetensors';assert digest(initial_path)==plan['initialModelSHA256']
        net=build_yolox_p2_model();net.load_state_dict(load_file(str(initial_path)),strict=True);net.eval()
        verified_sources=set()
        current=None;image=None;mask=None;weight=None
        def tile_input(row,supervision=False):
            nonlocal current,image,mask,weight
            lease.check();s=row['sha256'];source=original[s]
            if current!=s:
                image=None;mask=None;weight=None;gc.collect();path=Path(source['absolutePath'])
                if s not in verified_sources:assert digest(path)==s;verified_sources.add(s)
                image=cv2.imread(str(path));assert image is not None
                support=None
                if s in supports:
                    support_path=OUT/'train-clean-support'/(s+'.png');assert digest(support_path)==supports[s]['maskSHA256'];support=cv2.imread(str(support_path),cv2.IMREAD_GRAYSCALE)
                mask,weight=strict_clean_mask(source,image,[r['box'] for r in curated[s]['annotations']],reviewed_support=support)
                current=s
            a,b,c,d=row['rect'];tile=np.full((384,384,3),114,np.uint8);patch=image[b:d,a:c];tile[:patch.shape[0],:patch.shape[1]]=patch
            x=torch.from_numpy(tile.transpose(2,0,1).copy()).float()[None]
            if not supervision:return x
            y=torch.zeros((1,max(1,len(row['boxes'])),5))
            for i,(bx,by,ex,ey) in enumerate(row['boxes']):y[0,i]=torch.tensor([0,(bx+ex)/2,(by+ey)/2,ex-bx,ey-by])
            return x,y,known_cells(mask,weight,row['rect'])
        # Baseline geometry, class probabilities and TRAIN matches before adding
        # a new branch; all samples are fixed before fitting, no held-out labels.
        probe_rows=[r for _,r in object_rows]+plan['positiveProbes']
        baseline_outputs=[]
        with torch.inference_mode():
            for row in probe_rows:baseline_outputs.append(net(tile_input(row))[0].clone())
        install_objectness_features(net);net.eval()
        parity=[]
        with torch.inference_mode():
            for row,before in zip(probe_rows,baseline_outputs):
                after=net(tile_input(row))[0];delta=float((before-after).abs().max());assert delta<=1e-6
                assert not net.head._objectness_feature_inputs
                parity.append(dict(sha256=row['sha256'],tile=row['rect'],maxOutputDelta=delta))
        names=configure_learnable(net);params=[p for n,p in net.named_parameters() if n in names];initial_frozen=frozen_hash(net,names)
        class_probs={}
        for level,module in enumerate(net.head.cls_preds):
            module.register_forward_hook(lambda _m,_a,output,level=level:class_probs.__setitem__(level,output.detach().sigmoid().flatten(2).permute(0,2,1).reshape(-1,1)))
        class ObjectAuditFocal(SigmoidFocalObjectnessLoss):
            def forward(self,logits,truth):
                self.object_terms=[];extra=torch.zeros_like(truth,dtype=torch.bool)
                for item,box in self.objects:
                    negative=torch.tensor([box],dtype=torch.float32)
                    raw=reviewed_object_negative_mask(self.decoded_boxes,negative,torch.empty((0,4)))
                    safe=reviewed_object_negative_mask(self.decoded_boxes,negative,self.protected_boxes)
                    active=safe&(truth==0);extra|=active
                    self.object_terms.append(dict(item=item,mask=active,rawCount=int(raw.sum()),blockedByProtection=int((raw&~safe).sum()),positiveAssignedExcluded=int((safe&(truth>0)).sum())))
                self.known=self.known|extra
                saved=self.boundary_weights;self.boundary_weights=torch.where(extra,torch.ones_like(saved),saved)
                result=super().forward(logits,truth)
                self.boundary_weights=saved
                denom=max(1,int((self.known&(truth==0)).sum()))
                cls=torch.cat([class_probs[k] for k in range(4)],dim=0)
                self.prediction=logits.detach().sigmoid();self.cls=cls;self.truth=truth.detach();self.extra=extra
                for term in self.object_terms:
                    term['loss']=(result*term['mask']).sum()*plan['negativeWeight']/denom
                assert not bool((extra&(truth>0)).any())
                return result
        focal=ObjectAuditFocal(alpha=.25,gamma=2);net.head.obj_focal_loss=focal
        def setup(row,cells):
            focal.known,focal.boundary_weights=cells
            a,b,_,_=row['rect'];focal.protected_boxes=torch.tensor(row['protectedBoxes'],dtype=torch.float32).reshape(-1,4)
            focal.objects=[]
            for item in components:
                if item['sha256']!=row['sha256']:continue
                x,y,ex,ey=item['box'];local=[x-a,y-b,ex-a,ey-b]
                if local in row['objectNegatives']:focal.objects.append((item,local))
        def gradient_proof(term):
            grads=torch.autograd.grad(term['loss']/plan['accumulation'],params,retain_graph=True,allow_unused=True)
            per={n:dict(l2=float(g.detach().norm()),maxAbs=float(g.detach().abs().max())) for n,g in zip(names,grads) if g is not None}
            indices=torch.where(term['mask'][:,0])[0]
            anchors=[dict(anchor=int(i),decodedTileBox=focal.decoded_boxes[i].tolist(),objectness=float(focal.prediction[i]),classProbability=float(focal.cls[i]),objTimesCls=float(focal.prediction[i]*focal.cls[i])) for i in indices]
            feature_norm=sum(v['l2'] for n,v in per.items() if n.startswith('head.obj_convs.'))
            prediction_norm=sum(v['l2'] for n,v in per.items() if n.startswith('head.obj_preds.'))
            return dict(sourceAnnotationId=term['item']['sourceAnnotationId'],sha256=term['item']['sha256'],sourceBox=term['item']['box'],rawMatchingAnchors=term['rawCount'],blockedByProtection=term['blockedByProtection'],assignedPositivesExcluded=term['positiveAssignedExcluded'],negativeAnchors=len(anchors),normalizedNegativeLoss=float(term['loss'].detach()),gradientIncludesAccumulationDivision=plan['accumulation'],parameterGradients=per,featureGradientL2Sum=feature_norm,predictionGradientL2Sum=prediction_norm,anchors=anchors)
        path_proofs=[]
        # Five separate backward-path checks, without any parameter/optimizer
        # update. This is not an additional fit or a repeated previous pilot.
        for item,row in object_rows:
            x,y,cells=tile_input(row,True);setup(row,cells);net(x,y)
            term=next(t for t in focal.object_terms if t['item']['sourceAnnotationId']==item['sourceAnnotationId'])
            proof=gradient_proof(term);proof['tile']=row['rect']
            assert proof['negativeAnchors']>0 and proof['normalizedNegativeLoss']>0 and proof['featureGradientL2Sum']>0 and proof['predictionGradientL2Sum']>0
            path_proofs.append(proof);net.zero_grad(set_to_none=True)
        assert frozen_hash(net,names)==initial_frozen
        (DEST/'prefit-learning-path.json').write_text(json.dumps(dict(noOptimizerUpdate=True,parity=parity,objects=path_proofs,trainable=names,frozenSHA256=initial_frozen),indent=2),encoding='utf8')
        torch.manual_seed(plan['seed']);np.random.seed(plan['seed']);random.seed(plan['seed'])
        opt=torch.optim.AdamW(params,lr=plan['learningRate'],weight_decay=plan['weightDecay'])
        sched=torch.optim.lr_scheduler.LambdaLR(opt,lambda step:(step+1)/30 if step<30 else .5*(1+math.cos(math.pi*(step-30)/120)))
        baseline_matches=None
        def measure(step):
            nonlocal baseline_matches
            net.eval();objects=[];positives=[];now_matches=set();geometry_delta=0.;class_delta=0.
            with torch.inference_mode():
                for index,(row,before) in enumerate(zip(probe_rows,baseline_outputs)):
                    pred=net(tile_input(row))[0]
                    geometry_delta=max(geometry_delta,float((pred[:,:4]-before[:,:4]).abs().max()));class_delta=max(class_delta,float((pred[:,5:]-before[:,5:]).abs().max()))
                    assert geometry_delta<=1e-6 and class_delta<=1e-6
                    if index<5:
                        item=components[index];a,b,_,_=row['rect'];x,y,ex,ey=item['box'];known=reviewed_object_negative_mask(pred[:,:4],torch.tensor([[x-a,y-b,ex-a,ey-b]]),torch.tensor(row['protectedBoxes']).reshape(-1,4))[:,0];ids=torch.where(known)[0];scores=pred[:,4]*pred[:,5];best=int(ids[torch.argmax(scores[ids])]);objects.append(dict(sourceAnnotationId=item['sourceAnnotationId'],sha256=item['sha256'],sourceBox=item['box'],tile=row['rect'],matchingAnchors=len(ids),aboveThresholdAnchors=int((scores[ids]>=.30).sum()),anchor=best,objectness=float(pred[best,4]),classProbability=float(pred[best,5]),objTimesCls=float(scores[best])))
                    candidates=[]
                    for v in pred[(pred[:,4]*pred[:,5])>=.30].tolist():
                        cx,cy,w,h,obj,cls=v;candidates.append([max(0,cx-w/2),max(0,cy-h/2),min(row['rect'][2]-row['rect'][0],cx+w/2),min(row['rect'][3]-row['rect'][1],cy+h/2),obj*cls])
                    candidates=[v for v in candidates if v[2]>v[0] and v[3]>v[1]]
                    boxes=_nms(candidates,threshold=.30) if candidates else []
                    pairs=one_to_one(row['boxes'],[v[:4] for v in boxes]);key=row['sha256']+':'+','.join(map(str,row['rect']))
                    for t,_,_ in pairs:now_matches.add((key,t))
                    positives.append(dict(sha256=row['sha256'],tile=row['rect'],targets=len(row['boxes']),pairs=pairs))
            if baseline_matches is None:baseline_matches=now_matches
            result=dict(step=step,objects=objects,positiveProbeTiles=positives,positiveTargets=sum(p['targets'] for p in positives),positiveMatched=sum(len(p['pairs']) for p in positives),lostBaselineSourceTargets=sorted(baseline_matches-now_matches),gainedSourceTargets=sorted(now_matches-baseline_matches),maxGeometryDelta=geometry_delta,maxClassProbabilityDelta=class_delta,frozenStateUnchanged=frozen_hash(net,names)==initial_frozen)
            assert result['frozenStateUnchanged'];(DEST/f'measure-step-{step:06d}.json').write_text(json.dumps(result,indent=2),encoding='utf8');training_mode(net)
            print(json.dumps(dict(measure=step,objectMaxScores=[round(o['objTimesCls'],6) for o in objects],positiveMatched=result['positiveMatched'],positiveTargets=result['positiveTargets'],lost=len(result['lostBaselineSourceTargets']))),flush=True)
            return result
        def save_checkpoint(step,logs,ledger,updates):
            folder=DEST/f'checkpoint-step-{step:06d}';folder.mkdir(exist_ok=False)
            save_file({k:v.detach().contiguous() for k,v in net.state_dict().items()},str(folder/'model.safetensors'))
            tensors={'torch_rng':torch.get_rng_state()};states={};state=opt.state_dict()
            for i,values in state['state'].items():
                states[str(i)]={}
                for k,v in values.items():
                    if torch.is_tensor(v):key=f'{i}.{k}';tensors[key]=v;states[str(i)][k]={'tensor':key}
                    else:states[str(i)][k]=v
            save_file(tensors,str(folder/'optimizer-rng.safetensors'))
            state_payload=dict(step=step,optimizerState=states,paramGroups=state['param_groups'],scheduler=sched.state_dict(),pythonRNG=random.getstate(),numpyRNG=[np.random.get_state()[0],np.random.get_state()[1].tolist(),*np.random.get_state()[2:]],sampleSequenceSHA256=plan['sampleSequenceSHA256'],preregistrationSHA256=digest(DEST/'preregistration.json'),graphVersion=VERSION,trainable=names,logs=logs,perObjectExposure=ledger,firstActualUpdates=updates)
            (folder/'state.json').write_text(json.dumps(state_payload),encoding='utf8')
            loaded=load_file(str(folder/'model.safetensors'));assert set(loaded)==set(net.state_dict());del loaded
            loaded=load_file(str(folder/'optimizer-rng.safetensors'));assert 'torch_rng' in loaded;del loaded
            hashes={name:digest(folder/name) for name in ['model.safetensors','optimizer-rng.safetensors','state.json']};(folder/'hashes.json').write_text(json.dumps(hashes),encoding='utf8')
            temp=DEST/'CURRENT.tmp';temp.write_text(json.dumps(dict(step=step,directory=folder.name,hashes=hashes)),encoding='utf8');temp.replace(DEST/'CURRENT')
        measure(0);started=time.monotonic();logs=[];updates=[];seen=set();ledger={str(c['sourceAnnotationId']):dict(tileExposures=0,negativeAnchorExposures=0,normalizedNegativeLossSum=0.,blockedAnchorExposures=0,assignedPositiveExclusions=0,zeroAllowedExposures=0) for c in components}
        for step in range(150):
            lease.check();opt.zero_grad(set_to_none=True);total=0.;pending=[]
            for row in sequence[step*4:(step+1)*4]:
                x,y,cells=tile_input(row,True);setup(row,cells);loss=net(x,y)['total_loss'];assert torch.isfinite(loss)
                for term in focal.object_terms:
                    key=str(term['item']['sourceAnnotationId']);entry=ledger[key];count=int(term['mask'].sum());entry['tileExposures']+=1;entry['negativeAnchorExposures']+=count;entry['normalizedNegativeLossSum']+=float(term['loss'].detach());entry['blockedAnchorExposures']+=term['blockedByProtection'];entry['assignedPositiveExclusions']+=term['positiveAssignedExcluded'];entry['zeroAllowedExposures']+=count==0
                    if key not in seen and count:
                        proof=gradient_proof(term);proof.update(tile=row['rect'],optimizerStep=step+1)
                        assert proof['featureGradientL2Sum']>0 and proof['predictionGradientL2Sum']>0
                        pending.append((proof,row));seen.add(key)
                (loss/4).backward();total+=float(loss.detach())/4
            before_update={n:p.detach().clone() for n,p in net.named_parameters() if n in names} if pending else None
            norm=float(torch.nn.utils.clip_grad_norm_(params,plan['gradientClipNorm']));opt.step();sched.step()
            if pending:
                deltas={n:float((p.detach()-before_update[n]).norm()) for n,p in net.named_parameters() if n in names}
                net.eval()
                with torch.inference_mode():
                    for proof,row in pending:
                        pred=net(tile_input(row))[0];proof['parameterUpdateL2']=deltas;proof['gradientNormBeforeClip']=norm;proof['afterActualOptimizerUpdate']=[dict(anchor=v['anchor'],objectness=float(pred[v['anchor'],4]),classProbability=float(pred[v['anchor'],5]),objTimesCls=float(pred[v['anchor'],4]*pred[v['anchor'],5])) for v in proof['anchors']];updates.append(proof)
                training_mode(net);del before_update
            logs.append(dict(step=step+1,loss=total,gradientNormBeforeClip=norm,elapsedSeconds=time.monotonic()-started))
            if step+1 in plan['measureSteps']:measure(step+1)
            if (step+1)%25==0:save_checkpoint(step+1,logs,ledger,updates)
            if (step+1)%10==0:print(json.dumps(logs[-1]),flush=True)
        assert len(seen)==5 and all(v['negativeAnchorExposures']>0 for v in ledger.values())
        assert frozen_hash(net,names)==initial_frozen
        import shutil
        final=DEST/'checkpoint-step-000150'
        for name in ['model.safetensors','optimizer-rng.safetensors','state.json']:shutil.copyfile(final/name,DEST/name)
        receipt=dict(graphVersion=VERSION,steps=150,initialModelSHA256=plan['initialModelSHA256'],modelSHA256=digest(DEST/'model.safetensors'),preregistrationSHA256=digest(DEST/'preregistration.json'),sampleSequenceSHA256=plan['sampleSequenceSHA256'],trainable=names,frozenSHA256=initial_frozen,frozenStateUnchanged=frozen_hash(net,names)==initial_frozen,perObjectExposure=ledger,firstActualUpdates=updates,prefitProofSHA256=digest(DEST/'prefit-learning-path.json'),resource=lease.receipt(),productionActive=False)
        (DEST/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in receipt.items() if k not in ['firstActualUpdates','resource']}),flush=True)


if __name__=='__main__':main()
