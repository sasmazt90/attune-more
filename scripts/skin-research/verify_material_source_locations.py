"""Correct the product-location evidence, never rewrite the frozen 50 labels."""
import json,sys,hashlib
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-runtime-followup-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A,native_dry_path as N,material_component_features as M
from native_flake_support import native_field
cv2.setNumThreads(1)
path=ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json';payload=json.loads(path.read_text('utf8'));photo,digest=A.decode_photo(payload['photo']);capture={}
def observe(im,field,metric):
    capture.update(image=im.copy(),field=field.copy(),metric=metric)
    return field,{'classifierVersion':'diagnostic-proposal-only'}
result=N.analyze_native_dry(payload,observe);origin=result['nativeMetadata']['cropOrigin'];field=capture['field'];unclipped,_=native_field(capture['image'],capture['metric']);ids,rows=M.describe(capture['image'],field,capture['metric']);details=json.loads((OUT/'24031977-components.json').read_text('utf8'));preview=photo.copy()
# Source inspection after the failure receipt: visible lifted/peeling edges,
# not full polygon truth or biological dry/film attribution. The former y243
# rectangles missed these lower material positions; old files stay immutable.
targets=[dict(label='visible irregular left-display cheek material, etiology UNKNOWN',polygon=[[117,307],[141,306],[166,319],[183,337],[177,350],[159,347],[140,329],[120,324]]),dict(label='visible irregular right-display cheek material, etiology UNKNOWN',polygon=[[272,300],[296,301],[313,325],[319,351],[305,366],[287,354],[280,332]])]
for target in targets:
    poly=np.asarray(target['polygon'],np.int32);mask=np.zeros(photo.shape[:2],np.uint8);cv2.fillPoly(mask,[poly],1);local=mask[origin[1]:origin[1]+field.shape[0],origin[0]:origin[0]+field.shape[1]]>0
    touched=[r for r in details if ((ids==r['componentId'])&local).any()];target.update(preAnatomyProposalPixels=int(((unclipped>.04)&local).sum()),eligibleProposalPixels=int(((field>.04)&local).sum()),acceptedPixels=sum(int(((ids==r['componentId'])&local).sum()) for r in touched if r['accepted']),components=[{k:r[k] for k in ['componentId','rect','probability','accepted']} for r in touched],outsidePolygon='UNKNOWN',pixelGroundTruth=False)
    cv2.polylines(preview,[poly],True,(255,0,255),1)
ys,xs=np.where(field>.04);preview[ys+origin[1],xs+origin[0]]=(preview[ys+origin[1],xs+origin[0]]*.6+np.array([0,255,255])*.4).astype(np.uint8)
cv2.imwrite(str(OUT/'24031977-corrected-source-locations.png'),preview)
receipt=dict(source='24031977',photoId=digest,payloadSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),legacyLocationIssue='old y243 locations cover hair/upper cheek rather than the lower visible material; old receipt preserved',sourceLocationReview='engineering source-coordinate visual inspection; exposed development, not independent test',targets=targets,labelsUsedInInference=False,addedToTrain=False,old50LabelsUnchanged=True)
(OUT/'source-location-correction.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True)
