"""Optional, accepted photo-only ONNX models. No download, training or pickle.

Models are pinned by a bundled manifest. RGB source/crop stays independent of
presentation zoom; all learned degrees are global, never local severity masks.
"""
from functools import lru_cache
from pathlib import Path
import hashlib,json,threading,time
import cv2,numpy as np

FOLDER=Path(__file__).parent/'models'
MANIFEST=FOLDER/'skin-focused.json'
CLASSES=['normal','dry','oily','combination']
MEAN=np.array([.485,.456,.406],np.float32)[:,None,None]
STD=np.array([.229,.224,.225],np.float32)[:,None,None]
LOCK=threading.Lock()

def photo_input(bgr,points):
    p=np.array([[v['x'],v['y']] for v in points[:468]],np.float64)
    if p.shape!=(468,2) or not np.isfinite(p).all():raise ValueError('INVALID_MODEL_LANDMARKS')
    h,w=bgr.shape[:2];lo=p.min(0);hi=p.max(0);size=hi-lo
    start=np.maximum(0,lo-size*[.32,.35]);end=np.minimum(1,hi+size*[.32,.16])
    x,y=np.floor(start*[w,h]).astype(int);x1,y1=np.ceil(end*[w,h]).astype(int)
    if not 0<=x<x1<=w or not 0<=y<y1<=h:raise ValueError('INVALID_MODEL_CROP')
    rgb=cv2.resize(bgr[y:y1,x:x1,::-1],(224,224),interpolation=cv2.INTER_AREA)
    value=((rgb.transpose(2,0,1).astype(np.float32)/255-MEAN)/STD)[None].copy()
    return value,dict(x=int(x),y=int(y),width=int(x1-x),height=int(y1-y),inputWidth=224,inputHeight=224,RGB=True,cropVersion='camera-crop-v1',coordinateSpace='source-pixels')

@lru_cache(maxsize=1)
def load():
    if not MANIFEST.exists():return {'manifest':None,'sessions':{}}
    import onnxruntime as ort
    manifest=json.loads(MANIFEST.read_text('utf8'));assert manifest['classOrder']==CLASSES
    assert manifest['preprocessing']=={'RGB':True,'size':[224,224],'mean':[.485,.456,.406],'std':[.229,.224,.225],'cropVersion':'camera-crop-v1'}
    sessions={};options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    for task,m in manifest.get('models',{}).items():
        if not (m.get('accepted') or m.get('candidateAccepted')):continue
        path=FOLDER/m['file'];assert path.resolve().parent==FOLDER.resolve() and path.suffix=='.onnx'
        assert hashlib.sha256(path.read_bytes()).hexdigest()==m['sha256'],'MODEL_HASH_MISMATCH'
        start=time.perf_counter();session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);sessions[task]={'session':session,'loadMs':(time.perf_counter()-start)*1000,'metadata':m}
    return {'manifest':manifest,'sessions':sessions}

