"""Isolated hosted Roboflow research model runner for Lesion RF-DETR Large (m3)
and Regional NAS Seg (m6).

IMPORTANT:
- Both models are research-only (rejected by the product model acceptance gate).
- They NEVER run on the default product path (`/api/local-health/skin`) and
  NEVER mutate or mix into analytic `oil` or `acne` product measurements.
- Execution requires ALL THREE gates:
  1. Environment flag `ATTUNE_EXPERIMENTAL_HOSTED_SKIN_RESEARCH == '1'`
  2. Request flag `experimentalHostedSkinResearch is True`
  3. Scope-matched consent `hostedResearchModelConsent is True`
- Uses a bounded HTTP transport with explicit per-call timeout and cooperative
  request-budget checks (`check()`).
"""
from __future__ import annotations
import base64, json, os, time, urllib.parse, urllib.request
from typing import Callable
import cv2, numpy as np

LESION_LARGE_MODEL_ID = 'tolgar-sasmaz/lesion-detection-ruc40-qzwqz-1-rfdetr-large-t1'
LESION_LARGE_VERSION = 'roboflow-lesion-rfdetr-large-t1'
LESION_METHOD_VERSION = 'research-roboflow-lesion-rfdetr-large-v1'

REGIONAL_SEG_MODEL_ID = 'tolgar-sasmaz/attune-skin-regional-skin-map-1-rfdetr-nas-seg-t1--e79545'
REGIONAL_SEG_VERSION = 'roboflow-regional-nas-seg-e79545'
REGIONAL_SEG_METHOD_VERSION = 'research-roboflow-regional-nas-seg-v1'

# Validation-selected optimums on 27-image validation set (not locked test acceptance).
VALIDATION_LESION_THRESHOLDS = {
    'papule': 0.35,
    'pustule': 0.26,
    'open_comedo': 0.26,
    'closed_comedo': 0.29,
}
LESION_DECLARED_CLASSES = (
    'atrophic_scar',
    'closed_comedo',
    'hypertrophic_scar',
    'melasma',
    'nevus',
    'nodule',
    'open_comedo',
    'other',
    'papule',
    'pustule',
)

# Regional oily segmentation thresholds: validation optimum = 0.31, locked threshold = 0.35.
OILY_SEG_VALIDATION_OPTIMUM = 0.31
OILY_SEG_MIN_CONFIDENCE = 0.35
REGIONAL_SEG_DECLARED_CLASSES = ('Oily', 'Redness')
APPROVED_LESION_THRESHOLDS = VALIDATION_LESION_THRESHOLDS

HOSTED_CALL_TIMEOUT_SECONDS = 5.0
MAX_RESPONSE_BYTES = 2_000_000

HOSTED_RESEARCH_CONSENT_SCOPE = 'experimental-hosted-roboflow-dual-model-full-frame-1024px-v1'
HOSTED_RESEARCH_CONSENT_TEXT = (
    'Araştırma karşılaştırması kapsamında yüz fotoğrafımın (en uzun kenarı en fazla 1024 piksele '
    'küçültülmüş tam kare olarak) iki harici bulut araştırma modeline '
    '(Roboflow Lesion RF-DETR Large ve Regional NAS Seg) gönderilmesini onaylıyorum. '
    'Bu çıktılar ürün ölçüm puanlarına karıştırılmaz.'
)


def research_flag_enabled(payload: dict | None = None) -> bool:
    if os.environ.get('ATTUNE_EXPERIMENTAL_HOSTED_SKIN_RESEARCH') != '1':
        return False
    if not isinstance(payload, dict):
        return False
    return (
        payload.get('experimentalHostedSkinResearch') is True
        and payload.get('hostedResearchModelConsent') is True
    )


