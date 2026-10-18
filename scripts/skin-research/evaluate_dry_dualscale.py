"""One preregistered staging rule on seen frozen optical records; never fit.

--prepare freezes protocol/input index. --evaluate consumes that exact protocol
once. Source photos and labels stay outside Git; normal runtime is untouched.
Only missing final accepted fields are materialized from their existing cached
feature rows, not by rerunning the old 42-case feature/proposal/encoder audit.
"""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT.parent/'attune-live-test/audit-results'
OUT=ROOT.parent/'cdc-progress/skin-dryness-dualscale-20261018'
PRIOR=ROOT.parent/'cdc-progress/skin-dryness-closeout-20261017/seven-target-trace.json'
sys.path.insert(0,str(ROOT/'services/core-api'))
import numpy as np,cv2,psutil
from dry_dualscale_support import merge_accepted_supports,project_sampled_cells,VERSION,COORDINATES,OPTICAL_CUTOFF
cv2.setNumThreads(1)
def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(p.read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,value):
 p=OUT/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(value,indent=2,ensure_ascii=False),'utf8');os.replace(t,p)
def fixed_inputs():
 return {'prior':PRIOR,'labels':DATA/'dry-sag-component-followup-20261013/object-labels.json','scale':DATA/'native-dry-scale-20261013/independent-v3-comparison.json','optical':DATA/'native-camera-scope-20261013/single-crop-comparison.json','head':ROOT/'services/core-api/models/dryness-calibrated-v3/head.json','features':Path(read(PRIOR)['featureFile']['path']),'helper':ROOT/'services/core-api/dry_dualscale_support.py','featureCode':ROOT/'services/core-api/material_component_features.py','evaluator':Path(__file__).resolve()}

def prepare():
 assert not (OUT/'protocol.json').exists(),'Protocol already frozen; do not replace'
 prior=read(PRIOR);controls=read(fixed_inputs()['labels'])['controls']
 assert len(controls)==len(prior['sources'])==16 and len(prior['caseFiles'])==42
 assert len({r['sourceSHA256'] for r in controls})==16
 assert sha(fixed_inputs()['head'])=='7f13c7cb4eb65a3fb44abf062563ee3aff605a6ef9ff3271c5e32e206fedb8e1'
 assert sha(fixed_inputs()['features'])==prior['featureFile']['sha256']
 files=[dict(role=k,path=str(p),sha256=sha(p)) for k,p in fixed_inputs().items()]
 # Existing ordered audit already fixed the first10 added TRAIN cases followed
 # by 16 native/half pairs. Reuse that ledger, not source rehash/row identity work.
 needed=prior['caseFiles'][10:];assert len(needed)==32
 index=dict(atUTC=now(),sourceCount=16,conditionedLedgerCount=42,neededAcceptedFields=32,files=files,selectedConditionedFiles=needed,priorOnlyFirst10='Only componentIds lengths are read to locate existing cached feature offsets; no fit/head inference on those10 rows/cases',sources=[{k:r[k] for k in ('control','sourceSHA256','sourceSize','split','kind','group','metricBasis')} for r in prior['sources']],sourcePhotoHashChecks=0,sourcePhotoDecodeCalls=0,featureRowIdentityRecomputed=False,full42CaseAuditRepeated=False,modelIdentityFromPrior=prior['modelAssets'])
 save('input-index.json',index)
 protocol=dict(atUTC=now(),task='DRY-01',candidate=VERSION,coordinates=COORDINATES,seenData=True,preregistrationLimit='Written before this one candidate evaluation; these sources/labels/earlier scale results have already been seen. Not an independent preregistration or final test.',scales=[1.,.5],aggregation='source-grid max/OR for all inputs; no label/photo/split-based selection',headSHA256='7f13c7cb4eb65a3fb44abf062563ee3aff605a6ef9ff3271c5e32e206fedb8e1',encoderSHA256='a93e5445326c8071cd4d013b6fde494d9054dd4842dacf97028ceaefc9eb1987',sourceEncoderSHA256='e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a',headThreshold=.5,opticalCutoff=.04,hit={'minimumOriginalSourcePixels':3,'minimumReviewedPolygonFraction':.1,'rounding':False},pixelRule='Original source center (x+.5,y+.5); sampled cell owns origin+[j/f,(j+1)/f). Missing odd edge cells stay zero; source clipping then original supplied visibility; max overlap once. No dilation/interpolation.',opticalDomain='Recorded original crop domain ONLY; no anatomical mesh/quality/visibility admission invented. Real runtime must supply original visible anatomical mask and unchanged original quality/denominator.',fixedHeadReconstruction='Missing current-head final masks reconstructed only for32 required preserved pairs from existing cached rows. Old different-head gated fields are not substituted. No encoder/proposal/photo/fit.',opticalSelection={'nativeLostTargets':0,'minimumGainedTargets':1,'newReviewedNegativeAcceptedSourcePixels':0},runtimeActivationRequires='Optical pass plus same-source real accepted payload/anatomical/quality/map/history/performance controls. Otherwise staging only.',maxLogicalEvaluations=1,fitCount=0,inferenceEncoderCount=0,maxSampledRSSMiB=250,minimumAvailableMiB=650,inputIndexSHA256=sha(OUT/'input-index.json'),helperSHA256=sha(fixed_inputs()['helper']))
 save('protocol.json',protocol)
 s=read(OUT/'status.json');s.update(updatedAtUTC=now(),phase='single-rule-protocol-frozen',done=1,lastEvidence='protocol.json',lockedSourceCount=16,lockedConditionedCaseCount=32,totalConditionedLedgerCount=42);save('status.json',s)
 print(json.dumps(dict(prepared=True,cases=32,fit=0,encoderCalls=0,protocolSHA256=sha(OUT/'protocol.json'))))

