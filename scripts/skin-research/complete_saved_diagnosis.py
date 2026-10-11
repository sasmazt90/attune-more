"""Complete saved product-chain and analytical evidence; no new inference."""
import collections,json
from pathlib import Path
import numpy as np
from expanded_sources import OUT,ROOT,sha,write

def read(p):return json.loads(p.read_text('utf8'))
def iou(a,b):
 x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]));return x*y/max(1e-8,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-x*y)
def match(boxes,truth):
 used=set();records=[]
 for box in sorted(boxes,key=lambda b:-b[4]):
  ranks=sorted([(iou(box,b),i) for i,b in enumerate(truth)],reverse=True);best=next(((v,i) for v,i in ranks if i not in used and v>=.5),None)
  if best:used.add(best[1]);category='matched_source_box'
  elif ranks and ranks[0][0]>=.5:category='duplicate_source_lesion'
  else:category='annotation_unknown'
  records.append(dict(box=box,category=category,matchedTruth=best[1] if best else None))
 return dict(counts=dict(collections.Counter(r['category'] for r in records)),matchedTruth=sorted(used),missedTruth=sorted(set(range(len(truth)))-used),rows=records)

def main():
 d=OUT/'interim-diagnosis';chain=read(d/'yolo-chain.json');product=read(d/'positive-product-chain.json');data=read(OUT/'negative-expanded-detector-data.json')['rows'];results=[]
 observations={(0,0):('off_task','eye structure'),(0,105):('off_task','eyelash/eye boundary'),(0,50):('off_task','nostril'),(0,66):('off_task','lip boundary'),(0,116):('unknown','unlabelled pink skin spot; no expert lesion truth'),(0,46):('duplicate','same labelled lesion'),(1,0):('off_task','black clothing'),(1,5):('unknown','reddish skin; cannot infer missing active pimple label'),(1,39):('unknown','unlabelled skin detail'),(2,0):('engineering_false','forehead texture/crease in reviewed negative support'),(2,1):('engineering_false','cheek/crease in reviewed negative support'),(2,2):('engineering_false','forehead texture/crease in reviewed negative support'),(3,0):('engineering_false','ordinary skin texture in reviewed negative support')}
 reviewed=[]
 for r in read(d/'candidate-closeups.json'):
  category,reason=observations[(r['sourceIndex'],r['index'])];path=d/r['image'];reviewed.append(dict(**r,visualCategory=category,observation=reason,cropSHA256=sha(path),engineeringReview=True,expertClinicalDiagnosis=False))
 write('interim-diagnosis/visual-review.json',dict(rows=reviewed,reviewedCropCount=len(reviewed),allUnknownCandidatesNotRelabelled=True,unlabelledSpotNotConfirmedMissingLabel=True,originalCropReviewAlreadyCompleted=True))
 for r in product['rows']:
  source=next(v for v in data if v['sha256']==r['sha256']);truth=[v['box'] for v in source['annotations'] if v['classId']==0];before=match(r['decoder']['boxes'],truth);bounds=r['finalProductBoxes'];boxes=[[b['x'],b['y'],b['x']+b['width'],b['y']+b['height'],b['confidence']] for b in bounds];after=match(boxes,truth);region=[]
  for name,values in r['actualProductMeasurements'].items():
   for v in values:
    c=v['components'];assert c['candidateCount']==len(c['bounds']);assert v['modelHash']==r['modelSHA256'];assert v['normalizationVersion']=='unique-detection-box-area-fixed-v1'
    if v['value'] is not None:assert abs(v['value']-c['candidateBoxCoveragePercent'])<1e-8
    region.append(dict(region=name,candidateCount=c['candidateCount'],cardValue=v['value'],boxAreaDensity=c['candidateBoxCoveragePercent'],limitation=v['limitationCode'],cardMethod=v['methodVersion'],modelSHA256=v['modelHash'],mapEvidence='bounds saved; localMap is null in saved response, actual localized gradient rendering not proved for candidate'))
  assert sum(v['candidateCount'] for v in region)==len(bounds)
  results.append(dict(sha256=r['sha256'],cameraCrop=r['cameraCrop'],developmentCrop=r['developmentCrop'],rawResearchCandidateCount=len(next(v for v in chain['sources'] if v['source']['sha256']==r['sha256'])['finalBoxes']),normalDecoder=before,afterProductAnatomy=after,matchedTruthRemovedByProductFilter=sorted(set(before['matchedTruth'])-set(after['matchedTruth'])),regions=region,qualityPhysicalValidation=False,normalAPIInstalled=False,sourcePNGPixelParity=r['sourcePixelPNGParity'],filterLesionRetentionProven=set(before['matchedTruth'])<=set(after['matchedTruth'])))
 write('interim-diagnosis/product-filter-label-retention.json',dict(rows=results,savedModelSHA256=product['rows'][0]['modelSHA256'],noNewInference=True,noClaimOfPhysicalCameraAcceptance=True,mapParityPending=True))
 controls=read(OUT/'current-proxy-controls-v3/receipt.json');analytics={}
 causes=dict(oil='Visible specular area requires baseline oil response and local top-hat/shine support; zero does not prove no oil. Capture/exposure gates and photo-class vs regional highlight mismatch remain.',tone='Lab deviation from local median cancels homogeneous colour casts; it measures local photographic variation, not source class or a clinical tone grade.',redness='Lab red excess has a small development separation signal; warm light/pigment and capture gates remain confounders.',lines='Outer-canthus directional Gabor/local detail bands differ from whole-photo wrinkle labels; source-detail and glare gates exclude many photos.',dark='Narrow lower-lid relative contrast vs adjacent skin; two measurable negative photos cannot establish broad specificity.',bags='Local fold/edge/paired-contour support is not a photo bag class; all six positive source photos were unavailable, so positive performance is unmeasured.')
 for t in ['oil','redness','tone','lines','dark','bags']:
  examples=[];counts=collections.defaultdict(collections.Counter)
  for row in controls['rows']:
   label=row['engineeringLabels'].get(t)
   if label not in ['positive','negative']:continue
   values=[v[t] for v in row['base'].values() if t in v];available=[v['value'] for v in values if v['value'] is not None];reasons=sorted({v.get('limitationCode') for v in values if v.get('limitationCode')})
   if not available:
    for reason in reasons:counts[label][reason]+=1
   examples.append(dict(sha256=row['sha256'],group=row['group'],split=row['split'],label=label,photoMaximum=max(available) if available else None,unavailableReasons=reasons,regions=values))
  analytics[t]=dict(summary=controls['summary'][t],unavailablePhotoReasonCounts={k:dict(v) for k,v in counts.items()},reasonAssessment=causes[t],examples=examples,sourceClassNotClinicalGrade=True,methodVersion='appearance-cv-6',candidateMaskMetricsSeparate=True,accepted=False)
 write('interim-diagnosis/analytic-scope-assessment.json',dict(targets=analytics,inputReceiptSHA256=sha(OUT/'current-proxy-controls-v3/receipt.json'),codeSHA256=sha(ROOT/'services/core-api/appearance_analysis.py'),noNewInference=True,AGTopicsExcluded=['type','dry','sag']))
 print('SAVED DIAGNOSIS COMPLETED',[(len(r['normalDecoder']['matchedTruth']),len(r['afterProductAnatomy']['matchedTruth']),r['matchedTruthRemovedByProductFilter']) for r in results],flush=True)
if __name__=='__main__':main()
