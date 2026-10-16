"""Shared V5 fixed-objective utilities; immutable V4 inputs, isolated outputs."""
import collections,hashlib,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];TOGG=ROOT.parent
SRC=TOGG/'attune-claude-acne-audit';V4=TOGG/'cdc-progress/acne-verifier-v4-20261017';OUT=TOGG/'cdc-progress/acne-verifier-v5-20261017'
CACHE=SRC/'audit-results/acne-verifier';SEED=20261017;LAMBDA0=1/(.1*276)
TYPES=('pos','flat','mole-mark','pore-shine','other');SHARES=dict(zip(TYPES,[.5,.125,.125,.125,.125]))
sys.path.insert(0,str(ROOT/'.runtime/verifier-v4-deps'))

def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def atomic(name,value):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp-'+str(os.getpid()))
 with tmp.open('w',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2);f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
def status(phase,**kw):atomic('status.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),displayTimezone='Europe/Berlin',phase=phase,workspace=str(ROOT),productionActive=False,**kw))
def check_v4():
 snapshot=read(OUT/'input-snapshot.json')
 for p,d in snapshot['files'].items():assert sha(p)==d,'FROZEN_V4_ARTIFACT_CHANGED: '+p
 return snapshot

def balanced_weights(rows):
 counts=collections.Counter((r['type'],r['group']) for r in rows)
 groups={t:{r['group'] for r in rows if r['type']==t} for t in TYPES}
 assert all(groups[t] for t in TYPES),'MISSING_CATEGORY'
 raw=np.array([SHARES[r['type']]/len(groups[r['type']])/counts[r['type'],r['group']] for r in rows],float)
 w=raw/raw.mean();assert np.all(w>0) and np.isfinite(w).all()
 return w

def weight_summary(rows,w):
 total=float(w.sum());types={}
 for t in TYPES:
  by=collections.defaultdict(float)
  for r,wi in zip(rows,w):
   if r['type']==t:by[r['group']]+=float(wi)
  types[t]=dict(n=sum(r['type']==t for r in rows),groups=len(by),totalWeight=sum(by.values()),fraction=sum(by.values())/total,perGroup=dict(sorted(by.items())))
 return dict(n=len(rows),mean=float(w.mean()),sum=total,types=types)

def standardize_fit(X,w):
 mean=np.average(X,axis=0,weights=w);variance=np.average((X-mean)**2,axis=0,weights=w);scale=np.sqrt(variance);scale[scale<1e-8]=1.
 return mean,scale

def c_from_lambda(lam,w):
 assert lam>0 and float(np.sum(w))>0
 return 1/(float(lam)*float(np.sum(w)))

def threshold95(p,y):
 pos=np.sort(np.asarray(p)[np.asarray(y)==1]);assert len(pos)
 return float(pos[int(np.floor(.05*len(pos)))])

def probabilities(model,X):
 mean=np.asarray(model['standardizer']['mean']);scale=np.asarray(model['standardizer']['scale']);coef=np.asarray(model['model']['coef']);z=((np.asarray(X,float)-mean)/scale)@coef+model['model']['intercept']
 # Same stable logistic probability; no score/threshold adjustment.
 from scipy.special import expit
 return expit(z)

def objective(X,y,weights,coef,intercept,lam):
 z=np.asarray(X)@np.asarray(coef)+intercept
 return float(np.average(np.logaddexp(0,z)-np.asarray(y)*z,weights=weights)+.5*lam*np.dot(coef,coef))

def load_features(rows,role):
 assert role in ['learn','calibration'] and all(r['split']==role for r in rows)
 if role=='calibration':assert (OUT/'cv-results.json').exists() and (OUT/'selected-lambda.json').exists(),'CALIBRATION_BEFORE_CV_SELECTION'
 expected=read(V4/'input-hashes.json');by=collections.defaultdict(list);X=np.empty((len(rows),1920),float);access=[]
 for i,r in enumerate(rows):by[r['photo']].append((i,r))
 for ph,rs in by.items():
  p=CACHE/'train'/(ph+'.npz');jp=p.with_suffix('.json')
  assert sha(p)==expected[str(p)] and sha(jp)==expected[str(jp)],'FEATURE_INPUT_CHANGED'
  rec=read(jp)
  with np.load(p) as f:
   F=f['features'];assert F.shape==(len(rec['final']),1920)
   for i,r in rs:
    assert rec['sha256']==r['photoSHA256'];assert np.allclose(rec['final'][r['idx']][:4],r['box'],atol=.0051,rtol=0);X[i]=F[r['idx']]
  access.append(dict(photo=ph,role=role,path=str(p),sha256=expected[str(p)],rows=len(rs)))
 log=read(OUT/'feature-access.json') if (OUT/'feature-access.json').exists() else dict(phases=[])
 log['phases'].append(dict(timeUTC=datetime.now(timezone.utc).isoformat(),role=role,photos=access,rows=len(rows)));atomic('feature-access.json',log)
 assert np.isfinite(X).all();return X

def model_dict(clf,mean,scale,lam,w,threshold=None):
 return dict(featureVersion='acne-candidate-verifier-features-v1',version='v5',seed=SEED,standardizer=dict(mean=mean.tolist(),scale=scale.tolist(),fit='weighted learn only'),model=dict(family='logistic regression L2',C=c_from_lambda(lam,w),classWeight=None,coef=clf.coef_[0].tolist(),intercept=float(clf.intercept_[0]),lambdaValue=lam,sampleWeightSum=float(w.sum()),objective='weighted mean logistic loss + lambda/2 * ||coef||^2; intercept unpenalized'),threshold=threshold,protocol=str(OUT/'protocol.json'))
