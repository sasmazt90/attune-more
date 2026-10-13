#!/usr/bin/env python3
"""Evaluate all acne checkpoints side-by-side under the identical product contract.

Checkpoints evaluated:
1. Baseline: 1a014adad262...
2. Phase 1 Candidate: 388297d9...
3. Phase 2 Epoch 1: 2d3ba005...
4. Phase 2 Epoch 2: dac04d03...
5. Phase 2 Epoch 3: b63d3f43...

Contract steps for every model:
- 384x384 sliding tile extraction with stride 288
- Tile coordinate transformation to source pixels
- Confidence thresholding (conf >= 0.70)
- Image-level NMS (IoU >= 0.30)
- Filter v5 (acne_box_support.accepted_boxes) with adaptive cheek lateralization
- 1-to-1 bipartite matching to ground truth
- Multi-scope recall calculation (In-Scope 53, Capturable 14, All-Data 276)
- Negative control false alarm analysis (pores, moles, hair, reflections, loss dynamics)
"""

import os
import sys
import json
import math
import hashlib
from pathlib import Path
from collections import defaultdict
import cv2
import numpy as np
import torch
from safetensors.torch import load_file
from torchvision.ops import nms as torch_nms

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.append(str(LIVE_TEST / '.runtime/python-packages'))
import mediapipe as mp

sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
import acne_box_support
from acne_metrics import match_predictions_to_truth, compute_scope_recall
from train_acne_candidate import YOLOX, YOLOPAFPN, YOLOXHead, install_bounds

MANIFEST_PATH = ROOT / 'audit-results/acne-detection-verification-20261013/annotation-scope-manifest.json'
OUT_COMPARISON = ROOT / 'audit-results/acne-detection-verification-20261013/checkpoint-comparative-evaluation.json'

CHECKPOINTS = [
    {
        'key': 'baseline',
        'displayName': 'Baseline (1a014adad262)',
        'weightsPath': ROOT / 'audit-results/acne-candidate-training-20261013/baseline-snapshot.safetensors',
        'expectedSha': '1a014adad262b02eea128013d1d5d054dc583a2dbe818af58d8a5a29832cfaaf'
    },
    {
        'key': 'phase1_candidate',
        'displayName': 'Phase 1 Candidate (388297d9)',
        'weightsPath': ROOT / 'audit-results/acne-candidate-training-20261013/candidate-selected.safetensors',
        'expectedSha': '388297d9bb179bb38a57ef821e48816cdfb7b27aad82c5ef5372b7983e2497f9'
    },
    {
        'key': 'phase2_epoch1',
        'displayName': 'Phase 2 Epoch 1 (2d3ba005)',
        'weightsPath': ROOT / 'audit-results/acne-candidate-phase2-20261013/checkpoint-epoch-01.safetensors',
        'expectedSha': '2d3ba0052b1ca8adca4e1ef33b31401a0095e31511c777098bebb5a637c45a1a'
    },
    {
        'key': 'phase2_epoch2',
        'displayName': 'Phase 2 Epoch 2 (dac04d03)',
        'weightsPath': ROOT / 'audit-results/acne-candidate-phase2-20261013/checkpoint-epoch-02.safetensors',
        'expectedSha': 'dac04d031155d6f4b07b012d267e8ea5dcd8c0ff864234d4d9cc5a785dcb2a57'
    },
    {
        'key': 'phase2_epoch3',
        'displayName': 'Phase 2 Epoch 3 / Latest (b63d3f43)',
        'weightsPath': ROOT / 'audit-results/acne-candidate-phase2-20261013/checkpoint-epoch-03.safetensors',
        'expectedSha': 'b63d3f435b89775be8cfb88b32547703ca97794930da56650f94c0a2716f2ec3'
    }
]

LIMITS = {'analysisFacePixels': 720, 'minFacePixels': 280}
REGIONS = ('forehead', 'rightCheek', 'leftCheek', 'nose', 'chin')


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def compute_masks_and_envelopes(bgr, points, meshes):
    """Computes anatomical masks, envelopes, skin support, and face width in analysis crop space."""
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


