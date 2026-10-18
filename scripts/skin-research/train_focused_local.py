"""Finite native-tile acne comparison and polygon-only eye-bag experiment.

Reviewed source groups, not patients. Unknown unannotated skin is not a healthy
negative. Box predictions keep their box resolution, not invented pixel masks.
All experiments and images remain in the ignored research directory.
"""
import argparse, collections, json, random, sys, time
import cv2, numpy as np, torch
from safetensors.torch import load_file, save_file
from torchvision.ops import nms
from prepare_focused_data import ROOT, OUT, write, sha
REV='6ddff4824372906469a7fae2dc3206c7aa4bbaee'
sys.path.insert(0,str(ROOT/f'audit-results/combined-health-20261008/yolox/extracted/YOLOX-{REV}'))
from yolox.models import YOLOX,YOLOPAFPN,YOLOXHead
from yolox.utils import postprocess
SIZE=384

def setup(task):
    torch.set_num_threads(2);cv2.setNumThreads(1);torch.manual_seed(20261010);random.seed(20261010);np.random.seed(20261010)
    m=json.loads((OUT/'learning-manifest.json').read_text())
    assert (OUT/'quality-review.json').exists(),'Visual quality review required before learning'
    excluded=set(json.loads((OUT/'quality-review.json').read_text())['excludedSHA256'])
    rows=[r for r in m['rows'] if r['corpus']=='eye' and r['eligible'] and r['sha256'] not in excluded]
    taskrows=[r for r in rows if any(a['classId']==(0 if task=='acne' else 1) and (task=='acne' or a['kind']=='polygon') for a in r['annotations'])]
    return {s:[r for r in taskrows if r['split']==s] for s in ['train','validation','test']}

def acne_tiles(rows,training=True):
    tiles=[]
    for r in rows:
        x,y,x1,y1=r['crop'];w=x1-x;h=y1-y
        xs=sorted(set([*range(x,max(x+1,x1-SIZE+1),288),max(x,x1-SIZE)]));ys=sorted(set([*range(y,max(y+1,y1-SIZE+1),288),max(y,y1-SIZE)]))
        for a in xs:
            for b in ys:
                endx=min(x1,a+SIZE);endy=min(y1,b+SIZE);boxes=[]
                for ann in r['annotations']:
                    if ann['classId']!=0:continue
                    bx,by,ex,ey=ann['box'];cl=[max(bx,a),max(by,b),min(ex,endx),min(ey,endy)]
                    if cl[2]-cl[0]>=2 and cl[3]-cl[1]>=2 and (cl[2]-cl[0])*(cl[3]-cl[1])>=.7*(ex-bx)*(ey-by):boxes.append([cl[0]-a,cl[1]-b,cl[2]-a,cl[3]-b])
                # Empty tiles are unknown, not manufactured healthy negatives.
                if boxes or not training:tiles.append(dict(row=r,rect=[a,b,endx,endy],boxes=boxes))
    return tiles

def tile_image(t):
    im=cv2.imread(t['row']['absolutePath']);x,y,x1,y1=t['rect'];canvas=np.full((SIZE,SIZE,3),114,np.uint8);crop=im[y:y1,x:x1];canvas[:crop.shape[0],:crop.shape[1]]=crop
    return torch.from_numpy(canvas.transpose(2,0,1).copy()).float()

def yolo_batch(items):
    targets=torch.zeros((len(items),max(len(t['boxes']) for t in items),5))
    for i,t in enumerate(items):
        for j,(x,y,x1,y1) in enumerate(t['boxes']):targets[i,j]=torch.tensor([0,(x+x1)/2,(y+y1)/2,x1-x,y1-y])
    return torch.stack([tile_image(t) for t in items]),targets

