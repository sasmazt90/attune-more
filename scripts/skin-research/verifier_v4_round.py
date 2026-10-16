"""Single V4 verifier round. Source worktrees are read-only; progress is atomic."""
import argparse,collections,hashlib,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];TOGG=ROOT.parent
SRC=TOGG/'attune-claude-acne-audit';OUT=TOGG/'cdc-progress/acne-verifier-v4-20261017'
SEED=20261017
V1=SRC/'audit-results/acne-verifier';V3=SRC/'audit-results/acne-verifier-v3'
CATEGORIES={'A':'visible acne-like focal lesion at marker','F':'flat skin at marker, no clear focal lesion','M':'mole/pigment/mark/scar appearance','P':'pore/texture/specular shine at marker','O':'other visible structure, hair/fold/edge/eye/lip','U':'uncertain appearance or offset/insufficient visible evidence'}
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def H(*v):return hashlib.sha256('|'.join(map(str,v)).encode()).hexdigest()
def atomic(name,value):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp-'+str(os.getpid()))
 with tmp.open('w',encoding='utf8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
def status(phase,done=0,total=None,**extra):atomic('status.json',dict(timeUTC=datetime.now(timezone.utc).isoformat(),displayTimezone='Europe/Berlin',phase=phase,done=done,total=total,workspace=str(ROOT),productionActive=False,**extra))
def verify_inputs():
 for p,d in read(OUT/'input-hashes.json').items():
  if sha(p)!=d:raise RuntimeError('FROZEN_INPUT_CHANGED: '+p)
def prepare():
 if (OUT/'review-list.json').exists():raise RuntimeError('PREPARATION_ALREADY_FROZEN')
 OUT.mkdir(parents=True,exist_ok=True);status('preparing frozen TRAIN list')
 l1=read(V1/'labels.json');l3=read(V3/'labels-v3.json');rows=l3['rows'];todo=[r for r in rows if r['source']=='unreviewed-excluded']
 assert len(todo)==1868 and sum(r['label'] is not None for r in rows)==423
 assert sum(r['label']==1 for r in rows)==284 and sum(r['label']==0 for r in rows)==139
 reviewed={(r['photo'],r['idx']) for r in rows if r['source']!='unreviewed-excluded'}
 man=read(SRC/'audit-results/acne-v6-data/manifest-v6.json');photos={p['sha256'][:12]:p for p in man['photos']}
 # Read only TRAIN replay rows to obtain actual landmarks/face width; discard image strings.
 trainsha={p['sha256'] for p in man['photos']};attrs={}
 for name in ['audit-results/acne-v6/trainext/replay.jsonl','audit-results/acne-data-v2-20261015/replay.jsonl']:
  with (SRC/name).open(encoding='utf8') as f:
   for line in f:
    r=json.loads(line)
    if r['sha256'] not in trainsha or r['sha256'][:12] in attrs or not r.get('snapshot') or not r.get('landmarks'):continue
    p=photos[r['sha256'][:12]];lm=r['landmarks'];fw=(((lm[234]['x']-lm[454]['x'])*p['width'])**2+((lm[234]['y']-lm[454]['y'])*p['height'])**2)**.5
    attrs[r['sha256'][:12]]=dict(fwPx=fw,pose=r['matchedAngle'])
 # Existing V3 roles are immutable, including groups that have only new candidates.
 groups=l1['groups'];old_roles={}
 for r in rows:
  if r['label'] is not None:
   g=groups[r['photo']]
   if g in old_roles and old_roles[g]!=r['split']:raise RuntimeError('OLD_GROUP_ROLE_CONFLICT')
   old_roles[g]=r['split']
 roles={g:old_roles.get(g,'calibration' if int(H(SEED,'new-group-role',g),16)/2**256<.30 else 'learn') for g in sorted(set(groups.values()))}
 # Check known manifest source groups too; do not quietly split their members.
 source_group_roles=collections.defaultdict(set)
 for ph,g in groups.items():source_group_roles[photos[ph]['researchGroup']].add(roles[g])
 assert all(len(v)==1 for v in source_group_roles.values()),'KNOWN_SOURCE_GROUP_CROSSES_SPLIT'
 for ph,g in groups.items():
  path=V1/'train'/(ph+'.json');rec=read(path);assert rec['sha256']==photos[ph]['sha256']
  assert rec['sha256'][:12]==ph and ph in attrs
 # Prior test and supplement IDs are allowed only as exclusion metadata, never labels/features.
 banned=set()
 def walk(obj):
  if isinstance(obj,dict):
   for k,v in obj.items():
    if k in ['sha256','photoSHA256','sha','sourceSHA256'] and isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v.lower()):banned.add(v[:12])
    elif isinstance(v,(dict,list)):walk(v)
  elif isinstance(obj,list):
   for v in obj:walk(v)
 for path in [SRC/'docs/acne-unused-test-freeze-20261016.json',TOGG/'claude-progress/acne-unused-test-freeze-20261016.json',TOGG/'claude-progress/acne-v1-v3-positive-supplement-20261016/index.json']:
  if path.exists():walk(read(path))
 dev_ids={p.stem for p in (V1/'dev').glob('*.json')};assert not set(groups)&dev_ids and not set(groups)&banned,'EVALUATION_PHOTO_IN_TRAIN'
 todo.sort(key=lambda r:H(SEED,'v4-blind-review',r['photo'],r['idx']));items=[]
 for i,r in enumerate(todo):
  ph=r['photo'];p=photos[ph];assert (ph,r['idx']) not in reviewed
  file=SRC/'audit-results/acne-v6-data'/p['file'];assert sha(file)==p['sha256']
  items.append(dict(rid=f'V4R{i+1:04}',photo=ph,photoSHA256=p['sha256'],idx=r['idx'],box=r['box'],group=groups[ph],sourceGroup=p['researchGroup'],role=roles[groups[ph]],file=str(file),width=p['width'],height=p['height'],**attrs[ph]))
 # Immutable source inventory: models, cached features/candidates and original decisions.
 paths=[V1/'labels.json',V1/'verifier.json',V3/'verifier-v3.json',V3/'labels-v3.json',V3/'review-decisions-v3.json',SRC/'audit-results/acne-verifier-v2/review-decisions.json',SRC/'audit-results/acne-v6-data/manifest-v6.json',SRC/'scripts/skin-research/acne_candidate_verifier.py',SRC/'scripts/skin-research/verifier_v3_train.py',SRC/'scripts/skin-research/external_acne/common_scope_compare.py',SRC/'scripts/skin-research/external_acne/relabel_compare.py',TOGG/'attune-live-test/audit-results/acne-takeover-20261015/models/step0.safetensors']
 paths+=list((V1/'train').glob('*.json'))+list((V1/'train').glob('*.npz'))+list((V1/'dev').glob('*.json'))+list((V1/'dev').glob('*.npz'))
 paths+=list({Path(r['file']) for r in items});hashes={str(p):sha(p) for p in paths}
 assert sha(V1/'verifier.json')=='b6fa6c05b48a092623f7780200c07440ebaf934989ab66518ee21b23fa304f8a'
 assert sha(V3/'verifier-v3.json')=='94d18abb951c49847371f03513957681fd50392e0ebfb51c233a1db65492ab67'
 assert hashes[str(paths[11])]=='18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'
 atomic('input-hashes.json',hashes)
 atomic('group-roles.json',dict(seed=SEED,rule='preserve every used V3 group role; new groups hash(seed|new-group-role|group)<.30',roles=roles,existingRoles=old_roles,personIndependence=False,groupsOriginalHash=sha(V1/'labels.json'),exclusionMetadataIds=sorted(banned|dev_ids)))
 atomic('review-list.json',dict(n=len(items),photos=len({r['photo'] for r in items}),items=items,sourceReviewed=423,sourceUncertain=244,sourceConflicts=6,reviewLevel='AI engineering visual review, not expert',categories=CATEGORIES,blindFields='ID + source detail + wider context + entire photo; no labels/probabilities/acceptance',priorDecisionsUnchanged=True))
 atomic('protocol.json',dict(version='acne-verifier-v4-one-round-20261017',sourceHEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SRC,text=True).strip(),workspaceHEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),existingLabelled=423,newReview=1868,features=1920,fit=dict(C=.1,penalty='l2',class_weight='balanced',solver='lbfgs',max_iter=2000,tol=.0001,standardizer='learn only'),threshold='sort calibration positive probabilities; threshold at floor(.05*n), >=95% retained; no DEV selection',calibrationGate='same V3: AUC>=.65 and negatives removed>=.15; gate reported separately',selection='DEV found>=68 and false<=60 and at least one strict improvement vs V3; research development only',conflicts='same source centres <=.03*faceWidth, A versus F/M/P/O: both excluded in V4; prior decisions not rewritten',singleFit=True,singleDEV=True,noDetectorInference=True,noProductionOrPush=True,inputIndexSHA256=sha(OUT/'input-hashes.json')))
 atomic('source-start.json',dict(checkouts={str(p):dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=p,text=True).strip(),status=subprocess.check_output(['git','status','--short'],cwd=p,text=True)) for p in [SRC,TOGG/'attune-live-test',TOGG/'attune-antigravity-skin']},oldModels={'v1':sha(V1/'verifier.json'),'v3':sha(V3/'verifier-v3.json')}))
 status('review-list and roles frozen; rendering pending',0,len(items));print(json.dumps(dict(candidates=len(items),photos=len({r['photo'] for r in items}),roles=collections.Counter(roles.values()))))