def parse_hosted_type_response(data, model_id, elapsed=0.0):
    """Robust, tested parser for Roboflow classification responses.
    Handles:
    - predictions as list of dicts: [{'class': 'dry', 'confidence': 0.84}, ...]
    - predictions as flat dict: {'dry': 0.84, 'normal': 0.16}
    - predictions as nested dict: {'dry': {'confidence': 0.84}, 'normal': {'confidence': 0.16}}
    - Top/confidence consistency checking against predictions
    - Multi-label vs single-label separation (rejects multi-label multi-active classifications)
    - Rejection of unknown classes, non-finite/out-of-range confidences, inconsistent outputs
    """
    import math
    if not isinstance(data, dict):
        return None
    
    # Check multi-label declaration if present
    multi_label = data.get('multi_label') or data.get('multilabel') or False
    
    candidates = {}
    preds = data.get('predictions')
    
    if isinstance(preds, list):
        for p in preds:
            if isinstance(p, dict):
                c = str(p.get('class', '')).strip().lower()
                conf = p.get('confidence')
                # Handle nested confidence inside dict item if needed
                if isinstance(conf, dict):
                    conf = conf.get('confidence')
                if c in CLASSES and conf is not None:
                    try:
                        f_conf = float(conf)
                        if math.isfinite(f_conf) and 0.0 <= f_conf <= 1.0:
                            candidates[c] = f_conf
                    except (TypeError, ValueError):
                        pass
    elif isinstance(preds, dict):
        for c, val in preds.items():
            c_clean = str(c).strip().lower()
            if c_clean not in CLASSES:
                continue
            conf = val
            if isinstance(val, dict):
                conf = val.get('confidence')
            if conf is not None:
                try:
                    f_conf = float(conf)
                    if math.isfinite(f_conf) and 0.0 <= f_conf <= 1.0:
                        candidates[c_clean] = f_conf
                except (TypeError, ValueError):
                    pass

    # Top-level 'top' and 'confidence'
    top_c = str(data.get('top', '')).strip().lower() if 'top' in data and data.get('top') is not None else None
    top_conf = None
    if 'confidence' in data and data.get('confidence') is not None:
        try:
            f_top_conf = float(data['confidence'])
            if math.isfinite(f_top_conf) and 0.0 <= f_top_conf <= 1.0:
                top_conf = f_top_conf
        except (TypeError, ValueError):
            pass

    # Consistency check: If both top and predictions exist, top must match argmax of predictions
    if candidates:
        best_pred_class = max(candidates, key=candidates.get)
        best_pred_conf = candidates[best_pred_class]
        
        # Check for multi-label conflict:
        # If explicitly multi-label or multiple classes have high independent confidence (e.g. >0.65 each)
        # whose sum significantly exceeds 1.05, single-label 4-class classification contract is violated.
        high_conf_classes = [c for c, conf in candidates.items() if conf >= 0.60]
        if multi_label or len(high_conf_classes) > 1 or sum(candidates.values()) > 1.35:
            # Multi-label output cannot be blindly argmaxed into a single skin type
            return dict(
                value=None,
                quality='insufficient',
                confidence=best_pred_conf,
                methodVersion=f'hosted-roboflow-{model_id}',
                providerModelId=model_id,
                modelHash=None,
                limitationCode='MULTI_LABEL_CONFLICT',
                inferenceMs=elapsed
            )

        if top_c is not None:
            if top_c != best_pred_class:
                # Top declaration contradicts predictions list
                return None
            if top_conf is not None and abs(top_conf - best_pred_conf) > 0.05:
                # Top confidence contradicts predictions confidence
                return None

        best_class = best_pred_class
        best_conf = best_pred_conf
    elif top_c in CLASSES and top_conf is not None:
        best_class = top_c
        best_conf = top_conf
    else:
        return None

    valid = best_conf >= 0.50
    return dict(
        value=best_class if valid else None,
        quality='valid' if valid else 'insufficient',
        confidence=best_conf,
        methodVersion=f'hosted-roboflow-{model_id}',
        providerModelId=model_id,
        modelHash=None,  # Hosted weights SHA cannot be known; never fake weight hash
        limitationCode=None if valid else 'LOW_MODEL_SUPPORT',
        inferenceMs=elapsed
    )

def get_inference_client(api_key):
    """Factory for official Roboflow InferenceHTTPClient with header authentication and disabled uncontrolled retries."""
    from inference_sdk import InferenceConfiguration, InferenceHTTPClient
    client = InferenceHTTPClient(
        api_url="https://serverless.roboflow.com",
        api_key=api_key
    )
    client.configure(InferenceConfiguration(api_key_transport="header", workflow_run_retries_enabled=False))
    return client