def yolo_model():
    net=YOLOX(YOLOPAFPN(depth=.33,width=.5),YOLOXHead(1,width=.5));path=OUT/'pretrained/yolox_s.safetensors'
    if not path.exists():
        source=OUT/'pretrained/yolox_s.pth';state=torch.load(source,map_location='cpu',weights_only=True)['model'];save_file(state,str(path))
        write('pretrained/yolox-rights.json',dict(codeRevision=REV,source='https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.pth',codeLicense='Apache-2.0',weightTerms='official same-project release; repository Apache-2.0; COCO upstream data terms distinct',originalSHA256=sha(source),safeSHA256=sha(path)))
    rights=json.loads((OUT/'pretrained/yolox-rights.json').read_text());assert sha(path)==rights['safeSHA256']
    state=load_file(str(path));own=net.state_dict();mapped={k:v for k,v in state.items() if k in own and v.shape==own[k].shape};missing,_=net.load_state_dict(mapped,strict=False)
    assert all('cls_preds' in k for k in missing),missing
    net.head.initialize_biases(.01);return net

def detector(name):
    if name=='yolox':return yolo_model()
    import detection_pretrained_acne as previous
    previous.OUT=OUT/'fasterrcnn';net=previous.create()
    # Native tile has exactly 384 source pixels; no repeated crop scaling.
    net.transform.min_size=(SIZE,);net.transform.max_size=SIZE
    return net

def loss(net,name,items):
    if name=='yolox':
        x,y=yolo_batch(items);return net(x,y)['total_loss']
    x=[tile_image(t)[[2,1,0]]/255 for t in items];targets=[dict(boxes=torch.tensor(t['boxes'],dtype=torch.float32),labels=torch.ones(len(t['boxes']),dtype=torch.int64)) for t in items]
    return sum(net(x,targets).values())

def predict(net,name,rows):
    tiles=acne_tiles(rows,training=False);by=collections.defaultdict(list);net.eval()
    with torch.inference_mode():
        for t in tiles:
            if name=='yolox':
                p=postprocess(net(tile_image(t)[None]),1,.01,.45,class_agnostic=True)[0]
                ps=[] if p is None else [[*v[:4],v[4]*v[5]] for v in p.numpy()]
            else:
                p=net([tile_image(t)[[2,1,0]]/255])[0];ps=[[*b,float(s)] for b,s in zip(p['boxes'].numpy(),p['scores'].numpy()) if s>=.01]
            a,b,x1,y1=t['rect']
            for x,y,ex,ey,s in ps:by[t['row']['sha256']].append([max(a,x+a),max(b,y+b),min(x1,ex+a),min(y1,ey+b),s])
    result=[]
    for r in rows:
        arr=np.array(by[r['sha256']],np.float32).reshape(-1,5)
        if len(arr):arr=arr[(arr[:,2]>arr[:,0])&(arr[:,3]>arr[:,1])];keep=nms(torch.tensor(arr[:,:4]),torch.tensor(arr[:,4]),.3).numpy();arr=arr[keep]
        result.append(arr.tolist())
    return result

def overlap(a,b):
    x,y=np.maximum(a[:2],b[:2]);ex,ey=np.minimum(a[2:4],b[2:4]);inter=max(0,ex-x)*max(0,ey-y)
    return inter/max(1e-8,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)

