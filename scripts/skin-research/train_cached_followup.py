"""Finite CPU detector-head adaptation with transactional exact local resume.

Frozen pretrained features are computed once. This is head-only adaptation,
not full-backbone convergence. Old final groups are never used or re-opened.
Only trusted local safetensors/JSON checkpoints are loaded, never pickle.
"""
import argparse, collections, hashlib, json, random, time, types
from pathlib import Path
import numpy as np, torch
from safetensors.torch import save_file, load_file
from train_focused_local import setup, acne_tiles, tile_image, detector, predict, detection_metrics, yolo_batch, OUT as OLD
from diagnose_followup import NEW, write
from fast_detection_metrics import detection_metrics
from torchvision.ops import nms

def bounded_faster_prediction(net,rows,folder,state,budget,save):
    """Resume validation tiles as well as gradient steps; cache frozen FP32 ROI.

    Exactly the normal transform/RPN/ROI postprocess. No ground truth proposals
    are inserted in validation. Float32 features avoid score-boundary drift.
    """
    tiles=acne_tiles(rows,training=False);net.eval();save()
    signature=digest({'step':state['step'],'modelSHA256':state['modelSHA256'],'rows':[{'sha':r['sha256'],'crop':r['crop']} for r in rows]})
    progress_file=folder/f'validation-{signature}.json';cache=folder/'validation-cache';cache.mkdir(exist_ok=True)
    progress=json.loads(progress_file.read_text()) if progress_file.exists() else dict(signature=signature,cursor=0,by={})
    assert progress['signature']==signature
    for i in range(progress['cursor'],len(tiles)):
        if budget():write(str(progress_file.relative_to(NEW)),progress);return None
        tile=tiles[i];file=cache/f'{i:05d}.npz';key=digest({'identity':state['identity'],'sha':tile['row']['sha256'],'rect':tile['rect']})
        with torch.inference_mode():
            if file.exists():
                with np.load(file,allow_pickle=False) as cached:
                    assert str(cached['identity'])==key
                    features=torch.from_numpy(cached['features'].copy());proposals=[torch.from_numpy(cached['proposals'].copy())];sizes=[tuple(cached['imageSize'].tolist())]
            else:
                source=tile_image(tile)[[2,1,0]]/255;images,_=net.transform([source]);backbone=net.backbone(images.tensors);proposals,_=net.rpn(images,backbone);sizes=images.image_sizes;features=net.roi_heads.box_head(net.roi_heads.box_roi_pool(backbone,proposals,sizes))
                np.savez(file,features=features.numpy(),proposals=proposals[0].numpy(),imageSize=np.array(sizes[0]),identity=np.array(key))
            scores,deltas=net.roi_heads.box_predictor(features);boxes,scores,_=net.roi_heads.postprocess_detections(scores,deltas,proposals,sizes)
            ps=[[*b,float(s)] for b,s in zip(boxes[0].numpy(),scores[0].numpy()) if s>=.01]
        a,b,c,d=tile['rect'];dest=progress['by'].setdefault(tile['row']['sha256'],[])
        for x,y,ex,ey,score in ps:dest.append([float(max(a,x+a)),float(max(b,y+b)),float(min(c,ex+a)),float(min(d,ey+b)),float(score)])
        progress['cursor']=i+1
        if (i+1)%25==0:write(str(progress_file.relative_to(NEW)),progress);save();print('VALIDATION',i+1,len(tiles),flush=True)
    write(str(progress_file.relative_to(NEW)),progress);result=[]
    for row in rows:
        arr=np.array(progress['by'].get(row['sha256'],[]),np.float32).reshape(-1,5)
        if len(arr):
            arr=arr[(arr[:,2]>arr[:,0])&(arr[:,3]>arr[:,1])];keep=nms(torch.tensor(arr[:,:4]),torch.tensor(arr[:,4]),.3).numpy();arr=arr[keep]
        result.append(arr.tolist())
    return result

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
from training_checkpoint import checkpoint,resume

