import json,numpy as np,collections
from sklearn.metrics import roc_auc_score
exec(open('fuse.py').read().split("KEYS=sorted")[0].replace("D=np.load","D=None and np.load"))
KEYS=sorted(R[0]['f'])
face=[r for r in R if not r['eye']]
def auc_table(rows,ylab,keys,title):
  print('==',title)
  for s in sorted({r['set'] for r in rows}):
    rr=[r for r in rows if r['set']==s]; y=np.array([ylab(r) for r in rr])
    if y.sum()<5 or (1-y).sum()<5: continue
    a=sorted(((roc_auc_score(y,[r['f'][k] for r in rr]),k) for k in keys),reverse=True)
    print(f" {s:9s} n={len(y)} pos={int(y.sum())}",' '.join(f"{k}={v:.2f}" for v,k in a[:5]),'| worst',' '.join(f"{k}={v:.2f}" for v,k in a[-2:]))
oil=[r for r in face if r['type'] is not None]
auc_table(oil,lambda r:int(r['type']=='oily'),KEYS,'OILY')
dry=[r for r in face if r['type'] in('dry','normal')]
auc_table(dry,lambda r:int(r['type']=='dry'),KEYS,'DRY vs NORMAL')
sens=[r for r in face if r['sens'] is not None]
auc_table(sens,lambda r:r['sens'],KEYS,'SENS')
