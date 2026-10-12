"""Fixed-scale, current-photo contour + fold appearance indices (not tissue volume).
See docs/skin-appearance-indices-20261011.md. Historical contour_geometry is not called here.
"""
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d

UNIT='contour-fold-index-0-100'
# All intensities are 0..1; offsets are face-width-normalized pixels.
CONSTANTS=dict(edgeFloor=.018,edgeCeiling=.12,edgeRef=.04,foldFloor=.012,foldCeiling=.08,
               boundaryRef=.08,contrastCeiling=.14,minimumCoverage=.55,minimumFacePixels=180,
               maxYaw=.65,maxPitch=.22,maxMouthOpening=.10,minEyeAspect=.12)

def tracking_residual(selected,guide_line,width):
    """Quality of tracked displacement; expected anatomical bends are not noise."""
    displacement=np.asarray(selected)-np.asarray(guide_line)
    return float(np.mean(np.linalg.norm(displacement-gaussian_filter1d(displacement,2,axis=0),axis=1)))/(width/320)

def curve_profile(gray,eligible,guide,normal,offsets,width,center_support=None):
    """Track actual image support near an anatomical guide, never draw the guide as evidence."""
    guide=np.asarray(guide,np.float32)
    distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(guide,axis=0),axis=1))]
    if distance[-1]<3:return None
    t=np.linspace(0,distance[-1],64)
    line=np.column_stack([np.interp(t,distance,guide[:,i]) for i in (0,1)])
    offsets=np.asarray(offsets,np.float32)*width/320
    coords=line[:,None,:]+offsets[None,:,None]*normal
    x,y=coords[:,:,0].astype('float32'),coords[:,:,1].astype('float32')
    values=cv2.remap(gray,x,y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
    valid=cv2.remap(eligible.astype('uint8'),x,y,cv2.INTER_NEAREST)>0
    # Symmetric bright/dark/bright valley: color or a monotonic shadow is insufficient.
    values=cv2.GaussianBlur(values,(1,3),0)
    valley=np.minimum(values[:,:-4]-values[:,2:-2],values[:,4:]-values[:,2:-2])
    edge=np.minimum(np.abs(values[:,1:-3]-values[:,2:-2]),np.abs(values[:,3:-1]-values[:,2:-2]))
    usable=valid[:,2:-2]&valid[:,:-4]&valid[:,4:]
    if center_support is not None:
        # Context confirms paired brightness, but the measured fold center must
        # be visible in the same target band that can paint the local map.
        centers=cv2.remap(center_support.astype('uint8'),x,y,cv2.INTER_NEAREST)>0
        usable&=centers[:,2:-2]
        valley=np.where(usable,np.maximum(valley,0),-1)
    else:
        valley=np.where(usable,np.maximum(valley,0),0)
    best=valley.argmax(axis=1);contrast=np.maximum(valley[np.arange(64),best],0)
    selected=coords[np.arange(64),best+2]
    support=contrast>CONSTANTS['foldFloor']
    # Reject disconnected spots, makeup/hair-like sharp long segments and straight wrinkle-only paths.
    run=0;longest=0
    for item in support:
        run=run+1 if item else 0;longest=max(longest,run)
    coverage=float(usable.any(axis=1).mean())
    continuity=longest/64
    curvature=tracking_residual(selected,line,width)
    edges=edge[np.arange(64),best]
    folds=np.clip((contrast-.012)/.08,0,1)
    strength=float(np.mean(folds))
    pairedEdge=float(np.mean(np.clip((edges-.018)/.12,0,1)))
    if center_support is not None and usable.any():
        observed=usable.any(axis=1)
        strength=float(np.mean(folds[observed]))
        pairedEdge=float(np.mean(np.clip((edges-.018)/.12,0,1)[observed]))
    points=selected[support] if continuity>=.20 else np.empty((0,2))
    return dict(strength=strength,edge=pairedEdge,continuity=continuity,coverage=coverage,
                trackingResidual=curvature,trackingQualityVersion='guide-relative-displacement-v1',points=points,tracked=selected,values=folds,edgeValues=np.clip((edges-.018)/.12,0,1),support=support,observedSamples=usable.any(axis=1))

def boundary_support(gray,skin,guide,face_width):
    """Actual boundary tracking and local non-smoothness, independent of the fold detector."""
    guide=np.asarray(guide,np.float32);distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(guide,axis=0),axis=1))]
    if distance[-1]<10:return dict(value=0,coverage=0,points=[])
    t=np.linspace(0,distance[-1],64);line=np.column_stack([np.interp(t,distance,guide[:,i]) for i in (0,1)])
    tangent=np.gradient(line,axis=0);length=np.linalg.norm(tangent,axis=1);normal=np.column_stack([-tangent[:,1],tangent[:,0]])/np.maximum(length[:,None],.001)
    offsets=np.arange(-10,11,dtype=np.float32)*face_width/320
    coords=line[:,None,:]+normal[:,None,:]*offsets[None,:,None]
    values=cv2.remap(gray,coords[:,:,0].astype('float32'),coords[:,:,1].astype('float32'),cv2.INTER_LINEAR)
    visible=cv2.remap(skin.astype('uint8'),coords[:,:,0].astype('float32'),coords[:,:,1].astype('float32'),cv2.INTER_NEAREST)>0
    edges=np.abs(values[:,2:]-values[:,:-2]);edges=np.where(visible[:,1:-1]|visible[:,:-2]|visible[:,2:],edges,0)
    index=edges.argmax(axis=1)+1;tracked=coords[np.arange(64),index];strength=edges[np.arange(64),index-1]
    offset=(tracked-line)*normal;shift=offset.sum(axis=1)/(face_width/320)
    # Remove the expected anatomical guide and its broad smooth perspective curvature.
    local=shift-gaussian_filter1d(shift,8)
    deflection=np.clip((np.abs(local)-1.0)/4,0,1)*np.clip((strength-.04)/.18,0,1)
    coverage=float((visible.any(axis=1)).mean())
    return dict(value=float(deflection.mean()),coverage=coverage,edgeMean=float(strength.mean()),localDeflectionMean=float(np.abs(local).mean()),points=tracked.tolist(),supported=(strength>.04).tolist())

