"""Pinned three-class pretrained ORT CPU inference plus explicit regional rule.
No training, remote client, downloads, sebum/hydration or clinical claims.
"""
from __future__ import annotations
import copy, hashlib, json, math, threading, time
from pathlib import Path
import numpy as np
from PIL import Image

CONFIG = Path(__file__).resolve().parent / 'models' / 'skin-type-local.json'
CLASSES = ('dry', 'normal', 'oily')
VERSION = 'local-vit-dima806-5aace4f-v1'
RULE = 'tzone-oily-cheeks-dry-or-normal-v3'
COMB = f'{VERSION}+{RULE}'
REGIONS = ('forehead', 'nose', 'chin', 'leftCheek', 'rightCheek')
TZONE_REGIONS = ('forehead', 'nose', 'chin')
CHEEK_REGIONS = ('leftCheek', 'rightCheek')

# Uncalibrated regional appearance proxy thresholds (percentage scale 0..100).
# Intermediate values (OIL_NEGATIVE_MAX < v < OIL_POSITIVE_MIN) are strictly 'unknown'.
# Negative evidence ('normal') requires an explicitly accepted negative-evidence method;
# the default analytic shine proxy ('appearance-cv-6') is NOT accepted as negative evidence.
THRESHOLD_STATUS = 'uncalibrated-hypothesis'
OIL_POSITIVE_MIN = 2.0
OIL_NEGATIVE_MAX = 1.0
DRY_POSITIVE_MIN = 2.0
DRY_NEGATIVE_MAX = 1.0
MIN_ANALYSIS_PIXELS = 100
MIN_SOURCE_PIXELS = 100
MIN_COVERAGE_RATIO = 0.50

# Empty by default in production until a negative-evidence method is validated on held-out camera data.
ACCEPTED_NEGATIVE_METHODS: set[str] = set()

LOCK = threading.Lock()
_CACHE = None


def unavailable(reason: str, version: str = 'local-pretrained-skin-type-v1', model_hash: str | None = None, ms: float = 0.0) -> dict:
    return dict(
        value=None,
        quality='insufficient',
        confidence=None,
        methodVersion=version,
        modelVersion=version,
        modelHash=model_hash,
        limitationCode=reason,
        inferenceKind='local-onnx',
        inferenceMs=ms,
    )


def preprocess(bgr: np.ndarray) -> np.ndarray:
    if not isinstance(bgr, np.ndarray) or bgr.dtype != np.uint8 or bgr.ndim != 3 or bgr.shape[2] != 3 or min(bgr.shape[:2]) < 16:
        raise ValueError('INVALID_TYPE_IMAGE')
    # Exact declared ViTImageProcessor contract, PIL bilinear RGB 224, [0,1], .5/.5.
    image = Image.fromarray(bgr[:, :, ::-1]).resize((224, 224), Image.Resampling.BILINEAR)
    rgb = np.asarray(image).astype(np.float64) * (1 / 255.0)
    rgb = rgb.astype(np.float32)
    return np.ascontiguousarray(((rgb - 0.5) / 0.5).transpose(2, 0, 1)[None])


def load() -> dict:
    global _CACHE
    raw = CONFIG.read_bytes()
    signature = hashlib.sha256(raw).hexdigest()
    with LOCK:
        if _CACHE and _CACHE['signature'] == signature:
            return _CACHE
        config = json.loads(raw)
        if config.get('enabled') is not True:
            raise ValueError('LOCAL_TYPE_DISABLED')
        if config.get('classOrder') != list(CLASSES) or config.get('preprocessing') != {
            'RGB': True,
            'size': [224, 224],
            'resample': 'PIL-bilinear',
            'rescale': 1 / 255,
            'mean': [0.5, 0.5, 0.5],
            'std': [0.5, 0.5, 0.5],
        }:
            raise ValueError('LOCAL_TYPE_CONFIG_INVALID')
        path = (CONFIG.parent / config['file']).resolve()
        if not path.is_relative_to(CONFIG.parent.resolve()) or path.suffix != '.onnx':
            raise ValueError('LOCAL_TYPE_PATH_INVALID')
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != config['sha256']:
            raise ValueError('LOCAL_TYPE_HASH_MISMATCH')
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        start = time.perf_counter()
        session = ort.InferenceSession(data, sess_options=options, providers=['CPUExecutionProvider'])
        if session.get_providers() != ['CPUExecutionProvider'] or session.get_inputs()[0].shape != [1, 3, 224, 224]:
            raise ValueError('LOCAL_TYPE_GRAPH_INVALID')
        _CACHE = dict(
            signature=signature,
            config=config,
            session=session,
            loadMs=(time.perf_counter() - start) * 1000,
            modelHash=actual,
        )
        return _CACHE


