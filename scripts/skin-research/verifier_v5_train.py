"""Bounded V5: nine learn-only CV fits, one final fit and TRAIN calibration."""
import argparse,warnings,math
from verifier_v5_common import *

def prepare():
 assert not (OUT/'protocol.json').exists(),'V5_ALREADY_PREPARED'
 assert subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True) is not None
 files={str(V4/n):sha(V4/n) for n in ['data-list.json','group-roles.json','review-decisions.json','conflicts.json','input-hashes.json','calibration.json','freeze.json','verifier-v4.json','hash-index.json','source-start.json']}
 protected={}
 for p in [SRC,TOGG/'attune-live-test',TOGG/'attune-antigravity-skin']:
  protected[str(p)]=dict(head=subprocess.check_output(['git','--no-optional-locks','rev-parse','HEAD'],cwd=p,text=True).strip(),status=subprocess.check_output(['git','--no-optional-locks','status','--short'],cwd=p,text=True))
 atomic('input-snapshot.json',dict(files=files,protectedCheckouts=protected,startingCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
 rows=read(V4/'data-list.json')['rows'];learn=[r for r in rows if r['split']=='learn'];assert len(learn)==1548
 from sklearn.model_selection import StratifiedGroupKFold
 y=np.array([r['label'] for r in learn]);g=np.array([r['group'] for r in learn]);splitter=StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=SEED)
 folds=[]
 for fold,(tr,va) in enumerate(splitter.split(np.zeros((len(learn),1)),y,g),1):
  assert set(g[tr]).isdisjoint(g[va]);assert all(r['label'] in [0,1] for r in learn)
  # Preflight category coverage; do not invent scores for an absent category.
  balanced_weights([learn[i] for i in tr]);balanced_weights([learn[i] for i in va])
  folds.append(dict(fold=fold,trainIndices=tr.tolist(),validationIndices=va.tolist(),trainGroups=sorted(set(g[tr])),validationGroups=sorted(set(g[va]))))
 assert sorted(i for f in folds for i in f['validationIndices'])==list(range(len(learn)))
 atomic('folds.json',dict(splitter='StratifiedGroupKFold',nSplits=3,shuffle=True,seed=SEED,learnIDs=[dict(photo=r['photo'],idx=r['idx'],group=r['group'],label=r['label'],type=r['type']) for r in learn],folds=folds))
 import sklearn,sklearn.linear_model._logistic as lg
 source=Path(lg.__file__);assert 'l2_reg_strength = 1.0 / (C * sw_sum)' in source.read_text('utf8')
 atomic('implementation-contract.json',dict(sklearn=sklearn.__version__,source=str(source),sha256=sha(source),formula='l2_reg_strength = 1.0 / (C * sw_sum)',sourceConfirms=True,v4SampleCountRatio=1548/276,caution='verified implementation scaling; not a proven causal explanation of the V4 regression'))
 atomic('protocol.json',dict(version='verifier-v5-fixed-mean-L2-group-type-balanced',seed=SEED,lambda0=LAMBDA0,multipliers=[1,3,10],lambdas=[LAMBDA0*m for m in [1,3,10]],objective='weighted mean logistic loss + lambda/2 * ||coef||^2; intercept unpenalized',C='1/(lambda*sum(sample_weight))',weights=dict(typeShares=SHARES,groups='equal mass per existing data-list.group within category; candidates split group/category mass equally',normalization='mean sample_weight=1 in each fit',class_weight=None),standardization='same weights from fold training subset only; final from full learn only; std<1e-8 =>1',cv=dict(splitter='StratifiedGroupKFold',shuffle=True,n_splits=3,random_state=SEED,foldSHA256=sha(OUT/'folds.json'),metric='unweighted validation positive order statistic retains >=95%; negative removal weighted equally across negative types then groups',selection='highest arithmetic mean over 3 folds; exact ties choose stronger lambda',threshold='floor(.05*n_validation_positives), same V3/V4 rule, fold thresholds discarded'),fit=dict(solver='lbfgs',penalty='l2',tol=.0001,max_iter=2000,class_weight=None,threads=2),limit=dict(cvFits=9,finalFits=1,devApplications=1),finalThreshold='same floor(.05*n_calibration_positives) order statistic on held-out TRAIN calibration only',developmentSelection='found>=68, false<=60, at least one strict improvement vs V3; not product admission',noNewReviewLabelsDetectorDownloadOrDependencies=True,noProductionOrPushMerge=True,inputSnapshotSHA256=sha(OUT/'input-snapshot.json')))
 status('prepared: fixed folds, weights, three lambdas; CV pending',cvFits=0,finalFits=0);print('PREPARED',len(learn),[len(f['trainIndices']) for f in folds])

def fit_one(X,y,w,mean,scale,lam):
 from sklearn.linear_model import LogisticRegression
 from sklearn.exceptions import ConvergenceWarning
 from threadpoolctl import threadpool_limits
 t=time.perf_counter()
 with warnings.catch_warnings(record=True) as warn,threadpool_limits(limits=2):
  warnings.simplefilter('always');clf=LogisticRegression(C=c_from_lambda(lam,w),class_weight=None,solver='lbfgs',penalty='l2',tol=.0001,max_iter=2000).fit((X-mean)/scale,y,sample_weight=w)
 info=dict(sec=time.perf_counter()-t,nIter=clf.n_iter_.tolist(),converged=not any(issubclass(a.category,ConvergenceWarning) for a in warn),warnings=[str(a.message) for a in warn],C=clf.C,lambdaValue=lam,weightSum=float(w.sum()),effectiveLambda=1/(clf.C*float(w.sum())))
 return clf,info

def cv():
 assert not (OUT/'cv-start.json').exists(),'CV_ALREADY_STARTED'
 check_v4();protocol=read(OUT/'protocol.json');folds=read(OUT/'folds.json')['folds'];rows=[r for r in read(V4/'data-list.json')['rows'] if r['split']=='learn']
 from heavy_job_lease import HeavyJobLease
 with HeavyJobLease('CDC-verifier-v5-nine-learn-CV-fits',peak_mib=900,minimum_available_mib=1600,memory_metric='private') as lease:
  X=load_features(rows,'learn');y=np.array([r['label'] for r in rows]);atomic('cv-start.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),protocolSHA256=sha(OUT/'protocol.json'),foldsSHA256=sha(OUT/'folds.json'),maxFits=9));start=time.perf_counter();results=[]
  for fi,fold in enumerate(folds):
   tr=np.array(fold['trainIndices']);va=np.array(fold['validationIndices']);train=[rows[i] for i in tr];valid=[rows[i] for i in va];w=balanced_weights(train);wv=balanced_weights(valid);mean,scale=standardize_fit(X[tr],w)
   atomic(f'cv/fold-{fi+1}-weights.json',dict(train=weight_summary(train,w),validationMetric=weight_summary(valid,wv),trainRows=fold['trainIndices'],trainWeights=w.tolist(),validationRows=fold['validationIndices'],validationWeights=wv.tolist()))
   atomic(f'cv/fold-{fi+1}-standardizer.json',dict(mean=mean.tolist(),scale=scale.tolist(),fitIndices=fold['trainIndices'],weightSummarySHA256=sha(OUT/f'cv/fold-{fi+1}-weights.json')))
   for mult,lam in zip(protocol['multipliers'],protocol['lambdas']):
    lease.check();runid=f'fold-{fi+1}-lambda-x{mult}';atomic('cv/'+runid+'-start.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),ordinal=len(results)+1,lambdaValue=lam,trainN=len(tr),validationN=len(va)))
    clf,info=fit_one(X[tr],y[tr],w,mean,scale,lam);model=model_dict(clf,mean,scale,lam,w);pv=probabilities(model,X[va]);thr=threshold95(pv,y[va]);neg=y[va]==0
    removal=float(np.average(pv[neg]<thr,weights=wv[neg]));per={}
    for t in TYPES[1:]:
     m=np.array([r['type']==t for r in valid]);per[t]=dict(n=int(m.sum()),groups=len({r['group'] for r in valid if r['type']==t}),unweightedRemoved=int(np.sum(pv[m]<thr)),groupBalancedRemoved=float(np.average(pv[m]<thr,weights=wv[m])))
    entry=dict(runId=runid,fold=fi+1,multiplier=mult,lambdaValue=lam,fit=info,thresholdForCVOnly=thr,positiveN=int(np.sum(y[va]==1)),positiveKept=int(np.sum(pv[y[va]==1]>=thr)),positiveKeptFraction=float(np.mean(pv[y[va]==1]>=thr)),negativeTypeGroupBalancedRemoval=removal,byNegativeType=per,trainGroupOverlapValidation=False,standardizerSHA256=sha(OUT/f'cv/fold-{fi+1}-standardizer.json'),fitWeightedObjective=objective((X[tr]-mean)/scale,y[tr],w,clf.coef_[0],float(clf.intercept_[0]),lam))
    assert entry['positiveKeptFraction']>=.95
    atomic('cv/'+runid+'-model.json',model);atomic('cv/'+runid+'-result.json',entry);results.append(entry);status('learn-only CV',cvFits=len(results),maxCVFits=9,finalFits=0)
  means={m:float(np.mean([r['negativeTypeGroupBalancedRemoval'] for r in results if r['multiplier']==m])) for m in protocol['multipliers']};chosen=max(protocol['multipliers'],key=lambda m:(means[m],m));assert len(results)==9
  atomic('cv-results.json',dict(results=results,meanNegativeRemovalByMultiplier=means,selectedMultiplier=chosen,selectedLambda=LAMBDA0*chosen,selectionUses='learn folds only; no held-out calibration or DEV features/probabilities',CVFits=9,runtime=dict(totalSec=time.perf_counter()-start,resource=lease.receipt())))
  atomic('selected-lambda.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),lambdaValue=LAMBDA0*chosen,multiplier=chosen,cvResultsSHA256=sha(OUT/'cv-results.json'),finalThresholdNotSelectedYet=True))
  status('CV selection frozen; final fit pending',cvFits=9,selectedMultiplier=chosen,selectedLambda=LAMBDA0*chosen,finalFits=0);print('CV_COMPLETE',means,'selected',chosen)

def final():
 assert not (OUT/'final-fit-start.json').exists() and not (OUT/'verifier-v5.json').exists(),'FINAL_FIT_ALREADY_STARTED'
 check_v4();selected=read(OUT/'selected-lambda.json');assert sha(OUT/'cv-results.json')==selected['cvResultsSHA256'];allrows=read(V4/'data-list.json')['rows'];rows=[r for r in allrows if r['split']=='learn'];cal=[r for r in allrows if r['split']=='calibration'];assert {r['group'] for r in rows}.isdisjoint(r['group'] for r in cal)
 from heavy_job_lease import HeavyJobLease
 from sklearn.metrics import roc_auc_score
 with HeavyJobLease('CDC-verifier-v5-one-final-fit-and-calibration',peak_mib=900,minimum_available_mib=1600,memory_metric='private') as lease:
  start=time.perf_counter();X=load_features(rows,'learn');y=np.array([r['label'] for r in rows]);w=balanced_weights(rows);mean,scale=standardize_fit(X,w);lam=selected['lambdaValue']
  atomic('weights-summary.json',dict(summary=weight_summary(rows,w),rows=[dict(photo=r['photo'],idx=r['idx'],group=r['group'],type=r['type'],sampleWeight=float(wi)) for r,wi in zip(rows,w)]))
  atomic('final-fit-start.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),finalFitCount=1,CVFitCount=9,selectedLambdaSHA256=sha(OUT/'selected-lambda.json'),C=c_from_lambda(lam,w),lambdaValue=lam,weightSum=float(w.sum())))
  status('single final fit running; no DEV',cvFits=9,finalFits=1);clf,info=fit_one(X,y,w,mean,scale,lam);lease.check();model=model_dict(clf,mean,scale,lam,w)
  # Only now load held-out calibration features; never used by fit or lambda selection.
  tc=time.perf_counter();Xc=load_features(cal,'calibration');yc=np.array([r['label'] for r in cal]);pc=probabilities(model,Xc);sk=clf.predict_proba((Xc-mean)/scale)[:,1];err=float(np.max(np.abs(pc-sk)));assert err<1e-10;thr=threshold95(pc,yc);model['threshold']=thr
  atomic('verifier-v5.json',model);assert np.allclose(probabilities(read(OUT/'verifier-v5.json'),Xc),sk,atol=1e-10,rtol=0)
  wc=balanced_weights(cal);neg=yc==0;by={}
  for t in TYPES[1:]:
   m=np.array([r['type']==t for r in cal]);by[t]=dict(n=int(m.sum()),groups=len({r['group'] for r in cal if r['type']==t}),removed=int(np.sum(pc[m]<thr)),removedFraction=float(np.mean(pc[m]<thr)),groupBalancedRemoved=float(np.average(pc[m]<thr,weights=wc[m])))
  assert float(np.mean(pc[yc==1]>=thr))>=.95
  pl=probabilities(model,X);record=dict(fit=info,learn=dict(n=len(rows),pos=int(y.sum()),neg=int(np.sum(y==0)),groups=len({r['group'] for r in rows}),auc=float(roc_auc_score(y,pl)),weightedObjective=objective((X-mean)/scale,y,w,clf.coef_[0],float(clf.intercept_[0]),lam)),calibration=dict(n=len(cal),pos=int(yc.sum()),neg=int(np.sum(neg)),groups=len({r['group'] for r in cal}),auc=float(roc_auc_score(yc,pc)),threshold=thr,positiveOrderStatisticIndex=int(math.floor(.05*sum(yc==1))),positiveKept=int(np.sum(pc[yc==1]>=thr)),positiveKeptFraction=float(np.mean(pc[yc==1]>=thr)),negativeRemoved=int(np.sum(pc[neg]<thr)),negativeRemovedFraction=float(np.mean(pc[neg]<thr)),negativeTypeGroupBalancedRemoval=float(np.average(pc[neg]<thr,weights=wc[neg])),byType=by),serializationMaxProbabilityError=err,runtime=dict(calibrationSec=time.perf_counter()-tc,totalSec=time.perf_counter()-start,resource=lease.receipt()),noCalibrationFit=True,noDEVRead=True)
  atomic('calibration.json',record);atomic('train-calibration-probabilities.json',dict(rows=[dict(photo=r['photo'],idx=r['idx'],split=r['split'],label=r['label'],type=r['type'],proba=float(p)) for r,p in zip(rows+cal,np.r_[pl,pc])]))
  names=['verifier-v5.json','protocol.json','input-snapshot.json','folds.json','implementation-contract.json','cv-results.json','selected-lambda.json','weights-summary.json','final-fit-start.json','calibration.json','feature-access.json']
  atomic('freeze.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),beforeDEV=True,files={n:sha(OUT/n) for n in names},code={str(p):sha(p) for p in (ROOT/'scripts/skin-research').glob('verifier_v5_*.py')},CVFits=9,finalFits=1,threshold=thr,modelSHA256=sha(OUT/'verifier-v5.json')))
  atomic('checkpoint-index.json',dict(model=dict(path=str(OUT/'verifier-v5.json'),sha256=sha(OUT/'verifier-v5.json'),bytes=(OUT/'verifier-v5.json').stat().st_size),state='frozen before single DEV application',freezeSHA256=sha(OUT/'freeze.json')))
  status('final V5 and TRAIN threshold frozen; one DEV pending',cvFits=9,finalFits=1,modelSHA256=sha(OUT/'verifier-v5.json'));print('FINAL_FROZEN',info,record['calibration'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','cv','final']);a=p.parse_args();{'prepare':prepare,'cv':cv,'final':final}[a.phase]()
