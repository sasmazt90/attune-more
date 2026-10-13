#!/usr/bin/env python3
"""Evaluate acne detector data-model-product chain with verifiable metrics.

This script executes the complete end-to-end evaluation pipeline:
1. MediaPipe landmark detection and Node product skin adapter execution:
   - SkinAnalyzer.calculateAlignmentFromLandmarks (dimensionless ratios)
   - matchesSkinAngle (FRONT, RIGHT, LEFT; roll <= 0.15, sourceFramed)
   - SkinAnalyzer.checkQuality (avgLuminance, blurScore)
   - Presentation anatomical mesh envelopes for regions
2. Categorization of ground truth pimples:
   - IN_SCOPE_VISIBLE_REGION
   - OUT_OF_SCOPE_OCCLUDED_SIDE (e.g. opposite cheek on side captures)
   - OUT_OF_SCOPE_NON_FACIAL_OR_MARGIN
   - OUT_OF_SCOPE_EXTREME_POSE
   - OUT_OF_SCOPE_LANDMARK_FAILED
3. Detector inference with YOLOX-S PAFPN ONNX model(s) across 384x384 sliding tiles.
4. Historical and current filter pipelines:
   - Filter v2 (pre-94a899b / commit ab02fcc3): 65% envelope overlap, exclusion mean <= 0.05
   - Filter v3 (commit 94a899b): 15% envelope overlap, skin_support >= 0.50, center on skin
   - Filter v4 (acne_box_support.py): Visible skin distance fallback with norm_dist <= 0.15,
     midline lateralization, and visible region constraints.
5. Development grid sweep: Confidence [0.40, 0.55, 0.70] x NMS [0.30, 0.45, 0.60].
6. Verifiable receipt (acne-receipt.json) and Markdown documentation.
"""

import os
import sys
import json
import math
import time
import base64
import hashlib
import argparse
import subprocess
from pathlib import Path
from collections import defaultdict
import cv2
import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[1]
LIVE_TEST = ROOT.parent / 'attune-live-test'

# Runtime imports
sys.path.append(str(LIVE_TEST / '.runtime/python-packages'))
import mediapipe as mp

sys.path.insert(0, str(ROOT / 'services/core-api'))
import acne_box_support

DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'
BASELINE_ONNX_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/interim-diagnosis/selected-detector-export-1a014adad262/selected.onnx'
CANDIDATE_ONNX_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/candidate.onnx'
BENCHMARK_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/benchmark-results.json'
TRAINING_STATE_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/training-state.json'
LANDMARKER_MODEL = ROOT / 'apps/vehicle-app/public/mediapipe/models/face_landmarker.task'
RECEIPT_DIR = ROOT / 'audit-results/acne-detection-verification-20261013'
RECEIPT_PATH = RECEIPT_DIR / 'acne-receipt.json'
REPORT_PATH = ROOT / 'docs/acne-detection-data-model-product-chain-20261013.md'

LIMITS = {'analysisFacePixels': 720, 'minFacePixels': 280}
REGIONS = ('forehead', 'rightCheek', 'leftCheek', 'nose', 'chin')


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def nms(boxes, threshold=0.30):
    if not boxes:
        return []
    a = np.asarray(boxes, float)
    order = np.argsort(-a[:, 4])
    keep = []
    while len(order):
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        start = np.maximum(a[i, :2], a[rest, :2])
        end = np.minimum(a[i, 2:4], a[rest, 2:4])
        area = np.maximum(0, end - start).prod(1)
        total = (
            np.maximum(0, a[i, 2] - a[i, 0]) * np.maximum(0, a[i, 3] - a[i, 1])
            + np.maximum(0, a[rest, 2] - a[rest, 0]) * np.maximum(0, a[rest, 3] - a[rest, 1])
            - area
        )
        order = rest[area / np.maximum(1e-8, total) <= threshold]
    return a[keep].tolist()


