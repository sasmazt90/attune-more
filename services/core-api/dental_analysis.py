"""Visible dental candidates only; local CV + a hash-checked trained ONNX."""
import copy,hashlib,json
from pathlib import Path
import cv2,numpy as np
from scipy import ndimage
from skimage.segmentation import watershed
from appearance_analysis import decode_photo,row
ROOT=Path(__file__).resolve().parent
_session=None
_manifest=None
_model_runtime={}
_model_identity=None
ADULT_POLICY='adult-permanent-D-only-v1'


class DentalModelError(RuntimeError):
    """Technical model failure; never converts to an empty valid detection."""


def adult_product_result(result):
    """Product population scope AFTER raw model decode/NMS/source mapping.
    Raw D/d outputs and model identity stay intact; historical records never
    pass through this new-analysis boundary. No d-to-D reclassification.
    """
    result=copy.deepcopy(result)
    for view in result['views']:
        metric=view['caries'];candidates=metric.get('candidates')
        if not isinstance(candidates,list) or any(not isinstance(c,dict) or c.get('classCode') not in ('D','d') for c in candidates):raise DentalModelError('INVALID_PRODUCT_CANDIDATES')
        valid=metric.get('quality')=='valid'
        if valid and (view.get('quality',{}).get('valid') is not True or type(metric.get('value')) is not int or metric['value']!=len(candidates)):raise DentalModelError('INVALID_PRODUCT_CANDIDATE_COUNT')
        if not valid and metric.get('value') is not None:raise DentalModelError('INVALID_PRODUCT_UNAVAILABLE_VALUE')
        metric['candidates']=[c for c in candidates if c['classCode']=='D'] if valid else []
        metric['value']=len(metric['candidates']) if valid else None
        method=metric.get('detectorMethodVersion',metric['methodVersion'])
        metric.update(detectorMethodVersion=method,methodVersion=method+'+'+ADULT_POLICY,candidatePolicyVersion=ADULT_POLICY,includedClassCodes=['D'])
    method=result.get('sourceMethodVersion',result['methodVersion'])
    result.update(sourceMethodVersion=method,methodVersion=method+'+'+ADULT_POLICY,candidatePolicyVersion=ADULT_POLICY)
    return result


def anatomical_mouth_width(points,shape):
    """Mouth corner distance including landmark depth (z is in image-width units)."""
    a,b=points[78],points[308]
    return float(np.sqrt(((a['x']-b['x'])*shape[1])**2+((a['y']-b['y'])*shape[0])**2+((a.get('z',0)-b.get('z',0))*shape[1])**2))


def mouth_geometry(points,shape):
    if len(points)<468:raise ValueError('LANDMARKS_MISSING')
    p=np.array([[v['x']*shape[1],v['y']*shape[0]] for v in points],np.float32)
    if not np.isfinite(p).all():raise ValueError('INVALID_LANDMARKS')
    indices=[78,81,82,13,312,311,308,402,317,14,87,178]
    polygon=p[indices].astype(np.int32);mask=np.zeros(shape[:2],np.uint8);cv2.fillPoly(mask,[polygon],255)
    width=float(np.linalg.norm(p[78]-p[308]));opening=float(np.linalg.norm(p[13]-p[14])/max(width,1))
    return mask>0,width,opening,p