def _prepare_inference_image(bgr: np.ndarray, max_dim: int = 1024) -> tuple[np.ndarray, float]:
    h, w = bgr.shape[:2]
    scale = min(1.0, float(max_dim) / float(max(h, w, 1)))
    if scale < 1.0:
        resized = cv2.resize(
            bgr,
            (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
            interpolation=cv2.INTER_AREA,
        )
        return resized, scale
    return bgr, 1.0


def _bounded_roboflow_post(
    bgr: np.ndarray,
    model_id: str,
    api_key: str,
    timeout_s: float = HOSTED_CALL_TIMEOUT_SECONDS,
    check: Callable[[], None] | None = None,
) -> tuple[dict, float, float]:
    if check is not None:
        check()
    inf_img, rf_scale = _prepare_inference_image(bgr)
    ok, encoded = cv2.imencode('.jpg', inf_img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise ValueError('IMAGE_ENCODE_FAILED')
    b64_payload = base64.b64encode(encoded.tobytes())
    url = f"https://serverless.roboflow.com/{urllib.parse.quote(model_id, safe='/')}"
    req = urllib.request.Request(
        url,
        data=b64_payload,
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}',
            'X-Roboflow-Api-Key': api_key,
        },
        method='POST',
    )
    t0 = time.perf_counter()
    if check is not None:
        check()
    with urllib.request.urlopen(req, timeout=max(0.5, min(float(timeout_s), HOSTED_CALL_TIMEOUT_SECONDS))) as resp:
        raw = resp.read(MAX_RESPONSE_BYTES + 1)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    if check is not None:
        check()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError('HOSTED_RESPONSE_TOO_LARGE')
    data = json.loads(raw.decode('utf-8'))
    return data, rf_scale, elapsed_ms


def build_composite_model_identity(
    provider_model_id: str,
    model_version: str,
    declared_classes: tuple[str, ...],
    predictions: list,
    package_id: str | None = None,
) -> dict:
    observed = sorted(
        {
            str(p.get('class') or '').strip()
            for p in (predictions or [])
            if isinstance(p, dict) and str(p.get('class') or '').strip()
        }
    )
    declared = list(declared_classes)
    composite_id = (
        f"{provider_model_id}@{model_version}"
        f"#declared={','.join(declared)}"
        f"#observed={','.join(observed)}"
    )
    return dict(
        providerModelId=provider_model_id,
        modelVersion=model_version,
        declaredClassList=declared,
        observedResponseClasses=observed,
        roboflowPackageId=package_id,
        packageIdNote='Roboflow model_package_id can collide across model sizes (e.g. R1 Small vs Large); compositeIdentity is authoritative.',
        compositeIdentity=composite_id,
    )