def detection_metrics(rows,pred,threshold):
    # Restrict truth to annotated native face crops; annotation completeness is
    # unverified, so unmatched boxes are annotation-relative FP, not clinical FP.
    truths=[]
    for r in rows:
        a,b,x1,y1=r['crop'];truths.append([ann['box'] for ann in r['annotations'] if ann['classId']==0 and a<=sum(ann['box'][::2])/2<=x1 and b<=sum(ann['box'][1::2])/2<=y1])
    total=sum(map(len,truths));ranked=sorted([(p[4],i,p[:4]) for i,ps in enumerate(pred) for p in ps],reverse=True,key=lambda v:v[0]);aps=[];main=None
    for boundary in np.arange(.5,1,.05):
        used=collections.defaultdict(set);tp=[];fp=[]
        for score,i,box in ranked:
            value,j=max([(overlap(box,t),j) for j,t in enumerate(truths[i]) if j not in used[i]],default=(0,-1));positive=value>=boundary
            if positive:used[i].add(j)
            tp.append(int(positive));fp.append(int(not positive))
        ct=np.cumsum(tp);cf=np.cumsum(fp);rec=ct/max(1,total);precision=ct/np.maximum(1,ct+cf)
        aps.append(float(np.mean([precision[rec>=v].max(initial=0) for v in np.linspace(0,1,101)])))
        if main is None:
            n=sum(s>=threshold for s,_,_ in ranked);t=sum(tp[:n]);f=sum(fp[:n]);p=t/max(1,t+f);r=t/max(1,total)
            main=dict(precision=p,recall=r,F1=2*p*r/max(1e-8,p+r),truePositive=t,falsePositive=f,falseNegative=total-t,annotationRelativeFalseCandidatesPerPhoto=f/max(1,len(rows)),images=len(rows),sourceGroups=len({r['group'] for r in rows}),unlabelledAreasKnownHealthy=False)
    return dict(**main,AP50=aps[0],mAP50to95=float(np.mean(aps)),threshold=threshold)

def train_detection(name):
    splits=setup('acne');folder=OUT/name;folder.mkdir(exist_ok=True)
    assert not (folder/'final-test.json').exists(),'Completed protected test preserved'
    protocol=dict(architecture=name,nativeTileSize=SIZE,stride=288,sourceCoordinates=True,RGB=name!='yolox',epochs=12 if name=='yolox' else 6,patience=4,wallSeconds=3600,thresholds=[.1,.25,.4,.55,.7],minimumFinalF1=.5,minimumPrecision=.6,minimumRecall=.4,seed=20261010,emptyTilesNotHealthy=True,personIndependent=False,allEligibleTrainImages=len(splits['train']))
    write(name+'/protocol.json',protocol);tiles=acne_tiles(splits['train']);assert tiles and splits['validation'] and splits['test']
    net=detector(name);opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.0002,weight_decay=.0001);started=time.monotonic();net.train();tiny=tiles[:2];learning=[]
    for step in range(80):
        opt.zero_grad();v=loss(net,name,tiny);assert torch.isfinite(v);v.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),10);opt.step();learning.append(float(v.detach()))
    passed=np.mean(learning[-10:])<.65*np.mean(learning[:10]);write(name+'/learning.json',dict(passed=bool(passed),steps=80,firstLoss=float(np.mean(learning[:10])),lastLoss=float(np.mean(learning[-10:])),trainOnly=True));assert passed,'LEARNING_CHAIN_FAILED'
    # Reinitialize after the tiny check; never give its two images extra weight.
    del net;net=detector(name);opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.0002,weight_decay=.0001);history=[];best=-1;bad=0
    for epoch in range(protocol['epochs']):
        if time.monotonic()-started>protocol['wallSeconds']:break
        net.train();order=list(range(len(tiles)));random.shuffle(order);losses=[]
        def partial_checkpoint(completed_tiles,reason):
            # Research-only partial weights never become a validated selection.
            temporary=folder/'partial.safetensors.tmp'
            save_file(net.state_dict(),str(temporary))
            temporary.replace(folder/'partial.safetensors')
            write(name+'/partial-progress.json',dict(epoch=epoch+1,completedTiles=completed_tiles,
                  totalTiles=len(order),seconds=time.monotonic()-started,reason=reason,
                  eligibleForSelection=False,optimizerStateSaved=False,seed=protocol['seed']))
        for start in range(0,len(order),2):
            if time.monotonic()-started>protocol['wallSeconds']:
                partial_checkpoint(start,'WALL_BUDGET_BEFORE_VALIDATED_EPOCH')
                raise RuntimeError('WALL_BUDGET: partial weights preserved, no validation/test promotion')
            batch=[tiles[i] for i in order[start:start+2]]
            if len(batch)<2:continue
            opt.zero_grad();v=loss(net,name,batch);assert torch.isfinite(v);v.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),10);opt.step();losses.append(float(v.detach()))
            if (start+2)%200==0:
                partial_checkpoint(start+2,'PERIODIC_TRAINING_ONLY')
                print(name,'training tiles',start+2,'/',len(order),flush=True)
        pred=predict(net,name,splits['validation']);choices=[detection_metrics(splits['validation'],pred,t) for t in protocol['thresholds']];m=max(choices,key=lambda v:v['F1']);history.append(dict(epoch=epoch+1,loss=float(np.mean(losses)),validation=m,seconds=time.monotonic()-started));write(name+'/history.json',history)
        print(name,epoch+1,m,flush=True)
        if m['F1']>best+1e-4:best=m['F1'];bad=0;save_file(net.state_dict(),str(folder/'selected.safetensors'));write(name+'/validation-predictions.json',dict(rows=[dict(path=r['path'],truth=r['annotations'],predictions=p) for r,p in zip(splits['validation'],pred)],metrics=m))
        else:bad+=1
        if bad>=protocol['patience']:break
    assert (folder/'selected.safetensors').exists(),'No validated epoch completed'
    net.load_state_dict(load_file(str(folder/'selected.safetensors')));selected=max(history,key=lambda h:h['validation']['F1']);threshold=selected['validation']['threshold'];write(name+'/frozen-selection.json',dict(threshold=threshold,weightsSHA256=sha(folder/'selected.safetensors'),testOpened=False,protocol=protocol))
    pred=predict(net,name,splits['test']);m=detection_metrics(splits['test'],pred,threshold);accepted=m['F1']>=.5 and m['precision']>=.6 and m['recall']>=.4
    write(name+'/final-test.json',dict(metrics=m,accepted=accepted,cameraDomainAccepted=False,rows=[dict(path=r['path'],truth=r['annotations'],predictions=p) for r,p in zip(splits['test'],pred)]))
    print(name,'FINAL',m,'accepted',accepted,flush=True)
    if name=='yolox':
        net.eval();path=folder/'candidate.onnx';x=tile_image(tiles[0])[None];torch.onnx.export(net,x,str(path),input_names=['native_bgr_tile'],output_names=['detections'],opset_version=17,dynamo=False)
        import onnxruntime as ort
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        started=time.monotonic();session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);cold=time.monotonic()-started;result=session.run(None,{'native_bgr_tile':x.numpy()})[0]
        with torch.no_grad():expected=net(x).numpy()
        error=float(np.max(np.abs(result-expected)));assert error<.01
        durations=[]
        for _ in range(5):start=time.monotonic();session.run(None,{'native_bgr_tile':x.numpy()});durations.append(time.monotonic()-start)
        write(name+'/export.json',dict(accepted=accepted,sha256=sha(path),bytes=path.stat().st_size,maxAbsParity=error,coldLoadSeconds=cold,warmSeconds=durations,preprocessing='native 384 BGR tile, 114 padding, no resize or normalization',researchOnly=not accepted))