def dental_pixels(image,mouth,native_capture=False):
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV).astype(np.float32)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    # White/ivory within actual inner mouth; never equate open lips with teeth.
    b,g,r=[image[:,:,i].astype(np.float32) for i in range(3)]
    pink=(hsv[:,:,1]>60)&(r>g*1.10)&(g-b<np.maximum.reduce([r,g,b])*.08)
    tooth=mouth&(hsv[:,:,1]<( .58*255 if native_capture else 100))&(hsv[:,:,2]>100)&(gray>90)
    if native_capture:tooth&=(r<g*1.25)&(g>b*.85)&~pink
    tooth=cv2.morphologyEx(tooth.astype(np.uint8),cv2.MORPH_OPEN,np.ones((3,3),np.uint8))>0
    glare=tooth&(hsv[:,:,2]>=250)&(hsv[:,:,1]<20)
    tooth&=~cv2.dilate(glare.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
    gum=mouth&(hsv[:,:,1]>60)&(image[:,:,2]>image[:,:,1]*1.10)&(gray>40)
    if native_capture:gum&=pink # Yellow/ivory enamel cannot also be tongue support.
    tongue=cv2.erode(gum.astype(np.uint8),np.ones((7,7),np.uint8))>0
    return tooth,glare,gum,tongue,gray


# Same values as DENTAL_GATES in apps/vehicle-app/src/utils/dentalCapture.ts.
# Scale is gated once by mouth width; enamel amount is relative to it, and a
# small lip gap is enough when the enamel-visibility gate itself passes.
DENTAL_GATES={'minLipOpening':.06,'minMouthWidthPx':65,'minEnamelPerMouthWidth2':.008,'minEnamelColumnFraction':.30,'version':'vehicle-capture-v2'}
BITE_CONTACT={'centralHalfWidth':.25,'maxGapRatio':.04,'minContactColumns':.60,'minEnamelColumns':.50,'version':'incisal-contact-v1'}


def incisal_contact(tooth,mouth,p,width):
    """Visible upper/lower incisal contact in the central mouth columns.

    Lip aperture is not a bite signal: a wide bite smile parts the lips and a
    relaxed open mouth can have a small lip ratio. A natural-bite column has
    enamel on both sides of the inner-lip midline and no vertical non-enamel
    run between enamel pixels longer than maxGapRatio * mouth width.
    """
    h,w=mouth.shape;center=(p[13]+p[14])/2;axis=p[308]-p[78];slope=float(axis[1]/axis[0]) if abs(axis[0])>1e-6 else 0.
    half=width*BITE_CONTACT['centralHalfWidth'];limit=width*BITE_CONTACT['maxGapRatio']
    total=enamel=contact=0;gaps=[]
    for x in range(max(0,int(np.floor(center[0]-half))),min(w,int(np.ceil(center[0]+half))+1)):
        rows=np.flatnonzero(mouth[:,x])
        if len(rows)<3:continue
        total+=1;y0=rows.min();column=tooth[y0:rows.max()+1,x];idx=np.flatnonzero(column)
        if len(idx)<2:continue
        enamel+=1;midline=center[1]+(x-center[0])*slope-y0
        gap=int(np.max(np.diff(idx))-1);gaps.append(gap/width)
        if idx[0]<midline<idx[-1] and gap<=limit:contact+=1
    enamel_fraction=enamel/max(total,1);contact_fraction=contact/max(enamel,1)
    return dict(version=BITE_CONTACT['version'],centralColumns=total,enamelColumnFraction=enamel_fraction,contactColumnFraction=contact_fraction,
                medianIncisalGapRatio=float(np.median(gaps)) if gaps else None,
                confirmed=bool(total and enamel_fraction>=BITE_CONTACT['minEnamelColumns'] and contact_fraction>=BITE_CONTACT['minContactColumns']))


def gate_enamel(image,mouth):
    """Per-pixel enamel classification of the live capture gate (dentalCapture.ts),
    without the 3x3 opening used for analysis masks: at in-car image scales a
    thin-lip enamel band is only a few pixels high and the opening erased it,
    so the backend re-validation rejected frames the client had accepted."""
    f=image.astype(np.float32);b,g,r=f[:,:,0],f[:,:,1],f[:,:,2]
    v=np.maximum(np.maximum(r,g),b);sat=np.where(v>0,(v-np.minimum(np.minimum(r,g),b))/np.maximum(v,1),0)
    lum=.299*r+.587*g+.114*b;pink=(sat>60/255)&(r>g*1.10)&(g-b<v*.08)
    enamel=mouth&(v>100)&(sat<.58)&(lum>90)&(r<g*1.25)&(g>b*.85)&~pink
    return enamel&~((v>=250)&(sat<.08))


def dental_quality(image,points,bite=False,pose_check=True):
    mouth,width,opening,p=mouth_geometry(points,image.shape)
    tooth,glare,gum,tongue,gray=dental_pixels(image,mouth,native_capture=True)
    visible=gate_enamel(image,mouth)
    count=int(visible.sum());area=int(mouth.sum());area_fraction=count/max(area,1)
    columns=int(np.sum(visible.sum(axis=0)>=max(2,width*.015)));fraction=columns/max(width,1)
    # The same native inner-mouth neighbourhood as the live capture gate.
    # Rectangular crop/background edges must not supply artificial sharpness.
    interior=cv2.erode(mouth.astype(np.uint8),np.array([[0,1,0],[1,1,1],[0,1,0]],np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0)>0
    lap=cv2.Laplacian(gray,cv2.CV_32F)
    sharp=float(np.mean(lap[interior]**2)) if interior.any() else 0
    light=float(gray[mouth].mean()) if area else 0
    reasons=[];contact=incisal_contact(visible,mouth,p,width)
    anatomical=anatomical_mouth_width(points,image.shape)
    if anatomical<DENTAL_GATES['minMouthWidthPx']:reasons.append('INSUFFICIENT_TOOTH_DETAIL')
    if pose_check and not bite and opening<DENTAL_GATES['minLipOpening']:reasons.append('MOUTH_CLOSED')
    if pose_check and bite and not contact['confirmed']:reasons.append('NATURAL_BITE_REQUIRED')
    if count<width*width*DENTAL_GATES['minEnamelPerMouthWidth2'] or fraction<DENTAL_GATES['minEnamelColumnFraction']:reasons.append('TEETH_NOT_VISIBLE')
    if light<45 or light>230:reasons.append('LIGHT_INVALID')
    if sharp<12:reasons.append('BLURRY')
    if glare.sum()/max(count+glare.sum(),1)>.12:reasons.append('SALIVA_OR_GLARE')
    if tongue.sum()/max(area,1)>.7:reasons.append('TONGUE_OCCLUSION')
    ys,xs=np.where(mouth)
    roi=dict(x=int(xs.min()),y=int(ys.min()),width=int(xs.max()-xs.min()+1),height=int(ys.max()-ys.min()+1)) if len(xs) else None
    return dict(valid=not reasons,reasons=reasons,gateVersion=DENTAL_GATES['version'],anatomicalMouthWidthPixels=anatomical,mouthOpeningRatio=opening,mouthWidthPixels=width,incisalContact=contact,roi=roi,
                visibleToothPixels=count,toothFraction=fraction,enamelAreaFraction=area_fraction,supportedEnamelColumns=columns,sharpness=sharp,light=light,clippedPixels=int(glare.sum()))


def projected_contour_overlap(contours,axis):
    """Adjacent visible outline projections, not hidden/3-D tooth overlap."""
    direction=np.asarray(axis,np.float64);direction/=max(float(np.linalg.norm(direction)),1e-9)
    intervals=[]
    for item in contours:
        coordinates=np.asarray(item['points'],np.float64)@direction
        intervals.append((float(coordinates.min()),float(coordinates.max())))
    intervals.sort(key=lambda pair:(pair[0]+pair[1])/2)
    ratios=[]
    for a,b in zip(intervals,intervals[1:]):
        overlap=max(0.,min(a[1],b[1])-max(a[0],b[0]))
        ratios.append(min(1.,overlap/max(min(a[1]-a[0],b[1]-b[0]),1e-9)))
    return float(np.mean(ratios)) if ratios else None


def contours_and_alignment(image,tooth,mouth,p,row_center=None,source_mouth_width=None):
    """Marker controlled watershed on visible enamel, no invented FDI/teeth."""
    distance=cv2.distanceTransform(tooth.astype(np.uint8),cv2.DIST_L2,5)
    if distance.max()<2:return [],None,'TOOTH_BOUNDARIES_UNRELIABLE'
    maxima=(distance==cv2.dilate(distance,np.ones((9,9),np.uint8)))&(distance>max(2,distance.max()*.28))
    markers,count=ndimage.label(maxima)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32)/255
    gradient=np.hypot(cv2.Sobel(gray,cv2.CV_32F,1,0),cv2.Sobel(gray,cv2.CV_32F,0,1))
    labels=watershed(gradient,markers,mask=tooth,compactness=.002)
    contours=[];rows={'upper':[],'lower':[]}
    center=row_center if row_center is not None else (p[13,1]+p[14,1])/2;mouth_width=source_mouth_width if source_mouth_width is not None else float(np.linalg.norm(p[78]-p[308]))
    for label in range(1,count+1):
        cc,_=cv2.findContours((labels==label).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        if not cc:continue
        contour=max(cc,key=cv2.contourArea);area=cv2.contourArea(contour);x,y,w,h=cv2.boundingRect(contour)
        if area<max(20,mouth_width**2*.0015) or len(contour)<5 or not .2<w/max(h,1)<3:continue
        hull_area=cv2.contourArea(cv2.convexHull(contour))
        if area/max(hull_area,1)<.7:continue
        ellipse=cv2.fitEllipse(contour);angle=float(ellipse[2]);cx,cy=ellipse[0]
        # The ellipse axis has 180-degree symmetry; normalize its orientation.
        angle=((angle+90)%180)-90
        which='upper' if cy<center else 'lower'
        item=dict(points=contour[:,0,:].tolist(),angleDegrees=angle,centroid=[cx,cy],areaPixels=float(area),row=which)
        contours.append(item);rows[which].append(item)
    metrics={}
    for which,items in rows.items():
        if len(items)<3:metrics[which]=dict(value=None,unit='degrees',quality='insufficient',limitationCode='FEWER_THAN_THREE_RELIABLE_CONTOURS');continue
        items.sort(key=lambda a:a['centroid'][0]);xs=np.array([i['centroid'][0] for i in items]);ys=np.array([i['centroid'][1] for i in items]);slope,intercept=np.polyfit(xs,ys,1)
        angles=np.array([i['angleDegrees'] for i in items]);axis=float(np.degrees(np.angle(np.mean(np.exp(2j*np.radians(angles)))))/2)
        orientation=float(np.median(np.abs((angles-axis+90)%180-90)))
        residual=float(np.sqrt(np.mean((ys-(slope*xs+intercept))**2))/max(mouth_width,1))
        projection_overlap=projected_contour_overlap(items,[1.,slope])
        metrics[which]=dict(value=orientation,unit='degrees',quality='valid',limitationCode=None,contourCount=len(items),rowPositionResidual=residual,
            projectedContourOverlapRatio=projection_overlap,projectedOverlapMeaning='mean adjacent visible outline interval overlap / smaller interval width in fitted row direction; not physical or 3-D overlap',
            viewTiltDegrees=float(np.degrees(np.arctan(slope))),meaning='visible contour orientation dispersion, not malocclusion')
    return contours,metrics,None if any(v['value'] is not None for v in metrics.values()) else 'TOOTH_BOUNDARIES_UNRELIABLE'


def calculus_candidates(image,tooth,gum):
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV).astype(np.float32)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32)/255
    border=tooth&cv2.dilate(gum.astype(np.uint8),np.ones((11,11),np.uint8)).astype(bool)
    # Color is necessary, never sufficient: require irregular local texture and
    # tooth/gum border structure. Uniform yellow enamel/stain alone is negative.
    yellow=(hsv[:,:,0]>10)&(hsv[:,:,0]<40)&(hsv[:,:,1]>55)&(hsv[:,:,1]<170)
    texture=np.sqrt(np.maximum(0,cv2.GaussianBlur(gray*gray,(0,0),1.5)-cv2.GaussianBlur(gray,(0,0),1.5)**2))
    gradient=np.hypot(cv2.Sobel(gray,cv2.CV_32F,1,0),cv2.Sobel(gray,cv2.CV_32F,0,1))
    mask=border&yellow&(texture>.025)&(gradient>.12)&(gray>.15)&(gray<.9)
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8));candidates=[]
    # Same components/contours as before, but each is traced inside its own
    # bounding box (offset back to source pixels) and the enamel total is
    # computed once. The previous full-frame pass per component made large
    # uploads exceed the 30 s local analysis budget.
    area_limit=int(tooth.sum())*.15
    for i in range(1,n):
        x,y,w,h,area=stats[i]
        if area<6 or area>area_limit:continue
        cc,_=cv2.findContours((labels[y:y+h,x:x+w]==i).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE,offset=(int(x),int(y)))
        candidates.append(dict(bounds=dict(x=int(x),y=int(y),width=int(w),height=int(h)),points=max(cc,key=cv2.contourArea)[:,0,:].tolist(),areaPixels=int(area)))
    return candidates,int(border.sum())