def infer_lesion_large(
    bgr: np.ndarray,
    *,
    hosted_research_consent: bool = False,
    timeout_s: float = HOSTED_CALL_TIMEOUT_SECONDS,
    check: Callable[[], None] | None = None,
) -> dict:
    if not hosted_research_consent:
        return dict(valid=False, reason='HOSTED_RESEARCH_CONSENT_REQUIRED', boxes=[], rejected=[])
    if os.environ.get('ATTUNE_EXPERIMENTAL_HOSTED_SKIN_RESEARCH') != '1':
        return dict(valid=False, reason='HOSTED_RESEARCH_FLAG_DISABLED', boxes=[], rejected=[])
    api_key = os.environ.get('ATTUNE_ROBOFLOW_API_KEY') or os.environ.get('ROBOFLOW_API_KEY')
    if not api_key:
        return dict(valid=False, reason='HOSTED_CREDENTIALS_MISSING', boxes=[], rejected=[])
    t0 = time.perf_counter()
    try:
        data, rf_scale, elapsed_ms = _bounded_roboflow_post(
            bgr, LESION_LARGE_MODEL_ID, api_key, timeout_s=timeout_s, check=check
        )
    except Exception as exc:
        if exc.__class__.__name__ == 'NativeRequestStopped':
            raise
        return dict(
            valid=False,
            reason='HOSTED_CALL_FAILED_OR_TIMEOUT',
            boxes=[],
            rejected=[],
            timeoutSeconds=timeout_s,
            inferenceMs=round((time.perf_counter() - t0) * 1000.0, 2),
        )
    if not isinstance(data, dict):
        return dict(valid=False, reason='HOSTED_INVALID_RESPONSE', boxes=[], rejected=[], inferenceMs=elapsed_ms)

    resolved = data.get('resolved_model') or {}
    pkg_id = resolved.get('model_package_id')
    preds = data.get('predictions') or []
    identity = build_composite_model_identity(
        LESION_LARGE_MODEL_ID,
        LESION_LARGE_VERSION,
        LESION_DECLARED_CLASSES,
        preds,
        package_id=str(pkg_id) if pkg_id else None,
    )
    boxes = []
    rejected = []
    h, w = bgr.shape[:2]
    inv_scale = 1.0 / rf_scale
    for idx, p in enumerate(preds):
        if not isinstance(p, dict):
            continue
        cls_name = str(p.get('class') or '').strip().lower()
        conf = float(p.get('confidence') or 0.0)
        cx = float(p.get('x') or 0.0) * inv_scale
        cy = float(p.get('y') or 0.0) * inv_scale
        bw = float(p.get('width') or 0.0) * inv_scale
        bh = float(p.get('height') or 0.0) * inv_scale
        x1 = max(0.0, cx - bw / 2.0)
        y1 = max(0.0, cy - bh / 2.0)
        x2 = min(float(w), cx + bw / 2.0)
        y2 = min(float(h), cy + bh / 2.0)
        if cls_name not in VALIDATION_LESION_THRESHOLDS:
            rejected.append(
                dict(
                    index=idx,
                    rawClass=cls_name,
                    confidence=round(conf, 4),
                    reason='CLASS_NOT_IN_APPROVED_LESION_SET',
                )
            )
            continue
        min_thr = VALIDATION_LESION_THRESHOLDS[cls_name]
        if conf < min_thr:
            rejected.append(
                dict(
                    index=idx,
                    rawClass=cls_name,
                    confidence=round(conf, 4),
                    threshold=min_thr,
                    reason='BELOW_VALIDATION_CLASS_THRESHOLD',
                )
            )
            continue
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append([x1, y1, x2, y2, conf, cls_name])

    return dict(
        valid=True,
        researchOnly=True,
        mixedIntoProductMeasurements=False,
        methodVersion=LESION_METHOD_VERSION,
        modelVersion=LESION_LARGE_VERSION,
        providerModelId=LESION_LARGE_MODEL_ID,
        modelIdentity=identity,
        compositeModelIdentity=identity['compositeIdentity'],
        consentScope=HOSTED_RESEARCH_CONSENT_SCOPE,
        boxes=boxes,
        rejected=rejected,
        inferenceId=data.get('inference_id'),
        timeoutSeconds=timeout_s,
        inferenceMs=elapsed_ms,
        coordinateSpace='source-pixels',
        mapType='research-detection-boxes',
        thresholdStatus='validation-selected-27-image-unlocked',
        thresholds=dict(VALIDATION_LESION_THRESHOLDS),
    )


