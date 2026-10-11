"""Separate natural-negative presence phase from an exact completed checkpoint.

No mask or severity is inferred from presence. The original weak PUL labels and
processing confounder remain disclosed. Parent weights/AdamW/scheduler/RNG are
inherited; no overfit reset, product promotion or final-photo access occurs.
"""
import argparse,collections,json,random,time
from pathlib import Path
import cv2,numpy as np,torch
from safetensors.torch import load_file,save_file
from expanded_sources import ROOT,OUT,write,sha
from train_dry_texture import TextureNet
from prepare_continuation_masks import valid_skin_scope
from training_checkpoint import checkpoint,resume
NAME='negative-dry-presence'


def prepare():
 folder=OUT/NAME;folder.mkdir(exist_ok=True)
 if (folder/'data.json').exists():return json.loads((folder/'data.json').read_text('utf8'))
 old=OUT/'dry-texture';data=json.loads((old/'data.json').read_text('utf8'));rows=list(data['rows']);pixels=list(np.load(old/'pixels.npy'));negative=json.loads((OUT/'negative-expanded-mask-data.json').read_text('utf8'));candidates=json.loads((OUT/'negative-expansion/candidates.json').read_text('utf8'))['rows'];by={r['sha256']:r for r in candidates};oldgroups={r['group'] for r in rows}
 for r in negative['preparedNegativePhotos']:
  if 'dry' not in r['targets'] or r['group'] in oldgroups:continue
  source={**by[r['sha256']],**r};assert source['split']!='test' and sha(Path(source['absolutePath']))==r['sha256'];scope=valid_skin_scope(source);gray=cv2.cvtColor(cv2.imread(source['absolutePath']),cv2.COLOR_BGR2GRAY)
  for index in [10,205,425]:
   x=int(r['landmarks'][index]['x']*source['width']);y=int(r['landmarks'][index]['y']*source['height']);a=max(0,x-40);b=max(0,y-40);c=min(source['width'],a+80);d=min(source['height'],b+80)
   if min(c-a,d-b)<64 or scope[b:d,a:c].mean()<.75:continue
   pixels.append(cv2.resize(gray[b:d,a:c],(64,64),interpolation=cv2.INTER_AREA));rows.append(dict(sha256=r['sha256'],group=r['group'],split=r['split'],source=source['source'],nativeRect=[a,b,c,d],label=0,labelOrigin='hash-bound visually reviewed no-visible-flaking natural photo / observed skin ROI; presence only',input=64,upsampled=False,pixelTruth=False))
 assert not {r['group'] for r in rows if r['split']=='train'}&{r['group'] for r in rows if r['split']=='validation'}
 np.save(folder/'pixels.npy',np.stack(pixels),allow_pickle=False)
 result={**data,'rows':rows,'version':'native-gray64-natural-negative-presence-phase-v1','parentDataSHA256':sha(old/'data.json'),'negativeReviewSHA256':negative['negativeReviewSHA256'],'pixelSHA256':sha(folder/'pixels.npy'),'counts':{s:{str(k):dict(photos=len({r['sha256'] for r in rows if r['split']==s and r['label']==k}),groups=len({r['group'] for r in rows if r['split']==s and r['label']==k}),patches=sum(r['split']==s and r['label']==k for r in rows)) for k in [0,1]} for s in ['train','validation']},'nativeNegativePreparationIsNotPixelTrainingTruth':True,'phaseSeparate':True};write(NAME+'/data.json',result);return result


