"""Free local test of anismizi/skin-type-classifier (ResNet50, dry vs oily) as DRY evidence.
Scores: P(dry) on (a) the masked region crop and (b) the whole face crop. Evaluated as dry-vs-normal on our
region testbed and checked on Customer Profiles (does it call everyone dry?)."""
import json,sys,os,numpy as np,cv2,torch,torch.nn as nn
from PIL import Image
from torchvision.models import resnet50
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
m=resnet50(weights=None); m.fc=nn.Linear(m.fc.in_features,2)
sd=torch.load(f'{S}/hfm/anismizi/pytorch_model.bin',map_location='cpu'); sd={k.replace('resnet.',''):v for k,v in sd.items()}
print(m.load_state_dict(sd,strict=True)); m.eval(); torch.set_num_threads(2)
MEAN=np.array([0.485,0.456,0.406],np.float32); STD=np.array([0.229,0.224,0.225],np.float32)
def score(crops):
  out=[]
  with torch.no_grad():
    for i in range(0,len(crops),32):
      x=np.stack([(cv2.resize(c,(224,224),interpolation=cv2.INTER_AREA).astype(np.float32)/255-MEAN)/STD for c in crops[i:i+32]]).transpose(0,3,1,2)
      out+=torch.softmax(m(torch.from_numpy(x)),1)[:,0].tolist()
  return out
def run(tag):
  I={it['id']:it for it in json.load(open(f'{S}/rf/items{tag}.json'))}; F=json.load(open(f'{S}/rf/feats2{tag}.json'))
  reg=[];face=[];cache={}
  for r in F:
    it=I[r['id']]
    if r['id'] not in cache:
      img=np.array(Image.open(it['path']).convert('RGB')); allp=np.vstack([np.array(v) for v in it['regions'].values()])
      x0,y0=allp.min(0); x1,y1=allp.max(0); s=max(x1-x0,y1-y0)*1.15; cx,cy=(x0+x1)/2,(y0+y1)/2
      X0,Y0=int(max(0,cx-s/2)),int(max(0,cy-s/2)); fc=img[Y0:int(cy+s/2),X0:int(cx+s/2)]
      cache.clear(); cache[r['id']]=(img,fc)
    img,fc=cache[r['id']]; poly=np.array(it['regions'][r['region']],np.int32)
    mk=np.zeros(img.shape[:2],np.uint8); cv2.fillPoly(mk,[poly],1)
    if r['region'] in it['holes']: cv2.fillPoly(mk,[np.array(it['holes'][r['region']],np.int32)],0)
    ys,xs=np.where(mk>0); c=img[ys.min():ys.max()+1,xs.min():xs.max()+1].copy(); c[mk[ys.min():ys.max()+1,xs.min():xs.max()+1]==0]=0
    reg.append(c); face.append(fc)
  sr=score(reg); sf=score(face)
  for r,a,b in zip(F,sr,sf): r['f']['anis_dry_region']=float(a); r['f']['anis_dry_face']=float(b)
  json.dump(F,open(f'{S}/rf/feats2{tag}.json','w')); print(tag,'scored',len(F))
for t in sys.argv[1:]: run('' if t=='testbed' else t)
