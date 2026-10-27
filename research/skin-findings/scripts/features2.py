"""CV features measured only on bare skin (wrinkle lines + beard removed), plus tone (ITA) and coverage fractions.
Merged with model evidence from feats{TAG}.json."""
import json,os,numpy as np,cv2
from PIL import Image
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
TAG=os.environ.get('TAG','')
I={it['id']:it for it in json.load(open(f'{S}/rf/items{TAG}.json'))}; ITA=json.load(open(f'{S}/rf/ita{TAG}.json'))
F=json.load(open(f'{S}/rf/feats{TAG}.json'))
FACE=['forehead','nose','cheek_imgL','cheek_imgR','chin']
import collections
def _cats(ds):
  J=json.load(open(f'{ds}/valid/_annotations.coco.json')); c=collections.Counter(a['category_id'] for a in J['annotations']); out={}
  for x in J['categories']:
    if x['name'] not in out or c[x['id']]>c[out[x['name']]]: out[x['name']]=x['id']
  return {v:k for k,v in out.items()}
_FC=_cats(f'{S}/evalds/findings'); _LESF={'Akne','Siyah Nokta','Beyaz Nokta','Gunes Lekesi','Riskli Ben','Ucuk'}
LES=collections.defaultdict(list)
for k,d in json.load(open(f'{S}/rf/pred{TAG}_acnes.json')).items(): LES[k]+=d
for k,d in json.load(open(f'{S}/rf/pred{TAG}_findings.json')).items(): LES[k]+=[x for x in d if _FC.get(x[0]) in _LESF]
cache={}
def prep(iid):
  it=I[iid]; img=np.array(Image.open(it['path']).convert('RGB')); sc=400/max(it['faceW'],1)
  size=(max(1,round(it['w']*sc)),max(1,round(it['h']*sc)))
  im=cv2.resize(img,size,interpolation=cv2.INTER_AREA if sc<1 else cv2.INTER_CUBIC)
  mm=cv2.imread(f"{S}/rf/clean{TAG}/{iid}_m.png",0); mm=np.zeros(img.shape[:2],np.uint8) if mm is None else mm
  mm=cv2.resize(mm,size,interpolation=cv2.INTER_NEAREST)
  wr=cv2.dilate((mm&1).astype(np.uint8),np.ones((5,5),np.uint8))>0; br=cv2.dilate(((mm&2)>0).astype(np.uint8),np.ones((5,5),np.uint8))>0
  # lesions (acne, comedones, spots, moles) are not "flakes": remove their boxes from bare skin too
  for c,s,(x0,y0,x1,y1) in LES.get(str(iid),[]):
    if s<0.35 or (x1-x0)*(y1-y0)>0.25*it['w']*it['h']: continue
    br[max(0,int(y0*sc)):int(y1*sc)+1,max(0,int(x0*sc)):int(x1*sc)+1]=True
  lab=cv2.cvtColor(im,cv2.COLOR_RGB2LAB).astype(np.float32); L=lab[...,0]*100/255; A=lab[...,1]-128; B=lab[...,2]-128; C=np.hypot(A,B)
  hp=L-cv2.GaussianBlur(L,(0,0),3); th=cv2.morphologyEx(L,cv2.MORPH_TOPHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
  masks={}
  for k in it['regions']:
    m=np.zeros(L.shape,np.uint8); cv2.fillPoly(m,[(np.array(it['regions'][k])*sc).astype(np.int32)],1)
    if k in it['holes']: cv2.fillPoly(m,[(np.array(it['holes'][k])*sc).astype(np.int32)],0)
    masks[k]=m>0
  face=np.zeros(L.shape,bool)
  for k in FACE: face|=masks[k]
  clean_face=face&~wr&~br
  ref=clean_face if clean_face.sum()>300 else face
  st=dict(Lm=np.median(L[ref]),Ls=np.std(L[ref])+1e-6,Am=np.median(A[ref]),Cm=np.median(C[ref]),hps=np.std(hp[ref])+1e-6)
  return dict(L=L,A=A,C=C,hp=hp,th=th,wr=wr,br=br,masks=masks,st=st)
rows=[]
for r in F:
  iid=r['id']
  if iid not in cache: cache.clear(); cache[iid]=prep(iid)
  P=cache[iid]; m=P['masks'][r['region']]; st=P['st']
  if m.sum()<150: continue
  cl=m&~P['wr']&~P['br']; f=dict(r['f'])
  f['frac_clean']=float(cl.sum()/m.sum()); f['frac_beard']=float((m&P['br']).sum()/m.sum()); f['frac_wrinkle']=float((m&P['wr']).sum()/m.sum())
  use=cl if cl.sum()>=80 else None
  if use is None:
    for k in ('c_shine','c_p99','c_tex','c_flake','c_red','c_matte'): f[k]=None
  else:
    l=P['L'][use]
    f['c_shine']=float(((l>st['Lm']+1.6*st['Ls'])&(P['C'][use]<st['Cm'])).mean())
    f['c_p99']=float((np.percentile(l,99)-st['Lm'])/st['Ls'])
    f['c_tex']=float(np.std(P['hp'][use])/st['hps'])
    f['c_flake']=float(((P['th'][use]>max(4.0,0.08*st['Lm']))&(P['C'][use]<st['Cm'])).mean())   # flake contrast scaled to own skin lightness
    f['c_red']=float(P['A'][use].mean()-st['Am'])
    f['c_matte']=float(1.0-min(1.0,(np.percentile(l,95)-np.median(l))/max(st['Ls'],1e-6)/3))
  f['ita']=ITA.get(str(iid),ITA.get(iid,40.0))
  rows.append(dict(r,f=f))
json.dump(rows,open(f'{S}/rf/feats2{TAG}.json','w')); print('rows',len(rows))
