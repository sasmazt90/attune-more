"""Frozen DEV comparison, one application only, no detector or model changes."""
import collections,io,sys,tarfile,time
import numpy as np
from verifier_v4_round import *
sys.path.insert(0,str(ROOT/'scripts/skin-research/external_acne'))
import common_scope_compare as CS
import relabel_compare as RC
CL=['false','duplicate','onUncertain','onOther','nearOutOfScopeTarget','unreviewedInOval','nonSkin','unreviewedPhoto']

def key(b):return tuple(round(float(v),3) for v in b[:4])

def source_inventory():
 man=read(SRC/'audit-results/acne-v4-data/manifest-v4.json')['photos']+read(SRC/'audit-results/acne-v6/devext/manifest.json')['photos'];out={}
 for p in man:
  f=p['file'];local=TOGG/f.split('/TOGG/')[-1] if '/TOGG/' in f else SRC/'audit-results/acne-v4-data'/f
  out[p['sha256'][:12]]=dict(p,file=str(local),set='devext' if '/devext/' in str(local).replace('\\','/') else 'dev')
 return out

def prepare_dev():
 assert not (OUT/'dev-inputs.json').exists(),'DEV_INPUTS_ALREADY_FROZEN'
 import cv2
 photos=source_inventory();ids={p.stem for p in (V1/'dev').glob('*.json')};paths=[SRC/'docs/acne-point-relabel-layer1-20261016.json',SRC/'docs/acne-common-scope-results-20261016.json',SRC/'audit-results/acne-relabel/layer1-masks.tgz',V1/'dev-decisions.json',V3/'dev-decisions-v3.json',TOGG/'claude-progress/acne-verifier-v3-dev-results-20261016.json']
 paths += [SRC/'audit-results/acne-v6/eval'/s/'replay.jsonl' for s in ['dev','devext']]
 paths += [SRC/'audit-results/acne-v4-data/manifest-v4.json',SRC/'audit-results/acne-v6/devext/manifest.json']
 assert sha(paths[0])==read(paths[1])['inputHashes']['layer1']
 # Evaluation source metadata is used ONLY for exclusion and grouping checks before fit.
 trainman={p['sha256'][:12]:p for p in read(SRC/'audit-results/acne-v6-data/manifest-v6.json')['photos']};groups=read(V1/'labels.json')['groups'];excludes={}
 for name in ['acne-unused-test-eligibility-20261016.json','acne-unused-test-labels-20261016.json','acne-pos-supplement-index-20261016.json']:
  path=SRC/'docs'/name;paths.append(path);found=set()
  def walk(v):
   if isinstance(v,str) and len(v) in [12,64] and all(c in '0123456789abcdef' for c in v):found.add(v[:12])
   elif isinstance(v,dict):
    for k,z in v.items():walk(k);walk(z)
   elif isinstance(v,list):
    for z in v:walk(z)
  walk(read(path));assert not set(groups)&found,'PRIOR_TEST_IN_TRAIN';excludes[name]=sorted(found)
 def dhash(file):
  im=cv2.imread(str(file));assert im is not None;g=cv2.resize(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),(9,8),interpolation=cv2.INTER_AREA);return (g[:,1:]>g[:,:-1]).flatten()
 dh={ph:dhash(photos[ph]['file']) for ph in ids}
 near=[]
 for ph in groups:
  h=dhash(SRC/'audit-results/acne-v6-data'/trainman[ph]['file'])
  for d,v in dh.items():
   dist=int(np.count_nonzero(h!=v))
   if dist<=10:near.append(dict(train=ph,dev=d,distance=dist))
 assert not near,'TRAIN_DEV_NEAR_DUPLICATE'
 assert {trainman[ph]['researchGroup'] for ph in groups}.isdisjoint(photos[d]['researchGroup'] for d in ids),'TRAIN_DEV_SOURCE_GROUP'
 for ph in ids:
  assert sha(photos[ph]['file'])==photos[ph]['sha256'];paths.append(Path(photos[ph]['file']))
 atomic('dev-inputs.json',dict(files={str(p):sha(p) for p in paths},photos={ph:photos[ph] for ph in sorted(ids)},frozenScoredPhotos=28,applyPhotos=42,denominator=108,priorTestIDs=excludes,trainDevNearDuplicates=near,sourceGroupOverlap=0,eyewear='UNKNOWN/not replayed; cached research chain, not live camera acceptance'))
 print('DEV_INPUTS_FROZEN',len(ids),'no training overlap')

