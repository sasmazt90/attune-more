import json,numpy as np,collections,sys
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
L=json.load(open(f'{S}/rf/l6qra_rows.json')); LD=np.load(f'{S}/rf/l6qra_dino.npy')
def prf(y,p):
  tp=int(((y==1)&(p==1)).sum()); fp=int(((y==0)&(p==1)).sum()); fn=int(((y==1)&(p==0)).sum())
  P=tp/max(tp+fp,1); R=tp/max(tp+fn,1); return dict(P=round(P,3),R=round(R,3),F1=round(2*P*R/max(P+R,1e-9),3),n=len(y),pos=int(y.sum()))
idx=lambda sp:[i for i,r in enumerate(L) if r['split']==sp and r['label'] in('dry','normal')]
tr,va,te=idx('train'),idx('valid'),idx('test')
y=lambda ii:np.array([int(L[i]['label']=='dry') for i in ii])
clf=make_pipeline(StandardScaler(),LogisticRegression(C=0.05,max_iter=4000,class_weight='balanced')).fit(LD[tr],y(tr))
# own test (image level = mean over that image's crops)
def imglevel(ii):
  g=collections.defaultdict(list)
  for i,p in zip(ii,clf.predict_proba(LD[ii])[:,1]): g[L[i]['file']].append((p,int(L[i]['label']=='dry')))
  ps=np.array([np.mean([a for a,_ in v]) for v in g.values()]); ys=np.array([v[0][1] for v in g.values()]); return ys,ps
yv,pv=imglevel(va); yt,pt=imglevel(te)
grid=np.round(np.arange(0.1,0.91,0.025),3); t=max(grid,key=lambda t:prf(yv,(pv>=t).astype(int))['F1'])
print('l6qra own: valid AUC',round(roc_auc_score(yv,pv),3),'| TEST AUC',round(roc_auc_score(yt,pt),3),'thr',t,prf(yt,(pt>=t).astype(int)))
# our region testbed
exec(open(f'{S}/rf/fuse2.py').read().split("face=[r for r in R if not r['eye']]")[0])
D=np.load(f'{S}/rf/dino.npy'); assert len(D)==len(R)
for i,r in enumerate(R): r['ix']=i
face=[r for r in R if not r['eye'] and r['type'] in('dry','normal') and r['set']!='ka1tj']
s_l6=clf.predict_proba(D[[r['ix'] for r in face]])[:,1]
for part in ('test','all'):
  sel=[i for i,r in enumerate(face) if part=='all' or r['test']]
  yy=np.array([int(face[i]['type']=='dry') for i in sel])
  cur=np.array([face[i]['f'].get('findings_Kuru_Cilt_max') or 0 for i in sel])
  print(f"OUR testbed [{part}] n={len(yy)} pos={yy.sum()} | AUC l6qra-model={roc_auc_score(yy,s_l6[sel]):.3f}  current Kuru-model={roc_auc_score(yy,cur):.3f}")
  for s,nm in ((s_l6[sel],'l6qra'),):
    print('   ',nm,' '.join(f"{t}:{prf(yy,(s>=t).astype(int))['P']}/{prf(yy,(s>=t).astype(int))['R']}" for t in (0.3,0.4,0.5,0.6,0.7,0.8)))
  for g in ('light','medium','dark'):
    gi=[k for k,i in enumerate(sel) if face[i]['tone']==g]
    if len(gi)>5 and 0<yy[gi].sum()<len(gi): print(f"    tone {g}: n={len(gi)} AUC l6qra={roc_auc_score(yy[gi],s_l6[sel][gi]):.3f} kuru={roc_auc_score(yy[gi],cur[gi]):.3f}")
# as an added feature in the dry fusion (fit split -> test once)
from sklearn.model_selection import GroupKFold
fit=[i for i,r in enumerate(face) if not r['test']]; tst=[i for i,r in enumerate(face) if r['test']]
X=lambda ii,add:np.array([feats(face[i],'dry')+([s_l6[i]] if add else []) for i in ii])
yf=np.array([int(face[i]['type']=='dry') for i in fit]); yt2=np.array([int(face[i]['type']=='dry') for i in tst])
for add in (False,True):
  oof=np.zeros(len(fit)); gr=[f"{face[i]['set']}{face[i]['id']}" for i in fit]
  for a,b in GroupKFold(5).split(X(fit,add),yf,gr): oof[b]=LogisticRegression(C=0.3,max_iter=3000,class_weight='balanced').fit(X(fit,add)[a],yf[a]).predict_proba(X(fit,add)[b])[:,1]
  t=max(grid,key=lambda t:prf(yf,(oof>=t).astype(int))['F1'])
  m=LogisticRegression(C=0.3,max_iter=3000,class_weight='balanced').fit(X(fit,add),yf); p=m.predict_proba(X(tst,add))[:,1]
  print(f"fusion dry {'+l6qra' if add else 'current':8s} thr={t} TEST {prf(yt2,(p>=t).astype(int))} AUC={roc_auc_score(yt2,p):.3f} w={np.round(m.coef_[0],2).tolist()}")
np.save(f'{S}/rf/l6qra_clf_scores_face.npy',s_l6)
import pickle; pickle.dump(clf,open(f'{S}/rf/l6qra_clf.pkl','wb'))
