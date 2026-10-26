"""Cheek accuracy for the 40 pilot persons: front+20°, front+~25-32°, front+both. Model trained on all other persons
(20° data only, pilot persons and the new-angle images never in training)."""
import numpy as np, collections
exec(open('/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad/rf/k_train.py').read().split("C = ['dry'")[0])
from sklearn.linear_model import LogisticRegression; from sklearn.preprocessing import StandardScaler; from sklearn.pipeline import make_pipeline
pilot=set(open('/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad/gen/pilot32.txt').read().split())
tags=np.array([r['tag'] for r in rows]); kids=np.array([r['kid'] for r in rows])
tr=~np.isin(kids,list(pilot)) & (tags!='_k7')
m=make_pipeline(StandardScaler(),LogisticRegression(C=0.05,max_iter=3000,class_weight='balanced')).fit(X[tr],Y[tr])
P=m.predict_proba(X); C=np.array(['dry','normal','oily'])
thr={'dry':0.71,'normal':0.70,'oily':0.70}
def evaluate(name,use):
  agg=collections.defaultdict(list)
  for i,r in enumerate(rows):
    if r['kid'] in pilot and r['app'] in ('rightCheek','leftCheek') and use(r): agg[(r['kid'],r['app'])].append(i)
  pr=np.array([P[v].mean(0) for v in agg.values()]); yt=np.array([rows[v[0]]['y'] for v in agg.values()]); pd=C[pr.argmax(1)]
  keep=np.array([pr[i].max()>=thr[pd[i]] for i in range(len(pd))])
  s=f"{name:34s} n={len(yt)} doğruluk={np.mean(pd==yt):.2f} boyanma={keep.mean():.2f} boyananda={np.mean(pd[keep]==yt[keep]):.2f}"
  for c in C:
    k=keep&(pd==c); s+=f" {c}:P={np.mean(yt[k]==c) if k.sum() else float('nan'):.2f}(n={k.sum()})"
  print(s)
evaluate('ön + 20°',lambda r:r['tag']!='_k7')
evaluate('ön + ~25-32°',lambda r:r['tag']=='_k7' or r['view']=='front')
evaluate('ön + 20° + ~25-32°',lambda r:True)
evaluate('yalnız 20° yan',lambda r:r['tag']!='_k7' and r['view']!='front')
evaluate('yalnız ~25-32° yan',lambda r:r['tag']=='_k7' and r['view']!='front')
