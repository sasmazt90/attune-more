"""Finite source review; neutral-looking is not a sag grade or dry pixel label."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-camera-scope-20261013';sources=json.loads((OUT/'alternate-domain-selection.json').read_text('utf8'));rows=[]
for i,r in enumerate(sources):
    reason='natural source; lower boundary partly available, pose/quality pending real MediaPipe; no verified prominence label'
    if i in [2,3,4,5]:reason='partial face/profile or upper-face crop; lower-boundary neutral acceptance not established'
    if i==6:reason='visible stock attribution, extreme skin close-up; excluded from TRAIN and contour acceptance'
    if i==1:reason='natural full face; beard confounds lower boundary; no contour positive label'
    if i==13:reason='natural near-neutral side portrait with visible lower-face fullness; fullness/roundness alone is not local outward prominence truth; target UNKNOWN'
    if i in [9,10,14,15]:reason='natural full face, apparently near-neutral; ordinary-contour control candidate; pending actual pose/expression/quality and local support review'
    rows.append(dict(**r,reviewIndex=i,reviewReason=reason,neutralContourPositive=False,clinicalSagLabel=None,visibleDryMaterialPixelLabel=None,weakPhotoClassAsComponentTruth=False))
(OUT/'alternate-domain-reviewed.json').write_text(json.dumps(dict(rows=rows,authority='engineering full-source visual review, before branch inference',outsideReviewedAreas='UNKNOWN',wholeDataSetRejected=False),indent=2),'utf8')
selected=[rows[i] for i in [9,10,13,14,15]]
(OUT/'contour-probe-selection.json').write_text(json.dumps(selected,indent=2),'utf8')
# Reuse a previously recorded licensed native video source as a camera fixture,
# not its API answer or CNN feature cache. Two portrait stress cases stay listed.
old=ROOT/'audit-results/all-health-20261010/natural-skin';inventory=json.loads((old/'measurements-private.json').read_text('utf8'));video=next(r for r in inventory if r['index']==10)
source=ROOT/video['source'];assert source.exists() and hashlib.sha256(source.read_bytes()).hexdigest()==video['sourceSHA256']
(OUT/'camera-fixture-selection.json').write_text(json.dumps(dict(nativeVideoSource=dict(sourcePath=str(source),sourceSHA256=video['sourceSHA256'],previouslyLicensedLocalSource=True,pixelResizeForRuntime=False),portraitStressPreserved=['1944x2592/e1646fda','1920x2160/licensed-portrait'],idealConstraintIsNotMaximum=True,physicalUserCameraTest=False,actualTrackSettingsPending=True),indent=2),'utf8')
print(json.dumps(dict(contourSources=[r['sha256'][:8] for r in selected],cameraSource=str(source.relative_to(ROOT)))))
