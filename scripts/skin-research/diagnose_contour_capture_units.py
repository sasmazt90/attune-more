"""Frozen real browser landmarks: pixel/ratio gates and source-location targets."""
import json,sys,time
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-runtime-followup-20261013';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'services/core-api'))
import contour_appearance as C
import appearance_analysis as A
cv2.setNumThreads(1)
PREV=ROOT/'audit-results/native-material-contour-20261013';CENSUS=ROOT/'audit-results/dry-sag-source-census-20261013'
rows=[];views=[]
for prefix in ['99f82af5','fc3a6b13','05619d0a','f90e68f8','64b02ede','40c7edda']:
    path=CENSUS/'product'/prefix/(prefix+'-automatic-payload.json')
    if prefix=='05619d0a':path=ROOT/'audit-results/dry-sag-native-followup-20261013/05619d0a-payload.json'
    if prefix=='40c7edda':path=ROOT/'audit-results/native-dry-scale-20261013/sag-targeted/40c7edda-payload.json'
    if path.exists():payload=json.loads(path.read_text('utf8'))
    else:
        probe=json.loads((CENSUS/(prefix+'-probe.json')).read_text('utf8'));s=probe['snapshot']
        payload=dict(processingConsent=True,hostedProcessingConsent=False,photo=s['dataUrl'],photoId=s['photoId'],pose=s['angle'],meshes=s['meshes'],exclusions=s['exclusions'],landmarks=s['landmarks'],qualityValid=bool(probe['quality']['isValid'] and probe['poseCaptureCompleted']),conditions=probe['conditions'],temporal=[s['landmarks']]*3)
    image,digest=A.decode_photo(payload['photo']);h,w=image.shape[:2];p=np.array([[v['x']*w,v['y']*h] for v in payload['landmarks']]);axis=p[263]-p[33];axis/=np.linalg.norm(axis);vertical=np.array([-axis[1],axis[0]]);vertical*=1 if vertical[1]>0 else -1
    width=np.linalg.norm(p[61]-p[291]);opening=np.linalg.norm(p[13]-p[14])/width;smile=((p[61]+p[291]-p[13]-p[14])/2)@vertical/width
    norm=np.array([[v['x'],v['y']] for v in payload['landmarks']]);normalized_opening=np.linalg.norm(norm[13]-norm[14])/np.linalg.norm(norm[61]-norm[291])
    start=time.monotonic();result=C.analyze_contour(payload);seconds=time.monotonic()-start
    overlay=image.copy()
    for ids,color in [([61,13,291,14,61],(0,255,255)),([234,454],(255,180,0)),([33,263],(255,0,0))]:
        cv2.polylines(overlay,[np.rint(p[ids]).astype(np.int32)],False,color,1)
        for i in ids:cv2.putText(overlay,str(i),tuple(np.rint(p[i]).astype(int)),cv2.FONT_HERSHEY_SIMPLEX,.35,color,1)
    for region,ids in {'rightCheek':[132,58,172],'leftCheek':[361,288,397],'chin':[149,176,148,152,377,400,378]}.items():
        cv2.polylines(overlay,[np.rint(p[ids]).astype(np.int32)],False,(0,120,255),2)
        trace=result['measurements'].get(region,{}).get('trace',{})
        for point,accepted in zip(trace.get('tracked',[]),trace.get('accepted',[])):
            if point is not None:cv2.circle(overlay,tuple(np.rint(point).astype(int)),1,(0,255,0) if accepted else (255,0,255),-1)
    cv2.putText(overlay,prefix+' mouth %.4f corner %.4f'%(opening,smile),(8,22),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),2)
    cv2.imwrite(str(OUT/(prefix+'-capture-units.png')),overlay);views.append(cv2.resize(overlay,(320,320)))
    rows.append(dict(source=prefix,photoId=digest,payloadSHA256=__import__('hashlib').sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),qualityValid=payload['qualityValid'],pose=payload['pose'],conditions=payload['conditions'],mouthOpeningSourcePixelRatio=float(opening),mouthOpeningNormalizedRatio=float(normalized_opening),lipCornerSourcePixelRatio=float(smile),mouthWidthSourcePixels=float(width),thresholds=dict(opening=.10,corner=-.07,yaw=.65,pitch=.22),units='dimensionless ratios; yaw/pitch browser landmark estimator units, not degrees',mouthLandmarks={str(i):p[i].tolist() for i in [61,291,13,14]},results={k:{a:b for a,b in v.items() if a!='trace'} for k,v in result['measurements'].items()},seconds=seconds))
(OUT/'contour-capture-units.json').write_text(json.dumps(dict(rows=rows,thresholdsChanged=False,normalProductEnabled=False),indent=2),'utf8')
cv2.imwrite(str(OUT/'contour-capture-contact.png'),np.vstack([np.hstack(views[:3]),np.hstack(views[3:])]))
print(json.dumps(rows),flush=True)
