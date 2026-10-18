"""Development-only matched ImageNet vs type-finetuned feature comparison.

Per-target ridge selection uses identical rows/masks/scalers. No old final
image/label is loaded, and no selected candidate is installed automatically.
"""
import json,time
import numpy as np,torch
from safetensors.torch import load_file
from PIL import Image,ImageDraw
from train_focused_type import model,features,image,scores,CLASSES
from train_focused_degrees import fit,metrics,existing_comparison
from prepare_focused_data import TARGETS,sha
from diagnose_followup import NEW,OLD,write
from train_cached_followup import checkpoint,resume,digest

def extract(net,name,rows,tag):
    identity=digest([{'sha':r['sha256'],'crop':r['crop']} for r in rows])
    path=NEW/f'features/{tag}-final-quality-{identity[:12]}.npz';path.parent.mkdir(exist_ok=True)
    if path.exists():
        f=np.load(path,allow_pickle=False);assert str(f['identity'])==identity;return f['X'].astype(np.float64)
    net.eval();out=[];started=time.monotonic()
    original=NEW/'features'/f'{tag}.npz'
    reviewed=NEW/'development-manifest-exploratory.json'
    # Reuse exact features for surviving source hashes/crops; only compute the
    # restored objectively valid sources. Never silently reinterpret a cache.
    if original.exists() and reviewed.exists():
        task='typeEligible' if tag.endswith(('-type-train','-type-val')) else 'degreeEligible'
        split='train' if tag.endswith('-train') else 'validation'
        before=[r for r in json.loads(reviewed.read_text())['rows'] if r.get(task) and r['split']==split]
        cached=np.load(original,allow_pickle=False);assert str(cached['identity'])==digest([{'sha':r['sha256'],'crop':r['crop']} for r in before])
        mapping={(r['sha256'],tuple(r['crop'])):i for i,r in enumerate(before)}
        with torch.no_grad():
            for row in rows:
                index=mapping.get((row['sha256'],tuple(row['crop'])))
                out.append(cached['X'][index:index+1] if index is not None else features(net,name,image(row)[None]).numpy())
        X=np.concatenate(out).astype(np.float32);np.savez(path,X=X,identity=np.array(identity));write(f'features/{tag}-final-quality-receipt.json',dict(images=len(rows),seconds=time.monotonic()-started,identity=identity,reused=len([r for r in rows if (r['sha256'],tuple(r['crop'])) in mapping])));return X.astype(np.float64)
    with torch.no_grad():
        for start in range(0,len(rows),8):out.append(features(net,name,torch.stack([image(r) for r in rows[start:start+8]])).numpy())
    X=np.concatenate(out).astype(np.float32);np.savez(path,X=X,identity=np.array(identity));write(f'features/{tag}-receipt.json',dict(images=len(rows),seconds=time.monotonic()-started,identity=identity));return X.astype(np.float64)
