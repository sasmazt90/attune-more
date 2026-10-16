"""One reviewed-data-only V4 fit. No DEV predictions or detector execution."""
import collections,math,sys,time,warnings
from pathlib import Path
import numpy as np
from verifier_v4_round import *
sys.path.insert(0,str(ROOT/".runtime/verifier-v4-deps"))
TYPE=dict(A='pos',F='flat',M='mole-mark',P='pore-shine',O='other')

def threshold95(p,y):
 pos=np.sort(np.asarray(p)[np.asarray(y)==1]);assert len(pos)>0
 return float(pos[int(np.floor(.05*len(pos)))])

def assert_new_run():
 for name in ['fit-start.json','verifier-v4.json','freeze.json']:
  assert not (OUT/name).exists(),'SINGLE_FIT_ALREADY_STARTED: '+name

def freeze_data():
 assert not (OUT/'data-list.json').exists(),'DATA_ALREADY_FROZEN'
 verify_inputs()
 reviews=read(OUT/'review-decisions.json');items=read(OUT/'review-list.json')['items'];assert len(reviews['decisions'])==len(items)==1868
 roles=read(OUT/'group-roles.json');groups=read(V1/'labels.json')['groups'];old=read(V3/'labels-v3.json')['rows'];man={p['sha256'][:12]:p for p in read(SRC/'audit-results/acne-v6-data/manifest-v6.json')['photos']}
 # Recover source metadata for every prior decision without reviewing it again.
 meta={}
 for folder,listname in [('acne-verifier-v2','review-list.json'),('acne-verifier-v3','review-list.json')]:
  for r in read(SRC/'audit-results'/folder/listname)['items']:meta[r['photo']]=dict(fwPx=r['fwPx'],pose=r['pose'])
 for it in items:meta[it['photo']]=dict(fwPx=it['fwPx'],pose=it['pose'])
 # Recheck dHash <=10 groups using exactly the original hash contract, without loading a pool.
 import cv2
 hashes={}
 for ph in groups:
  im=cv2.imread(str(SRC/'audit-results/acne-v6-data'/man[ph]['file']));assert im is not None
  g=cv2.resize(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),(9,8),interpolation=cv2.INTER_AREA)
  hashes[ph]=(g[:,1:]>g[:,:-1]).flatten();del im,g
 pairs=[]
 for i,a in enumerate(sorted(groups)):
  for b in sorted(groups)[i+1:]:
   dist=int(np.count_nonzero(hashes[a]!=hashes[b]))
   if dist<=10:
    assert groups[a]==groups[b] and roles['roles'][groups[a]]==roles['roles'][groups[b]],'NEAR_DUPLICATE_SPLIT'
    pairs.append(dict(a=a,b=b,distance=dist,group=groups[a]))
 person=collections.defaultdict(list)
 for ph in groups:
  pid=man[ph].get('personIdentity')
  if pid and pid not in ['unknown','filename-derived group only']:person[str(pid)].append(ph)
 for pid,phs in person.items():assert len({roles['roles'][groups[p]] for p in phs})==1,'KNOWN_PERSON_SPLIT'
 # Prior excluded candidates remain excluded, preserving all 250 uncertainty/conflict decisions.
 new={(it['photo'],it['idx']):(it,reviews['decisions'][it['rid']]) for it in items};lab=[]
 for r in old:
  k=(r['photo'],r['idx']);rr=dict(r);rr['priorLabel']=r['label'];rr['priorSource']=r['source'];rr.pop('row',None)
  if k in new:
   it,d=new[k];assert r['source']=='unreviewed-excluded'
   rr.update(rid=it['rid'],category=d['cat'],reason=d['reason'],label=None if d['cat']=='U' else int(d['cat']=='A'),type=TYPE.get(d['cat']),source='uncertain-v4-excluded' if d['cat']=='U' else 'review-v4:'+d['cat'])
  else:rr['category']='A' if r['label']==1 else next((c for c,t in TYPE.items() if t==r['type']),None)
  rr.update(group=groups[r['photo']],role=roles['roles'][groups[r['photo']]],photoSHA256=man[r['photo']]['sha256'],fwPx=meta.get(r['photo'],{}).get('fwPx'),pose=meta.get(r['photo'],{}).get('pose'))
  lab.append(rr)
 by=collections.defaultdict(list)
 for i,r in enumerate(lab):
  if r['label'] is not None:by[r['photo']].append(i)
 conflicts=[];excluded=set()
 for ph,ids in by.items():
  for j,a in enumerate(ids):
   for b in ids[j+1:]:
    ra,rb=lab[a],lab[b]
    if ra['label']==rb['label']:continue
    ca=np.array([(ra['box'][0]+ra['box'][2])/2,(ra['box'][1]+ra['box'][3])/2]);cb=np.array([(rb['box'][0]+rb['box'][2])/2,(rb['box'][1]+rb['box'][3])/2]);dist=float(np.linalg.norm(ca-cb))
    if dist<=.03*ra['fwPx']:
     excluded.update([a,b]);conflicts.append(dict(photo=ph,a=dict(idx=ra['idx'],rid=ra['rid'],cat=ra['category'],priorLabel=ra['priorLabel']),b=dict(idx=rb['idx'],rid=rb['rid'],cat=rb['category'],priorLabel=rb['priorLabel']),distancePx=dist,rPx=.03*ra['fwPx']))
 for i,r in enumerate(lab):
  if i in excluded:r.update(label=None,source='new-conflict-v4-excluded')
  r['split']=r['role'] if r['label'] is not None else None
 used=[r for r in lab if r['label'] is not None];assert all(not(r['photo'] in roles['exclusionMetadataIds']) for r in used)
 assert sum(r['priorLabel'] is not None for r in lab)==423
 assert all(r['label'] is None for r in lab if r['priorSource'] in ['uncertain-excluded','conflict-excluded'])
 cov={s:{t:dict(n=sum(r['split']==s and r['type']==t for r in used),photos=len({r['photo'] for r in used if r['split']==s and r['type']==t}),groups=len({r['group'] for r in used if r['split']==s and r['type']==t})) for t in TYPE.values()} for s in ['learn','calibration']}
 atomic('conflicts.json',dict(pairs=conflicts,excludedCandidates=len(excluded),priorReviewedExcludedByNewConflict=sum(lab[i]['priorLabel'] is not None for i in excluded),policy=read(OUT/'protocol.json')['conflicts']))
 atomic('group-isolation.json',dict(nearDuplicateMethod='original 64-bit dHash Hamming <=10, all 158 TRAIN photos rechecked',pairs=pairs,roleCrossings=0,knownPersonGroups=person,personIndependence=False,unknownIdentity='No new identity claim; preserve source/research/dHash group roles',excludedEvaluationIDs=roles['exclusionMetadataIds'],oldGroupRolesUnchanged=all(roles['roles'][g]==s for g,s in roles['existingRoles'].items())))
 atomic('data-list.json',dict(rows=lab,coverage=cov,reviewedNew=collections.Counter(d['cat'] for d in reviews['decisions'].values()),labelled=len(used),positives=sum(r['label'] for r in used),negatives=sum(r['label']==0 for r in used),photos=len({r['photo'] for r in used}),excluded=collections.Counter(r['source'] for r in lab if r['label'] is None),priorDecisionFilesPreserved=True,reviewDecisionSHA256=sha(OUT/'review-decisions.json'),groupRolesSHA256=sha(OUT/'group-roles.json')))
 status('data and conflict exclusions frozen',1868,1868,labelled=len(used));print('FROZEN',len(used),cov)

