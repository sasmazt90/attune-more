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
from skin_general import general_result,oil_region_support,OIL_SAMPLING
from skin_models import infer as infer_skin_models, infer_acne, infer_bags, session_status
from skin_measurement_contract import attach_result_receipts
from skin_product_contract import apply_learned_general_degree, tone_separation_components
from skimage.feature import local_binary_pattern
from skimage.filters import gabor
from acne_box_support import region_envelopes,accepted_boxes as filter_acne_boxes,box_area,VERSION as ACNE_SUPPORT_VERSION
from skin_display_geometry import measured_line_paths
from roboflow_skin_models import infer_lesion_large, infer_regional_oily_seg
from skin_scan_baseline.oiliness import oiliness_map
from skin_scan_baseline.blemishes import blemish_map

VERSION = 'appearance-cv-6'
LINE_FREQUENCIES=(.13,.18,.26)
LIMITS = {'minFacePixels': 180, 'analysisFacePixels': 320, 'maxClippedFraction': .03}
NORMALIZATION={'tone':'lab-local-color-fixed-v1','redness':'lab-red-excess-fixed-v1','oil':'visible-specular-area-fixed-v1+regional-quality-union-v2','dry':'eligible-flake-luma-union-v3','acne':'unique-detection-box-anatomical-area-v2','lines':'outer-canthus-gabor-radiating-hair-excluded-v4','dark':'lower-lid-contrast-chroma-local-v4','sag':'contour-fold-lower-chin-observed-runs-v9','bags':'contour-fold-local-support-v5'}


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


def bag_support_mask(shape, mesh, scale, origin=(0,0)):
    """Fill only closed, supported eye cells; no visible diagonal is required.

    Other criteria still use the original explicit triangle union. Old photos
    without cells retain their original region support.
    """
    mask=polygon_mask(shape,mesh,scale,origin).astype(np.uint8)
    cells=mesh.get('bagCells',[])
    if not isinstance(cells,list) or len(cells)>32:raise ValueError('INVALID_BAG_CELLS')
    p=(np.asarray([[v['x'],v['y']] for v in mesh['points']],np.float32)-origin)*scale
    edges={tuple(sorted(e)) for e in mesh['edges']}
    for cell in cells:
        if len(cell)!=4 or len(set(cell))!=4 or any(not isinstance(i,int) or i<0 or i>=len(p) for i in cell):raise ValueError('INVALID_BAG_CELLS')
        if any(tuple(sorted((a,cell[(j+1)%4]))) not in edges for j,a in enumerate(cell)):raise ValueError('UNSUPPORTED_BAG_CELL')
        if not cv2.isContourConvex(p[cell].astype(np.float32)):continue
        a,b,c,d=cell
        for triangle in ((a,b,c),(a,c,d)):cv2.fillConvexPoly(mask,p[list(triangle)].astype(np.int32),1)
    return mask>0


def closed_surface_mask(shape,mesh,scale,origin=(0,0)):
    """Dry/sag-only closed convex cells, bounded by four actual safe edges.

    Sparse visible diagonals are drawing detail, not holes in closed skin cells.
    No hull, open edge, concave shortcut or unsupported point is filled.
    """
    import itertools
    mask=polygon_mask(shape,mesh,scale,origin).astype(np.uint8)
    edges={tuple(sorted(e)) for e in mesh['edges']}
    neighbors={i:set() for i in range(len(mesh['points']))}
    for a,b in edges:neighbors[a].add(b);neighbors[b].add(a)
    points=np.asarray([[p['x'],p['y']] for p in mesh['points']],np.float32)
    cells={}
    for a,b in itertools.combinations(neighbors,2):
        if (a,b) in edges:continue
        for c,d in itertools.combinations(sorted(neighbors[a]&neighbors[b]),2):
            if tuple(sorted((c,d))) in edges:continue
            cell=[a,c,b,d]
            if cv2.isContourConvex(points[cell]):cells[tuple(sorted(cell))]=cell
    if len(cells)>64:raise ValueError('INVALID_SURFACE_CELLS')
    for cell in cells.values():
        projected=((points[cell]-np.asarray(origin))*scale).astype(np.int32)
        cv2.fillPoly(mask,[projected],1)
    return mask>0


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


def validated_measurement_value(value, limitation=None):
    """Keep an unavailable measurement distinct from a measured zero.

    Upstream analyzers normally return a limitation together with ``None``.
    This boundary still fails closed if that limitation is accidentally lost,
    and it rejects non-finite values before they enter history or maps.
    """
    if limitation is not None:
        return None, limitation
    if value is None or isinstance(value, (bool, np.bool_)):
        return None, 'MEASUREMENT_UNAVAILABLE'
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        return None, 'MEASUREMENT_UNAVAILABLE'
    if not np.isfinite(numeric):
        return None, 'MEASUREMENT_UNAVAILABLE'
    return numeric, None


def eligible_flake_components(signal,eligible):
    """Recheck actual bright-island support after anatomical/hair exclusions."""
    count,labels,stats,_=cv2.connectedComponentsWithStats(((signal>.04)&eligible).astype(np.uint8))
    islands=np.zeros(signal.shape,bool)
    for label in range(1,count):
        x,y,w,h,pixels=stats[label]
        if 3<=pixels<=80 and .3<=w/max(h,1)<=3.3 and pixels/max(w*h,1)>.25:
            islands|=labels==label
    return signal*eligible*islands


