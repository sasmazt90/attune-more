"""SCIN head/neck (smartphone photos, dermatologist labels): case-level check of our evidence per skin-tone group.
Score of a case = max over its images of the model's max confidence for that class (full-frame boxes ignored)."""
import json,ast,collections,numpy as np,pandas as pd
from sklearn.metrics import roc_auc_score
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
I=json.load(open(f'{S}/rf/items_scin.json')); P={m:json.load(open(f'{S}/rf/pred_scin_{m}.json')) for m in ('findings','skinmap','acnes')}
def cats(ds):
  J=json.load(open(f'{ds}/valid/_annotations.coco.json')); c=collections.Counter(a['category_id'] for a in J['annotations']); out={}
  for x in J['categories']:
    if x['name'] not in out or c[x['id']]>c[out[x['name']]]: out[x['name']]=x['id']
  return {v:k for k,v in out.items()}
CAT={'findings':cats(f'{S}/evalds/findings'),'skinmap':cats(f'{S}/evalds/skinmap'),'acnes':cats(f'{S}/evalds/acnes')}
def img_scores(it):
  out=collections.defaultdict(float); cnt=collections.Counter()
  for m,dets in P.items():
    for c,s,(x0,y0,x1,y1) in dets[str(it['id'])]:
      if (x1-x0)*(y1-y0)>0.8*it['w']*it['h']: continue
      n=CAT[m].get(c)
      if n is None: continue
      k=f'{m}:{n}'; out[k]=max(out[k],s)
      if s>=0.35: cnt[k]+=1
  return out,cnt
cases=collections.defaultdict(lambda:collections.defaultdict(float))
for it in I:
  sc,_=img_scores(it)
  for k,v in sc.items(): cases[it['case_id']][k]=max(cases[it['case_id']][k],v)
c=pd.read_csv(f'{S}/scin/cases.csv'); l=pd.read_csv(f'{S}/scin/labels.csv'); d=c.merge(l,on='case_id'); d=d[d['body_parts_head_or_neck']=='YES']
def top(v):
  try: dd=ast.literal_eval(v); return max(dd,key=dd.get) if dd else None
  except Exception: return None
def fst(r):
  for col in ('dermatologist_fitzpatrick_skin_type_label_1','fitzpatrick_skin_type'):
    v=str(r.get(col,''))
    for k in ('1','2','3','4','5','6'):
      if k in v: return int(k)
  return None
rows=[]
for _,r in d.iterrows():
  cid=str(r['case_id'])
  if cid not in cases: continue
  rows.append(dict(cid=cid,label=top(r['weighted_skin_condition_label']),flaky=r['textures_rough_or_flaky']=='YES',fst=fst(r),s=cases[cid]))
print('cases',len(rows),'with FST',sum(x['fst'] is not None for x in rows),collections.Counter(('I-II' if x['fst'] and x['fst']<=2 else 'III-IV' if x['fst'] and x['fst']<=4 else 'V-VI' if x['fst'] else '?') for x in rows))
ECZ={'Eczema','Allergic Contact Dermatitis','Irritant Contact Dermatitis','CD - Contact dermatitis','Seborrheic Dermatitis','Acute dermatitis, NOS','Perioral Dermatitis','Photodermatitis','Acute and chronic dermatitis','Stasis Dermatitis'}
TASKS={
 'Egzama/dermatit':(lambda x:x['label'] in ECZ, lambda s:s['findings:Egzema']),
 'Rozasea':(lambda x:x['label']=='Rosacea', lambda s:s['findings:Rozasea']),
 'Rozasea (kızarıklık dahil)':(lambda x:x['label']=='Rosacea', lambda s:max(s['findings:Rozasea'],s['skinmap:Redness'])),
 'Akne':(lambda x:x['label']=='Acne', lambda s:max(s['acnes:papule'],s['acnes:pustule'],s['acnes:nodule'],s['acnes:blackhead'],s['acnes:whitehead'])),
 'Sedef':(lambda x:x['label']=='Psoriasis', lambda s:s['findings:Sedef ve Dokuntu']),
 'Pürüzlü/pul pul (kişi bildirimi)':(lambda x:x['flaky'], lambda s:max(s['findings:Kuru Cilt'],s['findings:Egzema'],s['findings:Sedef ve Dokuntu'])),
 'Hassas (egzama+sedef+rozasea)':(lambda x:x['label'] in ECZ|{'Rosacea','Psoriasis'}, lambda s:max(s['skinmap:Redness'],s['findings:Rozasea'],s['findings:Egzema'],s['findings:Sedef ve Dokuntu'])),
}
G=lambda f:'I-II' if f and f<=2 else ('III-IV' if f and f<=4 else ('V-VI' if f else None))
res={}
for name,(yl,sf) in TASKS.items():
  y=np.array([int(yl(x)) for x in rows]); s=np.array([sf(x['s']) for x in rows])
  line=f"{name:34s} pos={y.sum():3d}/{len(y)} AUC={roc_auc_score(y,s):.3f}"
  best=max(np.arange(0.1,0.9,0.05),key=lambda t:(lambda tp,fp,fn:2*tp/max(2*tp+fp+fn,1))(((y==1)&(s>=t)).sum(),((y==0)&(s>=t)).sum(),((y==1)&(s<t)).sum()))
  tp=((y==1)&(s>=best)).sum(); fp=((y==0)&(s>=best)).sum(); fn=((y==1)&(s<best)).sum()
  line+=f" | thr={best:.2f} P={tp/max(tp+fp,1):.2f} R={tp/max(tp+fn,1):.2f}"
  per={}
  for g in ('I-II','III-IV','V-VI'):
    gi=[i for i,x in enumerate(rows) if G(x['fst'])==g]
    if len(gi)>10 and 2<=y[gi].sum()<len(gi)-2: per[g]=round(roc_auc_score(y[gi],s[gi]),3); line+=f"  {g}:AUC={per[g]}(pos {y[gi].sum()})"
  res[name]=dict(pos=int(y.sum()),n=len(y),auc=round(roc_auc_score(y,s),3),perTone=per); print(line)
json.dump(res,open(f'{S}/rf/scin_results.json','w'),ensure_ascii=False,indent=1)
