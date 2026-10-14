"""TOGG Attune Skin Feature Integration Adapters for CDC Delivery
Provides clean product integration adapters for:
1. Sivilce (Acne) - YOLOX-S P2 small-lesion detector (PyTorch and ONNX)
2. Kuruluk (Dryness) - Calibrated source-group material classifier
3. Sarkma (Sagging) - Granular expression gate and smooth contour prominence tracker

CDC integration contract:
- Does NOT write to CDC directories directly.
- Standardizes input/output contracts, error reason codes, and tensor formats.
- All scores are appearance proxies, not clinical diagnostic truth.
"""

from pathlib import Path
import os
import json
import time
import hashlib
import numpy as np
import cv2

# ==============================================================================
# 1. KURULUK (DRYNESS) ADAPTER
# ==============================================================================

class CalibratedDrynessAdapter:
    """CDC adapter for calibrated material classification on native dryness paths.
    Eliminates the 10x visual suppression penalty from legacy featureGroupSizes,
    preventing pore texture false positives at half-scale while restoring true
    material flakes on glasses-free targets.
    """
    ENCODER_SAFELAYERS_SHA = 'e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a'
    ENCODER_ONNX_SHA = 'a93e5445326c8071cd4d013b6fde494d9054dd4842dacf97028ceaefc9eb1987'

    def __init__(self, head_path=None, encoder_path=None, onnx_receipt_path=None, use_onnx=True):
        repo_root = Path(__file__).resolve().parents[2]
        if head_path is None:
            # Look in standard delivery or calibration artifacts
            candidates = [
                repo_root / 'audit-results' / 'cdc-delivery-20261014-v2' / 'dryness' / 'calibrated-source-group-head.json',
                repo_root / 'audit-results' / 'cdc-delivery-20261014' / 'dryness' / 'calibrated-source-group-head.json',
                repo_root / 'audit-results' / 'material-calibrated-20261014' / 'calibrated-source-group-head.json'
            ]
            for c in candidates:
                if c.exists():
                    head_path = c
                    break
            if head_path is None or not Path(head_path).exists():
                raise FileNotFoundError(f"CalibratedDrynessAdapter: head file not found in candidates: {[str(p) for p in candidates]}")

        with open(head_path, 'r', encoding='utf-8') as f:
            self.head = json.load(f)
        self.head_path = str(head_path)
        self.threshold = float(self.head.get('threshold', 0.50))
        self.use_onnx = use_onnx
        self.encoder_path = encoder_path
        self.onnx_receipt_path = onnx_receipt_path
        self._encoder = None

    def _candidate_search_roots(self):
        roots = []
        if 'ATTUNE_ROOT' in os.environ:
            roots.append(Path(os.environ['ATTUNE_ROOT']))
        if 'CDC_ROOT' in os.environ:
            roots.append(Path(os.environ['CDC_ROOT']))

        this_repo = Path(__file__).resolve().parents[2]
        if this_repo not in roots:
            roots.append(this_repo)

        try:
            import material_component_features
            mcf_repo = Path(material_component_features.__file__).resolve().parents[2]
            if mcf_repo not in roots:
                roots.append(mcf_repo)
        except Exception:
            pass
        return roots

    def _discover_encoder(self):
        """Discovers verified encoder without hardcoded machine-specific fallbacks."""
        roots = self._candidate_search_roots()

        # Try ONNX first if requested
        if self.use_onnx:
            for root in roots:
                onnx_p = root / 'audit-results' / 'material-runtime-followup-20261013' / 'material-encoder.onnx'
                receipt_p = root / 'audit-results' / 'material-runtime-followup-20261013' / 'encoder-parity.json'
                if onnx_p.exists() and receipt_p.exists():
                    h = hashlib.sha256(onnx_p.read_bytes()).hexdigest()
                    if h.lower() == self.ENCODER_ONNX_SHA.lower():
                        return 'onnx', str(onnx_p), str(receipt_p)

        # Try PyTorch safetensors
        for root in roots:
            safe_p = root / 'audit-results' / 'focused-skin-20261010' / 'pretrained' / 'efficientnet_b0_rwightman-7f5810bc.pth.safetensors'
            if safe_p.exists():
                h = hashlib.sha256(safe_p.read_bytes()).hexdigest()
                if h.lower() == self.ENCODER_SAFELAYERS_SHA.lower():
                    return 'pytorch', str(safe_p), None

        raise FileNotFoundError(
            f"CalibratedDrynessAdapter: verified encoder not found in search roots: {[str(r) for r in roots]}. "
            f"Expected ONNX SHA-256: {self.ENCODER_ONNX_SHA} or safetensors SHA-256: {self.ENCODER_SAFELAYERS_SHA}."
        )

    @property
    def encoder(self):
        if self._encoder is None:
            import material_component_features as M
            if self.encoder_path is not None:
                enc_p = Path(self.encoder_path)
                if not enc_p.exists():
                    raise FileNotFoundError(f"CalibratedDrynessAdapter: explicit encoder path does not exist: {self.encoder_path}")
                if enc_p.suffix == '.onnx':
                    if self.onnx_receipt_path is None:
                        self.onnx_receipt_path = enc_p.parent / 'encoder-parity.json'
                    self._encoder = M.OnnxMaterialEncoder(enc_p, self.onnx_receipt_path)
                else:
                    self._encoder = M.FrozenMaterialEncoder(enc_p)
            else:
                enc_type, enc_path, receipt_path = self._discover_encoder()
                self.encoder_path = enc_path
                self.onnx_receipt_path = receipt_path
                if enc_type == 'onnx':
                    self._encoder = M.OnnxMaterialEncoder(enc_path, receipt_path)
                else:
                    self._encoder = M.FrozenMaterialEncoder(enc_path)
        return self._encoder

    def get_filter(self, check=None, details=None):
        """Returns a material_filter callback compatible with native_dry_path.analyze_native_dry."""
        from material_component_features import filter_material_support_streamed
        return lambda image, field, metric: filter_material_support_streamed(
            image, field, metric, self.encoder, self.head, check=check, details=details
        )

    def analyze(self, payload, check=None, details=None):
        """Execute full native dryness analysis pipeline with calibrated material classification."""
        from native_dry_path import analyze_native_dry
        return analyze_native_dry(payload, material_filter=self.get_filter(check=check, details=details), check=check)


