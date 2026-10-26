"""Tone-aware regional decisions. CV features measured on bare skin and standardised WITHIN skin-tone group
(ITA: light >41, medium 10..41, dark <10) so shine/flake/texture are judged against people of similar tone.
Small, regularised logistic models per task; thresholds by F1 on FIT (grouped OOF), per tone group when the
group has enough positives, otherwise the global threshold. TEST reported once, overall and per tone group."""
import json,sys,collections,numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
R=json.load(open(f'{S}/rf/feats2.json'))
exec(open(f'{S}/rf/fuse.py').read().split("KEYS=sorted")[0].split("R=json.load")[0])
TEST={('parin','test'),('skinmap','test'),('findings','test'),('a7el6','test'),('orhyy','valid'),('orhyy','test'),('ka1tj','test')}
exec("COV=0.25\n"+open(f'{S}/rf/fuse.py').read().split("COV=0.25")[1].split("KEYS=sorted")[0])
for r in R: r['eye']=r['region'].startswith('eye'); r['test']=(r['set'],r['split']) in TEST
GRP=lambda a:'light' if a>41 else ('medium' if a>10 else 'dark')
for r in R: r['tone']=GRP(r['f']['ita'])
import pickle as _pk
_L6=_pk.load(open(f'{S}/rf/l6qra_clf.pkl','rb')); _D=np.load(f'{S}/rf/dino.npy')
for i,(r,p) in enumerate(zip(R,_L6.predict_proba(_D)[:,1])): r['f']['l6qra_dry']=float(p)
TZ={'forehead','nose'}
def base(r,k): v=r['f'].get(k); return 0.0 if v is None else v
CVK=['c_shine','c_p99','c_tex','c_flake','c_matte','c_red']
fitrows=[r for r in R if not r['test'] and not r['eye']]
STATS={}
for g in ('light','medium','dark'):
  rr=[r for r in fitrows if r['tone']==g] or fitrows
  STATS[g]={k:(np.nanmedian([r['f'][k] if r['f'][k] is not None else np.nan for r in rr]),np.nanstd([r['f'][k] if r['f'][k] is not None else np.nan for r in rr])+1e-6) for k in CVK}
def z(r,k):
  v=r['f'].get(k)
  if v is None: return 0.0
  m,s=STATS[r['tone']][k]; return float(np.clip((v-m)/s,-4,6))
ACNE=lambda r:base(r,'acnes_papule_n35')+base(r,'acnes_pustule_n35')+base(r,'acnes_nodule_n35')+base(r,'acnes_blackhead_n35')+base(r,'acnes_whitehead_n35')
def feats(r,task):
  cleanw=base(r,'frac_clean')
  if task=='oily':
    return [base(r,'skinmap_Oily_max'),base(r,'regional_oily_max'),base(r,'findings_Yagli_Cilt_max'),z(r,'c_shine'),z(r,'c_p99'),min(ACNE(r),4)/4*min(1,max(0,z(r,'c_shine')+1))]
  if task=='dry':
    ecz=base(r,'findings_Egzema_max')*(0.5 if r['region'] in TZ else 1.0)
    return [base(r,'findings_Kuru_Cilt_max'),ecz,z(r,'c_flake')*cleanw,z(r,'c_tex')*cleanw,z(r,'c_matte')*cleanw,-z(r,'c_shine')]
  if task=='sens':
    return [base(r,'skinmap_Redness_max'),base(r,'findings_Rozasea_max'),base(r,'findings_Egzema_max'),base(r,'findings_Sedef_ve_Dokuntu_max'),z(r,'c_red'),min(base(r,'acnes_papule_n35')+base(r,'acnes_pustule_n35')+base(r,'acnes_nodule_n35'),4)/4]
NAMES={'oily':['skinmapOily','regionalOily','findingsYagli','shine_z','p99_z','acne×shine'],'dry':['findingsKuru','egzama(T×0.5)','flake_z','tex_z','matte_z','-shine_z'],'sens':['skinmapRedness','rozasea','egzama','sedef','red_z','iltihapliAkne']}
def prf(y,p):
  tp=int(((y==1)&(p==1)).sum()); fp=int(((y==0)&(p==1)).sum()); fn=int(((y==1)&(p==0)).sum())
  P=tp/max(tp+fp,1); Rr=tp/max(tp+fn,1); return dict(P=round(P,3),R=round(Rr,3),F1=round(2*P*Rr/max(P+Rr,1e-9),3),tp=tp,fp=fp,fn=fn,n=len(y))
