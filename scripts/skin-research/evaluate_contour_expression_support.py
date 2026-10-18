"""One predeclared expression-support comparison; original capture gates stay."""
import json,sys,time
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-runtime-followup-20261013';CENSUS=ROOT/'audit-results/dry-sag-source-census-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
import contour_appearance as C,appearance_analysis as A
cv2.setNumThreads(1);rows=[]
targets=json.loads((ROOT/'audit-results/native-material-contour-20261013/contour-visible-target-labels.json').read_text('utf8'))['targets']
for observation in json.loads((OUT/'browser-expression.json').read_text('utf8'))['rows']:
    prefix=observation['source'];path=CENSUS/'product'/prefix/(prefix+'-automatic-payload.json')
    if prefix=='05619d0a':path=ROOT/'audit-results/dry-sag-native-followup-20261013/05619d0a-payload.json'
    if prefix=='40c7edda':path=ROOT/'audit-results/native-dry-scale-20261013/sag-targeted/40c7edda-payload.json'
    if path.exists():payload=json.loads(path.read_text('utf8'))
    else:
        probe=json.loads((CENSUS/(prefix+'-probe.json')).read_text('utf8'));s=probe['snapshot'];payload=dict(processingConsent=True,hostedProcessingConsent=False,photo=s['dataUrl'],photoId=s['photoId'],pose=s['angle'],meshes=s['meshes'],exclusions=s['exclusions'],landmarks=s['landmarks'],qualityValid=bool(probe['quality']['isValid'] and probe['poseCaptureCompleted']),conditions=probe['conditions'],temporal=[s['landmarks']]*3)
    assert payload['photoId']==observation['photoId'];image,_=A.decode_photo(payload['photo']);h,w=image.shape[:2];old=C.analyze_contour(payload)
    delta=np.max(np.abs(np.array([[p['x'],p['y']] for p in payload['landmarks']])-np.array([[p['x'],p['y']] for p in observation['landmarks']])))
    payload['expressionObservation']=dict(photoId=observation['photoId'],version='local-mediapipe-expression-support-v1',scores=observation['blendshapes'])
    start=time.monotonic();new=C.analyze_contour(payload);seconds=time.monotonic()-start;preview=image.copy();comparisons=[]
    for region,r in new['measurements'].items():
        target=next((t for t in targets if t['source'].startswith(prefix) and t['region']==region),None);target_mask=np.zeros((h,w),np.uint8)
        if target:
            poly=np.asarray(target['polygon'],np.int32);cv2.fillPoly(target_mask,[poly],1);cv2.polylines(preview,[poly],True,(255,0,255),2)
        trace=r.get('trace');observed_hits=0;accepted_hits=0
        if trace:
            for xy in trace['guide']:cv2.circle(preview,tuple(np.rint(xy).astype(int)),1,(255,180,0),-1)
            for xy,yes in zip(trace['tracked'],trace['accepted']):
                if xy is None:continue
                x,y=np.rint(xy).astype(int);hit=0<=x<w and 0<=y<h and target_mask[y,x]>0;observed_hits+=int(hit);accepted_hits+=int(hit and yes and r['value'] is not None);cv2.circle(preview,(x,y),1,(0,255,0) if yes and r['value'] is not None else (0,180,255),-1)
        comparisons.append(dict(region=region,before=old['measurements'][region]['value'],beforeReason=old['measurements'][region]['reason'],after=r['value'],afterReason=r['reason'],observedSourceTargetCenters=observed_hits,acceptedSourceTargetCenters=accepted_hits,trackedImageSamples=r['trackedImageSamples'],activeSourcePixels=r['activeSourcePixels'],rawBrightnessEdgeRows=trace.get('rawBrightnessEdgeRows') if trace else None,exteriorConfirmedRows=trace.get('exteriorConfirmedRows') if trace else None,neighborFitSamples=sum(trace['observedNeighborFit']) if trace else 0))
    cv2.imwrite(str(OUT/(prefix+'-expression-contour.png')),preview);(OUT/(prefix+'-expression-result.json')).write_text(json.dumps(new,allow_nan=False),'utf8');rows.append(dict(source=prefix,seconds=seconds,maximumNormalizedLandmarkDelta=float(delta),expressionCoefficients={k:observation['blendshapes'][k] for k in ['mouthSmileLeft','mouthSmileRight','mouthFrownLeft','mouthFrownRight','jawOpen']},rows=comparisons));print(json.dumps(rows[-1]),flush=True)
(OUT/'expression-contour-comparison.json').write_text(json.dumps(dict(rows=rows,normalProductEnabled=False,thresholdTuning=False,qualityOverride=False,clinicalSuccessClaim=False),indent=2),'utf8')