def infer(bgr: np.ndarray, quality_valid: bool = True) -> dict:
    if not quality_valid:
        return unavailable('CAPTURE_QUALITY')
    start = time.perf_counter()
    try:
        x = preprocess(bgr)
        loaded = load()
        logits = loaded['session'].run(None, {'rgb': x})[0]
        if logits.shape != (1, 3) or not np.isfinite(logits).all():
            raise ValueError('LOCAL_TYPE_INVALID_OUTPUT')
        values = logits[0].astype(np.float64)
        p = np.exp(values - values.max())
        p /= p.sum()
        index = int(values.argmax())
        config = loaded['config']
        return dict(
            value=CLASSES[index],
            quality='valid',
            confidence=float(p[index]),
            methodVersion=config['version'],
            modelVersion=config['version'],
            modelHash=loaded['modelHash'],
            limitationCode=None,
            inferenceKind='local-onnx',
            inferenceMs=(time.perf_counter() - start) * 1000,
            sourceModel=config['sourceModel'],
            classOrder=list(CLASSES),
            logits=values.tolist(),
            fileHashVerified=True,
            sessionLoaded=True,
        )
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        reason = str(error) if isinstance(error, ValueError) else 'LOCAL_TYPE_UNAVAILABLE'
        return unavailable(reason)
    except Exception:
        return unavailable('LOCAL_TYPE_UNAVAILABLE')


def _metric(rows, key: str):
    if not isinstance(rows, list):
        return None, dict(value=None, quality='insufficient', limitationCode='REGION_MISSING')
    for r in rows:
        if isinstance(r, dict) and r.get('id') == key:
            q = r.get('quality')
            v = r.get('value')
            area = r.get('evaluatedArea') or {}
            ap = area.get('analysisPixels', 0)
            sp = area.get('sourcePixels', 0)
            if (
                q == 'valid'
                and isinstance(v, (int, float))
                and not isinstance(v, bool)
                and np.isfinite(v)
                and 0.0 <= float(v) <= 100.0
                and isinstance(ap, (int, float))
                and ap >= MIN_ANALYSIS_PIXELS
                and isinstance(sp, (int, float))
                and sp > 0
            ):
                if key == 'oil' and r.get('region') == 'nose':
                    if area.get('foreheadSourcePixels', 1) <= 0 or area.get('noseSourcePixels', 1) <= 0:
                        return None, dict(value=None, quality='insufficient', limitationCode='TZONE_SUBREGION_MISSING')
                return float(v), dict(
                    value=float(v),
                    quality='valid',
                    limitationCode=r.get('limitationCode'),
                    methodVersion=r.get('methodVersion'),
                    normalizationVersion=r.get('normalizationVersion'),
                    evaluatedArea=copy.deepcopy(area),
                    sourcePose=r.get('capturePose') or (r.get('captureConditions') or {}).get('pose'),
                    sourcePhotoId=r.get('photoId'),
                )
            return None, dict(
                value=None,
                quality=str(q or 'insufficient'),
                limitationCode=r.get('limitationCode') or 'METRIC_UNAVAILABLE',
                methodVersion=r.get('methodVersion'),
                normalizationVersion=r.get('normalizationVersion'),
                evaluatedArea=copy.deepcopy(area) if area else None,
            )
    return None, dict(value=None, quality='insufficient', limitationCode='METRIC_MISSING')


