#!/usr/bin/env python3
"""Audit eyewear, framing, pose, and quality across validation photos using CDC production methods."""

import sys
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from skin_eyewear import classify_source
from prepare_canonical_validation_cache import load_canonical_validation_cache


def skin_source_framed(points, width, height):
    if len(points) < 468:
        return False
    xs = [p['x'] for p in points[:468]]
    ys = [p['y'] for p in points[:468]]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return (
        min_x > 0.005 and max_x < 0.995 and
        min_y > 0.005 and max_y < 0.995 and
        (max_x - min_x) * width >= 4 and
        (max_y - min_y) * height >= 4
    )


def compute_quality(bgr, points):
    h, w = bgr.shape[:2]
    # Compute face bounding box from 468 landmarks
    xs = [p['x'] * w for p in points[:468]]
    ys = [p['y'] * h for p in points[:468]]
    x0 = max(0, min(w - 1, int(np.floor(min(xs)))))
    y0 = max(0, min(h - 1, int(np.floor(min(ys)))))
    x1 = min(w, int(np.ceil(max(xs))))
    y1 = min(h, int(np.ceil(max(ys))))

    if x1 - x0 < 4 or y1 - y0 < 4:
        return {'isValid': False, 'status': 'NO_FACE', 'avgLuminance': 0, 'blurScore': 0}

    # BGR to luminance: lum = 0.299 * R + 0.587 * G + 0.114 * B
    # In BGR: data[0] is B, data[1] is G, data[2] is R
    crop = bgr[y0:y1, x0:x1]
    ch, cw = crop.shape[:2]
    
    # Matching checkQuality: step = 2
    step = 2
    lum = 0.299 * crop[::step, ::step, 2] + 0.587 * crop[::step, ::step, 1] + 0.114 * crop[::step, ::step, 0]
    avg_lum = float(np.mean(lum))
    
    # Horizontal gradient difference
    diff = np.abs(lum[:, 1:] - lum[:, :-1])
    blur_score = float(np.mean(diff)) if diff.size > 0 else 0.0

    if avg_lum < 40:
        status = 'TOO_DARK'
        valid = False
    elif avg_lum > 220:
        status = 'TOO_BRIGHT'
        valid = False
    elif blur_score < 4.0:
        status = 'BLURRY'
        valid = False
    else:
        status = 'OPTIMAL'
        valid = True

    return {
        'isValid': valid,
        'status': status,
        'avgLuminance': round(avg_lum, 2),
        'blurScore': round(blur_score, 2),
        'faceBox': [x0, y0, x1 - x0, y1 - y0]
    }


def compute_pose(points, width, height):
    # MediaPipe landmark indices
    # NOSE_TIP: 1, LEFT_EYE_OUTER: 263, RIGHT_EYE_OUTER: 33, FOREHEAD_TOP: 10, CHIN_BOTTOM: 152
    nose = points[1]
    left_eye = points[263]
    right_eye = points[33]
    forehead = points[10]
    chin = points[152]

    eye_mid_x = (left_eye['x'] + right_eye['x']) / 2.0
    eye_dist = abs(left_eye['x'] - right_eye['x'])
    face_height_norm = abs(chin['y'] - forehead['y'])

    yaw = (nose['x'] - eye_mid_x) / (eye_dist * 0.8) if eye_dist > 0 else 0.0
    pitch = (nose['y'] - (forehead['y'] + face_height_norm * 0.6)) / (face_height_norm * 0.5) if face_height_norm > 0 else 0.0
    roll = np.arctan2((left_eye['y'] - right_eye['y']) * height, (left_eye['x'] - right_eye['x']) * width)

    return {
        'yaw': round(float(yaw), 2),
        'pitch': round(float(pitch), 2),
        'roll': round(float(roll), 2)
    }


