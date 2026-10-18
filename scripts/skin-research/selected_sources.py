"""Local selected-source ledger; immutable archives, typed supervision, frozen groups.

Photo grouping is a leakage precaution, NEVER a subject identity claim. Unreviewed
rights/geometry/negative coverage cannot be inferred from dataset-wide licenses.
"""
from pathlib import Path
import collections, csv, hashlib, json, re, zipfile
import sys
import cv2
import numpy as np
from prepare_focused_data import ROOT, sha

OUT = ROOT / 'audit-results/skin-selected-20261011'
sys.path.insert(0,str(OUT/'python-runtime'))  # Optional local COCO decoder; never product runtime.
AUDIT = ROOT.parent / 'audit-review/skin-alternatives-20261011'
DATA = Path('C:/Users/PC/Desktop/YENİ İŞ/Applications/7. TOGG/Datasets')
SOURCES = {
 'v11': ('Skin Analysis.v11-augmentation_version.coco-segmentation.zip','new-downloads-audit/skin-analysis-v11'),
 'smart': ('SmartSkinCare.v8i.coco.zip','folder-audit/smart'),
 'clean3': ('Skin-Problem-Detection-Relabel-Clean3.v1-skin-disease-detection-.coco.zip','folder-audit/clean3'),
 'dc': ('DC EB 2.v1i.coco.zip','folder-audit/dc-eb'),
 'wrinkles': ('Wrinkles Detector.v2i.coco-segmentation.zip','new-downloads-audit/wrinkles-detector'),
 'skin5': ('Skin.v5i.coco.zip','new-downloads-audit/skin-v5'),
 'face': ('skin_face_detection.v1i.coco.zip','folder-audit/skin-face'),
 'care': ('Skin care.v5i.coco.zip','folder-audit/taralina'),
 'merve': ('ciltanalizi.v12i.coco.zip','folder-audit/merve'),
 'arnold': ('yolo arnold.v1i.coco.zip','new-downloads-audit/arnold'),
 'csv': ('multi-class.v1i.multiclass.zip','new-downloads-audit/multiclass'),
}
TARGETS = ['acne','oil','redness','tone','lines','dark','bags']
MAP = {
 'v11': {'Acne':'acne','Oily':'oil','Redness':'redness','Dark-Spots':'tone','Eyebags':'bags'},
 'smart': {'Pimple':'acne'}, 'clean3': {'Acne':'acne','Oily-Skin':'oil','Dry-Skin':'dry'},
 'old-eye': {'Acne':'acne','Eyebags':'bags'},
 'dc': {'eyebag':'bags','darkcircle':'dark'},
 'wrinkles': {'wrinkle':'lines','acne':'acne','dark_circle':'dark'},
 'skin5': {'wrinkle':'lines','darkcircle':'dark'},
 'face': {'crows_feet':'lines'},
 'care': {'acne':'acne','redness':'redness','pigmentation':'tone','wrinkles':'lines'},
 'arnold': {'eyebag':'bags','dark_circle':'dark'},
}

def write(name, value):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8');q.replace(p)

def family(name):
 s=Path(name).stem.split('.rf.')[0].lower()
 return re.sub(r'(_jpg|_jpeg|_png|_webp)$','',s)

def dhash_image(im):
 from PIL import Image
 gray=np.asarray(Image.fromarray(im[:,:,::-1]).convert('L').resize((9,8),Image.Resampling.BICUBIC))
 bits=''.join(str(int(v)) for v in (gray[:,:-1]>gray[:,1:]).ravel())
 return f'{int(bits,2):016x}'

