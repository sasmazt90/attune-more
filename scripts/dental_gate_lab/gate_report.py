"""Before/after client gate table + backend (dental_quality) parity on the same frames."""
import json,sys,cv2
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
from dental_analysis import dental_quality
EXP={'src0':['FRONT','BITE'],'src1':['RIGHT'],'src2':['FRONT','BITE'],'src3':['FRONT','BITE'],'src4':[],'src5':['FRONT','BITE'],'src7':['LEFT'],'src8':['LEFT'],'src9':['LEFT'],
'syn_front_full':['FRONT'],'syn_left_full':['RIGHT'],'syn_right_full':['LEFT'],'syn_front_bite_full':['FRONT','BITE']}
NEVER={'syn_front_full':['BITE'],'src1':['BITE']}  # open mouth must never pass BITE
B={x['id']:x for x in json.load(open('gates-before.json'))};A={x['id']:x for x in json.load(open('gates-after.json'))};L={x['id']:x for x in json.load(open('all-lm.json'))}
out={'frames':[],'summary':{}};acc={'before':0,'after':0};n=0;bad={'before':0,'after':0};parity=[0,0]
for k in sorted(A):
    src=A[k]['src'];row={'id':k,'source':src,'expected':EXP[src]}
    for name,G in (('before',B),('after',A)):
        g=G[k]['gates'];row[name]={p:(g[p]['valid'],g[p]['reasons'][:1]) for p in ['FRONT','RIGHT','LEFT','BITE']}
        acc[name]+=sum(g[p]['valid'] for p in EXP[src]);bad[name]+=sum(g[p]['valid'] for p in NEVER.get(src,[]))
    n+=len(EXP[src])
    im=cv2.imread(L[k]['frame'])
    for p in EXP[src]:
        if A[k]['gates'][p]['valid']:
            q=dental_quality(im,L[k]['landmarks'],p=='BITE');parity[1]+=1;parity[0]+=q['valid'];row.setdefault('backend',{})[p]=(q['valid'],q['reasons'])
    out['frames'].append(row)
out['summary']=dict(expectedPoseChecks=n,acceptedBefore=acc['before'],acceptedAfter=acc['after'],openMouthAcceptedAsBite=bad,backendAgreesOnClientAccepted=f'{parity[0]}/{parity[1]}')
json.dump(out,open(sys.argv[1],'w'),indent=1,ensure_ascii=False);print(json.dumps(out['summary']))
for r in out['frames']:
    fails={p:r['after'][p][1] for p in r['expected'] if not r['after'][p][0]}
    be={p:v for p,v in r.get('backend',{}).items() if not v[0]}
    if fails or be:print(r['id'],'clientFail',fails,'backendFail',be)
