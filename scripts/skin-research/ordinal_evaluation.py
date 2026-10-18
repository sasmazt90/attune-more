"""Case-weighted ordinal errors and case-cluster bootstrap; no imputed truth."""
import numpy as np

def evaluate(truth,prediction,cases,seed=20261008):
    y=np.asarray(truth,dtype=int);p=np.asarray(prediction,dtype=int)
    assert len(y)==len(p)==len(cases)>0 and np.all((y>=0)&(y<=3)) and np.all((p>=0)&(p<=3))
    groups=sorted(set(cases));weights=np.array([1/sum(c==v for c in cases) for v in cases]);weights/=weights.sum()
    def summary(w):
        matrix=np.zeros((4,4),float)
        for a,b,c in zip(y,p,w):matrix[a,b]+=c
        distance=(np.arange(4)[:,None]-np.arange(4)[None,:])**2/9
        expected=np.outer(matrix.sum(1),matrix.sum(0));den=(distance*expected).sum()
        return {'MAE':float(np.sum(w*np.abs(p-y))),'bias':float(np.sum(w*(p-y))),
                'exactAgreement':float(np.sum(w*(p==y))),'withinOneAgreement':float(np.sum(w*(np.abs(p-y)<=1))),
                'quadraticWeightedKappa':float(1-(distance*matrix).sum()/den) if den>0 else None,
                'caseWeightedConfusion':matrix.tolist()}
    result=summary(weights);rng=np.random.default_rng(seed);replicates=[]
    for _ in range(1000):
        selected=rng.choice(groups,len(groups),replace=True)
        w=np.array([sum(c==v for c in selected)/sum(c==v for c in cases) for v in cases],dtype=float)
        w/=w.sum();replicates.append(summary(w))
    result['caseBootstrap95']={k:np.percentile([r[k] for r in replicates if r[k] is not None],[2.5,97.5]).tolist() for k in ['MAE','bias','exactAgreement','withinOneAgreement','quadraticWeightedKappa'] if any(r[k] is not None for r in replicates)}
    result['images']=len(y);result['independentCases']=len(groups)
    return result
