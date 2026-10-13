"""Pre-fit engineering partial visible-object annotations on unchanged controls."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-component-followup-20261013';OLD=ROOT/'audit-results/dry-sag-source-census-20261013'
controls=json.loads((OLD/'flake-controls/controls-reviewed.json').read_text('utf8'))['controls']
# Coordinates are in the previously frozen native ROI. These are visible-object
# partial outlines, not complete image segmentation or clinical truth.
positive={
0:[[(13,75),(21,78),(31,78),(37,83),(29,88),(22,88),(17,85)],[(125,61),(142,63),(152,68),(153,75),(144,73),(131,69)],[(46,98),(55,99),(59,110),(56,114),(48,114),(43,108)],[(92,118),(110,118),(117,126),(111,131),(98,126)]],
1:[[(90,4),(98,4),(99,14),(94,18),(90,11)],[(47,106),(59,102),(61,109),(56,114),(49,115),(47,111)],[(106,133),(116,134),(117,140),(113,146),(111,153),(106,154),(106,143)],[(4,122),(12,120),(15,126),(14,130),(9,130),(5,127)]],
2:[[(80,115),(88,118),(90,124),(91,134),(87,134),(82,128)],[(69,75),(75,73),(79,74),(80,78),(77,81),(72,80)]],
3:[[(31,43),(36,40),(36,49),(33,56),(30,57),(31,51)],[(8,49),(12,48),(16,52),(14,54),(8,52)],[(47,51),(51,48),(57,46),(62,46),(64,50),(61,55),(55,57),(52,53)]],
8:[[(5,80),(13,79),(23,78),(19,90),(14,99),(7,98),(4,90)]],
9:[[(107,34),(119,34),(118,51),(111,54),(111,43)],[(79,88),(86,87),(89,94),(87,105),(84,110),(80,109),(80,98)],[(18,126),(27,122),(32,125),(30,134),(24,136),(18,132)]],
10:[[(138,122),(145,117),(151,125),(149,137),(144,144),(138,142),(143,133)]],
11:[[(13,95),(18,94),(17,113),(14,119),(11,119),(10,111)],[(63,99),(69,99),(77,109),(76,114),(68,111),(65,105)],[(25,113),(30,110),(35,112),(37,117),(34,119),(25,119)]]}
negative={4:[[18,45,15,16],[87,63,16,18],[59,20,15,17]],5:[[18,28,20,20],[88,66,22,20],[116,116,22,20]],6:[[42,39,24,24],[85,80,24,24],[120,118,24,24]],7:[[20,28,30,30],[90,75,30,30],[116,119,25,25]],12:[[13,15,25,20],[68,20,20,20],[118,105,20,20]],13:[[8,65,25,30],[77,73,25,25],[120,113,25,25]],14:[[15,15,25,25],[65,32,25,25],[25,45,30,25]],15:[[60,60,50,45],[190,180,50,45],[330,70,50,45]]}
uncertain={2:[[117,100,13,12]],8:[[20,37,14,18],[27,102,10,17]],10:[[13,72,13,16],[46,107,9,17]]}
rows=[]
for c in controls:
 i=c['controlIndex'];x,y,w,h=c['roi'];source=Path(c['sourcePath']);assert hashlib.sha256(source.read_bytes()).hexdigest()==c['sourceSHA256']
 im=Image.open(source).convert('RGB').crop((x,y,x+w,y+h)).resize((w*4,h*4));d=ImageDraw.Draw(im)
 objects=[]
 for poly in positive.get(i,[]):objects.append(dict(label='visible-material',polygon=poly,meaning='partial visible peeling-material outline; etiology unconfirmed'))
 for label,rects in [('reviewed-non-flake',negative.get(i,[])),('unknown',uncertain.get(i,[]))]:
  for a,b,ww,hh in rects:objects.append(dict(label=label,polygon=[[a,b],[a+ww-1,b],[a+ww-1,b+hh-1],[a,b+hh-1]],meaning='reviewed local pores/reflection/texture, not whole-image health' if label!='unknown' else 'material, texture or processing ambiguity'))
 for j,obj in enumerate(objects):
  assert all(0<=a<w and 0<=b<h for a,b in obj['polygon'])
  color={'visible-material':'lime','reviewed-non-flake':'red','unknown':'yellow'}[obj['label']];points=[(a*4,b*4) for a,b in obj['polygon']];d.line(points+[points[0]],fill=color,width=2);d.text(points[0],str(j),fill=color)
 im.save(OUT/f'control-{i:02d}-object-labels.png')
 rows.append({**c,'objects':objects,'labelAuthority':'engineering visual native-source inspection before fitting; not expert diagnosis','outsideObjects':'unknown'})
file=OUT/'object-labels.json';assert not file.exists()
file.write_text(json.dumps(dict(frozenUTC=datetime.now(timezone.utc).isoformat(),protocolSHA256=hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest(),controls=rows,fitExecuted=False,referenceObjectsGeneratedFromProposal=False,allOldSourcesRetained=len(rows)==len(controls),personIndependentClaim=False),ensure_ascii=False,indent=2),'utf8')
# Every contact cell has been visually inspected after actual pose calculation.
sources=json.loads((OUT/'unseen-face-selection.json').read_text('utf8'))
natural={1,2,6,8,9,11,12,20,25,26,29,30,33,36,39,46,50,51,53,58,64,65,67,68,70,72,74,76,77,79,81,83,84,85,86,87,88,89,90,91,92,93,94,95}
neutral={2,8,9,46,51,77,85,90,93,94};candidates={68,92};review=[]
for r in sources:
 i=r['censusIndex'];p=json.loads((OUT/(r['sha256'][:8]+'-probe.json')).read_text('utf8'))
 reason='Composite/cut-and-paste and/or black occlusions; not a single natural camera source.';status='rejected-composite';categories=['composite-or-occluded']
 if i in natural:
  categories=['single-photograph-candidate'];reason='Expression, pose, framing, accessories or uncertain target: not an established neutral lower-contour positive.';status='rejected-for-positive-acceptance'
  if i in neutral:status='appropriate-for-control-review';reason='Neutral single-photo candidate; visible beard/ordinary contour or firm-looking boundary does not establish a positive sag target.';categories+=['neutral-candidate','target-not-established']
  if i in candidates:status='ambiguous-positive-candidate';reason='Visible lower contour fold, but mouth/expression and target scope need full-photo/product review; age is not truth.';categories+=['lower-contour-visible','expression-or-target-uncertain']
  if i==30:status='quarantined-near-copy';reason='Same underlying portrait as previously inspected f90e68f8 at a wider framing; not a new independent positive.';categories+=['prior-source-near-copy']
  if not p['quality']['isValid'] or not p['supportedAngles'] or p['snapshotFailure']:reason+=' Actual product quality/pose/snapshot gate is not eligible.'
 review.append(dict(index=i,sha256=r['sha256'],group=r['group'],rights=r['rights'],status=status,categories=categories,reason=reason,actualPoseQuality={k:p[k] for k in ('quality','conditions','supportedAngles','mouthOpening','snapshotFailure','realMediaPipe')},expertTruth=False))
(OUT/'unseen-face-visual-review.json').write_text(json.dumps(dict(records=review,reviewedGroups=len(review),selectedGroups=len(sources),outsideSelectionUnreviewed=json.loads((OUT/'selection-receipt.json').read_text('utf8'))['remainingUnreviewedGroups'],priorReviewsRepeated=False),ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(objects=sum(len(r['objects']) for r in rows),visibleMaterialObjects=sum(o['label']=='visible-material' for r in rows for o in r['objects']),unknownObjects=sum(o['label']=='unknown' for r in rows for o in r['objects']),reviewedNewFaceGroups=len(review))))
