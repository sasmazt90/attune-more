"""Fixed-scale, current-photo contour + fold appearance indices (not tissue volume).
See docs/skin-appearance-indices-20261011.md. Historical contour_geometry is not called here.
"""
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d
from skin_product_contract import sag_appearance_components

UNIT='contour-fold-index-0-100'
# All intensities are 0..1; offsets are face-width-normalized pixels.
CONSTANTS=dict(edgeFloor=.018,edgeCeiling=.12,edgeRef=.04,foldFloor=.012,foldCeiling=.08,
               boundaryRef=.08,contrastCeiling=.14,minimumCoverage=.55,minimumFacePixels=180,
               maxYaw=.65,maxPitch=.22,maxMouthOpening=.10,minEyeAspect=.12)

def tracking_residual(selected,guide_line,width):
    """Quality of tracked displacement; expected anatomical bends are not noise."""
    displacement=np.asarray(selected)-np.asarray(guide_line)
    return float(np.mean(np.linalg.norm(displacement-gaussian_filter1d(displacement,2,axis=0),axis=1)))/(width/320)

def observed_fold_tracking(selected,guide_line,width,observed,support):
    """Residual on observed contiguous fold runs; never smooth across a gap.

    Five samples cover the existing sigma=2 smoothing scale (2*sigma+1).
    A short run cannot establish tracking quality. A visible corridor without
    any fold is measured zero, while fragmented fold evidence stays unresolved.
    """
    finite=np.isfinite(selected).all(axis=1)&np.isfinite(guide_line).all(axis=1)
    fold=np.asarray(observed,bool)&np.asarray(support,bool)&finite
    edges=np.diff(np.r_[False,fold,False].astype(int))
    runs=[(int(a),int(b)) for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1))]
    accepted=np.zeros(len(fold),bool);errors=[];segments=[]
    for a,b in runs:
        if b-a<5:continue
        accepted[a:b]=True
        displacement=selected[a:b]-guide_line[a:b]
        local=np.linalg.norm(displacement-gaussian_filter1d(displacement,2,axis=0),axis=1)/(width/320)
        errors.extend(local.tolist());segments.append(dict(start=a,endExclusive=b,residual=float(local.mean())))
    status='observed-fold-runs' if errors else 'fragmented-fold-support' if fold.any() else 'no-fold-observed' if np.asarray(observed).any() else 'unobserved'
    return dict(residual=float(np.mean(errors)) if errors else None,accepted=accepted,status=status,
                rawFoldSamples=int(fold.sum()),trackedFoldSamples=int(accepted.sum()),segments=segments,minimumRunSamples=5)

def curve_profile(gray,eligible,guide,normal,offsets,width,center_support=None,observed_fold_runs=False):
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
    tracking=observed_fold_tracking(selected,line,width,usable.any(axis=1),support) if observed_fold_runs else None
    curvature=tracking['residual'] if tracking is not None else tracking_residual(selected,line,width)
    edges=edge[np.arange(64),best]
    folds=np.clip((contrast-.012)/.08,0,1)
    if tracking is not None:
        support=tracking['accepted']
        folds*=support
        # An invalid argmax is not a source coordinate or a measured sample.
        selected=selected.copy();selected[~usable.any(axis=1)]=np.nan
        edges=np.where(support,edges,0)
    strength=float(np.mean(folds))
    pairedEdge=float(np.mean(np.clip((edges-.018)/.12,0,1)))
    if center_support is not None and usable.any():
        observed=usable.any(axis=1)
        strength=float(np.mean(folds[observed]))
        pairedEdge=float(np.mean(np.clip((edges-.018)/.12,0,1)[observed]))
    points=selected[support] if continuity>=.20 else np.empty((0,2))
    result=dict(strength=strength,edge=pairedEdge,continuity=continuity,coverage=coverage,
                trackingResidual=curvature,trackingQualityVersion='observed-fold-runs-v2' if tracking is not None else 'guide-relative-displacement-v1',points=points,tracked=selected,values=folds,edgeValues=np.clip((edges-.018)/.12,0,1),support=support,observedSamples=usable.any(axis=1))
    if tracking is not None:result.update(trackingStatus=tracking['status'],trackingSegments=tracking['segments'],rawFoldSamples=tracking['rawFoldSamples'],trackedFoldSamples=tracking['trackedFoldSamples'],minimumTrackingRunSamples=tracking['minimumRunSamples'])
    return result

