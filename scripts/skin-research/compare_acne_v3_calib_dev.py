"""Four-way development comparison: Step0/.30, Step0/.001, corrected-300/.30, corrected-300/.005 (saved rows reused for .30)."""
import json,sys,statistics as st
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parent)]
import compare_acne_v3_product as C
A=C.out; B=C.code/'audit-results/acne-v3-calib-dev-20261016'
CFG={'step0@.30':(A,'v3prod-step0'),'step0@.001':(B,'step0-c0.001'),'fix300@.30':(A,'v3prod-fix-step-000300'),'fix300@.005':(B,'fix300-c0.005')}
def load(d,fn):
    rows=[json.loads(l) for l in (d/f'evaluation-{fn}.jsonl').read_text().splitlines()]
    side=[json.loads(l) for l in (d/f'{fn}-boxes.jsonl').read_text().splitlines()];k=0;res={}
    for r in rows:
        setn=r.pop('set');ran='candidates' in r;b=side[k] if ran else None;k+=ran
        if ran: assert len(b['boxes'])==r['candidates']
        T=C.truth(r,setn) if ran else []
        res[(setn,r['sha256'])]=dict(cohort=r.get('cohort',setn),ran=ran,valid=r.get('valid',True),targets=r['targets'],neg=setn=='development' and r['targets']==0,
            m50=set(r['matched']) if ran else set(),m30=C.o2o(T,b['boxes'],.30) if ran else set(),cleanFP=r.get('cleanFP',0),unknown=r.get('unknownCandidates',0),
            cand=r.get('candidates',0),sec=b['totalSec'] if b else None,raw=b.get('rawCandidates') if b else None)
    assert k==len(side);return res
M={n:load(*v) for n,v in CFG.items()}
ref=M['step0@.30']
G={'Scope B positives':lambda k,a:a['cohort']=='scopeB' and not a['neg'],'Reviewed negatives (7 valid)':lambda k,a:a['cohort']=='scopeB' and a['neg'],
   'Product-valid controls':lambda k,a:a['cohort']=='controls','Held-out 20 (replay pass, eyewear UNKNOWN; development)':lambda k,a:k[0]=='unusedEval'}
out={}
for g,f in G.items():
    keys=[k for k,a in ref.items() if f(k,a) and a['ran'] and a['valid']];row=dict(photos=len(keys))
    for n,R in M.items():
        x=dict(targets=sum(R[k]['targets'] for k in keys),hit50=sum(len(R[k]['m50']) for k in keys),hit30=sum(len(R[k]['m30']) for k in keys),
               reviewedNegFPperPhoto=round(sum(R[k]['cleanFP'] for k in keys)/len(keys),2),unknown=sum(R[k]['unknown'] for k in keys),finalCandidates=sum(R[k]['cand'] for k in keys),
               rawCandidates=(sum(R[k]['raw'] for k in keys) if all(R[k]['raw'] is not None for k in keys) else None),medianSec=round(st.median([R[k]['sec'] for k in keys]),2))
        for base,BR in (('vsStep0@.30',ref),('vsSameModel@.30',M[n.split('@')[0]+'@.30'])):
            if BR is R: continue
            x[base]=dict(gained50=sum(len(R[k]['m50']-BR[k]['m50']) for k in keys),lost50=sum(len(BR[k]['m50']-R[k]['m50']) for k in keys),
                         gained30=sum(len(R[k]['m30']-BR[k]['m30']) for k in keys),lost30=sum(len(BR[k]['m30']-R[k]['m30']) for k in keys))
        if n=='fix300@.005':
            O=M['step0@.001'];x['vsStep0@.001']=dict(gained50=sum(len(R[k]['m50']-O[k]['m50']) for k in keys),lost50=sum(len(O[k]['m50']-R[k]['m50']) for k in keys))
        row[n]=x
    out[g]=row;print(g,json.dumps(row))
(B/'comparison.json').write_text(json.dumps(out,indent=1))
