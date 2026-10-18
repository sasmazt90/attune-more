"""Validate real consented expert annotation manifests. Empty data stays empty.
No built-in example face, synthetic label, imputed target or clinical score.
"""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def duplicate_components(rows,root=ROOT):
 import cv2,numpy as np
 parent=list(range(len(rows)));hashes=[]
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for row in rows:
  gray=cv2.imread(str(root/row['imagePath']),cv2.IMREAD_GRAYSCALE)
  coeff=cv2.dct(cv2.resize(gray,(32,32)).astype(np.float32))[:8,:8].ravel()[1:]
  hashes.append(sum(int(v>np.median(coeff))<<j for j,v in enumerate(coeff)))
 for i,a in enumerate(rows):
  for j,b in enumerate(rows[:i]):
   if a['caseId']==b['caseId'] or a['photoSHA256']==b['photoSHA256'] or (hashes[i]^hashes[j]).bit_count()<=4:parent[find(i)]=find(j)
 return [find(i) for i in range(len(rows))]

def partitions_are_disjoint(rows,root=ROOT):
 groups=duplicate_components(rows,root)
 return all(len({r.get('split') for i,r in enumerate(rows) if groups[i]==group})==1 for group in set(groups))

def validate(rows,target,protocol,root=ROOT):
 spec=protocol['targets'][target];result=[];reasons=[]
 for i,row in enumerate(rows):
  try:
   assert row['target']==target and row['region'] in spec['regions']
   assert row['pose'] in protocol['capture']['poses'] and row['visibility']=='gradable'
   assert row.get('groundTruthSource')=='independent-human-experts' and not row.get('synthetic',False)
   grades=row['expertGrades'];assert len(grades)>=2 and all(type(g) is int and 0<=g<=3 for g in grades)
   assert len(set(row['expertReviewerIds']))>=2 and len(row['expertReviewerIds'])==len(grades)
   grade=row['consensusGrade'];assert type(grade) is int and 0<=grade<=3
   if len(set(grades))>1:assert row.get('adjudicatedByThirdExpert') is True
   else:assert grade==grades[0]
   rights=row['rightsRecord'];assert all(k in rights for k in protocol['rights']['required'])
   assert rights['commercialTrainingAllowed'] is True and rights['modelDistributionAllowed'] is True and rights['consentScope']=='skin-model-training-and-derived-model-distribution'
   assert all(isinstance(rights[k],str) and rights[k].strip() for k in ['sourceLicenseName','sourceLicenseURL','consentId','withdrawalPolicy'])
   assert rights['sourceLicenseURL'].startswith('https://') and re.fullmatch('[0-9a-f]{64}',rights['licenseTextSHA256'])
   license_path=(root/rights['licenseTextPath']).resolve();assert license_path.is_relative_to(root/'audit-results') and license_path.is_file()
   assert hashlib.sha256(license_path.read_bytes()).hexdigest()==rights['licenseTextSHA256']
   assert row['consentRecord']['id']==rights['consentId'] and row['consentRecord']['scope']==rights['consentScope'] and row['consentRecord']['withdrawn'] is False
   assert row['caseId'] and row['annotationRevision'] and row['cameraCondition'] and row['lightingCondition']
   path=(root/row['imagePath']).resolve();assert path.is_relative_to(root/'audit-results') and path.is_file()
   assert hashlib.sha256(path.read_bytes()).hexdigest()==row['photoSHA256']
   assert type(row['sourceWidth']) is int and type(row['sourceHeight']) is int and row['sourceWidth']>0 and row['sourceHeight']>0
   import cv2
   image=cv2.imread(str(path));assert image is not None and image.shape[:2]==(row['sourceHeight'],row['sourceWidth'])
   x,y,w,h=row['regionBox'];assert x>=0 and y>=0 and w>0 and h>0 and x+w<=row['sourceWidth'] and y+h<=row['sourceHeight']
   assert isinstance(row['invalidPolygons'],list) and isinstance(row['targetPolygons'],list)
   for polygon in row['invalidPolygons']+row['targetPolygons']:
    assert len(polygon)>=3 and all(len(p)==2 and all(isinstance(v,(int,float)) for v in p) and 0<=p[0]<row['sourceWidth'] and 0<=p[1]<row['sourceHeight'] for p in polygon)
   result.append(row)
  except (AssertionError,KeyError,TypeError,ValueError,OSError):reasons.append({'row':i,'status':'rejected-incomplete-rights-or-expert-target'})
 return result,reasons

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--target',choices=['dry','sag'],required=True);ap.add_argument('--manifest');ap.add_argument('--out',default='audit-results/skin-capabilities-20261008/annotations');args=ap.parse_args()
 out=(ROOT/args.out).resolve();assert out.is_relative_to(ROOT/'audit-results');out.mkdir(parents=True,exist_ok=True)
 protocol=json.loads((ROOT/'docs/skin-research/annotation-protocol.json').read_text('utf8'));rows=json.loads(Path(args.manifest).read_text('utf8')) if args.manifest else []
 accepted,rejected=validate(rows,args.target,protocol);report={'target':args.target,'realAcceptedAnnotations':len(accepted),'rejected':rejected,'readyForTraining':False,'productAccepted':False,'unit':protocol['targets'][args.target]['unit'],'nextStep':'Acquire rights-cleared standardized captures, two independent expert grades and agreed local annotations; run prepare_annotations then train_ordinal then evaluate held-out camera-domain cases'}
 if accepted:
  import random
  components=duplicate_components(accepted);groups=sorted(set(components));random.Random(protocol['seed']).shuffle(groups)
  splits={group:'train' if i<int(.6*len(groups)) else 'validation' if i<int(.8*len(groups)) else 'test' for i,group in enumerate(groups)}
  for r,group in zip(accepted,components):r['split']=splits[group]
  assert partitions_are_disjoint(accepted)
  report['duplicateComponents']=len(groups)
  report['readyForTraining']=all(len({r['caseId'] for r in accepted if r['split']==s and r['consensusGrade']==g})>=3 for s in ['train','validation','test'] for g in range(4))
 (out/(args.target+'-manifest.json')).write_text(json.dumps(accepted,indent=2),'utf8');(out/(args.target+'-report.json')).write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))
if __name__=='__main__':main()
