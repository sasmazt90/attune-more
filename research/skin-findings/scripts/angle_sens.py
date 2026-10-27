import numpy as np, collections
exec(open('/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad/rf/k_train.py').read().split("C = ['dry'")[0])
from sklearn.linear_model import LogisticRegression; from sklearn.preprocessing import StandardScaler; from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
pilot=set(open('/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad/gen/pilot32.txt').read().split())
tags=np.array([r['tag'] for r in rows]); kids=np.array([r['kid'] for r in rows]); tr=~np.isin(kids,list(pilot))&(tags!='_k7')
m=make_pipeline(StandardScaler(),LogisticRegression(C=0.05,max_iter=3000,class_weight='balanced')).fit(X[tr],Ys[tr]); P=m.predict_proba(X)[:,1]
for name,use in (('ön + 20°',lambda r:r['tag']!='_k7'),('ön + ~25°',lambda r:r['tag']=='_k7' or r['view']=='front'),('ön + 20° + ~25°',lambda r:True)):
  agg=collections.defaultdict(list)
  for i,r in enumerate(rows):
    if r['kid'] in pilot and r['app'] in ('rightCheek','leftCheek') and use(r): agg[(r['kid'],r['app'])].append(i)
  ps=np.array([P[v].mean() for v in agg.values()]); y=np.array([rows[v[0]]['sens'] for v in agg.values()])
  k=ps>=0.57; print(f"{name:18s} yanak hassasiyet: pozitif {y.sum()}/{len(y)} AUC={roc_auc_score(y,ps):.2f} | eşik 0.57: isabet={y[k].mean() if k.sum() else float('nan'):.2f} yakalama={(k&y).sum()/y.sum():.2f}")
