"""Step0 vs v4 candidate on the unchanged v2 product chain (saved rows; IoU .50 primary, .30 separate) + registered success rule."""
import json,sys,statistics as st
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parent)]
import compare_acne_v3_product as C
A=C.out
def load(fn):
    rows=[json.loads(l) for l in (A/f'evaluation-{fn}.jsonl').read_text().splitlines()]
    side=[json.loads(l) for l in (A/f'{fn}-boxes.jsonl').read_text().splitlines()];k=0;res={}
    for r in rows:
        setn=r.pop('set');ran='candidates' in r;b=side[k] if ran else None;k+=ran
        if ran: assert len(b['boxes'])==r['candidates']
        T=C.truth(r,setn) if ran else []
        res[(setn,r['sha256'])]=dict(cohort=r.get('cohort',setn),ran=ran,valid=r.get('valid',True),targets=r['targets'],neg=setn=='development' and r['targets']==0,T=T,
            m50=set(r['matched']) if ran else set(),m30=C.o2o(T,b['boxes'],.30) if ran else set(),cleanFP=r.get('cleanFP',0),unknown=r.get('unknownCandidates',0),cand=r.get('candidates',0),
            sec=b['totalSec'] if b else None,infer=b.get('inferSec') if b else None)
    assert k==len(side);return res
S=load('v3prod-step0');V=load(sys.argv[1] if len(sys.argv)>1 else 'v3prod-v4main-step-001000')
G={'scopeB-positive':lambda k,a:a['cohort']=='scopeB' and not a['neg'],'reviewedNegatives7':lambda k,a:a['cohort']=='scopeB' and a['neg'],
   'controls':lambda k,a:a['cohort']=='controls','heldOut20(replay pass, eyewear UNKNOWN)':lambda k,a:k[0]=='unusedEval'}
side=lambda b:max(b[2]-b[0],b[3]-b[1]); out={}; tot=dict(s50=0,v50=0,gained=0,lost=0,targets=0)
for g,f in G.items():
    keys=[k for k,a in S.items() if f(k,a) and a['ran'] and a['valid']]; row=dict(photos=len(keys))
    for n,R in (('step0',S),('v4',V)):
        small=[(k,i) for k in keys for i,t in enumerate(R[k]['T']) if side(t)<16]; med=[(k,i) for k in keys for i,t in enumerate(R[k]['T']) if side(t)>=16]
        row[n]=dict(targets=sum(R[k]['targets'] for k in keys),hit50=sum(len(R[k]['m50']) for k in keys),hit30=sum(len(R[k]['m30']) for k in keys),
                    small=f"{sum(1 for k,i in small if i in R[k]['m50'])}/{len(small)}",medium=f"{sum(1 for k,i in med if i in R[k]['m50'])}/{len(med)}",
                    reviewedNegFP=sum(R[k]['cleanFP'] for k in keys),fpPerPhoto=[R[k]['cleanFP'] for k in keys] if g.startswith('reviewed') else None,
                    unknown=sum(R[k]['unknown'] for k in keys),candidates=sum(R[k]['cand'] for k in keys),medianSec=round(st.median([R[k]['sec'] for k in keys]),2),
                    medianInferSec=round(st.median([R[k]['infer'] for k in keys if R[k]['infer'] is not None]),2) if any(R[k]['infer'] for k in keys) else None)
    row['gained50']=sum(len(V[k]['m50']-S[k]['m50']) for k in keys);row['lost50']=sum(len(S[k]['m50']-V[k]['m50']) for k in keys)
    row['gained30']=sum(len(V[k]['m30']-S[k]['m30']) for k in keys);row['lost30']=sum(len(S[k]['m30']-V[k]['m30']) for k in keys)
    if not g.startswith('reviewed'):
        tot['s50']+=row['step0']['hit50'];tot['v50']+=row['v4']['hit50'];tot['gained']+=row['gained50'];tot['lost']+=row['lost50'];tot['targets']+=row['step0']['targets']
    out[g]=row;print(g,json.dumps(row))
negFP=out['reviewedNegatives7']['v4']['reviewedNegFP']
crit=dict(hit50=f"{tot['v50']} >= {tot['s50']}+3",hitOK=tot['v50']>=tot['s50']+3,negFP=f'{negFP} <= 7',negOK=negFP<=7,lost=f"{tot['lost']} <= {tot['gained']}/3",lostOK=tot['lost']<=tot['gained']/3)
crit['SUCCESS']=crit['hitOK'] and crit['negOK'] and crit['lostOK'];out['totals']=tot;out['registeredSuccessRule']=crit;print(json.dumps(tot),json.dumps(crit))
(A/'comparison-v4-main.json').write_text(json.dumps(out,indent=1))