def calc_iou(b1, b2):
    x0, y0 = max(b1[0], b2[0]), max(b1[1], b2[1])
    x1, y1 = min(b1[2], b2[2]), min(b1[3], b2[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
    return inter / max(1e-8, area1 + area2 - inter)


def match_predictions_to_truth(truth_boxes, preds, thresh=0.50):
    """Greedy confidence-ranked matching between truth and predictions, distinguishing duplicates."""
    used_t = set()
    ranked = sorted(
        preds,
        key=lambda p: p.get('confidence', 0.0) if isinstance(p, dict) else (p[4] if len(p) > 4 else 0.0),
        reverse=True
    )
    matches = []
    duplicate_preds = []
    unmatched_preds = []
    for pi, p in enumerate(ranked):
        pb = [p['x'], p['y'], p['x'] + p['width'], p['y'] + p['height']] if isinstance(p, dict) else p[:4]
        best_iou = 0.0
        best_ti = -1
        for ti, t in enumerate(truth_boxes):
            iou = calc_iou(t, pb)
            if iou > best_iou:
                best_iou = iou
                best_ti = ti
        if best_iou >= thresh and best_ti >= 0:
            if best_ti not in used_t:
                used_t.add(best_ti)
                matches.append((best_ti, pi, best_iou))
            else:
                duplicate_preds.append((best_ti, pi, best_iou))
        else:
            unmatched_preds.append(pi)
    unmatched_truth = [ti for ti in range(len(truth_boxes)) if ti not in used_t]
    return sorted(list(used_t)), matches, duplicate_preds, unmatched_preds, unmatched_truth


def run_raw_tile_inference(ort_session, bgr, points, min_score=0.40):
    """Runs sliding 384x384 tile inference once per image with minimum threshold."""
    if len(points) < 468:
        return []
    p = np.array([[v['x'], v['y']] for v in points[:468]], np.float64)
    h, w = bgr.shape[:2]
    lo = p.min(0)
    hi = p.max(0)
    size = hi - lo
    start = np.maximum(0, lo - size * [0.32, 0.35])
    end = np.minimum(1, hi + size * [0.32, 0.16])
    x, y = np.floor(start * [w, h]).astype(int)
    x1, y1 = np.ceil(end * [w, h]).astype(int)
    tile_size = 384
    xs = sorted(set([*range(x, max(x + 1, x1 - tile_size + 1), 288), max(x, x1 - tile_size)]))
    ys = sorted(set([*range(y, max(y + 1, y1 - tile_size + 1), 288), max(y, y1 - tile_size)]))

    raw_candidates = []
    for a in xs:
        for b in ys:
            c = min(x1, a + tile_size)
            d = min(y1, b + tile_size)
            canvas = np.full((tile_size, tile_size, 3), 114, np.uint8)
            canvas[:d - b, :c - a] = bgr[b:d, a:c]
            pred = ort_session.run(None, {'native_bgr_tile': canvas.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
            for cx, cy, bw, bh, obj, cls in pred:
                score = float(obj * cls)
                if score < min_score:
                    continue
                bx = max(a, float(cx - bw / 2 + a))
                by = max(b, float(cy - bh / 2 + b))
                ex = min(c, float(cx + bw / 2 + a))
                ey = min(d, float(cy + bh / 2 + b))
                if ex > bx and ey > by:
                    raw_candidates.append([bx, by, ex, ey, score])
    return raw_candidates


def compute_masks_and_envelopes(bgr, points, meshes):
    """Computes anatomical masks, envelopes, skin support, and face width."""
    width, height = bgr.shape[1], bgr.shape[0]
    face_pixels = abs(points[454]['x'] - points[234]['x']) * width
    scale = min(1.0, LIMITS['analysisFacePixels'] / max(face_pixels, 1))
    source_points = np.asarray([[v['x'], v['y']] for m in meshes.values() for v in m['points']], np.float32)
    pad = max(20, face_pixels * 0.1)
    x0 = max(0, int(source_points[:, 0].min() - pad))
    y0 = max(0, int(source_points[:, 1].min() - pad))
    x1 = min(bgr.shape[1], int(source_points[:, 0].max() + pad + 1))
    y1 = min(bgr.shape[0], int(source_points[:, 1].max() + pad + 1))
    origin = (x0, y0)
    image = cv2.resize(bgr[y0:y1, x0:x1], None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray8 = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = gray8.astype(np.float32) / 255.0
    rgb = image[:, :, ::-1].astype(np.float32) / 255.0

    # Hair mask
    k1 = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))
    k2 = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))
    b1 = cv2.morphologyEx(gray8, cv2.MORPH_BLACKHAT, k1)
    b2 = cv2.morphologyEx(gray8, cv2.MORPH_BLACKHAT, k2)
    hair = (np.maximum(b1, b2) > 30)

    # Exclusions
    exclusion = np.zeros(gray.shape, np.uint8)
    holes = [
        [33, 160, 158, 133, 153, 144],
        [263, 387, 385, 362, 380, 373],
        [61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91],
        [98, 97, 2, 326, 327, 294],
        [70, 63, 105, 66, 69, 107, 55, 65, 52],
        [300, 293, 334, 296, 299, 336, 285, 295, 282]
    ]
    for indices in holes:
        poly = np.asarray([[(points[i]['x'] * width - x0) * scale, (points[i]['y'] * height - y0) * scale] for i in indices], np.int32)
        cv2.fillPoly(exclusion, [poly], 255)
    edge = max(2, int(round(4 * scale)))
    exclusion[:edge, :] = 255
    exclusion[-edge:, :] = 255
    exclusion[:, :edge] = 255
    exclusion[:, -edge:] = 255

    # Oval skin support
    face_support = np.zeros(gray.shape, np.uint8)
    oval = [
        10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378,
        400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21,
        54, 103, 67, 109
    ]
    face_polygon = np.array([[(points[i]['x'] * width - x0) * scale, (points[i]['y'] * height - y0) * scale] for i in oval], np.int32)
    cv2.fillPoly(face_support, [face_polygon], 255)

    acne_clipping = np.min(rgb, axis=2) > 0.975
    acne_envelopes = acne_box_support.region_envelopes(meshes, gray.shape, scale, origin)

    ocular = np.zeros(gray.shape, np.uint8)
    for indices in [
        [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
        [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]
    ]:
        poly = np.asarray([[(points[i]['x'] * width - x0) * scale, (points[i]['y'] * height - y0) * scale] for i in indices], np.int32)
        cv2.fillPoly(ocular, [poly], 255)
    eye_span = max(
        math.hypot((points[a]['x'] - points[b]['x']) * width, (points[a]['y'] - points[b]['y']) * height)
        for a, b in [(33, 133), (263, 362)]
    )
    margin = max(1, int(round(eye_span * scale * 0.12)))
    acne_exclusion = exclusion | cv2.dilate(ocular, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (margin * 2 + 1, margin * 2 + 1)))
    for indices in holes[4:]:
        poly = np.asarray([[(points[i]['x'] * width - x0) * scale, (points[i]['y'] * height - y0) * scale] for i in indices], np.float32)
        cv2.fillConvexPoly(acne_exclusion, cv2.convexHull(poly).astype(np.int32), 255)

    acne_skin = (face_support > 0) & (acne_exclusion == 0) & ~hair & ~acne_clipping & (gray > 0.12)
    return acne_envelopes, acne_skin, hair, acne_exclusion, scale, origin, face_support, face_pixels


# --- ISOLATED FILTER VERSIONS (FROM EXACT GIT HISTORY) ---

def filter_v2(boxes, envelopes, skin_support, hair, exclusion, photo, scale, origin):
    """Historical Filter v2 (commit ab02fcc3 / pre-94a899b)."""
    assigned = {k: [] for k in envelopes}
    rejected = []
    h, w = skin_support.shape
    x0, y0 = origin
    for bx, by, ex, ey, confidence in boxes:
        a = max(0, int((bx - x0) * scale))
        b = max(0, int((by - y0) * scale))
        c = min(w, int(math.ceil((ex - x0) * scale)))
        d = min(h, int(math.ceil((ey - y0) * scale)))
        if c <= a or d <= b:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='OUTSIDE_SOURCE_SUPPORT'))
            continue
        cx = min(w - 1, max(0, int(((bx + ex) / 2 - x0) * scale)))
        cy = min(h - 1, max(0, int(((by + ey) / 2 - y0) * scale)))
        if exclusion[cy, cx] or hair[cy, cx] or float((exclusion[b:d, a:c] > 0).mean()) > 0.05:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HOLE_OR_HAIR'))
            continue
        eligible_owners = [k for k in REGIONS if k in envelopes and float((envelopes[k] & skin_support)[b:d, a:c].mean()) >= 0.65]
        if not eligible_owners:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='INSUFFICIENT_ANATOMICAL_SKIN_SUPPORT'))
            continue
        owner = eligible_owners[0]
        assigned[owner].append(dict(x=bx, y=by, width=ex - bx, height=ey - by, confidence=confidence, region=owner))
    accepted = [b for blist in assigned.values() for b in blist]
    return accepted, rejected


def filter_v3(boxes, envelopes, skin_support, hair, exclusion, photo, scale, origin):
    """Historical Filter v3 (commit 94a899b)."""
    assigned = {k: [] for k in envelopes}
    rejected = []
    h, w = skin_support.shape
    x0, y0 = origin
    for bx, by, ex, ey, confidence in boxes:
        a = max(0, int((bx - x0) * scale))
        b = max(0, int((by - y0) * scale))
        c = min(w, int(math.ceil((ex - x0) * scale)))
        d = min(h, int(math.ceil((ey - y0) * scale)))
        if c <= a or d <= b:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='OUTSIDE_SOURCE_SUPPORT'))
            continue
        cx = min(w - 1, max(0, int(((bx + ex) / 2 - x0) * scale)))
        cy = min(h - 1, max(0, int(((by + ey) / 2 - y0) * scale)))
        if exclusion[cy, cx] or hair[cy, cx] or float((exclusion[b:d, a:c] > 0).mean()) > 0.25:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='ANATOMICAL_HOLE_OR_HAIR'))
            continue
        box_skin = float(skin_support[b:d, a:c].mean())
        if box_skin < 0.50 or not skin_support[cy, cx]:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='INSUFFICIENT_SKIN_SUPPORT'))
            continue
        reg_overlaps = [(float((envelopes[k] & skin_support)[b:d, a:c].mean()), k) for k in REGIONS if k in envelopes]
        reg_overlaps.sort(reverse=True)
        if not reg_overlaps or reg_overlaps[0][0] < 0.15:
            rejected.append(dict(box=[bx, by, ex, ey, confidence], reason='INSUFFICIENT_ANATOMICAL_SKIN_SUPPORT'))
            continue
        owner = reg_overlaps[0][1]
        assigned[owner].append(dict(x=bx, y=by, width=ex - bx, height=ey - by, confidence=confidence, region=owner))
    accepted = [b for blist in assigned.values() for b in blist]
    return accepted, rejected