def _classify_region_state(
    oil: float | None,
    dry: float | None,
    *,
    negative_evidence_ok: bool = False,
) -> tuple[str | None, str]:
    """Classify a single anatomical region from oil and dry measurements only.

    - Redness is never used to infer 'sensitive' skin type.
    - Values in the intermediate band (1.0 < v < 2.0) return 'unknown'.
    - Positive oil and positive dry together return 'unknown' (conflicting signal).
    - 'normal' requires both oil <= 1.0 and dry <= 1.0 AND an accepted negative-evidence method.
      When no negative-evidence method is accepted, low signal returns 'unevaluated'.
    """
    if oil is None or dry is None:
        return None, 'MISSING_OIL_OR_DRY_MEASUREMENT'
    if oil >= OIL_POSITIVE_MIN and dry >= DRY_POSITIVE_MIN:
        return 'unknown', 'CONFLICTING_OIL_AND_DRY_POSITIVE'
    if OIL_NEGATIVE_MAX < oil < OIL_POSITIVE_MIN or DRY_NEGATIVE_MAX < dry < DRY_POSITIVE_MIN:
        return 'unknown', 'INTERMEDIATE_BAND_UNKNOWN'
    if oil >= OIL_POSITIVE_MIN:
        return 'oily', 'OIL_AT_OR_ABOVE_UNCALIBRATED_THRESHOLD'
    if dry >= DRY_POSITIVE_MIN:
        return 'dry', 'DRY_AT_OR_ABOVE_UNCALIBRATED_THRESHOLD'
    # Both oil <= OIL_NEGATIVE_MAX and dry <= DRY_NEGATIVE_MAX
    if negative_evidence_ok:
        return 'normal', 'CONFIRMED_BELOW_NEGATIVE_THRESHOLDS'
    return 'unevaluated', 'NEGATIVE_EVIDENCE_METHOD_NOT_ACCEPTED'


def _input_row(rows, key: str):
    if not isinstance(rows, list):
        return None
    row = next((r for r in rows if isinstance(r, dict) and r.get('id') == key), None)
    if not row:
        return None
    return {
        k: copy.deepcopy(row.get(k))
        for k in ('value', 'quality', 'methodVersion', 'normalizationVersion', 'evaluatedArea', 'limitationCode')
    }