def geometry(ann, width, height):
 """Retain raw COCO box and mask separately. Never clip bad truth into validity."""
 raw=ann.get('segmentation',[]);b=ann.get('bbox',[])
 result=dict(label=ann['label'],bbox=b,segmentation=raw,kind='box',validBox=False,validMask=False)
 if len(b)==4:
  x,y,w,h=b
  result['validBox']=bool(np.isfinite(b).all() and x>=0 and y>=0 and w>0 and h>0 and x+w<=width+.01 and y+h<=height+.01)
 if isinstance(raw,dict):
  result['kind']='rle'
  try:
   from pycocotools import mask as M
   rle=M.frPyObjects(raw,height,width) if isinstance(raw.get('counts'),list) else raw
   mask=M.decode(rle);result['validMask']=mask.shape==(height,width) and bool(mask.any())
  except (ValueError,TypeError,KeyError,ImportError):result['maskReason']='INVALID_OR_UNSUPPORTED_RLE'
 elif raw:
  polys=[]
  try:
   for p in raw:
    a=np.asarray(p,float).reshape(-1,2)
    if len(a)<3 or not np.isfinite(a).all() or not ((a>=[0,0])&(a<=[width,height])).all() or abs(cv2.contourArea(a.astype(np.float32)))<1:raise ValueError()
    # Quarantine non-adjacent edge intersections rather than repairing truth.
    b=np.roll(a,-1,axis=0);n=len(a)
    cross=lambda u,v:u[...,0]*v[...,1]-u[...,1]*v[...,0]
    u=b-a
    for first in range(n):
     ids=np.arange(first+2,n)
     if first==0:ids=ids[ids!=n-1]
     if not len(ids):continue
     v=b[ids]-a[ids];delta=a[ids]-a[first];den=cross(u[first],v);nonparallel=np.abs(den)>1e-8
     t=np.divide(cross(delta,v),den,out=np.zeros(len(ids)),where=nonparallel);s=np.divide(cross(delta,u[first]),den,out=np.zeros(len(ids)),where=nonparallel)
     if (nonparallel&(t>0)&(t<1)&(s>0)&(s<1)).any():raise ValueError()
    polys.append(a)
   rectangle=all(len(np.unique(a,axis=0))==4 and len(np.unique(a[:,0]))==2 and len(np.unique(a[:,1]))==2 for a in polys)
   result.update(kind='rectangle-polygon' if rectangle else 'polygon',validMask=not rectangle)
  except (ValueError,TypeError):result.update(kind='invalid-polygon',maskReason='INVALID_OR_OUT_OF_FRAME')
 return result