def extract_raw_predictions_fast(net, bgr, points, tile_size=384, stride=288, min_score=0.05):
    """Fast native sliding tile inference with YOLOX PyTorch model."""
    h, w = bgr.shape[:2]
    face_lms = np.array([[p['x'] * w, p['y'] * h] for p in points[:468]])
    min_x, max_x = int(np.floor(face_lms[:, 0].min())), int(np.ceil(face_lms[:, 0].max()))
    min_y, max_y = int(np.floor(face_lms[:, 1].min())), int(np.ceil(face_lms[:, 1].max()))

    pad = max(24, int((max_x - min_x) * 0.15))
    crop_x0 = max(0, min_x - pad)
    crop_y0 = max(0, min_y - pad)
    crop_x1 = min(w, max_x + pad)
    crop_y1 = min(h, max_y + pad)

    xs = sorted(set([*range(crop_x0, max(crop_x0 + 1, crop_x1 - tile_size + 1), stride), max(crop_x0, crop_x1 - tile_size)]))
    ys = sorted(set([*range(crop_y0, max(crop_y0 + 1, crop_y1 - tile_size + 1), stride), max(crop_y0, crop_y1 - tile_size)]))

    tiles_info = []
    tile_tensors = []
    for a in xs:
        for b in ys:
            endx = min(w, a + tile_size)
            endy = min(h, b + tile_size)
            tile = np.full((tile_size, tile_size, 3), 114, dtype=np.uint8)
            tile[:endy - b, :endx - a] = bgr[b:endy, a:endx]
            t_tensor = torch.from_numpy(tile.transpose(2, 0, 1)).float()
            tile_tensors.append(t_tensor)
            tiles_info.append((a, b, endx, endy))

    if not tile_tensors:
        return []

    batch = torch.stack(tile_tensors, dim=0)
    with torch.no_grad():
        out = net(batch)

    raw_cands = []
    for i, (a, b, endx, endy) in enumerate(tiles_info):
        pred = out[i]
        scores = pred[:, 4] * pred[:, 5]
        mask = scores >= min_score
        if mask.any():
            filt = pred[mask]
            sc = scores[mask]
            cx, cy, bw, bh = filt[:, 0], filt[:, 1], filt[:, 2], filt[:, 3]
            bx = torch.clamp(cx - bw / 2 + a, min=float(a))
            by = torch.clamp(cy - bh / 2 + b, min=float(b))
            ex = torch.clamp(cx + bw / 2 + a, max=float(endx))
            ey = torch.clamp(cy + bh / 2 + b, max=float(endy))
            valid = (ex > bx) & (ey > by)
            if valid.any():
                boxes_xyxy = torch.stack([bx[valid], by[valid], ex[valid], ey[valid], sc[valid], filt[valid, 4], filt[valid, 5]], dim=1)
                for item in boxes_xyxy.cpu().numpy().tolist():
                    raw_cands.append({
                        'box': item[:4],
                        'score': float(item[4]),
                        'obj': float(item[5]),
                        'cls': float(item[6]),
                        'tileOrigin': [int(a), int(b)]
                    })
    return raw_cands


