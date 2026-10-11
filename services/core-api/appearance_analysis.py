"""Local, deterministic appearance proxies. No diagnosis, storage or network.

All maps have fixed physical digital scales (never per-image min/max). Coordinates
refer to the original opaque PNG. Display pixels are never changed. Pixel filters
are applied to a separate face-scale-normalized copy, not the displayed photo.
"""
from instant_appearance import instant_proxy, UNIT as INSTANT_UNIT
import base64
import hashlib
import math
import cv2
import numpy as np
from skin_general import general_result
from skin_models import infer as infer_skin_models, infer_acne, infer_bags
from skin_measurement_contract import attach_result_receipts
from skimage.feature import local_binary_pattern
from skimage.filters import gabor
from skin_scan_baseline.oiliness import oiliness_map
from skin_scan_baseline.blemishes import blemish_map

VERSION = 'appearance-cv-6'
LIMITS = {'minFacePixels': 180, 'analysisFacePixels': 320, 'maxClippedFraction': .03}
NORMALIZATION={'tone':'lab-local-color-fixed-v1','redness':'lab-red-excess-fixed-v1','oil':'visible-specular-area-fixed-v1','dry':'eligible-flake-area-fixed-v1','acne':'unique-detection-box-area-fixed-v1','lines':'outer-canthus-gabor-fixed-v1','dark':'lower-lid-relative-contrast-fixed-v1','sag':'contour-fold-fixed-v2','bags':'contour-fold-fixed-v2'}


def decode_photo(data):
    if not isinstance(data, str) or not data.startswith('data:image/png;base64,') or len(data) > 34_000_000:
        raise ValueError('INVALID_PHOTO')
    raw = base64.b64decode(data.split(',', 1)[1], validate=True)
    # PNG dimensions checked before decoder allocation.
    if raw[:8] != b'\x89PNG\r\n\x1a\n' or len(raw) < 24:
        raise ValueError('INVALID_PNG')
    width, height = int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')
    if not 16 <= width <= 4096 or not 16 <= height <= 4096 or width * height > 8_400_000:
        raise ValueError('PHOTO_LIMIT')
    bgr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None or bgr.shape[:2] != (height, width):
        raise ValueError('INVALID_PNG')
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
    return bgr, hashlib.sha256(rgba.tobytes()).hexdigest()


def polygon_mask(shape, mesh, scale, origin=(0,0)):
    mask = np.zeros(shape, np.uint8)
    p = (np.asarray([[v['x'], v['y']] for v in mesh['points']], np.float32)-origin) * scale
    if not np.isfinite(p).all() or not 3 <= len(p) <= 200 or len(mesh['edges']) > 1000:
        raise ValueError('INVALID_GEOMETRY')
    edges = {tuple(sorted(e)) for e in mesh['edges']}
    if any(len(e) != 2 or min(e) < 0 or max(e) >= len(p) for e in edges):
        raise ValueError('INVALID_GEOMETRY')
    neighbors=[set() for _ in p]
    for a,b in edges:neighbors[a].add(b);neighbors[b].add(a)
    for a,b in edges:
        for c in neighbors[a].intersection(neighbors[b]):
            if c>b:cv2.fillConvexPoly(mask,p[[a,b,c]].astype(np.int32),255)
    return mask > 0


def png(array):
    ok, data = cv2.imencode('.png', array)
    if not ok:
        raise ValueError('ENCODING_ERROR')
    return 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')


def map_result(values, mask, region, criterion, photo, pose, source_shape, scale, unit, ceiling, origin=(0,0)):
    ys, xs = np.where(mask)
    if not len(xs):
        return None
    x, y, w, h = int(xs.min()), int(ys.min()), int(xs.max()-xs.min()+1), int(ys.max()-ys.min()+1)
    v, m = values[y:y+h, x:x+w], mask[y:y+h, x:x+w]
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[:, :, :3] = (241, 228, 54)  # BGRA -> existing cyan palette.
    rgba[:, :, 3] = np.round(np.clip(v / ceiling, 0, 1) * m * 100).astype(np.uint8)
    return dict(criterion=criterion, region=region, pose=pose, photoId=photo,
                sourceWidth=source_shape[1], sourceHeight=source_shape[0], x=x/scale+origin[0], y=y/scale+origin[1],
                step=1/scale, width=w, height=h, unit=unit, method=VERSION,
                validation='appearance-proxy', colorMapping='cyan-fixed-100-v1',mapType='source-pixel-signal',
                dataUrl=png(rgba), validMaskUrl=png((m * 255).astype(np.uint8)), sampleCount=int(m.sum()))