def infer_hosted_type(crop_bgr):
    """Authorized hosted 4-class skin type adapter via official Roboflow Serverless Inference SDK.
    Only called if local accepted ONNX weights are not present and ATTUNE_ALLOW_HOSTED_INFERENCE=1 is explicitly set.
    Never sends full unapproved photos; operates solely on cropped face patch.
    Uses official inference-sdk with header authentication (never leaks credentials in URL, logs or errors).
    """
    import os
    model_id = os.environ.get('ATTUNE_SKIN_TYPE_MODEL', 'skin-type-axavj/1')

    # 1. Explicit permission guard: Key presence alone is NOT consent to transmit face data
    if os.environ.get('ATTUNE_ALLOW_HOSTED_INFERENCE') != '1':
        return dict(
            value=None,
            quality='insufficient',
            confidence=None,
            methodVersion=f'hosted-roboflow-{model_id}',
            providerModelId=model_id,
            modelHash=None,
            limitationCode='HOSTED_INFERENCE_PERMISSION_DENIED',
            inferenceMs=0.0
        )

    # 2. Check credentials
    api_key = os.environ.get('ATTUNE_ROBOFLOW_API_KEY') or os.environ.get('ROBOFLOW_API_KEY')
    if not api_key:
        return dict(
            value=None,
            quality='insufficient',
            confidence=None,
            methodVersion=f'hosted-roboflow-{model_id}',
            providerModelId=model_id,
            modelHash=None,
            limitationCode='HOSTED_CREDENTIALS_MISSING',
            inferenceMs=0.0
        )

    # 3. Call official SDK with controlled timeout and error differentiation
    try:
        from inference_sdk.http.errors import HTTPCallErrorError, HTTPClientError
        client = get_inference_client(api_key)
        start = time.perf_counter()
        data = client.infer(crop_bgr, model_id=model_id)
        elapsed = (time.perf_counter() - start) * 1000
        parsed = parse_hosted_type_response(data, model_id, elapsed)
        if parsed is None:
            return dict(
                value=None,
                quality='insufficient',
                confidence=None,
                methodVersion=f'hosted-roboflow-{model_id}',
                providerModelId=model_id,
                modelHash=None,
                limitationCode='HOSTED_INVALID_RESPONSE',
                inferenceMs=elapsed
            )
        return parsed
    except Exception as e:
        # Categorize errors safely without leaking credentials
        limitation = 'HOSTED_CALL_FAILED'
        err_str = str(e).lower()
        status_code = getattr(e, 'status_code', None)
        if status_code in (401, 403):
            limitation = 'HOSTED_AUTH_FAILED'
        elif status_code == 429:
            limitation = 'HOSTED_RATE_LIMIT_EXCEEDED'
        elif status_code == 404:
            limitation = 'HOSTED_MODEL_NOT_FOUND'
        elif 'timeout' in err_str or 'timed out' in err_str:
            limitation = 'HOSTED_TIMEOUT'
        elif 'connection' in err_str or 'network' in err_str or 'connect' in err_str:
            limitation = 'HOSTED_NETWORK_ERROR'
            
        return dict(
            value=None,
            quality='insufficient',
            confidence=None,
            methodVersion=f'hosted-roboflow-{model_id}',
            providerModelId=model_id,
            modelHash=None,
            limitationCode=limitation,
            inferenceMs=0.0
        )

VIT_CLASSES = ['dry', 'normal', 'oily']
FOREHEAD_INDICES = [103, 67, 109, 10, 338, 297, 332, 54, 104, 108, 151, 337, 333, 284, 21, 63, 66, 9, 296, 293, 251]
NOSE_INDICES = [67, 109, 10, 338, 297, 104, 108, 151, 337, 333, 63, 66, 9, 296, 293, 193, 168, 417, 122, 6, 351, 196, 197, 419, 3, 195, 248, 126, 51, 5, 281, 355, 129, 49, 4, 279, 358, 209, 48, 1, 278, 429, 102, 98, 2, 327, 331]
LEFT_CHEEK_INDICES = [340, 346, 348, 329, 352, 280, 266, 371, 376, 411, 425, 423, 361, 427, 436, 426, 288, 435, 416, 432, 397, 367, 434, 422]
RIGHT_CHEEK_INDICES = [111, 117, 119, 100, 123, 50, 36, 142, 147, 187, 205, 203, 132, 207, 216, 206, 58, 215, 192, 212, 172, 138, 214, 202]
T_ZONE_INDICES = FOREHEAD_INDICES + NOSE_INDICES
CHEEK_INDICES = RIGHT_CHEEK_INDICES + LEFT_CHEEK_INDICES