grid=np.round(np.arange(0.05,0.951,0.025),3)
def run(task,rows,ylab):
  fit=[r for r in rows if not r['test']]; te=[r for r in rows if r['test']]
  Xf=np.array([feats(r,task) for r in fit]); Xt=np.array([feats(r,task) for r in te]); yf=np.array([ylab(r) for r in fit]); yt=np.array([ylab(r) for r in te])
  mk=lambda:LogisticRegression(C=0.3,max_iter=3000,class_weight='balanced')
  oof=np.zeros(len(yf)); gr=[f"{r['set']}{r['id']}" for r in fit]
  for a,b in GroupKFold(5).split(Xf,yf,gr): oof[b]=mk().fit(Xf[a],yf[a]).predict_proba(Xf[b])[:,1]
  best=lambda idx:max(grid,key=lambda t:prf(yf[idx],(oof[idx]>=t).astype(int))['F1'])
  allidx=np.arange(len(yf)); tg=best(allidx); thr={}
  for g in ('light','medium','dark'):
    idx=np.array([i for i,r in enumerate(fit) if r['tone']==g],int)
    thr[g]=float(best(idx)) if len(idx) and yf[idx].sum()>=15 and (1-yf[idx]).sum()>=15 else float(tg)
  m=mk().fit(Xf,yf); pt=m.predict_proba(Xt)[:,1]
  pred=np.array([int(pt[i]>=thr[r['tone']]) for i,r in enumerate(te)])
  pg=np.array([int(pt[i]>=tg) for i in range(len(te))])
  out=dict(task=task,thrGlobal=float(tg),thrTone=thr,weights=dict(zip(NAMES[task],np.round(m.coef_[0],2).tolist())),testToneThr=prf(yt,pred),testGlobalThr=prf(yt,pg),perTone={},perSet={})
  for g in ('light','medium','dark'):
    idx=[i for i,r in enumerate(te) if r['tone']==g]
    if idx: out['perTone'][g]=dict(n=len(idx),pos=int(yt[idx].sum()),toneThr=prf(yt[idx],pred[idx]),globalThr=prf(yt[idx],pg[idx]))
  for s in sorted({r['set'] for r in te}):
    idx=[i for i,r in enumerate(te) if r['set']==s]
    if yt[idx].sum(): out['perSet'][s]=prf(yt[idx],pred[idx])
  print(f"\n== {task}: weights {out['weights']}\n   thr global={tg} tone={thr}\n   TEST tone-thr {out['testToneThr']}\n   TEST global   {out['testGlobalThr']}")
  for g,v in out['perTone'].items(): print(f"   {g:6s} n={v['n']} pos={v['pos']} tone {v['toneThr']['P']}/{v['toneThr']['R']}/{v['toneThr']['F1']}  global {v['globalThr']['P']}/{v['globalThr']['R']}/{v['globalThr']['F1']}")
  for s,v in out['perSet'].items(): print(f"   {s:9s} P={v['P']} R={v['R']} F1={v['F1']} pos={v['tp']+v['fn']}")
  return out,m,thr
face=[r for r in R if not r['eye']]
res={}
res['oily'],Mo,To=run('oily',[r for r in face if r['type'] is not None and r['set']!='ka1tj'],lambda r:int(r['type']=='oily'))
res['dry'],Md,Td=run('dry',[r for r in face if r['type'] in('dry','normal') and r['set']!='ka1tj'],lambda r:int(r['type']=='dry'))
# sensitive: rosacea/redness, plus eczema/psoriasis/inflamed acne count as sensitive per product definition
def ysens(r):
  g=r['gt']
  if r['set']=='skinmap': return int(g.get('Redness',0)>=COV)
  return int(any(g.get(k,0)>=COV for k in ('Rozasea','Egzema','Sedef ve Dokuntu')))
res['sens'],Ms,Ts=run('sens',[r for r in face if r['set'] in('skinmap','findings')],ysens)
# 3-class decision (oily first, then dry, else normal) on test
rows=[r for r in face if r['type'] in('oily','dry','normal') and r['set']!='ka1tj' and r['test']]
po=Mo.predict_proba(np.array([feats(r,'oily') for r in rows]))[:,1]; pdry=Md.predict_proba(np.array([feats(r,'dry') for r in rows]))[:,1]
dec=['oily' if po[i]>=To[r['tone']] else ('dry' if pdry[i]>=Td[r['tone']] else 'normal') for i,r in enumerate(rows)]
three={}
for c in ('oily','dry','normal'):
  y=np.array([int(r['type']==c) for r in rows]); p=np.array([int(d==c) for d in dec]); three[c]=prf(y,p)
print('\n3-class TEST',{c:(v['P'],v['R'],v['F1'],v['tp']+v['fn']) for c,v in three.items()})
res['threeClassTest']=three
import pickle; pickle.dump(dict(Mo=Mo,Md=Md,Ms=Ms,To=To,Td=Td,Ts=Ts,STATS=STATS),open(f'{S}/rf/fuse2_models.pkl','wb'))
json.dump(res,open(f'{S}/rf/fuse2_results.json','w'),indent=1,ensure_ascii=False)
