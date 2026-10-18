"""Two finite, photo-only candidates; validation selection then one frozen test.
Uses safe reviewed ImageNet tensors. No clinical or local-severity inference.
"""
from pathlib import Path
import argparse, json, time, random, hashlib
import cv2, numpy as np, torch
from torch import nn
from torchvision.models import resnet18, efficientnet_b0
from safetensors.torch import load_file, save_file
from prepare_focused_data import ROOT, OUT, CLASSES, write, sha
SEED=20261010
MEAN=np.array([.485,.456,.406],np.float32)[:,None,None]
STD=np.array([.229,.224,.225],np.float32)[:,None,None]

def image(row,flip=False):
    im=cv2.imread(row['absolutePath']);x,y,x1,y1=row['crop'];rgb=im[y:y1,x:x1,::-1]
    if flip:rgb=rgb[:,::-1]
    rgb=cv2.resize(rgb,(224,224),interpolation=cv2.INTER_AREA)
    return torch.from_numpy(((rgb.transpose(2,0,1).astype(np.float32)/255-MEAN)/STD).copy())
def model(name):
    net=resnet18(weights=None) if name=='resnet18' else efficientnet_b0(weights=None)
    file='resnet18-f37072fd.pth.safetensors' if name=='resnet18' else 'efficientnet_b0_rwightman-7f5810bc.pth.safetensors'
    rights=json.loads((OUT/'pretrained/rights.json').read_text());r=next(r for r in rights if file==r['file']+'.safetensors')
    assert sha(OUT/'pretrained'/file)==r['safeSHA256']
    net.load_state_dict(load_file(str(OUT/'pretrained'/file)),strict=True)
    if name=='resnet18':net.fc=nn.Linear(512,4)
    else:net.classifier=nn.Sequential(nn.Dropout(.2),nn.Linear(1280,4))
    return net
def head(net,name):return net.fc if name=='resnet18' else net.classifier
def features(net,name,x):
    if name=='resnet18':
        x=net.maxpool(net.relu(net.bn1(net.conv1(x))));x=net.layer4(net.layer3(net.layer2(net.layer1(x))));return net.avgpool(x).flatten(1)
    return net.avgpool(net.features(x)).flatten(1)
def scores(truth,logits):
    pred=np.asarray(logits).argmax(1);truth=np.asarray(truth);matrix=np.zeros((4,4),int)
    for a,b in zip(truth,pred):matrix[a,b]+=1
    per=[]
    for k in range(4):
        tp=int(matrix[k,k]);p=tp/max(1,int(matrix[:,k].sum()));r=tp/max(1,int(matrix[k,:].sum()))
        per.append(dict(label=CLASSES[k],precision=p,recall=r,F1=2*p*r/max(1e-12,p+r),support=int(matrix[k,:].sum())))
    return dict(macroF1=float(np.mean([r['F1'] for r in per])),balancedAccuracy=float(np.mean([r['recall'] for r in per])),accuracy=float(np.mean(pred==truth)),classes=per,confusionMatrix=matrix.tolist(),images=len(truth))
def evaluate(net,rows):
    net.eval();result=[]
    with torch.inference_mode():
        for start in range(0,len(rows),16):result.extend(net(torch.stack([image(r) for r in rows[start:start+16]])).numpy().tolist())
    return np.asarray(result,np.float32)
def setup():
    torch.set_num_threads(2);cv2.setNumThreads(1);torch.manual_seed(SEED);np.random.seed(SEED);random.seed(SEED)
    manifest=json.loads((OUT/'learning-manifest.json').read_text())
    assert manifest.get('qualityFinalizedBeforeTraining') and (OUT/'quality-review.json').exists()
    return manifest,[r for r in manifest['rows'] if r['typeEligible']]