def row(region, criterion, value, unit, area, conditions, limitation=None, components=None, kind='appearance_proxy', uncertainty=None):
    return dict(id=criterion, type=kind, value=value, unit=unit, methodVersion=VERSION,
                scoreDirection='higher-is-more-visible',normalizationVersion=NORMALIZATION[criterion],
                modelVersion=None, modelHash=None, quality='valid' if value is not None else 'insufficient',
                uncertainty=uncertainty or ['illumination', 'visible-surface-only', 'unvalidated-cosmetic-proxy'],
                region=region, evaluatedArea=area, captureConditions=conditions,
                limitationCode=limitation, referenceId=None, localMap=None, components=components or {})


def eligible_flake_components(signal,eligible):
    """Recheck actual bright-island support after anatomical/hair exclusions."""
    count,labels,stats,_=cv2.connectedComponentsWithStats(((signal>.04)&eligible).astype(np.uint8))
    islands=np.zeros(signal.shape,bool)
    for label in range(1,count):
        x,y,w,h,pixels=stats[label]
        if 3<=pixels<=80 and .3<=w/max(h,1)<=3.3 and pixels/max(w*h,1)>.25:
            islands|=labels==label
    return signal*eligible*islands


def elongated_dark_mask(gray8):
    """Exclude long dark filaments, not every round dark focus as hair."""
    dark=cv2.morphologyEx(gray8,cv2.MORPH_BLACKHAT,np.ones((7,7),np.uint8))>35
    n,labels,stats,_=cv2.connectedComponentsWithStats(dark.astype(np.uint8))
    hair=np.zeros_like(dark)
    for i in range(1,n):
        _,_,w,h,area=stats[i]
        if max(w,h)>=8 and max(w,h)/max(min(w,h),1)>=3:
            hair|=labels==i
    return cv2.dilate(hair.astype(np.uint8),np.ones((5,5),np.uint8))>0


def local_color_signals(image,valid):
    """Fixed-scale chromatic contrast; luminance is not a tone defect.
    Robust observed skin reference cancels uniform tint approximately. This
    evaluates relative appearance; it cannot infer globally diffuse erythema.
    """
    lab=cv2.cvtColor(image.astype(np.float32)/255,cv2.COLOR_BGR2LAB)
    chroma=lab[:,:,1:3];empty=np.zeros(image.shape[:2],np.float32)
    if not valid.any():return empty,empty,{}
    center=np.median(chroma[valid],axis=0)
    difference=np.linalg.norm(chroma-center,axis=2)
    tone=np.clip(difference,0,100)
    # One fixed a* contrast scale, never the image's own min/max.
    reference=float(np.percentile(chroma[:,:,0][valid],25))
    redness=np.clip((chroma[:,:,0]-reference-2.)*2.,0,100)
    return tone,redness,dict(colorSpace='CIELAB a*,b*',observedReference=center.tolist(),redReferenceA=reference,redDeadbandA=2.,redScale=2.,toneMeaning='mean chromatic Delta-ab to observed regional median',redMeaning='positive local a* difference; uniform color cast not erythema severity')


def eye_skin_bands(points, shape, scale, origin, source_shape):
    """Distinct lower-lid skin and outer-canthus supports in source coordinates.
    These masks restrict measurement; the approved presentation mesh is unchanged.
    """
    p=np.asarray([[(v['x']*source_shape[1]-origin[0])*scale,
                   (v['y']*source_shape[0]-origin[1])*scale] for v in points],np.float32)
    axis=p[263]-p[33];axis/=max(float(np.linalg.norm(axis)),.001)
    down=np.array([-axis[1],axis[0]],np.float32)
    if down[1]<0:down=-down
    face_width=max(float(abs((p[454]-p[234])@axis)),1.)
    result={k:np.zeros(shape,np.uint8) for k in ('dark','bags','lines')}
    for lower,corner,sign in [([33,163,144,145,153,154,155,133],33,-1),([263,390,373,374,380,381,382,362],263,1)]:
        line=p[lower]
        for criterion,top,bottom in [('dark',.012,.065),('bags',.022,.095)]:
            polygon=np.concatenate([line+down*face_width*top,(line+down*face_width*bottom)[::-1]])
            cv2.fillPoly(result[criterion],[np.rint(polygon).astype(np.int32)],255)
        c=p[corner];out=axis*sign*face_width
        polygon=np.asarray([c+out*.012-down*face_width*.012,c+out*.085-down*face_width*.025,
                            c+out*.09+down*face_width*.05,c+out*.012+down*face_width*.06])
        cv2.fillPoly(result['lines'],[np.rint(polygon).astype(np.int32)],255)
    return {k:v>0 for k,v in result.items()}


