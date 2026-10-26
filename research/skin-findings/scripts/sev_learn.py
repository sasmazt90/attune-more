"""Learned severity: out-of-fold Spearman vs blind visual ratings, repeated 5-fold CV on rated positives."""
import json, numpy as np, collections, sys
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import KFold
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
exec(open(f'{S}/rf/sev_corr.py').read().split('out={}')[0].split("C={'torba'")[0])
Cfull={}
exec("Cfull={'torba'"+open(f'{S}/rf/sev_corr.py').read().split("C={'torba'")[1].split('out={}')[0].replace('C=','Cfull='))
z=np.load(f'{S}/rf/finding_angle4_emb.npz',allow_pickle=True); E=z['E']; M=z['meta']
CR={'torba':['under_L','under_R'],'morluk':['under_L','under_R'],'kapak':['lid_L','lid_R'],'kaz':['corner_L','corner_R'],
    'alin':['forehead'],'akneizi':['cheek_L','cheek_R','jaw'],'ucuk':['lip']}
idx=collections.defaultdict(list)
for i,m in enumerate(M): idx[(m['kid'],m['crop'],m['src'])].append(i)
def emb(k,crops,srcs=('front','s20')):
    ii=[i for c in crops for s in srcs for i in idx.get((k,c,s),[])]
    return E[ii].mean(0) if ii else None
def oof(X,y,alpha,reps=10):
    rs=[]
    for rep in range(reps):
        p=np.zeros(len(y))
        for tr,te in KFold(5,shuffle=True,random_state=rep).split(X):
            m=make_pipeline(StandardScaler(),Ridge(alpha=alpha)).fit(X[tr],y[tr]); p[te]=m.predict(X[te])
        rs.append(spearmanr(y,p).correlation)
    return np.mean(rs),np.std(rs)
RES={}
for f in CR:
    y=np.array(R[f],float); ks=K[f]
    Xe=np.array([emb(k,CR[f]) for k in ks])
    phys=[]
    for nm,g in Cfull[f]:
        v=np.array([g(k) if g(k) is not None else np.nan for k in ks],float)
        if np.isnan(v).sum()==0: phys.append((nm,v))
    Xp=np.column_stack([v for _,v in phys])
    print(f'\n{f} (n={len(y)})')
    for a in (1e2,1e3,1e4):
        print(f'  DINOv2 gömme ridge a={a:g}: rho={oof(Xe,y,a)[0]:+.2f}')
    for a in (1,10,30):
        print(f'  fiziksel+logit ridge ({",".join(n for n,_ in phys)}) a={a}: rho={oof(Xp,y,a)[0]:+.2f}')