def render():
 from heavy_job_lease import HeavyJobLease
 with HeavyJobLease('CDC-v4-blind-review-sheets',peak_mib=900,minimum_available_mib=1600,memory_metric='private') as lease:
  import cv2,numpy as np
  cv2.setNumThreads(2);items=read(OUT/'review-list.json')['items'];folder=OUT/'blind-sheets';folder.mkdir(exist_ok=True);S=128;PER=32
  def crop(im,c,half):
   x,y=int(round(c[0]-half)),int(round(c[1]-half));n=max(2,int(round(2*half)));can=np.zeros((n,n,3),np.uint8);a,b,ex,ey=max(0,x),max(0,y),min(im.shape[1],x+n),min(im.shape[0],y+n)
   if ex>a and ey>b:can[b-y:ey-y,a-x:ex-x]=im[b:ey,a:ex]
   can=cv2.resize(can,(S,S),interpolation=cv2.INTER_CUBIC if n<S else cv2.INTER_AREA)
   for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:cv2.line(can,(64+dx*14,64+dy*14),(64+dx*24,64+dy*24),(0,255,255),1)
   return can
  for start in range(0,len(items),PER):
   sheet=np.full((154*8,384*4,3),245,np.uint8)
   for k,it in enumerate(items[start:start+PER]):
    lease.check();im=cv2.imread(it['file']);assert im is not None;box=it['box'];c=((box[0]+box[2])/2,(box[1]+box[3])/2);fw=it['fwPx'];tight=crop(im,c,max(10,.05*fw));near=crop(im,c,.15*fw);full=np.zeros((S,S,3),np.uint8)
    ratio=min(S/im.shape[1],S/im.shape[0]);small=cv2.resize(im,None,fx=ratio,fy=ratio,interpolation=cv2.INTER_AREA);oy=(S-small.shape[0])//2;ox=(S-small.shape[1])//2;full[oy:oy+small.shape[0],ox:ox+small.shape[1]]=small;cv2.circle(full,(int(c[0]*ratio+ox),int(c[1]*ratio+oy)),2,(0,255,255),1)
    y=(k//4)*154;x=(k%4)*384;cv2.putText(sheet,it['rid'],(x+4,y+19),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,0,0),1);sheet[y+26:y+154,x:x+384]=np.hstack([tight,near,full])
   path=folder/f'page-{start//PER+1:03}.jpg';assert not path.exists(),'BLIND_PAGE_ALREADY_EXISTS';cv2.imwrite(str(path),sheet,[cv2.IMWRITE_JPEG_QUALITY,94]);status('blind sheets rendering',min(start+PER,len(items)),len(items))
  atomic('blind-sheet-index.json',dict(perPage=PER,pages=[dict(page=p.name,sha256=sha(p)) for p in sorted(folder.glob('*.jpg'))],resource=lease.receipt()));status('blind visual review pending',0,len(items));print('PAGES',len(list(folder.glob('*.jpg'))))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','render']);args=parser.parse_args()
 {'prepare':prepare,'render':render}[args.phase]()