def main(seconds):
 torch.set_num_threads(1);cv2.setNumThreads(1);data=prepare();folder=OUT/NAME
 if (folder/'selection.json').exists():print('Completed negative presence phase preserved');return
 rows=data['rows'];x=torch.from_numpy(np.load(folder/'pixels.npy').copy())[:,None].float()/255;y=torch.tensor([r['label'] for r in rows]);tr=[i for i,r in enumerate(rows) if r['split']=='train'];va=[i for i,r in enumerate(rows) if r['split']=='validation'];net=TextureNet();opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.01);scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(opt,32)
 protocol=dict(version=data['version'],dataSHA256=sha(folder/'data.json'),minimumEpochs=12,maximumEpochs=20,patience=8,optimizerSchedulerRNGInherited=True,weightsNotReset=True,groupBalancedBeforeRepeat=True,originalCosineScheduleContinuesWithoutReset=True,inheritedCosineHorizon=32,postHorizonCosineIncreaseExplicit=True,confidenceNotSeverity=True,independentFinal=False);write(NAME+'/protocol.json',protocol);identity=sha(folder/'protocol.json');started=time.monotonic();previous=0.
 def save():
  state['scheduler']=scheduler.state_dict();state['seconds']=previous+time.monotonic()-started;checkpoint(folder,net,opt,state)
 if (folder/'CURRENT').exists():state=resume(folder,net,opt,identity);scheduler.load_state_dict(state['scheduler']);previous=state['seconds']
 else:
  parent=OUT/'dry-texture';gen=parent/(parent/'CURRENT').read_text('utf8');ps=json.loads((gen/'state.json').read_text('utf8'));assert not ps['order'] and ps['cursor']==0;pin=folder/'frozen-parent'/gen.name;pin.mkdir(parents=True,exist_ok=True)
  for name in ['model.safetensors','optimizer.safetensors','state.json']:
   if not (pin/name).exists():(pin/name).hardlink_to(gen/name)
  (pin.parent/'CURRENT').write_text(gen.name,'utf8');inherited=resume(pin.parent,net,opt,ps['identity']);scheduler.load_state_dict(inherited['scheduler']);previous=inherited['seconds'];save_file(net.state_dict(),str(folder/'feature-initial.safetensors'));state=dict(identity=identity,epoch=0,step=inherited['step'],cursor=0,order=[],losses=[],history=[],best=-1.,bad=0,actualConsumedROIIDs=[],groupQueues={})
  write(NAME+'/parent-receipt.json',dict(modelSHA256=inherited['modelSHA256'],optimizerSHA256=inherited['optimizerSHA256'],parentEpoch=inherited['epoch'],schedulerLastEpoch=scheduler.last_epoch,weightsOptimizerSchedulerRNGPreserved=True,originalSelectionUnmodified=True));save()
 by={k:collections.defaultdict(list) for k in [0,1]}
 for i in tr:by[rows[i]['label']][rows[i]['group']].append(i)
 def next_group(k):
  queue=state['groupQueues'].setdefault(str(k),[])
  if not queue:queue.extend(random.sample(sorted(by[k]),len(by[k])))
  return random.choice(by[k][queue.pop()])
 def metrics():
  net.eval()
  with torch.inference_mode():prob=net(x[va]).softmax(1)[:,1].numpy()
  groups=collections.defaultdict(list)
  for i,v in zip(va,prob):groups[(rows[i]['group'],rows[i]['label'])].append(float(v))
  truth=np.array([k[1] for k in groups]);pred=np.array([np.median(v)>=.5 for v in groups.values()]);tp=int((pred&(truth==1)).sum());fp=int((pred&(truth==0)).sum());fn=int((~pred&(truth==1)).sum());tn=int((~pred&(truth==0)).sum());p=tp/max(1,tp+fp);r=tp/max(1,tp+fn)
  return dict(scope='source-group development weak texture presence with expanded natural negatives; no severity',precision=p,recall=r,F1=2*p*r/max(p+r,1e-12),confusionMatrix=[[tn,fp],[fn,tp]],positiveGroups=int((truth==1).sum()),negativeGroups=int((truth==0).sum()),negativeFPR=fp/max(1,fp+tn))
 while state['epoch']<20 and (state['epoch']<12 or state['bad']<8):
  if not state['order']:
   order=[next_group(k) for _ in range(max(len(by[0]),len(by[1]))) for k in [0,1]];random.shuffle(order);state.update(order=order,cursor=0,losses=[])
  while state['cursor']<len(state['order']):
   if time.monotonic()-started>=seconds:save();write(NAME+'/stop.json',dict(reason='RESUMABLE_INVOCATION_TIME_SLICE',trainingComplete=False));return
   ids=state['order'][state['cursor']:state['cursor']+8];net.train();opt.zero_grad();loss=torch.nn.functional.cross_entropy(net(x[ids]),y[ids]);assert torch.isfinite(loss);loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),1,error_if_nonfinite=True);opt.step();state['losses'].append(float(loss.detach()));state['actualConsumedROIIDs']=sorted(set(state['actualConsumedROIIDs'])|set(ids));state['cursor']+=len(ids);state['step']+=1
  m=metrics();state['epoch']+=1;state['history'].append(dict(phase=NAME,epoch=state['epoch'],loss=float(np.mean(state['losses'])),validation=m))
  if m['F1']>state['best']+1e-5:state['best']=m['F1'];state['bad']=0;save_file(net.state_dict(),str(folder/'selected.safetensors'))
  else:state['bad']+=1
  scheduler.step();state.update(order=[],cursor=0);save();print('Natural-negative presence phase',state['epoch'],m['F1'],flush=True)
 selected=load_file(str(folder/'selected.safetensors'));initial=load_file(str(folder/'feature-initial.safetensors'));changes={key:float((selected[key]-initial[key]).abs().max()) for key in ['0.weight','3.weight','6.weight','11.weight']};winner=max(state['history'],key=lambda v:v['validation']['F1']);write(NAME+'/selection.json',dict(trainingComplete=True,epochs=state['epoch'],selectedEpoch=winner['epoch'],validation=winner['validation'],features=changes,weightsSHA256=sha(folder/'selected.safetensors'),actualConsumedROIIDs=state['actualConsumedROIIDs'],probabilityNotSeverity=True,sourceProcessingConfounderUnresolved=True,acceptanceDecisionRequired=True));write(NAME+'/history.json',state['history']);write(NAME+'/label-function-evidence-v2.json',dict(method=dict(labelType='ROIPresence',functions=['presence']),metrics=winner['validation'],data=dict(engineeringLabelsDisclosed=True,sourceReviewComplete=True,labelSemanticsMatched=True,naturalCameraDomainReviewed=False,unusedHoldout=False),export={},product={}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=3600);main(p.parse_args().seconds)