def boundary_support(gray,skin,guide,face_width,contour_support=None):
    """Actual boundary tracking and local non-smoothness, independent of the fold detector."""
    guide=np.asarray(guide,np.float32);distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(guide,axis=0),axis=1))]
    if distance[-1]<10:return dict(value=0,coverage=0,points=[])
    t=np.linspace(0,distance[-1],64);line=np.column_stack([np.interp(t,distance,guide[:,i]) for i in (0,1)])
    tangent=np.gradient(line,axis=0);length=np.linalg.norm(tangent,axis=1);normal=np.column_stack([-tangent[:,1],tangent[:,0]])/np.maximum(length[:,None],.001)
    offsets=np.arange(-10,11,dtype=np.float32)*face_width/320
    coords=line[:,None,:]+normal[:,None,:]*offsets[None,:,None]
    values=cv2.remap(gray,coords[:,:,0].astype('float32'),coords[:,:,1].astype('float32'),cv2.INTER_LINEAR)
    visible=cv2.remap(skin.astype('uint8'),coords[:,:,0].astype('float32'),coords[:,:,1].astype('float32'),cv2.INTER_NEAREST)>0
    edge_eligible=visible[:,1:-1]|visible[:,:-2]|visible[:,2:]
    if contour_support is not None:
        geometry=cv2.remap(contour_support.astype('uint8'),coords[:,:,0].astype('float32'),coords[:,:,1].astype('float32'),cv2.INTER_NEAREST)>0
        # Interior pores/creases are not an independent jaw silhouette. Require
        # the actual sampled image edge to cross the face contour support.
        edge_eligible&=geometry[:,:-2]!=geometry[:,2:]
    edges=np.abs(values[:,2:]-values[:,:-2]);edges=np.where(edge_eligible,edges,0)
    index=edges.argmax(axis=1)+1;tracked=coords[np.arange(64),index];strength=edges[np.arange(64),index-1]
    offset=(tracked-line)*normal;shift=offset.sum(axis=1)/(face_width/320)
    # Remove the expected anatomical guide and its broad smooth perspective curvature.
    local=shift-gaussian_filter1d(shift,8)
    deflection=np.clip((np.abs(local)-1.0)/4,0,1)*np.clip((strength-.04)/.18,0,1)
    coverage=float(edge_eligible.any(axis=1).mean()) if contour_support is not None else float(visible.any(axis=1).mean())
    return dict(value=float(deflection.mean()),coverage=coverage,edgeMean=float(strength.mean()),localDeflectionMean=float(np.abs(local).mean()),points=tracked.tolist(),supported=(strength>.04).tolist(),**({'trackingSupportVersion':'anatomical-silhouette-crossing-v1','_localSupport':deflection.tolist()} if contour_support is not None else {}))

