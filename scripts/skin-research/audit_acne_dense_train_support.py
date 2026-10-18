"""Dense TRAIN hard-background audit, distinct from confidence>=.30 product FP.

Inspect the actual sampled TRAIN grids and gradients. Low-score diagnostics never
enter product NMS or become positive/pseudo labels. All masks are existing
criterion-specific reviewed clean negatives; no validation photograph is loaded.
"""
import json,math
from pathlib import Path
from acne_takeover_support import ROOT,OUT,read,digest,strict_clean_mask,known_cells
from heavy_job_lease import HeavyJobLease
STEP0_HASH='18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'

def main():
    original=read(OUT/'inputs/original-reviewed-detector-data.json');rows={r['sha256']:r for r in original['rows'] if r['split']=='train'};cohort=read(OUT/'inputs/controlled_train_cohort.json');allowed=set(cohort['pilotTrainShas'])
    supports={r['sha256']:r for r in read(OUT/'train-clean-support/manifest.json')['rows']}
    with HeavyJobLease('CDC-acne-actual-train-dense-gradient-audit',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        import cv2,numpy as np,torch
        from PIL import Image,ImageDraw
        from safetensors.torch import load_file
        from yolox_p2 import build_yolox_p2_model
        from focal_objectness_loss import SigmoidFocalObjectnessLoss
        torch.set_num_threads(4);path=OUT/'models/step0.safetensors';assert digest(path)==STEP0_HASH;net=build_yolox_p2_model();net.load_state_dict(load_file(str(path)),strict=True);net.eval()
        order=np.arange(len(cohort['pilotTrainTiles']));np.random.RandomState(20261015).shuffle(order);selected=set(order[:600].tolist());records=[];all_tiles=[];shown=0;shown_sources=set();board=Image.new('RGB',(1000,800),'#222');draw=ImageDraw.Draw(board)
        current=None;image=None;mask=None;weight=None
        for ti,tile in enumerate(cohort['pilotTrainTiles']):
            s=tile['imageSha256'];r=rows[s]
            if ti not in selected or s not in allowed or r.get('annotations') or not r.get('negativeROI'):continue
            lease.check()
            if current!=s:
                image=cv2.imread(r['absolutePath']);assert image is not None and digest(Path(r['absolutePath']))==s;support_path=OUT/'train-clean-support'/(s+'.png');assert digest(support_path)==supports[s]['maskSHA256'];support=cv2.imread(str(support_path),cv2.IMREAD_GRAYSCALE);mask,weight=strict_clean_mask(r,image,reviewed_support=support);current=s
            a,b,c,d=tile['rect'];x=np.full((384,384,3),114,np.uint8);patch=image[b:d,a:c];x[:patch.shape[0],:patch.shape[1]]=patch
            known,boundary=known_cells(mask,weight,tile['rect'])
            if not known.any():continue
            with torch.inference_mode():pred=net(torch.from_numpy(x.transpose(2,0,1).copy()).float()[None])[0].clone()
            reachable=known&(pred[:,5:6]>=.30)
            if not reachable.any():continue
            # Detach fresh normal tensors: autograd tests just loss-mask behavior,
            # not a model training step. No weights/optimizer are changed.
            logits=torch.logit(pred[:,4].clone().clamp(1e-7,1-1e-7)).reshape(-1,1).requires_grad_();truth=torch.zeros_like(logits);fl=SigmoidFocalObjectnessLoss();fl.known=reachable;fl.boundary_weights=boundary;loss=fl(logits,truth);normalizer=max(1,int(reachable.sum()));(loss.sum()/normalizer*20).backward()
            assert (logits.grad[~reachable]==0).all();ids=torch.where(reachable[:,0])[0];ids=ids[torch.argsort(pred[ids,4]*pred[ids,5],descending=True)]
            emitted=[]
            for index in ids.tolist():
                cx,cy,bw,bh,obj,cls=pred[index].tolist();box=[max(a,cx+a-bw/2),max(b,cy+b-bh/2),min(c,cx+a+bw/2),min(d,cy+b+bh/2)];xx,yy,ex,ey=[int(round(v)) for v in box]
                if ex<=xx or ey<=yy:continue
                clean=mask[yy:ey,xx:ex]
                if not clean.size or clean.mean()<.8:continue
                center=[(xx+ex)/2,(yy+ey)/2]
                if any(math.dist(center,p)<24 for p in emitted):continue
                emitted.append(center);record=dict(sha256=s,group=r['group'],tileIndex=ti,tileRect=tile['rect'],anchor=index,box=box,objectness=obj,classProbability=cls,confidence=obj*cls,known=True,boundaryWeight=float(boundary[index]),normalizedObjectnessGradient=float(logits.grad[index]),cleanBoxAreaFraction=float(clean.mean()),selectedInOld150=True,currentProductFalsePositive=obj*cls>=.30)
                records.append(record)
                if shown<12 and s not in shown_sources:
                    im=Image.fromarray(image[:,:,::-1]);px,py=center;crop=im.crop((int(px-40),int(py-40),int(px+40),int(py+40))).resize((200,200));left=(shown%4)*250;top=(shown//4)*265;board.paste(crop,(left,top+25));draw.rectangle((left+100+(xx-px)*2.5,top+125+(yy-py)*2.5,left+100+(ex-px)*2.5,top+125+(ey-py)*2.5),outline='red',width=2);draw.text((left,top),s[:8]+' obj='+str(round(obj,4)),fill='white');draw.text((left,top+230),'score='+format(obj*cls,'.3g')+' grad='+format(float(logits.grad[index]),'.2e'),fill='white');shown+=1;shown_sources.add(s)
                if len(emitted)>=3:break
            all_tiles.append(dict(tileIndex=ti,sha256=s,knownAnchors=int(known.sum()),unknownGradientZero=True,selectedDiagnostics=len(emitted)))
        board.save(OUT/'train-dense-hard-background-board.png');report=dict(trainOnly=True,source='actual sampled reviewed-negative TRAIN tiles; Step 0',modelSHA256=STEP0_HASH,productConfidenceThresholdUnchanged=.30,verifiedCleanFalseCandidates=sum(r['currentProductFalsePositive'] for r in records),denseHardNegativeDiagnostics=len(records),reviewedDenseHardNegatives=0,visualReview='PENDING',records=records,tiles=all_tiles,allDiagnosticAnchorsAlreadySupervised=all(r['normalizedObjectnessGradient']!=0 for r in records),heldoutOrScopeBUsedForMining=False,resource=lease.receipt(),interpretation='Below-threshold hard background is not reported as product FP. Dense mining tests mean-loss dilution; missing supervision is not asserted without a zero gradient.')
        (OUT/'train-dense-negative-audit.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items() if k not in ['records','tiles','resource']}),flush=True)

if __name__=='__main__':main()
