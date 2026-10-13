"""Two already-reviewed source targets; annotations never enter inference."""
import hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-material-contour-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
import contour_appearance as C
import appearance_analysis as A
cv2.setNumThreads(1)
selection=json.loads((ROOT/'audit-results/dry-sag-source-census-20261013/contour-selection.json').read_text('utf8'))
targets=[dict(index=468,source=selection[468]['sha256'],region='leftCheek',polygon=[[447,414],[465,438],[461,470],[445,493],[429,500],[428,490],[447,466],[453,440],[439,421]],label='visible local lower-cheek outline lobule; cause/clinical sag unknown'),
         dict(index=111,source=selection[111]['sha256'],region='rightCheek',polygon=[[126,354],[145,387],[158,420],[170,460],[158,473],[146,444],[135,410],[120,367]],label='visible lateral lower-face edge; not age/fold truth; contrast/context review')]
target_file=OUT/'contour-visible-target-labels.json';assert not target_file.exists();target_file.write_text(json.dumps(dict(targets=targets,authority='engineering visual source outline review before branch inference',outsidePolygon='UNKNOWN',clinicalGrade=None),indent=2),'utf8')
rows=[]
for target in targets:
    prefix=target['source'][:8]
    if prefix=='99f82af5':payload=json.loads((ROOT/'audit-results/dry-sag-source-census-20261013/product'/prefix/(prefix+'-automatic-payload.json')).read_text('utf8'))
    else:
        probe=json.loads((ROOT/'audit-results/dry-sag-source-census-20261013'/(prefix+'-probe.json')).read_text('utf8'));s=probe['snapshot']
        payload=dict(processingConsent=True,hostedProcessingConsent=False,photo=s['dataUrl'],photoId=s['photoId'],pose=s['angle'],meshes=s['meshes'],exclusions=s['exclusions'],landmarks=s['landmarks'],qualityValid=bool(probe['quality']['isValid'] and probe['poseCaptureCompleted']),conditions=probe['conditions'],temporal=[s['landmarks']]*3)
    assert not payload['hostedProcessingConsent'];result=C.analyze_contour(payload);image,_=A.decode_photo(payload['photo']);annot=np.zeros(image.shape[:2],np.uint8);poly=np.asarray(target['polygon'],np.int32);cv2.fillPoly(annot,[poly],1);preview=image.copy();cv2.polylines(preview,[poly],True,(255,0,255),2)
    r=result['measurements'].get(target['region']);overlap=None;deviation=None
    if r:
        trace=r.get('trace')
        if trace:
            track=trace['tracked'];hits=[]
            for i,xy in enumerate(track):
                if xy is None:continue
                x,y=np.rint(xy).astype(int);inside=0<=x<image.shape[1] and 0<=y<image.shape[0] and bool(annot[y,x]);cv2.circle(preview,(x,y),2,(0,255,0) if trace['accepted'][i] and r['value'] is not None else (0,180,255),-1)
                if inside:hits.append(dict(index=i,excursion=trace['excursion'][i],noise=trace['localizationUncertainty'][i],accepted=trace['accepted'][i]))
            overlap=dict(observedTargetCenters=len(hits),acceptedTargetCenters=sum(h['accepted'] for h in hits) if r['value'] is not None else 0);deviation=hits
        cv2.imwrite(str(OUT/(prefix+'-contour-target.png')),preview)
    rows.append(dict(source=prefix,pose=payload['pose'],conditions=payload['conditions'],target=target,branchValue=r['value'] if r else None,reason=r['reason'] if r else 'REGION_NOT_IN_CAPTURE',overlap=overlap,localDeviations=deviation));print(json.dumps(rows[-1]),flush=True)
(OUT/'contour-visible-target-comparison.json').write_text(json.dumps(dict(rows=rows,normalProductEnabled=False,clinicalDetectionAccuracyNotComputed=True),indent=2),'utf8')