def prepare_model_input(image,mouth,size):
    # Only the actual visible mouth is resized. Preview/CSS zoom is irrelevant.
    ys,xs=np.where(mouth)
    if not len(xs):raise ValueError('VISIBLE_MOUTH_MISSING')
    h,w=image.shape[:2];pad=max(4,int((xs.max()-xs.min()+1)*.15))
    x0,y0=max(0,int(xs.min())-pad),max(0,int(ys.min())-pad)
    x1,y1=min(w,int(xs.max())+pad+1),min(h,int(ys.max())+pad+1)
    source=image[y0:y1,x0:x1];ratio=min(size/source.shape[0],size/source.shape[1])
    canvas=np.full((size,size,3),114,np.uint8)
    resized=cv2.resize(source,(max(1,int(source.shape[1]*ratio)),max(1,int(source.shape[0]*ratio))))
    canvas[:resized.shape[0],:resized.shape[1]]=resized
    return canvas.transpose(2,0,1)[None].astype(np.float32),ratio,(x0,y0)


def model_candidates(image,mouth,check=lambda:None):
    check()
    global _session,_manifest,_model_runtime,_model_identity
    path=ROOT/'models/dental-yolox-s.onnx';manifest_path=ROOT/'models/dental-yolox-s.json'
    if not path.exists() or not manifest_path.exists():raise DentalModelError('TRAINED_MODEL_NOT_INSTALLED')
    identity=tuple((p.stat().st_size,p.stat().st_mtime_ns) for p in (path,manifest_path))
    if _session is not None and _model_identity is not None and identity!=_model_identity:raise DentalModelError('MODEL_IDENTITY_CHANGED')
    if _session is None:
        import onnxruntime as ort
        manifest=json.loads(manifest_path.read_text('utf8'))
        with path.open('rb') as model_file:digest=hashlib.file_digest(model_file,'sha256').hexdigest()
        if digest!=manifest['modelHash']:raise DentalModelError('MODEL_HASH_MISMATCH')
        if manifest.get('classes')!=['D','d'] or manifest.get('inputSize')!=320 or manifest.get('confidenceThreshold')!=.35 or manifest.get('modelVersion')!='yolox-s-dental-from-scratch-v1':raise DentalModelError('MODEL_CONTRACT_MISMATCH')
        options=ort.SessionOptions();options.intra_op_num_threads=2
        try:_session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
        except Exception as error:raise DentalModelError('MODEL_LOAD_FAILED') from error
        _manifest=manifest
        _model_identity=identity
        _model_runtime=dict(onnxruntime=ort.__version__,opencv=cv2.__version__,numpy=np.__version__)
    size=_manifest['inputSize'];h,w=image.shape[:2]
    tensor,ratio,(origin_x,origin_y)=prepare_model_input(image,mouth,size)
    check()
    try:raw=_session.run(None,{'images':tensor})[0]
    except Exception as error:raise DentalModelError('MODEL_INFERENCE_FAILED') from error
    if not isinstance(raw,np.ndarray) or raw.shape!=(1,2100,7) or not np.isfinite(raw).all() or np.any(raw[:,:,4:]<0) or np.any(raw[:,:,4:]>1):
        raise DentalModelError('INVALID_MODEL_OUTPUT')
    check()
    outputs=raw[0]
    probabilities=outputs[:,4:5]*outputs[:,5:];classes=np.argmax(probabilities,axis=1);scores=np.max(probabilities,axis=1)
    chosen=np.flatnonzero(scores>=_manifest['confidenceThreshold']);boxes=[];class_values=[];confidences=[]
    for i in chosen:
        cx,cy,bw,bh=outputs[i,:4]/ratio;cx+=origin_x;cy+=origin_y;x0,y0=max(0,cx-bw/2),max(0,cy-bh/2);x1,y1=min(w,cx+bw/2),min(h,cy+bh/2)
        if x1<=x0 or y1<=y0:continue
        # Do not display detections outside the currently visible inner mouth.
        if not mouth[min(h-1,max(0,int(cy))),min(w-1,max(0,int(cx)))]:continue
        visible=mouth[int(y0):int(np.ceil(y1)),int(x0):int(np.ceil(x1))]
        if visible.size==0 or float(visible.mean())<.65:continue
        boxes.append([float(x0),float(y0),float(x1-x0),float(y1-y0)]);class_values.append(int(classes[i]));confidences.append(float(scores[i]))
    keep=[]
    for category in set(class_values):
        indices=[i for i,c in enumerate(class_values) if c==category]
        selected=cv2.dnn.NMSBoxes([boxes[i] for i in indices],[confidences[i] for i in indices],_manifest['confidenceThreshold'],.45)
        keep.extend(indices[int(i)] for i in np.asarray(selected).ravel())
    candidates=[dict(bounds=dict(zip(('x','y','width','height'),boxes[i])),classCode=_manifest['classes'][class_values[i]],confidence=confidences[i]) for i in keep]
    return candidates,dict(quality='valid',methodVersion='official-yolox-s-local-v1',decisionThreshold=_manifest['confidenceThreshold'],modelHash=_manifest['modelHash'],modelVersion=_manifest['modelVersion'],datasetLicense='CC-BY-4.0',evaluation=_manifest['evaluation'],runtimeVersions=_model_runtime,limitationCode='VISIBLE_SURFACE_ONLY_NOT_DIAGNOSIS',inputRegion='actual-inner-mouth-with-15-percent-source-margin')