def regional_decision(
    base: dict | None,
    measurements: dict | None,
    *,
    accepted_negative_methods: set[str] | None = None,
) -> dict:
    """Derive regional and whole-face skin type strictly from regional rules.

    The global ViT prediction (`base`) is retained ONLY in `basePrediction` and
    `decisionTrace.baseValue` for audit/record purposes and NEVER leaks to `value`.
    """
    if not isinstance(base, dict):
        return unavailable('SKIN_TYPE_BASE_MISSING')
    if isinstance(base.get('basePrediction'), dict):
        base = copy.deepcopy(base['basePrediction'])
    if base.get('value') == 'combination' or isinstance(base.get('decisionTrace'), dict) or '+' in str(base.get('methodVersion') or ''):
        return unavailable('SKIN_TYPE_BASE_NOT_preserved', str(base.get('methodVersion') or VERSION), base.get('modelHash'))
    if base.get('quality') != 'valid' or base.get('value') not in ('dry', 'normal', 'oily'):
        return base

    active_neg_methods = ACCEPTED_NEGATIVE_METHODS if accepted_negative_methods is None else set(accepted_negative_methods)

    reg = {}
    vals = {}
    for name in REGIONS:
        rows = (measurements or {}).get(name)
        oil, oil_s = _metric(rows, 'oil')
        dry, dry_s = _metric(rows, 'dry')
        vals[name] = (oil, dry)
        oil_method = str(oil_s.get('methodVersion') or '')
        dry_method = str(dry_s.get('methodVersion') or '')
        neg_ok = bool(oil_method in active_neg_methods and dry_method in active_neg_methods)
        state, reason = _classify_region_state(oil, dry, negative_evidence_ok=neg_ok)
        reg[name] = dict(
            oil=oil_s if oil is not None else None,
            dry=dry_s if dry is not None else None,
            inputs=dict(
                oil=_input_row(rows, 'oil'),
                dry=_input_row(rows, 'dry'),
            ),
            state=state,
            reason=reason,
            negativeEvidenceAccepted=neg_ok,
            sourcePose=oil_s.get('sourcePose') or dry_s.get('sourcePose') or 'FRONT',
            sourcePhotoId=oil_s.get('sourcePhotoId') or dry_s.get('sourcePhotoId'),
        )

    f_oil, f_dry = vals['forehead']
    n_oil, n_dry = vals['nose']
    chin_oil, chin_dry = vals['chin']
    l_oil, l_dry = vals['leftCheek']
    r_oil, r_dry = vals['rightCheek']

    # T-zone requires all three subregions (forehead, nose, chin) to be measured and valid,
    # and none of them may be in the indeterminate 'unknown' band.
    t_measured = all(v is not None for v in (f_oil, f_dry, n_oil, n_dry, chin_oil, chin_dry))
    t_states = [reg[r_name]['state'] for r_name in TZONE_REGIONS]
    t_valid = bool(t_measured and all(s in ('oily', 'dry', 'normal', 'unevaluated') for s in t_states))
    t_oily_regions = [
        r_name for r_name in TZONE_REGIONS
        if reg[r_name]['state'] == 'oily'
    ]
    # T-zone is oily only if at least 2/3 of (forehead, nose, chin) are 'oily' AND at least one is forehead or nose,
    # and all three T-zone subregions are measured and not in the indeterminate 'unknown' band.
    t_oily = bool(
        t_valid
        and len(t_oily_regions) >= 2
        and any(r_name in ('forehead', 'nose') for r_name in t_oily_regions)
    )
    t_oil_mean = round((f_oil + n_oil + chin_oil) / 3.0, 2) if t_measured else None

    cheek_measured = all(v is not None for v in (l_oil, l_dry, r_oil, r_dry))
    cheek_states = [reg['leftCheek']['state'], reg['rightCheek']['state']]
    cheek_complete = bool(cheek_measured and all(s is not None for s in cheek_states))
    # Non-oily cheeks require both cheeks to be confirmed 'normal' or 'dry' (never 'unknown' or 'unevaluated' oil).
    cheek_non_oily = bool(
        cheek_complete
        and l_oil <= OIL_NEGATIVE_MAX
        and r_oil <= OIL_NEGATIVE_MAX
        and reg['leftCheek']['state'] in ('normal', 'dry')
        and reg['rightCheek']['state'] in ('normal', 'dry')
        and (
            reg['leftCheek']['negativeEvidenceAccepted'] or reg['leftCheek']['state'] == 'dry'
        )
        and (
            reg['rightCheek']['negativeEvidenceAccepted'] or reg['rightCheek']['state'] == 'dry'
        )
    )
    all_measured = bool(t_measured and cheek_measured)
    states = [reg[r_name]['state'] for r_name in REGIONS]
    has_unknown = any(s == 'unknown' for s in states)
    has_unevaluated = any(s == 'unevaluated' for s in states)
    complete = bool(all_measured and not has_unknown and not has_unevaluated)
    comb = bool(all_measured and not has_unknown and t_oily and cheek_non_oily)

    base_ver = str(base.get('modelVersion') or base.get('methodVersion') or VERSION).split('+')[0]
    ver = f"{base_ver}+{RULE}"

    applied = False
    limitation_code = None
    display_value = None

    if not cheek_measured:
        final_value = None
        final_quality = 'insufficient'
        limitation_code = 'INCOMPLETE_CHEEKS_UNVERIFIED'
        display_value = 'Belirsiz (Yanak verisi eksik)'
    elif not t_measured:
        final_value = None
        final_quality = 'insufficient'
        limitation_code = 'INCOMPLETE_TZONE_UNVERIFIED'
        display_value = 'Belirsiz (T-bölgesi verisi eksik)'
    elif has_unknown:
        final_value = None
        final_quality = 'insufficient'
        limitation_code = 'INTERMEDIATE_BAND_UNDETERMINED'
        display_value = 'Belirlenemedi (Ara sinyal bandı)'
    elif comb:
        final_value = 'combination'
        final_quality = 'valid'
        applied = True
        limitation_code = 'DERIVED_REGIONAL_RULE_CONFIDENCE_NOT_APPLICABLE'
    else:
        oily_count = sum(1 for s in states if s == 'oily')
        dry_count = sum(1 for s in states if s == 'dry')
        normal_count = sum(1 for s in states if s == 'normal')
        if oily_count == len(REGIONS):
            final_value = 'oily'
            final_quality = 'valid'
            applied = True
        elif dry_count == len(REGIONS):
            final_value = 'dry'
            final_quality = 'valid'
            applied = True
        elif normal_count == len(REGIONS):
            final_value = 'normal'
            final_quality = 'valid'
            applied = True
        elif has_unevaluated and oily_count == 0 and dry_count == 0:
            final_value = None
            final_quality = 'insufficient'
            limitation_code = 'NEGATIVE_EVIDENCE_METHOD_NOT_ACCEPTED'
            display_value = 'Değerlendirilmedi'
        else:
            # Mixed or partial regional pattern (e.g., Scenario D: forehead oily, chin dry).
            # Never fall back to or leak the global ViT label (`base['value']`).
            final_value = None
            final_quality = 'insufficient'
            limitation_code = 'MIXED_REGIONAL_PATTERN_UNDETERMINED'
            display_value = 'Karışık desen (Belirlenemedi)'

    trace = dict(
        rule=RULE,
        version=RULE,
        applied=applied,
        complete=complete,
        combinationMatched=comb,
        baseValue=base.get('value'),
        baseConfidence=base.get('confidence'),
        baseModelHash=base.get('modelHash'),
        finalValue=final_value,
        displayValue=display_value,
        tZoneOily=t_oily,
        tZoneValid=t_valid,
        tZoneOilySubregions=t_oily_regions,
        cheekComplete=cheek_complete,
        cheekNonOily=cheek_non_oily,
        limitationCode=limitation_code,
        thresholds=dict(
            status=THRESHOLD_STATUS,
            oilPositiveMin=OIL_POSITIVE_MIN,
            oilNegativeMax=OIL_NEGATIVE_MAX,
            dryPositiveMin=DRY_POSITIVE_MIN,
            dryNegativeMax=DRY_NEGATIVE_MAX,
            minAnalysisPixels=MIN_ANALYSIS_PIXELS,
            tZoneMinOilySubregions=2,
            tZoneRequiresForeheadOrNose=True,
            negativeEvidenceMethods=sorted(active_neg_methods),
        ),
        tZone=dict(
            valid=t_valid,
            oily=t_oily,
            state='oily' if t_oily else ('non-oily' if t_valid and not has_unevaluated else 'unknown'),
            oilyRegions=t_oily_regions,
            oilySubregions=t_oily_regions,
            meanOil=t_oil_mean,
            subregions={r_name: reg[r_name]['inputs']['oil'] for r_name in TZONE_REGIONS},
            inputs={r_name: reg[r_name]['inputs']['oil'] for r_name in TZONE_REGIONS},
            observation=reg['nose']['oil'],
        ),
        cheeks=dict(
            complete=cheek_complete,
            nonOily=cheek_non_oily,
            leftState=reg['leftCheek']['state'],
            rightState=reg['rightCheek']['state'],
        ),
        regions=reg,
    )
    result = copy.deepcopy(base)
    for k in ('status', 'reason', 'calibrationVersion', 'coverage'):
        result.pop(k, None)
    result.update(
        methodVersion=ver,
        modelVersion=ver,
        value=final_value,
        quality=final_quality,
        confidence=None,
        limitationCode=limitation_code,
        displayValue=display_value,
        basePrediction=copy.deepcopy(base),
        decisionVersion=RULE,
        decisionTrace=trace,
        components={
            **(result.get('components') or {}),
            'baseValue': base.get('value'),
            'decisionRule': RULE,
            'applied': applied,
            'complete': complete,
        },
    )
    return result


