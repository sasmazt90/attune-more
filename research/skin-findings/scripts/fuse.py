"""Step 4: region-level oily / dry / sensitive decisions. Fit on FIT split, thresholds by F1 on FIT
(grouped CV out-of-fold scores), TEST reported once. Face regions and eye regions reported separately."""
import json,sys,collections,numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.decomposition import PCA
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
R=json.load(open(f'{S}/rf/feats.json')); D=np.load(f'{S}/rf/dino.npy') if '--dino' in sys.argv else None
TEST={('parin','test'),('skinmap','test'),('findings','test'),('a7el6','test'),('orhyy','valid'),('orhyy','test'),('ka1tj','test')}
for i,r in enumerate(R): r['i']=i; r['eye']=r['region'].startswith('eye'); r['test']=(r['set'],r['split']) in TEST
COV=0.25
def lab_type(r):
  g=r['gt']; s=r['set']
  if s=='parin':
    if not r['classes']: return 'normal'
    d,o=g.get('dry',0),g.get('oily',0)
    if max(d,o)>=COV: return 'oily' if o>=d else 'dry'
    return None
  if s in('a7el6','orhyy','ka1tj'):
    c={k:g.get(k,0) for k in('dry','oily','normal')}; k=max(c,key=c.get)
    return k if c[k]>=COV else None
  if s=='findings':
    if g.get('Kuru Cilt',0)>=COV: return 'dry'
    if g.get('Yagli Cilt',0)>=COV: return 'oily'
    return None
  if s=='skinmap':
    return 'oily' if g.get('Oily',0)>=COV else 'notoily'
def lab_sens(r):
  g=r['gt']
  if r['set']=='skinmap': return int(g.get('Redness',0)>=COV)
  if r['set']=='findings': return int(g.get('Rozasea',0)>=COV) if (g or r['classes']) else None
  return None
for r in R: r['type']=lab_type(r); r['sens']=lab_sens(r)
KEYS=sorted(R[0]['f'])
def X(rows,keys):
  return np.array([[r['f'][k] for k in keys] for r in rows],float)
def prf(y,p):
  tp=int(((y==1)&(p==1)).sum()); fp=int(((y==0)&(p==1)).sum()); fn=int(((y==1)&(p==0)).sum())
  P=tp/max(tp+fp,1); Rr=tp/max(tp+fn,1); return dict(P=round(P,3),R=round(Rr,3),F1=round(2*P*Rr/max(P+Rr,1e-9),3),tp=tp,fp=fp,fn=fn,n=len(y))
def task(name,rows_fit,rows_test,y_fit,y_test,keys,dino=False,C=0.5):
  Xf=X(rows_fit,keys); Xt=X(rows_test,keys)
  if dino:
    pca=PCA(24,random_state=0).fit(D[[r['i'] for r in rows_fit]]); Xf=np.hstack([Xf,pca.transform(D[[r['i'] for r in rows_fit]])]); Xt=np.hstack([Xt,pca.transform(D[[r['i'] for r in rows_test]])])
  mk=lambda:make_pipeline(StandardScaler(),LogisticRegression(C=C,max_iter=2000,class_weight='balanced'))
  groups=[f"{r['set']}{r['id']}" for r in rows_fit]; oof=np.zeros(len(y_fit))
  for tr,va in GroupKFold(5).split(Xf,y_fit,groups):
    oof[va]=mk().fit(Xf[tr],y_fit[tr]).predict_proba(Xf[va])[:,1]
  grid=np.round(np.arange(0.1,0.951,0.025),3); sw={t:prf(y_fit,(oof>=t).astype(int)) for t in grid}
  t1=max(grid,key=lambda t:sw[t]['F1']); ok=[t for t in grid if sw[t]['P']>=0.9 and sw[t]['tp']>=5]; t2=min(ok) if ok else None
  m=mk().fit(Xf,y_fit); pt=m.predict_proba(Xt)[:,1]
  out=dict(task=name,nFit=len(y_fit),posFit=int(y_fit.sum()),nTest=len(y_test),posTest=int(y_test.sum()),thrF1=float(t1),fitOOF=sw[t1],test=prf(y_test,(pt>=t1).astype(int)),
           thrP90=None if t2 is None else float(t2),testP90=None if t2 is None else prf(y_test,(pt>=t2).astype(int)))
  coef=m[-1].coef_[0][:len(keys)]; out['topFeatures']=sorted(zip(keys,np.round(coef,2).tolist()),key=lambda x:-abs(x[1]))[:8]
  print(f"{name:34s} fit n={len(y_fit)} pos={int(y_fit.sum())} | thr={t1} OOF F1={sw[t1]['F1']} | TEST P={out['test']['P']} R={out['test']['R']} F1={out['test']['F1']} (n={len(y_test)},pos={int(y_test.sum())})"+('' if t2 is None else f" | P90 thr={t2} TEST P={out['testP90']['P']} R={out['testP90']['R']}"))
  return out,m
res={}
OILY_KEYS=[k for k in KEYS if k.startswith('cv_') or 'Oily' in k or 'Yagli' in k or k.startswith('regional_oily') or k.startswith('acnes_')]
DRY_KEYS=[k for k in KEYS if k.startswith('cv_') or 'Kuru' in k or k.startswith('regional_dry') or 'Oily' in k or 'Yagli' in k]
SENS_KEYS=[k for k in KEYS if k.startswith('cv_red') or 'Redness' in k or 'Rozasea' in k or k.startswith('acnes_')]
for eye in (False,True):
  tag='EYE' if eye else 'FACE'
  pool=[r for r in R if r['eye']==eye]
  # OILY vs not
  rows=[r for r in pool if r['type'] is not None]
  f=[r for r in rows if not r['test']]; t=[r for r in rows if r['test']]
  y=lambda rr:np.array([int(r['type']=='oily') for r in rr])
  for dn in (False,True) if D is not None else (False,):
    res[f'{tag}_oily_dino{int(dn)}'],_=task(f'{tag} yağlı (dino={int(dn)})',f,t,y(f),y(t),OILY_KEYS,dn)
  # DRY vs normal (oily excluded)
  rows=[r for r in pool if r['type'] in('dry','normal')]
  f=[r for r in rows if not r['test']]; t=[r for r in rows if r['test']]
  y=lambda rr:np.array([int(r['type']=='dry') for r in rr])
  for dn in (False,True) if D is not None else (False,):
    res[f'{tag}_dry_dino{int(dn)}'],_=task(f'{tag} kuru vs normal (dino={int(dn)})',f,t,y(f),y(t),DRY_KEYS,dn)
  # SENSITIVE
  rows=[r for r in pool if r['sens'] is not None]
  f=[r for r in rows if not r['test']]; t=[r for r in rows if r['test']]
  y=lambda rr:np.array([r['sens'] for r in rr])
  if len(f)>30 and sum(r['sens'] for r in f)>=5: res[f'{tag}_sens'],_=task(f'{tag} hassas',f,t,y(f),y(t),SENS_KEYS)
json.dump(res,open(f'{S}/rf/fuse_results.json','w'),indent=1,ensure_ascii=False)