def acne_candidates(red, gray, saturation, high, local_contrast, baseline, eligible):
    """One connected component list per source; no regional duplicate detections."""
    red_center=red-cv2.GaussianBlur(red,(0,0),4)
    scale2=red-cv2.GaussianBlur(red,(0,0),2)
    detected=((red_center>.055)&(scale2>.028)&(local_contrast>.008)&(baseline>.02)&eligible).astype(np.uint8)
    n,labels,stats,_=cv2.connectedComponentsWithStats(detected)
    support=cv2.erode(eligible.astype(np.uint8),np.ones((5,5),np.uint8))>0
    objects=[]
    for label in range(1,n):
        x,y,w,h,count=stats[label];blob=labels==label
        if not 5<=count<=180 or not .45<=w/max(h,1)<=2.2 or count/max(w*h,1)<.38:continue
        if not support[blob].all() or np.mean(gray[blob])<.20 or np.mean(saturation[blob])<.12 or np.mean(high[blob]>0)<.08:continue
        objects.append((int(x),int(y),int(w),int(h),int(count),blob))
    return objects,red_center


def contour_geometry(points, region, conditions, temporal):
    """Roll-corrected dimensionless *within-person* geometry, not sag severity."""
    aspect=float(conditions.get('sourceHeight',1))/max(float(conditions.get('sourceWidth',1)),1)
    def normalise(frame):
        raw=np.asarray([[v['x'],v['y']*aspect,v.get('z',0)] for v in frame],np.float64)
        if len(raw)<468 or not np.isfinite(raw).all():return None
        horizontal=raw[263]-raw[33];distance=np.linalg.norm(horizontal)
        if distance<=1e-5:return None
        horizontal/=distance
        vertical=raw[152]-raw[10];vertical-=horizontal*np.dot(vertical,horizontal)
        if np.linalg.norm(vertical)<=1e-5:return None
        vertical/=np.linalg.norm(vertical)
        centered=(raw-(raw[33]+raw[263])/2)/distance
        return np.column_stack([centered@horizontal,centered@vertical])
    q=normalise(points)
    if q is None:return None,'LANDMARKS_INVALID'
    mouth = np.linalg.norm(q[13] - q[14]) / max(np.linalg.norm(q[61]-q[291]), .001)
    if abs(conditions.get('yaw', 99)) > .65 or abs(conditions.get('pitch', 99)) > .22 or mouth > .10:
        return None, 'POSE_OR_EXPRESSION_INCOMPATIBLE'
    if len(temporal) < 3:
        return None, 'TEMPORAL_SUPPORT_MISSING'
    supports=[normalise(frame.get('points',frame) if isinstance(frame,dict) else frame) for frame in temporal]
    if any(frame is None for frame in supports):return None,'TEMPORAL_SUPPORT_INVALID'
    stable=np.std(np.asarray(supports)[:,[33,263,152,145,373],:],axis=0).max()
    if stable>.035:return None,'CONTOUR_NOT_STABLE'
    if region == 'chin':
        indices = [172, 136, 150, 152, 379, 365, 397]
    elif region == 'rightCheek':
        indices = [50, 187, 147, 172, 136]
    elif region == 'leftCheek':
        indices = [280, 411, 376, 397, 365]
    elif region == 'forehead':
        indices = [70, 63, 105, 66, 107, 336, 296, 334, 293, 300]
    elif region == 'periorbital':
        indices = [145, 153, 154, 373, 380, 381]
    else:
        return None, 'ANATOMY_NOT_APPLICABLE'
    # Translation/roll/face-width invariant real contour ordinates.
    features = q[indices, 1]
    return dict(features=features.tolist(), indices=indices, points=[points[i] for i in indices],
                ratio=float(np.mean(features)), neutralMouthRatio=float(mouth), samples=len(temporal)), None