def main():
    print("=== AUDIT VALIDATION IMAGES VIA CDC EYEWEAR & QUALITY PREFLIGHT ===")
    cached_images = load_canonical_validation_cache()
    print(f"Loaded {len(cached_images)} cached validation items.")

    findings = []
    eyewear_rejections = []
    quality_rejections = []
    accepted_product_items = []

    for idx, item in enumerate(cached_images):
        sha = item['sha256']
        bgr = item['bgr']
        points = item['landmarks']
        is_neg = item['isNegative']
        is_prod_pose = item['isProductPose']
        product_angle = item['productAngle']
        in_scope_truth = len([c for c in item['truthCategories'] if c == 'IN_SCOPE_VISIBLE_REGION'])
        h, w = bgr.shape[:2]

        if not points:
            findings.append({
                'index': idx,
                'sha256': sha,
                'isNegative': is_neg,
                'productAngle': product_angle,
                'isProductPose': is_prod_pose,
                'inScopeTruth': in_scope_truth,
                'acceptedForProductAnalysis': False,
                'rejectionReasons': ['NO_LANDMARKS'],
                'decision': 'REJECT_NO_LANDMARKS',
                'reason': 'MediaPipe landmarks unavailable'
            })
            continue

        # 1. CDC Eyewear Check
        eyewear_res = classify_source(bgr, points)
        eyewear_status = eyewear_res['status']
        eyewear_prob = eyewear_res['probability']

        # 2. Framing Check
        framed = skin_source_framed(points, w, h)

        # 3. Quality Check
        quality_res = compute_quality(bgr, points)

        # 4. Pose Check
        pose_res = compute_pose(points, w, h)

        # Determine Product Capture Preflight Status
        # Product Gate: eyewear == 'CLEAR' AND framed == True AND quality['isValid'] == True AND pose within bounds
        reasons = []
        if eyewear_status != 'CLEAR':
            reasons.append(f"EYEWEAR_{eyewear_status}(prob={eyewear_prob:.3f})")
            eyewear_rejections.append((sha, eyewear_status, eyewear_prob, is_neg))

        if not framed:
            reasons.append("NOT_SOURCE_FRAMED")

        if not quality_res['isValid']:
            reasons.append(f"QUALITY_{quality_res['status']}(blur={quality_res['blurScore']},lum={quality_res['avgLuminance']})")
            quality_rejections.append((sha, quality_res['status'], is_neg))

        # Angle pose matching
        if product_angle == 'FRONT':
            if abs(pose_res['yaw']) > 0.20:
                reasons.append(f"YAW_OUT_OF_BOUNDS({pose_res['yaw']})")
        elif product_angle == 'RIGHT':
            if not (-0.65 <= pose_res['yaw'] <= -0.28):
                reasons.append(f"SIDE_YAW_OUT_OF_BOUNDS({pose_res['yaw']})")
        elif product_angle == 'LEFT':
            if not (0.28 <= pose_res['yaw'] <= 0.65):
                reasons.append(f"SIDE_YAW_OUT_OF_BOUNDS({pose_res['yaw']})")

        if abs(pose_res['pitch']) > 0.22:
            reasons.append(f"PITCH_OUT_OF_BOUNDS({pose_res['pitch']})")
        if abs(pose_res['roll']) > 0.15:
            reasons.append(f"ROLL_OUT_OF_BOUNDS({pose_res['roll']})")

        accepted = (len(reasons) == 0 and is_prod_pose)

        record = {
            'index': idx,
            'sha256': sha,
            'isNegative': is_neg,
            'productAngle': product_angle,
            'isProductPose': is_prod_pose,
            'inScopeTruth': in_scope_truth,
            'eyewear': {
                'status': eyewear_status,
                'probability': round(eyewear_prob, 4),
                'crop': eyewear_res['crop']
            },
            'quality': quality_res,
            'pose': pose_res,
            'framed': framed,
            'acceptedForProductAnalysis': accepted,
            'rejectionReasons': reasons
        }
        findings.append(record)
        if accepted:
            accepted_product_items.append(record)

    print("\n--- SUMMARY OF VALIDATION PREFLIGHT AUDIT ---")
    print(f"Total Cached Validation Items: {len(findings)}")
    print(f"Total Scored Positive Items: {len([f for f in findings if not f.get('isNegative', False) and f.get('isProductPose', False)])}")
    print(f"Total Negative Items: {len([f for f in findings if f.get('isNegative', False)])}")
    print(f"Total Eyewear Rejections: {len(eyewear_rejections)}")
    for r in eyewear_rejections:
        print(f"  {r[0][:8]}: status={r[1]}, prob={r[2]:.3f}, isNegative={r[3]}")

    print(f"\nTotal Quality Rejections (Blur/Dark/Bright): {len(quality_rejections)}")
    print(f"Accepted for Product Analysis: {len(accepted_product_items)} items")
    acc_pos = [f for f in accepted_product_items if not f['isNegative']]
    acc_neg = [f for f in accepted_product_items if f['isNegative']]
    acc_truth = sum(f['inScopeTruth'] for f in acc_pos)
    print(f"  Accepted Positive Photos: {len(acc_pos)} (containing {acc_truth} in-scope targets)")
    print(f"  Accepted Negative Photos: {len(acc_neg)}")

    out_path = ROOT / 'audit-results/acne-input-audit-20261015-findings.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(findings, f, indent=2)
    print(f"Detailed audit saved to: {out_path}")


if __name__ == '__main__':
    main()