def yolo_features(net,tile):
    with torch.no_grad():
        neck=net.backbone(tile_image(tile)[None]);result={}
        for k,x in enumerate(neck):
            x=net.head.stems[k](x);result[f'cls{k}']=net.head.cls_convs[k](x)[0].numpy();result[f'reg{k}']=net.head.reg_convs[k](x)[0].numpy()
    return result
def yolo_loss(net,files,items):
    head=net.head;out=[];xs=[];ys=[];ss=[]
    for k,stride in enumerate(head.strides):
        cls=torch.stack([torch.from_numpy(f[f'cls{k}'].astype(np.float32)) for f in files]);reg=torch.stack([torch.from_numpy(f[f'reg{k}'].astype(np.float32)) for f in files])
        value=torch.cat([head.reg_preds[k](reg),head.obj_preds[k](reg),head.cls_preds[k](cls)],1)
        value,grid=head.get_output_and_grid(value,k,stride,cls.type());out.append(value);xs.append(grid[:,:,0]);ys.append(grid[:,:,1]);ss.append(torch.full((1,grid.shape[1]),stride,dtype=torch.float32))
    target=torch.zeros((len(items),max(len(t['boxes']) for t in items),5))
    for i,t in enumerate(items):
        for j,(a,b,c,d) in enumerate(t['boxes']):target[i,j]=torch.tensor([0,(a+c)/2,(b+d)/2,c-a,d-b])
    values=head.get_losses(None,xs,ys,ss,target,torch.cat(out,1),[],torch.float32)
    return values[0],dict(zip(['iouWeighted','objectness','classification','l1','foregroundPerGT'],[float(v.detach()) if torch.is_tensor(v) else float(v) for v in values[1:]]))
def faster_features(net,tile):
    from torchvision.models.detection.roi_heads import fastrcnn_loss
    x=tile_image(tile)[[2,1,0]]/255;target={'boxes':torch.tensor(tile['boxes'],dtype=torch.float32),'labels':torch.ones(len(tile['boxes']),dtype=torch.int64)}
    with torch.no_grad():
        imgs,targets=net.transform([x],[target]);features=net.backbone(imgs.tensors);proposals,_=net.rpn(imgs,features)
        proposals,_,labels,regression=net.roi_heads.select_training_samples(proposals,targets)
        features=net.roi_heads.box_head(net.roi_heads.box_roi_pool(features,proposals,imgs.image_sizes))
    return dict(features=features.numpy(),labels=labels[0].numpy(),regression=regression[0].numpy())
def faster_loss(net,files,items):
    from torchvision.models.detection.roi_heads import fastrcnn_loss
    f=torch.cat([torch.from_numpy(v['features'].astype(np.float32)) for v in files]);labels=[torch.from_numpy(v['labels'].astype(np.int64)) for v in files];regression=[torch.from_numpy(v['regression'].astype(np.float32)) for v in files]
    logits,boxes=net.roi_heads.box_predictor(f);cl,box=fastrcnn_loss(logits,boxes,labels,regression)
    return cl+box,dict(classification=float(cl.detach()),boxRegression=float(box.detach()))