def compute_dryness_signal(gray8, support_mask=None):
    """Shared, production dryness/flaking signal pipeline.
    Applies multi-scale DoG, uniform LBP filtering, local contrast gating,
    black-hat dark pore/filament ringing exclusion, and eligible bright island component filtering.
    Used identically by full-face analyze_skin and local ROI / patch benchmark evaluation.
    """
    gray = gray8.astype(np.float32) / 255.0
    high = gray - cv2.GaussianBlur(gray, (0, 0), 1.2)
    broad = cv2.GaussianBlur(gray, (0, 0), 0.7) - cv2.GaussianBlur(gray, (0, 0), 2.3)
    flakes = np.clip((high - 0.025) / 0.10, 0, 1) * np.clip((broad - 0.018) / 0.10, 0, 1)
    lbp = local_binary_pattern(gray8, 8, 1, 'uniform')
    flakes *= (lbp < 8)
    local_contrast = np.sqrt(np.maximum(0, cv2.GaussianBlur(gray * gray, (0, 0), 2) - cv2.GaussianBlur(gray, (0, 0), 2)**2))
    flakes *= ((local_contrast > 0.015) & (local_contrast < 0.14))

    # Exclude bright ringing around dark pores/hairs
    dark_ringing = cv2.dilate((cv2.morphologyEx(gray8, cv2.MORPH_BLACKHAT, np.ones((7, 7), np.uint8)) > 35).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    valid_support = np.ones(gray8.shape, bool) if support_mask is None else support_mask
    regional_flakes = eligible_flake_components(flakes, valid_support & ~dark_ringing)
    return regional_flakes, flakes, local_contrast, lbp, dark_ringing, high


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


def coherent_line_signal(signal,eligible):
    """Accept a connected local line spanning one coarsest Gabor period.

    The minimum span follows the configured filter wavelength, not a photo or
    score threshold. ROI/occlusion clipping precedes this check, so hidden
    eye/hair responses cannot supply the visible line's continuity.
    """
    count,labels,stats,_=cv2.connectedComponentsWithStats(((signal>0)&eligible).astype(np.uint8),8)
    minimum_span=int(np.ceil(1/min(LINE_FREQUENCIES)))
    ids=np.where((np.maximum(stats[:,cv2.CC_STAT_WIDTH],stats[:,cv2.CC_STAT_HEIGHT])>=minimum_span)&(np.arange(count)>0))[0]
    return np.where(np.isin(labels,ids),signal,0)


def isolated_impulse_sampling(source):
    """Remove only extreme native 1/2-pixel impulses for fold sampling.

    Resizing first spreads an isolated corrupt pixel into paired-edge support.
    Coherent lines, ordinary skin texture and the displayed photo stay intact.
    This is a photometric sampling contract, not a quality override.
    """
    gray=cv2.cvtColor(source,cv2.COLOR_BGR2GRAY)
    median=cv2.medianBlur(gray,3)
    suspect=np.abs(gray.astype(np.int16)-median.astype(np.int16))>255*.35
    count,labels,stats,_=cv2.connectedComponentsWithStats(suspect.astype(np.uint8),8)
    ids=np.where((stats[:,cv2.CC_STAT_AREA]<=2)&(np.arange(count)>0))[0]
    impulses=np.isin(labels,ids)
    if not impulses.any():return source,impulses
    sampled=source.copy()
    sampled[impulses]=cv2.medianBlur(source,3)[impulses]
    return sampled,impulses


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


def eye_skin_bands(points, shape, scale, origin, source_shape, by_side=False):
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
    sides={}
    for side,lower,corner,sign in [('right',[33,163,144,145,153,154,155,133],33,-1),('left',[263,390,373,374,380,381,382,362],263,1)]:
        local={k:np.zeros(shape,np.uint8) for k in result}
        line=p[lower]
        for criterion,top,bottom in [('dark',.012,.065),('bags',.022,.095)]:
            polygon=np.concatenate([line+down*face_width*top,(line+down*face_width*bottom)[::-1]])
            cv2.fillPoly(local[criterion],[np.rint(polygon).astype(np.int32)],255)
        c=p[corner];out=axis*sign*face_width
        polygon=np.asarray([c+out*.030-down*face_width*.035,c+out*.095-down*face_width*.040,
                            c+out*.095+down*face_width*.050,c+out*.030+down*face_width*.035])
        cv2.fillPoly(local['lines'],[np.rint(polygon).astype(np.int32)],255)
        sides[side]={k:v>0 for k,v in local.items()}
        for k,v in local.items():result[k]|=v
    return sides if by_side else {k:v>0 for k,v in result.items()}


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
    _, flakes, local_contrast, lbp, dark_ringing, high = compute_dryness_signal(gray8)
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
    band_sides=eye_skin_bands(points,gray.shape,scale,origin,bgr.shape,by_side=True)
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
    # A saturated red channel still carries green/blue skin detail. Only loss
    # of every colour channel is detector clipping; other criteria keep their gates.
    acne_clipping=np.min(rgb,axis=2)>.975
    acne_envelopes=region_envelopes(payload['meshes'],gray.shape,scale,origin)
    # Eye corners, lashes and brow boundaries are not lesion support. Include
    # their source-detail margin independently of gaps in the presentation mesh.
    ocular=np.zeros(gray.shape,np.uint8)
    for indices in [[33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246], [263,249,390,373,374,380,381,382,362,398,384,385,386,387,388,466]]:
        poly=np.asarray([[(points[i]['x']*width-x0)*scale,(points[i]['y']*bgr.shape[0]-y0)*scale] for i in indices],np.int32)
        cv2.fillPoly(ocular,[poly],255)
    eye_span=max(math.hypot((points[a]['x']-points[b]['x'])*width,(points[a]['y']-points[b]['y'])*bgr.shape[0]) for a,b in [(33,133),(263,362)])
    margin=max(1,int(round(eye_span*scale*.12)))
    acne_exclusion=exclusion|cv2.dilate(ocular,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(margin*2+1,margin*2+1)))
    # Brow landmark order is not a polygon contour. A crossing path leaves
    # gaps in actual brow tissue; its convex envelope needs no forehead margin.
    for indices in holes[4:]:
        poly=np.asarray([[(points[i]['x']*width-x0)*scale,(points[i]['y']*bgr.shape[0]-y0)*scale] for i in indices],np.float32)
        cv2.fillConvexPoly(acne_exclusion,cv2.convexHull(poly).astype(np.int32),255)
    acne_skin=(face_support>0)&(acne_exclusion==0)&~hair&~acne_clipping&(gray>.12)
    experimental_research_models=None
    if not include_research_features and payload.get('experimentalHostedSkinResearch') is True and payload.get('hostedResearchModelConsent') is True and payload.get('qualityValid') is True:
        rf_lesion=infer_lesion_large(bgr,True,experimental_opt_in=True)
        rf_oily=infer_regional_oily_seg(bgr,gray.shape,scale,origin,acne_skin,acne_exclusion,hair,True,experimental_opt_in=True)
        experimental_research_models={'mixedIntoProductMeasurements':False,'lesionLarge':{k:v for k,v in rf_lesion.items() if k!='boxes'},'regionalOilySeg':{k:v for k,v in rf_oily.items() if k!='mask'}}
    accepted_boxes={k:[] for k in masks}
    rejected_boxes=[]
    if trained_acne and trained_acne.get('valid'):
        assigned_boxes,rejected_boxes=filter_acne_boxes(trained_acne['boxes'],acne_envelopes,acne_skin,hair,acne_exclusion,source_hash,scale,origin)
        for reg_name,reg_list in assigned_boxes.items():
            for b in reg_list:
                b.update(modelVersion=trained_acne.get('modelVersion'),modelHash=trained_acne.get('modelHash'),pointSource='box_centroid',photoId=source_hash)
                if trained_acne.get('providerModelId'):b['providerModelId']=trained_acne['providerModelId']
        accepted_boxes.update(assigned_boxes)
    response, maps, contours = {}, {}, {}
    surface_masks={k:closed_surface_mask(gray.shape,m,scale,origin) for k,m in payload['meshes'].items()}
    luma_clipping=gray>.975  # Dry/sag use luminance detail, not color-channel fidelity.
    texture_visible=(exclusion==0)&~hair&~luma_clipping&(gray>.12)
    dry_union=np.logical_or.reduce(list(surface_masks.values()))&texture_visible
    shared_flakes=eligible_flake_components(flakes,dry_union&~dark_ringing)
    sag_samples={};sag_measured=np.zeros(gray.shape,bool);sag_field=np.zeros(gray.shape,np.float32)
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
        def target_quality(target, minimum_pixels):
            observed=exposure_support & target
            usable=valid & target
            limitation='CAPTURE_QUALITY' if not payload.get('qualityValid') else 'GLARE_OR_EXPOSURE' if observed.any() and float(clipping[observed].mean())>.03 else 'INSUFFICIENT_VISIBLE_AREA' if int(usable.sum())<minimum_pixels else None
            target_area=dict(sourcePixels=float(usable.sum()/scale**2),analysisPixels=int(usable.sum()),anatomicalSourcePixels=float((anatomical&target).sum()/scale**2),sourceFacePixels=float(face_pixels),scope='criterion-specific-anatomical-band')
            return limitation,target_area
        items = []
        def add(criterion, value, unit, signal=None, ceiling=1., limitation=reason, components=None, signal_mask=None,measurement_area=None,map_support=None):
            value, limitation = validated_measurement_value(value, limitation)
            usable = limitation is None
            item = row(region, criterion, value, unit, measurement_area if measurement_area is not None else area, conditions, limitation, components)
            item['photoId'] = source_hash
            item['capturePose'] = payload.get('pose', 'FRONT')
            if criterion=='sag' and components and components.get('formulaVersion'):
                item['normalizationVersion']=components['formulaVersion']
            items.append(item)
            if usable and signal is not None:
                layer = map_result(signal, (valid & display_anatomical if map_support is None else map_support) & (signal_mask if signal_mask is not None else True), region, criterion, source_hash, payload['pose'], bgr.shape, scale, unit, ceiling, origin)
                if layer:
                    if criterion=='oil':layer.update(normalizationVersion=NORMALIZATION['oil'],samplingSupportVersion=OIL_SAMPLING)
                    key=f'{region}:{criterion}';maps[key]=layer
                    # Descriptor only: the pixel/mask payload remains ephemeral
                    # in response.maps and never enters numeric history records.
                    item['localMap']=dict(key=key,photoId=source_hash,region=region,
                        criterion=criterion,coordinateSpace='source-pixels')
        if region != 'periorbital':
            tone,redness,color_components=local_color_signals(image,valid)
            add('tone',np.mean(tone[valid]) if valid.any() else 0,'relative-color-index-0-100',tone,100,components=tone_separation_components(color_components))
            add('redness',np.mean(redness[valid]) if valid.any() else 0,'relative-color-index-0-100',redness,100,components=color_components)
            add('oil', np.mean(shine[valid] > .12)*100 if valid.any() else 0, 'percent-visible-area', shine,
                components={'localIntensity': float(np.mean(shine[valid])) if valid.any() else None, 'clippedFraction': clipped,
                    'samplingSupportVersion':OIL_SAMPLING,'temporalPhotometryMeasured':False})
            # Small red center-surround candidates need circularity, texture and
            # multi-scale agreement. Dark moles/freckles and hair aren't acne evidence.
            boxes=[];candidate_area=np.zeros(gray.shape,bool)
            if include_research_features:
                for x,y,w,h,count,blob in assigned[region]:
                    candidate_area|=blob;boxes.append(dict(x=float(x/scale+x0),y=float(y/scale+y0),width=float(w/scale),height=float(h/scale),areaPixels=float(count/scale**2)))
            elif trained_acne and trained_acne.get('valid'):
                boxes=accepted_boxes[region]
                for box in boxes:
                    a=max(0,int((box['x']-x0)*scale));b=max(0,int((box['y']-y0)*scale));c=min(gray.shape[1],int(math.ceil((box['x']+box['width']-x0)*scale)));d=min(gray.shape[0],int(math.ceil((box['y']+box['height']-y0)*scale)));candidate_area[b:d,a:c]=True
            acne_valid=acne_envelopes.get(region,np.zeros_like(valid))&acne_skin if not include_research_features else valid
            observed=acne_envelopes.get(region,np.zeros_like(valid))&(face_support>0)&(exclusion==0)&~hair
            acne_reason=('CAPTURE_QUALITY' if not payload.get('qualityValid') else 'GLARE_OR_EXPOSURE' if observed.any() and acne_clipping[observed].mean()>.03 else 'INSUFFICIENT_VISIBLE_AREA' if acne_valid.sum()<100 else None) if not include_research_features else reason
            acne_reason=acne_reason or (None if include_research_features or trained_acne and trained_acne.get('valid') else (trained_acne or {}).get('reason','ACNE_MODEL_NOT_ACCEPTED'))
            if acne_reason:boxes=[];candidate_area[:]=False
            coverage=float(candidate_area[acne_valid].mean()*100) if acne_valid.any() else 0.
            acne_area={**area,'sourcePixels':float(acne_valid.sum()/scale**2),'analysisPixels':int(acne_valid.sum()),'anatomicalSourcePixels':float(acne_envelopes.get(region,anatomical).sum()/scale**2),'scope':ACNE_SUPPORT_VERSION}
            add('acne',coverage,'appearance-score-0-100',limitation=acne_reason,measurement_area=acne_area,components={'bounds':boxes,'candidateCount':len(boxes),'evaluatedArea':acne_area,'candidateBoxCoveragePercent':coverage,'normalization':'unique accepted detection-box pixels / visible anatomical source pixels *100','pixelSegmentation':False,'filterVersion':ACNE_SUPPORT_VERSION,'clinicalSeverity':False})
            if acne_reason is None and not include_research_features:
                signal=cv2.GaussianBlur(candidate_area.astype(np.float32),(0,0),2)*acne_valid
                layer=map_result(signal,acne_valid,region,'acne',source_hash,payload['pose'],bgr.shape,scale,'percent-visible-area',1.,origin)
                if layer:
                    layer.update(mapType='detection-box-support',method=ACNE_SUPPORT_VERSION,clinicalSeverity=False)
                    maps[region+':acne']=layer;items[-1]['localMap']=dict(key=region+':acne',photoId=source_hash,region=region,criterion='acne',coordinateSpace='source-pixels')
            if trained_acne and trained_acne.get('valid'):
                items[-1].update(modelVersion=trained_acne['modelVersion'],modelHash=trained_acne['modelHash']);items[-1]['components']['inference']= {k:trained_acne[k] for k in ('tileCount','loadMs','inferenceMs')}
        detail_reason = reason or ('INSUFFICIENT_SOURCE_DETAIL' if face_pixels < LIMITS['minFacePixels'] else None)
        # Compression around dark pores/hairs can create bright ringing. This
        # exclusion is specific to white flake evidence: round dark foci remain
        # available to the independent acne candidate detector.
        dry_valid=surface_masks[region]&texture_visible
        dry_exposed=surface_masks[region]&(exclusion==0)&~hair&(gray>.12)
        dry_reason='CAPTURE_QUALITY' if not payload.get('qualityValid') else 'GLARE_OR_EXPOSURE' if dry_exposed.any() and float(luma_clipping[dry_exposed].mean())>.03 else 'INSUFFICIENT_VISIBLE_AREA' if dry_valid.sum()<100 else 'INSUFFICIENT_SOURCE_DETAIL' if face_pixels<LIMITS['minFacePixels'] else None
        dry_area=dict(scope='shared-luma-visible-flake-support',sourcePixels=float(dry_valid.sum()/scale**2),analysisPixels=int(dry_valid.sum()),anatomicalSourcePixels=float(surface_masks[region].sum()/scale**2),sourceFacePixels=float(face_pixels))
        add('dry', np.mean(shared_flakes[dry_valid] > .04)*100 if dry_valid.any() else 0, 'percent-visible-area', shared_flakes,
            limitation=dry_reason, signal_mask=dry_valid,map_support=dry_valid,measurement_area=dry_area,components={'samplingSupportVersion':'shared-luma-closed-cell-flakes-v3','roughnessIndex':float(np.clip(np.mean(local_contrast[dry_valid])/.12*100,0,100)) if dry_valid.any() else None,
            'lbpNonUniformFraction':float(np.mean(lbp[dry_valid] == 9)) if dry_valid.any() else None,
            'meaning':'fine-bright-flaking-candidates; roughness alone is not dryness'})
        if region == 'periorbital':
            # Each eye owns its target quality and adjacent skin reference.
            # An occluded/clipped side stays unknown while the other can measure.
            def eye_measurement(criterion,minimum_pixels,field):
                signal=np.zeros(gray.shape,np.float32);observed=np.zeros(gray.shape,bool);sides=[]
                for side,local_bands in band_sides.items():
                    target=local_bands[criterion];under=valid&target
                    limitation,_=target_quality(target,minimum_pixels)
                    local=None
                    active_support=under
                    if limitation is None:
                        field_res=field(under)
                        if len(field_res)==3:
                            local,limitation,active_support=field_res
                        else:
                            local,limitation=field_res
                            active_support=under
                    if limitation is not None or active_support is None or not active_support.any():
                        value=None
                        analysis_pixels=int(active_support.sum()) if active_support is not None else 0
                    else:
                        value=float(np.mean(local[active_support]))
                        analysis_pixels=int(active_support.sum())
                        signal[active_support]=local[active_support]
                        observed|=active_support
                    sides.append(dict(side=side,value=value,limitationCode=limitation,analysisPixels=analysis_pixels))
                measured=[v for v in sides if v['value'] is not None]
                value=float(np.mean(signal[observed])) if (measured and observed.any()) else 0.
                limitation=None if measured else next((v['limitationCode'] for v in sides if v['limitationCode']),'ANATOMICAL_BAND_NOT_VISIBLE')
                target_area=dict(scope='measured-local-eye-target-bands',sourcePixels=float(observed.sum()/scale**2),analysisPixels=int(observed.sum()),anatomicalSourcePixels=float((anatomical&bands[criterion]).sum()/scale**2),sourceFacePixels=float(face_pixels),unknownSides=[v['side'] for v in sides if v['value'] is None])
                return value,signal,observed,limitation,target_area,dict(sides=sides,partialCoverage=len(measured)<len(sides),band=criterion)
            def dark_field(under):
                adjacent=cv2.dilate(under.astype(np.uint8),np.ones((25,25),np.uint8)).astype(bool)&~bands['dark']&(exclusion==0)&~clipping&~hair&(face_support>0)&(gray>.12)
                if adjacent.sum()<100:return None,'ADJACENT_SKIN_MISSING'
                ref_l=float(np.median(gray[adjacent]))
                rel_contrast=np.maximum(0.,(ref_l-gray)/max(ref_l,.1))
                # Deadband: normal healthy skin variance is 0-5%
                deadband=.05
                excess=np.maximum(0.,rel_contrast-deadband)
                # Chromatic verification: pigment/vascular dark circles shift CIELAB chroma (Delta-ab)
                lab_img=cv2.cvtColor(image,cv2.COLOR_BGR2LAB).astype(np.float32)
                chroma=lab_img[:,:,1:3]
                ref_chroma=np.median(chroma[adjacent],axis=0)
                delta_chroma=np.linalg.norm(chroma-ref_chroma,axis=2)
                # Pure shadow has minimal chroma shift; true pigment has elevated Delta-ab
                chroma_gate=np.clip((delta_chroma-1.0)/3.0,0.15,1.)
                signal=excess*chroma_gate*100.
                return signal,None
            value,dark,known,dark_reason,dark_area,dark_components=eye_measurement('dark',100,dark_field)
            add('dark',value,'relative-color-index-0-100',dark,100,limitation=dark_reason,signal_mask=known,measurement_area=dark_area,components=dark_components)
            lines_source,_=isolated_impulse_sampling(bgr)
            lines_image=cv2.resize(lines_source[y0:y1,x0:x1],None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
            lines_gray=cv2.cvtColor(lines_image,cv2.COLOR_BGR2GRAY).astype(np.float32)/255
            eye_axis=np.array([(points[263]['x']-points[33]['x'])*width,(points[263]['y']-points[33]['y'])*bgr.shape[0]])
            roll_rad=float(np.arctan2(eye_axis[1],eye_axis[0])) if np.linalg.norm(eye_axis)>1e-5 else 0.
            radiating_thetas=(np.pi/2+roll_rad-np.pi/6,np.pi/2+roll_rad,np.pi/2+roll_rad+np.pi/6)
            ortho_thetas=(roll_rad-np.pi/6,roll_rad,roll_rad+np.pi/6)
            rad_sig=np.zeros(gray.shape,np.float32)
            ortho_sig=np.zeros(gray.shape,np.float32)
            for frequency in LINE_FREQUENCIES:
                for theta in radiating_thetas:
                    real,imaginary=gabor(lines_gray,frequency=frequency,theta=theta)
                    rad_sig=np.maximum(rad_sig,np.hypot(real,imaginary))
                for theta in ortho_thetas:
                    real,imaginary=gabor(lines_gray,frequency=frequency,theta=theta)
                    ortho_sig=np.maximum(ortho_sig,np.hypot(real,imaginary))
            ratio=rad_sig/np.maximum(ortho_sig,0.005)
            dir_gate=np.clip((ratio-1.22)/0.35,0.,1.)
            lines=np.clip((rad_sig-0.0125)/0.055,0.,1.)*dir_gate
            hair_margin=cv2.dilate(hair.astype(np.uint8),np.ones((5,5),np.uint8))>0
            def line_field(under):
                valid_line=under & ~hair_margin
                if valid_line.sum()<20:return None,'HAIR_OR_OCCLUSION_IN_LINE_BAND',valid_line
                med_l=float(np.median(gray[valid_line]))
                skin_support=valid_line & (gray>=med_l*0.50)
                if skin_support.sum()<20:return None,'HAIR_OR_OCCLUSION_IN_LINE_BAND',skin_support
                return (None,'INSUFFICIENT_SOURCE_DETAIL',skin_support) if face_pixels<LIMITS['minFacePixels'] else (coherent_line_signal(lines,skin_support)*100,None,skin_support)
            value,line_signal,known,lines_reason,lines_area,line_components=eye_measurement('lines',75,line_field)
            line_components['samplingSupportVersion']='native-impulse-one-cycle-lines-v1'
            line_components['photometricSamplingVersion']='native-isolated-impulse-median-v1'
            line_components['lineSupportVersion']='connected-local-one-coarsest-period-v1'
            raw_line_paths=measured_line_paths(rad_sig*dir_gate,known,0.0125) if lines_reason is None else []
            source_line_paths=[{**lp,'points':[{'x':round(float(pt['x']/scale+x0),1),'y':round(float(pt['y']/scale+y0),1)} for pt in lp['points']]} for lp in raw_line_paths]
            line_components['linePaths']=source_line_paths
            add('lines',value,'directional-line-index-0-100',line_signal/100,limitation=lines_reason,signal_mask=known,measurement_area=lines_area,components=line_components)
            if 'periorbital:lines' in maps:maps['periorbital:lines']['linePaths']=source_line_paths
        if region != 'nose':
            contour_support=base&~clipping&(gray>.12)
            contour_gray=gray
            contour_clipping=clipping
            contour_context=(face_support>0)&(exclusion==0)&~clipping&(gray>.12)
            contour_exposure=(face_support>0)&(exclusion==0)&~hair&(gray>.12)
            if region in ('rightCheek','leftCheek','chin'):
                contour_support=surface_masks[region]&texture_visible
                contour_clipping=luma_clipping
                contour_context=(face_support>0)&texture_visible
                contour_exposure=(face_support>0)&(exclusion==0)&~hair&(gray>.12)
            if region=='periorbital':
                bag_anatomical=bag_support_mask(gray.shape,payload['meshes'][region],scale,origin)
                contour_support=bag_anatomical&(exclusion==0)&~clipping&(gray>.12)&bands['bags']&~hair
                sampled,impulses=isolated_impulse_sampling(bgr)
                bag_image=cv2.resize(sampled[y0:y1,x0:x1],None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
                contour_gray=cv2.cvtColor(bag_image,cv2.COLOR_BGR2GRAY).astype(np.float32)/255
            value,components,signal,lines,limitation=instant_proxy(contour_gray,contour_support,points,region,conditions,scale,origin,bgr.shape,hair,contour_context,contour_clipping,contour_exposure,boundary_geometry=(face_support>0) if region=='chin' else None,expression_observation=payload.get('expressionObservation'),photo_id=source_hash,capture_pose=payload['pose'])
            local_samples=components.pop('_samplingCenters',[])
            local_measured=components.pop('_measuredSupport',None)
            if region in ('rightCheek','leftCheek','chin') and value is not None and payload.get('qualityValid'):
                for x,y,intensity in local_samples:sag_samples[(x,y)]=max(sag_samples.get((x,y),0),intensity)
                if local_measured is not None:sag_measured|=local_measured
                sag_field=np.maximum(sag_field,signal)
            if region=='periorbital':
                components['samplingSupportVersion']='tracked-center-closed-cells-impulse-v3' if payload['meshes'][region].get('bagCells') else 'tracked-center-eligible-impulse-v3'
                components['photometricSamplingVersion']='native-isolated-impulse-median-v1'
            criterion = 'bags' if region == 'periorbital' else 'sag'
            used_bag_mask=False
            if region=='periorbital' and trained_bags and not trained_bags.get('valid'):
                value=None;signal=None;lines=[]
                limitation=trained_bags.get('reason','ACCEPTED_MODEL_UNAVAILABLE')
                components={'acceptedModelFailed':True,'analyticSubstitutionBlocked':True}
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
            # Sag has its own lower-face sampling-corridor quality. Capture
            # validity is still required; exposure/visibility stay local per side.
            contour_reason=(('CAPTURE_QUALITY' if not payload.get('qualityValid') else None) or limitation) if criterion in ['sag','bags'] else reason or limitation
            add(criterion,value,INSTANT_UNIT,signal,limitation=contour_reason,components=components,measurement_area=components.get('measurementROI',area),map_support=contour_support if region in ('rightCheek','leftCheek','chin','periorbital') and not used_bag_mask else None)
            if used_bag_mask and value is not None:
                items[-1].update(modelVersion=trained_bags['modelVersion'],modelHash=trained_bags['modelHash'],unit='appearance-score-0-100',normalizationVersion='predicted-lower-lid-mask-area-v1')
                if 'periorbital:bags' in maps:maps['periorbital:bags'].update(mapType='predicted-presence-mask',unit='appearance-score-0-100',method=trained_bags['modelVersion'],modelHash=trained_bags['modelHash'])
            if value is not None and contour_reason is None and lines:
                contours[region]=dict(points=lines[0],lines=lines,features=[])
        response[region]=items
    result=dict(methodVersion=VERSION,photoId=source_hash,measurements=response,maps=maps,contours=contours,
                storage='volatile-memory-only',sourceWidth=bgr.shape[1],sourceHeight=bgr.shape[0])
    if trained_acne and trained_acne.get('valid'):
        all_acne_boxes=[b for r_list in accepted_boxes.values() for b in r_list]
        result['acneCandidates']={**accepted_boxes,'overview':all_acne_boxes}
        result['lesionRuntime']=dict(modelVersion=trained_acne.get('modelVersion'),providerModelId=trained_acne.get('providerModelId'),modelHash=trained_acne.get('modelHash'),acceptedCount=len(all_acne_boxes),rejectedAnatomyOrThresholdCount=len(rejected_boxes)+len(trained_acne.get('rejected',[])),thresholds=trained_acne.get('thresholds'))
    if experimental_research_models:
        result['experimentalResearchModels']=experimental_research_models
    if payload['pose']=='FRONT':
        union=np.logical_or.reduce(list(masks.values()))&(exclusion==0)&~hair&~clipping&(gray>.12)
        general_tone,general_redness,_=local_color_signals(image,union)
        general_area=dict(sourcePixels=float(union.sum()/scale**2),anatomicalSourcePixels=float(np.logical_or.reduce(list(masks.values())).sum()/scale**2),analysisPixels=int(union.sum()),sourceFacePixels=float(face_pixels))
        # Whole-face dryness uses the same valid bright-island support as the
        # regional rows. Compression ringing is never restored by unioning ROIs.
        general_flakes=shared_flakes
        measured_dry=[surface_masks[name] for name,rows in response.items() if any(r['id']=='dry' and r['quality']=='valid' for r in rows)]
        dry_union=(np.logical_or.reduce(measured_dry) if measured_dry else np.zeros_like(dry_union))&texture_visible
        global_candidates=np.zeros(gray.shape,bool)
        if include_research_features:
            for detection in detections:global_candidates|=detection[-1]
        elif trained_acne and trained_acne.get('valid'):
            final_boxes=[box for items in response.values() for item in items if item['id']=='acne' and item['quality']=='valid' for box in item['components']['bounds']]
            global_candidates=box_area(final_boxes,gray.shape,scale,origin)
        oil_union,_=oil_region_support(response,masks,union)
        result['general']=general_result(response,masks,union,general_tone,general_redness,shine,general_flakes,
            general_area,conditions,payload.get('qualityValid',False),candidate_coverage=float(np.mean(global_candidates[union])*100) if union.any() else None,normalizations=NORMALIZATION,dry_support=dry_union,sag_support=(sag_samples,sag_measured,scale),analysis_scale=scale)
        for item in result['general']['measurements']:
            item['scoreDirection']='higher-is-more-visible'
            if item['id'] in NORMALIZATION:
                item['normalizationVersion']=NORMALIZATION[item['id']]+('-expression-v3-observed-pose' if item['id']=='sag' else '')
            if item['id']=='acne' and item['value'] is not None and not include_research_features:
                measured=[name for name,rows in response.items() if any(r['id']=='acne' and r['quality']=='valid' for r in rows)]
                support=np.logical_or.reduce([acne_envelopes[name]&acne_skin for name in measured])
                item['value']=float(global_candidates[support].mean()*100) if support.any() else None
                item['evaluatedArea']={'scope':ACNE_SUPPORT_VERSION,'sourcePixels':float(support.sum()/scale**2),'analysisPixels':int(support.sum())}
                item['components'].update(visibleCandidateAreaPercent=item['value'],filterVersion=ACNE_SUPPORT_VERSION,clinicalSeverity=False,pixelSegmentation=False)
                layer=map_result(cv2.GaussianBlur(global_candidates.astype(np.float32),(0,0),2)*support,support,'overview','acne',source_hash,'FRONT',bgr.shape,scale,'percent-visible-area',1.,origin)
                if layer:
                    layer.update(mapType='detection-box-support',method=ACNE_SUPPORT_VERSION,clinicalSeverity=False)
                    maps['overview:acne']=layer;item['localMap']=dict(key='overview:acne',photoId=source_hash,region='overview',criterion='acne',coordinateSpace='source-pixels')
            if item['id']=='bags' and trained_bags and trained_bags.get('valid') and item['modelHash']==trained_bags['modelHash']:item['normalizationVersion']='predicted-lower-lid-mask-area-v1'
        if not include_research_features:
            type_quality=payload.get('qualityValid') is True and face_pixels>=180 and abs(conditions.get('yaw',99))<=.65
            learned=infer_skin_models(bgr,points,result['general']['measurements'][0]['quality']=='valid' and face_pixels>=180,hosted_consent=payload.get('hostedProcessingConsent') is True,type_quality_valid=type_quality)
            # Keep the model output intact. Product-native replacements run
            # after this shared analyzer; only the product endpoint finalizes
            # the regional combination decision against those final rows.
            if learned['skinType']:result['general']['skinType']=learned['skinType']
            result['general']['modelInference']=learned.get('models',{})
            result['general']['modelRuntime']=learned.get('modelRuntime',{})
            result['general']['modelInputTransform']=learned.get('sourceTransform')
            for item in result['general']['measurements']:
                degree=learned['degrees'].get(item['id'])
                if item['id'] in learned.get('unavailableTargets',[]):
                    item.update(value=None,quality='insufficient',limitationCode=learned['failure'],localMap=None)
                    item['components'].update(acceptedModelFailed=True,analyticSubstitutionBlocked=True)
                # Acne card and source marks remain the same accepted detector
                # candidates. A whole-photo acne grade is not a calibrated
                # fusion with detection-box coverage and cannot replace it.
                if degree and item['id']!='acne':
                    # Generic degree heads are whole-photo ordinal outputs. The
                    # shared contract blocks them from replacing localized sag
                    # contour/fold evidence or inheriting its analytic map.
                    apply_learned_general_degree(item,degree)
        if include_research_features:
            # Offline train/validation comparison only. The normal API never
            # requests or persists these alternatives or uses them as scores.
            oil_usable=next(r for r in result['general']['measurements'] if r['id']=='oil')['quality']=='valid'
            result['researchFeatures']={'oil-baseline':float(np.mean((baseline_oil>0)[union])*100) if union.any() and oil_usable else None}
        for criterion,signal,ceiling in [('tone',general_tone,100),('redness',general_redness,100),('oil',shine,1),('dry',general_flakes,1)]:
            measurement=next(r for r in result['general']['measurements'] if r['id']==criterion)
            # A whole-photo ordinal grade has no pixel severity localization.
            # Do not attach an analytic field under that grade's calibration.
            if measurement['value'] is not None and measurement['components'].get('modelScope')!='whole-face':
                layer=map_result(signal,oil_union if criterion=='oil' else dry_union if criterion=='dry' else union,'overview',criterion,source_hash,'FRONT',bgr.shape,scale,measurement['unit'],ceiling,origin)
                if layer:
                    if criterion=='oil':layer.update(normalizationVersion=NORMALIZATION['oil'],samplingSupportVersion=OIL_SAMPLING)
                    maps['overview:'+criterion]=layer
                    measurement['localMap']=dict(key='overview:'+criterion,photoId=source_hash,region='overview',criterion=criterion,coordinateSpace='source-pixels')
        sag_overview=next(r for r in result['general']['measurements'] if r['id']=='sag')
        if sag_overview['value'] is not None and sag_measured.any() and sag_overview['components'].get('modelScope')!='whole-face':
            layer=map_result(sag_field,sag_measured,'overview','sag',source_hash,'FRONT',bgr.shape,scale,INSTANT_UNIT,1.,origin)
            if layer:
                maps['overview:sag']=layer
                sag_overview['localMap']=dict(key='overview:sag',photoId=source_hash,region='overview',criterion='sag',coordinateSpace='source-pixels')
        for criterion in ['dark','lines','bags']:
            layer=maps.get('periorbital:'+criterion)
            if layer:maps['overview:'+criterion]={**layer,'region':'overview'}
    result['modelRuntime']=result.get('general',{}).get('modelRuntime') or session_status(reason='NON_FRONT_PAYLOAD' if payload.get('pose')!='FRONT' else 'not-used')
    return attach_result_receipts(result)