def analyze_dental(payload,check=lambda:None):
    check()
    if len(payload.get('captures',[])) not in (1,2,3,4):raise ValueError('CAPTURE_LIMIT')
    captures=payload['captures']
    # Repeated frames or repeated view names are not independent views.
    if len({c.get('photoId') for c in captures})!=len(captures):raise ValueError('DUPLICATE_CAPTURE')
    if len({c.get('pose') for c in captures})!=len(captures):raise ValueError('DUPLICATE_VIEW')
    views=[]
    for capture in payload['captures']:
        check()
        image,source_hash=decode_photo(capture['photo'])
        if source_hash!=capture['photoId']:raise ValueError('SOURCE_HASH_MISMATCH')
        quality=dental_quality(image,capture['landmarks'],capture.get('pose')=='BITE')
        if not quality['valid']:
            unavailable=dict(value=None,quality='insufficient',limitationCode='CAPTURE_QUALITY',
                region='visible-inner-mouth',evaluatedArea=None,captureConditions={**capture.get('conditions',{}),**quality},
                uncertainty=['capture-quality-failed'],referenceId=None,localMap=None,modelVersion=None,modelHash=None)
            views.append(dict(photoId=source_hash,pose=capture['pose'],sourceWidth=image.shape[1],sourceHeight=image.shape[0],quality=quality,
                caries=dict(type='trained_prediction',unit='candidate-count',methodVersion='official-yolox-s-local-v1',candidates=[],**unavailable),
                accumulation=dict(type='appearance_proxy',unit='percent-visible-border-area',methodVersion='dental-border-cv-v2',candidates=[],**unavailable),
                alignment=dict(type='appearance_proxy',unit='degrees-of-visible-axis-dispersion',methodVersion='marker-watershed-v1',rows=None,contours=[],**unavailable)));continue
        mouth,_,_,points=mouth_geometry(capture['landmarks'],image.shape);tooth,_,gum,_,_=dental_pixels(image,mouth,native_capture=True)
        deposits,area=calculus_candidates(image,tooth,gum)
        mouth_width=max(float(np.linalg.norm(points[308]-points[78])),1);horizontal=(points[308]-points[78])/mouth_width;vertical=np.array([-horizontal[1],horizontal[0]]);center=(points[13]+points[14])/2
        for candidate in deposits:
            box=candidate['bounds'];position=np.array([box['x']+box['width']/2,box['y']+box['height']/2])-center
            candidate['mouthPosition']=[float(position@horizontal/mouth_width),float(position@vertical/mouth_width)]
            candidate['normalizedArea']=candidate['areaPixels']/mouth_width**2
        check();caries,model=model_candidates(image,mouth,check)
        contours,alignment,reason=contours_and_alignment(image,tooth,mouth,points) if capture['pose']=='BITE' else ([],None,'NATURAL_BITE_CAPTURE_REQUIRED')
        meta=dict(region='visible-inner-mouth',captureConditions={**capture.get('conditions',{}),**quality},
                  modelVersion=None,modelHash=None,referenceId=None,localMap=None)
        model_meta={**meta,**model}
        views.append(dict(photoId=source_hash,pose=capture['pose'],sourceWidth=image.shape[1],sourceHeight=image.shape[0],quality=quality,
            caries=dict(type='trained_prediction',value=len(caries) if model['quality']=='valid' else None,unit='candidate-count',candidates=caries,evaluatedArea=int(mouth.sum()),uncertainty=['dataset-domain-shift','visible-surface-only','confidence-is-not-severity'],**model_meta),
            accumulation=dict(type='appearance_proxy',value=sum(c['areaPixels'] for c in deposits)/area*100 if area>100 else None,unit='percent-visible-border-area',candidateArea=sum(c['areaPixels'] for c in deposits),evaluatedArea=area,candidates=deposits,methodVersion='dental-border-cv-v2',quality='valid' if area>100 else 'insufficient',limitationCode=None if area>100 else 'GINGIVAL_BORDER_NOT_VISIBLE',viewSupport=1,evidenceScope='per-view-appearance-unconfirmed',uncertainty=['stain-food-filling-confounders','visible-border-only','not-multiview-confirmed'],**meta),
            alignment=dict(type='appearance_proxy',value={key:item['value'] for key,item in alignment.items()} if reason is None else None,unit='degrees-of-visible-axis-dispersion',rows=alignment,contours=contours,evaluatedArea=int(tooth.sum()),uncertainty=['view-perspective','visible-contour-separation','not-malocclusion'],quality='valid' if reason is None else 'insufficient',limitationCode=reason,methodVersion='marker-watershed-v1',**meta)))
    # A local border-appearance measure is valid from one accepted photograph.
    # Relative mouth position/color is not tooth identity across perspective;
    # do not invent multiview confirmation or suppress valid per-view evidence.
    check()
    missing=[pose for pose in ('FRONT','RIGHT','LEFT','BITE') if pose not in {c['pose'] for c in captures}]
    return adult_product_result(dict(methodVersion='dental-visible-v2',sourceType='camera',views=views,missingViews=missing,biteGate=BITE_CONTACT['version'],storage='volatile-memory-only',clinicalValidation=False))