def evaluate():
 assert not (OUT/'evaluation-start.json').exists(),'One comparison budget already consumed'
 protocol=read(OUT/'protocol.json');index=read(OUT/'input-index.json')
 assert sha(OUT/'input-index.json')==protocol['inputIndexSHA256'] and sha(fixed_inputs()['helper'])==protocol['helperSHA256']
 for row in index['files']:assert sha(Path(row['path']))==row['sha256'],row['role']
 save('evaluation-start.json',dict(atUTC=now(),logicalEvaluation=1,protocolSHA256=sha(OUT/'protocol.json')))
 process=psutil.Process();start=time.monotonic();peak=0.
 def check():
  nonlocal peak
  peak=max(peak,process.memory_info().rss/2**20)
  if peak>250 or psutil.virtual_memory().available<650*2**20:raise RuntimeError('OFFLINE_RESOURCE_RESERVE')
 check();import material_component_features as M
 prior=read(PRIOR);controls=read(fixed_inputs()['labels'])['controls'];scales=read(fixed_inputs()['scale'])['rows'];optical=read(fixed_inputs()['optical'])['rows'];head=read(fixed_inputs()['head'])
 assert head['threshold']==.5 and head['lossVersion']=='source-group-balanced-calibrated-v3-c04-clean'
 with np.load(fixed_inputs()['features'],allow_pickle=False) as f:features=f['features'].copy()
 offset=0
 for row in prior['caseFiles'][:10]:
  with np.load(row['path'],allow_pickle=False) as f:offset+=len(f['componentIds'])
 results=[];objects=[];negative_masks={};known_masks={};source_fields={};reconstructed_components=0;head_seconds=0.;union_seconds=0.
 for ci,control in enumerate(controls):
  check();source=next(r for r in prior['sources'] if r['control']==ci);sw,sh=source['sourceSize'];fields={};origins={};pair_start=time.monotonic()
  for pair,factor in enumerate((1.,.5)):
   receipt=index['selectedConditionedFiles'][2*ci+pair];path=Path(receipt['path'])
   assert sha(path)==receipt['sha256'],'Required field input drift'
   with np.load(path,allow_pickle=False) as f:field=f['field'].copy();ids=f['ids'];cids=f['componentIds'];geometry=f['X'][:,-12:]
   meta=next(r for r in optical if r['control']==ci and r['factor']==factor)
   assert meta['origin']==scales[ci]['cropOrigin'];assert field.shape==(round(meta['cropShape'][1]*factor),round(meta['cropShape'][0]*factor))
   tick=time.monotonic();X=np.c_[features[offset:offset+len(cids)],geometry];p=M.predict(X,head);head_seconds+=time.monotonic()-tick;offset+=len(cids);reconstructed_components+=len(cids)
   allowed=np.zeros(int(ids.max())+1,bool);allowed[cids]=p>=.5;fields[factor]=field*allowed[ids];origins[factor]=tuple(int(v) for v in meta['origin'])
  x,y=origins[1.];cw,ch=next(r for r in optical if r['control']==ci and r['factor']==1.)['cropShape']
  visible=np.zeros((sh,sw),bool);visible[y:y+ch,x:x+cw]=True
  tick=time.monotonic();union=merge_accepted_supports(fields[1.],fields[.5],source_shape=(sh,sw),native_origin=origins[1.],half_origin=origins[.5],visible_source=visible);union_seconds+=time.monotonic()-tick
  half=project_sampled_cells(fields[.5],(sh,sw),origins[.5],.5,visible)
  native=union.native>OPTICAL_CUTOFF;candidate=union.combined>OPTICAL_CUTOFF
  known=np.zeros((sh,sw),bool);negative=np.zeros((sh,sw),bool)
  for oi,obj in enumerate(control['objects']):
   mask=np.zeros((sh,sw),np.uint8);polygon=np.asarray([[px+control['roi'][0],py+control['roi'][1]] for px,py in obj['polygon']],np.int32);cv2.fillPoly(mask,[polygon],1);mask=mask>0
   if obj['label'] in ('visible-material','reviewed-non-flake'):known|=mask
   if obj['label']=='reviewed-non-flake':negative|=mask
   if obj['label']!='visible-material':continue
   area=int(mask.sum());bn=int((native&mask).sum());cn=int((candidate&mask).sum());hn=int(((half>OPTICAL_CUTOFF)&mask).sum())
   hit=lambda n:bool(n>=3 and n/max(1,area)>=.1)
   oldrow=next(r for r in prior['allReviewedObjects'] if r['control']==ci and r['index']==oi and r['factor']==1.)
   objects.append(dict(id=f'C{ci:02d}/{oi}',control=ci,index=oi,sourceSHA256=control['sourceSHA256'],split=control['split'],kind=control['kind'],group=control['group'],reviewedOriginalPixels=area,nativePixels=bn,halfMappedPixels=hn,candidatePixels=cn,nativeHit=hit(bn),halfMappedHit=hit(hn),candidateHit=hit(cn),oldNativeFrozenHit=oldrow['finalOptical']['objectHit']))
  added=candidate&~native
  results.append(dict(control=ci,sourceSHA256=control['sourceSHA256'],split=control['split'],kind=control['kind'],group=control['group'],sourceSize=[sw,sh],cropOrigin=list(origins[1.]),cropSize=[cw,ch],opticalDomainOnly=True,sourceGrid=union.metadata,reviewedNegativePixels=int(negative.sum()),nativeNegativeAcceptedPixels=int((native&negative).sum()),candidateNegativeAcceptedPixels=int((candidate&negative).sum()),newNegativeAcceptedPixels=int((added&negative).sum()),nativeUnknownAcceptedPixels=int((native&~known).sum()),candidateUnknownAcceptedPixels=int((candidate&~known).sum()),addedUnknownAcceptedPixels=int((added&~known).sum()),seconds=time.monotonic()-pair_start))
  # Local source grids/GT stay outside Git. Reusable for inspecting exact gains.
  np.savez_compressed(OUT/f'C{ci:02d}-source-supports.npz',native=union.native,combined=union.combined,reviewedNegative=negative,reviewedKnown=known)
  del union,half,native,candidate,fields,known,negative,added;check()
 assert offset==len(features) and len(objects)==21
 native_ids=[o['id'] for o in objects if o['nativeHit']];candidate_ids=[o['id'] for o in objects if o['candidateHit']];gained=[v for v in candidate_ids if v not in native_ids];lost=[v for v in native_ids if v not in candidate_ids]
 newneg=sum(r['newNegativeAcceptedPixels'] for r in results)
 decision=not lost and bool(gained) and newneg==0
 summary=dict(nativeHits=len(native_ids),candidateHits=len(candidate_ids),targets=21,nativeFound=native_ids,candidateFound=candidate_ids,gained=gained,lost=lost,halfMappedHits=sum(o['halfMappedHit'] for o in objects),priorHalfFrozenHits=13,halfCoordinateScopeChanged=True,originalReviewedNegativePixels=sum(r['reviewedNegativePixels'] for r in results),nativeNegativeAcceptedPixels=sum(r['nativeNegativeAcceptedPixels'] for r in results),candidateNegativeAcceptedPixels=sum(r['candidateNegativeAcceptedPixels'] for r in results),newNegativeAcceptedPixels=newneg,nativeUnknownAcceptedPixels=sum(r['nativeUnknownAcceptedPixels'] for r in results),candidateUnknownAcceptedPixels=sum(r['candidateUnknownAcceptedPixels'] for r in results),addedUnknownAcceptedPixels=sum(r['addedUnknownAcceptedPixels'] for r in results),nativeFrozenTargetResultDifferences=[o['id'] for o in objects if o['nativeHit']!=o['oldNativeFrozenHit']],opticalDevelopmentCandidatePass=decision,notClinicalProductAcceptance=True)
 groups=[]
 for split in ('train','validation'):
  for kind in ('pul','raw','old'):
   rows=[o for o in objects if o['split']==split and o['kind']==kind]
   if rows:groups.append(dict(split=split,kind=kind,targets=len(rows),nativeHits=sum(r['nativeHit'] for r in rows),candidateHits=sum(r['candidateHit'] for r in rows)))
 check();result=dict(atUTC=now(),candidate=VERSION,protocolSHA256=sha(OUT/'protocol.json'),inputIndexSHA256=sha(OUT/'input-index.json'),summary=summary,groups=groups,targets=objects,sources=results,fitCount=0,encoderCalls=0,proposalCalls=0,sourcePhotoDecodes=0,sourcePhotosRehashed=0,headReconstructionComponents=reconstructed_components,headReconstructionCases=32,full42CaseFeatureAuditRepeated=False,normalRuntimeActive=False,sourceMasksAreOpticalNotAnatomical=True,unknownOutsideReviewedMasks=True,resource=dict(seconds=time.monotonic()-start,headSeconds=head_seconds,unionSeconds=union_seconds,peakSampledRSSMiB=peak,pid=process.pid,started=process.create_time(),exe=process.exe(),cwd=process.cwd(),argvSHA256=hashlib.sha256(json.dumps(process.cmdline()).encode()).hexdigest(),budgetMiB=250,reserveMiB=650,heavyModelGuardMiB=2500,heavyModelGuardEntered=False),nextAction='If optical pass, lock <=3 real same-source accepted product payloads before any targeted runtime check; else stop this candidate without another rule/fit.')
 save('results.json',result)
 s=read(OUT/'status.json');s.update(updatedAtUTC=now(),phase='one-optical-comparison-complete',done=2,lastEvidence='results.json',inferenceCount=0,fitCount=0,opticalCandidatePass=decision,blocker=None if decision else 'Single candidate failed predeclared optical selection; stop without second rule');save('status.json',s)
 print(json.dumps(dict(summary=summary,groups=groups,resource=result['resource'])))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--evaluate',action='store_true');args=parser.parse_args()
 if args.prepare==args.evaluate:parser.error('Choose exactly one finite phase')
 if args.prepare:prepare()
 else:evaluate()