def bag_rois(rows):
    sys.path.insert(0,str(ROOT/'services/core-api'))
    from skin_models import eye_rois
    result=[]
    for r in rows:
        points={int(k):v for k,v in r['eyeLandmarks'].items()} if 'eyeLandmarks' in r else r['landmarks'];w,h=r['width'],r['height']
        for roi in eye_rois(points,w,h):
            eye=roi['eye'];rect=roi['rect'];a,b,c,d=rect
            anns=[]
            for ann in r['annotations']:
                if ann['classId']!=1 or ann['kind']!='polygon':continue
                poly=np.array(ann['polygon']);center=poly.mean(0)
                if a<center[0]<c and b<center[1]<d and np.all((poly[:,0]>=a)&(poly[:,0]<c)&(poly[:,1]>=b)&(poly[:,1]<d)):anns.append(ann)
            if anns and c-a>=12 and d-b>=8:result.append(dict(row=r,eye=eye,rect=rect,annotations=anns))
    return result

def bag_tensor(t):
    a,b,c,d=t['rect'];rgb=cv2.imread(t['row']['absolutePath'])[b:d,a:c,::-1];mask=np.zeros((d-b,c-a),np.uint8)
    for ann in t['annotations']:cv2.fillPoly(mask,[np.round(np.array(ann['polygon'])-[a,b]).astype(np.int32)],1)
    # Only polygon and a two-source-pixel boundary band are supervised.
    # Unannotated outer ROI is unknown, not a whole-image negative mask.
    support=cv2.dilate(mask,np.ones((5,5),np.uint8))
    x=cv2.resize(rgb,(128,128),interpolation=cv2.INTER_AREA).transpose(2,0,1).astype(np.float32)/255;x=(x-np.array([.485,.456,.406])[:,None,None])/np.array([.229,.224,.225])[:,None,None]
    y=cv2.resize(mask,(128,128),interpolation=cv2.INTER_NEAREST);s=cv2.resize(support,(128,128),interpolation=cv2.INTER_NEAREST)
    return torch.tensor(x,dtype=torch.float32),torch.tensor(y[None],dtype=torch.float32),torch.tensor(s[None],dtype=torch.float32)

