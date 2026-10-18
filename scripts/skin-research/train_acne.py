"""Small, from-scratch CPU baseline. Never installs a model in the product.
Case + exact/near-image duplicate components split before training. No identity
recognition. Labels are case differential diagnoses, not image lesion truth.
"""
import argparse, collections, hashlib, json, math, random, time
from pathlib import Path
import cv2, numpy as np, torch
from torch import nn
ROOT=Path(__file__).resolve().parents[2]

def binary_metrics(y,p,threshold):
 y=np.asarray(y);p=np.asarray(p);pred=p>=threshold;tp=int(sum(pred&(y==1)));fp=int(sum(pred&(y==0)));fn=int(sum(~pred&(y==1)));tn=int(sum(~pred&(y==0)))
 precision=tp/max(1,tp+fp);recall=tp/max(1,tp+fn)
 pos=p[y==1];neg=p[y==0];auc=float(np.mean([(x>neg).mean()+.5*(x==neg).mean() for x in pos])) if len(pos) and len(neg) else None
 ece=0.
 for left in np.arange(0,1,.1):
  mask=(p>=left)&(p<left+.1+(1e-8 if left>.89 else 0))
  if mask.any():ece+=float(mask.mean()*abs(y[mask].mean()-p[mask].mean()))
 def wilson(k,n):
  if not n:return 0.
  z=1.96;v=k/n;return (v+z*z/(2*n)-z*math.sqrt(v*(1-v)/n+z*z/(4*n*n)))/(1+z*z/n)
 return {'cases':len(y),'positiveCases':int(sum(y==1)),'negativeCases':int(sum(y==0)),'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':precision,'recall':recall,'F1':2*precision*recall/max(1e-10,precision+recall),'AUC':auc,'Brier':float(np.mean((y-p)**2)),'ECE':ece,'precisionWilsonLower':wilson(tp,tp+fp),'recallWilsonLower':wilson(tp,tp+fn)}