# ==============================================================================
# 2. SARKMA (SAGGING) ADAPTER
# ==============================================================================

class ContourSaggingAdapter:
    """CDC adapter for contour appearance and jawline / cheek sagging analysis.
    Implements:
    - Disambiguated expression rejection codes (EXPRESSION_OPEN_MOUTH, EXPRESSION_SMILE,
      EXPRESSION_FROWN, EXPRESSION_CHEEK_PUFF, EXPRESSION_MOUTH_PRESS, EXPRESSION_PUCKER).
    - Separation of resting full lips (jawOpen < 0.004, lip_width_ratio >= 0.35) from
      true active pucker (mouthPucker > 0.50 with narrow lips or funnel).
    - Continuous boundary tracing and smooth prominence support without requiring
      isolated sharp fold lines.
    """
    def __init__(self):
        pass

    def evaluate_expression_gate(self, payload, mouth, smile, lip_width_ratio=None):
        """Disambiguated expression gating logic."""
        import contour_appearance
        return contour_appearance.expression_reason(payload, mouth, smile, lip_width_ratio)

    def analyze_fold(self, payload):
        """Full native fold appearance analysis via instant_proxy with calibrated expression gate."""
        import appearance_analysis
        return appearance_analysis.analyze_skin(payload)

    def analyze(self, payload, check=None):
        """Full native contour appearance analysis."""
        import contour_appearance
        return contour_appearance.analyze_contour(payload, check=check)


# ==============================================================================
# 3. SİVİLCE (ACNE) ADAPTER
# ==============================================================================

