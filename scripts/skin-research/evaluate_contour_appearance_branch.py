"""Actual browser geometry, image boundary and separate fold/contour evidence."""
import base64,hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-material-contour-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
import contour_appearance as C
import appearance_analysis as A
cv2.setNumThreads(1)
paths=[]
for prefix in ['f90e68f8','64b02ede']:
    paths.append((prefix,ROOT/'audit-results/dry-sag-source-census-20261013/product'/prefix/(prefix+'-automatic-payload.json'),'existing engineering lower-face appearance; strong contour truth not implied'))
for prefix,review in [('e35b68b8','rounded smooth shape; contour target UNKNOWN'),('40c7edda','reviewed ordinary contour control'),('dedbb492','visible submental/neck pleat outside intended jaw target')]:paths.append((prefix,ROOT/'audit-results/native-dry-scale-20261013/sag-targeted'/(prefix+'-payload.json'),review))
paths.append(('05619d0a',ROOT/'audit-results/dry-sag-native-followup-20261013/05619d0a-payload.json','visible lower-cheek contour lobule; engineer optical review, not age or clinical grade'))
for source in json.loads((OUT/'contour-browser-selection.json').read_text('utf8')):
    prefix=source['sha256'][:8];probe=json.loads((OUT/'contour-browser'/(prefix+'-probe.json')).read_text('utf8'));s=probe['snapshot'];accepted=bool(probe['quality']['isValid'] and probe['supportedAngles'] and probe['poseCaptureCompleted'])
    p=dict(processingConsent=True,hostedProcessingConsent=False,photo=s['dataUrl'],photoId=s['photoId'],pose=s['angle'],meshes=s['meshes'],exclusions=s['exclusions'],landmarks=s['landmarks'],qualityValid=accepted,conditions=probe['conditions'],temporal=[s['landmarks']]*3)
    file=OUT/'contour-browser'/(prefix+'-payload.json');file.write_text(json.dumps(p),'utf8');paths.append((prefix,file,'previously reviewed contour reference; fresh automatic capture accepted' if accepted else 'fresh automatic capture rejected; no pose override'))
cases=[]
for prefix,path,review in paths:
    payload=json.loads(path.read_text('utf8'));assert not payload['hostedProcessingConsent'];result=C.analyze_contour(payload);fold=A.analyze_skin(payload);image,_=A.decode_photo(payload['photo']);preview=image.copy();rows=[]
    for region,row in result['measurements'].items():
        trace=row.get('trace');mesh=A.closed_surface_mask(image.shape[:2],payload['meshes'][region],1)
        if trace:
            for xy in trace['guide']:cv2.circle(preview,tuple(np.rint(xy).astype(int)),1,(255,160,0),-1)
            for xy,accepted in zip(trace['tracked'],trace['accepted']):
                if xy is not None:cv2.circle(preview,tuple(np.rint(xy).astype(int)),2,(0,255,0) if accepted and row['value'] is not None else (0,190,255),-1)
        layer=result['maps'].get(region);outside=0
        if layer:
            rgba=cv2.imdecode(np.frombuffer(base64.b64decode(layer['dataUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED);ys,xs=np.where(rgba[:,:,3]>0);sx=xs+int(layer['x']);sy=ys+int(layer['y']);outside=int((~mesh[sy,sx]).sum());assert outside==0
            assert len(xs)==row['activeSourcePixels'] and row['acceptedSamples']==len(xs)
            assert row['value']==100*row['acceptedBoundarySlots']/max(1,row['uniqueObservedSlots'])
        f=next(v for v in fold['measurements'][region] if v['id']=='sag');rows.append(dict(region=region,foldValue=f['value'],foldReason=f['limitationCode'],contourValue=row['value'],contourReason=row['reason'],activeMapPixels=row['activeSourcePixels'],outsideMesh=outside,observedSlots=row['uniqueObservedSlots'],acceptedSlots=row['acceptedBoundarySlots'],imageTracked=row['trackedImageSamples'],trackingResidual=trace['trackingResidual'] if trace else None,rawBrightnessEdgeRows=trace.get('rawBrightnessEdgeRows') if trace else None,exteriorConfirmedRows=trace.get('exteriorConfirmedRows') if trace else None))
    suffix='-v2' if 'exterior' in C.VERSION else ''
    cv2.imwrite(str(OUT/(prefix+'-contour-branch-source'+suffix+'.png')),preview);(OUT/(prefix+'-contour-branch'+suffix+'.json')).write_text(json.dumps(result,allow_nan=False),'utf8')
    cases.append(dict(source=prefix,payloadSHA256=hashlib.sha256(path.read_bytes()).hexdigest(),photoId=payload['photoId'],review=review,qualityValid=payload['qualityValid'],conditions=payload['conditions'],rows=rows,sourceWidth=image.shape[1],sourceHeight=image.shape[0]));print(json.dumps(cases[-1]),flush=True)
(OUT/('contour-branch-comparison-v2.json' if 'exterior' in C.VERSION else 'contour-branch-comparison.json')).write_text(json.dumps(dict(cases=cases,parameters=C.PARAMETERS,normalProductEnabled=False,clinicalGrade=False,geometryRatioNotSeverity=True),indent=2),'utf8')