def main():
    import cv2;cv2.setNumThreads(1)
    torch.set_num_threads(2);torch.manual_seed(20261011);np.random.seed(20261011)
    m=json.loads((NEW/'development-manifest-v2.json').read_text());assert m['oldFinalRowsExcluded'] and all(r['split']!='test' for r in m['rows'])
    degree=[r for r in m['rows'] if r.get('degreeEligible')];train=[r for r in degree if r['split']=='train'];val=[r for r in degree if r['split']=='validation']
    # Training tensor/product tensor comparison on real labelled dev sources.
    import sys;sys.path.insert(0,str(OLD.parents[1]/'services/core-api'));from skin_models import photo_input
    import cv2
    parity=[];sheet=Image.new('RGB',(896,256*4),(12,18,30));draw=ImageDraw.Draw(sheet)
    for k,r in enumerate(train[:4]):
        bgr=cv2.imread(r['absolutePath']);actual,transform=photo_input(bgr,r['landmarks']);expected=image(r).numpy()[None];error=float(np.abs(actual-expected).max());assert error==0
        source=Image.fromarray(bgr[:,:,::-1]);source.thumbnail((220,224));sheet.paste(source,(0,k*256));a,b,c,d=r['crop'];crop=Image.fromarray(bgr[b:d,a:c,::-1]);crop.thumbnail((220,224));sheet.paste(crop,(224,k*256));tensor=((expected[0]*np.array([.229,.224,.225])[:,None,None]+np.array([.485,.456,.406])[:,None,None])*255).transpose(1,2,0);sheet.paste(Image.fromarray(np.clip(np.rint(tensor),0,255).astype(np.uint8)),(448,k*256));draw.text((676,k*256+15),r['sha256'][:20],fill='white');draw.text((676,k*256+35),'RGB224 / identical product input',fill='white');draw.text((676,k*256+55),'classes: normal dry oily combination',fill='white')
        parity.append(dict(sha256=r['sha256'],crop=r['crop'],productTransform=transform,maxAbsTensorDifference=error))
    sheet.save(NEW/'photo-product-tensor-parity.png');write('photo-product-tensor-parity.json',parity)
    results=[]
    for name in ['resnet18','efficientnet_b0']:
        for stage in ['imagenet','type-finetuned']:
            net=model(name)
            if stage=='type-finetuned':net.load_state_dict(load_file(str(OLD/name/'selected.safetensors')))
            tag=name+'-'+stage;X=extract(net,name,train,tag+'-degree-train');VX=extract(net,name,val,tag+'-degree-val');mean=X.mean(0);std=np.maximum(X.std(0),1e-3);X=(X-mean)/std;VX=(VX-mean)/std
            Y=np.array([[np.nan if v is None else v for v in r['grades']] for r in train]);VY=np.array([[np.nan if v is None else v for v in r['grades']] for r in val]);heads=[]
            for k,target in enumerate(TARGETS):
                choices=[];valid=np.isfinite(Y[:,k])
                if valid.sum()>=10:
                    for ridge in [.01,.1,1,10]:
                        w,b=fit(X,Y[:,k],ridge);pred=np.clip(VX@w+b,0,5);score=metrics(VY[:,k],pred)
                        if score['support']:choices.append((score['MAE'],ridge,score,pred))
                if not choices:heads.append(dict(target=target,available=False));continue
                _,ridge,score,pred=min(choices,key=lambda c:c[0]);med=metrics(VY[:,k],np.full(len(val),np.nanmedian(Y[:,k])));avg=metrics(VY[:,k],np.full(len(val),np.nanmean(Y[:,k])));comparison=existing_comparison(target,val,VY[:,k],pred,'selection')
                heads.append(dict(target=target,validation=score,regularization=ridge,trainMedianBaseline=med,trainMeanBaseline=avg,existingMethod=comparison,beatsConstants=score['MAE']<min(med['MAE'],avg['MAE']),productAccepted=False))
            results.append(dict(backbone=name,stage=stage,trainImages=len(train),validationImages=len(val),heads=heads));write('degree-backbone-comparison-final.json',dict(results=results,testOpened=False,independentFinalAvailable=False,normalization='identical train-only feature scaler per backbone',qualityManifestSHA256=sha(NEW/'development-manifest-v2.json'),elasticityNotSagging=True));print('DEGREES',tag,[(h['target'],round(h['validation']['MAE'],3)) for h in heads if 'validation' in h],flush=True)
            # Fully train finite classifier heads after objective cleaning.
            tr=[r for r in m['rows'] if r.get('typeEligible') and r['split']=='train'];va=[r for r in m['rows'] if r.get('typeEligible') and r['split']=='validation']
            TX=extract(net,name,tr,tag+'-type-train');TV=extract(net,name,va,tag+'-type-val');center=TX.mean(0);scale=np.maximum(TX.std(0),.001);TX=torch.tensor((TX-center)/scale,dtype=torch.float32);TV=torch.tensor((TV-center)/scale,dtype=torch.float32);y=torch.tensor([CLASSES.index(r['class']) for r in tr]);vy=np.array([CLASSES.index(r['class']) for r in va]);counts=torch.bincount(y,minlength=4);weights=counts.sum()/(4*counts.float())
            manifest_hash=sha(NEW/'development-manifest-v2.json');folder=NEW/f'type-final-quality/{manifest_hash[:12]}/{tag}';folder.mkdir(parents=True,exist_ok=True);head=torch.nn.Linear(TX.shape[1],4);opt=torch.optim.AdamW(head.parameters(),lr=.001,weight_decay=.1);identity=digest({'manifest':manifest_hash,'tag':tag,'epochs':80,'patience':10,'lr':.001,'weightDecay':.1,'classOrder':CLASSES})
            state=dict(identity=identity,step=0,epoch=0,best=-1,bad=0,history=[])
            if (folder/'CURRENT').exists():state=resume(folder,head,opt,identity)
            while state['epoch']<80 and state['bad']<10:
                losses=[];head.train()
                for ids in torch.randperm(len(y)).split(64):opt.zero_grad();loss=torch.nn.functional.cross_entropy(head(TX[ids]),y[ids],weight=weights);loss.backward();opt.step();losses.append(float(loss.detach()));state['step']+=1
                head.eval()
                with torch.no_grad():logits=head(TV).numpy()
                score=scores(vy,logits);state['epoch']+=1;state['history'].append(dict(epoch=state['epoch'],loss=float(np.mean(losses)),validation=score))
                if score['macroF1']>state['best']+.0001:
                    state['best']=score['macroF1'];state['bad']=0;from safetensors.torch import save_file;save_file(head.state_dict(),str(folder/'selected.safetensors'));np.save(folder/'validation-logits.npy',logits,allow_pickle=False)
                else:state['bad']+=1
                state=checkpoint(folder,head,opt,state)
            write(f'type-final-quality/{manifest_hash[:12]}/{tag}/result.json',dict(complete=True,headOnly=True,manifestSHA256=manifest_hash,epochs=state['epoch'],stop='patience' if state['bad']>=10 else 'finite-epoch-cap',validation=scores(vy,np.load(folder/'validation-logits.npy',allow_pickle=False)),history=state['history'],trainImages=len(tr),validationImages=len(va),classOrder=CLASSES,classCounts=counts.tolist(),independentFinalAvailable=False,productAccepted=False));write(f'type-final-quality/current-{tag}.json',dict(result=str(folder/'result.json'),manifestSHA256=manifest_hash));print('TYPE',tag,state['epoch'],state['best'],flush=True)
            del net,TX,TV
if __name__=='__main__':main()
