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
RULE = 'tzone-oily-cheeks-dry-or-normal-v2'
COMB = f'{VERSION}+{RULE}'
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


def _classify_region_state(oil: float | None, dry: float | None, redness: float | None = None) -> tuple[str | None, str]:
    if oil is None or dry is None:
        return None, 'MISSING_OIL_OR_DRY_MEASUREMENT'
    if oil >= OIL_POSITIVE_MIN and oil >= dry:
        return 'oily', 'OIL_AT_OR_ABOVE_POSITIVE_THRESHOLD'
    if dry >= DRY_POSITIVE_MIN:
        return 'dry', 'DRY_AT_OR_ABOVE_POSITIVE_THRESHOLD'
    if redness is not None and redness >= SENSITIVE_REDNESS_MIN and oil <= OIL_NEGATIVE_MAX:
        return 'sensitive', 'REDNESS_AT_OR_ABOVE_SENSITIVE_THRESHOLD'
    if oil <= OIL_NEGATIVE_MAX and dry <= DRY_NEGATIVE_MAX:
        return 'normal', 'CONFIRMED_BELOW_NEGATIVE_THRESHOLDS'
    return 'normal', 'SUBTHRESHOLD_INTERMEDIATE_SIGNAL'


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


def regional_decision(base: dict | None, measurements: dict | None) -> dict:
    if not isinstance(base, dict):
        return unavailable('SKIN_TYPE_BASE_MISSING')
    if isinstance(base.get('basePrediction'), dict):
        base = copy.deepcopy(base['basePrediction'])
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
            oil=oil_s if oil is not None else None,
            dry=dry_s if dry is not None else None,
            redness=red_s if red is not None else None,
            inputs=dict(
                oil=_input_row(rows, 'oil'),
                dry=_input_row(rows, 'dry'),
                redness=_input_row(rows, 'redness'),
            ),
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

    # When regional coverage is incomplete, do NOT leak a global ViT label ('dry'/'normal'/'oily') as verified.
    if not cheek_complete:
        incomplete_limitation = 'INCOMPLETE_CHEEKS_UNVERIFIED'
    elif not t_valid:
        incomplete_limitation = 'INCOMPLETE_TZONE_UNVERIFIED'
    else:
        incomplete_limitation = None

    applied = False
    if not complete:
        final_value = None
        final_quality = 'insufficient'
        final_conf = None
        ver = f"{base_ver}+{RULE}"
    elif comb:
        final_value = 'combination'
        final_quality = 'valid'
        final_conf = None
        applied = True
        ver = f"{base_ver}+{RULE}"
    else:
        # All 5 regions are measured and valid, and not combination.
        states = [reg[r_name]['state'] for r_name in REGIONS]
        oily_count = sum(1 for s in states if s == 'oily')
        dry_count = sum(1 for s in states if s == 'dry')
        sens_count = sum(1 for s in states if s == 'sensitive')
        if oily_count >= 3:
            final_value = 'oily'
        elif dry_count >= 2 and oily_count == 0:
            final_value = 'dry'
        elif sens_count >= 2 and oily_count == 0 and dry_count == 0:
            final_value = 'sensitive'
        elif all(s == 'normal' for s in states):
            # When all 5 regions are confirmed normal, reconcile uncalibrated global 'dry' argmax to 'normal'
            final_value = 'normal' if base.get('value') == 'dry' else base.get('value')
        else:
            final_value = base.get('value')
        final_quality = 'valid'
        final_conf = base.get('confidence') if final_value == base.get('value') else None
        ver = f"{base_ver}+{RULE}"

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
        tZoneOily=t_oily,
        tZoneValid=t_valid,
        tZoneOilySubregions=t_oily_regions,
        cheekComplete=cheek_complete,
        cheekNonOily=cheek_non_oily,
        limitationCode=incomplete_limitation,
        thresholds=dict(
            status='initial-calibrated-hypothesis-v2',
            oilPositiveMin=OIL_POSITIVE_MIN,
            oilNegativeMax=OIL_NEGATIVE_MAX,
            dryPositiveMin=DRY_POSITIVE_MIN,
            dryNegativeMax=DRY_NEGATIVE_MAX,
            sensitiveRednessMin=SENSITIVE_REDNESS_MIN,
            minAnalysisPixels=MIN_ANALYSIS_PIXELS,
            tZoneMinOilySubregions=2,
            tZoneRequiresForeheadOrNose=True,
        ),
        tZone=dict(
            valid=t_valid,
            oily=t_oily,
            state='oily' if t_oily else ('non-oily' if t_valid else 'unknown'),
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
        confidence=final_conf,
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