HOLES_INDICES = [
    [33, 160, 158, 133, 153, 144],  # right eye
    [263, 387, 385, 362, 380, 373],  # left eye
    [61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91],  # lips
    [98, 97, 2, 326, 327, 294],  # nostrils
    [70, 63, 105, 66, 69, 107, 55, 65, 52],  # right brow
    [300, 293, 334, 296, 299, 336, 285, 295, 282]  # left brow
]

def preprocess_vit_face(bgr, transform=None):
    """Unified ViT preprocessing adhering to preprocessor_config.json:
    Crop according to transform (if provided) -> BGR to RGB ->
    PIL.Image.Resampling.BILINEAR resize to (224, 224) ->
    normalize with mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5] ->
    returns float32 array with shape (1, 3, 224, 224).
    """
    from PIL import Image
    if transform is not None:
        x, y = int(transform['x']), int(transform['y'])
        w, h = int(transform['width']), int(transform['height'])
        crop_bgr = bgr[y:y+h, x:x+w]
    else:
        crop_bgr = bgr
    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    pil_resized = pil_img.resize((224, 224), resample=Image.Resampling.BILINEAR)
    arr = np.array(pil_resized, dtype=np.float32) / 255.0
    normed = (arr - 0.5) / 0.5
    tensor = normed.transpose(2, 0, 1)[None, ...].astype(np.float32)
    return tensor