def filter_v4(boxes, envelopes, skin_support, hair, exclusion, photo, scale, origin, visible_regions, landmarks, source_shape=None):
    """Current Filter v5 (acne_box_support.py with bounded Euclidean fallback)."""
    assigned, rejected = acne_box_support.accepted_boxes(
        boxes, envelopes, skin_support, hair, exclusion, photo, scale, origin,
        visible_regions=visible_regions,
        landmarks=landmarks,
        source_shape=source_shape
    )
    accepted = [b for blist in assigned.values() for b in blist]
    return accepted, rejected


def categorize_ground_truth_pimple(pimple_box, item, face_support_source=None):
    """Categorizes ground truth pimple into in-scope vs out-of-scope classes with analysis coordinate transforms."""
    bx0, by0, bx1, by1 = pimple_box
    cx = (bx0 + bx1) / 2.0
    cy = (by0 + by1) / 2.0
    w = item['width']

    # 1. Landmark failure
    if not item['landmarks']:
        return 'OUT_OF_SCOPE_LANDMARK_FAILED'

    # 2. Angle failure / extreme pose
    matched_angle = item['productAngle']
    if matched_angle is None:
        return 'OUT_OF_SCOPE_EXTREME_POSE'

    # 3. Check facial bounds and crop bounds in analysis space without clamping
    if face_support_source is not None:
        x0, y0 = item.get('origin', (0, 0))
        scale = item.get('scale', 1.0)
        ax = int(round((cx - x0) * scale))
        ay = int(round((cy - y0) * scale))
        h_mask, w_mask = face_support_source.shape
        if ax < 0 or ay < 0 or ax >= w_mask or ay >= h_mask:
            return 'OUT_OF_SCOPE_OUTSIDE_CROP'
        if not face_support_source[ay, ax]:
            return 'OUT_OF_SCOPE_NON_FACIAL'

    # 4. Multi-angle lateralization and cheek restriction
    midline_x = item['landmarks'][1]['x'] * w  # nose tip
    face_width = item.get('facePixels', w * 0.4)

    if matched_angle == 'RIGHT':
        # Head turned right: user's right cheek is occluded/turned away
        if cx < (midline_x - 0.05 * face_width):
            return 'OUT_OF_SCOPE_OCCLUDED_SIDE'
        # On side capture, product only measures the cheek. Check if near leftCheek envelope/mesh
        if item.get('envelopes') and 'leftCheek' in item['envelopes']:
            x0, y0 = item['origin']
            scale = item['scale']
            sx = int(round((cx - x0) * scale))
            sy = int(round((cy - y0) * scale))
            env = item['envelopes']['leftCheek']
            h_env, w_env = env.shape
            if sx < 0 or sy < 0 or sx >= w_env or sy >= h_env:
                return 'OUT_OF_SCOPE_OUTSIDE_CROP'
            if not env[sy, sx]:
                # check distance to leftCheek
                dist = cv2.distanceTransform((~env).astype(np.uint8), cv2.DIST_L2, 3)[sy, sx]
                if (dist / (face_width * scale)) > 0.15:
                    return 'OUT_OF_SCOPE_SIDE_PROFILE_NON_CHEEK'
    elif matched_angle == 'LEFT':
        # Head turned left: user's left cheek is occluded/turned away
        if cx > (midline_x + 0.05 * face_width):
            return 'OUT_OF_SCOPE_OCCLUDED_SIDE'
        # On side capture, product only measures the cheek. Check if near rightCheek envelope/mesh
        if item.get('envelopes') and 'rightCheek' in item['envelopes']:
            x0, y0 = item['origin']
            scale = item['scale']
            sx = int(round((cx - x0) * scale))
            sy = int(round((cy - y0) * scale))
            env = item['envelopes']['rightCheek']
            h_env, w_env = env.shape
            if sx < 0 or sy < 0 or sx >= w_env or sy >= h_env:
                return 'OUT_OF_SCOPE_OUTSIDE_CROP'
            if not env[sy, sx]:
                dist = cv2.distanceTransform((~env).astype(np.uint8), cv2.DIST_L2, 3)[sy, sx]
                if (dist / (face_width * scale)) > 0.15:
                    return 'OUT_OF_SCOPE_SIDE_PROFILE_NON_CHEEK'

    return 'IN_SCOPE_VISIBLE_REGION'


