"""Person-level check of every displayed criterion against the generation labels of the 150 automated characters.
Score = max over the relevant regions (and the 3 poses) of the evidence; AUC + precision/recall at the best-F1 threshold."""
import json,re,collections,numpy as np
from sklearn.metrics import roc_auc_score
S='/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
st={p['id']:p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status']=='approved'}
I={};F=[]
for tag in ('_k5','_k6'):
  I.update({it['id']:it for it in json.load(open(f'{S}/rf/items{tag}.json'))}); F+=json.load(open(f'{S}/rf/feats2{tag}.json'))
by=collections.defaultdict(lambda:collections.defaultdict(dict))
for r in F:
  kid=re.match(r'(K-\d+)',I[r['id']]['key']).group(1); by[kid][r['region']][r['id']]=r['f']
def mx(kid,regions,keys):
  v=[float(f.get(k) or 0) for rg in regions for f in by[kid].get(rg,{}).values() for k in keys]; return max(v) if v else 0.0
CHEEK=['cheek_imgL','cheek_imgR']; ALL=['forehead','nose','cheek_imgL','cheek_imgR','chin']; EYE=['eye_imgL','eye_imgR']
ACNE=['findings_Akne_max','acnes_papule_max','acnes_pustule_max','acnes_nodule_max','acnes_skin_acne_max']
T={
 'Sivilce':(lambda p:p['acne']!='yok', lambda k:mx(k,ALL,ACNE)),
 'Güneş lekesi':(lambda p:'güneş lekesi' in p['extras'], lambda k:mx(k,ALL,['findings_Gunes_Lekesi_max'])),
 'Melazma':(lambda p:'melazma (yanaklarda)' in p['extras'], lambda k:mx(k,CHEEK,['findings_Gunes_Lekesi_max'])),
 'Ben':(lambda p:'ben (yanakta)' in p['extras'], lambda k:mx(k,CHEEK,['findings_Riskli_Ben_max'])),
 'Uçuk':(lambda p:'dudakta uçuk' in p['extras'], lambda k:mx(k,ALL,['findings_Ucuk_max'])),
 'Rozasea':(lambda p:p['sens']=='rozasea', lambda k:mx(k,ALL,['findings_Rozasea_max'])),
 'Egzama':(lambda p:p['sens']=='egzama', lambda k:mx(k,ALL,['findings_Egzema_max'])),
 'Sedef':(lambda p:p['sens']=='sedef', lambda k:mx(k,ALL,['findings_Sedef_ve_Dokuntu_max'])),
 'Kızarıklık (genel)':(lambda p:p['sens']!='yok', lambda k:mx(k,ALL,['skinmap_Redness_max','findings_Rozasea_max','findings_Egzema_max'])),
 'Kaz ayağı':(lambda p:'kaz ayağı' in p['extras'], lambda k:mx(k,EYE,['frac_wrinkle'])),
 'Alın kırışıklığı':(lambda p:'alın kırışıklığı' in p['extras'], lambda k:mx(k,['forehead'],['frac_wrinkle'])),
 'Geniş gözenek':(None,None),
}
res={}
for name,(yl,sf) in T.items():
  if yl is None: continue
  ks=[k for k in st if k in by]; y=np.array([yl(st[k]) for k in ks]); s=np.array([sf(k) for k in ks])
  if y.sum()<3: print(name,'yetersiz pozitif'); continue
  auc=roc_auc_score(y,s); best=None
  for t in np.unique(s):
    tp=((s>=t)&y).sum(); fp=((s>=t)&~y).sum(); fn=((s<t)&y).sum(); f1=2*tp/max(2*tp+fp+fn,1)
    if best is None or f1>best[0]: best=(f1,t,tp/max(tp+fp,1),tp/max(tp+fn,1))
  # precision >= .8 operating point
  p80=None
  for t in sorted(np.unique(s)):
    k=s>=t
    if k.sum()>=3 and y[k].mean()>=.8: p80=(t,y[k].mean(),(k&y).sum()/y.sum()); break
  res[name]=dict(pos=int(y.sum()),n=len(y),auc=round(auc,3),bestF1=dict(thr=round(float(best[1]),3),P=round(best[2],2),R=round(best[3],2)),P80=None if p80 is None else dict(thr=round(float(p80[0]),3),P=round(float(p80[1]),2),R=round(float(p80[2]),2)))
  print(f"{name:20s} pozitif {y.sum():3d}/{len(y)} AUC={auc:.2f} | en iyi F1: P={best[2]:.2f} R={best[3]:.2f} | P≥0.8: {'yok' if p80 is None else f'R={p80[2]:.2f}'}")
json.dump(res,open(f'{S}/rf/crit_eval.json','w'),ensure_ascii=False,indent=1)
