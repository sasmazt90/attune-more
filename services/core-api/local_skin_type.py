from __future__ import annotations
import copy, hashlib, json, time
from pathlib import Path
import cv2, numpy as np

MODEL_DIR = Path(__file__).resolve().parent / 'models' / 'skin-type-local-v1'
CONFIG = MODEL_DIR / 'config.json'
VERSION = 'skin-type-local-vit-v1'
RULE = 'tzone-oily-cheeks-dry-or-normal-v2'
COMB = 'skin-type-local-vit-v1+tzone-oily-cheeks-dry-or-normal-v2'
REGIONS = ('forehead', 'nose', 'chin', 'leftCheek', 'rightCheek')
TZONE_REGIONS = ('forehead', 'nose', 'chin')
CHEEK_REGIONS = ('leftCheek', 'rightCheek')

# Calibrated regional appearance proxy thresholds (percentage scale 0..100).
# Positives require >= 2.0% regional proxy signal; non-positive confirmation requires <= 1.0%.
OIL_POSITIVE_MIN = 2.0
OIL_NEGATIVE_MAX = 1.0
DRY_POSITIVE_MIN = 2.0
DRY_NEGATIVE_MAX = 1.0
SENSITIVE_REDNESS_MIN = 18.0
MIN_ANALYSIS_PIXELS = 100
MIN_SOURCE_PIXELS = 100
MIN_COVERAGE_RATIO = 0.50

_cache = {'key': None, 'session': None, 'cfg': None}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def unavailable(code: str, version: str = VERSION, model_hash: str | None = None, ms: float | None = None) -> dict:
    return dict(
        id='type',
        scope='whole-face',
        region='overview',
        type='model_inference',
        methodVersion=version,
        modelVersion=version,
        normalizationVersion='imagenet-vit-224-v1',
        unit='class',
        value=None,
        confidence=None,
        quality='insufficient',
        limitationCode=code,
        modelHash=model_hash,
        inferenceMs=ms,
        inferenceKind='local-onnx',
        fileHashVerified=bool(model_hash),
        sessionLoaded=False,
        probabilities=None,
        calibration=None,
        components={},
    )


def _session():
    if not CONFIG.exists():
        return None, None, 'LOCAL_SKIN_TYPE_CONFIG_MISSING'
    cfg = json.loads(CONFIG.read_text('utf8'))
    weights = MODEL_DIR / cfg.get('weightsFile', 'model.onnx')
    expected = cfg.get('sha256')
    if not weights.exists() or not expected:
        return cfg, None, 'LOCAL_SKIN_TYPE_WEIGHTS_MISSING'
    actual = _sha(weights)
    if actual.lower() != str(expected).lower():
        return cfg, None, 'LOCAL_SKIN_TYPE_HASH_MISMATCH'
    key = (str(weights), actual)
    if _cache['key'] != key or _cache['session'] is None:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        _cache.update(
            key=key,
            session=ort.InferenceSession(str(weights), sess_options=opts, providers=['CPUExecutionProvider']),
            cfg=cfg,
        )
    return cfg, _cache['session'], actual