def prepare():
 OUT.mkdir(parents=True,exist_ok=True);cv2.setNumThreads(1)
 assert not (OUT/'manifest.json').exists(),'Preserve frozen manifest; use a new run for changed preparation'
 exposure=set()
 for f in ['folder-audit/review-exposure.json','folder-audit/additional-review-exposure.json']:
  for r in json.loads((AUDIT/f).read_text('utf8')):
   exposure.add((r['dataset'],r['path']));
 # The prior summary selections are development even if the archive says test.
 rows=[];rights=[];thumbs=[]
 aliases={'v11':'skin-analysis-v11','dc':'dc-eb','wrinkles':'wrinkles-detector','skin5':'skin-v5','face':'skin-face','care':'taralina','csv':'multiclass'}
 for key,(archive_name,audit_name) in SOURCES.items():
  archive=DATA/archive_name;digest=sha(archive);base=OUT/'sources'/key;base.mkdir(parents=True,exist_ok=True)
  cached=OUT/'prepare-cache'/f'{key}.json';thumbfile=cached.with_suffix('.npy')
  if cached.exists() and thumbfile.exists():
   saved=json.loads(cached.read_text('utf8'));assert saved['archiveSHA256']==digest
   rows.extend(saved['rows']);rights.append(saved['rights']);thumbs.extend(np.load(thumbfile,allow_pickle=False));print('cached',key,len(rows),flush=True);continue
  source_start=len(rows)
  summary=json.loads((AUDIT/(audit_name+'-summary.json')).read_text('utf8'))
  fingerprint_file=AUDIT/(audit_name+'-fingerprints.json')
  fingerprints={r['path']:r for r in json.loads(fingerprint_file.read_text('utf8'))['rows']}
  annotations=json.loads((AUDIT/(audit_name+'-annotations.json')).read_text('utf8')) if key!='csv' else {}
  selected={r if isinstance(r,str) else r['path'] for r in summary.get('sampleSelection',[]) if isinstance(r,str) or 'path' in r}
  if key=='csv':
   selected|={r[1]['zipPath'] for r in json.loads((AUDIT/'new-downloads-audit/multiclass-reviewed-selection.json').read_text('utf8'))}
  with zipfile.ZipFile(archive) as z:
   for info in z.infolist():
    destination=(base/info.filename).resolve()
    assert destination.is_relative_to(base.resolve()) and not ((info.external_attr>>16)&0o170000)==0o120000,'UNSAFE_ARCHIVE_ENTRY'
    if not destination.exists():z.extract(info,base)
  csv_labels={}
  for f in base.rglob('*.csv'):
   with f.open(encoding='utf-8-sig',newline='') as stream:
    for v in csv.DictReader(stream):
     name=v.get('filename')
     if name:csv_labels[(f.parent/name).relative_to(base).as_posix()]={k:int(x) for k,x in v.items() if k!='filename' and x in ('0','1')}
  rights.append(dict(id=key,archiveSHA256=digest,archive=archive_name,readmes=summary.get('readmes',{}),license='publisher-declared CC-BY-4.0',individualImageRights='unverified until review; stock markers excluded',transform='original export retained; ROI tensors tracked separately',auditInputSHA256=sha(AUDIT/(audit_name+'-summary.json'))))
  for f in sorted(base.rglob('*')):
   if f.suffix.lower() not in ['.jpg','.jpeg','.png','.webp']:continue
   name=f.relative_to(base).as_posix();im=cv2.imread(str(f));assert im is not None,name
   h,w=im.shape[:2];anns=[geometry(a,w,h) for a in annotations.get(name,[])]
   r=dict(source=key,path=name,absolutePath=str(f),sha256=sha(f),decodedSHA256=hashlib.sha256(im.tobytes()).hexdigest(),width=w,height=h,family=family(name),annotations=anns,csvLabels=csv_labels.get(name),knownNegativeAreas=[],quality='unreviewed',naturalRGB=None,rights='publisher-declared; individual-photo-review-pending',reviewExposed=name in selected or (aliases.get(key,key),name) in exposure,personIdentity=None)
   prior=fingerprints.get(name);assert prior and prior['sha256']==r['sha256'] and prior['width']==w and prior['height']==h,'AUDIT_IMAGE_DRIFT'
   r['dhash']=prior['dhash']
   if re.search(r'istock|getty|shutterstock|dermnet',name,re.I):r.update(rights='excluded-stock-rights-unverified',excluded='STOCK_RIGHTS')
   if re.search(r'clahe',name,re.I):r.update(naturalRGB=False,colorCalibrationExcluded='PROCESSED_SOURCE')
   r['targets']={a['label']:MAP.get(key,{}).get(a['label']) for a in anns}
   rows.append(r);thumbs.append(cv2.resize(im,(32,32),interpolation=cv2.INTER_AREA))
  write(str(cached.relative_to(OUT)),dict(archiveSHA256=digest,rows=rows[source_start:],rights=rights[-1]));np.save(thumbfile,np.stack(thumbs[source_start:]),allow_pickle=False)
  print('prepared',key,len(rows),flush=True)
 # Old sources remain local, with already reviewed crops/geometry and exposure.
 old=json.loads((ROOT/'audit-results/focused-skin-20261010/learning-manifest.json').read_text('utf8'))
 for r in old['rows']:
  im=cv2.imread(r['absolutePath'])
  if im is None:continue
  q=dict(source='old-'+r['corpus'],path=r['path'],absolutePath=r['absolutePath'],sha256=r['sha256'],decodedSHA256=hashlib.sha256(im.tobytes()).hexdigest(),width=r['width'],height=r['height'],family=r.get('sourceName',family(r['path'])),dhash=dhash_image(im),annotations=[],knownNegativeAreas=[],reviewExposed=True,oldGroup=r['group'],rights=r['license'],quality='previous-review',oldMetadata=r,personIdentity=None)
  rows.append(q);thumbs.append(cv2.resize(im,(32,32),interpolation=cv2.INTER_AREA))
 # Conservatively join families WITHIN a source and exact bytes/pixels across all sources.
 parent=list(range(len(rows)))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def join(i,j):parent[find(j)]=find(i)
 keys={};edges=collections.Counter()
 for i,r in enumerate(rows):
  for k in [('bytes',r['sha256']),('decoded',r['decodedSHA256']),('export-family',r['source'],r['family']),('old-group',r.get('oldGroup'))]:
   if k==('old-group',None):continue
   if k in keys:join(i,keys[k]);edges[k[0]]+=1
   else:keys[k]=i
 # Verify re-encoded/resized image candidates numerically at 32x32 RGB. Broad
 # perceptual/name candidates are quarantined from a final; not person matches.
 from scipy.spatial import cKDTree
 T=np.stack(thumbs).astype(np.float32)/255
 # PCA-free low-dimensional lookup; detailed pixel comparison verifies pairs.
 descriptors=np.stack([cv2.resize(t,(8,8),interpolation=cv2.INTER_AREA).ravel() for t in T])
 tree=cKDTree(descriptors);near=[]
 for i,v in enumerate(descriptors):
  for j in tree.query_ball_point(v,.32):
   if j<=i:continue
   err=float(np.abs(T[i]-T[j]).mean())
   if err<=.015:join(i,j);edges['reencoded-resized-pixel-match']+=1
   elif err<=.035:
    rows[i]['reviewExposed']=rows[j]['reviewExposed']=True;near.append([i,j,err])
 # dHash proximity is a review candidate only. Quarantine both endpoints from
 # a final holdout, without calling them the same person/photo. This includes
 # cross-export/crop uncertainties that full-pixel matching does not resolve.
 buckets=collections.defaultdict(list);dh_pairs=0
 for i,r in enumerate(rows):
  if 'dhash' not in r:continue
  v=int(r['dhash'],16);candidate=set()
  for band in range(8):candidate.update(buckets[(band,(v>>(8*band))&255)])
  for j in candidate:
   if (v^int(rows[j]['dhash'],16)).bit_count()<=6 and find(i)!=find(j):
    rows[i]['reviewExposed']=rows[j]['reviewExposed']=True;dh_pairs+=1
  for band in range(8):buckets[(band,(v>>(8*band))&255)].append(i)
 groups=collections.defaultdict(list)
 for i in range(len(rows)):groups[find(i)].append(i)
 for indices in groups.values():
  g=min(rows[i]['sha256'] for i in indices);exposed=any(rows[i]['reviewExposed'] for i in indices)
  stock=any(rows[i].get('excluded')=='STOCK_RIGHTS' for i in indices)
  u=int(hashlib.sha256(('selected-20261011:'+g).encode()).hexdigest()[:8],16)/2**32
  split=('train' if u<.82 else 'validation') if exposed else ('train' if u<.70 else 'validation' if u<.85 else 'test')
  for i in indices:
   rows[i].update(group=g,split=split,groupExposed=exposed)
   if stock:rows[i].update(excluded='STOCK_RIGHTS',rights='excluded-known-stock-source-group')
 write('manifest.json',dict(version='selected-skin-v1',seed=20261011,rows=rows,sources=rights,personIndependent=False,holdoutScope='provisional unused photo groups; crop/collage residual review pending; never person independent',groupEdges=dict(edges),perceptualQuarantinePairs=near,unknownAreaPolicy='loss masked; CSV zero not pixel negative; box not mask',excludedArchives=['skin_concern_detection_model.v1i.coco.zip','Skin_Analysis.v1i.coco.zip','Find wrinkles- marks and dark circles.v2-roboflow-instant-1--eval-.coco.zip']))
 write('receipt.json',dict(manifestSHA256=sha(OUT/'manifest.json'),images=len(rows),groups=len(groups),counts=dict(collections.Counter(r['source']+':'+r['split'] for r in rows)),sourceHashes={r['archive']:r['archiveSHA256'] for r in rights},groupEdges=dict(edges),dhashCandidatePairsQuarantined=dh_pairs,sourceArchivesChanged=False,trainingCompleted=False))