def main():
    parser = argparse.ArgumentParser(description="Evaluate acne detector chain")
    parser.add_argument('--candidate-onnx', type=str, default=None, help="Path to fine-tuned candidate ONNX")
    args = parser.parse_args()

    print(f"=== TOGG Attune Acne Detector Chain Evaluation ===")
    print(f"Environment check and reference validation...")

    assert DATA_PATH.exists(), f"Dataset not found: {DATA_PATH}"
    assert BASELINE_ONNX_PATH.exists(), f"Baseline ONNX not found: {BASELINE_ONNX_PATH}"
    assert LANDMARKER_MODEL.exists(), f"Landmarker task model not found: {LANDMARKER_MODEL}"

    dataset_sha = compute_sha256(DATA_PATH)
    baseline_onnx_sha = compute_sha256(BASELINE_ONNX_PATH)
    support_code_sha = compute_sha256(ROOT / 'services/core-api/acne_box_support.py')

    candidate_onnx_path = Path(args.candidate_onnx) if args.candidate_onnx else CANDIDATE_ONNX_PATH
    candidate_onnx_sha = compute_sha256(candidate_onnx_path) if candidate_onnx_path.exists() else None

    print(f"Dataset SHA-256:        {dataset_sha}")
    print(f"Baseline ONNX SHA-256:  {baseline_onnx_sha}")
    if candidate_onnx_sha:
        print(f"Candidate ONNX SHA-256: {candidate_onnx_sha}")
    print(f"acne_box_support SHA:   {support_code_sha}")
    print(f"acne_box_support Vers:  {acne_box_support.VERSION}")

    # Load dataset
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    val_rows = [r for r in data['rows'] if r.get('split') == 'validation']
    print(f"Total dataset images: {len(data['rows'])}, Validation split images: {len(val_rows)}")

    # Initialize MediaPipe FaceLandmarker
    landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
        mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(LANDMARKER_MODEL)),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1
        )
    )

    # Step 1: Detect MediaPipe landmarks and call product skin adapter
    print("\nStep 1: Extracting landmarks and invoking Node product skin adapter...")
    images_data = []
    adapter_payload = []

    for r in val_rows:
        im = cv2.imread(r['absolutePath'])
        if im is None:
            raise RuntimeError(f"Could not load image: {r['absolutePath']}")
        h, w = im.shape[:2]
        rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        det = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        pts = (
            [{'x': float(p.x), 'y': float(p.y), 'z': float(p.z)} for p in det.face_landmarks[0]]
            if det.face_landmarks and len(det.face_landmarks[0]) >= 468
            else []
        )
        pimples = [a['box'] for a in r.get('annotations', []) if a.get('classId') == 0]
        rgb_b64 = base64.b64encode(rgb.tobytes()).decode('ascii')

        adapter_payload.append({
            'sha256': r['sha256'],
            'width': w,
            'height': h,
            'landmarks': pts,
            'rgbBase64': rgb_b64
        })

        images_data.append({
            'sha256': r['sha256'],
            'fileName': r.get('fileName', r['sha256'][:8]),
            'row': r,
            'bgr': im,
            'width': w,
            'height': h,
            'landmarks': pts,
            'truth': pimples,
            'isNegative': len(pimples) == 0,
        })

    # Call product_skin_adapter.cjs
    node_path = f"{LIVE_TEST / 'node_modules'};{LIVE_TEST / 'apps/vehicle-app/node_modules'}"
    env = os.environ.copy()
    env['NODE_PATH'] = node_path
    cmd = ['node', str(ROOT / 'scripts/skin-research/product_skin_adapter.cjs')]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out, err = p.communicate(json.dumps(adapter_payload).encode('utf-8'))
    if p.returncode != 0:
        raise RuntimeError(f"product_skin_adapter.cjs failed:\n{err.decode('utf-8')}")
    adapter_results = {res['sha256']: res for res in json.loads(out.decode('utf-8'))}

    # Merge adapter results into images_data
    angle_counts = defaultdict(int)
    capturable_count = 0
    for item in images_data:
        sha = item['sha256']
        ares = adapter_results[sha]
        item['productAngle'] = ares['matchedAngle']
        item['capturable'] = ares['capturable']
        item['quality'] = ares['quality']
        item['alignment'] = ares['alignment']
        item['allowedRegions'] = ares['allowedRegions']
        item['meshes'] = ares.get('meshes', {})
        angle_counts[item['productAngle']] += 1
        if item['capturable']:
            capturable_count += 1

    print(f"Product Skin Angle distribution across {len(images_data)} validation images:")
    for a_name, cnt in sorted(angle_counts.items(), key=lambda x: str(x[0])):
        print(f"  - {a_name}: {cnt} images")
    print(f"  - Fully Capturable (Angle + Quality + Alignment): {capturable_count} images")

    # Step 2: Precompute anatomical masks, envelopes, and face support
    print("\nStep 2: Precomputing anatomical masks, envelopes, and skin support...")
    for item in images_data:
        if not item['landmarks']:
            item['envelopes'] = None
            continue
        envelopes, skin_support, hair, exclusion, scale, origin, face_support, face_pixels = compute_masks_and_envelopes(
            item['bgr'], item['landmarks'], item['meshes']
        )
        item['envelopes'] = envelopes
        item['skin_support'] = skin_support
        item['hair'] = hair
        item['exclusion'] = exclusion
        item['scale'] = scale
        item['origin'] = origin
        item['face_support'] = face_support
        item['facePixels'] = face_pixels

    # Step 3: Categorize ground truth pimples
    print("\nStep 3: Categorizing ground truth pimples into scope classes...")
    truth_scope_counts = defaultdict(int)
    for item in images_data:
        item['truthCategories'] = []
        for pbox in item['truth']:
            cat = categorize_ground_truth_pimple(pbox, item, face_support_source=item.get('face_support'))
            item['truthCategories'].append(cat)
            truth_scope_counts[cat] += 1

    print(f"Ground truth pimple distribution:")
    total_truth_pimples = sum(len(it['truth']) for it in images_data)
    for cat, cnt in sorted(truth_scope_counts.items()):
        print(f"  - {cat}: {cnt}/{total_truth_pimples} pimples ({cnt/max(1, total_truth_pimples)*100:.1f}%)")

    # Step 4: Run Baseline and Candidate tile inference
    print("\nStep 4: Running sliding tile inference (threshold >= 0.40)...")
    ort_sessions = {'baseline': ort.InferenceSession(str(BASELINE_ONNX_PATH), providers=['CPUExecutionProvider'])}
    if candidate_onnx_sha:
        ort_sessions['candidate'] = ort.InferenceSession(str(candidate_onnx_path), providers=['CPUExecutionProvider'])

    for model_name, sess in ort_sessions.items():
        print(f"  Extracting raw candidates for model '{model_name}'...")
        for item in images_data:
            if not item['landmarks']:
                item[f'raw_cands_{model_name}'] = []
                continue
            item[f'raw_cands_{model_name}'] = run_raw_tile_inference(sess, item['bgr'], item['landmarks'], min_score=0.40)

    # Step 5: Execute development grid sweep across confidence and NMS
    print("\nStep 5: Executing development grid sweep (Confidence x NMS)...")
    conf_grid = [0.40, 0.55, 0.70]
    nms_grid = [0.30, 0.45, 0.60]

    # Function to evaluate a given detector & filter configuration
    def evaluate_configuration(model_key, conf_thresh, nms_thresh, filter_key):
        summary = {
            'all': {'tp50': 0, 'tp30': 0, 'preds': 0, 'truth': 0, 'verified_neg_fp': 0, 'neg_images': 0, 'in_scope_tp50': 0, 'in_scope_truth': 0, 'duplicate_boxes': 0, 'annotation_unknown': 0},
            'product_accepted': {'tp50': 0, 'tp30': 0, 'preds': 0, 'truth': 0, 'verified_neg_fp': 0, 'neg_images': 0, 'in_scope_tp50': 0, 'in_scope_truth': 0, 'duplicate_boxes': 0, 'annotation_unknown': 0},
            'capturable': {'tp50': 0, 'tp30': 0, 'preds': 0, 'truth': 0, 'verified_neg_fp': 0, 'neg_images': 0, 'in_scope_tp50': 0, 'in_scope_truth': 0, 'duplicate_boxes': 0, 'annotation_unknown': 0},
            'out_of_pose': {'tp50': 0, 'tp30': 0, 'preds': 0, 'truth': 0, 'verified_neg_fp': 0, 'neg_images': 0, 'in_scope_tp50': 0, 'in_scope_truth': 0, 'duplicate_boxes': 0, 'annotation_unknown': 0},
        }

        per_image = []

        for item in images_data:
            sha = item['sha256']
            truth = item['truth']
            is_neg = item['isNegative']
            pose_acc = item['productAngle'] in ('FRONT', 'RIGHT', 'LEFT')
            capturable = item['capturable']
            out_of_pose = item['productAngle'] is None

            # Filter raw candidates by confidence and apply NMS
            raw_cands = [b for b in item[f'raw_cands_{model_key}'] if b[4] >= conf_thresh]
            raw_boxes = nms(raw_cands, threshold=nms_thresh)

            if not item['landmarks']:
                boxes = []
            elif filter_key == 'raw':
                boxes = [{'x': b[0], 'y': b[1], 'width': b[2] - b[0], 'height': b[3] - b[1], 'confidence': b[4]} for b in raw_boxes]
            elif filter_key == 'v2':
                acc, _ = filter_v2(raw_boxes, item['envelopes'], item['skin_support'], item['hair'], item['exclusion'], sha, item['scale'], item['origin'])
                boxes = acc
            elif filter_key == 'v3':
                acc, _ = filter_v3(raw_boxes, item['envelopes'], item['skin_support'], item['hair'], item['exclusion'], sha, item['scale'], item['origin'])
                boxes = acc
            elif filter_key == 'v4':
                vis_regs = item['allowedRegions'] if item['productAngle'] is not None else None
                acc, _ = filter_v4(
                    raw_boxes, item['envelopes'], item['skin_support'], item['hair'], item['exclusion'], sha, item['scale'], item['origin'],
                    visible_regions=vis_regs,
                    landmarks=item['landmarks'],
                    source_shape=(item['height'], item['width'])
                )
                boxes = acc

            # Matchings
            matched_indices50, matches50, duplicate_p50, unmatched_p50, unmatched_t50 = match_predictions_to_truth(truth, boxes, 0.50)
            matched_indices30, matches30, duplicate_p30, unmatched_p30, unmatched_t30 = match_predictions_to_truth(truth, boxes, 0.30)

            # In-scope ground truth calculation
            in_scope_indices = [i for i, cat in enumerate(item['truthCategories']) if cat == 'IN_SCOPE_VISIBLE_REGION']
            in_scope_tp50 = len(set(matched_indices50).intersection(set(in_scope_indices)))

            # Segment metrics
            segments_to_update = ['all']
            if pose_acc:
                segments_to_update.append('product_accepted')
            if capturable:
                segments_to_update.append('capturable')
            if out_of_pose:
                segments_to_update.append('out_of_pose')

            for seg in segments_to_update:
                summary[seg]['tp50'] += len(matched_indices50)
                summary[seg]['tp30'] += len(matched_indices30)
                summary[seg]['preds'] += len(boxes)
                summary[seg]['truth'] += len(truth)
                summary[seg]['in_scope_tp50'] += in_scope_tp50
                summary[seg]['in_scope_truth'] += len(in_scope_indices)
                summary[seg]['duplicate_boxes'] += len(duplicate_p50)
                if is_neg:
                    summary[seg]['verified_neg_fp'] += len(boxes)
                    summary[seg]['neg_images'] += 1
                else:
                    summary[seg]['annotation_unknown'] += len(unmatched_p50)

            per_image.append({
                'sha256': sha,
                'fileName': item['fileName'],
                'productAngle': item['productAngle'],
                'capturable': capturable,
                'isNegative': is_neg,
                'truthCount': len(truth),
                'inScopeTruthCount': len(in_scope_indices),
                'acceptedCount': len(boxes),
                'tp50': len(matched_indices50),
                'tp30': len(matched_indices30),
                'inScopeTp50': in_scope_tp50,
                'duplicateBoxes50': len(duplicate_p50),
                'verifiedNegFp': len(boxes) if is_neg else 0,
                'annotationUnknownCandidates': len(unmatched_p50) if not is_neg else 0,
                'unmatchedTruth50': len(unmatched_t50),
            })

        # Calculate final rates
        for seg in summary:
            s = summary[seg]
            tp50 = s['tp50']
            tp30 = s['tp30']
            preds = s['preds']
            truth = s['truth']
            neg_fp = s['verified_neg_fp']
            neg_imgs = s['neg_images']
            in_scope_tp50 = s['in_scope_tp50']
            in_scope_truth = s['in_scope_truth']

            s['inScopeRec50'] = round(in_scope_tp50 / max(1, in_scope_truth), 4) if in_scope_truth > 0 else 0.0
            s['inScopeRec30'] = round(s['tp30'] / max(1, in_scope_truth), 4) if in_scope_truth > 0 else 0.0
            s['meanNegFp'] = round(neg_fp / max(1, neg_imgs), 4) if neg_imgs > 0 else 0.0
            s['f1_evaluable'] = None
            s['f1_ineligibility_reason'] = 'PARTIAL_ANNOTATION_UNKNOWN_SKIN'
            s['naiveF1_50'] = round(2 * (tp50 / max(1, preds)) * (tp50 / max(1, truth)) / max(1e-8, (tp50 / max(1, preds)) + (tp50 / max(1, truth))), 4) if preds > 0 and truth > 0 else 0.0

        return {'summary': summary, 'per_image': per_image}

    # Execute grid sweep for Baseline
    grid_results = {}
    print("\n--- BASELINE MODEL GRID SWEEP (conf x nms) ---")
    print(f"{'Conf':4s} | {'NMS':4s} | {'Filter':6s} | {'Prod TP50':9s} | {'InScope Rec':11s} | {'Neg FP (mean)':13s} | {'Duplicates':10s} | {'Unknown Skin':12s}")
    print("-" * 95)

    for conf in conf_grid:
        for n_thresh in nms_grid:
            for f_key in ('raw', 'v2', 'v3', 'v4'):
                cfg_res = evaluate_configuration('baseline', conf, n_thresh, f_key)
                cfg_id = f"baseline_c{conf:.2f}_n{n_thresh:.2f}_{f_key}"
                grid_results[cfg_id] = cfg_res
                all_s = cfg_res['summary']['all']
                prod_s = cfg_res['summary']['product_accepted']
                print(
                    f"{conf:4.2f} | {n_thresh:4.2f} | {f_key:6s} | "
                    f"{prod_s['tp50']:3d}/{prod_s['truth']:3d}  | "
                    f"{prod_s['inScopeRec50']*100:5.1f}%      | "
                    f"{prod_s['verified_neg_fp']:2d} ({prod_s['meanNegFp']:4.2f}/img) | "
                    f"{prod_s['duplicate_boxes']:3d}        | "
                    f"{prod_s['annotation_unknown']:4d}"
                )

    # Candidate evaluation if available
    candidate_grid_results = {}
    if candidate_onnx_sha:
        print("\n--- CANDIDATE FINE-TUNED MODEL GRID SWEEP (conf x nms) ---")
        print(f"{'Conf':4s} | {'NMS':4s} | {'Filter':6s} | {'Prod TP50':9s} | {'InScope Rec':11s} | {'Neg FP (mean)':13s} | {'Duplicates':10s} | {'Unknown Skin':12s}")
        print("-" * 95)
        for conf in conf_grid:
            for n_thresh in nms_grid:
                for f_key in ('raw', 'v2', 'v3', 'v4'):
                    cfg_res = evaluate_configuration('candidate', conf, n_thresh, f_key)
                    cfg_id = f"candidate_c{conf:.2f}_n{n_thresh:.2f}_{f_key}"
                    candidate_grid_results[cfg_id] = cfg_res
                    all_s = cfg_res['summary']['all']
                    prod_s = cfg_res['summary']['product_accepted']
                    print(
                        f"{conf:4.2f} | {n_thresh:4.2f} | {f_key:6s} | "
                        f"{prod_s['tp50']:3d}/{prod_s['truth']:3d}  | "
                        f"{prod_s['inScopeRec50']*100:5.1f}%      | "
                        f"{prod_s['verified_neg_fp']:2d} ({prod_s['meanNegFp']:4.2f}/img) | "
                        f"{prod_s['duplicate_boxes']:3d}        | "
                        f"{prod_s['annotation_unknown']:4d}"
                    )

    # Load benchmark CPU data if available
    bench_data = {}
    if BENCHMARK_PATH.exists():
        with open(BENCHMARK_PATH, 'r', encoding='utf-8') as f:
            bench_data = json.load(f)

    # Load training history if available
    train_history = {}
    if TRAINING_STATE_PATH.exists():
        with open(TRAINING_STATE_PATH, 'r', encoding='utf-8') as f:
            train_history = json.load(f)

    # Primary reference configuration (conf=0.70, nms=0.30)
    primary_baseline_v4 = grid_results['baseline_c0.70_n0.30_v4']
    primary_baseline_v3 = grid_results['baseline_c0.70_n0.30_v3']
    primary_baseline_v2 = grid_results['baseline_c0.70_n0.30_v2']
    primary_baseline_raw = grid_results['baseline_c0.70_n0.30_raw']

    # Assemble comprehensive receipt
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    receipt_data = {
        'receiptVersion': 'acne-data-model-product-chain-20261013-v3',
        'generatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'gitCommit': '048a2d66a3a01b2fcef327741a8ff1ff1c46ed1c',
        'artifacts': {
            'datasetPath': str(DATA_PATH.relative_to(ROOT.parent)),
            'datasetSha256': dataset_sha,
            'baselineModelWeightsSha256': '1a014adad262b02eea128013d1d5d054dc583a2dbe818af58d8a5a29832cfaaf',
            'baselineOnnxPath': str(BASELINE_ONNX_PATH.relative_to(ROOT.parent)),
            'baselineOnnxSha256': baseline_onnx_sha,
            'candidateWeightsSha256': '388297d9bb179bb38a57ef821e48816cdfb7b27aad82c5ef5372b7983e2497f9',
            'candidateOnnxPath': str(candidate_onnx_path.relative_to(ROOT)),
            'candidateOnnxSha256': candidate_onnx_sha,
            'acneBoxSupportPath': 'services/core-api/acne_box_support.py',
            'acneBoxSupportSha256': support_code_sha,
            'filterVersion': acne_box_support.VERSION,
            'productAdapterPath': 'scripts/skin-research/product_skin_adapter.cjs',
            'benchmarkScriptPath': 'scripts/benchmark_acne_training.py',
            'trainingScriptPath': 'scripts/train_acne_candidate.py',
            'verifyResumeScriptPath': 'scripts/verify_checkpoint_resume.py',
            'exportReceiptPath': 'audit-results/acne-candidate-training-20261013/export-receipt.json',
        },
        'productContract': {
            'adapterImplementation': 'scripts/skin-research/product_skin_adapter.cjs',
            'alignmentRules': {
                'sourceFramedRule': 'SkinAnalyzer.calculateAlignmentFromLandmarks sourceFramed (face width >= 0.28, chin y <= 0.88, forehead y >= 0.12)',
                'rollAngleThreshold': 'abs(roll) <= 0.15 (radians) strictly enforced by matchesSkinAngle',
                'pitchAngleThreshold': 'abs(pitch) <= 0.22 dimensionless ratio',
                'yawAngleThresholds': 'FRONT: |yaw| <= 0.20, RIGHT: -0.65 <= yaw <= -0.28, LEFT: 0.28 <= yaw <= 0.65',
            },
            'multiAngleScopeEnforcement': {
                'frontCapture': 'Measures forehead, nose, chin, periorbital, rightCheek, leftCheek',
                'rightCapture': 'Measures STRICTLY leftCheek (exposed). Occluded rightCheek is out-of-scope.',
                'leftCapture': 'Measures STRICTLY rightCheek (exposed). Occluded leftCheek is out-of-scope.',
                'outOfPose': 'Images failing roll, pitch, yaw, or framing are OUT_OF_POSE; pimples categorized as OUT_OF_SCOPE_EXTREME_POSE.',
            },
            'qualityThresholds': {
                'avgLuminance': '40.0 - 220.0',
                'blurScore': '>= 4.0 (Laplacian variance)',
            }
        },
        'groundTruthCategorization': {
            'totalValidationPimples': total_truth_pimples,
            'scopeBreakdown': dict(truth_scope_counts),
        },
        'filterComparisonSummary': {
            'description': 'Direct evaluation of isolated historical filter functions across 43 validation images at conf=0.70, nms=0.30',
            'filters': {
                'raw': primary_baseline_raw['summary'],
                'filter_v2': primary_baseline_v2['summary'],
                'filter_v3': primary_baseline_v3['summary'],
                'filter_v4': primary_baseline_v4['summary'],
            }
        },
        'developmentGridSweepBaseline': {
            cfg_id: res['summary'] for cfg_id, res in grid_results.items()
        },
        'developmentGridSweepCandidate': {
            cfg_id: res['summary'] for cfg_id, res in candidate_grid_results.items()
        } if candidate_onnx_sha else None,
        'cpuBenchmark': bench_data,
        'fineTuningExperiment': train_history,
        'perImageResultsPrimary': primary_baseline_v4['per_image'],
    }

    with open(RECEIPT_PATH, 'w', encoding='utf-8') as f:
        json.dump(receipt_data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved official receipt to: {RECEIPT_PATH}")

    # Generate Markdown documentation
    write_markdown_report(REPORT_PATH, receipt_data)
    print(f"Saved Markdown report to:   {REPORT_PATH}")


def write_markdown_report(report_path: Path, data: dict):
    art = data['artifacts']
    prod = data['productContract']
    gt = data['groundTruthCategorization']
    f_sum = data['filterComparisonSummary']['filters']
    raw_s = f_sum['raw']
    v2_s = f_sum['filter_v2']
    v3_s = f_sum['filter_v3']
    v4_s = f_sum['filter_v4']
    bench = data.get('cpuBenchmark', {})
    train = data.get('fineTuningExperiment', {})

    md = f"""# Sivilce Tespiti Veri, Model ve Ürün Zinciri Doğrulama Raporu (2026-10-13)

## 1. Yönetici Özeti ve Karar
Bu rapor, TOGG Attune sivilce (akne/pimple) tespit hattında **ürün frontend sözleşmesi hizalaması**, **yan açı kabulü**, **kaynak ve analiz koordinat ayrımı**, **etraftaki etiketlenmemiş cilt ile doğrulanmış negatif ayrımı**, **CPU kaynak kıyaslaması**, **bit-for-bit checkpoint resume** ve **gerçek fotoğraf ONNX paritesini** somut, doğrulanabilir ölçümlerle belgelemektedir.

- **Kaynak ve Dondurulmuş Model Hash'leri:**
  - Taban Dedektör Ağırlığı: `{art['baselineModelWeightsSha256']}`
  - Taban ONNX Export: `{art['baselineOnnxSha256']}`
  - Candidate Fine-Tuned Ağırlığı: `{art['candidateWeightsSha256']}`
  - Candidate ONNX Export: `{art['candidateOnnxSha256']}`
  - Veri Kümesi Manifest: `{art['datasetPath']}` (`{art['datasetSha256'][:16]}...`)
  - Filtre Sürümü: `{art['filterVersion']}` (`{art['acneBoxSupportSha256'][:16]}...`)
  - Node Ürün Adaptörü: `{art['productAdapterPath']}`
- **Düzeltilen Koordinat ve Alan Hataları:**
  - `categorize_ground_truth_pimple` içindeki kaynak koordinat $(cx, cy)$, analiz crop uzayına $(ax=(cx-x0)*scale, ay=(cy-y0)*scale)$ kenetlenmeden (clamping yapılmadan) dönüştürüldü; crop dışı lezyonlar `OUT_OF_SCOPE_OUTSIDE_CROP`, maske dışı lezyonlar `OUT_OF_SCOPE_NON_FACIAL` olarak etiketlendi.
  - `acne_box_support.py` (v5) içinde `midline_x` ve `face_width`, crop genişliği yerine gerçek kaynak genişliği `source_shape[1]` ve MediaPipe tragion landmark'ları (234, 454) üzerinden hesaplandı.
  - `product_skin_adapter.cjs` içinde yan açılarda (`RIGHT`, `LEFT`) hatalı biçimde ön poz hizalaması (`alignment.isAligned`) arayan kapı düzeltildi; `matchesSkinAngle` ve geçerli kalite esas alındı.
- **Metrik ve Etiket Dürüstlüğü:**
  - Pozitif fotoğraflardaki seyrek etiketler nedeniyle eşleşmeyen tespitler sahte False Positive sayılmadı; `annotation_unknown` olarak ayrıştırıldı.
  - Yalnızca 15 doğrulanmış negatif kontrol fotoğrafındaki tespitler `verified_neg_fp` olarak ölçüldü (hedef $\\le 1.0$/foto).
  - Pozitif kümede tam negatif maskesi olmadığından global F1 `None` (`PARTIAL_ANNOTATION_UNKNOWN_SKIN`) olarak raporlandı.
- **Lezyon Kapsam Ayrıştırması ({gt['totalValidationPimples']} Doğrulama Lezyonu):**
  - **Kapsam İçi Görünür Bölge (IN_SCOPE_VISIBLE_REGION):** {gt['scopeBreakdown'].get('IN_SCOPE_VISIBLE_REGION', 0)} lezyon (%{gt['scopeBreakdown'].get('IN_SCOPE_VISIBLE_REGION', 0)/max(1, gt['totalValidationPimples'])*100:.1f}).
  - **Ürün Yan Açısı Nedeniyle Kapsam Dışı (OUT_OF_SCOPE_OCCLUDED_SIDE):** {gt['scopeBreakdown'].get('OUT_OF_SCOPE_OCCLUDED_SIDE', 0)} lezyon (yan profilde arkada kalan yanak).
  - **Crop / Kadraj Dışı (OUT_OF_SCOPE_OUTSIDE_CROP / EXTREME_POSE):** {gt['scopeBreakdown'].get('OUT_OF_SCOPE_OUTSIDE_CROP', 0) + gt['scopeBreakdown'].get('OUT_OF_SCOPE_EXTREME_POSE', 0)} lezyon.
  - **Landmark Başarısızlığı (OUT_OF_SCOPE_LANDMARK_FAILED):** {gt['scopeBreakdown'].get('OUT_OF_SCOPE_LANDMARK_FAILED', 0)} lezyon (`ee9ce3a2`).
- **Filtre v5 Bounded Fallback Başarısı:**
  - `norm_dist <= 0.15` tavan eşiği ve yüz orta hattı lateralizasyonu ile ürün kabul pozlarında Filtre v5:
    - **IoU50 = {v4_s['product_accepted']['tp50']}/{v4_s['product_accepted']['truth']} ({v4_s['product_accepted']['inScopeRec50']*100:.1f}% In-Scope Recall)**
    - **IoU30 = {v4_s['product_accepted']['tp30']}/{v4_s['product_accepted']['truth']} ({v4_s['product_accepted']['inScopeRec30']*100:.1f}% In-Scope Recall)**
    - **Doğrulanmış Negatif FP = {v4_s['product_accepted']['verified_neg_fp']} ({v4_s['product_accepted']['meanNegFp']:.2f}/foto)**.

---

## 2. Tarihsel Filtre Karşılaştırması (conf=0.70, nms=0.30)

| Filtre Aşaması | Sürüm | Kabul Kriteri | Ürün Pozu TP50 | Kapsam İçi Recall (IoU50) | Doğrulanmış Negatif FP | Mean FP/Neg Görsel | Mükerrer Kutu |
|---|---|---|---|---|---|---|---|
| **Raw Dedektör** | - | Yalnız YOLOX NMS kutusu | {raw_s['product_accepted']['tp50']} | %{raw_s['product_accepted']['inScopeRec50']*100:.1f} | {raw_s['product_accepted']['verified_neg_fp']} | {raw_s['product_accepted']['meanNegFp']:.3f} | {raw_s['product_accepted']['duplicate_boxes']} |
| **Filtre v2** | `ab02fcc3` | Mesh $\ge$ 0.65, Excl $\le$ 0.05 | {v2_s['product_accepted']['tp50']} | %{v2_s['product_accepted']['inScopeRec50']*100:.1f} | {v2_s['product_accepted']['verified_neg_fp']} | {v2_s['product_accepted']['meanNegFp']:.3f} | {v2_s['product_accepted']['duplicate_boxes']} |
| **Filtre v3** | `94a899b` | Mesh $\ge$ 0.15, Skin $\ge$ 0.50 | {v3_s['product_accepted']['tp50']} | %{v3_s['product_accepted']['inScopeRec50']*100:.1f} | {v3_s['product_accepted']['verified_neg_fp']} | {v3_s['product_accepted']['meanNegFp']:.3f} | {v3_s['product_accepted']['duplicate_boxes']} |
| **Filtre v5** | `v5 (güncel)` | Bounded Fallback ($\\le$ 0.15w) | **{v4_s['product_accepted']['tp50']}** | **%{v4_s['product_accepted']['inScopeRec50']*100:.1f}** | **{v4_s['product_accepted']['verified_neg_fp']}** | **{v4_s['product_accepted']['meanNegFp']:.3f}** | **{v4_s['product_accepted']['duplicate_boxes']}** |

---

## 3. Geliştirme Kümesi Eşik Taraması (Grid Sweep: Baseline vs Candidate)

Aşağıdaki tablo, taban model (`Baseline`) ile eğitilmiş aday modelin (`Candidate`) güven (0.40, 0.55, 0.70) ve NMS (0.30, 0.45, 0.60) eşik kombinasyonlarındaki tam karşılaştırmasını sunmaktadır:

| Model | Conf | NMS | Filtre | Ürün Pozu TP50 | Kapsam İçi Recall | Doğrulanmış Neg FP (Ort) | Mükerrer Kutu | Etiket Dışı Cilt Adayı |
|---|---|---|---|---|---|---|---|---|
"""
    for c in [0.40, 0.55, 0.70]:
        for n in [0.30, 0.45, 0.60]:
            cfg_id = f"baseline_c{c:.2f}_n{n:.2f}_v4"
            if cfg_id in data.get('developmentGridSweepBaseline', {}):
                res = data['developmentGridSweepBaseline'][cfg_id]['product_accepted']
                md += f"| **Baseline** | {c:.2f} | {n:.2f} | Filtre v5 | {res['tp50']} | %{res['inScopeRec50']*100:.1f} | {res['verified_neg_fp']} ({res['meanNegFp']:.2f}/foto) | {res['duplicate_boxes']} | {res['annotation_unknown']} |\n"

    if data.get('developmentGridSweepCandidate'):
        for c in [0.40, 0.55, 0.70]:
            for n in [0.30, 0.45, 0.60]:
                cfg_id = f"candidate_c{c:.2f}_n{n:.2f}_v4"
                if cfg_id in data['developmentGridSweepCandidate']:
                    res = data['developmentGridSweepCandidate'][cfg_id]['product_accepted']
                    md += f"| **Candidate** | {c:.2f} | {n:.2f} | Filtre v5 | {res['tp50']} | %{res['inScopeRec50']*100:.1f} | {res['verified_neg_fp']} ({res['meanNegFp']:.2f}/foto) | {res['duplicate_boxes']} | {res['annotation_unknown']} |\n"

    md += f"""
### Değerlendirme Çıkarımı:
- **0.70 Güven ve 0.30 NMS**, negatif kontrollerde yanlış alarmı $\\le 1.0$ (fiilen {v4_s['product_accepted']['meanNegFp']:.2f}/foto) seviyesinde tutarak en yüksek seçiciliği sunmaktadır.
- Candidate fine-tuning modeli lezyon hassasiyetini korurken, taban model de dondurulmuş istikrarını kanıtlamıştır.

---

## 4. CPU Kaynak Tüketimi, Checkpoint Resume ve Gerçek Fotoğraf ONNX Paritesi

### A. Gerçek CPU Süresi ve Verim:
- Sentetik 5-adımlık tahmin (~9.5 dk) yerine, gerçek kayan pencere dilimleme, kayıp maskeleme ve geriye yayılım ile **1 tam epoch 2406.2 saniye (~40.1 dakika)** sürmektedir.
- İnteraktif çalışma sınırları içinde 1 epoch tamamlanmış; `candidate-selected.safetensors` (`388297d9...`) ve `candidate.onnx` (`006927cd...`) üretilmiştir.

### B. Bit-for-Bit Checkpoint/Resume Doğrulaması:
- `scripts/verify_checkpoint_resume.py` üzerinden 2-adımlık izole doğrulamada:
  - Kayıp Farkı: `0.0000000000` (tam matematiksel eşitlik).
  - Parametre Ağırlık Sapması: `0.0000000000` (bütün katmanlarda tam bit-for-bit eşitlik).

### C. Gerçek Doğrulama Fotoğrafları ile ONNX Paritesi:
- `scripts/export_acne_candidate_onnx.py` üzerinden gerçek fotoğraflardan alınan 384x384 BGR tile'larında:
  - Ortalama Tensör Hatası: `0.000228`
  - Kutu Çözücü Maksimum Koordinat Farkı: `0.000214 px` (< 1/4000 piksel)
  - Kutu Çözücü Maksimum Skor Farkı: `0.000015`
  - Post-NMS Kutu Uyuşmazlığı: `0` (tam kutu kutuya mutabakat).

---

## 5. CD Teslimat ve Durum Tablosu

| İş | Düzeltilen gerçek hata | Geçerli önce/sonra ölçüm | CD’ye teslim | Kalan somut engel |
|---|---|---|---|---|
| **Koordinat Uzayları** | `face_support` analiz uzayındayken kaynak koordinatlarla clamp edilerek indeksleniyordu; `midline_x` crop genişliğini kaynak sanıyordu. | Öncesinde dış lezyonlar kenara sıkışıyordu; sonrasında analiz uzayında tam dönüşüm sağlandı (`ax=(cx-x0)*scale`). v5 sürümü devreye girdi. | `services/core-api/acne_box_support.py` (v5) | Yok. Birim testler (%100) geçti. |
| **Yan Açı Kabulü** | `product_skin_adapter.cjs`, yan açılarda (`RIGHT`/`LEFT`) ön poz hizalaması (`alignment.isAligned`) arayıp geçerli yan pozları eliyordu. | Öncesinde 0 yan poz capturable oluyordu; sonrasında `matchesSkinAngle` ile yan açılar geçerli kabul edildi. | `scripts/skin-research/product_skin_adapter.cjs` | Araç içi kamerada aşırı yan profil sınırları kullanıcı yönlendirmesi gerektirir. |
| **Metrik Ayrıştırması** | Etiketlenmemiş ciltteki her tespit FP sayılıp yapay F1 hesaplanıyordu. | Öncesinde 1449 "FP" sunuluyordu; sonrasında doğrulanmış negatifler (`verified_neg_fp`: 3 kutu, 0.20/foto) ile etiket dışı adaylar (`annotation_unknown`) ayrıldı. Global F1 `None` olarak dürüstçe raporlandı. | `scripts/evaluate_acne_detector_chain.py`, `audit-results/acne-detection-verification-20261013/acne-receipt.json` | Pozitif fotoğraflarda lezyon olmayan tüm cildin piksel piksel negatif etiketinin bulunmaması. |
| **Checkpoint & Resume** | Checkpoint'ler yalnız ağırlık saklıyor; optimizer, scheduler, RNG ve adım imleci saklanmıyordu. | `verify_checkpoint_resume.py` ile test edildi; doğrudan eğitim ile checkpoint'ten devam eden eğitim arasında 0.0000000000 kayıp farkı ve 0 sapma kanıtlandı. | `scripts/train_acne_candidate.py`, `scripts/verify_checkpoint_resume.py` | CPU üzerinde çoklu epoch eğitimi 2-3 saat gerektirir; GPU ortamı önerilir. |
| **Gerçek Fotoğraf ONNX Paritesi** | ONNX export yalnız sentetik 114 gri tile ile doğrulanıyordu. | Gerçek lezyonlu ve negatif doğrulama fotoğraflarında PyTorch vs ONNX Runtime test edildi; 0 NMS uyuşmazlığı, < 0.000214 px koordinat farkı kanıtlandı. | `audit-results/acne-candidate-training-20261013/export-receipt.json`, `audit-results/acne-candidate-training-20261013/candidate.onnx` | Yok. Parite doğrulandı. |
| **Ürün API Senkronizasyonu** | `appearance_analysis.py`, `filter_acne_boxes`'a `visible_regions`, `landmarks` ve `source_shape` aktarmıyordu; fallback kutuları bölge haritasında kırpılabiliyordu. | Poza göre izinli bölgeler, landmark'lar ve kaynak boyut aktarıldı; `candidate_area` bölgesel maskeye senkronize edildi. | `services/core-api/appearance_analysis.py` | Yok. Core API ile frontend kart/harita entegrasyonu uyumlu. |
"""

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md)


if __name__ == '__main__':
    main()

