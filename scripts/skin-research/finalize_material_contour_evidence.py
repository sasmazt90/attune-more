"""Compute admission evidence including the actual full native product path."""
import base64,collections,hashlib,json,subprocess,sys,urllib.request
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-material-contour-20261013';sys.path.insert(0,str(ROOT/'services/core-api'));sys.path.insert(0,str(ROOT/'scripts/skin-research'))
import appearance_analysis as A
from component_flake_gate import masks
def read(p):return json.loads(p.read_text('utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def decode(url):return cv2.imdecode(np.frombuffer(base64.b64decode(url.split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)
review=read(OUT/'added-components-reviewed.json');initial=read(OUT/'material-encoder-comparison.json');corrected=read(OUT/'material-encoder-scale-corrected.json');native=read(OUT/'encoder-native-product-comparison.json');contour=read(OUT/'contour-branch-comparison-v2.json');contour_old=read(OUT/'contour-branch-comparison.json');labels=read(ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json')
summaries=[]
for factor in [1.,.5]:
    for kind in ['pul','raw','old']:
        rows=[r for r in corrected['rows'] if r['factor']==factor and r['kind']==kind];obj=[o for r in rows for o in r['objects'] if o['label']=='visible-material']
        summaries.append(dict(factor=factor,kind=kind,objects=len(obj),methods={name:dict(hits=sum(o['fields'][name]['objectHit'] for o in obj),negativeSourcePixels=sum(r['negative'][name]['activeSourcePixels'] for r in rows)) for name in ['proposal','encoder','eightExpanded','tenPreserved']}))
matrix={k:np.zeros((2,2),int) for k in ['encoderAccepted','geometryAccepted','preservedTenAccepted']}
for row in corrected['validationComponents']:
    for name in matrix:matrix[name][row['label'],int(row[name])]+=1
misses=[dict(controlIndex=r['controlIndex'],sourceSHA256=r['sourceSHA256'],factor=r['factor'],objectIndex=o['index'],proposal=o['fields']['proposal'],encoder=o['fields']['encoder']) for r in corrected['rows'] for o in r['objects'] if o['label']=='visible-material' and o['fields']['proposal']['objectHit'] and not o['fields']['encoder']['objectHit']]

# Review is restricted to the actual marked lens rim; outside this component
# is UNKNOWN, not automatically healthy eye skin. This source was selected in
# the previous native path phase, before this fit and its predictions.
full_scope=[]
for r in native['rows']:
    result=read(OUT/(r['source']+'-encoder-native-result.json'));h=result['sourceHeight'];w=result['sourceWidth'];active=np.zeros((h,w),bool)
    for layer in result['maps'].values():
        rgba=decode(layer['dataUrl']);x,y=int(layer['x']),int(layer['y']);active[y:y+rgba.shape[0],x:x+rgba.shape[1]]|=rgba[:,:,3]>0
    scope=dict(source=r['source'],activeUniqueSourcePixels=int(active.sum()))
    if r['source']=='9bab7ab2':
        rim=np.zeros_like(active);rim[326:350,212:281]=True
        scope.update(reviewedFailureClass='eyewear-rim mistaken for material',reviewRectangle=[212,326,69,24],falseMaterialPixelsInReviewedRim=int((active&rim).sum()),wholeEyeNegative=False)
    if r['source']=='24031977':
        # Visible flaking/film was already recorded by the source review.
        # These small descriptive polygons do not establish etiology or label
        # every pixel inside as material, and were never supplied to inference.
        polygons=[[[58,243],[70,244],[87,258],[93,285],[83,306],[71,286]],[[254,242],[279,245],[295,265],[306,292],[286,297],[267,272]]]
        areas=[]
        for polygon in polygons:
            mask=np.zeros((h,w),np.uint8);cv2.fillPoly(mask,[np.asarray(polygon,np.int32)],1);areas.append(dict(polygon=polygon,markedSupportInside=int((active&(mask>0)).sum()),scope='visible peeling/film location; etiology UNKNOWN; not pixel precision truth'))
        scope.update(materialLocationReview=areas)
    control=next((c for c in labels['controls'] if c['sourceSHA256'].startswith(r['source'])),None)
    if control:
        known,_=masks((h,w),control);neg=known['reviewed-non-flake']>0
        scope.update(existingControlIndex=control['controlIndex'],reviewedNegativePixels=int(neg.sum()),actualProductNegativeActivePixels=int((active&neg).sum()))
    full_scope.append(scope)

contour_changes=[]
for current,old in zip(contour['cases'],contour_old['cases']):
    assert current['source']==old['source']
    for now,prev in zip(current['rows'],old['rows']):
        assert now['region']==prev['region']
        contour_changes.append(dict(source=current['source'],region=now['region'],before=prev['contourValue'],after=now['contourValue'],afterReason=now['contourReason'],rawBrightnessEdgeRows=now['rawBrightnessEdgeRows'],exteriorConfirmedRows=now['exteriorConfirmedRows'],activeMapPixels=now['activeMapPixels'],outsideMesh=now['outsideMesh']))

# One read-only normal API preservation check, not a repeated UI campaign.
payload=read(ROOT/'audit-results/dry-sag-source-census-20261013/product/f90e68f8/f90e68f8-automatic-payload.json');assert not payload['hostedProcessingConsent'];expected=A.analyze_skin(payload)
request=urllib.request.Request('http://127.0.0.1:8000/api/local-health/skin',json.dumps(payload).encode(),{'Content-Type':'application/json'})
actual=json.loads(urllib.request.urlopen(request,timeout=45).read());same=all(actual[k]==expected[k] for k in ['measurements','maps','contours']);assert same
source_receipt=read(ROOT/'.runtime/skin-proposal-tracking-final-20261013/source-receipt.json');frontend={name:sha(ROOT/name)==digest for name,digest in source_receipt.items()};assert all(frontend.values())
unchanged=subprocess.check_output(['git','diff','085a20395c009199c5924ed9683d3f98ce771bb1','--','services/core-api/appearance_analysis.py','services/core-api/instant_appearance.py','services/core-api/skin_general.py','services/core-api/local_health.py','apps/vehicle-app','packages/shared'],cwd=ROOT)==b'';assert unchanged
native_rows=[r for r in corrected['rows'] if r['factor']==1];objects=[o for r in native_rows for o in r['objects'] if o['label']=='visible-material']
preserved=sum(o['fields']['tenPreserved']['objectHit'] and o['fields']['encoder']['objectHit'] for o in objects);old_hits=sum(o['fields']['tenPreserved']['objectHit'] for o in objects)
false_rim=next(r['falseMaterialPixelsInReviewedRim'] for r in full_scope if r['source']=='9bab7ab2');latency=max(r['seconds'] for r in native['rows'])
decision=dict(oldGateHits=old_hits,newGateHits=sum(o['fields']['encoder']['objectHit'] for o in objects),oldHitsRetained=preserved,allOldHitsRetained=preserved==old_hits,reviewedNegativeNativePixels=sum(r['negative']['encoder']['activeSourcePixels'] for r in native_rows),reviewedEyewearFailurePixels=false_rim,maxNativeObservedSeconds=latency,apiDeadlineSeconds=45,withinAPIDeadline=latency<=45,normalProductEnabled=False,
    reasons=['native material retention is incomplete and half-resolution capture degrades','actual eyewear edge is accepted as material','full high-resolution inference exceeds normal API time budget'])
head=read(OUT/'encoder-material-head.json');assert head['fitCount']==1 and not head['accepted'] and corrected['headRefitted'] is False and corrected['trainFeaturesUnchanged']
files=['added-components-reviewed.json','material-protocol.json','source-nearcopy-check.json','encoder-material-head.json','material-encoder-comparison.json','material-encoder-scale-corrected.json','encoder-native-product-comparison.json','contour-branch-comparison.json','contour-branch-comparison-v2.json','contour-visible-target-labels.json','contour-visible-target-comparison.json']
evidence=dict(baselineSHA='085a20395c009199c5924ed9683d3f98ce771bb1',BUILD_ID=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip(),productionChanged=False,
    dataReview=dict(selectedAddedSourceGroups=22,reviewedComponents=len(review['rows']),classCounts=review['counts'],includedAddedGroups=review['includedGroups'],sourceExclusions=review['sourceExclusions'],oldLabelsSHA256=sha(ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json'),outsideKnownLabels='UNKNOWN',personIndependentClaim=False),
    trainScope={k:initial[k] for k in ['trainRows','trainGroups','trainClassCounts','classGroupCounts','validationRows','validationIndependentFinal']},encoder=dict(source='local original ImageNet safe weights, not skin-type head',sha256=head['encoderSHA256'],frozen=True,threads=1,batch=4,maximumResidentCropTensors=32,headFitCount=1),
    proposalChanged=False,originalNativeComparison=initial['summary'],scaleCorrectedComparison=corrected['summary'],domainComparisons=summaries,componentValidationConfusion={k:v.tolist() for k,v in matrix.items()},classifierMaterialMisses=misses,
    cropCorrection=dict(reason='native minimum context/margins did not shrink with a controlled half-source sampling; physical context silently doubled',version=corrected['cropSamplingVersion'],same63TrainFeatures=corrected['trainFeaturesUnchanged'],headRefitted=corrected['headRefitted'],actualNativeProductInputChanged=False),
    fullNativeProduct=native,fullSourceSupportReview=full_scope,dryAdmission=decision,contourMechanism='observed exterior boundary tracking, roll/face-width normalization, central-excluded neighbor curvature/excursion; branch independent of fold; no history reference',contourChanges=contour_changes,contourVisibleTargets=read(OUT/'contour-visible-target-comparison.json'),
    contourAdmission=dict(normalProductEnabled=False,realPositiveCaptureDemonstrated=False,reason='image/neighbor contour observation and capture-expression gates remain limiting; a conservative null or normal contour zero is not positive sag success'),
    preservation=dict(normalAPIEqualsSource=same,normalAPIPhotoId=actual['photoId'],frontendMatchedFiles=sum(frontend.values()),normalSourcePathsUnchanged=unchanged,newBuild=False,userRecordsRewritten=False,AGTouched=False,normalDry='eligible-flake-luma-union-v3',normalChin='contour-fold-lower-chin-observed-runs-v9',normalCheek='contour-fold-visible-region-unique-centers-v7'),
    focusedTests=dict(firstRunPassed=33,finalAffectedFilePassed=11,coverage='crop RGB/scale, train-only scaler, real edge versus guide, no unseen continuity, source roll/scale, skin-shadow rejection, same accepted pixel support regardless of confidence; prior native/v9/history regressions retained'),
    artifactInventory=[dict(path=str((OUT/f).relative_to(ROOT)),bytes=(OUT/f).stat().st_size,sha256=sha(OUT/f)) for f in files])
target=ROOT/'docs/material-contour-evidence-20261013.json';target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n','utf8')
print(json.dumps(dict(decision=decision,domain=summaries,fullScope=full_scope,publicBytes=target.stat().st_size)))
