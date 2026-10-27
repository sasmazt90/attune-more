import json, numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
exec(open(f'{S}/rf/sev_learn.py').read().split('def oof')[0])
U=json.load(open(f'{S}/rf/ucuk_sev.json'))
Cfull['ucuk']=Cfull['ucuk']+[('lezyon skoru',lambda k:U[k]['smean']),('lezyon alanı',lambda k:U[k]['big'])]
AL=(30,100,300,1000,3000,10000)
def fitpred(Xe,Xp,y,tr,te,a,w):
    se=StandardScaler().fit(Xe[tr]); A=se.transform(Xe)
    if Xp is not None and w>0:
        sp=StandardScaler().fit(Xp[tr]); A=np.hstack([A,w*np.sqrt(Xe.shape[1]/max(1,Xp.shape[1]))*0.1*sp.transform(Xp)])
    return Ridge(alpha=a).fit(A[tr],y[tr]).predict(A[te])
def nested(Xe,Xp,y,ws,reps=10):
    rs=[]
    for rep in range(reps):
        p=np.zeros(len(y))
        for tr,te in KFold(5,shuffle=True,random_state=rep).split(Xe):
            best=None
            for a in AL:
                for w in ws:
                    q=np.zeros(len(tr))
                    for t2,v2 in KFold(4,shuffle=True,random_state=99).split(tr):
                        q[v2]=fitpred(Xe[tr],Xp[tr] if Xp is not None else None,y[tr],t2,v2,a,w)
                    s=spearmanr(y[tr],q).correlation
                    if best is None or s>best[0]: best=(s,a,w)
            p[te]=fitpred(Xe,Xp,y,tr,te,best[1],best[2])
        rs.append(spearmanr(y,p).correlation)
    return np.mean(rs),np.percentile(rs,10),np.percentile(rs,90)
res={}
for f in CR:
    y=np.array(R[f],float); ks=K[f]; Xe=np.array([emb(k,CR[f]) for k in ks])
    ph=[(n,np.array([g(k) if g(k) is not None else np.nan for k in ks],float)) for n,g in Cfull[f]]
    ph=[(n,v) for n,v in ph if not np.isnan(v).any()]
    Xp=np.column_stack([v for _,v in ph])
    a=nested(Xe,None,y,(0,)); b=nested(Xe,Xp,y,(0,0.5,1,2,4))
    single=max(((abs(spearmanr(y,v).correlation),n) for n,v in ph))
    res[f]=dict(emb=a,combo=b,single=single)
    print(f'{f:8s} tek ölçü en iyi: {single[1]} |rho|={single[0]:.2f} | DINOv2 gömme: {a[0]:+.2f} ({a[1]:+.2f}..{a[2]:+.2f}) | gömme+ölçüler: {b[0]:+.2f} ({b[1]:+.2f}..{b[2]:+.2f})',flush=True)
json.dump({k:{kk:list(map(lambda x: x if isinstance(x,str) else float(x),vv)) for kk,vv in v.items()} for k,v in res.items()},open(f'{S}/rf/sev_final.json','w'),ensure_ascii=False)
