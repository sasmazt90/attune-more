"""Read-only diagnosis of the Step0 -> v3 step-900 product-chain regression from SAVED outputs only (no new inference)."""
import json,sys,statistics as st,collections
from pathlib import Path
HERE=Path(__file__).resolve().parent; sys.path[:0]=[str(HERE)]
import compare_acne_v3_product as C   # reuses truth(), iou(), o2o() and the aligned loader
def boxes_by_row(name):
    rows=[json.loads(l) for l in (C.out/f'evaluation-{name}.jsonl').read_text().splitlines()]
    side=[json.loads(l) for l in (C.out/f'{name}-boxes.jsonl').read_text().splitlines()];k=0;res={}
    for r in rows:
        if 'candidates' in r: res[(r['set'],r['sha256'])]=dict(row=r,boxes=side[k]['boxes']);k+=1
    return res
A=boxes_by_row('v3prod-step0');B=boxes_by_row('v3prod-step-000900')
side=lambda b:max(b[2]-b[0],b[3]-b[1])
out={}
# 1. reviewed negatives
neg=[k for k,v in A.items() if k[0]=='development' and v['row'].get('cohort')=='scopeB' and v['row']['targets']==0 and v['row'].get('valid')]
persist=new=gone=0;rows=[];newsides=[];oldsides=[]
for k in neg:
    a,b=A[k]['boxes'],B[k]['boxes']
    pa=C.o2o(a,b,.30) if a and b else set()   # indices of a that persist in b
    pb=C.o2o(b,a,.30) if a and b else set()
    persist+=len(pa);gone+=len(a)-len(pa);new+=len(b)-len(pb)
    newsides+=[side(x) for i,x in enumerate(b) if i not in pb];oldsides+=[side(x) for x in a]
    rows.append(dict(sha=k[1][:8],step0=dict(cand=len(a),cleanFP=A[k]['row']['cleanFP'],unknown=A[k]['row']['unknownCandidates']),
                     s900=dict(cand=len(b),cleanFP=B[k]['row']['cleanFP'],unknown=B[k]['row']['unknownCandidates'])))
out['reviewedNegatives']=dict(photos=len(neg),persisting=persist,new=new,vanished=gone,perPhoto=rows,
    newBoxSidePx=dict(median=st.median(newsides) if newsides else None,min=min(newsides,default=None),max=max(newsides,default=None)),
    step0BoxSidePx=sorted(round(s,1) for s in oldsides),
    note='cleanFP = candidate centre inside the reviewed known-negative mask (unchanged v2 evaluator); unknown = outside it, never counted as FP')
# 2. lost control targets at IoU>=.50
cat=collections.Counter();det=[]
for k,v in A.items():
    if v['row'].get('cohort')!='controls':continue
    T=C.truth(v['row'],'development');lost=set(v['row']['matched'])-set(B[k]['row']['matched'])
    pb=B[k]['boxes']
    for t in sorted(lost):
        best=max((C.iou(T[t],p) for p in pb),default=0.)
        m30=t in C.o2o(T,pb,.30)
        c='box-present-IoU.30-.50 (localization)' if m30 else 'final box overlaps but IoU<.30' if best>0 else 'no final box overlapping'
        cat[c]+=1;det.append(dict(sha=k[1][:8],target=t,truthSide=round(side(T[t]),1),bestIoU900=round(best,3),cause=c))
out['lostControlTargets']=dict(total=sum(cat.values()),byCause=cat,detail=det,
    rawCauseResolution='UNKNOWN for targets without a final box: raw pre-NMS candidates, scores and filter decisions were not saved, so raw-absence vs low score vs NMS vs anatomical filter cannot be separated without new inference')
# 3. box size bias on matched pairs (IoU>=.30), all product-valid positive sets
ratio=collections.defaultdict(list)
for nm,M in (('step0',A),('s900',B)):
    for k,v in M.items():
        if k[0]=='trainProbe' or v['row']['targets']==0:continue
        T=C.truth(v['row'],'development' if k[0]=='development' else k[0]);P=v['boxes']
        pr=sorted(((C.iou(t,p),i,j) for i,t in enumerate(T) for j,p in enumerate(P)),reverse=True);ut,up=set(),set()
        for val,i,j in pr:
            if val<.3:break
            if i in ut or j in up:continue
            ut.add(i);up.add(j);ratio[nm].append((P[j][2]-P[j][0])*(P[j][3]-P[j][1])/max(1e-6,(T[i][2]-T[i][0])*(T[i][3]-T[i][1])))
out['matchedBoxAreaRatioPredOverTruth']={nm:dict(n=len(r),median=round(st.median(r),3),p25=round(sorted(r)[len(r)//4],3),p75=round(sorted(r)[3*len(r)//4],3)) for nm,r in ratio.items()}
# product truth sizes (for scale comparison with the training target distribution)
ts=[side(t) for k,v in A.items() if k[0]!='trainProbe' for t in C.truth(v['row'],'development' if k[0]=='development' else k[0])]
out['productTruthSidePx']=dict(n=len(ts),median=st.median(ts),p25=sorted(ts)[len(ts)//4],p75=sorted(ts)[3*len(ts)//4])
Path(C.out/'diagnosis-v3-regression.json').write_text(json.dumps(out,indent=1,default=list));print(json.dumps({k:(v if k!='lostControlTargets' else {kk:vv for kk,vv in v.items() if kk!='detail'}) for k,v in out.items()},indent=1,default=list))