class AcneSmallFociAdapter:
    """CDC adapter for YOLOX-S P2 small-foci detection.
    Supports both PyTorch (.safetensors) and ONNX (.onnx) runtime execution.
    Preserves strict preprocessing (BGR, 384x384, [0, 255]) and postprocessing contracts.
    """
    def __init__(self, model_path=None, use_onnx=True, conf_threshold=0.30, nms_threshold=0.30):
        self.use_onnx = use_onnx
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.model_path = model_path
        self._session = None
        self._pytorch_net = None

        if self.model_path is None:
            repo_root = Path(__file__).resolve().parents[2]
            candidates = [
                repo_root / 'audit-results' / 'cdc-delivery-20261014-v2' / ('onnx/model.onnx' if use_onnx else 'weights/candidate-selected.safetensors'),
                repo_root / 'audit-results' / 'cdc-delivery-20261014' / ('onnx/model.onnx' if use_onnx else 'weights/candidate-selected.safetensors'),
                repo_root / 'audit-results' / 'acne-candidate-p2-small-foci-20261014' / ('model.onnx' if use_onnx else 'candidate-selected.safetensors'),
            ]
            for c in candidates:
                if c.exists():
                    self.model_path = str(c)
                    break

    def _init_onnx(self):
        if self.model_path is None or not Path(self.model_path).exists():
            raise FileNotFoundError(f"AcneSmallFociAdapter: ONNX model path not found: {self.model_path}")
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        self._session = ort.InferenceSession(self.model_path, opts, providers=['CPUExecutionProvider'])

    def _init_pytorch(self):
        if self.model_path is None or not Path(self.model_path).exists():
            raise FileNotFoundError(f"AcneSmallFociAdapter: PyTorch model path not found: {self.model_path}")
        import sys
        import torch
        from safetensors.torch import load_file
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root / 'scripts' / 'skin-research'))
        from yolox_p2 import build_yolox_p2_model
        net = build_yolox_p2_model(num_classes=1)
        state_dict = load_file(self.model_path)
        net.load_state_dict(state_dict, strict=True)
        net.eval()
        self._pytorch_net = net

    def predict_tile(self, tile_bgr_float32):
        """tile_bgr_float32: numpy array of shape (1, 3, 384, 384) in range [0.0, 255.0].
        Returns: raw detection tensor (1, 12240, 6) [cx, cy, w, h, obj_conf, cls_conf].
        """
        if self.use_onnx:
            if self._session is None:
                self._init_onnx()
            inputs = {self._session.get_inputs()[0].name: tile_bgr_float32.astype(np.float32)}
            outputs = self._session.run(None, inputs)
            return outputs[0]
        else:
            if self._pytorch_net is None:
                self._init_pytorch()
            import torch
            with torch.no_grad():
                t = torch.from_numpy(tile_bgr_float32).float()
                out = self._pytorch_net(t)
                return out.cpu().numpy()

    def postprocess_detections(self, raw_pred, conf_thresh=None):
        """Decode raw prediction boxes, apply confidence thresholding and NMS.
        raw_pred: shape (1, 12240, 6) or (12240, 6)
        """
        if conf_thresh is None:
            conf_thresh = self.conf_threshold
        
        pred = raw_pred[0] if raw_pred.ndim == 3 else raw_pred
        scores = pred[:, 4] * pred[:, 5]
        mask = scores >= conf_thresh
        if not np.any(mask):
            return np.empty((0, 5), dtype=np.float32)

        boxes = pred[mask, :4].copy()
        scored = scores[mask]

        # Convert cx, cy, w, h to x1, y1, x2, y2
        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        x2 = boxes[:, 0] + boxes[:, 2] / 2
        y2 = boxes[:, 1] + boxes[:, 3] / 2

        # Fast NMS
        order = scored.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            area_i = (x2[i] - x1[i]) * (y2[i] - y1[i])
            area_rest = (x2[order[1:]] - x1[order[1:]]) * (y2[order[1:]] - y1[order[1:]])
            union = area_i + area_rest - inter
            iou = inter / np.maximum(union, 1e-8)

            inds = np.where(iou <= self.nms_threshold)[0]
            order = order[inds + 1]

        kept_boxes = np.column_stack([x1[keep], y1[keep], x2[keep], y2[keep], scored[keep]])
        return kept_boxes.astype(np.float32)