def bag_model():
    import segmentation_models_pytorch as smp
    net=smp.Unet(encoder_name='resnet18',encoder_weights=None,classes=1,decoder_channels=(128,64,32,16,8));state=load_file(str(OUT/'pretrained/resnet18-f37072fd.pth.safetensors'));net.encoder.load_state_dict({k:v for k,v in state.items() if not k.startswith('fc.')},strict=True);return net

def bag_loss(net,items):
    vals=[bag_tensor(t) for t in items];x,y,s=[torch.stack([v[i] for v in vals]) for i in range(3)];logit=net(x);p=torch.sigmoid(logit);bce=(torch.nn.functional.binary_cross_entropy_with_logits(logit,y,reduction='none')*s).sum()/s.sum().clamp_min(1)
    return bce+1-(2*(p*y*s).sum()+1)/((p*s).sum()+(y*s).sum()+1)

def bag_metrics(net,items,threshold):
    net.eval();rows=[]
    with torch.inference_mode():
        for t in items:
            x,y,s=bag_tensor(t);p=(torch.sigmoid(net(x[None]))[0]>=threshold).numpy();truth=y.numpy().astype(bool);support=s.numpy().astype(bool);p=p&support;truth=truth&support;inter=int((p&truth).sum());union=int((p|truth).sum());rows.append(dict(path=t['row']['path'],eye=t['eye'],Dice=2*inter/max(1,int(p.sum()+truth.sum())),IoU=inter/max(1,union),scope='polygon plus two-source-pixel boundary; unknown outer ROI excluded'))
    return dict(Dice=float(np.mean([r['Dice'] for r in rows])),IoU=float(np.mean([r['IoU'] for r in rows])),annotatedROIs=len(rows),threshold=threshold,rows=rows)