def run():
 from heavy_job_lease import HeavyJobLease
 import cv2
 from acne_candidate_verifier import Verifier
 assert not (OUT/'dev-start.json').exists() and not (OUT/'dev-results.json').exists(),'SINGLE_DEV_ALREADY_STARTED'
 freeze=read(OUT/'freeze.json')
 for name,d in freeze['files'].items():assert sha(OUT/name)==d,'FROZEN_MODEL_DATA_CHANGED'
 inputs=read(OUT/'dev-inputs.json')
 for p,d in inputs['files'].items():assert sha(p)==d,'DEV_INPUT_CHANGED'
 verify_inputs()
 with HeavyJobLease('CDC-verifier-v4-one-frozen-DEV-comparison',peak_mib=900,minimum_available_mib=1600,memory_metric='private') as lease:
  cv2.setNumThreads(2);start=time.perf_counter();atomic('dev-start.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),freezeSHA256=sha(OUT/'freeze.json'),devInputsSHA256=sha(OUT/'dev-inputs.json'),evaluationCount=1));status('single frozen DEV evaluation running',1868,1868)
  Ds={'v1':read(V1/'dev-decisions.json'),'v3':read(V3/'dev-decisions-v3.json')};v=Verifier(OUT/'verifier-v4.json');new={};apply0=time.perf_counter();applycompute=0.
  for j in sorted((V1/'dev').glob('*.json')):
   lease.check();r=read(j)
   with np.load(j.with_suffix('.npz')) as archive:F=archive['features'];assert F.shape==(len(r['final']),1920)
   for n,d in Ds.items():assert d['photos'][r['photo']]['final']==r['final'],'BASE_CANDIDATES_CHANGED'
   t=time.perf_counter();p=v.proba(F) if len(F) else np.zeros(0);k=p>=v.threshold;dt=time.perf_counter()-t;applycompute+=dt
   new[r['photo']]=dict(kind=r['kind'],final=r['final'],proba=p.tolist(),keep=k.tolist(),verifierSec=dt)
  atomic('dev-decisions-v4.json',dict(model=sha(OUT/'verifier-v4.json'),threshold=v.threshold,photos=new));Ds['v4']=dict(photos=new);applysec=time.perf_counter()-apply0
  L=read(SRC/'docs/acne-point-relabel-layer1-20261016.json')['photos'];photos=sorted(L);rp={}
  for s in ['dev','devext']:
   with (SRC/'audit-results/acne-v6/eval'/s/'replay.jsonl').open(encoding='utf8') as f:
    for line in f:
     r=__import__('json').loads(line);ph=r['sha256'][:12]
     if ph in L:rp[ph]={'landmarks':r['landmarks']}
  S={'Step0':{ph:[b[:4] for b in new[ph]['final']] for ph in photos}}
  for name,d in Ds.items():S[name]={ph:[b[:4] for b,k in zip(d['photos'][ph]['final'],d['photos'][ph]['keep']) if k] for ph in photos}
  res={n:{} for n in S};score0=time.perf_counter();maskpix=0;reviewed=[]
  with tarfile.open(SRC/'audit-results/acne-relabel/layer1-masks.tgz') as tar:
   for ph in photos:
    lease.check();lab=L[ph];raw=tar.extractfile('masks/'+ph+'.png').read();assert __import__('hashlib').sha256(raw).hexdigest()==lab['mask']['sha256']
    mask=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_GRAYSCALE)>0;maskpix+=int(mask.sum());h,w=mask.shape
    assert (w,h)==(inputs['photos'][ph]['width'],inputs['photos'][ph]['height']);oval=RC.oval_mask(rp[ph],w,h)
    if mask.any():reviewed.append(ph)
    for n in S:res[n][ph]=CS.classify(lab,S[n][ph],mask,oval,.03*lab['faceWidthPx'])
  tab={n:dict(found=sum(len(res[n][ph]['hitIds']) for ph in photos),of=sum(len(res[n][ph]['inScope']) for ph in photos),points=sum(len(res[n][ph]['classes']) for ph in photos),**{c:sum(res[n][ph]['classes'].count(c) for ph in photos) for c in CL}) for n in S}
  old=read(TOGG/'claude-progress/acne-verifier-v3-dev-results-20261016.json')
  for n,k in [('Step0','A'),('v1','v1'),('v3','v3')]:assert tab[n]==old['table'][k],('EXACT_BASELINE_PARITY',n,tab[n],old['table'][k])
  ids={n:{(ph,h) for ph in photos for h in res[n][ph]['hitIds']} for n in S};fmt=lambda s:sorted(f'{a}#{b}' for a,b in s)
  targets={n:dict(gainedVsV3=fmt(ids[n]-ids['v3']),lostVsV3=fmt(ids['v3']-ids[n])) for n in S}
  pointdiff={};per={}
  for ph in photos:
   classes={n:{key(b):c for b,c in zip(S[n][ph],res[n][ph]['classes'])} for n in S};false={n:{b for b,c in d.items() if c=='false'} for n,d in classes.items()}
   pointdiff[ph]=dict(removedFalse=[dict(box=list(k),v4Class=classes['v4'].get(k,'rejected')) for k in sorted(false['v3']-false['v4'])],addedFalse=[dict(box=list(k),v3Class=classes['v3'].get(k,'rejected')) for k in sorted(false['v4']-false['v3'])],removedCandidates=[dict(box=list(k),classV3=classes['v3'][k]) for k in sorted(classes['v3'].keys()-classes['v4'].keys())],addedCandidates=[dict(box=list(k),classV4=classes['v4'][k]) for k in sorted(classes['v4'].keys()-classes['v3'].keys())])
   per[ph]=dict(set=inputs['photos'][ph]['set'],reviewed=ph in reviewed,targets=len(res['Step0'][ph]['inScope']),**{n:dict(found=len(res[n][ph]['hitIds']),hitIds=res[n][ph]['hitIds'],points=len(S[n][ph]),**{c:res[n][ph]['classes'].count(c) for c in CL}) for n in S})
  distributions={n:dict(all28=[per[ph][n]['false'] for ph in photos],reviewedOnly=[per[ph][n]['false'] for ph in reviewed],reviewedPhotos=len(reviewed),meanReviewed=tab[n]['false']/len(reviewed),medianReviewed=float(np.median([per[ph][n]['false'] for ph in reviewed])),maximum=max(per[ph][n]['false'] for ph in photos),falsePerReviewedMP=tab[n]['false']/(maskpix/1e6)) for n in S}
  selection=tab['v4']['found']>=68 and tab['v4']['false']<=60 and (tab['v4']['found']>68 or tab['v4']['false']<60)
  negs=[ph for ph,r in new.items() if r['kind']=='negative-photo'];clear={n:sum(sum(Ds[n]['photos'][ph]['keep']) for ph in negs) if n!='Step0' else sum(len(new[ph]['final']) for ph in negs) for n in S}
  atomic('dev-results.json',dict(table=tab,targets=targets,pointChangesVsV3=pointdiff,perPhoto=per,falseDistribution=distributions,perPhotoClasses=res,candidateBoxes=S,clear=dict(photos=len(negs),retainedCandidateCounts=clear,note='all 14 have zero baseline candidates; no negative-discrimination evidence here'),runtime=dict(applyAll42Sec=applysec,verifierComputeSec=applycompute,scoreSec=time.perf_counter()-score0,totalSec=time.perf_counter()-start,resource=lease.receipt(),cacheReuse=True,detectorInferenceCount=0),baselineParity=True,selection=dict(rule=read(OUT/'protocol.json')['selection'],passed=selection,productionAccepted=False),inputs=dict(modelSHA256=sha(OUT/'verifier-v4.json'),freezeSHA256=sha(OUT/'freeze.json'),devInputIndexSHA256=sha(OUT/'dev-inputs.json')),caution='108 frozen point targets in 28 exposed DEV photos, 22 reviewed-mask photos; eyewear UNKNOWN; AI engineering labels, no independent final/product/clinical acceptance'))
  status('single DEV complete; report pending',1868,1868,developmentSelectionPassed=selection);print('DEV_RESULT',tab,targets['v4'],'selection',selection)
if __name__=='__main__':{'prepare':prepare_dev,'run':run}[sys.argv[1]]()