def train(name):
    manifest,rows=setup();folder=OUT/name;folder.mkdir(exist_ok=True)
    if (folder/'selection.json').exists():raise RuntimeError('Completed candidate is preserved; do not restart')
    protocol=dict(architecture=name,seed=SEED,headEpochLimit=5,fineTuneEpochLimit=20,patience=5,wallSecondsLimit=3600,optimizer='AdamW',headLR=.002,fineTuneLR=.00005,weightDecay=.01,batch=16,scheduler='cosine for upper-layer fine tuning',augmentation='train-only horizontal flip; no color/texture synthesis',normalization=dict(mean=MEAN[:,0,0].tolist(),std=STD[:,0,0].tolist(),RGB=True,input=[224,224],cropVersion=manifest['cropVersion']),selection='validation macro-F1',testSealed=True,acceptance=dict(macroF1Minimum=.6,minimumClassF1=.4,mustBeatTrainPrior=True,confidencePrecision=.7,confidenceMinimumSupport=10))
    write(name+'/protocol.json',protocol)
    train=[r for r in rows if r['split']=='train'];val=[r for r in rows if r['split']=='validation']
    assert all(sum(r['class']==c for r in train)>0 and sum(r['class']==c for r in val)>0 for c in CLASSES)
    y=torch.tensor([CLASSES.index(r['class']) for r in train]);vy=np.array([CLASSES.index(r['class']) for r in val]);counts=torch.bincount(y,minlength=4);weights=counts.sum()/(4*counts.float())
    net=model(name);net.eval();started=time.monotonic();cache=[]
    with torch.inference_mode():
        for start in range(0,len(train),16):cache.append(features(net,name,torch.stack([image(r) for r in train[start:start+16]])).clone())
    X=torch.cat(cache).clone();VH=[]
    with torch.inference_mode():
        for start in range(0,len(val),16):VH.append(features(net,name,torch.stack([image(r) for r in val[start:start+16]])).clone())
    VX=torch.cat(VH).clone();classifier=head(net,name)
    # A tiny train-only balanced learning-chain check, no validation/test tuning.
    tiny=torch.tensor([int((y==c).nonzero()[i]) for c in range(4) for i in range(min(2,int((y==c).sum())))])
    initial={k:v.clone() for k,v in classifier.state_dict().items()};opt=torch.optim.AdamW(classifier.parameters(),lr=.01,weight_decay=.001);losses=[]
    for step in range(160):
        classifier.train();opt.zero_grad();loss=nn.functional.cross_entropy(classifier(X[tiny]),y[tiny],weight=weights);loss.backward();opt.step();losses.append(float(loss.detach()))
    classifier.eval()
    with torch.no_grad():accuracy=float((classifier(X[tiny]).argmax(1)==y[tiny]).float().mean())
    write(name+'/learning.json',dict(passed=accuracy>=.875,trainOnly=True,images=len(tiny),steps=160,firstLoss=losses[0],lastLoss=losses[-1],accuracy=accuracy))
    assert accuracy>=.875,'LEARNING_CHAIN_FAILED'
    classifier.load_state_dict(initial);opt=torch.optim.AdamW(classifier.parameters(),lr=.002,weight_decay=.01);best=-1.;bad=0;history=[]
    def select(stage,epoch,logits,loss):
        nonlocal best,bad
        m=scores(vy,logits);entry=dict(stage=stage,epoch=epoch,trainLoss=loss,seconds=time.monotonic()-started,validation=m);history.append(entry)
        if m['macroF1']>best+1e-5:best=m['macroF1'];bad=0;save_file(net.state_dict(),str(folder/'selected.safetensors'));np.save(folder/'validation-logits.npy',logits,allow_pickle=False)
        else:bad+=1
        write(name+'/history.json',history);print(name,stage,epoch,round(m['macroF1'],4),round(entry['seconds'],1),flush=True)
    for epoch in range(5):
        classifier.train();losses=[]
        for ids in torch.randperm(len(train)).split(16):
            opt.zero_grad();loss=nn.functional.cross_entropy(classifier(X[ids]),y[ids],weight=weights);loss.backward();opt.step();losses.append(float(loss.detach()))
        classifier.eval()
        with torch.no_grad():logits=classifier(VX).numpy()
        select('head',epoch+1,logits,float(np.mean(losses)))
    net.load_state_dict(load_file(str(folder/'selected.safetensors')))
    for key,p in net.named_parameters():p.requires_grad=key.startswith(('layer4','fc') if name=='resnet18' else ('features.7','features.8','classifier'))
    opt=torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],lr=.00005,weight_decay=.01);scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(opt,20);bad=0
    for epoch in range(20):
        if time.monotonic()-started>=3600:break
        net.train()
        for m in net.modules():
            if isinstance(m,nn.BatchNorm2d):m.eval()
        losses=[]
        for ids in torch.randperm(len(train)).split(16):
            x=torch.stack([image(train[int(i)],flip=random.random()<.5) for i in ids]);opt.zero_grad();loss=nn.functional.cross_entropy(net(x),y[ids],weight=weights)
            if not torch.isfinite(loss):raise RuntimeError('NONFINITE_LOSS')
            loss.backward();nn.utils.clip_grad_norm_(net.parameters(),5);opt.step();losses.append(float(loss.detach()))
        logits=evaluate(net,val);select('upper-layers',epoch+1,logits,float(np.mean(losses)));scheduler.step()
        if bad>=5:break
    net.load_state_dict(load_file(str(folder/'selected.safetensors')));net.eval();logits=np.load(folder/'validation-logits.npy',allow_pickle=False)
    # Fit temperature only on validation labels, no test access.
    temperatures=np.geomspace(.5,5,61);nll=[]
    for t in temperatures:
        v=logits/t;v-=v.max(1,keepdims=True);p=np.exp(v);p/=p.sum(1,keepdims=True);nll.append(float(-np.log(p[np.arange(len(vy)),vy]+1e-12).mean()))
    t=float(temperatures[int(np.argmin(nll))]);v=logits/t;v-=v.max(1,keepdims=True);p=np.exp(v);p/=p.sum(1,keepdims=True)
    thresholds=[]
    for threshold in np.arange(.4,.951,.025):
        mask=p.max(1)>=threshold;n=int(mask.sum());precision=float((p.argmax(1)[mask]==vy[mask]).mean()) if n else 0
        if n>=10 and precision>=.7:thresholds.append((n,float(threshold),precision))
    chosen=max(thresholds,default=(0,1.,0))
    selection=dict(model=name,weightsSHA256=sha(folder/'selected.safetensors'),validation=scores(vy,logits),temperature=t,confidenceThreshold=chosen[1],confidenceValidationPrecision=chosen[2],confidenceValidationSupport=chosen[0],trainCounts=counts.tolist(),trainPriorClass=int(counts.argmax()),protocol=protocol,seconds=time.monotonic()-started,datasetManifestSHA256=sha(OUT/'dataset-manifest.json'),protectedDegreeTestExcluded=True,testOpened=False)
    write(name+'/selection.json',selection)