class TinyNet(nn.Module):
 def __init__(self):
  super().__init__();self.features=nn.Sequential(nn.Conv2d(3,8,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),nn.Conv2d(8,16,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),nn.Conv2d(16,24,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d(1));self.head=nn.Linear(24,1)
 def forward(self,x):return self.head(self.features(x).flatten(1)).flatten()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',default='audit-results/skin-capabilities-20261008/scin/fullface-manifest.json');ap.add_argument('--epochs',type=int,default=16);ap.add_argument('--out',default='audit-results/skin-capabilities-20261008/acne-full-face');ap.add_argument('--candidate-diagnostic-only',action='store_true',help='Reproduce rejected Haar/macro candidate baseline; never facial validity');args=ap.parse_args()
 assert 1<=args.epochs<=40
 out=(ROOT/args.out).resolve();assert out.is_relative_to(ROOT/'audit-results');out.mkdir(parents=True,exist_ok=True)
 criteria=json.loads((Path(__file__).parent/'acceptance.json').read_text());seed=criteria['seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
 manifest=Path(args.manifest);all_rows=json.loads(manifest.read_text('utf8'));parent={r['case_id']:r['case_id'] for r in all_rows}
 def find(x):
  while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
  return x
 def union(a,b):parent[find(b)]=find(a)
 duplicates=0
 for i,a in enumerate(all_rows):
  for b in all_rows[:i]:
   if a['case_id']!=b['case_id'] and (a['sha256']==b['sha256'] or (a['phash']^b['phash']).bit_count()<=4):union(a['case_id'],b['case_id']);duplicates+=1
 rows=[r for r in all_rows if r['eligible'] and (r.get('fullFaceGeometry') is True or args.candidate_diagnostic_only)];groups=collections.defaultdict(list)
 for r in rows:groups[find(r['case_id'])].append(r)
 ambiguous=[key for key,group in groups.items() if len({r['target'] for r in group})>1]
 for key in ambiguous:del groups[key]
 split={};rng=random.Random(seed)
 for label in [0,1]:
  keys=sorted(k for k,v in groups.items() if v[0]['target']==label);rng.shuffle(keys);n=len(keys);train_end=int(n*.6);val_end=int(n*.8)
  for i,k in enumerate(keys):split[k]='train' if i<train_end else 'validation' if i<val_end else 'test'
 selected=[{**r,'group':find(r['case_id']),'split':split[find(r['case_id'])]} for v in groups.values() for r in v]
 assert not any({r['split'] for r in selected if r['case_id']==case}.__len__()>1 for case in parent)
 (out/'split-manifest.json').write_text(json.dumps(selected,indent=2),'utf8');(out/'acceptance.json').write_text(json.dumps(criteria,indent=2),'utf8')
 if any(len({r['case_id'] for r in selected if r['split']==s and r['target']==y})<2 for s in ['train','validation','test'] for y in [0,1]):
  (out/'report.json').write_text(json.dumps({'trained':False,'reason':'Fewer than two real cases per class in a required partition','criteria':criteria,'counts':{str(k):v for k,v in collections.Counter((r['split'],r['target']) for r in selected).items()}},default=str),'utf8');print('Training refused: insufficient real cases per partition',flush=True);return
 reports={};start=time.perf_counter()
 for mode in ['face','background-only']:
  tensors=[]
  for r in selected:
   path=(ROOT/r['image_path']).resolve();assert path.is_relative_to(ROOT/'audit-results') and hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256'];assert r['license']=='SCIN Data Use License'
   im=cv2.imread(str(ROOT/r['image_path']));x,y,w,h=r['face_box'];
   if mode=='face':im=im[y:y+h,x:x+w]
   else:im=im.copy();im[y:y+h,x:x+w]=0
   im=cv2.cvtColor(cv2.resize(im,(64,64),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2RGB)
   tensors.append(torch.tensor(im.transpose(2,0,1).copy(),dtype=torch.float32)/255.)
  X=torch.stack(tensors);Y=torch.tensor([r['target'] for r in selected],dtype=torch.float32);train=[i for i,r in enumerate(selected) if r['split']=='train'];val=[i for i,r in enumerate(selected) if r['split']=='validation']
  # Weight each case equally even when it has multiple images.
  counts=collections.Counter(r['case_id'] for r in selected);weight=torch.tensor([1/counts[r['case_id']] for r in selected]);positive=float(sum(Y[train]*weight[train]));pos_weight=(float(weight[train].sum())-positive)/max(1,positive)
  torch.manual_seed(seed);model=TinyNet();opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01);criterion=nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight),reduction='none');best=float('inf');history=[]
  for epoch in range(args.epochs):
   model.train();order=torch.tensor(train)[torch.randperm(len(train))];losses=[]
   for indexes in order.split(16):
    opt.zero_grad();loss=(criterion(model(X[indexes]),Y[indexes])*weight[indexes]).sum()/weight[indexes].sum();loss.backward();opt.step();losses.append(float(loss.detach()))
   model.eval()
   with torch.no_grad():vl=float(nn.functional.binary_cross_entropy_with_logits(model(X[val]),Y[val]))
   history.append({'epoch':epoch+1,'trainLoss':float(np.mean(losses)),'validationLoss':vl})
   if vl<best:best=vl;torch.save(model.state_dict(),out/(mode+'.pt'))
  model.load_state_dict(torch.load(out/(mode+'.pt'),weights_only=True));model.eval()
  with torch.no_grad():logits=model(X).numpy()
  # Calibration and threshold selection use validation cases only.
  temps=np.arange(.5,3.01,.1);temperature=float(min(temps,key=lambda t:np.mean(np.logaddexp(0,logits[val]/t)-Y[val].numpy()*logits[val]/t)))
  probs=1/(1+np.exp(-logits/temperature));case_scores={}
  for r,p in zip(selected,probs):case_scores.setdefault(r['case_id'],{'label':r['target'],'split':r['split'],'tone':r['tone'],'shotType':r['shotType'],'p':[]})['p'].append(float(p))
  cases=[{'case':k,**v,'p':float(np.mean(v['p']))} for k,v in case_scores.items()];validation=[r for r in cases if r['split']=='validation']
  threshold=float(max(np.arange(.05,.96,.05),key=lambda t:binary_metrics([r['label'] for r in validation],[r['p'] for r in validation],t)['F1']))
  report={s:binary_metrics([r['label'] for r in cases if r['split']==s],[r['p'] for r in cases if r['split']==s],threshold) for s in ['train','validation','test']};report.update(threshold=threshold,temperature=temperature,parameters=sum(p.numel() for p in model.parameters()),modelSHA256=hashlib.sha256((out/(mode+'.pt')).read_bytes()).hexdigest(),modelBytes=(out/(mode+'.pt')).stat().st_size,history=history)
  test=[r for r in cases if r['split']=='test'];report['toneSubgroups']={tone:binary_metrics([r['label'] for r in test if r['tone']==tone],[r['p'] for r in test if r['tone']==tone],threshold) for tone in sorted({r['tone'] for r in test})};report['shotSubgroups']={shot:binary_metrics([r['label'] for r in test if r['shotType']==shot],[r['p'] for r in test if r['shotType']==shot],threshold) for shot in sorted({r['shotType'] for r in test})}
  (out/(mode+'-predictions-private.json')).write_text(json.dumps(cases,indent=2),'utf8');reports[mode]=report;print(mode,json.dumps(report['test']),flush=True)
  del X,Y,model,tensors
 face=reports['face']['test'];bg=reports['background-only']['test'];reasons=[]
 if min(face['positiveCases'],face['negativeCases'])<criteria['minIndependentTestCasesEachClass']:reasons.append('insufficient independent test cases')
 for key,minimum in [('precision',criteria['minPrecision']),('recall',criteria['minRecall']),('F1',criteria['minF1']),('precisionWilsonLower',criteria['minWilsonLowerPrecisionRecall']),('recallWilsonLower',criteria['minWilsonLowerPrecisionRecall'])]:
  if face[key]<minimum:reasons.append(key+' below preregistered acceptance')
 if face['ECE']>criteria['maxECE']:reasons.append('calibration ECE above acceptance')
 if bg['AUC'] is None or bg['AUC']>criteria['maxBackgroundOnlyAUC']:reasons.append('background-only control not passed')
 for kind in ['toneSubgroups','shotSubgroups']:
  for group,metric in reports['face'][kind].items():
   if min(metric['positiveCases'],metric['negativeCases'])<criteria['subgroups']['minCasesEachClass']:reasons.append(kind+' '+group+' insufficient cases')
   elif metric['recall']<criteria['subgroups']['minRecall']:reasons.append(kind+' '+group+' recall below acceptance')
 reasons+=['face candidates lack expert image/lesion review','no independent webcam-domain evaluation','no localization/count/severity labels']
 report={'trained':True,'fromScratch':True,'pretrainedWeights':False,'localCPU':True,'seed':seed,'seconds':time.perf_counter()-start,'manifestSHA256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'acceptanceSHA256':hashlib.sha256((Path(__file__).parent/'acceptance.json').read_bytes()).hexdigest(),'nearDuplicateCrossCasePairs':duplicates,'conflictingDuplicateComponentsRemoved':len(ambiguous),'caseLeakageAcrossSplits':False,'splitCases':{s:len({r['case_id'] for r in selected if r['split']==s}) for s in ['train','validation','test']},'reports':reports,'productAccepted':False,'reasons':reasons,'modelLicense':'SCIN Data Use License preserved for these derivative research weights; product code license separate; no product distribution','localMap':False,'meaning':'Acne expert case differential proxy classification; not severity or presence confirmation','cameraMetadataAvailable':False}
 report['wholeFaceValidationInvalidated']=args.candidate_diagnostic_only
 report['trainingCodeSHA256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 if args.candidate_diagnostic_only:report['validationInvalidationReason']='Unreviewed Haar/macro/ear candidate diagnostic. These metrics are not facial acne validity.'
 (out/'report.json').write_text(json.dumps(report,indent=2),'utf8');print('Research training completed; product gate CLOSED',flush=True)
if __name__=='__main__':main()
