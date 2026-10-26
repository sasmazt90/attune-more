import json,numpy as np,collections,itertools
from sklearn.metrics import roc_auc_score
exec(open('fuse.py').read().split("KEYS=sorted")[0].replace("D=np.load","D=None and np.load"))
face=[r for r in R if not r['eye']]
def prf(y,p):
  tp=int(((y==1)&(p==1)).sum()); fp=int(((y==0)&(p==1)).sum()); fn=int(((y==1)&(p==0)).sum()); tn=int(((y==0)&(p==0)).sum())
  P=tp/max(tp+fp,1); Rr=tp/max(tp+fn,1); return dict(P=round(P,3),R=round(Rr,3),F1=round(2*P*Rr/max(P+Rr,1e-9),3),NPV=round(tn/max(tn+fn,1),3),tp=tp,fp=fp,fn=fn,n=len(y))
f=lambda r,k:r['f'][k]
SC={
 'oily_models':lambda r:(f(r,'skinmap_Oily_max')+f(r,'regional_oily_max')+f(r,'findings_Yagli_Cilt_max'))/3,
 'oily_models+shine':lambda r:(f(r,'skinmap_Oily_max')+f(r,'regional_oily_max')+f(r,'findings_Yagli_Cilt_max')+min(1,f(r,'cv_shine')*8))/4,
 'dry_models':lambda r:(f(r,'regional_dry_max')+f(r,'findings_Kuru_Cilt_max'))/2,
 'dry_models+flake':lambda r:(f(r,'regional_dry_max')+f(r,'findings_Kuru_Cilt_max')+min(1,f(r,'cv_flake')*6))/3,
 'sens_max':lambda r:max(f(r,'skinmap_Redness_max'),f(r,'findings_Rozasea_max')),
 'sens_mean':lambda r:(f(r,'skinmap_Redness_max')+f(r,'findings_Rozasea_max'))/2,
}
ACNE=lambda r:f(r,'acnes_papule_n35')+f(r,'acnes_pustule_n35')+f(r,'acnes_nodule_n35')+f(r,'acnes_blackhead_n35')+f(r,'acnes_whitehead_n35')
SETS_OK=lambda r:r['set']!='ka1tj'
TASKS={'oily':([r for r in face if r['type'] is not None and SETS_OK(r)],lambda r:int(r['type']=='oily'),['oily_models','oily_models+shine']),
 'dry':([r for r in face if r['type'] in('dry','normal') and SETS_OK(r)],lambda r:int(r['type']=='dry'),['dry_models','dry_models+flake']),
 'sens':([r for r in face if r['sens'] is not None],lambda r:r['sens'],['sens_max','sens_mean'])}
out={}
grid=np.round(np.arange(0.05,0.951,0.025),3)
for tn,(rows,yl,scs) in TASKS.items():
  fit=[r for r in rows if not r['test']]; te=[r for r in rows if r['test']]
  yf=np.array([yl(r) for r in fit]); yt=np.array([yl(r) for r in te])
  for sc in scs:
    sf=np.array([SC[sc](r) for r in fit]); st=np.array([SC[sc](r) for r in te])
    sw={t:prf(yf,(sf>=t).astype(int)) for t in grid}; t1=max(grid,key=lambda t:sw[t]['F1'])
    ok=[t for t in grid if sw[t]['P']>=0.9 and sw[t]['tp']>=5]; t2=min(ok) if ok else None
    res=dict(thr=float(t1),fit=sw[t1],test=prf(yt,(st>=t1).astype(int)),aucTest=round(roc_auc_score(yt,st),3),perSetTest={})
    for s in sorted({r['set'] for r in te}):
      idx=[i for i,r in enumerate(te) if r['set']==s]
      if yt[idx].sum()>0: res['perSetTest'][s]=prf(yt[idx],(st[idx]>=t1).astype(int))
    if t2: res['thrP90']=float(t2); res['testP90']=prf(yt,(st>=t2).astype(int))
    out[f'{tn}:{sc}']=res
    print(f"{tn}:{sc:20s} thr={t1} fit F1={sw[t1]['F1']} | TEST P={res['test']['P']} R={res['test']['R']} F1={res['test']['F1']} AUC={res['aucTest']} n={len(yt)} pos={int(yt.sum())}"+(f" | P90 thr={t2} P={res['testP90']['P']} R={res['testP90']['R']}" if t2 else ''))
    for s,v in res['perSetTest'].items(): print(f"      {s:9s} P={v['P']} R={v['R']} F1={v['F1']} n={v['n']} pos={v['tp']+v['fn']}")
# acne-assisted oily rule (user rule): oily if score>=T1, or (acne>=2 and score>=T2<T1)
rows,yl,_=TASKS['oily']; fit=[r for r in rows if not r['test']]; te=[r for r in rows if r['test']]
yf=np.array([yl(r) for r in fit]); yt=np.array([yl(r) for r in te]); sc=SC['oily_models+shine']
best=None
for t1 in grid:
  for t2 in grid[grid<t1]:
    for na in (2,3):
      p=np.array([int(sc(r)>=t1 or (ACNE(r)>=na and sc(r)>=t2)) for r in fit]); m=prf(yf,p)
      if not best or m['F1']>best[0]['F1']: best=(m,t1,t2,na)
m,t1,t2,na=best; p=np.array([int(sc(r)>=t1 or (ACNE(r)>=na and sc(r)>=t2)) for r in te])
out['oily:acne_rule']=dict(T1=float(t1),T2=float(t2),acneMin=na,fit=m,test=prf(yt,p))
print('oily acne rule',t1,t2,na,'fit',m['F1'],'TEST',prf(yt,p))
acne_only=np.array([int(ACNE(r)>=2) for r in te]); print('acne-only (>=2) as oily TEST',prf(yt,acne_only))
json.dump(out,open('rules_results.json','w'),indent=1)
