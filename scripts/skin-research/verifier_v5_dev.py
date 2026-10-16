"""Apply only frozen V5 once; reuse all stored V4 comparator baseline results."""
import tarfile
from verifier_v5_common import *
from verifier_v4_dev import key
sys.path.insert(0,str(ROOT/'scripts/skin-research/external_acne'))
import common_scope_compare as CS
import relabel_compare as RC
CL=['false','duplicate','onUncertain','onOther','nearOutOfScopeTarget','unreviewedInOval','nonSkin','unreviewedPhoto']

def run():
 assert not (OUT/'dev-start.json').exists() and not (OUT/'dev-results.json').exists(),'V5_SINGLE_DEV_ALREADY_STARTED'
 check_v4();freeze=read(OUT/'freeze.json')
 for n,d in freeze['files'].items():assert sha(OUT/n)==d,'FROZEN_V5_CHANGED'
 for p,d in freeze['code'].items():assert sha(p)==d,'FROZEN_V5_CODE_CHANGED'
 # Old masks/labels/landmarks and cached metadata are reused, never re-created.
 old=read(V4/'dev-results.json');inputs=read(V4/'dev-inputs.json');expected=read(V4/'input-hashes.json')
 needed=[SRC/'docs/acne-point-relabel-layer1-20261016.json',SRC/'audit-results/acne-relabel/layer1-masks.tgz']+[SRC/'audit-results/acne-v6/eval'/s/'replay.jsonl' for s in ['dev','devext']]
 for p in needed:assert sha(p)==inputs['files'][str(p)]
 from heavy_job_lease import HeavyJobLease
 from threadpoolctl import threadpool_limits
 import cv2
 with HeavyJobLease('CDC-verifier-v5-one-frozen-DEV',peak_mib=900,minimum_available_mib=1600,memory_metric='private') as lease,threadpool_limits(limits=2):
  cv2.setNumThreads(2);start=time.perf_counter();model=read(OUT/'verifier-v5.json');atomic('dev-start.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),count=1,freezeSHA256=sha(OUT/'freeze.json'),modelSHA256=sha(OUT/'verifier-v5.json'),previousResultsSHA256=sha(V4/'dev-results.json')));status('single frozen V5 DEV application',cvFits=9,finalFits=1,devApplications=1)
  apply0=time.perf_counter();computed=0.;decisions={}
  for p in sorted((CACHE/'dev').glob('*.json')):
   lease.check();fp=p.with_suffix('.npz');assert sha(p)==expected[str(p)] and sha(fp)==expected[str(fp)]
   rec=read(p)
   with np.load(fp) as a:F=a['features'];assert F.shape==(len(rec['final']),1920)
   t=time.perf_counter();pv=probabilities(model,F) if len(F) else np.zeros(0);keep=pv>=model['threshold'];dt=time.perf_counter()-t;computed+=dt
   decisions[rec['photo']]=dict(kind=rec['kind'],final=rec['final'],proba=pv.tolist(),keep=keep.tolist(),verifierSec=dt)
  assert len(decisions)==42
  atomic('dev-decisions-v5.json',dict(modelSHA256=sha(OUT/'verifier-v5.json'),threshold=model['threshold'],photos=decisions));applysec=time.perf_counter()-apply0
  labels=read(SRC/'docs/acne-point-relabel-layer1-20261016.json')['photos'];photos=sorted(labels);landmarks={}
  for s in ['dev','devext']:
   with (SRC/'audit-results/acne-v6/eval'/s/'replay.jsonl').open(encoding='utf8') as f:
    for line in f:
     r=json.loads(line);ph=r['sha256'][:12]
     if ph in labels:landmarks[ph]=dict(landmarks=r['landmarks'])
  boxes={};classes={};reviewed=[];maskPixels=0;score0=time.perf_counter()
  with tarfile.open(SRC/'audit-results/acne-relabel/layer1-masks.tgz') as archive:
   for ph in photos:
    lease.check();d=decisions[ph];assert [key(b) for b in d['final']]==[key(b) for b in old['candidateBoxes']['Step0'][ph]],'STEP0_CANDIDATE_PARITY'
    boxes[ph]=[b[:4] for b,k in zip(d['final'],d['keep']) if k];lab=labels[ph];raw=archive.extractfile('masks/'+ph+'.png').read();assert hashlib.sha256(raw).hexdigest()==lab['mask']['sha256']
    mask=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_GRAYSCALE)>0;h,w=mask.shape;assert (w,h)==(inputs['photos'][ph]['width'],inputs['photos'][ph]['height']);oval=RC.oval_mask(landmarks[ph],w,h);maskPixels+=int(mask.sum())
    if mask.any():reviewed.append(ph)
    classes[ph]=CS.classify(lab,boxes[ph],mask,oval,.03*lab['faceWidthPx'])
  table=dict(old['table']);table['v5']=dict(found=sum(len(v['hitIds']) for v in classes.values()),of=sum(len(v['inScope']) for v in classes.values()),points=sum(len(v['classes']) for v in classes.values()),**{c:sum(v['classes'].count(c) for v in classes.values()) for c in CL});assert table['v5']['of']==108
  baseids={(ph,x) for ph in photos for x in old['perPhotoClasses']['v3'][ph]['hitIds']};ids={(ph,x) for ph in photos for x in classes[ph]['hitIds']};fmt=lambda s:sorted(f'{p}#{x}' for p,x in s)
  changes={};per={}
  for ph in photos:
   before=dict(zip(map(key,old['candidateBoxes']['v3'][ph]),old['perPhotoClasses']['v3'][ph]['classes']));after=dict(zip(map(key,boxes[ph]),classes[ph]['classes']));bf={k for k,c in before.items() if c=='false'};af={k for k,c in after.items() if c=='false'}
   changes[ph]=dict(removedFalse=[dict(box=list(k),v5Class=after.get(k,'rejected')) for k in sorted(bf-af)],addedFalse=[dict(box=list(k),v3Class=before.get(k,'rejected')) for k in sorted(af-bf)],removedCandidates=[dict(box=list(k),classV3=before[k]) for k in sorted(before.keys()-after.keys())],addedCandidates=[dict(box=list(k),classV5=after[k]) for k in sorted(after.keys()-before.keys())])
   per[ph]=dict(old['perPhoto'][ph]);per[ph]['v5']=dict(found=len(classes[ph]['hitIds']),hitIds=classes[ph]['hitIds'],points=len(boxes[ph]),**{c:classes[ph]['classes'].count(c) for c in CL})
  t=table['v5'];passed=t['found']>=68 and t['false']<=60 and (t['found']>68 or t['false']<60);dist=dict(all28=[per[ph]['v5']['false'] for ph in photos],reviewedOnly=[per[ph]['v5']['false'] for ph in reviewed],reviewedPhotos=len(reviewed),meanReviewed=t['false']/len(reviewed),medianReviewed=float(np.median([per[p]['v5']['false'] for p in reviewed])),maximum=max(per[p]['v5']['false'] for p in photos),falsePerReviewedMP=t['false']/(maskPixels/1e6))
  clear=[p for p,d in decisions.items() if d['kind']=='negative-photo'];clearpoints=sum(sum(decisions[p]['keep']) for p in clear)
  atomic('dev-results.json',dict(table=table,targetsVsV3=dict(gained=fmt(ids-baseids),lost=fmt(baseids-ids)),pointChangesVsV3=changes,perPhoto=per,v5PerPhotoClasses=classes,v5CandidateBoxes=boxes,falseDistributionV5=dist,clear=dict(photos=len(clear),retainedPoints=clearpoints,baselinePoints=old['clear']['retainedCandidateCounts']['Step0'],note='zero baseline candidates; no new negative discrimination evidence'),selection=dict(rule=read(OUT/'protocol.json')['developmentSelection'],passed=passed,productionAccepted=False),baselineResultsReused=True,baselineResultsSHA256=sha(V4/'dev-results.json'),inputs=dict(freezeSHA256=sha(OUT/'freeze.json'),modelSHA256=sha(OUT/'verifier-v5.json')),runtime=dict(applyAll42Sec=applysec,verifierComputeSec=computed,scoreSec=time.perf_counter()-score0,totalSec=time.perf_counter()-start,resource=lease.receipt(),newDetectorInference=0),scope='unchanged 108 point targets, 28 exposed DEV photos, 22 reviewed-mask photos, eyewear UNKNOWN; no product/clinical acceptance'))
  status('single V5 DEV complete; final report pending',cvFits=9,finalFits=1,devApplications=1,found=t['found'],falsePoints=t['false'],developmentSelected=passed);print('V5_DEV',table['v5'],fmt(ids-baseids),fmt(baseids-ids),'SELECTED',passed)
if __name__=='__main__':run()
