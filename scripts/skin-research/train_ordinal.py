"""From-scratch regional ordinal research baseline for expert dry/sag labels."""
import argparse,hashlib,json,random
from pathlib import Path
import numpy as np,cv2,torch
from torch import nn
from train_acne import TinyNet
from prepare_annotations import validate,partitions_are_disjoint
from ordinal_evaluation import evaluate
ROOT=Path(__file__).resolve().parents[2]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--target',choices=['dry','sag'],required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--epochs',type=int,default=16);ap.add_argument('--out',default='audit-results/skin-capabilities-20261008/annotations');args=ap.parse_args();assert 1<=args.epochs<=40
 rows=json.loads(Path(args.manifest).read_text('utf8'));protocol=json.loads((ROOT/'docs/skin-research/annotation-protocol.json').read_text('utf8'));rows,rejected=validate(rows,args.target,protocol)
 out=(ROOT/args.out).resolve();assert out.is_relative_to(ROOT/'audit-results');out.mkdir(exist_ok=True,parents=True)
 if rejected or not all(len({r['caseId'] for r in rows if r.get('split')==s and r['consensusGrade']==g})>=3 for s in ['train','validation','test'] for g in range(4)):
  (out/(args.target+'-training.json')).write_text(json.dumps({'trained':False,'realAnnotations':len(rows),'reason':'insufficient independently annotated real cases per grade/partition','productAccepted':False},indent=2),'utf8');print('Training refused: expert data missing/insufficient');return
 assert all(len({r['split'] for r in rows if r['caseId']==c})==1 for c in {r['caseId'] for r in rows})
 assert partitions_are_disjoint(rows),'Exact/near-duplicate leakage across partitions'
 torch.manual_seed(protocol['seed']);random.seed(protocol['seed']);torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
 images=[]
 for r in rows:
  im=cv2.imread(str(ROOT/r['imagePath']));x,y,w,h=r['regionBox'];assert x>=0 and y>=0 and w>0 and h>0 and x+w<=im.shape[1] and y+h<=im.shape[0]
  images.append(torch.tensor(cv2.cvtColor(cv2.resize(im[y:y+h,x:x+w],(64,64)),cv2.COLOR_BGR2RGB).transpose(2,0,1).copy(),dtype=torch.float32)/255.)
 X=torch.stack(images);Y=torch.tensor([r['consensusGrade'] for r in rows]);model=TinyNet();model.head=nn.Linear(24,4);optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
 train=[i for i,r in enumerate(rows) if r['split']=='train'];validation=[i for i,r in enumerate(rows) if r['split']=='validation'];best=float('inf')
 for _ in range(args.epochs):
  model.train()
  for indexes in torch.tensor(train)[torch.randperm(len(train))].split(16):optimizer.zero_grad();loss=nn.functional.cross_entropy(model(X[indexes]),Y[indexes]);loss.backward();optimizer.step()
  model.eval()
  with torch.no_grad():vl=float(nn.functional.cross_entropy(model(X[validation]),Y[validation]))
  if vl<best:best=vl;torch.save(model.state_dict(),out/(args.target+'.pt'))
 model.load_state_dict(torch.load(out/(args.target+'.pt'),weights_only=True));test=[i for i,r in enumerate(rows) if r['split']=='test']
 with torch.no_grad():pred=model(X[test]).argmax(1).numpy()
 truth=Y[test].numpy();matrix=np.zeros((4,4),int)
 for a,b in zip(truth,pred):matrix[a,b]+=1
 weights=(np.arange(4)[:,None]-np.arange(4)[None,:])**2/9;expected=np.outer(matrix.sum(1),matrix.sum(0))/max(1,matrix.sum());den=(weights*expected).sum();kappa=1-(weights*matrix).sum()/den if den else None
 report={'trained':True,'seed':protocol['seed'],'modelSHA256':hashlib.sha256((out/(args.target+'.pt')).read_bytes()).hexdigest(),'testConfusion':matrix.tolist(),'testMAE':float(np.abs(truth-pred).mean()),'testWeightedKappa':kappa,'unit':'expert-ordinal-grade-0-3','productAccepted':False,'localMap':False,'reason':'requires inter-rater and camera-domain acceptance; regional grade is not a localization map'}
 report['caseWeightedModel']=evaluate(truth,pred,[rows[i]['caseId'] for i in test])
 baseline=int(np.median(Y[train].numpy()));report['trainMedianGradeBaseline']=evaluate(truth,np.full(len(test),baseline),[rows[i]['caseId'] for i in test])
 report['datasetSHA256']=hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest()
 # Numeric-only portable weights. No pickle/object arrays or executable code.
 np.savez_compressed(out/(args.target+'-weights.npz'),**{k:v.detach().cpu().numpy() for k,v in model.state_dict().items()})
 report['portableWeightsSHA256']=hashlib.sha256((out/(args.target+'-weights.npz')).read_bytes()).hexdigest()
 report['partitionCases']={s:len({r['caseId'] for r in rows if r['split']==s}) for s in ['train','validation','test']}
 (out/(args.target+'-training.json')).write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))
if __name__=='__main__':main()