def refine():
 """Pre-training fingerprint quarantine for an already extracted ledger."""
 assert not (OUT/'review/candidates.json').exists(),'Cannot change groups after review/training'
 path=OUT/'manifest.json';m=json.loads(path.read_text('utf8'));rows=m['rows'];prior_sha=sha(path)
 by_source={k:{r['path']:r for r in json.loads((AUDIT/(v[1]+'-fingerprints.json')).read_text('utf8'))['rows']} for k,v in SOURCES.items()}
 probe=next(r for r in rows if r['source']=='v11');assert dhash_image(cv2.imread(probe['absolutePath']))==by_source['v11'][probe['path']]['dhash'],'AUDIT_DHASH_CONVENTION_NOT_REPRODUCED'
 for r in rows:
  if r['source'] in by_source:
   f=by_source[r['source']][r['path']];assert f['sha256']==r['sha256'];r['dhash']=f['dhash']
   r['annotations']=[geometry(a,r['width'],r['height']) for a in r['annotations']]
  else:
   r['dhash']=dhash_image(cv2.imread(r['absolutePath']))
 stock_groups={r['group'] for r in rows if r.get('excluded')=='STOCK_RIGHTS'}
 for r in rows:
  if r['group'] in stock_groups:r.update(excluded='STOCK_RIGHTS',rights='excluded-known-stock-source-group')
 buckets=collections.defaultdict(list);quarantine=set();pairs=0
 for i,r in enumerate(rows):
  v=int(r['dhash'],16);candidates=set()
  for band in range(8):candidates.update(buckets[(band,(v>>(8*band))&255)])
  for j in candidates:
   if (v^int(rows[j]['dhash'],16)).bit_count()<=6 and r['group']!=rows[j]['group']:
    quarantine.update([r['group'],rows[j]['group']]);pairs+=1
  for band in range(8):buckets[(band,(v>>(8*band))&255)].append(i)
 for r in rows:
  if r['group'] in quarantine:
   r.update(perceptualCandidateOnly=True,groupExposed=True)
   u=int(hashlib.sha256(('selected-20261011:'+r['group']).encode()).hexdigest()[:8],16)/2**32;r['split']='train' if u<.82 else 'validation'
 m.update(fingerprintRefinement=dict(previousManifestSHA256=prior_sha,dhashCandidatePairsQuarantined=pairs,identityClaim=False),trainingFreeze=True)
 write('manifest.json',m);receipt=json.loads((OUT/'receipt.json').read_text('utf8'));receipt.update(manifestSHA256=sha(path),counts=dict(collections.Counter(r['source']+':'+r['split'] for r in rows)),dhashCandidatePairsQuarantined=pairs,trainingFreeze=True)
 # Rehash every immutable ZIP after extraction, before any selected-source training.
 for src in m['sources']:assert sha(DATA/src['archive'])==src['archiveSHA256'],'SOURCE_ARCHIVE_CHANGED'
 write('receipt.json',receipt)
 print('Frozen',len(rows),'rows; quarantined candidate pairs',pairs,flush=True)

if __name__=='__main__':
 import sys
 refine() if '--refine' in sys.argv else prepare()
