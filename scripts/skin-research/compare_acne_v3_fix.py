"""Step0 vs failed step-300 vs corrected step-300 on the unchanged v2 product chain (saved outputs; IoU .50 primary, .30 separate)."""
import json,sys,statistics as st
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parent)]
import compare_acne_v3_product as C
M={'step0':C.load('v3prod-step0'),'old300':C.load('v3prod-step-000300'),'fix300':C.load('v3prod-fix-step-000300')}
assert M['step0'].keys()==M['old300'].keys()==M['fix300'].keys()
sets={'scopeB-positive':lambda k,a:a['cohort']=='scopeB' and not a['neg'],'scopeB-reviewedNegative':lambda k,a:a['cohort']=='scopeB' and a['neg'],
      'controls':lambda k,a:a['cohort']=='controls','unusedEval':lambda k,a:k[0]=='unusedEval'}
def area_ratio(R,keys):
    r=[]
    for k in keys:
        a=R[k]
        if not a['ran'] or a['targets']==0:continue
        T=C.truth({'sha256':k[1]},'development' if k[0]=='development' else k[0]);P=a['boxes']
        pr=sorted(((C.iou(t,p),i,j) for i,t in enumerate(T) for j,p in enumerate(P)),reverse=True);ut,up=set(),set()
        for v,i,j in pr:
            if v<.3:break
            if i in ut or j in up:continue
            ut.add(i);up.add(j);r.append((P[j][2]-P[j][0])*(P[j][3]-P[j][1])/max(1e-6,(T[i][2]-T[i][0])*(T[i][3]-T[i][1])))
    return dict(n=len(r),median=round(st.median(r),3)) if r else dict(n=0,median=None)
# attach final boxes
for nm,fn in (('step0','v3prod-step0'),('old300','v3prod-step-000300'),('fix300','v3prod-fix-step-000300')):
    side=[json.loads(l) for l in (C.out/f'{fn}-boxes.jsonl').read_text().splitlines()];rows=[json.loads(l) for l in (C.out/f'evaluation-{fn}.jsonl').read_text().splitlines()];k=0
    for r in rows:
        if 'candidates' in r: M[nm][(r['set'],r['sha256'])]['boxes']=side[k]['boxes'];k+=1
res={}
for g,f in sets.items():
    keys=[k for k,a in M['step0'].items() if f(k,a) and a['ran'] and a['valid']]
    row=dict(photos=len(keys))
    for nm,R in M.items():
        row[nm]=dict(targets=sum(R[k]['targets'] for k in keys),hit50=sum(len(R[k]['m50']) for k in keys),hit30=sum(len(R[k]['m30']) for k in keys),
                     reviewedNegFP=sum(R[k]['cleanFP'] for k in keys),unmatched=sum(R[k]['unknown'] for k in keys),candidates=sum(R[k]['cand'] for k in keys),
                     medianSec=round(st.median([R[k]['sec'] for k in keys]),2),boxAreaRatio=area_ratio(R,keys))
        if nm!='step0':
            for thr in ('m50','m30'): row[nm]['vsStep0_gained'+thr[1:]]=sum(len(R[k][thr]-M['step0'][k][thr]) for k in keys); row[nm]['vsStep0_lost'+thr[1:]]=sum(len(M['step0'][k][thr]-R[k][thr]) for k in keys)
    res[g]=row;print(g,json.dumps(row))
(C.out/'comparison-v3-fix300.json').write_text(json.dumps(res,indent=1))