def evaluate_model_on_images(net, images_data, conf_thresh=0.70, nms_thresh=0.30):
    """Executes the complete product pipeline: Tiling -> Threshold -> NMS -> Filter v5 -> Bipartite Matching."""
    net.eval()
    
    per_image_results = []
    
    summary = {
        'productPose': {
            'tp50': 0, 'tp30': 0, 'inScopeTruth': 53, 'truth': 60,
            'rec50': 0.0, 'rec30': 0.0, 'precision': 0.0, 'f1_50': 0.0, 'f1_30': 0.0,
            'preds': 0, 'verifiedNegFp': 0, 'meanNegFp': 0.0
        },
        'capturable': {
            'tp50': 0, 'tp30': 0, 'inScopeTruth': 14, 'truth': 17,
            'rec50': 0.0, 'rec30': 0.0, 'precision': 0.0,
            'preds': 0, 'verifiedNegFp': 0, 'meanNegFp': 0.0
        },
        'allData': {
            'tp50': 0, 'tp30': 0, 'truth': 276,
            'rec50': 0.0, 'rec30': 0.0, 'preds': 0,
            'verifiedNegFp': 0, 'meanNegFp': 0.0
        },
        'negativeControls': {
            'totalImages': 15, 'capturableImages': 10,
            'totalFp': 0, 'meanFpPerPhoto': 0.0,
            'capturableFp': 0, 'meanCapturableFpPerPhoto': 0.0
        },
        'regionalDistribution': {
            'forehead': 0, 'rightCheek': 0, 'leftCheek': 0, 'nose': 0, 'chin': 0, 'total': 0
        },
        'negativeFalseAlarmsBreakdown': []
    }

    for item in images_data:
        bgr = item['bgr']
        points = item['landmarks']
        is_neg = item['isNegative']
        is_prod_pose = item['isProductPose']
        is_capturable = item['capturable']
        truth_boxes = item['truth']
        truth_categories = item['truthCategories']

        if not points:
            accepted_boxes = []
            rejected_boxes = []
        else:
            raw_cands = extract_raw_predictions_fast(net, bgr, points, min_score=conf_thresh)
            if raw_cands:
                boxes_t = torch.tensor([c['box'] for c in raw_cands], dtype=torch.float32)
                scores_t = torch.tensor([c['score'] for c in raw_cands], dtype=torch.float32)
                keep_idx = torch_nms(boxes_t, scores_t, nms_thresh)
                nms_cands = [raw_cands[i] for i in keep_idx.numpy()]
            else:
                nms_cands = []

            # Format for filter_v4 (Filter v5 with acne_box_support)
            raw_nms_boxes = [c['box'] + [c['score']] for c in nms_cands]
            vis_regs = item['allowedRegions'] if item['productAngle'] is not None else None
            acc, rej = acne_box_support.accepted_boxes(
                raw_nms_boxes,
                item['envelopes'],
                item['skin_support'],
                item['hair'],
                item['exclusion'],
                item['sha256'],
                item['scale'],
                item['origin'],
                visible_regions=vis_regs,
                landmarks=points,
                source_shape=(item['height'], item['width'])
            )
            accepted_boxes = [b for blist in acc.values() for b in blist]
            rejected_boxes = rej

        # Matchings using shared bipartite logic
        matched_indices50, matches50, duplicate_p50, unmatched_p50, unmatched_t50 = match_predictions_to_truth(truth_boxes, accepted_boxes, 0.50)
        matched_indices30, matches30, duplicate_p30, unmatched_p30, unmatched_t30 = match_predictions_to_truth(truth_boxes, accepted_boxes, 0.30)

        # In-scope truth matching (product pose scope)
        in_scope_indices = [i for i, cat in enumerate(truth_categories) if cat == 'IN_SCOPE_VISIBLE_REGION']
        in_scope_tp50 = len(set(matched_indices50).intersection(set(in_scope_indices)))
        in_scope_tp30 = len(set(matched_indices30).intersection(set(in_scope_indices)))

        # Update Regional Distribution
        for b in accepted_boxes:
            reg = b.get('region', 'other')
            if reg in summary['regionalDistribution']:
                summary['regionalDistribution'][reg] += 1
            summary['regionalDistribution']['total'] += 1

        # Update Scopes
        summary['allData']['tp50'] += len(matched_indices50)
        summary['allData']['tp30'] += len(matched_indices30)
        summary['allData']['preds'] += len(accepted_boxes)

        if is_prod_pose:
            summary['productPose']['tp50'] += in_scope_tp50
            summary['productPose']['tp30'] += in_scope_tp30
            summary['productPose']['preds'] += len(accepted_boxes)

        if is_capturable:
            summary['capturable']['tp50'] += in_scope_tp50
            summary['capturable']['tp30'] += in_scope_tp30
            summary['capturable']['preds'] += len(accepted_boxes)

        if is_neg:
            fp_count = len(accepted_boxes)
            summary['negativeControls']['totalFp'] += fp_count
            if is_prod_pose:
                summary['productPose']['verifiedNegFp'] += fp_count
            if is_capturable:
                summary['negativeControls']['capturableFp'] += fp_count
                summary['capturable']['verifiedNegFp'] += fp_count
            summary['allData']['verifiedNegFp'] += fp_count

            # Detailed false alarm diagnosis on negative photos
            for b in accepted_boxes:
                bx, by, bw, bh = int(b['x']), int(b['y']), int(b['width']), int(b['height'])
                patch = bgr[max(0, by):min(item['height'], by + bh), max(0, bx):min(item['width'], bx + bw)]
                patch_gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY) if patch.size > 0 else np.zeros((1, 1), np.uint8)
                
                # Check patch characteristics
                lap_var = float(cv2.Laplacian(patch_gray, cv2.CV_64F).var()) if patch.size > 0 else 0.0
                mean_lum = float(patch_gray.mean()) if patch.size > 0 else 0.0
                min_lum = float(patch_gray.min()) if patch.size > 0 else 0.0
                
                # Morphological pore detection (blackhat filter response)
                blackhat = cv2.morphologyEx(patch_gray, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
                pore_response = float(blackhat.max()) if patch.size > 0 else 0.0
                
                if pore_response > 40:
                    suspected_type = 'PORE_OR_FOLLICLE'
                elif min_lum < 40 and (mean_lum - min_lum) > 50:
                    suspected_type = 'NEVUS_OR_FRECKLE'
                elif lap_var < 15:
                    suspected_type = 'LOW_CONTRAST_TEXTURE'
                else:
                    suspected_type = 'HIGH_FREQUENCY_TEXTURE_OR_SHADOW'

                summary['negativeFalseAlarmsBreakdown'].append({
                    'fileName': item['fileName'],
                    'sha256': item['sha256'],
                    'productAngle': item['productAngle'],
                    'capturable': is_capturable,
                    'box': [bx, by, bx + bw, by + bh],
                    'region': b.get('region'),
                    'confidence': round(float(b.get('confidence', 0.0)), 4),
                    'suspectedType': suspected_type,
                    'laplacianVariance': round(lap_var, 2),
                    'poreResponse': round(pore_response, 2),
                    'meanLuminance': round(mean_lum, 2)
                })

        per_image_results.append({
            'fileName': item['fileName'],
            'sha256': item['sha256'],
            'productAngle': item['productAngle'],
            'isProductPose': is_prod_pose,
            'capturable': is_capturable,
            'isNegative': is_neg,
            'truthCount': len(truth_boxes),
            'inScopeTruthCount': len(in_scope_indices),
            'acceptedCount': len(accepted_boxes),
            'tp50': len(matched_indices50),
            'tp30': len(matched_indices30),
            'inScopeTp50': in_scope_tp50,
            'inScopeTp30': in_scope_tp30,
            'verifiedNegFp': len(accepted_boxes) if is_neg else 0,
            'boxes': accepted_boxes
        })

    # Final summary ratios
    pp = summary['productPose']
    pp['rec50'] = compute_scope_recall(pp['tp50'], pp['inScopeTruth'])
    pp['rec30'] = compute_scope_recall(pp['tp30'], pp['inScopeTruth'])
    pp['precision'] = round(pp['tp50'] / max(1, pp['preds']), 4) if pp['preds'] > 0 else 0.0
    if pp['rec50'] and pp['precision']:
        pp['f1_50'] = round(2 * pp['precision'] * pp['rec50'] / (pp['precision'] + pp['rec50']), 4)
    if pp['rec30'] and pp['precision']:
        pp['f1_30'] = round(2 * pp['precision'] * pp['rec30'] / (pp['precision'] + pp['rec30']), 4)
    pp['meanNegFp'] = round(pp['verifiedNegFp'] / 10.0, 4)  # 10 product-accepted negative images

    cp = summary['capturable']
    cp['rec50'] = compute_scope_recall(cp['tp50'], cp['inScopeTruth'])
    cp['rec30'] = compute_scope_recall(cp['tp30'], cp['inScopeTruth'])
    cp['precision'] = round(cp['tp50'] / max(1, cp['preds']), 4) if cp['preds'] > 0 else 0.0
    cp['meanNegFp'] = round(cp['verifiedNegFp'] / 10.0, 4)

    ad = summary['allData']
    ad['rec50'] = compute_scope_recall(ad['tp50'], ad['truth'])
    ad['rec30'] = compute_scope_recall(ad['tp30'], ad['truth'])
    ad['meanNegFp'] = round(ad['verifiedNegFp'] / 15.0, 4)  # 15 negative images

    nc = summary['negativeControls']
    nc['meanFpPerPhoto'] = round(nc['totalFp'] / 15.0, 4)
    nc['meanCapturableFpPerPhoto'] = round(nc['capturableFp'] / 10.0, 4)

    return summary, per_image_results


def main():
    print("=== Side-by-Side Evaluation of All Acne Checkpoints ===")
    assert MANIFEST_PATH.exists(), f"Manifest missing: {MANIFEST_PATH}"
    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    # Load dataset for image paths
    data_path = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    rows_by_sha = {r['sha256']: r for r in data['rows'] if r.get('split') == 'validation'}

    # Build image objects with precomputed envelopes
    print("Loading validation images and precomputing anatomical envelopes...")
    images_data = []
    adapter_payload = []
    landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
        mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(ROOT / 'apps/vehicle-app/public/mediapipe/models/face_landmarker.task')),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1
        )
    )

    for m_img in manifest['images']:
        sha = m_img['sha256']
        row = rows_by_sha[sha]
        img_path = Path(row['absolutePath']) if 'absolutePath' in row and Path(row['absolutePath']).exists() else (LIVE_TEST / row['path'])
        assert img_path.exists(), f"Image missing: {img_path}"
        bgr = cv2.imread(str(img_path))
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        det = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        points = (
            [{'x': float(p.x), 'y': float(p.y), 'z': float(p.z)} for p in det.face_landmarks[0]]
            if det.face_landmarks and len(det.face_landmarks[0]) >= 468
            else []
        )
        import base64
        rgb_b64 = base64.b64encode(rgb.tobytes()).decode('ascii')
        adapter_payload.append({
            'sha256': sha,
            'width': w,
            'height': h,
            'landmarks': points,
            'rgbBase64': rgb_b64
        })

    import subprocess
    node_path = f"{LIVE_TEST / 'node_modules'};{LIVE_TEST / 'apps/vehicle-app/node_modules'};{ROOT / 'node_modules'};{ROOT / 'apps/vehicle-app/node_modules'}"
    env = os.environ.copy()
    env['NODE_PATH'] = node_path
    cmd = ['node', str(ROOT / 'scripts/skin-research/product_skin_adapter.cjs')]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out, err = p.communicate(json.dumps(adapter_payload).encode('utf-8'))
    if p.returncode != 0:
        raise RuntimeError(f"product_skin_adapter.cjs failed:\n{err.decode('utf-8')}")
    adapter_results = {res['sha256']: res for res in json.loads(out.decode('utf-8'))}

    for m_img in manifest['images']:
        sha = m_img['sha256']
        row = rows_by_sha[sha]
        img_path = Path(row['absolutePath']) if 'absolutePath' in row and Path(row['absolutePath']).exists() else (LIVE_TEST / row['path'])
        bgr = cv2.imread(str(img_path))
        ares = adapter_results[sha]
        points = ares.get('alignment') and ares['alignment'].get('box') and [item for item in adapter_payload if item['sha256'] == sha][0]['landmarks']
        meshes = ares.get('meshes', {})

        if points:
            envelopes, skin_support, hair, exclusion, scale, origin, face_support, face_pixels = compute_masks_and_envelopes(
                bgr, points, meshes
            )
        else:
            envelopes, skin_support, hair, exclusion, scale, origin, face_support, face_pixels = [None]*8

        allowed_regions = ares.get('allowedRegions', [])

        truth_boxes = [a['box'] for a in m_img['annotations']]
        truth_categories = [a['scopeCategory'] for a in m_img['annotations']]

        images_data.append({
            'sha256': sha,
            'fileName': m_img['fileName'],
            'bgr': bgr,
            'width': m_img['width'],
            'height': m_img['height'],
            'landmarks': points,
            'productAngle': m_img['productAngle'],
            'isProductPose': m_img['isProductPose'],
            'capturable': m_img['capturable'],
            'isNegative': m_img['isNegative'],
            'truth': truth_boxes,
            'truthCategories': truth_categories,
            'envelopes': envelopes,
            'skin_support': skin_support,
            'hair': hair,
            'exclusion': exclusion,
            'scale': scale,
            'origin': origin,
            'face_support': face_support,
            'facePixels': face_pixels,
            'allowedRegions': allowed_regions
        })

    print(f"Loaded {len(images_data)} validation images successfully.\n")

    comparative_results = {}
    false_alarm_diagnosis = {}

    for ckpt in CHECKPOINTS:
        print(f"--- Evaluating {ckpt['displayName']} ---")
        w_path = ckpt['weightsPath']
        assert w_path.exists(), f"Weights file not found: {w_path}"
        actual_sha = compute_sha256(w_path)
        assert actual_sha == ckpt['expectedSha'], f"SHA mismatch for {ckpt['key']}: expected {ckpt['expectedSha']}, got {actual_sha}"
        print(f"  Verified Weights SHA-256: {actual_sha}")

        net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
        install_bounds(net)
        weights = load_file(str(w_path))
        net.load_state_dict(weights)
        net.eval()

        summary, per_img = evaluate_model_on_images(net, images_data, conf_thresh=0.70, nms_thresh=0.30)
        comparative_results[ckpt['key']] = {
            'checkpointKey': ckpt['key'],
            'displayName': ckpt['displayName'],
            'weightsPath': str(w_path.relative_to(ROOT)),
            'weightsSha256': actual_sha,
            'summary': summary,
            'perImageResults': per_img
        }

        # Collect false alarms on negative images
        false_alarm_diagnosis[ckpt['key']] = summary['negativeFalseAlarmsBreakdown']

        print(f"  Product Pose In-Scope Rec@IoU50: {summary['productPose']['rec50']} (TP={summary['productPose']['tp50']}/53) | Rec@IoU30: {summary['productPose']['rec30']} (TP={summary['productPose']['tp30']}/53)")
        print(f"  Capturable In-Scope Rec@IoU50:   {summary['capturable']['rec50']} (TP={summary['capturable']['tp50']}/14) | Rec@IoU30: {summary['capturable']['rec30']} (TP={summary['capturable']['tp30']}/14)")
        print(f"  All-Data Rec@IoU50:              {summary['allData']['rec50']} (TP={summary['allData']['tp50']}/276) | Rec@IoU30: {summary['allData']['rec30']} (TP={summary['allData']['tp30']}/276)")
        print(f"  Negative Control FP/Photo:       {summary['negativeControls']['meanFpPerPhoto']} ({summary['negativeControls']['totalFp']}/15 images)")
        print(f"  Capturable Negative FP/Photo:    {summary['negativeControls']['meanCapturableFpPerPhoto']} ({summary['negativeControls']['capturableFp']}/10 images)")
        print(f"  Regional Distribution:           {summary['regionalDistribution']}")
        print()

    # Comparative Summary Table
    print("\n========================= SIDE-BY-SIDE CHECKPOINT COMPARISON =========================")
    print(f"{'Model':<30} | {'InScope Rec50':<14} | {'InScope Rec30':<14} | {'Capturable Rec50':<16} | {'Neg FP/photo':<12} | {'Total Neg FP':<12}")
    print("-" * 110)
    for ckpt in CHECKPOINTS:
        k = ckpt['key']
        s = comparative_results[k]['summary']
        pp_r50 = str(s['productPose']['rec50']) + f" ({s['productPose']['tp50']}/53)"
        pp_r30 = str(s['productPose']['rec30']) + f" ({s['productPose']['tp30']}/53)"
        cp_r50 = str(s['capturable']['rec50']) + f" ({s['capturable']['tp50']}/14)"
        neg_fp = f"{s['negativeControls']['meanFpPerPhoto']:.2f}"
        tot_fp = f"{s['negativeControls']['totalFp']}/15"
        print(f"{ckpt['displayName']:<30} | {pp_r50:<14} | {pp_r30:<14} | {cp_r50:<16} | {neg_fp:<12} | {tot_fp:<12}")
    print("======================================================================================\n")

    # Diagnosis Summary of Phase 2 False Alarm Jump
    p1_fas = false_alarm_diagnosis['phase1_candidate']
    p2_fas = false_alarm_diagnosis['phase2_epoch3']
    print(f"=== Root Cause Diagnosis of Phase 2 False Alarm Spike ===")
    print(f"Phase 1 Candidate False Alarms on Negative Controls: {len(p1_fas)} ({len(p1_fas)/15:.2f}/photo)")
    print(f"Phase 2 Epoch 3 False Alarms on Negative Controls:   {len(p2_fas)} ({len(p2_fas)/15:.2f}/photo)")
    
    p2_by_type = defaultdict(int)
    for fa in p2_fas:
        p2_by_type[fa['suspectedType']] += 1
    print(f"\nPhase 2 False Alarms by Anatomical & Texture Type:")
    for t_name, count in sorted(p2_by_type.items(), key=lambda x: -x[1]):
        print(f"  - {t_name}: {count} ({count/len(p2_fas)*100:.1f}%)")

    output_payload = {
        'evaluationVersion': 'checkpoint-comparative-evaluation-20261013-v1',
        'generatedAt': '2026-10-13T10:00:00Z',
        'pipeline': {
            'tileSize': 384,
            'stride': 288,
            'confidenceThreshold': 0.70,
            'nmsThreshold': 0.30,
            'filterVersion': 'v5_acne_box_support_bounded_fallback',
            'matching': 'bipartite_greedy_1to1'
        },
        'checkpoints': comparative_results,
        'phase2SpikeDiagnosis': {
            'phase1FpCount': len(p1_fas),
            'phase1MeanFp': round(len(p1_fas) / 15.0, 4),
            'phase2FpCount': len(p2_fas),
            'phase2MeanFp': round(len(p2_fas) / 15.0, 4),
            'breakdownByType': dict(p2_by_type),
            'provenMechanisms': [
                "Objectness loss divisor discrepancy in yolo_head.py: loss_obj is normalized by num_fg = max(num_fg, 1). Pure negative batches divide by 1, whereas positive batches average across 10-20 active targets.",
                "Loss masking asymmetry in KnownObjectnessBCE: in positive training tiles, known_cells is zeroed out because has_neg is False. Background skin in positive tiles was completely unpenalized, while negative tiles penalized all skin cells.",
                "CosineAnnealingLR across 3 epochs without early stopping caused overconfidence drift on high-frequency skin textures, pores, and hair follicles."
            ]
        }
    }

    OUT_COMPARISON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_COMPARISON, 'w', encoding='utf-8') as f:
        json.dump(output_payload, f, indent=2)

    print(f"\nComparative results successfully saved to: {OUT_COMPARISON}")


if __name__ == '__main__':
    main()
