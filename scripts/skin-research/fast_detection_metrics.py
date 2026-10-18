"""Same annotation-relative greedy AP; compute pairwise IoU once, not 10x.

No confidence/acceptance threshold change, approximate metric or source resize.
Ties retain the original (IoU, highest truth index) max tuple convention.
"""
import collections
import numpy as np
def detection_metrics(rows,pred,threshold):
    truth=[];matrices=[]
    for r,ps in zip(rows,pred):
        a,b,c,d=r['crop'];boxes=[ann['box'] for ann in r['annotations'] if ann['classId']==0 and a<=sum(ann['box'][::2])/2<=c and b<=sum(ann['box'][1::2])/2<=d];truth.append(boxes)
        p=np.array(ps,dtype=np.float64).reshape(-1,5);t=np.array(boxes,dtype=np.float64).reshape(-1,4)
        lo=np.maximum(p[:,None,:2],t[None,:,:2]);hi=np.minimum(p[:,None,2:4],t[None,:,2:4]);inter=np.maximum(0,hi-lo).prod(2);pa=(p[:,2]-p[:,0])*(p[:,3]-p[:,1]);ta=(t[:,2]-t[:,0])*(t[:,3]-t[:,1]);matrices.append(inter/np.maximum(1e-8,pa[:,None]+ta[None,:]-inter))
    ranked=sorted([(p[4],i,j) for i,ps in enumerate(pred) for j,p in enumerate(ps)],reverse=True,key=lambda v:v[0]);total=sum(map(len,truth));aps=[];main=None
    for boundary in np.arange(.5,1,.05):
        used=[np.zeros(len(t),bool) for t in truth];tp=[];fp=[]
        for score,i,j in ranked:
            ids=np.flatnonzero(~used[i])[::-1]
            if len(ids):
                values=matrices[i][j,ids];k=int(values.argmax());positive=values[k]>=boundary
                if positive:used[i][ids[k]]=True
            else:positive=False
            tp.append(int(positive));fp.append(int(not positive))
        ct=np.cumsum(tp);cf=np.cumsum(fp);rec=ct/max(1,total);precision=ct/np.maximum(1,ct+cf);aps.append(float(np.mean([precision[rec>=v].max(initial=0) for v in np.linspace(0,1,101)])))
        if main is None:
            n=sum(s>=threshold for s,_,_ in ranked);t=sum(tp[:n]);f=sum(fp[:n]);p=t/max(1,t+f);r=t/max(1,total);main=dict(precision=p,recall=r,F1=2*p*r/max(1e-8,p+r),truePositive=t,falsePositive=f,falseNegative=total-t,annotationRelativeFalseCandidatesPerPhoto=f/max(1,len(rows)),images=len(rows),sourceGroups=len({r['group'] for r in rows}),unlabelledAreasKnownHealthy=False)
    return dict(**main,AP50=aps[0],mAP50to95=float(np.mean(aps)),threshold=threshold)