def fit():
 from heavy_job_lease import HeavyJobLease
 assert_new_run();verify_inputs();data=read(OUT/'data-list.json');used=[r for r in data['rows'] if r['label'] is not None]
 with HeavyJobLease('CDC-verifier-v4-single-L2-fit',peak_mib=900,minimum_available_mib=1600,memory_metric='private') as lease:
  from sklearn.linear_model import LogisticRegression
  from sklearn.metrics import roc_auc_score
  from sklearn.exceptions import ConvergenceWarning
  from threadpoolctl import threadpool_limits
  from acne_candidate_verifier import VERSION,Verifier
  from verifier_v2_train import wilson
  X=np.empty((len(used),1920),np.float64);by=collections.defaultdict(list)
  for i,r in enumerate(used):by[r['photo']].append((i,r))
  t0=time.perf_counter()
  for ph,rs in by.items():
   lease.check();rec=read(V1/'train'/(ph+'.json'))
   with np.load(V1/'train'/(ph+'.npz')) as archive:
    F=archive['features'];assert F.shape==(len(rec['final']),1920)
    for i,r in rs:
     assert np.allclose(rec['final'][r['idx']][:4],r['box'],atol=.0051,rtol=0),'CANDIDATE_INDEX_MISMATCH'
     X[i]=F[r['idx']]
  y=np.array([r['label'] for r in used]);types=np.array([r['type'] for r in used]);il=np.array([i for i,r in enumerate(used) if r['split']=='learn']);ic=np.array([i for i,r in enumerate(used) if r['split']=='calibration'])
  assert set(used[i]['group'] for i in il).isdisjoint(used[i]['group'] for i in ic)
  mean=X[il].mean(0);scale=X[il].std(0);scale[scale<1e-8]=1.;Z=(X-mean)/scale
  atomic('fit-start.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),dataSHA256=sha(OUT/'data-list.json'),reviewSHA256=sha(OUT/'review-decisions.json'),rolesSHA256=sha(OUT/'group-roles.json'),protocolSHA256=sha(OUT/'protocol.json'),fitCount=1,solver='lbfgs',tol=.0001,max_iter=2000))
  status('single L2 fit running',1868,1868);tf=time.perf_counter()
  with warnings.catch_warnings(record=True) as warns,threadpool_limits(limits=2):
   warnings.simplefilter('always');clf=LogisticRegression(C=.1,penalty='l2',class_weight='balanced',solver='lbfgs',max_iter=2000,tol=.0001).fit(Z[il],y[il]);fitsec=time.perf_counter()-tf
   lease.check();pl=clf.predict_proba(Z[il])[:,1];pc=clf.predict_proba(Z[ic])[:,1]
  tc=time.perf_counter();yc=y[ic];thr=threshold95(pc,yc);per={}
  for t in ['flat','mole-mark','pore-shine','other']:
   m=types[ic]==t;n=int(m.sum());k=int(np.count_nonzero(pc[m]<thr));per[t]=dict(n=n,photos=len({used[i]['photo'] for i in ic[m]}),removed=k,removedFrac=k/n if n else None,removedCI95=wilson(k,n),aucVsPositives=float(roc_auc_score(np.r_[np.ones(sum(yc==1)),np.zeros(n)],np.r_[pc[yc==1],pc[m]])) if n else None)
  auc=float(roc_auc_score(yc,pc));removed=float(np.mean(pc[yc==0]<thr));keep=float(np.mean(pc[yc==1]>=thr));assert keep>=.95
  model=dict(featureVersion=VERSION,version='v4',seed=SEED,standardizer=dict(mean=mean.tolist(),scale=scale.tolist()),model=dict(family='logistic regression L2',C=.1,classWeight='balanced',coef=clf.coef_[0].tolist(),intercept=float(clf.intercept_[0])),threshold=thr,protocol=str(OUT/'protocol.json'))
  atomic('verifier-v4.json',model);v=Verifier(OUT/'verifier-v4.json');parity=float(np.max(np.abs(v.proba(X[ic])-pc)));assert parity<1e-10
  calibrationSec=time.perf_counter()-tc
  atomic('calibration.json',dict(coverage=data['coverage'],labelled=len(y),learn=dict(n=len(il),pos=int(y[il].sum()),neg=int(sum(y[il]==0)),auc=float(roc_auc_score(y[il],pl))),calibration=dict(n=len(ic),pos=int(yc.sum()),neg=int(sum(yc==0)),auc=auc,threshold=thr,positiveOrderStatisticIndex=int(math.floor(.05*sum(yc==1))),keptPositives=keep,removedNegatives=removed,byType=per),gate=dict(rule='same V3 calibration AUC>=.65 and negative removal>=.15; reported separately',passed=auc>=.65 and removed>=.15),convergence=dict(nIter=clf.n_iter_.tolist(),limit=2000,warnings=[str(w.message) for w in warns],converged=not any(issubclass(w.category,ConvergenceWarning) for w in warns)),serializationMaxProbabilityError=parity,timing=dict(cacheLoadSec=tf-t0,fitSec=fitsec,calibrationSec=calibrationSec,totalSec=time.perf_counter()-t0),resource=lease.receipt(),environment=dict(numpy=np.__version__,sklearn=__import__('sklearn').__version__),caution='TRAIN fit/calibration metrics are not DEV or product accuracy'))
  atomic('train-calibration-probabilities.json',dict(rows=[dict(photo=r['photo'],idx=r['idx'],split=r['split'],label=r['label'],type=r['type'],proba=float(v.proba(X[i:i+1])[0])) for i,r in enumerate(used)]))
  frozenfiles=['verifier-v4.json','data-list.json','group-roles.json','review-decisions.json','conflicts.json','group-isolation.json','protocol.json','input-hashes.json','fit-start.json','calibration.json']
  atomic('freeze.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),beforeDEV=True,files={n:sha(OUT/n) for n in frozenfiles},singleFit=True,threshold=thr,devHasNotBeenEvaluated=True))
  atomic('checkpoint-index.json',dict(model=dict(path=str(OUT/'verifier-v4.json'),bytes=(OUT/'verifier-v4.json').stat().st_size,sha256=sha(OUT/'verifier-v4.json')),state='frozen before DEV',scope='full fitted scaler and classifier coefficients; detector unchanged',freezeSHA256=sha(OUT/'freeze.json')))
  status('model and TRAIN threshold frozen; single DEV pending',1868,1868,modelSHA256=sha(OUT/'verifier-v4.json'));print('FIT_COMPLETE',thr,auc,removed,fitsec)
if __name__=='__main__':{'freeze-data':freeze_data,'fit':fit}[sys.argv[1]]()
