"""Native local source-PUL texture classification, not moisture or segmentation.

Boxes provide weak ROI presence only. Negative photo review provides presence
controls, never a filled pixel mask. Both domains are grayscale at native 64px.
This limited experiment cannot establish natural dry severity acceptance.
"""
import argparse,collections,json,random,time
from pathlib import Path
import cv2,numpy as np,torch
from torch import nn
from safetensors.torch import load_file,save_file
from expanded_sources import ROOT,OUT,PREVIOUS,write,sha
from prepare_continuation_masks import valid_skin_scope
from training_checkpoint import checkpoint,resume
from skin_acceptance import decide

class TextureNet(nn.Sequential):
 def __init__(self):
  super().__init__(nn.Conv2d(1,16,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),nn.Conv2d(16,32,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),nn.Conv2d(32,32,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d(1),nn.Flatten(),nn.Dropout(.2),nn.Linear(32,2))

def prepare():
 path=OUT/'dry-texture/data.json';folder=path.parent;folder.mkdir(exist_ok=True)
 if path.exists():return json.loads(path.read_text('utf8'))
 cp=OUT/'candidates.json';dp=OUT/'decisions.json';c=json.loads(cp.read_text('utf8'))['rows'];d={r['reviewKey']:r for r in json.loads(dp.read_text('utf8'))['rows']};pos=[r for r in c if r['source']=='merve' and 'dry' in d[r['reviewKey']]['acceptedTargets'] and d[r['reviewKey']]['rightsEligible']]
 negative_path=OUT/'local-control-review/dry-negative-index.json';negative_decisions=OUT/'local-control-review/decisions.json';n=json.loads(negative_path.read_text('utf8'));nd={r['reviewIndex']:r for r in json.loads(negative_decisions.read_text('utf8'))['rows']};neg=[r for r in n if nd[r['reviewIndex']]['eligibleForVisibleFlakeNegative'] and nd[r['reviewIndex']]['rightsEligible']];items=[];patches=[]
 def add(r,rect,label,origin):
  a,b,c,d=rect
  if min(c-a,d-b)<64:return
  gray=cv2.cvtColor(cv2.imread(r['absolutePath']),cv2.COLOR_BGR2GRAY);crop=gray[b:d,a:c];crop=cv2.resize(crop,(64,64),interpolation=cv2.INTER_AREA);patches.append(crop);items.append(dict(sha256=r['sha256'],group=r['group'],split=r['split'],source=r['source'],nativeRect=rect,label=label,labelOrigin=origin,input=64,upsampled=False,pixelTruth=False))
 for r in pos:
  assert sha(Path(r['absolutePath']))==r['sha256']
  for a in r['annotations']:
   if a['label']=='pul' and a['validBox']:
    x,y,w,h=a['bbox'];add(r,[max(0,int(x)),max(0,int(y)),min(r['width'],int(x+w)),min(r['height'],int(y+h))],1,'reviewed source PUL box, weak texture presence only')
 for r in neg:
  assert sha(Path(r['absolutePath']))==r['sha256'];scope=valid_skin_scope(r);points=r['landmarks']
  for index in [10,205,425]:
   x=int(points[index]['x']*r['width']);y=int(points[index]['y']*r['height']);a=max(0,x-40);b=max(0,y-40);c=min(r['width'],a+80);d=min(r['height'],b+80)
   if scope[b:d,a:c].mean()>=.75:add(r,[a,b,c,d],0,'visually reviewed no-visible-flaking photo; local observed skin presence control, no pixel mask')
 train_groups={r['group'] for r in items if r['split']=='train'};val_groups={r['group'] for r in items if r['split']=='validation'};assert not train_groups&val_groups
 np.save(folder/'pixels.npy',np.stack(patches),allow_pickle=False);data=dict(rows=items,counts={s:{str(label):dict(photos=len({r['sha256'] for r in items if r['split']==s and r['label']==label}),groups=len({r['group'] for r in items if r['split']==s and r['label']==label}),patches=sum(r['split']==s and r['label']==label for r in items)) for label in [0,1]} for s in ['train','validation']},pixelSHA256=sha(folder/'pixels.npy'),reviewSHA256=sha(dp),negativeReviewSHA256=sha(negative_decisions),sourceClassNotExpertTruth=True,sourceProcessingConfounderUnresolved=True,clinicalMoisture=False,calibratedSeverity=False,testPixelsOpened=False);write('dry-texture/data.json',data);return data

def main(seconds):
 torch.set_num_threads(1);cv2.setNumThreads(1);torch.manual_seed(20261011);random.seed(20261011);np.random.seed(20261011);data=prepare();folder=OUT/'dry-texture';rows=data['rows'];x=torch.from_numpy(np.load(folder/'pixels.npy').copy())[:,None].float()/255;y=torch.tensor([r['label'] for r in rows]);tr=[i for i,r in enumerate(rows) if r['split']=='train'];va=[i for i,r in enumerate(rows) if r['split']=='validation'];assert all(any(rows[i]['label']==k for i in tr) and any(rows[i]['label']==k for i in va) for k in [0,1]);net=TextureNet();initial={k:v.clone() for k,v in net.state_dict().items()};opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.01);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,32);protocol=dict(dataSHA256=sha(folder/'data.json'),pixelsSHA256=data['pixelSHA256'],version='weak-native-source-PUL-gray64-v1',minimumEpochs=12,maximumEpochs=32,patience=8,optimizer='AdamW',lr=.001,weightDecay=.01,confidenceNotSeverity=True,normalAPIModified=False);write('dry-texture/protocol.json',protocol);identity=sha(folder/'protocol.json');state=dict(identity=identity,step=0,epoch=0,cursor=0,order=[],losses=[],history=[],best=-1.,bad=0,seconds=0.,scheduler=sched.state_dict());started=time.monotonic();previous=0.
 def advance(ids):
  net.train();opt.zero_grad();loss=nn.functional.cross_entropy(net(x[ids]),y[ids]);assert torch.isfinite(loss);loss.backward();nn.utils.clip_grad_norm_(net.parameters(),1,error_if_nonfinite=True);opt.step();return float(loss.detach())
 def metrics():
  net.eval()
  with torch.inference_mode():p=net(x[va]).softmax(1)[:,1].numpy()
  buckets=collections.defaultdict(list)
  for i,v in zip(va,p):buckets[(rows[i]['group'],rows[i]['label'])].append(float(v))
  truth=np.array([k[1] for k in buckets]);pred=np.array([np.median(v)>=.5 for v in buckets.values()]);tp=int((pred&(truth==1)).sum());fp=int((pred&(truth==0)).sum());fn=int((~pred&(truth==1)).sum());tn=int((~pred&(truth==0)).sum());precision=tp/max(tp+fp,1);recall=tp/max(tp+fn,1)
  return dict(scope='weak source-group development texture presence; not severity or mask',F1=2*precision*recall/max(precision+recall,1e-12),precision=precision,recall=recall,confusionMatrix=[[tn,fp],[fn,tp]],positiveGroups=int((truth==1).sum()),negativeGroups=int((truth==0).sum()),negativeFPR=fp/max(fp+tn,1))
 def save():
  state['seconds']=previous+time.monotonic()-started;state['scheduler']=sched.state_dict();checkpoint(folder,net,opt,state)
 if (folder/'selection.json').exists():print('Completed limited local texture experiment preserved');return
 if (folder/'CURRENT').exists():state=resume(folder,net,opt,identity);sched.load_state_dict(state['scheduler']);previous=state['seconds']
 else:
  tiny=[next(i for i in tr if rows[i]['label']==k) for k in [0,1]];losses=[advance(tiny) for _ in range(160)];passed=np.mean(losses[-5:])<np.mean(losses[:5])*.5;write('dry-texture/learning.json',dict(first=float(np.mean(losses[:5])),last=float(np.mean(losses[-5:])),passed=bool(passed),trainOnly=True,resetBeforeBroad=True));assert passed;net.load_state_dict(initial);opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.01);sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,32);save_file(initial,str(folder/'feature-initial.safetensors'));save()
 while state['epoch']<32 and (state['epoch']<12 or state['bad']<8):
  if not state['order']:
   by={k:[i for i in tr if rows[i]['label']==k] for k in [0,1]};order=[]
   for _ in range(max(map(len,by.values()))):order.extend([random.choice(by[0]),random.choice(by[1])])
   random.shuffle(order);state.update(order=order,cursor=0,losses=[])
  while state['cursor']<len(state['order']):
   if time.monotonic()-started>=seconds:save();write('dry-texture/stop.json',dict(trainingComplete=False,reason='RESUMABLE_TIME_SLICE'));return
   ids=state['order'][state['cursor']:state['cursor']+8];state['losses'].append(advance(ids));state['cursor']+=len(ids);state['step']+=1
  value=metrics();state['epoch']+=1;state['history'].append(dict(epoch=state['epoch'],loss=float(np.mean(state['losses'])),validation=value))
  if value['F1']>state['best']+1e-5:state['best']=value['F1'];state['bad']=0;save_file(net.state_dict(),str(folder/'selected.safetensors'))
  else:state['bad']+=1
  sched.step();state.update(order=[],cursor=0);save();write('dry-texture/history.json',state['history']);print('weak dry texture epoch',state['epoch'],value['F1'],flush=True)
 selected=load_file(str(folder/'selected.safetensors'));net.load_state_dict(selected);changes={k:float((selected[k]-initial[k]).abs().max()) for k in ['0.weight','3.weight','6.weight','11.weight']};assert all(v>0 for v in changes.values());write('dry-texture/selection.json',dict(trainingComplete=True,epochs=state['epoch'],features=changes,weightsSHA256=sha(folder/'selected.safetensors'),validation=metrics(),experimentLimited=True,architectureRejected=False,productionAccepted=False,naturalPositiveSeverityCalibrationMissing=True))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=3600);main(p.parse_args().seconds)