def infer_regional_oily_seg(
    bgr: np.ndarray,
    gray_shape: tuple[int, int],
    scale: float,
    origin: tuple[int, int],
    valid_skin: np.ndarray,
    acne_exclusion: np.ndarray,
    hair: np.ndarray,
    *,
    hosted_research_consent: bool = False,
    timeout_s: float = HOSTED_CALL_TIMEOUT_SECONDS,
    check: Callable[[], None] | None = None,
) -> dict:
    if not hosted_research_consent:
        return dict(valid=False, reason='HOSTED_RESEARCH_CONSENT_REQUIRED', mask=None)
    if os.environ.get('ATTUNE_EXPERIMENTAL_HOSTED_SKIN_RESEARCH') != '1':
        return dict(valid=False, reason='HOSTED_RESEARCH_FLAG_DISABLED', mask=None)
    api_key = os.environ.get('ATTUNE_ROBOFLOW_API_KEY') or os.environ.get('ROBOFLOW_API_KEY')
    if not api_key:
        return dict(valid=False, reason='HOSTED_CREDENTIALS_MISSING', mask=None)
    t0 = time.perf_counter()
    try:
        data, rf_scale, elapsed_ms = _bounded_roboflow_post(
            bgr, REGIONAL_SEG_MODEL_ID, api_key, timeout_s=timeout_s, check=check
        )
    except Exception as exc:
        if exc.__class__.__name__ == 'NativeRequestStopped':
            raise
        return dict(
            valid=False,
            reason='HOSTED_CALL_FAILED_OR_TIMEOUT',
            mask=None,
            timeoutSeconds=timeout_s,
            inferenceMs=round((time.perf_counter() - t0) * 1000.0, 2),
        )
    if not isinstance(data, dict):
        return dict(valid=False, reason='HOSTED_INVALID_RESPONSE', mask=None, inferenceMs=elapsed_ms)

    resolved = data.get('resolved_model') or {}
    pkg_id = resolved.get('model_package_id')
    preds = data.get('predictions') or []
    identity = build_composite_model_identity(
        REGIONAL_SEG_MODEL_ID,
        REGIONAL_SEG_VERSION,
        REGIONAL_SEG_DECLARED_CLASSES,
        preds,
        package_id=str(pkg_id) if pkg_id else None,
    )
    x0, y0 = origin
    raw_oily = np.zeros(gray_shape, np.uint8)
    oily_polys = 0
    inv_rf_scale = 1.0 / rf_scale
    for p in preds:
        if not isinstance(p, dict):
            continue
        cls_name = str(p.get('class') or '').strip().lower()
        conf = float(p.get('confidence') or 0.0)
        pts = p.get('points') or []
        if cls_name == 'oily' and conf >= OILY_SEG_MIN_CONFIDENCE and len(pts) >= 3:
            poly = np.asarray(
                [
                    [(float(pt['x']) * inv_rf_scale - x0) * scale, (float(pt['y']) * inv_rf_scale - y0) * scale]
                    for pt in pts
                ],
                np.int32,
            )
            cv2.fillPoly(raw_oily, [poly], 255)
            oily_polys += 1

    # Strict anatomical clipping: never bleed into eyes, lips, brows, nostrils, hair, or outside face support.
    allowed_support = valid_skin & (acne_exclusion == 0) & ~hair
    clipped_mask = (raw_oily > 0) & allowed_support
    visible_px = max(1, int(allowed_support.sum()))
    research_coverage_pct = round(float(clipped_mask.sum()) * 100.0 / float(visible_px), 4)
    return dict(
        valid=True,
        researchOnly=True,
        mixedIntoProductMeasurements=False,
        methodVersion=REGIONAL_SEG_METHOD_VERSION,
        modelVersion=REGIONAL_SEG_VERSION,
        providerModelId=REGIONAL_SEG_MODEL_ID,
        modelIdentity=identity,
        compositeModelIdentity=identity['compositeIdentity'],
        consentScope=HOSTED_RESEARCH_CONSENT_SCOPE,
        mask=clipped_mask,
        researchVisibleAreaPercent=research_coverage_pct,
        oilyPolygonCount=oily_polys,
        rawPixels=int((raw_oily > 0).sum()),
        clippedPixels=int(clipped_mask.sum()),
        clippedToAnatomy=True,
        inferenceId=data.get('inference_id'),
        timeoutSeconds=timeout_s,
        inferenceMs=elapsed_ms,
        thresholdStatus='locked-research-threshold-0.35-validation-optimum-0.31',
        threshold=OILY_SEG_MIN_CONFIDENCE,
        validationOptimumThreshold=OILY_SEG_VALIDATION_OPTIMUM,
    )