def build_anatomical_skin_masks(shape, points, min_pixels=80):
    """Constructs anatomically isolated forehead, nose, left cheek, and right cheek masks.
    Subtracts eyes, lips, nostrils, and eyebrows.
    Guarantees no cheek bridging across nose or mouth.
    Returns: masks_dict, valid_support (bool), reason (str or None).
    """
    if not points or len(points) < 468:
        return {}, False, 'INSUFFICIENT_VISIBLE_AREA'
    h, w = shape[:2]
    def poly_mask(indices):
        pts = np.array([[int(points[i]['x'] * w), int(points[i]['y'] * h)] for i in indices if i < len(points)], np.int32)
        m = np.zeros((h, w), np.uint8)
        if len(pts) >= 3:
            cv2.fillConvexPoly(m, cv2.convexHull(pts), 255)
        return m

    fh_m = poly_mask(FOREHEAD_INDICES)
    nose_m = poly_mask(NOSE_INDICES)
    lc_m = poly_mask(LEFT_CHEEK_INDICES)
    rc_m = poly_mask(RIGHT_CHEEK_INDICES)

    holes_m = np.zeros((h, w), np.uint8)
    for h_indices in HOLES_INDICES:
        h_pts = np.array([[int(points[i]['x'] * w), int(points[i]['y'] * h)] for i in h_indices if i < len(points)], np.int32)
        if len(h_pts) >= 3:
            cv2.fillPoly(holes_m, [h_pts], 255)

    not_holes = cv2.bitwise_not(holes_m)
    fh_m = cv2.bitwise_and(fh_m, not_holes)
    nose_m = cv2.bitwise_and(nose_m, not_holes)
    lc_m = cv2.bitwise_and(lc_m, not_holes)
    rc_m = cv2.bitwise_and(rc_m, not_holes)

    t_mask = cv2.bitwise_or(fh_m, nose_m)
    cheeks_mask = cv2.bitwise_or(lc_m, rc_m)

    t_px = np.count_nonzero(t_mask)
    lc_px = np.count_nonzero(lc_m)
    rc_px = np.count_nonzero(rc_m)

    valid_support = (t_px >= min_pixels and lc_px >= min_pixels // 2 and rc_px >= min_pixels // 2)
    reason = None if valid_support else 'INSUFFICIENT_VISIBLE_AREA'

    masks = {
        'forehead': fh_m,
        'nose': nose_m,
        'left_cheek': lc_m,
        'right_cheek': rc_m,
        't_zone': t_mask,
        'cheeks': cheeks_mask,
        'holes': holes_m
    }
    return masks, valid_support, reason

def regional_combination_rule(bgr, points, p_vit, clipping_gate=0.15):
    """Explainable Regional Combination (Karma) Rule v2.
    Evaluates spatial sebum divergence between T-zone and cheeks.
    Requires significant deadband (spec_diff >= 0.40), elevated T-zone sebum,
    and matte/balanced cheeks.
    Clipping is strictly computed on observed skin support, not whole image background.
    """
    p_dry, p_norm, p_oil = [float(v) for v in p_vit]
    base_idx = int(np.argmax(p_vit))
    base_class = VIT_CLASSES[base_idx]
    base_conf = float(p_vit[base_idx])

    masks, valid_support, reason = build_anatomical_skin_masks(bgr.shape, points)
    if not valid_support:
        return base_class, None, False, 'INSUFFICIENT_VISIBLE_AREA', {
            'isKarma': False,
            'basis': 'INSUFFICIENT_VISIBLE_AREA',
            'reason': reason,
            'modelProbs': {'dry': round(p_dry, 4), 'normal': round(p_norm, 4), 'oily': round(p_oil, 4)}
        }

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    v = hsv[:, :, 2] / 255.0
    sat = hsv[:, :, 1] / 255.0

    t_mask = masks['t_zone']
    u_mask = masks['cheeks']
    skin_mask = (t_mask > 0) | (u_mask > 0)

    # Evaluate clipping solely on observed facial skin pixels
    skin_v = v[skin_mask]
    clipping = float(np.mean(skin_v > 0.975)) if len(skin_v) > 0 else 0.0
    if clipping > clipping_gate:
        return base_class, None, False, 'GLARE_OR_EXPOSURE', {
            'isKarma': False,
            'basis': 'GLARE_OR_EXPOSURE',
            'clipping': round(clipping, 4),
            'skinPixels': int(len(skin_v)),
            'modelProbs': {'dry': round(p_dry, 4), 'normal': round(p_norm, 4), 'oily': round(p_oil, 4)}
        }

    local_v = cv2.GaussianBlur(v, (0, 0), 15)
    spec = np.clip(v - local_v * 0.96, 0, 1) * np.clip(1.0 - sat, 0, 1)

    t_spec = float(np.mean(spec[t_mask > 0]) * 100) if (t_mask > 0).any() else 0.0
    u_spec = float(np.mean(spec[u_mask > 0]) * 100) if (u_mask > 0).any() else 0.0
    spec_diff = t_spec - u_spec

    deadband_met = spec_diff >= 0.40
    t_zone_supported = t_spec >= 1.80
    cheeks_matte = u_spec < 4.00

    is_karma = False
    basis = 'FULL_FACE_MODEL_CLASSIFICATION'

    if deadband_met and t_zone_supported and cheeks_matte:
        if p_oil >= 0.28 and (p_dry + p_norm) >= 0.50:
            is_karma = True
            basis = 'SPATIAL_DIVERGENCE_T_OILY_CHEEK_BALANCED'
        elif base_class == 'oily' and spec_diff >= 0.60 and u_spec < 2.50:
            is_karma = True
            basis = 'SPATIAL_DIVERGENCE_CHEEKS_BELOW_T_ZONE'
        elif base_class == 'normal' and p_oil >= 0.32 and spec_diff >= 0.50:
            is_karma = True
            basis = 'SPATIAL_DIVERGENCE_T_ZONE_ELEVATED'
    else:
        if 0.0 < spec_diff < 0.40:
            basis = 'REJECTED_INSUFFICIENT_DEADBAND'
        elif not t_zone_supported:
            basis = 'REJECTED_LOW_T_ZONE_SEBUM'
        elif not cheeks_matte:
            basis = 'REJECTED_UNIFORM_FACIAL_SHINE'

    if is_karma:
        final_class = 'combination'
        contrast = min(1.0, spec_diff / 1.5)
        matte = max(0.0, 1.0 - u_spec / max(t_spec, 1e-3))
        final_conf = round(float(np.clip(p_oil * 0.40 + contrast * 0.35 + matte * 0.25, 0.40, 0.88)), 4)
    else:
        final_class = base_class
        final_conf = base_conf

    div_info = {
        'isKarma': is_karma,
        'basis': basis,
        'tZoneSpecularity': round(t_spec, 2),
        'cheekSpecularity': round(u_spec, 2),
        'specularDivergence': round(spec_diff, 2),
        'clipping': round(clipping, 4),
        'deadbandMet': deadband_met,
        'tZoneSupported': t_zone_supported,
        'cheeksMatte': cheeks_matte,
        'modelProbs': {'dry': round(p_dry, 4), 'normal': round(p_norm, 4), 'oily': round(p_oil, 4)},
        'combinationConfidence': final_conf if is_karma else None
    }
    return final_class, final_conf, True, None, div_info

def infer(bgr,points,quality_valid,hosted_consent=True,type_quality_valid=None):
    empty=dict(skinType=None,degrees={},models={},sourceTransform=None)
    can_run_degrees = bool(quality_valid)
    can_run_type = bool(type_quality_valid) if type_quality_valid is not None else bool(quality_valid)
    if not can_run_degrees and not can_run_type:return empty
    try:
        with LOCK:loaded=load()
        x,transform=photo_input(bgr,points);result={**empty,'sourceTransform':transform}
        # Check local sessions first
        type_computed = False
        if loaded.get('sessions'):
            for task,item in loaded['sessions'].items():
                if task not in ('type','degrees'):continue
                if task == 'degrees' and not can_run_degrees:continue
                if task == 'type' and not can_run_type:continue
                m=item['metadata']
                if task=='type':
                    vit_x = preprocess_vit_face(bgr, transform)
                    start=time.perf_counter();output=item['session'].run(None,{'rgb':vit_x})[0][0];elapsed=(time.perf_counter()-start)*1000
                    if not np.isfinite(output).all():raise ValueError('NONFINITE_MODEL_OUTPUT')
                    result['models'][task]=dict(modelHash=m['sha256'],modelVersion=m['version'],loadMs=item['loadMs'],inferenceMs=elapsed)
                    type_computed = True
                    assert output.shape==(3,);v=output/float(m.get('temperature', 1.0));v-=v.max();p=np.exp(v);p/=p.sum()
                    conf=float(p.max());valid_base=conf>=float(m.get('confidenceThreshold', 0.36)) and (type_quality_valid is not False)
                    final_cls, conf_val, rule_valid, rule_lim, div_info = regional_combination_rule(bgr, points, p)
                    is_valid = valid_base and rule_valid
                    lim = None if is_valid else (rule_lim or ('LOW_MODEL_SUPPORT' if not valid_base else None))
                    result['skinType']=dict(value=final_cls if is_valid else None,quality='valid' if is_valid else 'insufficient',confidence=conf_val if is_valid else None,methodVersion=m['version'],modelHash=m['sha256'],limitationCode=lim,regionalDivergence=div_info)
                elif task=='degrees':
                    start=time.perf_counter();output=item['session'].run(None,{'rgb':x})[0][0];elapsed=(time.perf_counter()-start)*1000
                    if not np.isfinite(output).all():raise ValueError('NONFINITE_MODEL_OUTPUT')
                    result['models'][task]=dict(modelHash=m['sha256'],modelVersion=m['version'],loadMs=item['loadMs'],inferenceMs=elapsed)
                    assert len(output)==len(m['targets'])
                    for target,value in zip(m['targets'],output):
                        if target in m['acceptedTargets']:result['degrees'][target]=dict(value=float(np.clip(value,0,5)*20),rawGrade=float(np.clip(value,0,5)),methodVersion=m['version'],modelHash=m['sha256'],confidence=None,scope='whole-face',normalizationVersion='ordinal-0-5-times-20-v1')
        
        # If no local accepted model for type, check authorized hosted adapter fallback only when local model unavailable
        if not type_computed and hosted_consent is True and os.environ.get('ATTUNE_ALLOW_HOSTED_INFERENCE') == '1' and (type_quality_valid is None or type_quality_valid is True):
            crop_bgr = bgr[transform['y']:transform['y']+transform['height'], transform['x']:transform['x']+transform['width']]
            hosted = infer_hosted_type(crop_bgr)
            if hosted:
                elapsed = hosted.pop('inferenceMs', 0.0)
                result['models']['type'] = dict(
                    modelHash=hosted.get('modelHash'),
                    modelVersion=hosted.get('methodVersion'),
                    providerModelId=hosted.get('providerModelId'),
                    loadMs=0.0,
                    inferenceMs=elapsed
                )
                result['skinType'] = hosted
            else:
                manifest = loaded.get('manifest') or {}
                type_head = manifest.get('models', {}).get('type', {})
                if type_head.get('accepted') or type_head.get('candidateAccepted'):
                    result['skinType'] = dict(value=None, quality='insufficient', confidence=None,
                                              methodVersion=type_head.get('version'), modelHash=type_head.get('sha256'),
                                              limitationCode='ACCEPTED_MODEL_UNAVAILABLE')

        return result
    except Exception:
        # Compact unavailable state; no old result, substitute weights or zeros.
        # Preserve the expected accepted targets so the product can make them
        # unavailable instead of silently substituting an analytic score.
        targets=[];unavailable_type=None
        try:
            manifest=json.loads(MANIFEST.read_text('utf8'))
            head=manifest.get('models',{}).get('degrees',{})
            if head.get('accepted'):targets=list(head.get('acceptedTargets',[]))
            type_head=manifest.get('models',{}).get('type',{})
            if type_head.get('accepted') or type_head.get('candidateAccepted'):
                unavailable_type=dict(value=None,quality='insufficient',confidence=None,methodVersion=type_head.get('version'),modelHash=type_head.get('sha256'),limitationCode='ACCEPTED_MODEL_UNAVAILABLE')
        except (OSError,ValueError):pass
        return {**empty,'skinType':unavailable_type,'failure':'ACCEPTED_MODEL_UNAVAILABLE','unavailableTargets':targets}

def _nms(boxes,threshold=.3):
    if not boxes:return []
    a=np.asarray(boxes,float);order=np.argsort(-a[:,4]);keep=[]
    while len(order):
        i=int(order[0]);keep.append(i);rest=order[1:]
        start=np.maximum(a[i,:2],a[rest,:2]);end=np.minimum(a[i,2:4],a[rest,2:4]);area=np.maximum(0,end-start).prod(1)
        total=np.maximum(0,a[i,2]-a[i,0])*np.maximum(0,a[i,3]-a[i,1])+np.maximum(0,a[rest,2]-a[rest,0])*np.maximum(0,a[rest,3]-a[rest,1])-area
        order=rest[area/np.maximum(1e-8,total)<=threshold]
    return a[keep].tolist()

def infer_acne(bgr,points,quality_valid):
    if not quality_valid:return None
    try:
        with LOCK:item=load()['sessions'].get('acne')
        if not item:return None
        _,transform=photo_input(bgr,points);x,y=transform['x'],transform['y'];x1=x+transform['width'];y1=y+transform['height'];size=384
        xs=sorted(set([*range(x,max(x+1,x1-size+1),288),max(x,x1-size)]));ys=sorted(set([*range(y,max(y+1,y1-size+1),288),max(y,y1-size)]))
        if len(xs)*len(ys)>64:return {'valid':False,'reason':'NATIVE_TILE_BUDGET_EXCEEDED'}
        boxes=[];started=time.perf_counter();meta=item['metadata']
        for a in xs:
            for b in ys:
                c=min(x1,a+size);d=min(y1,b+size);canvas=np.full((size,size,3),114,np.uint8);canvas[:d-b,:c-a]=bgr[b:d,a:c]
                pred=item['session'].run(None,{'native_bgr_tile':canvas.transpose(2,0,1)[None].astype(np.float32)})[0][0]
                assert pred.shape[1]==6 and np.isfinite(pred).all()
                for cx,cy,w,h,obj,cls in pred:
                    score=float(obj*cls)
                    if score<meta['confidenceThreshold']:continue
                    bx=max(a,float(cx-w/2+a));by=max(b,float(cy-h/2+b));ex=min(c,float(cx+w/2+a));ey=min(d,float(cy+h/2+b))
                    if ex>bx and ey>by:boxes.append([bx,by,ex,ey,score])
        return dict(valid=True,boxes=_nms(boxes),modelHash=meta['sha256'],modelVersion=meta['version'],tileCount=len(xs)*len(ys),loadMs=item['loadMs'],inferenceMs=(time.perf_counter()-started)*1000,coordinateSpace='source-pixels',mapType='detection-boxes')
    except Exception:return {'valid':False,'reason':'ACCEPTED_MODEL_UNAVAILABLE'}

def eye_rois(points,width,height):
    rois=[]
    for eye,ids in [('right',[33,133,145]),('left',[263,362,374])]:
        p=np.array([[points[i]['x']*width,points[i]['y']*height] for i in ids]);span=abs(p[1,0]-p[0,0]);cx=(p[0,0]+p[1,0])/2;cy=max(p[:,1]);rect=[int(max(0,cx-.7*span)),int(max(0,cy-.12*span)),int(min(width,cx+.7*span)),int(min(height,cy+.8*span))]
        a,b,c,d=rect
        if c-a>=12 and d-b>=8:rois.append({'eye':eye,'rect':rect})
    return rois

def infer_bags(bgr,points,quality_valid):
    if not quality_valid:return None
    try:
        with LOCK:item=load()['sessions'].get('bags')
        if not item:return None
        layers=[];start=time.perf_counter();m=item['metadata']
        for roi in eye_rois(points,bgr.shape[1],bgr.shape[0]):
            a,b,c,d=roi['rect'];rgb=cv2.resize(bgr[b:d,a:c,::-1],(128,128),interpolation=cv2.INTER_AREA);x=((rgb.transpose(2,0,1).astype(np.float32)/255-MEAN)/STD)[None].copy();logits=item['session'].run(None,{'rgb_eye_roi':x})[0][0,0]
            assert logits.shape==(128,128) and np.isfinite(logits).all();probability=1/(1+np.exp(-np.clip(logits,-50,50)))
            layers.append({**roi,'mask':(probability>=m['probabilityThreshold']).astype(np.uint8),'mapType':'predicted-presence-mask','confidenceNotSeverity':True})
        return dict(valid=len(layers)==2,layers=layers,modelHash=m['sha256'],modelVersion=m['version'],loadMs=item['loadMs'],inferenceMs=(time.perf_counter()-start)*1000)
    except Exception:return {'valid':False,'reason':'ACCEPTED_MODEL_UNAVAILABLE'}
