import json,sys,os,time,torch
from PIL import Image
import rfdetr
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
torch.set_num_threads(2)
MODELS={'skinmap':('RFDETRSegSmall',f'{S}/weights/attune-skin-regional-skin-map-v1-small/weights.pt'),
 'findings':('RFDETRSmall',f'{S}/weights/attune-skin-findings-boxes-research-v1-small/weights.pt'),
 'acnes':('RFDETRSegSmall',f'{S}/weights/acnes-wscug-bi73e-v1-small/weights.pt'),
 'regional':('RFDETRSmall',f'{S}/weights/regional-r1-v2/weights.pt')}
import os; TAG=os.environ.get('TAG',''); I=json.load(open(f'{S}/rf/items{TAG}.json'))
for name in sys.argv[1].split(','):
  out=f'{S}/rf/pred{TAG}_{name}.json'; P=json.load(open(out)) if os.path.exists(out) else {}
  arch,w=MODELS[name]; M=getattr(rfdetr,arch)(pretrain_weights=w); t=time.time(); n=0
  for it in I:
    k=str(it['id'])
    if k in P: continue
    d=M.predict(Image.open(it['path']).convert('RGB'),threshold=0.05)
    P[k]=[(int(c),round(float(s),4),[round(v,1) for v in b]) for b,s,c in zip(d.xyxy.tolist(),d.confidence,d.class_id)]
    n+=1
    if n%50==0: json.dump(P,open(out,'w')); print(name,n,round((time.time()-t)/n,2),'s/img',flush=True)
  json.dump(P,open(out,'w')); print(name,'done',flush=True)
