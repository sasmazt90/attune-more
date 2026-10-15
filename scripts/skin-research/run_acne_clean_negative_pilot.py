"""Two sequential bounded objectness-only arms, never the failed IoU/GIoU run.

Only variable: reviewed source non-Pimple object negative supervision.
Both arms share frozen Step-0 geometry/class heads, original TRAIN positives,
strict clean review masks, exact source/tile order, seed and schedule.
"""
import argparse,gc,hashlib,json,math,random,time
from pathlib import Path
from acne_takeover_support import ROOT,AG,OUT,read,digest,strict_clean_mask,known_cells
from heavy_job_lease import HeavyJobLease

STEP0=OUT/'models/step0.safetensors'
STEP0_HASH='18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--arm',choices=['control','hard-negative'],required=True);parser.add_argument('--steps',type=int,default=150);args=parser.parse_args()
    if args.steps!=150:raise ValueError('Preregistered 150 steps; no adaptive parameter search')
    target=OUT/('clean-pilot-'+args.arm)
    if (target/'model.safetensors').exists():raise ValueError('Completed arm preserved; refuse duplicate training')
    if (target/'CURRENT').exists():raise ValueError('Partial immutable checkpoint preserved; explicit state validation/resume required, never silently restart')
    prereg=read(OUT/'pilot-preregistration.json');assert prereg['steps']==args.steps
    baseline=read(OUT/'evaluation-step0/summary.json')
    assert baseline['modelSHA256']==STEP0_HASH
    assert baseline['tilingContract']=='current-skin-models-photo-input-camera-crop-v1'
    repair=read(OUT/'source-negative-repair-probe.json');review=read(OUT/'train-mole-label-review.json')
    assert repair['trainOnly'] and repair['eligibleComponents']>0 and review['reviewStatus']=='REVIEWED'
    reviewed=[r for r in repair['components'] if r['selectedTile'] and r['selectedTile']['aboveThresholdAnchors']]
    support_manifest=read(OUT/'train-clean-support/manifest.json')
    support_rows={r['sha256']:r for r in support_manifest['rows']}
    data=read(OUT/'inputs/original-reviewed-detector-data.json');original={r['sha256']:r for r in data['rows'] if r['split']=='train'}
    curated=read(OUT/'inputs/train-data-engineering-reviewed-20261013.json');curated={r['sha256']:r for r in curated['rows'] if r['split']=='train'}
    cohort=read(OUT/'inputs/controlled_train_cohort.json');tiles=cohort['pilotTrainTiles'];rng=random.Random(20261015);order=list(range(len(tiles)));rng.shuffle(order);order=order[:args.steps*4];assert len(order)==args.steps*4
    # Validation, Scope B, held-out groups, engineering pseudo positives excluded.
    heldout=set(cohort['pilotControlShas']);train=set(cohort['pilotTrainShas']);assert not heldout&train
    assert not {original[s]['group'] for s in train}&{original[s]['group'] for s in heldout}
    paired=[];ordinary=iter(order)
    for i in range(args.steps*4):
        if i%10==9:
            item=reviewed[(i//10)%len(reviewed)];paired.append(dict(imageSha256=item['sha256'],rect=item['selectedTile']['rect'],purpose='reviewed-source-negative-probe'))
        else:paired.append(tiles[next(ordinary)])
    manifest=[]
    for tile in paired:
        s=tile['imageSha256'];assert s in train and s in original
        r=original[s];a,b,c,d=tile['rect'];boxes=[]
        for ann in r.get('annotations',[]):
            if ann.get('classId')!=0:continue
            x,y,ex,ey=ann['box'];cl=[max(x,a),max(y,b),min(ex,c),min(ey,d)]
            if cl[2]-cl[0]>=2 and cl[3]-cl[1]>=2 and (cl[2]-cl[0])*(cl[3]-cl[1])>=.7*(ex-x)*(ey-y):boxes.append([cl[0]-a,cl[1]-b,cl[2]-a,cl[3]-b])
        nonpimple=[]
        for item in reviewed:
            if item['sha256']!=s:continue
            x,y,ex,ey=item['box']
            if a<=x<ex<=c and b<=y<ey<=d:nonpimple.append([x-a,y-b,ex-a,ey-b])
        overridden={v for item in reviewed if item['sha256']==s for v in item['overriddenPseudoSourceIds']}
        protected=[z['box'] for z in r['annotations']]+[z['box'] for z in curated[s].get('annotations',[]) if z.get('reviewStatus')=='engineering_review' and z.get('sourceId') not in overridden]
        protected=[[x-a-16,y-b-16,ex-a+16,ey-b+16] for x,y,ex,ey in protected]
        manifest.append(dict(sha256=s,rect=tile['rect'],boxes=boxes,objectNegatives=nonpimple,protectedBoxes=protected,group=r['group'],purpose=tile.get('purpose','original-train-sequence')))
    sequence_hash=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest();target.mkdir(parents=True,exist_ok=True)
    (target/'sequence.json').write_text(json.dumps(manifest),'utf8')
    # Small frozen-backbone microbatches, accumulation=4. Hard system reserve and
    # both atomic ownership leases remain unchanged. No all-image/tile preload.
    with HeavyJobLease('CDC-acne-clean-'+args.arm,peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        import cv2,numpy as np,torch
        from safetensors.torch import load_file,save_file
        from yolox_p2 import build_yolox_p2_model
        from focal_objectness_loss import SigmoidFocalObjectnessLoss
        from acne_object_negatives import reviewed_object_negative_mask
        torch.set_num_threads(4);torch.manual_seed(20261015);np.random.seed(20261015);random.seed(20261015)
        assert digest(STEP0)==STEP0_HASH
        net=build_yolox_p2_model();net.load_state_dict(load_file(str(STEP0)),strict=True)
        def frozen_hash():
            h=hashlib.sha256()
            for name,tensor in sorted(net.state_dict().items()):
                if not name.startswith('head.obj_preds.'):h.update(name.encode());h.update(tensor.detach().cpu().numpy().tobytes())
            return h.hexdigest()
        initial_frozen=frozen_hash()
        for p in net.parameters():p.requires_grad_(False)
        names=[]
        for name,p in net.named_parameters():
            if name.startswith('head.obj_preds.'):
                p.requires_grad_(True);names.append(name)
        net.train()
        for module in net.modules():
            if isinstance(module,torch.nn.BatchNorm2d):module.eval()
        class CleanFocal(SigmoidFocalObjectnessLoss):
            def forward(self,logits,truth):
                saved=self.boundary_weights
                extra=reviewed_object_negative_mask(self.decoded_boxes,self.negative_boxes,self.protected_boxes)&(truth==0)
                self.extra_count=0;self.extra_loss=0.
                if args.arm=='hard-negative':
                    self.known=self.known|extra;self.boundary_weights=torch.where(extra,torch.ones_like(saved),saved);self.extra_count=int(extra.sum())
                result=super().forward(logits,truth)
                if args.arm=='hard-negative':self.extra_loss=float((result*extra).sum().detach())
                self.boundary_weights=saved;return result
        focal=CleanFocal(alpha=.25,gamma=2);net.head.obj_focal_loss=focal
        probe=torch.tensor([[1.],[1.],[1.]],requires_grad=True);probe_truth=torch.tensor([[1.],[0.],[0.]])
        focal.known=torch.tensor([[False],[True],[False]]);focal.boundary_weights=torch.ones_like(probe);focal.decoded_boxes=torch.zeros((3,4));focal.negative_boxes=torch.empty((0,4));focal.protected_boxes=torch.empty((0,4));focal(probe,probe_truth).sum().backward()
        assert probe.grad[2].item()==0 and probe.grad[0].item()!=0 and probe.grad[1].item()!=0
        opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=3e-5)
        sched=torch.optim.lr_scheduler.LambdaLR(opt,lambda step:(step+1)/30 if step<30 else .5*(1+math.cos(math.pi*(step-30)/120)))
        def save_complete_checkpoint(directory,step):
            directory.mkdir(exist_ok=False)
            save_file({k:v.contiguous() for k,v in net.state_dict().items()},str(directory/'model.safetensors'))
            state=opt.state_dict();tensors={};states={}
            for i,values in state['state'].items():
                states[str(i)]={}
                for k,v in values.items():
                    if torch.is_tensor(v):name=f'{i}.{k}';tensors[name]=v;states[str(i)][k]={'tensor':name}
                    else:states[str(i)][k]=v
            tensors['torch_rng']=torch.get_rng_state();save_file(tensors,str(directory/'optimizer-rng.safetensors'))
            payload=dict(step=step,optimizerState=states,paramGroups=state['param_groups'],scheduler=sched.state_dict(),pythonRNG=random.getstate(),numpyRNG=[np.random.get_state()[0],np.random.get_state()[1].tolist(),*np.random.get_state()[2:]],seed=20261015,sampleSequenceSHA256=sequence_hash)
            (directory/'state.json').write_text(json.dumps(payload),'utf8')
            # Verify all tensors load and all file bytes before publishing CURRENT.
            reloaded=load_file(str(directory/'model.safetensors'));assert set(reloaded)==set(net.state_dict());del reloaded
            optimizer_reload=load_file(str(directory/'optimizer-rng.safetensors'));assert 'torch_rng' in optimizer_reload;del optimizer_reload
            receipt={name:digest(directory/name) for name in ['model.safetensors','optimizer-rng.safetensors','state.json']};(directory/'hashes.json').write_text(json.dumps(receipt),'utf8')
            tmp=target/'CURRENT.tmp';tmp.write_text(json.dumps(dict(directory=directory.name,step=step,hashes=receipt)),'utf8');tmp.replace(target/'CURRENT')
        logs=[];current=None;image=None;mask=None;weight=None;started=time.monotonic();known_total=0;extra_total=0
        for step in range(args.steps):
            lease.check();opt.zero_grad(set_to_none=True);tot=0;negative=0;positive=0;extra_count=0;extra_loss=0.
            for tile in manifest[step*4:(step+1)*4]:
                lease.check();s=tile['sha256'];row=original[s]
                if current!=s:
                    image=None;mask=None;weight=None;gc.collect();p=Path(row['absolutePath']);assert digest(p)==s;image=cv2.imread(str(p));assert image is not None
                    holes=[a['box'] for a in curated[s].get('annotations',[])];support=None
                    if s in support_rows:
                        support_path=OUT/'train-clean-support'/(s+'.png');assert digest(support_path)==support_rows[s]['maskSHA256'];support=cv2.imread(str(support_path),cv2.IMREAD_GRAYSCALE)
                    mask,weight=strict_clean_mask(row,image,holes,reviewed_support=support);current=s
                a,b,c,d=tile['rect'];x=np.full((384,384,3),114,np.uint8);patch=image[b:d,a:c];x[:patch.shape[0],:patch.shape[1]]=patch
                focal.known,focal.boundary_weights=known_cells(mask,weight,tile['rect']);known_total+=int(focal.known.sum())
                focal.negative_boxes=torch.tensor(tile['objectNegatives'],dtype=torch.float32).reshape(-1,4);focal.protected_boxes=torch.tensor(tile['protectedBoxes'],dtype=torch.float32).reshape(-1,4)
                y=torch.zeros((1,max(1,len(tile['boxes'])),5))
                for i,(bx,by,ex,ey) in enumerate(tile['boxes']):y[0,i]=torch.tensor([0,(bx+ex)/2,(by+ey)/2,ex-bx,ey-by])
                loss=net(torch.from_numpy(x.transpose(2,0,1).copy()).float()[None],y)['total_loss'];assert torch.isfinite(loss);(loss/4).backward();tot+=float(loss.detach())/4;negative+=focal.last_metrics['raw_neg_obj_loss'];positive+=focal.last_metrics['num_pos_anchors'];extra_count+=focal.extra_count;extra_loss+=focal.extra_loss
            torch.nn.utils.clip_grad_norm_([p for p in net.parameters() if p.requires_grad],5);opt.step();sched.step()
            extra_total+=extra_count;row=dict(step=step+1,totalLoss=tot,negativeLoss=negative,positiveAnchors=positive,repairedNegativeAnchors=extra_count,repairedNegativeLoss=extra_loss,elapsedSeconds=time.monotonic()-started);logs.append(row)
            if (step+1)%25==0:save_complete_checkpoint(target/f'checkpoint-step-{step+1:06d}',step+1)
            if (step+1)%10==0 or step==0:
                print(json.dumps(dict(arm=args.arm,**row)),flush=True);(target/'progress.json').write_text(json.dumps(row),'utf8')
        lease.check();assert known_total>0
        if args.arm=='hard-negative':assert extra_total>0,'No source-backed repair supervision applied'
        assert frozen_hash()==initial_frozen,'Frozen geometry/class/backbone changed'
        # Final aliases copied from the fully verified immutable generation.
        import shutil
        final=target/f'checkpoint-step-{args.steps:06d}'
        for name in ['model.safetensors','optimizer-rng.safetensors','state.json']:shutil.copyfile(final/name,target/name)
        receipt=dict(arm=args.arm,method='reviewed-source-nonpimple-object-supervision-repair-v3',steps=args.steps,initialWeightsSHA256=STEP0_HASH,checkpointSHA256=digest(target/'model.safetensors'),sampleSequenceSHA256=sequence_hash,onlyTrainableParameters=names,frozenGeometryClassBackboneSHA256=initial_frozen,frozenStateUnchanged=True,unknownGradientZeroVerified=True,knownNegativeAnchorExposures=known_total,repairedNegativeAnchorExposures=extra_total,logs=logs,resource=lease.receipt(),productionActivation=False)
        (target/'receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps({k:v for k,v in receipt.items() if k not in ['logs','resource']}),flush=True)

if __name__=='__main__':main()