def instant_proxy(gray,eligible,points,region,conditions,scale,origin,source_shape,hair=None,context_skin=None,clipping=None,exposure_skin=None):
    """Returns an index, component metadata, actual pixel evidence, and a failure code."""
    h,w=source_shape[:2]
    p=np.array([[(v['x']*w-origin[0])*scale,(v['y']*h-origin[1])*scale] for v in points],float)
    eye=p[263]-p[33];eye_width=float(np.linalg.norm(eye))
    empty=np.zeros(gray.shape,np.float32)
    formula='contour-fold-target-roi-local-support-v6' if region!='periorbital' else 'contour-fold-local-support-v5'
    fail=lambda code:(None,dict(formulaVersion=formula,**({'samplingSupportVersion':'tracked-center-eligible-v1'} if region=='periorbital' else {})),empty,[],code)
    if region=='forehead':return fail('BROW_FOLD_IS_NOT_LOWER_FACE_SAGGING')
    if eye_width<35:return fail('INSUFFICIENT_NATIVE_DETAIL')
    if abs(conditions.get('yaw',99))>.65 or abs(conditions.get('pitch',99))>.22:return fail('HEAD_ANGLE_UNSUPPORTED')
    horizontal=eye/eye_width;vertical=np.array([-horizontal[1],horizontal[0]])
    if vertical[1]<0:vertical=-vertical
    face=float(abs((p[454]-p[234])@horizontal)/scale)
    if face<180:return fail('INSUFFICIENT_NATIVE_DETAIL')
    mouth_width=max(float(np.linalg.norm(p[61]-p[291])),1)
    opening=float(np.linalg.norm(p[13]-p[14]))/mouth_width
    smile=float(((p[61]+p[291])/2-(p[13]+p[14])/2)@vertical)/mouth_width
    eye_aspects=[float(np.linalg.norm(p[a]-p[b]))/max(float(np.linalg.norm(p[c]-p[d])),1) for a,b,c,d in [(159,145,33,133),(386,374,263,362)]]
    if region in ('rightCheek','leftCheek','chin'):
        if opening>.10 or smile<-.07:return fail('EXPRESSION_OPEN_MOUTH_OR_SMILE')
    elif region in ('periorbital','forehead'):
        if min(eye_aspects)<.12:return fail('SQUINT_OR_EYE_OCCLUSION')
        if region=='periorbital' and smile<-.18:return fail('EXPRESSION_OPEN_MOUTH_OR_SMILE')
    if eligible.sum()<100:return fail('INSUFFICIENT_SKIN_SUPPORT')
    paths=[]
    if region=='periorbital':
        # Anatomical right/left are not display-side aliases.
        # Offsets start at 7 to exclude normal pretarsal lower eyelid margin (<7 px)
        # and stay within anatomical infraorbital bag band (<28 px).
        paths=[('right',[144,145,153,154,133]),('left',[373,374,380,381,362])]
        offsets=np.arange(7,28);direction=vertical
    elif region=='rightCheek':paths=[('right',[98,205,206,216,61]),('lower-right',[61,186,172,136])];offsets=np.arange(-10,11);direction=horizontal
    elif region=='leftCheek':paths=[('left',[327,425,426,436,291]),('lower-left',[291,410,397,365])];offsets=np.arange(-10,11);direction=horizontal
    elif region=='chin':paths=[('lower-right',[61,186,172,136]),('lower-left',[291,410,397,365])];offsets=np.arange(-10,11);direction=horizontal
    elif region=='forehead':
        # Brow-adjacent fold + actual brow boundary support; no copied cheek/jaw metric.
        paths=[('right-brow',[70,63,105,66,107]),('left-brow',[300,293,334,296,336])];offsets=np.arange(-24,-2);direction=vertical
        brow_ratio=np.mean([((p[105]-p[159])@vertical)/eye_width,((p[334]-p[386])@vertical)/eye_width])
        if brow_ratio<-.30:return fail('RAISED_BROW')
    else:return fail('ANATOMY_NOT_APPLICABLE')
    if region in ('rightCheek','leftCheek','chin'):
        target_corridor=np.zeros(gray.shape,np.uint8)
        thickness=max(1,int(np.ceil(21*face*scale/320)))
        for _,indices in paths:cv2.polylines(target_corridor,[np.rint(p[indices]).astype(np.int32)],False,1,thickness)
        jaw_indices={'rightCheek':[132,58,172,136,150],'leftCheek':[361,288,397,365,379],'chin':[172,136,150,152,379,365,397]}[region]
        cv2.polylines(target_corridor,[np.rint(p[jaw_indices]).astype(np.int32)],False,1,thickness)
        eligible=eligible&(target_corridor>0)
        if eligible.sum()<100:return fail('INSUFFICIENT_SKIN_SUPPORT')
    smooth=cv2.GaussianBlur(gray,(0,0),8)
    ys,xs=np.where(eligible)
    # Fit the change across the observed skin area, not an extrapolation across
    # the full photograph from a tiny regional mask.
    A=np.column_stack([(xs-xs.min())/max(np.ptp(xs),1),(ys-ys.min())/max(np.ptp(ys),1),np.ones(len(xs))])
    slope=np.linalg.lstsq(A,smooth[eligible],rcond=None)[0]
    shadow_threshold=.75 if region=='periorbital' else .55
    if np.linalg.norm(slope[:2])>shadow_threshold:return fail('HARD_DIRECTIONAL_SHADOW')
    native_width=face*scale
    skin=context_skin if context_skin is not None else eligible
    if hair is not None and np.mean(hair[eligible])>.22:return fail('HAIR_OR_SHARP_LINE_CONFOUNDER')
    if region=='periorbital':
        # Opaque, long high-contrast straight supports are possible spectacles
        # or cosmetic borders, not enough evidence for infraorbital volume.
        dark=((gray<.18)&eligible).astype('uint8')*255
        frame=cv2.HoughLinesP(dark,1,np.pi/180,20,minLineLength=max(15,int(eye_width*.30)),maxLineGap=3)
        if frame is not None:return fail('EYEWEAR_OR_COSMETIC_EDGE')
    # Only the actual anatomical sampling corridors participate in exposure
    # quality. Clipped upper-cheek pixels cannot reject a visible jaw corridor.
    exposure_masks={};exposure_corridors={}
    def exposure(guide,offsets):
        corridor=np.zeros(gray.shape,np.uint8)
        thickness=max(1,int(np.ceil(2*max(abs(float(v)) for v in offsets)*native_width/320+1)))
        cv2.polylines(corridor,[np.rint(guide).astype(np.int32)],False,1,thickness)
        observed=(corridor>0)&(exposure_skin if exposure_skin is not None else eligible)
        fraction=float(clipping[observed].mean()) if clipping is not None and observed.any() else 0.
        receipt=dict(clippedFraction=fraction,observedPixels=int(observed.sum()),maximumClippedFraction=.03)
        exposure_masks[id(receipt)]=observed
        exposure_corridors[id(receipt)]=corridor>0
        return receipt
    boundary=None;boundary_exposure=None
    if region in ('rightCheek','leftCheek','chin'):
        jaw={'rightCheek':[132,58,172,136,150],'leftCheek':[361,288,397,365,379],'chin':[172,136,150,152,379,365,397]}[region]
        boundary=boundary_support(gray,context_skin if context_skin is not None else eligible,p[jaw],native_width)
        boundary_exposure=exposure(p[jaw],np.arange(-10,11))
        boundary['exposure']=boundary_exposure
    elif region=='forehead':
        # Separate actual brow-boundary deviations from the above-brow skin fold signal.
        boundaries=[boundary_support(gray,context_skin if context_skin is not None else eligible,p[ii],native_width) for ii in ([70,63,105,66,107],[300,293,334,296,336])]
        boundary=dict(value=float(np.mean([v['value'] for v in boundaries])),coverage=float(np.mean([v['coverage'] for v in boundaries])),sides=boundaries)
    sides=[];evidence=[];signal=empty.copy()
    for side,indices in paths:
        profile=curve_profile(gray,skin,p[indices],direction,offsets,native_width,center_support=eligible) if region=='periorbital' else curve_profile(gray,skin,p[indices],direction,offsets,native_width)
        if profile is None:continue
        q=profile;local_exposure=exposure(p[indices],offsets)
        # Joint support: no contour/paired-edge => no fold-derived sag/bag signal.
        # Normalize confirmation factors (edge and boundary) against their expected full-support reference scales
        # so confirmation gates don't over-dampen visible anatomical folds into sub-percent fractions (< 0.5% => 0% UI).
        edge_gate = np.minimum(1.0, np.sqrt(q['edgeValues'] / 0.04))
        if region == 'periorbital':
            continuity_gate = 0.0 if q['continuity'] < 0.20 else min(1.0, q['continuity'] / 0.6)
        else:
            continuity_gate = min(1.0, q['continuity'] / 0.6)
        if boundary is not None:
            boundary_gate = min(1.0, np.sqrt(max(0.0, boundary['value']) / 0.08))
            joint = float(np.mean(q['values'] * edge_gate)) * continuity_gate * boundary_gate
        else:
            visible=q.get('observedSamples',np.ones(len(q['values']),bool))
            joint = float(np.mean((q['values'] * np.sqrt(q['edgeValues']))[visible])) * continuity_gate if visible.any() else 0.
        limitation=None
        if local_exposure['clippedFraction']>.03 or boundary_exposure is not None and boundary_exposure['clippedFraction']>.03:limitation='GLARE_OR_EXPOSURE'
        elif q['coverage']<.55 or boundary is not None and boundary['coverage']<.55:limitation='ANATOMICAL_BAND_NOT_VISIBLE'
        elif q['trackingResidual']>(2.8 if region=='periorbital' else 2.5):limitation='CONTOUR_TRACKING_UNSTABLE'
        side_value=None if limitation else float(np.clip(joint*100,0,100))
        sides.append(dict(side=side,value=side_value,fold=q['strength'],pairedEdge=q['edge'],continuity=q['continuity'],coverage=q['coverage'],trackingResidual=q['trackingResidual'],trackingQualityVersion=q['trackingQualityVersion'],exposure=local_exposure,limitationCode=limitation))
        if side_value is not None and side_value>0:
            pts=q['tracked']
            # Only measured source coordinates, never synthesize hidden skin surfaces.
            line=[]
            if boundary is not None:
                local_values = q['values'] * edge_gate * continuity_gate * boundary_gate
            else:
                local_values = q['values'] * np.sqrt(q['edgeValues']) * continuity_gate
            for xy,supported,intensity in zip(pts,q['support'],local_values):
                x,y=np.rint(xy).astype(int)
                if supported and 0<=x<gray.shape[1] and 0<=y<gray.shape[0] and eligible[y,x]:
                    cv2.circle(signal,(x,y),2,float(intensity),-1)
                    line.append(dict(x=float((xy[0]/scale+origin[0])/w),y=float((xy[1]/scale+origin[1])/h)))
                elif line:
                    if len(line)>1:evidence.append(line)
                    line=[]
            if len(line)>1:evidence.append(line)
    valid=[v['value'] for v in sides if v['value'] is not None]
    if valid and any(v>0 for v in valid) and boundary is not None:
        boundaries=boundary.get('sides',[boundary])
        for b in boundaries:
            line=[]
            for xy,supported in zip(b.pop('points',[]),b.pop('supported',[])):
                x,y=np.rint(xy).astype(int)
                if supported and 0<=x<gray.shape[1] and 0<=y<gray.shape[0] and eligible[y,x]:
                    line.append(dict(x=float((xy[0]/scale+origin[0])/w),y=float((xy[1]/scale+origin[1])/h)))
                elif line:
                    if len(line)>1:evidence.append(line)
                    line=[]
            if len(line)>1:evidence.append(line)
    elif boundary is not None:
        for b in boundary.get('sides',[boundary]):b.pop('points',None);b.pop('supported',None)
    measured_roi=np.zeros(gray.shape,bool)
    for side in sides:
        if side['value'] is not None:measured_roi|=exposure_masks[id(side['exposure'])]
    if valid and boundary_exposure is not None:measured_roi|=exposure_masks[id(boundary_exposure)]
    measured_roi&=eligible
    measurement_roi=dict(scope='measured-anatomical-sampling-corridors',analysisPixels=int(measured_roi.sum()),sourcePixels=float(measured_roi.sum()/scale**2),anatomicalSourcePixels=float(np.logical_or.reduce(list(exposure_corridors.values())).sum()/scale**2) if exposure_corridors else 0.,sourceFacePixels=face,unknownSides=[side['side'] for side in sides if side['value'] is None])
    components=dict(formulaVersion=formula,measurementROI=measurement_roi,sides=sides,fixedConstants=CONSTANTS,
                    indexAggregation='mean of measured local fold * min(1, sqrt(pairedEdge/0.04)), times continuity/0.6 and min(1, sqrt(jaw boundary/0.08)) where applicable' if region!='periorbital' else 'mean of measured local fold * sqrt(local paired edge), times supported continuity (minimum 0.20)',
                    localMapMeaning='measured local support intensity; no confidence or pixel disease severity',
                    meaning='visible-supported-contour-fold; not probability, volume or clinical severity',boundary=boundary,
                    weights=dict(fold=1,pairedEdgeRef=.04,continuityRef=.60,boundaryRef=.08) if region!='periorbital' else dict(fold=1,pairedEdge=.5,continuity=1,boundary=.5),
                    rollRadians=float(np.arctan2(horizontal[1],horizontal[0])),normalization='2D eye axis and face width; no z/depth',
                    mouthOpening=opening,eyeAspects=eye_aspects,shadowPlaneSlope=slope[:2].tolist())
    if region=='periorbital':components['samplingSupportVersion']='tracked-center-eligible-v1'
    if not valid:return None,components,empty,[],next((v['limitationCode'] for v in sides if v.get('limitationCode')), 'ANATOMICAL_BAND_NOT_VISIBLE')
    signal*=eligible
    # Mean only measured local subregions; missing side stays null, never copied.
    return float(np.mean(valid)),components,signal,evidence,None
