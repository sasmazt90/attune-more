"""Public SCIN only. Local audit/data stay outside Git. No identity embeddings.
Head/neck is self-report, not a face annotation. Haar outputs are candidates,
not expert face/lesion labels; this distinction is retained in the manifest.
"""
import argparse, ast, collections, concurrent.futures, csv, hashlib, io, json
from pathlib import Path
import urllib.request, threading
import cv2, numpy as np

ROOT=Path(__file__).resolve().parents[2]
BUCKET='https://storage.googleapis.com/dx-scin-public-data/'
GOOD={'DEFAULT_YES_IMAGE_QUALITY_SUFFICIENT','YES_IMAGE_QUALITY_SUFFICIENT_NO_DISCERNIBLE_PATHOLOGY'}
def digest(data):return hashlib.sha256(data).hexdigest()
def parsed(value,default):
 try:return ast.literal_eval(value)
 except (ValueError,SyntaxError):return default
def labels_for(row):
 names=parsed(row.get('dermatologist_skin_condition_on_label_name',''),[])
 scores=parsed(row.get('dermatologist_skin_condition_confidence',''),[])
 gradable=any(row.get('dermatologist_gradable_for_skin_condition_'+str(i)) in GOOD for i in [1,2,3])
 positive=any(n.lower()=='acne' and c>=3 for n,c in zip(names,scores))
 acne_like=any('acne' in n.lower() or 'follicul' in n.lower() or 'rosacea' in n.lower() for n in names)
 negative=bool(names) and not acne_like and any(c>=3 for c in scores)
 return gradable,1 if gradable and positive else 0 if gradable and negative else None

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='audit-results/skin-capabilities-20261008/scin');ap.add_argument('--download-images',action='store_true');ap.add_argument('--all-images',action='store_true');ap.add_argument('--analysis-workers',type=int,choices=[1,2,4],default=2);args=ap.parse_args()
 out=(ROOT/args.out).resolve();assert out.is_relative_to(ROOT/'audit-results');out.mkdir(parents=True,exist_ok=True)
 rows={};sources={}
 for name in ['scin_cases.csv','scin_labels.csv']:
  p=out/name
  if not p.exists():p.write_bytes(urllib.request.urlopen(BUCKET+'dataset/'+name,timeout=40).read())
  expected={'scin_cases.csv':'7923ee9ba9775af413ca115c4587dc1bd32259d7936aa97fa80d88dd616ca3c3','scin_labels.csv':'616ad03c24c304f5f7ef01b4116e4d3274f1c71c9b19a0e3d5620698b081a9fe'}
  assert digest(p.read_bytes())==expected[name], 'Dataset metadata changed: require a new source/license review'
  sources[name]=digest(p.read_bytes());rows[name]=list(csv.DictReader(p.open(encoding='utf8')))
 cases=rows['scin_cases.csv'];labels={r['case_id']:r for r in rows['scin_labels.csv']}
 head=[r for r in cases if r['body_parts_head_or_neck']=='YES']
 stats={'cases':len(cases),'images':sum(bool(r['image_'+str(i)+'_path']) for r in cases for i in [1,2,3]),'headNeckSelfReportedCases':len(head),'headNeckImageReferences':sum(bool(r['image_'+str(i)+'_path']) for r in head for i in [1,2,3]),'faceAnnotationAvailable':False,'faceDetectedIsExpertUsable':False,'metadataSHA256':sources}
 stats['expertGradableCases']=sum(labels_for(labels[r['case_id']])[0] for r in cases)
 stats['expertAcneNamedCases']=sum(any(n.lower()=='acne' for n in parsed(labels[r['case_id']]['dermatologist_skin_condition_on_label_name'],[])) for r in cases)
 stats['headExpertAcneEligibleCases']=sum(labels_for(labels[r['case_id']])[1]==1 for r in head)
 stats['headExpertNegativeProxyEligibleCases']=sum(labels_for(labels[r['case_id']])[1]==0 for r in head)
 pairs=collections.Counter(('user_acne' if r['related_category']=='ACNE' else 'user_other_or_missing','expert_acne' if any(n.lower()=='acne' for n in parsed(labels[r['case_id']]['dermatologist_skin_condition_on_label_name'],[])) else 'expert_other_or_missing') for r in cases)
 stats['selfReportExpertCrossTab']={'/'.join(k):v for k,v in pairs.items()}
 if not args.download_images:
  (out/'counts.json').write_text(json.dumps(stats,indent=2),'utf8');print(json.dumps(stats));return
 images=out/'images';images.mkdir(exist_ok=True)
 pool_cases=cases if args.all_images else head
 stats['imageInventoryScope']='all released cases' if args.all_images else 'self-reported head/neck only'
 jobs=[(r,i) for r in pool_cases for i in [1,2,3] if r['image_'+str(i)+'_path']]
 def download(job):
  r,i=job;path=r['image_'+str(i)+'_path'];assert path.startswith('dataset/images/') and '..' not in path
  key=digest(path.encode());p=images/(key+'.png')
  try:
   if not p.exists():
    with urllib.request.urlopen(BUCKET+urllib.parse.quote(path),timeout=40) as response:data=response.read(64*1024*1024+1)
    if len(data)>64*1024*1024:raise ValueError('Image size cap')
    p.write_bytes(data)
   return r,i,p,None
  except Exception as e:return r,i,p,type(e).__name__
 print('Downloading public image inventory:',len(jobs),flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:downloaded=list(pool.map(download,jobs))
 cv2.setNumThreads(1);local=threading.local()
 cached={}
 if (out/'manifest.json').exists():cached={m['source_path']:m for m in json.loads((out/'manifest.json').read_text('utf8'))}
 def analyze(job):
  r,i,p,error=job
  if error:return None,error
  previous=cached.get(r['image_'+str(i)+'_path'])
  if previous and digest(p.read_bytes())==previous['sha256']:return previous,None
  if not hasattr(local,'detector'):local.detector=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
  detector=local.detector
  im=cv2.imread(str(p));
  if im is None:return None,'decode'
  h,w=im.shape[:2];scale=min(1,640/max(h,w));small=cv2.resize(im,(round(w*scale),round(h*scale))) if scale<1 else im
  gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY);faces=detector.detectMultiScale(gray,scaleFactor=1.1,minNeighbors=5,minSize=(48,48))
  ph=cv2.dct(cv2.resize(gray,(32,32)).astype(np.float32))[:8,:8].ravel()[1:];bits=sum(int(v>np.median(ph))<<j for j,v in enumerate(ph));gradable,target=labels_for(labels[r['case_id']])
  box=None;blur=None;lum=None
  if len(faces)==1:
   x,y,fw,fh=faces[0];box=[int(x/scale),int(y/scale),int(fw/scale),int(fh/scale)];roi=gray[y:y+fh,x:x+fw];blur=float(cv2.Laplacian(roi,cv2.CV_32F).var());lum=float(roi.mean())
  eligible=box is not None and blur>=10 and 35<=lum<=220 and target is not None
  tone_label=labels[r['case_id']].get('monk_skin_tone_label_us','') or labels[r['case_id']].get('monk_skin_tone_label_india','') or 'missing'
  return {'case_id':r['case_id'],'image_path':str(p.relative_to(ROOT)),'source_path':r['image_'+str(i)+'_path'],'sha256':digest(p.read_bytes()),'phash':bits,'width':w,'height':h,'face_box':box,'faceReview':'unreviewed-Haar-candidate','blur':blur,'luminance':lum,'expertGradableCase':gradable,'target':target,'eligible':eligible,'tone':tone_label,'shotType':r['image_'+str(i)+'_shot_type'],'license':'SCIN Data Use License','sourceRevision':'b5a498233ef23b24c2f9fdb41b53e162c6eeb98d'},None
 manifest=[];failures=collections.Counter();tone=collections.Counter();quality=collections.Counter()
 with concurrent.futures.ThreadPoolExecutor(max_workers=args.analysis_workers) as pool:
  for n,(row,error) in enumerate(pool.map(analyze,downloaded)):
   if error:failures[error]+=1
   else:
    manifest.append(row);quality['singleFace' if row['face_box'] else 'zeroOrMultipleFaces']+=1
    if row['eligible']:tone[row['tone']]+=1
   if n%200==0:print('Analyzed',n,'/',len(jobs),flush=True)
 stats.update(downloadedImages=len(downloaded)-sum(failures.values()),imageFailures=dict(failures),faceDetectorCounts=dict(quality),singleFaceCandidates=sum(m['face_box'] is not None for m in manifest),gradableCaseSingleFaceCandidates=sum(m['face_box'] is not None and m['expertGradableCase'] for m in manifest),eligibleImageCandidates=sum(m['eligible'] for m in manifest),eligibleCases=len({m['case_id'] for m in manifest if m['eligible']}),eligibleAcneImageCandidates=sum(m['eligible'] and m['target']==1 for m in manifest),eligibleAcneCases=len({m['case_id'] for m in manifest if m['eligible'] and m['target']==1}),eligibleToneDistribution=dict(tone),expertVerifiedFaceImages=None,localLesionLabelsAvailable=False,negativeCertifiedAbsence=False)
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8');(out/'counts.json').write_text(json.dumps(stats,indent=2),'utf8');print(json.dumps(stats),flush=True)
if __name__=='__main__':main()
