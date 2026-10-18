"""Matched clean-v2 development comparison using pinned cached source features."""
import json
import numpy as np
from safetensors.torch import load_file
from prepare_focused_data import TARGETS,sha
from diagnose_followup import NEW,OLD,write
from train_focused_degrees import fit,metrics,existing_comparison
def main():
    v1=json.loads((NEW/'development-manifest-exploratory.json').read_text());v2=json.loads((NEW/'development-manifest-v2.json').read_text());rows=[r for r in v2['rows'] if r.get('degreeEligible')];result=[];weights=[]
    for name in ['resnet18','efficientnet_b0']:
        pre=load_file(str(OLD/'pretrained'/('resnet18-f37072fd.pth.safetensors' if name=='resnet18' else 'efficientnet_b0_rwightman-7f5810bc.pth.safetensors')));fine=load_file(str(OLD/name/'selected.safetensors'));keys=[k for k in fine if not k.startswith(('fc.','classifier.')) and not k.endswith('num_batches_tracked')];changed=[k for k in keys if not __import__('torch').equal(pre[k],fine[k])];weights.append(dict(backbone=name,featureTensors=len(keys),changedFeatureTensors=len(changed),identicalImageNetFeatures=not changed,changedKeys=changed,nonInferenceBatchCountersExcluded=True))
        for stage in ['imagenet','type-finetuned']:
            tag=name+'-'+stage;parts=[];splits=[]
            for split,suffix in [('train','train'),('validation','val')]:
                original=[r for r in v1['rows'] if r.get('degreeEligible') and r['split']==split];clean=[r for r in rows if r['split']==split];indices={r['sha256']:i for i,r in enumerate(original)};cache=np.load(NEW/f'features/{tag}-degree-{suffix}.npz',allow_pickle=False)['X'];parts.append(cache[[indices[r['sha256']] for r in clean]].astype(np.float64));splits.append(clean)
            X,VX=parts;tr,va=splits;mean=X.mean(0);std=np.maximum(X.std(0),.001);X=(X-mean)/std;VX=(VX-mean)/std;Y=np.array([[np.nan if x is None else x for x in r['grades']] for r in tr]);VY=np.array([[np.nan if x is None else x for x in r['grades']] for r in va]);heads=[]
            for k,target in enumerate(TARGETS):
                candidates=[]
                for ridge in [.01,.1,1,10]:
                    w,b=fit(X,Y[:,k],ridge);pred=np.clip(VX@w+b,0,5);score=metrics(VY[:,k],pred);candidates.append((score['MAE'],ridge,score,pred))
                _,ridge,score,pred=min(candidates,key=lambda c:c[0]);median=metrics(VY[:,k],np.full(len(va),np.nanmedian(Y[:,k])));average=metrics(VY[:,k],np.full(len(va),np.nanmean(Y[:,k])));comparison=existing_comparison(target,va,VY[:,k],pred,'selection')
                heads.append(dict(target=target,validation=score,regularization=ridge,medianBaseline=median,meanBaseline=average,beatsConstants=score['MAE']<min(median['MAE'],average['MAE']),existingMethod=comparison,productAccepted=False))
            result.append(dict(backbone=name,stage=stage,trainImages=len(tr),validationImages=len(va),heads=heads))
    write('degree-backbone-comparison-v2.json',dict(results=result,featureWeightComparison=weights,manifestSHA256=sha(NEW/'development-manifest-v2.json'),oldFinalOpened=False,independentFinalAvailable=False,featureSelectionDevelopmentOnly=True,finetunedBackbonesPreviouslySelectedOnOverlappingDevelopmentTypeLabels=True,clinicalGradesExpertProtocolVerified=False,elasticityNotSagging=True))
    print(json.dumps(weights,indent=2),flush=True)
if __name__=='__main__':main()
