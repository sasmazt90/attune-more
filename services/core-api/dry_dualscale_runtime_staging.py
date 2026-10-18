"""Explicit staging caller, never imported by the normal product selector.

Reuses actual native geometry/quality and the same encoder/head instance.
Original valid-mask PNGs are lossless native geometry, not predicted support.
"""
import base64,copy,time
import cv2,numpy as np
from dry_dualscale_support import merge_accepted_supports,VERSION,OPTICAL_CUTOFF
METHOD='appearance-native-dualscale-dry-1-staging'
NORMALIZATION='native-calibrated-dualscale-visible-source-area-v9-staging'

def _mask(layer,shape):
    data=base64.b64decode(layer['validMaskUrl'].split(',',1)[1],validate=True)
    image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_GRAYSCALE)
    if layer['step']!=1 or image.shape!=(layer['height'],layer['width']):raise ValueError('NATIVE_VISIBLE_GRID_REQUIRED')
    x,y=int(layer['x']),int(layer['y'])
    if x!=layer['x'] or y!=layer['y'] or x<0 or y<0 or x+image.shape[1]>shape[1] or y+image.shape[0]>shape[0]:raise ValueError('VISIBLE_MASK_SOURCE_BOUNDS')
    mask=np.zeros(shape,bool);mask[y:y+image.shape[0],x:x+image.shape[1]]=image>0
    if int(mask.sum())!=layer['sampleCount']:raise ValueError('VISIBLE_MASK_AREA_MISMATCH')
    return mask

def _half_visibility(visible,shape):
    """A half cell can be processed if it owns any original visible center."""
    ys,xs=np.where(visible);xx=np.floor((xs+.5)*.5).astype(int);yy=np.floor((ys+.5)*.5).astype(int)
    ok=(xx<shape[1])&(yy<shape[0]);result=np.zeros(shape,bool);result[yy[ok],xx[ok]]=True
    return result

def _half_material(image,field,metric,encoder,head,check):
    # Same frozen feature/head contract, with the already-fixed half density
    # explicitly passed to source-scaled near/context crop construction.
    import material_component_features as M
    labels,rows=M.describe(image,field,metric);allowed=np.zeros(int(labels.max())+1,bool)
    calls=getattr(encoder,'calls',0);features={};encoded=0
    for offset in range(0,len(rows),16):
        check();current=rows[offset:offset+16];pending={};pairs=[]
        for row in current:
            pair=[]
            for box in M.component_crop_boxes(row,metric,pixel_density=.5):
                key=tuple(box[k] for k in ('x','y','width','height'));pair.append(key)
                if key not in features and key not in pending:pending[key]=M.material_crop(image,box)
            pairs.append(pair)
        keys=list(pending)
        for start in range(0,len(keys),16):
            check();batch=keys[start:start+16];output=encoder.extract([pending[k] for k in batch],16,check=check);features.update(zip(batch,output));encoded+=len(batch)
        p=M.predict(np.c_[[np.r_[features[a],features[b]] for a,b in pairs],[row['geometry'] for row in current]],head)
        for row,prob in zip(current,p):allowed[row['componentId']]=prob>=head['threshold']
    check();return field*allowed[labels],dict(candidateComponents=len(rows),acceptedComponents=int(allowed.sum()),encoderCalls=getattr(encoder,'calls',0)-calls,encodedCrops=encoded,threshold=head['threshold'],pixelDensity=.5)