def train_bags():
    source=setup('bags');splits={s:bag_rois(rows) for s,rows in source.items()};folder=OUT/'bags';folder.mkdir(exist_ok=True);assert not (folder/'final-test.json').exists()
    protocol=dict(architecture='SMP Unet ResNet18',codeLicense='MIT',epochs=15,patience=4,wallSeconds=3600,batch=8,input=[128,128],seed=20261010,rectangularPolygonsExcluded=True,boxOnlyExcluded=True,unknownOutsideIgnored=True,supervision='polygon plus 2 source pixel boundary band',thresholds=[.3,.5,.7],minimumFinalDice=.65,minimumFinalIoU=.5,requiresIndependentConfounderReview=True,ROIs={s:len(v) for s,v in splits.items()});write('bags/protocol.json',protocol);assert all(splits.values())
    started=time.monotonic();net=bag_model();opt=torch.optim.AdamW(net.parameters(),lr=.0003,weight_decay=.0001);net.train();learning=[]
    for step in range(80):opt.zero_grad();v=bag_loss(net,splits['train'][:2]);v.backward();opt.step();learning.append(float(v.detach()))
    passed=np.mean(learning[-10:])<.65*np.mean(learning[:10]);write('bags/learning.json',dict(passed=bool(passed),steps=80,firstLoss=float(np.mean(learning[:10])),lastLoss=float(np.mean(learning[-10:])),trainOnly=True));assert passed,'LEARNING_CHAIN_FAILED'
    del net;net=bag_model();opt=torch.optim.AdamW(net.parameters(),lr=.0003,weight_decay=.0001);history=[];best=-1;bad=0
    for epoch in range(protocol['epochs']):
        if time.monotonic()-started>protocol['wallSeconds']:break
        net.train();order=list(range(len(splits['train'])));random.shuffle(order);losses=[]
        for start in range(0,len(order),8):
            items=[splits['train'][i] for i in order[start:start+8]]
            if len(items)<2:continue
            opt.zero_grad();v=bag_loss(net,items);assert torch.isfinite(v);v.backward();opt.step();losses.append(float(v.detach()))
        choices=[bag_metrics(net,splits['validation'],t) for t in protocol['thresholds']];m=max(choices,key=lambda x:x['Dice']);history.append(dict(epoch=epoch+1,loss=float(np.mean(losses)),validation={k:v for k,v in m.items() if k!='rows'},seconds=time.monotonic()-started));write('bags/history.json',history);print('bags',epoch+1,history[-1],flush=True)
        if m['Dice']>best+1e-4:best=m['Dice'];bad=0;save_file(net.state_dict(),str(folder/'selected.safetensors'));write('bags/validation.json',m)
        else:bad+=1
        if bad>=protocol['patience']:break
    net.load_state_dict(load_file(str(folder/'selected.safetensors')));threshold=max(history,key=lambda h:h['validation']['Dice'])['validation']['threshold'];write('bags/frozen-selection.json',dict(weightsSHA256=sha(folder/'selected.safetensors'),threshold=threshold,testOpened=False))
    m=bag_metrics(net,splits['test'],threshold);maskAccepted=m['Dice']>=.65 and m['IoU']>=.5;write('bags/final-test.json',dict(**m,maskMetricsAccepted=maskAccepted,accepted=False,reason='Independent pigment/shadow/normal-eye confounder review pending',cameraDomainAccepted=False))
    print('bags FINAL', {k:v for k,v in m.items() if k!='rows'},flush=True)
    path=folder/'candidate.onnx';net.eval();x=bag_tensor(splits['test'][0])[0][None];torch.onnx.export(net,x,str(path),input_names=['rgb_eye_roi'],output_names=['mask_logits'],opset_version=17,dynamo=False)
    import onnxruntime as ort
    options=ort.SessionOptions();options.intra_op_num_threads=2;start=time.monotonic();session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);cold=time.monotonic()-start;actual=session.run(None,{'rgb_eye_roi':x.numpy()})[0]
    with torch.no_grad():expected=net(x).numpy()
    error=float(np.max(np.abs(actual-expected)));assert error<1e-3;times=[]
    for _ in range(5):start=time.monotonic();session.run(None,{'rgb_eye_roi':x.numpy()});times.append(time.monotonic()-start)
    write('bags/export.json',dict(sha256=sha(path),bytes=path.stat().st_size,maskMetricsAccepted=maskAccepted,accepted=False,maxAbsParity=error,coldLoadSeconds=cold,warmSeconds=times,input='native source lower-lid ROI -> RGB INTER_AREA128 -> ImageNet normalization',probabilityNotSeverity=True))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('task',choices=['yolox','fasterrcnn','bags']);args=parser.parse_args()
    if args.task=='bags' and (OUT/'bags/final-test.json').exists() and (OUT/'bags/export.json').exists():
        exported=json.loads((OUT/'bags/export.json').read_text());assert sha(OUT/'bags/candidate.onnx')==exported['sha256']
        print('Preserved completed bags candidate and frozen export; no training or test repeated',flush=True)
    else:train_bags() if args.task=='bags' else train_detection(args.task)