def final():
    manifest,rows=setup();selections=[json.loads((OUT/name/'selection.json').read_text()) for name in ['resnet18','efficientnet_b0']]
    review=json.loads((OUT/'type-validation-review.json').read_text())
    assert all(any(r['model']==s['model'] and r['weightsSHA256']==s['weightsSHA256'] and r.get('visualReviewComplete') for r in review) for s in selections),'Review both frozen validation error sheets before opening the protected test; resume final only, never restart candidates'
    winner=max(selections,key=lambda s:s['validation']['macroF1']);name=winner['model'];folder=OUT/name
    assert not (OUT/'type-final-test.json').exists(),'Protected final test is one-time'
    # Freeze model/calibration before touching protected test inputs.
    write('type-frozen-selection.json',winner)
    test=[r for r in rows if r['split']=='test'];truth=np.array([CLASSES.index(r['class']) for r in test]);net=model(name);net.load_state_dict(load_file(str(folder/'selected.safetensors')));net.eval();logits=evaluate(net,test);metrics=scores(truth,logits)
    prior=np.zeros((len(truth),4));prior[:,winner['trainPriorClass']]=1.;baseline=scores(truth,prior)
    accepted=metrics['macroF1']>=.6 and min(c['F1'] for c in metrics['classes'])>=.4 and metrics['macroF1']>baseline['macroF1'] and winner['confidenceValidationSupport']>=10
    write('type-final-test.json',dict(selected=name,metrics=metrics,trainPriorBaseline=baseline,accepted=accepted,cameraDomainAcceptance=False,personIndependent=False,testGroups=len({r['group'] for r in test}),rows=[dict(path=r['path'],group=r['group'],className=r['class'],prediction=CLASSES[int(p.argmax())],logits=p.tolist()) for r,p in zip(test,logits)]))
    # Export also rejected candidate for honest parity/diagnostics, never install it.
    path=folder/'selected.onnx';example=torch.randn(1,3,224,224)
    torch.onnx.export(net,example,str(path),input_names=['rgb'],output_names=['type_logits'],opset_version=17,dynamo=False)
    import onnxruntime as ort
    options=ort.SessionOptions();options.intra_op_num_threads=2;start=time.monotonic();session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);cold=time.monotonic()-start;examples=[image(r).unsqueeze(0).numpy() for r in test[:8]];parity=[];times=[]
    for x in examples:
        start=time.monotonic();actual=session.run(None,{'rgb':x})[0];times.append((time.monotonic()-start)*1000)
        with torch.inference_mode():expected=net(torch.from_numpy(x)).numpy()
        parity.append(float(np.max(np.abs(actual-expected))))
    assert max(parity)<1e-3
    write('type-export.json',dict(selected=name,accepted=accepted,onnxSHA256=sha(path),bytes=path.stat().st_size,maxAbsoluteError=max(parity),coldLoadSeconds=cold,firstInferenceMs=times[0],laterInferenceMs=times[1:],input='RGB source MediaPipe camera-crop-v1 -> INTER_AREA 224 -> ImageNet normalization',classOrder=CLASSES,sourceRights=json.loads((OUT/'pretrained/rights.json').read_text())))
    print('Final',name,metrics,'accepted',accepted,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['resnet18','efficientnet_b0','final']);a=p.parse_args()
    final() if a.mode=='final' else train(a.mode)
