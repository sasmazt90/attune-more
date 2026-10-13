"""Isolated native anatomical dryness path; does not change normal v3 selection.

All score numerators/denominators are original source pixels. Rendering is
lossless native PNG by default. Display pooling is an independent utility.
"""
import cv2
import numpy as np
import time
from native_flake_support import native_field,VERSION as PROPOSAL_VERSION

NORMALIZATION='native-material-visible-source-area-v4-staging'
SAMPLING='native-source-closed-cells-max-union-v4-staging'

def analyze_native_dry(payload,material_filter=None,check=None,profile=None,material_filter_reference=False):
    # Reuse geometry/encoding contracts, not the resized photometric fields.
    from appearance_analysis import decode_photo,closed_surface_mask,map_result,LIMITS
    check=check or (lambda:None);check();t=time.monotonic();timings={}
    bgr,digest=decode_photo(payload['photo']);timings['decode']=time.monotonic()-t;t=time.monotonic()
    if digest!=payload['photoId']:raise ValueError('SOURCE_HASH_MISMATCH')
    h,w=bgr.shape[:2];points=payload['landmarks'];face=abs(points[454]['x']-points[234]['x'])*w
    source_points=np.array([[p['x'],p['y']] for m in payload['meshes'].values() for p in m['points']],float)
    if not len(source_points):raise ValueError('INVALID_GEOMETRY')
    metric=max(.125,face/640);pad=max(48,int(np.ceil(40*metric)))
    x0=max(0,int(np.floor(source_points[:,0].min()))-pad);y0=max(0,int(np.floor(source_points[:,1].min()))-pad)
    x1=min(w,int(np.ceil(source_points[:,0].max()))+pad+1);y1=min(h,int(np.ceil(source_points[:,1].max()))+pad+1)
    origin=(x0,y0);crop=bgr[y0:y1,x0:x1];shape=crop.shape[:2]
    if not crop.size:raise ValueError('INVALID_GEOMETRY')
    gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY);g=gray.astype(np.float32)/255
    masks={name:closed_surface_mask(shape,mesh,1,origin) for name,mesh in payload['meshes'].items()}
    excluded=np.zeros(shape,np.uint8)
    for box in payload.get('exclusions',[]):
        cv2.rectangle(excluded,(int(np.floor(box['x']-x0)),int(np.floor(box['y']-y0))),(int(np.ceil(box['x']+box['w']-x0)),int(np.ceil(box['y']+box['h']-y0))),1,-1)
    holes=[[33,160,158,133,153,144],[263,387,385,362,380,373],[61,40,37,0,267,270,291,321,314,17,84,91],[98,97,2,326,327,294],[70,63,105,66,107,55,65,52],[300,293,334,296,336,285,295,282]]
    for indices in holes:
        p=np.asarray([[points[i]['x']*w-x0,points[i]['y']*h-y0] for i in indices],np.int32);cv2.fillPoly(excluded,[p],1)
    # Native filament exclusion scales with actual source face span. Ordinary
    # compact pores are handled by the material proposal, not an entire halo.
    kernel=max(3,2*int(round(3*metric))+1);dark=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,np.ones((kernel,kernel),np.uint8))>35
    n,ids,stats,_=cv2.connectedComponentsWithStats(dark.astype(np.uint8),8);keep=np.zeros(n,bool)
    for i in range(1,n):
        _,_,ww,hh,_=stats[i];keep[i]=max(ww,hh)>=max(3,8*metric) and max(ww,hh)/max(1,min(ww,hh))>=3
    hair=cv2.dilate(keep[ids].astype(np.uint8),np.ones((max(3,2*int(round(2*metric))+1),)*2,np.uint8))>0
    exposed=(excluded==0)&~hair&(g>.12);clipped=g>.975;visible=exposed&~clipped
    union=np.logical_or.reduce(list(masks.values()))&visible
    timings['geometry']=time.monotonic()-t;check();t=time.monotonic()
    field,metadata=native_field(crop,metric,union,check=check,**({'reference':True} if material_filter_reference else {}))
    reference_support=metadata.pop('_referenceSupport',None)
    timings['proposal']=time.monotonic()-t;check();t=time.monotonic()
    if material_filter is not None:
        field,classification=material_filter(crop,field,metric,reference_support) if material_filter_reference else material_filter(crop,field,metric)
        field*=union;metadata.update(classification)
    timings['material']=time.monotonic()-t;check();t=time.monotonic()
    rows={};maps={};measured=[]
    minimum_area=100/max(min(1,320/max(face,1))**2,1e-8)
    def item(region,mask,reason):
        check()
        eligible=mask&visible;active=(field>0)&eligible
        value=None if reason else float(100*active.sum()/max(1,eligible.sum()))
        row=dict(id='dry',type='appearance_proxy',region=region,value=value,unit='percent-visible-area',methodVersion='appearance-native-dry-1',normalizationVersion=NORMALIZATION,
            modelVersion=None,modelHash=None,quality='insufficient' if reason else 'valid',limitationCode=reason,referenceId=None,localMap=None,
            scoreDirection='higher-is-more-visible',captureConditions=payload['conditions'],uncertainty=['applied-products','illumination','visible-material-only','unvalidated-cosmetic-proxy'],
            evaluatedArea=dict(scope='native-visible-anatomical-source',sourcePixels=int(eligible.sum()),analysisPixels=int(eligible.sum()),anatomicalSourcePixels=int(mask.sum()),sourceFacePixels=face),
            components=dict(samplingSupportVersion=SAMPLING,proposalVersion=PROPOSAL_VERSION,acceptedMaterialSourcePixels=int(active.sum()),uniqueVisibleSourcePixels=int(eligible.sum()),overlapCountedOnce=True,confidenceNotSeverity=True,nativeAnalysisResize=False,meaning='local visible material support; not moisture or clinical severity',**({'classifierVersion':metadata['classifierVersion']} if material_filter is not None else {})))
        if material_filter is not None:
            row['normalizationVersion']='native-encoder-material-source-area-v6-staging' if 'ring-conditioned' in metadata['classifierVersion'] else 'native-encoder-material-source-area-v5-staging' if 'block-balanced' in metadata['classifierVersion'] else 'native-encoder-material-source-area-v4-staging'
        if reason is None:
            # Step=1 retains every accepted tiny native component. Existing SVG
            # mesh clipping is still required by any caller that displays it.
            layer=map_result(field,eligible,region,'dry',digest,payload['pose'],bgr.shape,1.,'percent-visible-area',1.,origin)
            if layer:
                layer.update(method='appearance-native-dry-1',normalizationVersion=row['normalizationVersion'],nativeScoreSourcePixels=int(active.sum()),displayAggregation='lossless-native-grid')
                maps[region+':dry']=layer;row['localMap']=dict(key=region+':dry',photoId=digest,region=region,criterion='dry',coordinateSpace='source-pixels')
        return row
    for region,mask in masks.items():
        support=mask&exposed;eligible=mask&visible
        reason='CAPTURE_QUALITY' if not payload.get('qualityValid') else 'INSUFFICIENT_SOURCE_DETAIL' if face<LIMITS['minFacePixels'] else 'GLARE_OR_EXPOSURE' if support.any() and clipped[support].mean()>.03 else 'INSUFFICIENT_VISIBLE_AREA' if eligible.sum()<minimum_area else None
        rows[region]=item(region,mask,reason)
        if reason is None:measured.append(mask)
    general=None
    if payload['pose']=='FRONT':
        required=['forehead','rightCheek','leftCheek','chin'];complete=all(name in rows and rows[name]['value'] is not None for name in required)
        mask=np.logical_or.reduce(measured) if measured else np.zeros(shape,bool)
        general=item('overview',mask,None if complete else 'INSUFFICIENT_FRONT_COVERAGE')
    timings['mapsAndResults']=time.monotonic()-t
    if profile is not None:profile.update(timings)
    check()
    return dict(photoId=digest,sourceWidth=w,sourceHeight=h,measurements=rows,general=general,maps=maps,
        nativeMetadata={**metadata,'cropOrigin':list(origin),'cropShape':[crop.shape[1],crop.shape[0]],'sourceImageSize':[w,h],'normalProductEnabled':False})
