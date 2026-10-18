"""Masked, regularized image-feature regression, no oracle metadata inputs.

Whole-image ordinal targets never become anatomical/pixel labels. Elasticity
stays elasticity; dehydration is an appearance label, not biological moisture.
"""
import json,time
import numpy as np, torch
from train_focused_type import setup,model,features,image,OUT,write,sha
from prepare_focused_data import TARGETS
from safetensors.torch import load_file

def extract(net,name,rows):
    net.eval();parts=[]
    with torch.inference_mode():
        for start in range(0,len(rows),16):parts.append(features(net,name,torch.stack([image(r) for r in rows[start:start+16]])).numpy())
    return np.concatenate(parts).astype(np.float64)
def metrics(truth,pred):
    valid=np.isfinite(truth);truth=truth[valid];pred=pred[valid]
    if not len(truth):return dict(support=0,MAE=None,ordinalAgreement=None)
    return dict(support=len(truth),MAE=float(np.abs(truth-pred).mean()),ordinalAgreement=float(np.mean(np.floor(truth+.5)==np.floor(pred+.5))),withinOneGrade=float(np.mean(np.abs(truth-pred)<=1)))
def existing_comparison(target,rows,truth,pred,phase):
    path=OUT/('appearance-features-'+phase+'.json')
    if not path.exists():return dict(available=False,reason='SOURCE_METHOD_COMPARISON_NOT_READY')
    source={r['sha256']:r for r in json.loads(path.read_text())};ids=[i for i,r in enumerate(rows) if source.get(r['sha256'],{}).get('signals',{}).get(target) is not None and np.isfinite(truth[i])]
    if len(ids)<10:return dict(available=False,support=len(ids),reason='INSUFFICIENT_COMPARABLE_GLOBAL_FEATURES')
    baseline=np.array([source[rows[i]['sha256']]['signals'][target]/20 for i in ids]);model=metrics(truth[ids],pred[ids]);old=metrics(truth[ids],baseline)
    return dict(available=True,scope='whole-face only; no regional target copies',sourceMethod='appearance-cv-6 offline analytic baseline',model=model,baseline=old,beatsExisting=model['MAE']<old['MAE'])
def fit(X,y,regularization):
    mask=np.isfinite(y);a=X[mask];b=y[mask];center=b.mean()
    # Loss per valid count, not per complete row; missing/11 target stays masked.
    weights=a.T@np.linalg.solve(a@a.T+len(a)*regularization*np.eye(len(a)),b-center)
    return weights,center