def analyze_staging(payload,head,encoder,check):
    """Current native path once, half path once, SAME source-grid union helper.

    This is an in-process dry-path check, not a full API performance proof.
    Caller must admit actual capture/consent and retain the45s/2500MiB guards.
    """
    from native_dry_path import analyze_native_dry
    from native_flake_support import native_field
    from appearance_analysis import map_result
    import material_component_features as M
    check();started=time.monotonic();captured={};native_profile={}
    def classify(image,field,metric):
        accepted,metadata=M.filter_material_support_streamed(image,field,metric,encoder,head,check=check)
        captured.update(image=image,field=accepted.copy(),metric=metric)
        return accepted,metadata
    native=analyze_native_dry(payload,material_filter=classify,check=check,profile=native_profile)
    shape=(native['sourceHeight'],native['sourceWidth']);visible=np.zeros(shape,bool);masks={}
    for key,layer in native['maps'].items():
        masks[key]=_mask(layer,shape);visible|=masks[key]
    # Only actually published valid regions contribute. Insufficient rows remain
    # null; no half branch can manufacture a valid region or enlarge its area.
    origin=tuple(native['nativeMetadata']['cropOrigin']);image=captured['image'];h,w=image.shape[:2];x,y=origin
    visible_crop=visible[y:y+h,x:x+w]
    accepted_native=captured['field']*visible_crop
    check();t=time.monotonic()
    if visible.any():
        half_image=cv2.resize(image,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
        eligible_half=_half_visibility(visible_crop,half_image.shape[:2])
        half,proposal_meta=native_field(half_image,captured['metric']*.5,eligible_half,pixel_density=.5,check=check)
        half,classifier_meta=_half_material(half_image,half,captured['metric']*.5,encoder,head,check)
    else:
        half=np.zeros((round(h*.5),round(w*.5)),np.float32);proposal_meta={};classifier_meta={'encoderCalls':0}
    half_seconds=time.monotonic()-t;check()
    merged=merge_accepted_supports(accepted_native,half,source_shape=shape,native_origin=origin,half_origin=origin,visible_source=visible)
    candidate=copy.deepcopy(native)
    def stamp(row):
        key=row['region']+':dry'
        row.update(methodVersion=METHOD,normalizationVersion=NORMALIZATION)
        row['components'].update(samplingSupportVersion=VERSION,dualscaleSupportVersion=VERSION)
        if row['value'] is None:
            if key in candidate['maps']:raise ValueError('NULL_REGION_HAS_MAP')
            return
        mask=masks[key];count=int(((merged.combined>OPTICAL_CUTOFF)&mask).sum())
        if int(mask.sum())!=row['components']['uniqueVisibleSourcePixels']:raise ValueError('ORIGINAL_DENOMINATOR_CHANGED')
        row['value']=100*count/max(1,int(mask.sum()));row['components']['acceptedMaterialSourcePixels']=count
        layer=map_result(merged.combined,mask,row['region'],'dry',payload['photoId'],payload['pose'],shape,1.,'percent-visible-area',1.,(0,0))
        layer.update(method=METHOD,normalizationVersion=NORMALIZATION,nativeScoreSourcePixels=count,displayAggregation='lossless-native-grid',samplingSupportVersion=VERSION)
        candidate['maps'][key]=layer
    for row in candidate['measurements'].values():stamp(row)
    if candidate.get('general') is not None:stamp(candidate['general'])
    candidate['nativeMetadata'].update(normalProductEnabled=False,dualscaleVersion=VERSION,halfProposal=proposal_meta,halfClassifier=classifier_meta,originalQualityAndDenominator=True)
    check()
    return dict(native=native,candidate=candidate,support=merged,visible=visible,profile=dict(native=native_profile,halfSeconds=half_seconds,totalDrySeconds=time.monotonic()-started),halfContract=dict(factor=.5,metric=captured['metric']*.5,sourceFaceSpan=abs(payload['landmarks'][454]['x']-payload['landmarks'][234]['x'])*shape[1]*.5,cropOrigin=list(origin),pixelDensity=.5,originalSourceShape=list(shape)),crop=image,origin=origin)

def analyze_product_candidate(value,base_analyzer,check,*,promoted=False):
    """Explicit dry-only callback seam; no normal selector imports this yet."""
    import hashlib,json
    import product_dryness as P,material_component_features as M
    from skin_measurement_contract import attach_result_receipts
    import psutil
    caller_check=check
    def check():
        caller_check()
        if psutil.virtual_memory().available<400*2**20:raise P.DrynessModelUnavailable('LOCAL_MEMORY_RESERVE')
    started=time.monotonic();check();result=base_analyzer(value);check()
    def other(r):
        return dict(measurements={k:[x for x in v if x['id']!='dry'] for k,v in r['measurements'].items()},maps={k:v for k,v in r['maps'].items() if not k.endswith(':dry')},generalMeasurements=[x for x in r.get('general',{}).get('measurements',[]) if x['id']!='dry'],baseType=r.get('general',{}).get('skinType'),contours=r.get('contours'))
    digest=lambda r:hashlib.sha256(json.dumps(other(r),sort_keys=True).encode()).hexdigest()
    before=digest(result);head,encoder=P.runtime(check);staged=analyze_staging(value,head,encoder,check)
    identity=hashlib.sha256((P.HEAD_SHA+P.ORT_SHA+M.ENCODER_SHA).encode()).hexdigest()
    result=P.replace_dryness(result,staged['candidate'],identity)
    method='appearance-native-dry-3' if promoted else METHOD
    normalization='native-calibrated-dualscale-visible-source-area-v9' if promoted else NORMALIZATION
    sampling='native-half-accepted-source-max-v1' if promoted else VERSION
    owners=[row for rows in result['measurements'].values() for row in rows if row['id']=='dry']+[row for row in result.get('general',{}).get('measurements',[]) if row['id']=='dry']
    for row in owners:
        row.update(methodVersion=method,normalizationVersion=normalization)
        row['components'].pop('nativeAnalysisResize',None)
        row['components'].update(samplingSupportVersion=sampling,analysisScales=[1.,.5],nativeBranchAnalysisResize=False,halfBranchAnalysisResize=True,originalSourceDenominator=True)
    for key,layer in result['maps'].items():
        if key.endswith(':dry'):layer.update(method=method,normalizationVersion=normalization,samplingSupportVersion=sampling)
    after=digest(result)
    if before!=after:raise ValueError('DUALSCALE_NON_DRY_MUTATION')
    result['drynessRuntime'].update(normalProductEnabled=bool(promoted),analysisResize=True,nativeBranchAnalysisResize=False,halfBranchAnalysisResize=True,sourcePhotoOrDisplayResized=False,analysisScales=[dict(factor=1.,analysisResize=False),{**staged['halfContract'],'analysisResize':True}],profile=staged['profile'],fullAnalysisSeconds=time.monotonic()-started,nonDryPreservation=dict(beforeSHA256=before,afterSHA256=after,equal=True,scope='Actual same-call base calculations before/after dry-only replacement; final regional Karma runs later in normal router'),sourceUnion=staged['support'].metadata)
    check();return attach_result_receipts(result)