def finalize_product_type(
    result: dict,
    *,
    accepted_negative_methods: set[str] | None = None,
) -> dict:
    if not isinstance(result, dict):
        return result
    general = result.get('general') or {}
    current = general.get('skinType')
    if isinstance(current, dict) and current.get('inferenceKind') == 'local-onnx':
        base = current.get('basePrediction') if isinstance(current.get('basePrediction'), dict) else current
        final = regional_decision(
            base,
            result.get('measurements'),
            accepted_negative_methods=accepted_negative_methods,
        )
        general['skinType'] = final
        trace = final.get('decisionTrace') if isinstance(final.get('decisionTrace'), dict) else {}
        regional_map = dict(
            schemaVersion=2,
            methodVersion=final.get('methodVersion'),
            complete=bool(trace.get('complete')),
            limitationCode=trace.get('limitationCode'),
            displayValue=trace.get('displayValue'),
            thresholds=copy.deepcopy(trace.get('thresholds')),
            tZone=copy.deepcopy(trace.get('tZone')),
            cheeks=copy.deepcopy(trace.get('cheeks')),
            regions={
                r_name: dict(
                    state=(trace.get('regions', {}).get(r_name) or {}).get('state') or 'unknown',
                    reason=(trace.get('regions', {}).get(r_name) or {}).get('reason'),
                    oil=(((trace.get('regions', {}).get(r_name) or {}).get('inputs') or {}).get('oil') or {}).get('value'),
                    dry=(((trace.get('regions', {}).get(r_name) or {}).get('inputs') or {}).get('dry') or {}).get('value'),
                    sourcePose=(trace.get('regions', {}).get(r_name) or {}).get('sourcePose') or 'FRONT',
                    sourcePhotoId=(trace.get('regions', {}).get(r_name) or {}).get('sourcePhotoId'),
                )
                for r_name in REGIONS
            },
        )
        general['regionalSkinMap'] = regional_map
        result['regionalSkinMap'] = regional_map
    from skin_measurement_contract import attach_result_receipts
    return attach_result_receipts(result)


