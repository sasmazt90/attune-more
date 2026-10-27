"""Step 3: per-region features: CV (relative to the person's own skin), detector evidence, DINOv2 crop embedding."""
import json,sys,os,numpy as np,cv2
from PIL import Image
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
import os; TAG=os.environ.get('TAG',''); I=json.load(open(f'{S}/rf/items{TAG}.json'))
P={m:json.load(open(f'{S}/rf/pred{TAG}_{m}.json')) for m in ('skinmap','findings','acnes','regional')}
def cats(ds):
  J=json.load(open(f'{ds}/valid/_annotations.coco.json')); import collections
  c=collections.Counter(a['category_id'] for a in J['annotations']); out={}
  for x in J['categories']:
    n=x['name']
    if n not in out or c[x['id']]>c[out[n]]: out[n]=x['id']
  return {v:k for k,v in out.items()}
CAT={'skinmap':cats(f'{S}/evalds/skinmap'),'findings':cats(f'{S}/evalds/findings'),'acnes':cats(f'{S}/evalds/acnes'),'regional':{1:'dry',2:'oily'}}
FACE=['forehead','nose','cheek_imgL','cheek_imgR','chin']
def rmask(it,k,sc,shape):
  m=np.zeros(shape,np.uint8); cv2.fillPoly(m,[(np.array(it['regions'][k])*sc).astype(np.int32)],1)
  if k in it['holes']: cv2.fillPoly(m,[(np.array(it['holes'][k])*sc).astype(np.int32)],0)
  return m.astype(bool)
DO_DINO='--dino' in sys.argv
if DO_DINO:
  import torch; from transformers import AutoImageProcessor, AutoModel
  proc=AutoImageProcessor.from_pretrained('facebook/dinov2-small'); dm=AutoModel.from_pretrained('facebook/dinov2-small').eval(); torch.set_num_threads(2)
rows=[]; crops=[]
for it in I:
  img=np.array(Image.open(it['path']).convert('RGB')); sc=400/max(it['faceW'],1)
  im=cv2.resize(img,(max(1,round(it['w']*sc)),max(1,round(it['h']*sc))),interpolation=cv2.INTER_AREA if sc<1 else cv2.INTER_CUBIC)
  lab=cv2.cvtColor(im,cv2.COLOR_RGB2LAB).astype(np.float32); L=lab[...,0]*100/255; A=lab[...,1]-128; B=lab[...,2]-128; C=np.hypot(A,B)
  hp=L-cv2.GaussianBlur(L,(0,0),3); th=cv2.morphologyEx(L,cv2.MORPH_TOPHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
  masks={k:rmask(it,k,sc,L.shape) for k in it['regions']}
  fm=np.zeros(L.shape,bool)
  for k in FACE: fm|=masks[k]
  if fm.sum()<500: continue
  Lm,Ls=np.median(L[fm]),np.std(L[fm])+1e-6; Am=np.median(A[fm]); Cm=np.median(C[fm]); hps=np.std(hp[fm])+1e-6
  for k,m in masks.items():
    if m.sum()<150: continue
    l=L[m]; f={}
    spec=(l>Lm+1.6*Ls)&(C[m]<Cm)
    f['cv_shine']=float(spec.mean()); f['cv_p99']=float((np.percentile(l,99)-Lm)/Ls); f['cv_lrel']=float((l.mean()-Lm)/Ls)
    f['cv_tex']=float(np.std(hp[m])/hps); f['cv_texabs']=float(np.std(hp[m])); f['cv_flake']=float(((th[m]>6)&(C[m]<Cm)).mean())
    f['cv_red']=float(A[m].mean()-Am); f['cv_redp90']=float(np.percentile(A[m],90)-Am)
    # detector evidence: coverage of boxes(thr) inside region + max conf overlapping
    for mn,cmap in CAT.items():
      dets=P[mn].get(str(it['id']),[])
      for cname in set(cmap.values()):
        cov=np.zeros(L.shape,np.float32); cnt=0
        for c,s,(x0,y0,x1,y1) in dets:
          if cmap.get(c)!=cname: continue
          X0,Y0,X1,Y1=[int(round(v*sc)) for v in (x0,y0,x1,y1)]
          if (x1-x0)*(y1-y0)>0.8*it['w']*it['h']: continue  # full-frame artefact
          sub=cov[max(0,Y0):Y1,max(0,X0):X1]; np.maximum(sub,s,out=sub)
          cx,cy=int((X0+X1)/2),int((Y0+Y1)/2)
          if 0<=cy<L.shape[0] and 0<=cx<L.shape[1] and m[cy,cx] and s>=0.35: cnt+=1
        v=cov[m]; key=f'{mn}_{cname}'.replace(' ','_')
        f[key+'_max']=float(v.max()) if v.size else 0.0
        for t in (0.2,0.3,0.45): f[f'{key}_cov{int(t*100)}']=float((v>=t).mean())
        f[key+'_n35']=cnt
    rows.append(dict(id=it['id'],set=it['set'],split=it['split'],region=k,gt=it['gt'].get(k,{}),classes=it['classes'],f=f))
    if DO_DINO:
      ys,xs=np.where(m); y0,y1,x0,x1=ys.min(),ys.max()+1,xs.min(),xs.max()+1
      cr=im[y0:y1,x0:x1].copy(); cr[~m[y0:y1,x0:x1]]=0; crops.append(cv2.resize(cr,(224,224),interpolation=cv2.INTER_AREA))
json.dump(rows,open(f'{S}/rf/feats{TAG}.json','w')); print('rows',len(rows))
if DO_DINO:
  F=[]
  with torch.no_grad():
    for i in range(0,len(crops),32):
      o=dm(**proc(images=[Image.fromarray(c) for c in crops[i:i+32]],return_tensors='pt')).last_hidden_state
      F.append(torch.cat([o[:,0],o[:,1:].mean(1)],1).numpy())
  np.save(f'{S}/rf/dino{TAG}.npy',np.concatenate(F)); print('dino',np.concatenate(F).shape)
