"""Materialize sealed, typed unused-final labels without model inference.

No JPEG is decoded or displayed. True masks/boxes/photo presence remain
separate; outside partial annotations is unknown. Semantic/ROI/rights review
is an explicit later final-readiness task, never a made-up severity label.
"""
import collections,json
from pathlib import Path
import numpy as np
from expanded_sources import OUT,LABELS,sha,write
from review_selected_sources import annotation_mask
from selected_sources import MAP

def main():
 folder=OUT/'unused-final-preparation';manifest=folder/'manifest.json';data=json.loads(manifest.read_text('utf8'));rows=data['rows'];labels=[];counts=collections.defaultdict(collections.Counter)
 for r in rows:
  assert sha(Path(r['absolutePath']))==r['sha256'] and r['split']=='test';targets=[]
  for a in r['annotations']:
   target=LABELS.get(r['source'],{}).get(a['label'])
   if not target:continue
   if a['validMask']:
    # Decode the source annotation, not the photo and not a prediction.
    rr={**r,'source':'v11','annotations':[{**a,'label':'Acne'}]}
    mask=annotation_mask(rr,'acne');assert mask.shape==(r['height'],r['width']) and mask.any()
    targets.append(dict(target=target,type='genuine-polygon-or-RLE',sourceAnnotation=a,positivePixels=int(mask.sum()),outsideAnnotation='unknown',boxFilledAsMask=False,severityGrade=None));counts[target]['maskAnnotations']+=1
   elif a['validBox']:
    targets.append(dict(target=target,type='source-box',sourceAnnotation=a,boxFilledAsMask=False,severityGrade=None));counts[target]['boxAnnotations']+=1
  if r['source']=='csv':
   for name,target in [('Oily-Skin','oil'),('Dry-Skin','dry'),('Eyebags','bags')]:
    value=(r.get('csvLabels') or {}).get(name)
    if value in [0,1]:targets.append(dict(target=target,type='source-photo-presence',presence=value,pixelTruth=False,severityGrade=None));counts[target]['photoPresenceLabels']+=1
  for target in {a['target'] for a in targets}:counts[target]['photos']+=1
  labels.append(dict(sha256=r['sha256'],decodedSHA256=r.get('decodedSHA256'),group=r['group'],source=r['source'],nativeSize=[r['width'],r['height']],targets=targets,sourceFileSHA256Verified=True,sourcePhotoDecoded=False,blindSemanticAndROIReviewPending=True,rightsDeclaration=r['rights'],expertGrade=None,personIndependent=False))
 write('unused-final-preparation/typed-label-index.json',dict(version='sealed-unused-typed-label-preparation-v1',rows=labels,counts={k:dict(v) for k,v in counts.items()},manifestSHA256=sha(manifest),protocolFreezeSHA256=sha(OUT/'label-function-protocol-freeze.json'),preparationComplete=True,finalPerformanceReady=False,sourcePhotosDecoded=False,modelPredictionsOpened=False,oldOpenedTestsExcluded=True,outsidePartialLabelsUnknown=True,boxesAreMasks=False,CSVZerosArePixelLabels=False))
 print('Sealed typed label preparation',len(labels),'source groups; final semantic/ROI review pending',flush=True)
if __name__=='__main__':main()
