import json,sys,statistics as st
from pathlib import Path
sys.path[:0]=['scripts/skin-research']
import run_acne_v2_pilot as v2
code=Path('.').resolve(); togg=code.parent; v2.setup_paths(code,togg)
out=Path('audit-results/acne-v3-20261015'); live=togg/'attune-live-test'/v2.TAKEOVER
ledger={r['sha256']:r for r in v2.read_json(live/'inputs/original-reviewed-detector-data.json')['rows']}
scope={r['sha256']:r for r in v2.read_json(live/'inputs/annotation-scope-manifest.json')['images']}
man={p['sha256']:p for p in v2.read_json('docs/acne-data-v2-manifest-20261015.json')['photos']}
def truth(row,setn):
    s=row['sha256']
    if setn=='development':
        r=ledger[s]; anns=[v for v in scope[s]['annotations'] if v['scopeCategory']=='IN_SCOPE_VISIBLE_REGION'] if s in scope else r.get('annotations',[])
        return [v['box'] for v in anns]
    return [t['box'] for t in man[s]['targets']]
def iou(a,b):
    ix=max(0,min(a[2],b[2])-max(a[0],b[0]));iy=max(0,min(a[3],b[3])-max(a[1],b[1]));i=ix*iy;u=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-i;return i/u if u>0 else 0
def o2o(T,P,thr):
    pr=sorted(((iou(t,p),i,j) for i,t in enumerate(T) for j,p in enumerate(P)),reverse=True);ut,up,m=set(),set(),[]
    for v,i,j in pr:
        if v<thr:break
        if i in ut or j in up:continue
        ut.add(i);up.add(j);m.append(i)
    return set(m)
def load(name):
    rows=[json.loads(l) for l in (out/f'evaluation-{name}.jsonl').read_text().splitlines()]
    side=[json.loads(l) for l in (out/f'{name}-boxes.jsonl').read_text().splitlines()]
    k=0;res={}
    for r in rows:
        setn=r.pop('set'); ran='candidates' in r
        b=None
        if ran:
            b=side[k];k+=1
            assert len(b['boxes'])==r['candidates'],('ALIGN',name,r['sha256'][:8])
        cohort=r.get('cohort',setn)
        T=truth(r,setn) if ran else []
        res[(setn,r['sha256'])]=dict(cohort=cohort,ran=ran,valid=r.get('valid',True),targets=r['targets'],m50=set(r['matched']) if ran else set(),
              m30=o2o(T,b['boxes'],.30) if ran else set(),cleanFP=r.get('cleanFP',0),unknown=r.get('unknownCandidates',0),cand=r.get('candidates',0),sec=b['totalSec'] if b else None,infer=b['inferSec'] if b else None,neg=(setn=='development' and r['targets']==0))
    assert k==len(side)
    return res
A=load('v3prod-step0');B=load('v3prod-step-000900')
assert A.keys()==B.keys()
hist={(r['set'],r['sha256']):r for r in map(json.loads,Path('audit-results/acne-v2-pilot-20261015/evaluation-step0.jsonl').read_text().splitlines())}
par=sum(1 for k,a in A.items() if k in hist and a['ran'] and set(hist[k].get('matched',[]))==a['m50'] and hist[k].get('cleanFP',0)==a['cleanFP'] and hist[k].get('candidates')==a['cand'])
print('historicParity rowsEqual',par,'of',sum(1 for k,a in A.items() if k in hist and a['ran']))
groups={'scopeB-positive':lambda k,a:a['cohort']=='scopeB' and not a['neg'],'scopeB-reviewedNegative':lambda k,a:a['cohort']=='scopeB' and a['neg'],
        'controls':lambda k,a:a['cohort']=='controls','unusedEval(replay pass, eyewear UNKNOWN)':lambda k,a:k[0]=='unusedEval','trainProbe(seen in v3 training? see note)':lambda k,a:k[0]=='trainProbe'}
for g,f in groups.items():
    keys=[k for k,a in A.items() if f(k,a)]
    ran=[k for k in keys if A[k]['ran'] and A[k]['valid']]; notvalid=[k for k in keys if not(A[k]['ran'] and A[k]['valid'])]
    line=dict(photos=len(keys),productValidRun=len(ran),excludedNotValidOrNoSnapshot=len(notvalid))
    for nm,M in (('step0',A),('s900',B)):
        T=sum(M[k]['targets'] for k in ran)
        line[nm]=dict(targets=T,hit50=sum(len(M[k]['m50']) for k in ran),hit30=sum(len(M[k]['m30']) for k in ran),reviewedNegFP=sum(M[k]['cleanFP'] for k in ran),
                      unmatchedUnknown=sum(M[k]['unknown'] for k in ran),candidatesPerPhoto=round(sum(M[k]['cand'] for k in ran)/max(1,len(ran)),2),
                      medianSec=round(st.median([M[k]['sec'] for k in ran]),2) if ran else None)
    for thr in ('m50','m30'):
        line['gained'+thr[1:]]=sum(len(B[k][thr]-A[k][thr]) for k in ran); line['lost'+thr[1:]]=sum(len(A[k][thr]-B[k][thr]) for k in ran)
    print(g,json.dumps(line))