def main():
    manifest,_=setup();selection=json.loads((OUT/'type-frozen-selection.json').read_text());name=selection['model']
    assert selection['protectedDegreeTestExcluded']
    rows=[r for r in manifest['rows'] if r['degreeEligible']]
    train=[r for r in rows if r['split']=='train'];val=[r for r in rows if r['split']=='validation']
    test=[r for r in rows if r['split']=='test'];test_groups={r['group'] for r in test}
    assert not test_groups&{r['group'] for r in manifest['rows'] if r['typeEligible'] and r['split'] in ['train','validation']}
    assert not (OUT/'degrees-final-test.json').exists(),'Retain frozen final test, do not rerun selection on it'
    protocol=dict(targets=TARGETS,featureBackbone=name,backboneSHA256=selection['weightsSHA256'],backboneDegreeTestExcluded=True,regularizationCandidates=[.01,.1,1,10],selection='per-target validation MAE',gradeRange=[0,5],maskedInvalidPolicy='only invalid target, never discard valid companion labels',normalization='train-only feature mean/std',baselines=['train target median','train target mean'],localSeverityMap=False,acceptance='at least 10 validation and test targets; MAE beats both constants in both splits; test MAE <= 1.0',elasticityNotSagging=True,dehydrationNotMoisture=True)
    write('degrees-protocol.json',protocol);net=model(name);net.load_state_dict(load_file(str(OUT/name/'selected.safetensors')));started=time.monotonic()
    X=extract(net,name,train);VX=extract(net,name,val);mean=X.mean(0);std=np.maximum(X.std(0),1e-3);X=(X-mean)/std;VX=(VX-mean)/std
    Y=np.array([[np.nan if v is None else v for v in r['grades']] for r in train]);VY=np.array([[np.nan if v is None else v for v in r['grades']] for r in val]);heads=[];weights=[];biases=[]
    learning=[]
    for k,target in enumerate(TARGETS):
        ids=np.flatnonzero(np.isfinite(Y[:,k]))[:8]
        if len(ids)<3:continue
        w,b=fit(X[ids],Y[ids,k],.001);pred=np.clip(X[ids]@w+b,0,5);constant=np.full(len(ids),np.mean(Y[ids,k]));actual=metrics(Y[ids,k],pred);baseline=metrics(Y[ids,k],constant)
        learning.append(dict(target=target,trainOnly=True,images=len(ids),closedFormMaskedRidge=True,MAE=actual['MAE'],constantMAE=baseline['MAE'],passed=actual['MAE']<=baseline['MAE']))
    write('degrees-learning.json',dict(targets=learning,passed=all(r['passed'] for r in learning),testNotOpened=True));assert all(r['passed'] for r in learning),'LEARNING_CHAIN_FAILED'
    for k,target in enumerate(TARGETS):
        truth=Y[:,k];valid=np.isfinite(truth);choices=[]
        if valid.sum()>=10:
            for ridge in [.01,.1,1,10]:
                w,b=fit(X,truth,ridge);pred=np.clip(VX@w+b,0,5);m=metrics(VY[:,k],pred)
                if m['support']:choices.append((m['MAE'],ridge,w,b,m))
        if not choices:
            weights.append(np.zeros(X.shape[1]));biases.append(0);heads.append(dict(target=target,available=False,reason='INSUFFICIENT_VALID_TARGETS'));continue
        _,ridge,w,b,m=min(choices,key=lambda c:c[0]);median=float(np.median(truth[valid]));average=float(truth[valid].mean())
        base_median=metrics(VY[:,k],np.full(len(val),median));base_mean=metrics(VY[:,k],np.full(len(val),average))
        weights.append(w);biases.append(b);heads.append(dict(target=target,available=True,regularization=ridge,validation=m,trainMedian=median,trainMean=average,validationMedianBaseline=base_median,validationMeanBaseline=base_mean,validationAccepted=m['support']>=10 and m['MAE']<min(base_median['MAE'],base_mean['MAE'])))
        comparison=existing_comparison(target,val,VY[:,k],np.clip(VX@w+b,0,5),'selection');heads[-1]['validationExistingMethod']=comparison
        if comparison['available']:heads[-1]['validationAccepted'] &= comparison['beatsExisting']
    W=np.stack(weights);B=np.array(biases);np.savez_compressed(OUT/'degrees-frozen-head.npz',mean=mean,std=std,weights=W,bias=B)
    write('degrees-frozen-selection.json',dict(protocol=protocol,heads=heads,headSHA256=sha(OUT/'degrees-frozen-head.npz'),testOpened=False))
    # Protected test is read after all per-target heads and scalers are frozen.
    TX=(extract(net,name,test)-mean)/std;TY=np.array([[np.nan if v is None else v for v in r['grades']] for r in test]);pred=np.clip(TX@W.T+B,0,5)
    for k,h in enumerate(heads):
        if not h['available']:h['accepted']=False;continue
        h['test']=metrics(TY[:,k],pred[:,k]);h['testMedianBaseline']=metrics(TY[:,k],np.full(len(test),h['trainMedian']));h['testMeanBaseline']=metrics(TY[:,k],np.full(len(test),h['trainMean']))
        h['accepted']=h['validationAccepted'] and h['test']['support']>=10 and h['test']['MAE']<=1 and h['test']['MAE']<min(h['testMedianBaseline']['MAE'],h['testMeanBaseline']['MAE'])
        comparison=existing_comparison(h['target'],test,TY[:,k],pred[:,k],'final');h['testExistingMethod']=comparison
        if comparison['available']:h['accepted'] &= comparison['beatsExisting']
    write('degrees-final-test.json',dict(heads=heads,trainImages=len(train),validationImages=len(val),testImages=len(test),testGroups=len(test_groups),personIndependent=False,cameraDomainAccepted=False,seconds=time.monotonic()-started,localSeverityMap=False,rows=[dict(path=r['path'],group=r['group'],truth=r['grades'],predictions=p.tolist()) for r,p in zip(test,pred)]))
    # Export photo -> features -> fixed scaler/head. No metadata input or map.
    from torch import nn
    class DegreeModel(nn.Module):
        def __init__(self):
            super().__init__();self.backbone=net;self.register_buffer('mean',torch.tensor(mean,dtype=torch.float32));self.register_buffer('std',torch.tensor(std,dtype=torch.float32));self.register_buffer('weights',torch.tensor(W,dtype=torch.float32));self.register_buffer('bias',torch.tensor(B,dtype=torch.float32))
        def forward(self,x):return torch.clamp(((features(self.backbone,name,x)-self.mean)/self.std)@self.weights.T+self.bias,0,5)
    exported=DegreeModel().eval();path=OUT/'degrees.onnx';torch.onnx.export(exported,torch.randn(1,3,224,224),str(path),input_names=['rgb'],output_names=['appearance_grades'],opset_version=17,dynamo=False)
    import onnxruntime as ort
    options=ort.SessionOptions();options.intra_op_num_threads=2;start=time.monotonic();session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);cold=time.monotonic()-start;parity=[];timings=[]
    for r in test[:8]:
        x=image(r)[None].numpy();start=time.monotonic();actual=session.run(None,{'rgb':x})[0];timings.append(time.monotonic()-start)
        with torch.no_grad():expected=exported(torch.from_numpy(x)).numpy()
        parity.append(float(np.max(np.abs(actual-expected))))
    assert max(parity)<1e-3
    write('degrees-export.json',dict(sha256=sha(path),bytes=path.stat().st_size,targets=TARGETS,acceptedTargets=[h['target'] for h in heads if h.get('accepted')],maxAbsParity=max(parity),coldLoadSeconds=cold,warmSeconds=timings,localSeverityMap=False))
    print(json.dumps(dict(heads=[{k:h.get(k) for k in ['target','accepted','validation','test']} for h in heads]),indent=2),flush=True)
if __name__=='__main__':main()
