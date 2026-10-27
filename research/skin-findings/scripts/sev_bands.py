import json, numpy as np
from scipy.stats import spearmanr, rankdata
exec(open('rf/sev_final.py').read().split('res={}')[0])
CFG={'torba':(1000,0),'morluk':(1000,1),'kapak':(300,0),'kaz':(1000,0),'alin':(300,0),'akneizi':(300,0)}
out={}
for f,(a,w) in CFG.items():
    y=np.array(R[f],float); ks=K[f]; Xe=np.array([emb(k,CR[f]) for k in ks])
    ph=[(n,np.array([g(k) if g(k) is not None else np.nan for k in ks],float)) for n,g in Cfull[f]]
    Xp=np.column_stack([v for _,v in ph if not np.isnan(v).any()])
    P=[]
    for rep in range(20):
        p=np.zeros(len(y))
        for tr,te in KFold(5,shuffle=True,random_state=rep).split(Xe): p[te]=fitpred(Xe,Xp,y,tr,te,a,w)
        P.append((rankdata(p)-0.5)/len(p)*100)
    s=np.mean(P,0)
    lv=[f'{s[y==i].mean():.0f}' for i in (1,2,3)]
    band=np.minimum((s//20).astype(int),4)
    far=np.mean(((y==1)&(band>=3))|((y==3)&(band<=1)))
    print(f'{f:8s} rho={spearmanr(y,s).correlation:+.2f} ortalama skor hafif/orta/belirgin = {"/".join(lv)} ; 2+ bant uzak hata=%{far*100:.0f}')