def infer(crop_bgr: np.ndarray, quality_valid: bool = True) -> dict:
    if not quality_valid:
        return unavailable('CAPTURE_QUALITY')
    if crop_bgr is None or getattr(crop_bgr, 'ndim', 0) != 3 or min(crop_bgr.shape[:2]) < 64:
        return unavailable('SKIN_CROP_INVALID')
    t0 = time.perf_counter()
    try:
        cfg, sess, status = _session()
    except Exception:
        return unavailable('LOCAL_SKIN_TYPE_LOAD_FAILED')
    if sess is None:
        return unavailable(status, (cfg or {}).get('version', VERSION))
    size = int(cfg.get('inputSize', 224))
    rgb = cv2.cvtColor(cv2.resize(crop_bgr, (size, size), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.asarray(cfg.get('mean', [0.5, 0.5, 0.5]), np.float32)
    std = np.asarray(cfg.get('std', [0.5, 0.5, 0.5]), np.float32)
    x = np.transpose((rgb - mean) / std, (2, 0, 1))[None].astype(np.float32)
    logits = np.asarray(sess.run(None, {sess.get_inputs()[0].name: x})[0], np.float64).reshape(-1)
    ms = round((time.perf_counter() - t0) * 1000.0, 2)
    labels = cfg.get('labels') or ['dry', 'normal', 'oily']
    if logits.size != len(labels) or not np.all(np.isfinite(logits)):
        return unavailable('LOCAL_SKIN_TYPE_INVALID_OUTPUT', cfg.get('version', VERSION), status, ms)
    cal = cfg.get('calibration') or {}
    temp = cal.get('temperature')
    scaled = logits / float(temp) if isinstance(temp, (int, float)) and temp > 0 else logits
    ex = np.exp(scaled - np.max(scaled))
    probs = ex / np.sum(ex)
    idx = int(np.argmax(probs))
    calibrated = bool(cal.get('calibrated')) and isinstance(temp, (int, float)) and temp > 0
    ver = cfg.get('version', VERSION)
    return dict(
        id='type',
        scope='whole-face',
        region='overview',
        type='model_inference',
        methodVersion=ver,
        modelVersion=ver,
        normalizationVersion='imagenet-vit-224-v1',
        unit='class',
        value=str(labels[idx]),
        confidence=round(float(probs[idx]), 4) if calibrated else None,
        quality='valid',
        limitationCode=None if calibrated else 'UNCALIBRATED_CONFIDENCE_WITHHELD',
        modelHash=status,
        inferenceMs=ms,
        inferenceKind='local-onnx',
        fileHashVerified=True,
        sessionLoaded=True,
        probabilities={str(labels[i]): round(float(probs[i]), 4) for i in range(len(labels))},
        calibration=dict(calibrated=calibrated, temperature=temp, fittedOn=cal.get('fittedOn')),
        components=dict(topProbability=round(float(probs[idx]), 4), labelOrder=list(labels)),
    )


def _metric(rows, cid: str):
    row = next((r for r in (rows or []) if isinstance(r, dict) and r.get('id') == cid), None)
    if not row:
        return None, None
    area = row.get('evaluatedArea')
    area_ok = (
        isinstance(area, dict)
        and (area.get('analysisPixels') or 0) >= MIN_ANALYSIS_PIXELS
        and (area.get('sourcePixels') or 0) >= MIN_SOURCE_PIXELS
    )
    val = row.get('value')
    ok = (
        row.get('quality') == 'valid'
        and area_ok
        and isinstance(val, (int, float))
        and not isinstance(val, bool)
        and np.isfinite(val)
        and 0 <= float(val) <= 100
    )
    snap = {k: copy.deepcopy(row.get(k)) for k in ('value', 'quality', 'methodVersion', 'normalizationVersion', 'evaluatedArea', 'limitationCode')}
    return (float(val) if ok else None), snap


def _classify_region_state(oil: float | None, dry: float | None, redness: float | None = None) -> tuple[str | None, str]:
    if oil is None or dry is None:
        return None, 'unmeasured'
    if oil >= OIL_POSITIVE_MIN:
        return 'oily', 'oil_above_positive_threshold'
    if dry >= DRY_POSITIVE_MIN and oil <= OIL_NEGATIVE_MAX:
        return 'dry', 'dry_above_positive_threshold'
    if redness is not None and redness >= SENSITIVE_REDNESS_MIN and oil <= OIL_NEGATIVE_MAX:
        return 'sensitive', 'redness_above_sensitive_threshold'
    if oil <= OIL_NEGATIVE_MAX and dry <= DRY_NEGATIVE_MAX:
        return 'normal', 'oil_and_dry_below_negative_threshold'
    return 'normal', 'intermediate_deadband_normal'


def regional_decision(skin_type: dict, measurements: dict | None) -> dict:
    base = copy.deepcopy(skin_type if isinstance(skin_type, dict) else unavailable('SKIN_TYPE_MISSING'))
    if base.get('value') == 'combination' or isinstance(base.get('decisionTrace'), dict) or '+' in str(base.get('methodVersion') or ''):
        return unavailable('SKIN_TYPE_BASE_NOT_preserved', str(base.get('methodVersion') or VERSION), base.get('modelHash'))
    if base.get('quality') != 'valid' or base.get('value') not in ('dry', 'normal', 'oily'):
        return base

    reg = {}
    vals = {}
    for name in REGIONS:
        rows = (measurements or {}).get(name)
        oil, oil_s = _metric(rows, 'oil')
        dry, dry_s = _metric(rows, 'dry')
        red, red_s = _metric(rows, 'redness')
        vals[name] = (oil, dry, red)
        state, reason = _classify_region_state(oil, dry, red)
        reg[name] = dict(
            oil=oil_s,
            dry=dry_s,
            redness=red_s,
            inputs=dict(oil=oil_s, dry=dry_s, redness=red_s),
            state=state,
            reason=reason,
        )

    f_oil, f_dry, _ = vals['forehead']
    n_oil, n_dry, _ = vals['nose']
    chin_oil, chin_dry, _ = vals['chin']
    l_oil, l_dry, _ = vals['leftCheek']
    r_oil, r_dry, _ = vals['rightCheek']

    # T-zone requires all three subregions (forehead, nose, chin) to be measured and valid.
    t_valid = all(v is not None for v in (f_oil, f_dry, n_oil, n_dry, chin_oil, chin_dry))
    t_oily_regions = [
        r_name for r_name in TZONE_REGIONS
        if vals[r_name][0] is not None and vals[r_name][0] >= OIL_POSITIVE_MIN
    ]
    # T-zone is oily only if at least 2/3 of (forehead, nose, chin) are oily AND at least one is forehead or nose.
    t_oily = bool(
        t_valid
        and len(t_oily_regions) >= 2
        and any(r_name in ('forehead', 'nose') for r_name in t_oily_regions)
    )
    t_oil_mean = round((f_oil + n_oil + chin_oil) / 3.0, 2) if t_valid else None

    cheek_complete = all(v is not None for v in (l_oil, l_dry, r_oil, r_dry))
    # Non-oily cheeks require both cheeks to be confirmed <= OIL_NEGATIVE_MAX (normal, dry, or sensitive).
    cheek_non_oily = bool(
        cheek_complete
        and l_oil <= OIL_NEGATIVE_MAX
        and r_oil <= OIL_NEGATIVE_MAX
        and reg['leftCheek']['state'] in ('normal', 'dry', 'sensitive')
        and reg['rightCheek']['state'] in ('normal', 'dry', 'sensitive')
    )
    complete = bool(t_valid and cheek_complete)
    comb = bool(complete and t_oily and cheek_non_oily)

    base_ver = str(base.get('modelVersion') or base.get('methodVersion') or VERSION).split('+')[0]
    ver = f'{base_ver}+{RULE}'

    incomplete_limitation = (
        'INCOMPLETE_CHEEKS_UNVERIFIED'
        if not cheek_complete
        else ('INCOMPLETE_TZONE_UNVERIFIED' if not t_valid else None)
    )

    # Determine final product skinType when complete vs incomplete:
    applied = False
    applied_reason = 'base_model_retained'
    final_value = base.get('value')
    final_quality = base.get('quality')
    final_conf = base.get('confidence')

    if not complete:
        # Blocker 1 fix: never leak global dry/normal/oily when regional cheek or T-zone coverage is incomplete.
        final_value = None
        final_quality = 'insufficient'
        final_conf = None
        applied = False
        applied_reason = incomplete_limitation or 'incomplete_regional_coverage'
    elif comb:
        final_value = 'combination'
        final_quality = 'valid'
        final_conf = None
        applied = True
        applied_reason = 'tzone_2of3_oily_and_cheeks_non_oily'
    else:
        # Reconcile global label with verified regional measurements so all-normal regions never show global 'dry'.
        states = [reg[r_name]['state'] for r_name in REGIONS]
        oily_count = sum(1 for s in states if s == 'oily')
        dry_count = sum(1 for s in states if s == 'dry')
        sens_count = sum(1 for s in states if s == 'sensitive')
        if oily_count >= 3 or (t_oily and any(reg[c]['state'] == 'oily' for c in CHEEK_REGIONS)):
            final_value = 'oily'
            if base.get('value') != 'oily':
                applied = True
                final_conf = None
                applied_reason = 'regional_consensus_oily'
        elif dry_count >= 2 and oily_count == 0:
            final_value = 'dry'
            if base.get('value') != 'dry':
                applied = True
                final_conf = None
                applied_reason = 'regional_consensus_dry'
        elif sens_count >= 2 and oily_count == 0:
            final_value = 'sensitive'
            applied = True
            final_conf = None
            applied_reason = 'regional_consensus_sensitive'
        elif all(s == 'normal' for s in states):
            final_value = 'normal'
            if base.get('value') != 'normal':
                applied = True
                final_conf = None
                applied_reason = 'regional_consensus_normal'

    trace = dict(
        ruleVersion=RULE,
        applied=applied,
        appliedReason=applied_reason,
        complete=complete,
        baseValue=base.get('value'),
        finalValue=final_value,
        limitationCode=incomplete_limitation,
        thresholds=dict(
            status='initial-calibrated-hypothesis-v2',
            oilPositiveMin=OIL_POSITIVE_MIN,
            oilNegativeMax=OIL_NEGATIVE_MAX,
            dryPositiveMin=DRY_POSITIVE_MIN,
            dryNegativeMax=DRY_NEGATIVE_MAX,
            sensitiveRednessMin=SENSITIVE_REDNESS_MIN,
            minAnalysisPixels=MIN_ANALYSIS_PIXELS,
            minCoverageRatio=MIN_COVERAGE_RATIO,
            tZoneRule='at_least_2_of_3_subregions_oily_including_forehead_or_nose',
        ),
        tZone=dict(
            regions=list(TZONE_REGIONS),
            valid=t_valid,
            oilMean=t_oil_mean,
            chinOil=chin_oil,
            oilyRegions=t_oily_regions,
            oilyCount=len(t_oily_regions),
            requiredOilyCount=2,
            state='oily' if t_oily else ('non-oily' if t_valid else 'unknown'),
        ),
        cheeks=dict(
            regions=list(CHEEK_REGIONS),
            complete=cheek_complete,
            nonOily=cheek_non_oily,
            leftState=reg['leftCheek']['state'],
            rightState=reg['rightCheek']['state'],
        ),
        regions=reg,
    )

    result = copy.deepcopy(base)
    result.update(
        methodVersion=ver,
        modelVersion=ver,
        value=final_value,
        quality=final_quality,
        confidence=final_conf,
        basePrediction=copy.deepcopy(base),
        decisionTrace=trace,
        components={
            **(result.get('components') or {}),
            'baseValue': base.get('value'),
            'decisionRule': RULE,
            'applied': applied,
            'complete': complete,
        },
    )
    if incomplete_limitation:
        result['limitationCode'] = incomplete_limitation
    elif applied:
        result['limitationCode'] = 'DERIVED_REGIONAL_RULE_CONFIDENCE_NOT_APPLICABLE'
    return result


def finalize_product_type(result: dict) -> dict:
    if not isinstance(result, dict):
        return result
    general = result.get('general') or {}
    current = general.get('skinType')
    if isinstance(current, dict) and current.get('inferenceKind') == 'local-onnx':
        base = current.get('basePrediction') if isinstance(current.get('basePrediction'), dict) else current
        final = regional_decision(base, result.get('measurements'))
        general['skinType'] = final
        trace = final.get('decisionTrace') if isinstance(final.get('decisionTrace'), dict) else {}
        regional_map = dict(
            schemaVersion=1,
            methodVersion=final.get('methodVersion'),
            complete=bool(trace.get('complete')),
            limitationCode=trace.get('limitationCode'),
            thresholds=copy.deepcopy(trace.get('thresholds')),
            tZone=copy.deepcopy(trace.get('tZone')),
            cheeks=copy.deepcopy(trace.get('cheeks')),
            regions={
                r_name: dict(
                    state=(trace.get('regions', {}).get(r_name) or {}).get('state') or 'unknown',
                    reason=(trace.get('regions', {}).get(r_name) or {}).get('reason'),
                    oil=((trace.get('regions', {}).get(r_name) or {}).get('oil') or {}).get('value'),
                    dry=((trace.get('regions', {}).get(r_name) or {}).get('dry') or {}).get('value'),
                    redness=((trace.get('regions', {}).get(r_name) or {}).get('redness') or {}).get('value'),
                )
                for r_name in REGIONS
            },
        )
        general['regionalSkinMap'] = regional_map
        result['regionalSkinMap'] = regional_map
    from skin_measurement_contract import attach_result_receipts
    return attach_result_receipts(result)