def fuse_multi_angle_skin(
    front_result: dict,
    left_result: dict | None = None,
    right_result: dict | None = None,
    *,
    accepted_negative_methods: set[str] | None = None,
) -> dict:
    """Fuse FRONT (T-zone + periorbital), LEFT (rightCheek), and RIGHT (leftCheek) results.

    Preserves each region's capturePose ('FRONT', 'LEFT', 'RIGHT') and photoId,
    updates regional maps/contours/acneCandidates, and recomputes the regional skin map
    and whole-face skinType decision from the fused 3-angle measurements.
    """
    if not isinstance(front_result, dict):
        raise ValueError('FRONT_RESULT_REQUIRED')
    fused = copy.deepcopy(front_result)
    front_pid = fused.get('photoId')
    measurements = fused.setdefault('measurements', {})
    maps = fused.setdefault('maps', {})
    contours = fused.setdefault('contours', {})
    acne_cands = fused.get('acneCandidates') if isinstance(fused.get('acneCandidates'), dict) else None

    for reg_name in ('forehead', 'nose', 'chin', 'periorbital'):
        for row in measurements.get(reg_name) or []:
            if isinstance(row, dict):
                row['photoId'] = row.get('photoId') or front_pid
                row['capturePose'] = 'FRONT'
                row.setdefault('captureConditions', {})['pose'] = 'FRONT'

    captures = {
        'FRONT': {
            'captureId': front_pid,
            'pose': 'FRONT',
            'sourceWidth': fused.get('sourceWidth'),
            'sourceHeight': fused.get('sourceHeight'),
        }
    }

    side_sources = [
        ('LEFT', 'rightCheek', left_result),
        ('RIGHT', 'leftCheek', right_result),
    ]
    for pose_name, cheek_region, side_res in side_sources:
        if not isinstance(side_res, dict):
            continue
        side_pid = side_res.get('photoId')
        captures[pose_name] = {
            'captureId': side_pid,
            'pose': pose_name,
            'sourceWidth': side_res.get('sourceWidth'),
            'sourceHeight': side_res.get('sourceHeight'),
        }
        side_rows = copy.deepcopy((side_res.get('measurements') or {}).get(cheek_region))
        if isinstance(side_rows, list):
            for row in side_rows:
                if isinstance(row, dict):
                    row['photoId'] = side_pid
                    row['capturePose'] = pose_name
                    row.setdefault('captureConditions', {})['pose'] = pose_name
            measurements[cheek_region] = side_rows
        for k, v in (side_res.get('maps') or {}).items():
            if k.startswith(f'{cheek_region}:'):
                maps[k] = copy.deepcopy(v)
        if cheek_region in (side_res.get('contours') or {}):
            contours[cheek_region] = copy.deepcopy(side_res['contours'][cheek_region])
        if acne_cands is not None and isinstance(side_res.get('acneCandidates'), dict):
            if cheek_region in side_res['acneCandidates']:
                acne_cands[cheek_region] = copy.deepcopy(side_res['acneCandidates'][cheek_region])

    if acne_cands is not None:
        all_boxes = []
        for reg_name in ('forehead', 'rightCheek', 'leftCheek', 'nose', 'chin'):
            for b in acne_cands.get(reg_name) or []:
                all_boxes.append(b)
        acne_cands['overview'] = all_boxes

    fused['captures'] = captures
    fused['comparisonScope'] = 'three-angle-v2'
    return finalize_product_type(fused, accepted_negative_methods=accepted_negative_methods)