def instant_proxy(gray,eligible,points,region,conditions,scale,origin,source_shape,hair=None,context_skin=None,clipping=None,exposure_skin=None,boundary_geometry=None,expression_observation=None,photo_id=None,capture_pose=None):
    """Returns an index, component metadata, actual pixel evidence, and a failure code."""
    h,w=source_shape[:2]
    p=np.array([[(v['x']*w-origin[0])*scale,(v['y']*h-origin[1])*scale] for v in points],float)
    eye=p[263]-p[33];eye_width=float(np.linalg.norm(eye))
    empty=np.zeros(gray.shape,np.float32)
    formula='contour-fold-lower-chin-observed-runs-v9' if region=='chin' else 'contour-fold-local-support-v5' if region=='periorbital' else 'contour-fold-visible-region-unique-centers-v7'
    if region in ('rightCheek','leftCheek','chin'):formula+='-expression-v3-observed-pose'
    def failure_components():
        components=dict(formulaVersion=formula,**({'samplingSupportVersion':'tracked-center-eligible-v1'} if region=='periorbital' else {}))
        return components if region=='periorbital' else sag_appearance_components(components)
    fail=lambda code:(None,failure_components(),empty,[],code)
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
        from skin_expression import reason,pose_reason
        if capture_pose is not None:
            invalid_pose=pose_reason(capture_pose,conditions)
            if invalid_pose:return fail(invalid_pose)
        expression_reason=reason(expression_observation,photo_id,opening,smile,mouth_width/max(float(abs((p[454]-p[234])@horizontal)),1))
        if expression_reason:return fail(expression_reason)
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
    elif region=='rightCheek':paths=[('right',[100,142,203,206]),('lower-right',[206,212,202])];offsets=np.arange(-10,11);direction=horizontal
    elif region=='leftCheek':paths=[('left',[329,371,423,426]),('lower-left',[426,432,422])];offsets=np.arange(-10,11);direction=horizontal
    elif region=='chin':
        # The ordinary mentolabial crease is not a lower-jaw descent target.
        # Track the lower interior chin row, separately from both mouth-side
        # cheek folds. Actual jaw-boundary confirmation remains mandatory.
        paths=[('lower-chin',[170,208,199,428,395])];offsets=np.arange(-10,11);direction=vertical
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
        if region=='chin' and boundary_geometry is None:
            # Direct/offline callers must use the same v8 contour contract as
            # the normal API, rather than silently falling back to a v7 gate.
            oval=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
            boundary_geometry=np.zeros(gray.shape,np.uint8)
            cv2.fillPoly(boundary_geometry,[p[oval].astype(np.int32)],1)
        jaw={'rightCheek':[132,58,172,136,150],'leftCheek':[361,288,397,365,379],'chin':[172,136,150,152,379,365,397]}[region]
        boundary=boundary_support(gray,context_skin if context_skin is not None else eligible,p[jaw],native_width,boundary_geometry)
        boundary_exposure=exposure(p[jaw],np.arange(-10,11))
        boundary['exposure']=boundary_exposure
    elif region=='forehead':
        # Separate actual brow-boundary deviations from the above-brow skin fold signal.
        boundaries=[boundary_support(gray,context_skin if context_skin is not None else eligible,p[ii],native_width) for ii in ([70,63,105,66,107],[300,293,334,296,336])]
        boundary=dict(value=float(np.mean([v['value'] for v in boundaries])),coverage=float(np.mean([v['coverage'] for v in boundaries])),sides=boundaries)
    sides=[];evidence=[];signal=empty.copy();sampling_centers={}
    for side,indices in paths:
        profile=curve_profile(gray,skin,p[indices],direction,offsets,native_width,center_support=eligible,**({'observed_fold_runs':True} if region=='chin' else {}))
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
            if boundary.get('_localSupport') is not None:
                boundary_points=np.asarray(boundary['points'],np.float32)
                finite=np.isfinite(q['tracked']).all(axis=1)
                nearest=np.zeros(len(q['tracked']),int)
                nearest[finite]=np.linalg.norm(q['tracked'][finite,None,:]-boundary_points[None,:,:],axis=2).argmin(axis=1)
                boundary_gate=np.where(finite,np.minimum(1.,np.sqrt(np.asarray(boundary['_localSupport'])[nearest]/.08)),0.)
                boundary['foldConfirmationVersion']='nearest-contour-local-support-v1'
            visible=q['observedSamples']
            if boundary.get('_localSupport') is not None:
                joint = float(np.mean((q['values'] * edge_gate * boundary_gate)[visible])) * continuity_gate if visible.any() else 0.
            else:
                joint = float(np.mean((q['values'] * edge_gate)[visible])) * continuity_gate * boundary_gate if visible.any() else 0.
        else:
            visible=q.get('observedSamples',np.ones(len(q['values']),bool))
            joint = float(np.mean((q['values'] * np.sqrt(q['edgeValues']))[visible])) * continuity_gate if visible.any() else 0.
        limitation=None
        if local_exposure['clippedFraction']>.03 or boundary_exposure is not None and boundary_exposure['clippedFraction']>.03:limitation='GLARE_OR_EXPOSURE'
        elif q['coverage']<.55 or boundary is not None and boundary['coverage']<.55:limitation='ANATOMICAL_BAND_NOT_VISIBLE'
        elif q.get('trackingStatus')=='fragmented-fold-support':limitation='CONTOUR_TRACKING_INSUFFICIENT_SUPPORT'
        elif q['trackingResidual'] is not None and q['trackingResidual']>(2.8 if region=='periorbital' else 2.5):limitation='CONTOUR_TRACKING_UNSTABLE'
        side_value=None if limitation else float(np.clip(joint*100,0,100))
        sides.append(dict(side=side,value=side_value,fold=q['strength'],pairedEdge=q['edge'],continuity=q['continuity'],coverage=q['coverage'],trackingResidual=q['trackingResidual'],trackingQualityVersion=q['trackingQualityVersion'],exposure=local_exposure,limitationCode=limitation))
        if region=='chin':sides[-1].update({k:q[k] for k in ['trackingStatus','trackingSegments','rawFoldSamples','trackedFoldSamples','minimumTrackingRunSamples'] if k in q})
        if side_value is not None and region!='periorbital':
            local_values=q['values']*edge_gate*continuity_gate*boundary_gate
            for xy,observed,intensity in zip(q['tracked'],q['observedSamples'],local_values):
                if not observed or not np.isfinite(xy).all():continue
                x,y=np.rint(xy).astype(int)
                if observed and 0<=x<gray.shape[1] and 0<=y<gray.shape[0] and eligible[y,x]:
                    sampling_centers[(int(x),int(y))]=max(sampling_centers.get((int(x),int(y)),0.),float(intensity))
        if side_value is not None and side_value>0:
            pts=q['tracked']
            # Only measured source coordinates, never synthesize hidden skin surfaces.
            line=[]
            if boundary is not None:
                local_values = q['values'] * edge_gate * continuity_gate * boundary_gate
            else:
                local_values = q['values'] * np.sqrt(q['edgeValues']) * continuity_gate
            for xy,supported,intensity in zip(pts,q['support'],local_values):
                if not np.isfinite(xy).all():
                    if len(line)>1:evidence.append(line)
                    line=[];continue
                x,y=np.rint(xy).astype(int)
                if supported and 0<=x<gray.shape[1] and 0<=y<gray.shape[0] and eligible[y,x]:
                    if region=='periorbital':cv2.circle(signal,(x,y),2,float(intensity),-1)
                    else:
                        local=np.zeros_like(signal);cv2.circle(local,(x,y),2,float(intensity),-1);np.maximum(signal,local,out=signal)
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
    if boundary is not None:boundary.pop('_localSupport',None)
    measurement_roi=dict(scope='measured-anatomical-sampling-corridors',analysisPixels=int(measured_roi.sum()),sourcePixels=float(measured_roi.sum()/scale**2),anatomicalSourcePixels=float(np.logical_or.reduce(list(exposure_corridors.values())).sum()/scale**2) if exposure_corridors else 0.,sourceFacePixels=face,unknownSides=[side['side'] for side in sides if side['value'] is None])
    components=dict(formulaVersion=formula,measurementROI=measurement_roi,sides=sides,fixedConstants=CONSTANTS,
                    indexAggregation='mean of measured local fold * min(1, sqrt(pairedEdge/0.04)), times continuity/0.6 and min(1, sqrt(nearest supported jaw boundary/0.08)) where applicable' if region=='chin' else 'mean of measured local fold * min(1, sqrt(pairedEdge/0.04)), times continuity/0.6 and min(1, sqrt(jaw boundary/0.08)) where applicable' if region!='periorbital' else 'mean of measured local fold * sqrt(local paired edge), times supported continuity (minimum 0.20)',
                    localMapMeaning='measured local support intensity; no confidence or pixel disease severity',
                    meaning='visible-supported-contour-fold; not probability, volume, elasticity or clinical severity',boundary=boundary,
                    weights=dict(fold=1,pairedEdgeRef=.04,continuityRef=.60,boundaryRef=.08) if region!='periorbital' else dict(fold=1,pairedEdge=.5,continuity=1,boundary=.5),
                    rollRadians=float(np.arctan2(horizontal[1],horizontal[0])),normalization='2D eye axis and face width; no z/depth',
                    mouthOpening=opening,eyeAspects=eye_aspects,shadowPlaneSlope=slope[:2].tolist())
    if region=='periorbital':components['samplingSupportVersion']='tracked-center-eligible-v1'
    else:
        components['expressionGateVersion']='source-bound-lower-face-expression-v3-observed-pose'
        components.update(samplingSupportVersion='lower-chin-observed-fold-runs-unique-centers-v9' if region=='chin' else 'visible-region-unique-centers-v7',uniqueObservedCenters=len(sampling_centers),overlapCountedOnce=True,partialCoverage=any(side['value'] is None for side in sides),appearanceSemantics='visible-lower-face-contour-fold-appearance-v1',clinicalSeverity=False,elasticity=False,comparisonMode='same-person-compatible-capture-only')
        # Ephemeral raster/coordinates are consumed by the overview aggregator;
        # appearance_analysis removes them before returning or storing JSON.
        components['_samplingCenters']=[[x,y,v] for (x,y),v in sampling_centers.items()]
        components['_measuredSupport']=measured_roi
    if not valid:return None,components,empty,[],next((v['limitationCode'] for v in sides if v.get('limitationCode')), 'ANATOMICAL_BAND_NOT_VISIBLE')
    signal*=eligible
    # Mean only measured local subregions; missing side stays null, never copied.
    if region!='periorbital':
        if not sampling_centers:return None,components,empty,[],'ANATOMICAL_BAND_NOT_VISIBLE'
        return float(100*np.mean(list(sampling_centers.values()))),components,signal,evidence,None
    return float(np.mean(valid)),components,signal,evidence,None
