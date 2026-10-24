"""Hosted Roboflow skin model integration for Lesion RF-DETR Large (m3) and
Regional NAS Seg (m6).

Credentials are read strictly from environment variables (ROBOFLOW_API_KEY or
ATTUNE_ROBOFLOW_API_KEY). Never runs without explicit hosted_consent=True.
"""
from __future__ import annotations
import os, time
import cv2, numpy as np

LESION_LARGE_MODEL_ID = 'tolgar-sasmaz/lesion-detection-ruc40-qzwqz-1-rfdetr-large-t1'
REGIONAL_SEG_MODEL_ID = 'tolgar-sasmaz/attune-skin-regional-skin-map-1-rfdetr-nas-seg-t1--e79545'

APPROVED_LESION_THRESHOLDS = {
    'papule': 0.35,
    'pustule': 0.26,
    'open_comedo': 0.26,
    'closed_comedo': 0.29,
}
OILY_SEG_MIN_CONFIDENCE = 0.45
_CLIENT_CACHE: dict[str, object] = {}


def _get_client(api_key: str):
    cached = _CLIENT_CACHE.get(api_key)
    if cached is not None:
        return cached
    from inference_sdk import InferenceConfiguration, InferenceHTTPClient
    client = InferenceHTTPClient(api_url='https://serverless.roboflow.com', api_key=api_key)
    client.configure(
        InferenceConfiguration(
            api_key_transport='header',
            workflow_run_retries_enabled=False,
            disable_active_learning=True,
        )
    )
    _CLIENT_CACHE[api_key] = client
    return client


def _prepare_inference_image(bgr: np.ndarray, max_dim: int = 1024) -> tuple[np.ndarray, float]:
    h, w = bgr.shape[:2]
    scale = min(1.0, float(max_dim) / float(max(h, w, 1)))
    if scale < 1.0:
        resized = cv2.resize(bgr, (max(1, int(round(w * scale))), max(1, int(round(h * scale)))), interpolation=cv2.INTER_AREA)
        return resized, scale
    return bgr, 1.0


def infer_lesion_large(bgr: np.ndarray, hosted_consent: bool = False) -> dict:
    if not hosted_consent:
        return dict(valid=False, reason='HOSTED_INFERENCE_PERMISSION_DENIED', boxes=[], rejected=[])
    api_key = os.environ.get('ATTUNE_ROBOFLOW_API_KEY') or os.environ.get('ROBOFLOW_API_KEY')
    if not api_key:
        return dict(valid=False, reason='HOSTED_CREDENTIALS_MISSING', boxes=[], rejected=[])
    t0 = time.perf_counter()
    try:
        client = _get_client(api_key)
        inf_img, rf_scale = _prepare_inference_image(bgr)
        data = client.infer(inf_img, model_id=LESION_LARGE_MODEL_ID)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    except Exception:
        return dict(
            valid=False,
            reason='HOSTED_CALL_FAILED',
            boxes=[],
            rejected=[],
            inferenceMs=round((time.perf_counter() - t0) * 1000.0, 2),
        )
    if not isinstance(data, dict):
        return dict(valid=False, reason='HOSTED_INVALID_RESPONSE', boxes=[], rejected=[], inferenceMs=elapsed_ms)

    resolved = data.get('resolved_model') or {}
    pkg_id = resolved.get('model_package_id') or 'lesion-rfdetr-large-t1'
    preds = data.get('predictions') or []
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
        if cls_name not in APPROVED_LESION_THRESHOLDS:
            rejected.append(
                dict(
                    index=idx,
                    rawClass=cls_name,
                    confidence=round(conf, 4),
                    reason='CLASS_NOT_IN_APPROVED_LESION_SET',
                )
            )
            continue
        min_thr = APPROVED_LESION_THRESHOLDS[cls_name]
        if conf < min_thr:
            rejected.append(
                dict(
                    index=idx,
                    rawClass=cls_name,
                    confidence=round(conf, 4),
                    threshold=min_thr,
                    reason='BELOW_CALIBRATED_CLASS_THRESHOLD',
                )
            )
            continue
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append([x1, y1, x2, y2, conf, cls_name])

    return dict(
        valid=True,
        boxes=boxes,
        rejected=rejected,
        modelVersion='roboflow-lesion-rfdetr-large-t1',
        providerModelId=LESION_LARGE_MODEL_ID,
        modelHash=str(pkg_id),
        inferenceId=data.get('inference_id'),
        tileCount=1,
        loadMs=0.0,
        inferenceMs=elapsed_ms,
        coordinateSpace='source-pixels',
        mapType='detection-boxes',
        thresholds=dict(APPROVED_LESION_THRESHOLDS),
    )


def infer_regional_oily_seg(
    bgr: np.ndarray,
    gray_shape: tuple[int, int],
    scale: float,
    origin: tuple[int, int],
    valid_skin: np.ndarray,
    acne_exclusion: np.ndarray,
    hair: np.ndarray,
    hosted_consent: bool = False,
) -> dict:
    if not hosted_consent:
        return dict(valid=False, reason='HOSTED_INFERENCE_PERMISSION_DENIED', mask=None)
    api_key = os.environ.get('ATTUNE_ROBOFLOW_API_KEY') or os.environ.get('ROBOFLOW_API_KEY')
    if not api_key:
        return dict(valid=False, reason='HOSTED_CREDENTIALS_MISSING', mask=None)
    t0 = time.perf_counter()
    try:
        client = _get_client(api_key)
        inf_img, rf_scale = _prepare_inference_image(bgr)
        data = client.infer(inf_img, model_id=REGIONAL_SEG_MODEL_ID)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    except Exception:
        return dict(
            valid=False,
            reason='HOSTED_CALL_FAILED',
            mask=None,
            inferenceMs=round((time.perf_counter() - t0) * 1000.0, 2),
        )
    if not isinstance(data, dict):
        return dict(valid=False, reason='HOSTED_INVALID_RESPONSE', mask=None, inferenceMs=elapsed_ms)

    resolved = data.get('resolved_model') or {}
    pkg_id = resolved.get('model_package_id') or 'regional-nas-seg-e79545'
    preds = data.get('predictions') or []
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
                [[(float(pt['x']) * inv_rf_scale - x0) * scale, (float(pt['y']) * inv_rf_scale - y0) * scale] for pt in pts],
                np.int32,
            )
            cv2.fillPoly(raw_oily, [poly], 255)
            oily_polys += 1

    # Strict anatomical clipping: never bleed into eyes, lips, brows, nostrils, hair, or outside face support.
    allowed_support = valid_skin & (acne_exclusion == 0) & ~hair
    clipped_mask = (raw_oily > 0) & allowed_support
    return dict(
        valid=True,
        mask=clipped_mask,
        oilyPolygonCount=oily_polys,
        rawPixels=int((raw_oily > 0).sum()),
        clippedPixels=int(clipped_mask.sum()),
        clippedToAnatomy=True,
        modelVersion='roboflow-regional-nas-seg-e79545',
        providerModelId=REGIONAL_SEG_MODEL_ID,
        modelHash=str(pkg_id),
        inferenceId=data.get('inference_id'),
        inferenceMs=elapsed_ms,
        threshold=OILY_SEG_MIN_CONFIDENCE,
    )