def analyze_skin(payload, include_research_features=False):
    bgr, source_hash = decode_photo(payload['photo'])
    if source_hash != payload['photoId']:
        raise ValueError('SOURCE_HASH_MISMATCH')
    points = payload.get('landmarks', [])
    if len(points) < 468:
        raise ValueError('LANDMARKS_MISSING')
    width = bgr.shape[1]
    face_pixels = abs(points[454]['x'] - points[234]['x']) * width
    scale = min(1., LIMITS['analysisFacePixels'] / max(face_pixels, 1))
    source_points=np.asarray([[v['x'],v['y']] for m in payload['meshes'].values() for v in m['points']],np.float32)
    if not len(source_points) or not np.isfinite(source_points).all():raise ValueError('INVALID_GEOMETRY')
    pad=max(20,face_pixels*.1);x0=max(0,int(source_points[:,0].min()-pad));y0=max(0,int(source_points[:,1].min()-pad))
    x1=min(bgr.shape[1],int(source_points[:,0].max()+pad+1));y1=min(bgr.shape[0],int(source_points[:,1].max()+pad+1))
    if x1<=x0 or y1<=y0:raise ValueError('INVALID_GEOMETRY')
    origin=(x0,y0)
    image = cv2.resize(bgr[y0:y1,x0:x1], None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray8 = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = gray8.astype(np.float32)/255
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
    saturation, v = hsv[:, :, 1]/255, hsv[:, :, 2]/255
    rgb = image[:, :, ::-1].astype(np.float32)/255
    red = np.maximum(0, 2*rgb[:, :, 0]-rgb[:, :, 1]-rgb[:, :, 2])
    local_v = cv2.GaussianBlur(v, (0, 0), 5)
    local_s = cv2.GaussianBlur(saturation, (0, 0), 5)
    # Skin-scan oiliness starts with bright, low-saturation pixels; here require
    # local contrast AND saturation drop. Bright matte skin alone is insufficient.
    shine = np.clip((v/np.maximum(local_v, .05)-1.08)/.24, 0, 1) * np.clip((local_s-saturation)/.18, 0, 1)
    high = gray-cv2.GaussianBlur(gray, (0, 0), 1.2)
    broad = cv2.GaussianBlur(gray, (0, 0), .7)-cv2.GaussianBlur(gray, (0, 0), 2.3)
    # Bright fine islands at both scales; long dark hairs/creases excluded later.
    flakes = np.clip((high-.025)/.10, 0, 1)*np.clip((broad-.018)/.10, 0, 1)
    lbp = local_binary_pattern(gray8, 8, 1, 'uniform')
    flakes*=lbp<8
    local_contrast = np.sqrt(np.maximum(0, cv2.GaussianBlur(gray*gray, (0, 0), 2)-cv2.GaussianBlur(gray, (0, 0), 2)**2))
    flakes*=(local_contrast>.015)&(local_contrast<.14)
    flakes=eligible_flake_components(flakes,np.ones(gray.shape,bool))
    hair = elongated_dark_mask(gray8)
    clipping = (v > .975)  # Darkness/hair is an exclusion, not specular glare.
    masks = {k: polygon_mask(gray.shape, m, scale, origin) for k, m in payload['meshes'].items()}
    exclusion = np.zeros(gray.shape, np.uint8)
    for box in payload.get('exclusions', []):
        x=int((box['x']-x0)*scale);y=int((box['y']-y0)*scale);w=int(box['w']*scale);h=int(box['h']*scale)
        cv2.rectangle(exclusion, (max(0, x), max(0, y)), (max(0, x+w), max(0, y+h)), 255, -1)
    # Always remove eyes/lips/nostrils/brows using actual landmarks, including
    # periorbital masks. These holes apply independently of ROI rectangle gates.
    holes = [[33,160,158,133,153,144], [263,387,385,362,380,373],
             [61,40,37,0,267,270,291,321,314,17,84,91],
             [98,97,2,326,327,294], [70,63,105,66,107,55,65,52], [300,293,334,296,336,285,295,282]]
    for indices in holes:
        poly = np.asarray([[(points[i]['x']*width-x0)*scale, (points[i]['y']*bgr.shape[0]-y0)*scale] for i in indices], np.int32)
        cv2.fillPoly(exclusion, [poly], 255)
    # Filter support at a cropped source edge is invalid, rather than a dark border signal.
    edge=max(2,int(round(4*scale)))
    exclusion[:edge,:]=255;exclusion[-edge:,:]=255;exclusion[:,:edge]=255;exclusion[:,-edge:]=255
    face_support=np.zeros(gray.shape,np.uint8)
    oval=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
    face_polygon=np.array([[(points[i]['x']*width-x0)*scale,(points[i]['y']*bgr.shape[0]-y0)*scale] for i in oval],np.int32)
    cv2.fillPoly(face_support,[face_polygon],255)
    baseline_masks={k:(m*255).astype(np.uint8) for k,m in masks.items()}
    baseline_oil=oiliness_map(image,baseline_masks)
    baseline_blemish=blemish_map(image,baseline_masks) if include_research_features else None
    shine*=baseline_oil>0
    bands=eye_skin_bands(points,gray.shape,scale,origin,bgr.shape)
    overall=np.logical_or.reduce(list(masks.values()))&(exclusion==0)&~hair&~clipping&(gray>.12)
    detections,red_center=acne_candidates(red,gray,saturation,high,local_contrast,baseline_blemish,overall) if include_research_features else ([],np.zeros(gray.shape,np.float32))
    # A component has one owning anatomical region in this source. T-zone overlap
    # must not turn a forehead component into an additional nose detection.
    assigned={k:[] for k in masks}
    for detection in detections:
        x,y,w,h,count,blob=detection
        eligible_owners=[k for k in ('forehead','rightCheek','leftCheek','nose','chin') if k in masks and masks[k][blob].mean()>=.65]
        if eligible_owners:assigned[eligible_owners[0]].append(detection)
    # Rejected heuristic candidates stay available only to an explicit offline
    # baseline experiment. Normal results require a pinned accepted detector.
    trained_acne=None if include_research_features else infer_acne(bgr,points,payload.get('qualityValid',False))
    trained_bags=None if include_research_features else infer_bags(bgr,points,payload.get('qualityValid',False))
    accepted_boxes={k:[] for k in masks}
    if trained_acne and trained_acne.get('valid'):
        for bx,by,ex,ey,confidence in trained_acne['boxes']:
            a=max(0,int((bx-x0)*scale));b=max(0,int((by-y0)*scale));c=min(gray.shape[1],int(math.ceil((ex-x0)*scale)));d=min(gray.shape[0],int(math.ceil((ey-y0)*scale)))
            if c<=a or d<=b:continue
            owners=[k for k in ('forehead','rightCheek','leftCheek','nose','chin') if k in masks and np.mean(masks[k][b:d,a:c]&overall[b:d,a:c])>=.65]
            if owners:accepted_boxes[owners[0]].append(dict(x=bx,y=by,width=ex-bx,height=ey-by,confidence=confidence,candidateId=hashlib.sha256(f'{source_hash}:{bx:.3f}:{by:.3f}:{ex:.3f}:{ey:.3f}'.encode()).hexdigest()[:24],coordinateSpace='source-pixels',localization='detection-box'))
    response, maps, contours = {}, {}, {}
    conditions = {**payload['conditions'],'sourceWidth':bgr.shape[1],'sourceHeight':bgr.shape[0]}
    for region, anatomical in masks.items():
        display_anatomical=anatomical
        if region=='nose':anatomical=anatomical|masks.get('forehead',np.zeros_like(anatomical))
        base = anatomical & (exclusion == 0)
        exposure_support=base & ~hair & (gray>.12)
        clipped = float(np.mean(clipping[exposure_support])) if exposure_support.any() else 1.
        valid = base & ~hair & ~clipping & (gray > .12)
        area = dict(sourcePixels=float(valid.sum()/scale**2), analysisPixels=int(valid.sum()),
                    anatomicalSourcePixels=float(anatomical.sum()/scale**2),
                    sourceFacePixels=float(face_pixels), excludedPixels=float((base.sum()-valid.sum())/scale**2))
        reason = 'CAPTURE_QUALITY' if not payload.get('qualityValid') else 'GLARE_OR_EXPOSURE' if clipped > .03 else 'INSUFFICIENT_VISIBLE_AREA' if valid.sum() < 100 else None
        if region=='nose':
            area.update(foreheadSourcePixels=float((valid&masks.get('forehead',np.zeros_like(valid))).sum()/scale**2),
                        noseSourcePixels=float((valid&display_anatomical).sum()/scale**2),
                        chinSourcePixels=0.)
        items = []
        def add(criterion, value, unit, signal=None, ceiling=1., limitation=reason, components=None, signal_mask=None):
            usable = limitation is None
            item = row(region, criterion, float(value) if usable else None, unit, area, conditions, limitation, components)
            items.append(item)
            if usable and signal is not None:
                layer = map_result(signal, valid & display_anatomical & (signal_mask if signal_mask is not None else True), region, criterion, source_hash, payload['pose'], bgr.shape, scale, unit, ceiling, origin)
                if layer:
                    key=f'{region}:{criterion}';maps[key]=layer
                    # Descriptor only: the pixel/mask payload remains ephemeral
                    # in response.maps and never enters numeric history records.
                    item['localMap']=dict(key=key,photoId=source_hash,region=region,
                        criterion=criterion,coordinateSpace='source-pixels')
        if region != 'periorbital':
            tone,redness,color_components=local_color_signals(image,valid)
            add('tone',np.mean(tone[valid]) if valid.any() else 0,'relative-color-index-0-100',tone,100,components=color_components)
            add('redness',np.mean(redness[valid]) if valid.any() else 0,'relative-color-index-0-100',redness,100,components=color_components)
            add('oil', np.mean(shine[valid] > .12)*100 if valid.any() else 0, 'percent-visible-area', shine,
                components={'localIntensity': float(np.mean(shine[valid])) if valid.any() else None, 'clippedFraction': clipped})
            # Small red center-surround candidates need circularity, texture and
            # multi-scale agreement. Dark moles/freckles and hair aren't acne evidence.
            boxes=[];candidate_area=np.zeros(gray.shape,bool)
            if include_research_features:
                for x,y,w,h,count,blob in assigned[region]:
                    candidate_area|=blob;boxes.append(dict(x=float(x/scale+x0),y=float(y/scale+y0),width=float(w/scale),height=float(h/scale),areaPixels=float(count/scale**2)))
            elif trained_acne and trained_acne.get('valid'):
                boxes=accepted_boxes[region]+(accepted_boxes.get('forehead',[]) if region=='nose' else [])
                for box in boxes:
                    a=max(0,int((box['x']-x0)*scale));b=max(0,int((box['y']-y0)*scale));c=min(gray.shape[1],int(math.ceil((box['x']+box['width']-x0)*scale)));d=min(gray.shape[0],int(math.ceil((box['y']+box['height']-y0)*scale)));candidate_area[b:d,a:c]=True
            acne_reason=reason or (None if include_research_features or trained_acne and trained_acne.get('valid') else (trained_acne or {}).get('reason','ACNE_MODEL_NOT_ACCEPTED'))
            coverage=float(np.mean(candidate_area[valid])*100) if valid.any() else 0.
            add('acne',coverage,'appearance-score-0-100',limitation=acne_reason,components={'bounds':boxes,'candidateCount':len(boxes),'evaluatedArea':area,'candidateBoxCoveragePercent':coverage,'normalization':'unique accepted detection-box pixels / visible anatomical source pixels *100','pixelSegmentation':False})
            if trained_acne and trained_acne.get('valid'):
                items[-1].update(modelVersion=trained_acne['modelVersion'],modelHash=trained_acne['modelHash']);items[-1]['components']['inference']= {k:trained_acne[k] for k in ('tileCount','loadMs','inferenceMs')}
        detail_reason = reason or ('INSUFFICIENT_SOURCE_DETAIL' if face_pixels < LIMITS['minFacePixels'] else None)
        # Compression around dark pores/hairs can create bright ringing. This
        # exclusion is specific to white flake evidence: round dark foci remain
        # available to the independent acne candidate detector.
        dark_ringing=cv2.dilate((cv2.morphologyEx(gray8,cv2.MORPH_BLACKHAT,np.ones((7,7),np.uint8))>35).astype(np.uint8),np.ones((7,7),np.uint8))>0
        regional_flakes=eligible_flake_components(flakes,valid & ~dark_ringing)
        add('dry', np.mean(regional_flakes[valid] > .04)*100 if valid.any() else 0, 'percent-visible-area', regional_flakes,
            limitation=detail_reason, components={'roughnessIndex':float(np.clip(np.mean(local_contrast[valid])/.12*100,0,100)) if valid.any() else None,
            'lbpNonUniformFraction':float(np.mean(lbp[valid] == 9)) if valid.any() else None,
            'meaning':'fine-bright-flaking-candidates; roughness alone is not dryness'})
        if region == 'periorbital':
            under=valid&bands['dark']
            adjacent = cv2.dilate(under.astype(np.uint8), np.ones((25,25),np.uint8)).astype(bool) & ~under & (exclusion == 0) & ~clipping & ~hair & (face_support>0) & (gray>.12)
            if adjacent.sum() >= 100 and under.sum()>=100:
                # Local relative contrast; global exposure cancels approximately.
                dark = np.maximum(0,(np.median(gray[adjacent])-gray)/max(float(np.median(gray[adjacent])), .1))*100
                add('dark', np.mean(dark[under]), 'relative-color-index-0-100', dark, 100,signal_mask=bands['dark'],components={'band':'lower-lid-skin','analysisPixels':int(under.sum())})
            else: add('dark', 0, 'relative-color-index-0-100', limitation='ADJACENT_SKIN_MISSING')
            lines = np.zeros(gray.shape, np.float32)
            for frequency in (.18,.28):
                for theta in (0,np.pi/4,np.pi/2,3*np.pi/4):
                    real, imaginary = gabor(gray, frequency=frequency, theta=theta)
                    lines = np.maximum(lines, np.clip((np.hypot(real,imaginary)-.015)/.06,0,1))
            # Outer canthi only; don't report lower-eye texture as crow's feet.
            outer=valid&bands['lines'];lines*=outer
            add('lines', np.mean(lines[outer])*100 if outer.any() else 0, 'directional-line-index-0-100', lines, limitation=detail_reason or (None if outer.sum()>=30 else 'OUTER_CORNER_NOT_VISIBLE'),signal_mask=bands['lines'])
        if region != 'nose':
            contour_support=base&~clipping&(gray>.12)
            if region=='periorbital':contour_support&=bands['bags']
            value,components,signal,lines,limitation=instant_proxy(gray,contour_support,points,region,conditions,scale,origin,bgr.shape,hair,(face_support>0)&(exclusion==0)&~clipping&(gray>.12))
            criterion = 'bags' if region == 'periorbital' else 'sag'
            used_bag_mask=False
            if region=='periorbital' and trained_bags and trained_bags.get('valid') and reason is None and detail_reason is None:
                used_bag_mask=True
                signal=np.zeros(gray.shape,np.float32);sides=[]
                for layer in trained_bags['layers']:
                    a,b,c,d=layer['rect'];mask=cv2.resize(layer['mask'],(c-a,d-b),interpolation=cv2.INTER_NEAREST)
                    source=np.zeros(bgr.shape[:2],np.uint8);source[b:d,a:c]=mask
                    projected=cv2.resize(source[y0:y1,x0:x1],(gray.shape[1],gray.shape[0]),interpolation=cv2.INTER_NEAREST)>0
                    signal[projected & valid & bands['bags']]=1
                    sides.append({'eye':layer['eye'],'sourceROI':layer['rect'],'predictedMaskPixels':int(mask.sum()),'modelResolution':[128,128]})
                under=valid&bands['bags'];value=float(np.mean(signal[under])*100) if under.sum()>=100 else None
                components={'sides':sides,'meaning':'predicted visible bag-presence area; not tissue volume or pixel severity','confidenceNotSeverity':True};lines=[];limitation=None if value is not None else 'INSUFFICIENT_VISIBLE_AREA'
            # Contours already carry measured coordinates; no region-wide sag fill.
            add(criterion,value or 0,INSTANT_UNIT,signal,limitation=reason or limitation,components=components)
            if used_bag_mask and value is not None:
                items[-1].update(modelVersion=trained_bags['modelVersion'],modelHash=trained_bags['modelHash'],unit='appearance-score-0-100',normalizationVersion='predicted-lower-lid-mask-area-v1')
                if 'periorbital:bags' in maps:maps['periorbital:bags'].update(mapType='predicted-presence-mask',unit='appearance-score-0-100',method=trained_bags['modelVersion'],modelHash=trained_bags['modelHash'])
            if value is not None and reason is None and lines:
                contours[region]=dict(points=lines[0],lines=lines,features=[])
        response[region]=items
    result=dict(methodVersion=VERSION,photoId=source_hash,measurements=response,maps=maps,contours=contours,
                storage='volatile-memory-only',sourceWidth=bgr.shape[1],sourceHeight=bgr.shape[0])
    if payload['pose']=='FRONT':
        union=np.logical_or.reduce(list(masks.values()))&(exclusion==0)&~hair&~clipping&(gray>.12)
        general_tone,general_redness,_=local_color_signals(image,union)
        general_area=dict(sourcePixels=float(union.sum()/scale**2),anatomicalSourcePixels=float(np.logical_or.reduce(list(masks.values())).sum()/scale**2),analysisPixels=int(union.sum()),sourceFacePixels=float(face_pixels))
        # Whole-face dryness uses the same valid bright-island support as the
        # regional rows. Compression ringing is never restored by unioning ROIs.
        general_flakes=eligible_flake_components(flakes,union & ~dark_ringing)
        global_candidates=np.zeros(gray.shape,bool)
        if include_research_features:
            for detection in detections:global_candidates|=detection[-1]
        elif trained_acne and trained_acne.get('valid'):
            for values in accepted_boxes.values():
                for box in values:
                    a=max(0,int((box['x']-x0)*scale));b=max(0,int((box['y']-y0)*scale));c=min(gray.shape[1],int(math.ceil((box['x']+box['width']-x0)*scale)));d=min(gray.shape[0],int(math.ceil((box['y']+box['height']-y0)*scale)));global_candidates[b:d,a:c]=True
        result['general']=general_result(response,masks,union,general_tone,general_redness,shine,general_flakes,
            general_area,conditions,payload.get('qualityValid',False),candidate_coverage=float(np.mean(global_candidates[union])*100) if union.any() else None)
        for item in result['general']['measurements']:
            item['scoreDirection']='higher-is-more-visible'
            item['normalizationVersion']=NORMALIZATION[item['id']]
            if item['id']=='bags' and trained_bags and trained_bags.get('valid') and item['modelHash']==trained_bags['modelHash']:item['normalizationVersion']='predicted-lower-lid-mask-area-v1'
        if not include_research_features:
            learned=infer_skin_models(bgr,points,result['general']['measurements'][0]['quality']=='valid' and face_pixels>=180)
            if learned['skinType']:result['general']['skinType']=learned['skinType']
            result['general']['modelInference']=learned.get('models',{})
            result['general']['modelInputTransform']=learned.get('sourceTransform')
            for item in result['general']['measurements']:
                degree=learned['degrees'].get(item['id'])
                # Acne card and source marks remain the same accepted detector
                # candidates. A whole-photo acne grade is not a calibrated
                # fusion with detection-box coverage and cannot replace it.
                if degree and item['id']!='acne':
                    item.update(value=degree['value'],type='trained_prediction',methodVersion=degree['methodVersion'],modelVersion=degree['methodVersion'],modelHash=degree['modelHash'],quality='valid',limitationCode=None,normalizationVersion=degree['normalizationVersion'],uncertainty=['source-label-protocol-unverified','camera-domain-shift'])
                    item['components'].update(rawGrade=degree['rawGrade'],normalizationVersion=degree['normalizationVersion'],modelScope='whole-face',localMapIsSeparateAnalyticSignal=True)
        if include_research_features:
            # Offline train/validation comparison only. The normal API never
            # requests or persists these alternatives or uses them as scores.
            oil_usable=next(r for r in result['general']['measurements'] if r['id']=='oil')['quality']=='valid'
            result['researchFeatures']={'oil-baseline':float(np.mean((baseline_oil>0)[union])*100) if union.any() and oil_usable else None}
        for criterion,signal,ceiling in [('tone',general_tone,100),('redness',general_redness,100),('oil',shine,1),('dry',general_flakes,1)]:
            measurement=next(r for r in result['general']['measurements'] if r['id']==criterion)
            if measurement['value'] is not None:
                layer=map_result(signal,union,'overview',criterion,source_hash,'FRONT',bgr.shape,scale,measurement['unit'],ceiling,origin)
                if layer:
                    maps['overview:'+criterion]=layer
                    measurement['localMap']=dict(key='overview:'+criterion,photoId=source_hash,region='overview',criterion=criterion,coordinateSpace='source-pixels')
        for criterion in ['dark','lines','bags']:
            layer=maps.get('periorbital:'+criterion)
            if layer:maps['overview:'+criterion]={**layer,'region':'overview'}
    return attach_result_receipts(result)