def main(args):
    torch.set_num_threads(2);torch.manual_seed(20261011);np.random.seed(20261011);random.seed(20261011)
    splits=setup('acne');tiles=acne_tiles(splits['train']);folder=NEW/args.model;folder.mkdir(parents=True,exist_ok=True);cache=folder/'cache';cache.mkdir(exist_ok=True)
    protocol=dict(model=args.model,stage='frozen-feature predictor adaptation',maximumEpochs=8,patience=3,batch=8,wallSecondsPerInvocation=args.seconds,totalWallSecondsLimit=3600,learningRate=.0002,thresholds=[.1,.25,.4,.55,.7],acceptance={'F1':.5,'precision':.6,'recall':.4},independentFinalAvailable=False,trainTiles=len(tiles),cachePrecision='float16 frozen features; predictor/loss float32',negativeCompletenessKnown=False,originalFullBackboneTrainingNotCompleted=True,seed=20261011)
    tile_ids=[dict(sha=t['row']['sha256'],rect=t['rect'],boxes=t['boxes']) for t in tiles];identity=digest({'protocol':{k:v for k,v in protocol.items() if k!='wallSecondsPerInvocation'},'tiles':tile_ids})
    if (folder/'protocol.json').exists():assert json.loads((folder/'protocol.json').read_text())['identity']==identity
    (folder/'protocol.json').write_text(json.dumps({**protocol,'identity':identity},indent=2),'utf8')
    # Do not overwrite old initialization evidence.
    if args.model=='fasterrcnn':
        import detection_pretrained_acne as init
        init.OUT=folder;net=init.create();net.transform.min_size=(384,);net.transform.max_size=384
    else:
        net=detector('yolox');net.load_state_dict(load_file(str(OLD/'yolox/selected.safetensors')))
    for key,p in net.named_parameters():p.requires_grad=('head.' in key and any(z in key for z in ['cls_preds','reg_preds','obj_preds'])) if args.model=='yolox' else key.startswith('roi_heads.box_predictor.')
    net.eval();opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=protocol['learningRate'],weight_decay=.0001)
    state=dict(identity=identity,step=0,epoch=0,cursor=0,order=[],losses=[],components=[],history=[],best=-1.,bad=0,totalSeconds=0.,phase='cache',cacheCursor=0,legacyResume='weights-only (optimizer absent)' if args.model=='yolox' else 'fresh pretrained initialization (no previous trained checkpoint exists)')
    if (folder/'CURRENT').exists():state=resume(folder,net,opt,identity);print('EXACT_RESUME',args.model,state['step'],state['epoch'],state['cursor'],flush=True)
    if args.total_seconds>3600:
        assert state['cacheCursor']==len(tiles),'MEASURE_PREPARATION_BEFORE_RESERVING_COMPLETION_BUDGET'
        state['completionBudgetPlan']=dict(initialTotalSeconds=3600,totalLimitSeconds=args.total_seconds,additionalMaximumSeconds=args.total_seconds-3600,finiteEpochCap=args.max_epochs,reason='Measured preparation consumed most initial wall budget; reserve bounded time for completing predictor validation, preserving optimizer/RNG/cursor. No additional full-backbone epochs or acceptance change.')
    started=time.monotonic();base=state['totalSeconds']
    def save():
        nonlocal state
        state['totalSeconds']=base+time.monotonic()-started;state=checkpoint(folder,net,opt,state)
    def budget():return time.monotonic()-started>=args.seconds or base+time.monotonic()-started>=args.total_seconds
    for i in range(state['cacheCursor'],len(tiles)):
        if budget():save();print('BOUNDED_CACHE_PAUSE',i,flush=True);return
        file=cache/f'{i:05d}.npz'
        if not file.exists():
            f=yolo_features(net,tiles[i]) if args.model=='yolox' else faster_features(net,tiles[i]);np.savez(file,**{k:v.astype(np.float16) if v.dtype.kind=='f' else v for k,v in f.items()},cacheTorchRNG=torch.get_rng_state().numpy())
        elif args.model=='fasterrcnn':
            # A cache file may have been committed just after the last state
            # transaction. Replay its post-sampler RNG before continuing.
            with np.load(file,allow_pickle=False) as saved:
                assert 'cacheTorchRNG' in saved,'CACHE_RNG_MISSING';torch.set_rng_state(torch.from_numpy(saved['cacheTorchRNG']))
        state['cacheCursor']=i+1
        if (i+1)%100==0:save();print('CACHE',args.model,i+1,len(tiles),round(time.monotonic()-started,1),flush=True)
    state['phase']='train';save()
    loss_fn=yolo_loss if args.model=='yolox' else faster_loss
    # First exact cached-vs-source loss check, no optimizer step.
    if not (folder/'cache-parity.json').exists():
        sample=[tiles[i] for i in range(2)];exact=[yolo_features(net,t) if args.model=='yolox' else faster_features(net,t) for t in sample]
        stored=[np.load(cache/f'{i:05d}.npz',allow_pickle=False) for i in range(2)]
        a,ac=loss_fn(net,exact,sample);b,bc=loss_fn(net,stored,sample);err=abs(float(a.detach())-float(b.detach()))
        # Faster's ROI sampler is random; fixed stored samples differ. Compare
        # features in each file to their own f16 round trip instead of claiming
        # random proposals are the same.
        write(f'{args.model}/cache-parity.json',dict(lossExact=float(a.detach()),lossCached=float(b.detach()),absoluteLossDifference=err,samplerRandom=args.model=='fasterrcnn',cachedStage='frozen predictor input',cacheLossComponents=bc))
        if args.model=='yolox':assert err<.02
        save()
    state['finiteEpochCap']=args.max_epochs
    while state['epoch']<state['finiteEpochCap'] and state['bad']<3:
        if not state['order']:state['order']=torch.randperm(len(tiles)).tolist();state['cursor']=0;state['losses']=[];state['components']=[]
        for cursor in range(state['cursor'],len(tiles),8):
            if budget():save();print('BOUNDED_TRAIN_PAUSE',state['epoch'],cursor,flush=True);return
            ids=state['order'][cursor:cursor+8];items=[tiles[i] for i in ids];files=[np.load(cache/f'{i:05d}.npz',allow_pickle=False) for i in ids]
            opt.zero_grad();value,components=loss_fn(net,files,items);assert torch.isfinite(value);value.backward();torch.nn.utils.clip_grad_norm_([p for p in net.parameters() if p.requires_grad],10);opt.step()
            for f in files:f.close()
            state['step']+=1;state['cursor']=cursor+len(ids);state['losses'].append(float(value.detach()));state['components'].append(components)
            if state['step']%25==0:save();print('STEP',args.model,state['step'],state['epoch'],state['cursor'],round(float(value.detach()),4),flush=True)
        # Validation is development only. Its predictions are never relabelled
        # final, nor mixed with opened old final sources.
        if budget():save();print('BOUNDED_BEFORE_VALIDATION',flush=True);return
        state['phase']='validation'
        try:
            pred=bounded_faster_prediction(net,splits['validation'],folder,state,budget,save) if args.model=='fasterrcnn' else predict(net,args.model,splits['validation'])
        except Exception:
            # Preserve the completed gradient epoch even if validation I/O
            # fails. Frozen per-tile feature files remain reusable on resume.
            save();raise
        if pred is None:save();print('BOUNDED_VALIDATION_PAUSE',flush=True);return
        choices=[detection_metrics(splits['validation'],pred,t) for t in protocol['thresholds']];m=max(choices,key=lambda v:v['F1'])
        entry=dict(epoch=state['epoch']+1,loss=float(np.mean(state['losses'])),componentMeans={k:float(np.mean([c[k] for c in state['components']])) for k in state['components'][0]},development=m,totalSeconds=base+time.monotonic()-started)
        state['history'].append(entry);state['epoch']+=1;state['order']=[];state['cursor']=0
        if m['F1']>state['best']+.0001:
            state['best']=m['F1'];state['bad']=0;save_file(net.state_dict(),str(folder/'selected.safetensors'));write(f'{args.model}/validation-predictions.json',dict(metrics=m,rows=[dict(path=r['path'],group=r['group'],truth=r['annotations'],predictions=p) for r,p in zip(splits['validation'],pred)]))
        else:state['bad']+=1
        write(f'{args.model}/history.json',state['history']);save();print('EPOCH',args.model,json.dumps(entry),flush=True)
    state['phase']='finite-stage-complete';save();write(f'{args.model}/result.json',dict(history=state['history'],complete=True,finiteEpochCap=state['finiteEpochCap'],stop='patience' if state['bad']>=3 else 'finite-epoch-cap',fullBackboneConverged=False,independentFinalAvailable=False,productAccepted=False,requiresNewIndependentSources=True,totalSeconds=state['totalSeconds'],completionBudgetPlan=state.get('completionBudgetPlan'),totalWallSecondsLimit=args.total_seconds))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('model',choices=['yolox','fasterrcnn']);p.add_argument('--seconds',type=int,default=1200);p.add_argument('--max-epochs',type=int,default=4);p.add_argument('--total-seconds',type=int,default=3600);a=p.parse_args();assert 1<=a.seconds<=3600 and 1<=a.max_epochs<=8 and 3600<=a.total_seconds<=4800;main(a)
