#!/usr/bin/env python3
"""Rigorous Dual-Scope Evaluation and Input Suitability Audit across All 5 Checkpoint Models.

Contract & Integrity Rules (User Directives):
1. Fixed Model Identifiers:
   - Step 0 (Calibrated Baseline): SHA 18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655
   - Epoch 1 (Step 207): SHA a58ed405ff7f5d280551f03aa52100e7d9dac24f4505c194706bf3dc1df27b76
   - Epoch 2 (Step 414): SHA 8bd97bee474a7a3152629a5cfc0088f944fd83e6350835398c4c4802ede00876
   - Epoch 3 (Step 621): SHA 4f9d2081f5f7cad3685a5e2d0434ca54731fa5ef8a2ba9c9a4a809532014af2f
   - Epoch 4 (Step 828): SHA 91c1bdfd06d6b04d0040c5bcd4a8204c1a38d8dc88c859d42b4e8fed564e6233
2. Evaluates Two Fixed Scopes:
   - Scope A (Eski Canonical Kapsam): 43 validation images, 9 scored positive (53 targets), 15 negative photos.
   - Scope B (Güncel Ürün Kapılarından Geçen Sabit Kapsam): Photos passing CDC eyewear preflight, framing,
     quality (blurScore >= 4.0, luminance in [40, 220]), and angle pose matching.
3. Strict Parity & Invariants:
   - Native 384x384 BGR float32, pad 114, conf=0.30, NMS=0.30, Filter v5 anatomical support,
     1-to-1 bipartite matching at IoU 0.50.
   - Disambiguate source lesion ID from tile observation ID (no double counting).
   - Zero metric falsification; no tuning of conf/NMS, no box enlargement.
4. Annotation & Target Analysis:
   - Detailed inspection of all 53 targets (measurability, blur/visibility context, size breakdown).
"""

import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple
import numpy as np
import torch
from safetensors.torch import load_file

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from skin_eyewear import classify_source
from prepare_canonical_validation_cache import load_canonical_validation_cache
from train_p2_focal_trial import extract_p2_predictions_fast, torch_nms, match_predictions_to_truth
import acne_box_support

TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014'
RESEARCH_DIR = ROOT.parent / 'research/acne-input-audit-20261015'
LOCAL_AUDIT_DIR = ROOT / 'audit-results/acne-input-audit-20261015'

MODELS_CONFIG = [
    {
        'name': 'Step 0 (Calibrated Baseline)',
        'dirName': 'checkpoint-epoch-00-step-000000-1792014463030016700',
        'epoch': 0,
        'step': 0,
        'expectedSha': '18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'
    },
    {
        'name': 'Epoch 1 (Fine-tuned)',
        'dirName': 'checkpoint-epoch-01-step-000207-1792016978761664300',
        'epoch': 1,
        'step': 207,
        'expectedSha': 'a58ed405ff7f5d280551f03aa52100e7d9dac24f4505c194706bf3dc1df27b76'
    },
    {
        'name': 'Epoch 2 (Fine-tuned)',
        'dirName': 'checkpoint-epoch-02-step-000414-1792018400781891800',
        'epoch': 2,
        'step': 414,
        'expectedSha': '8bd97bee474a7a3152629a5cfc0088f944fd83e6350835398c4c4802ede00876'
    },
    {
        'name': 'Epoch 3 (Fine-tuned)',
        'dirName': 'checkpoint-epoch-03-step-000621-1792019596010397000',
        'epoch': 3,
        'step': 621,
        'expectedSha': '4f9d2081f5f7cad3685a5e2d0434ca54731fa5ef8a2ba9c9a4a809532014af2f'
    },
    {
        'name': 'Epoch 4 (Fine-tuned)',
        'dirName': 'checkpoint-epoch-04-step-000828-1792020809525886000',
        'epoch': 4,
        'step': 828,
        'expectedSha': '91c1bdfd06d6b04d0040c5bcd4a8204c1a38d8dc88c859d42b4e8fed564e6233'
    }
]


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


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
    xs = [p['x'] * w for p in points[:468]]
    ys = [p['y'] * h for p in points[:468]]
    x0 = max(0, min(w - 1, int(np.floor(min(xs)))))
    y0 = max(0, min(h - 1, int(np.floor(min(ys)))))
    x1 = min(w, int(np.ceil(max(xs))))
    y1 = min(h, int(np.ceil(max(ys))))

    if x1 - x0 < 4 or y1 - y0 < 4:
        return {'isValid': False, 'status': 'NO_FACE', 'avgLuminance': 0.0, 'blurScore': 0.0}

    crop = bgr[y0:y1, x0:x1]
    step = 2
    lum = 0.299 * crop[::step, ::step, 2] + 0.587 * crop[::step, ::step, 1] + 0.114 * crop[::step, ::step, 0]
    avg_lum = float(np.mean(lum))
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
    # MediaPipe LM.NOSE_TIP: 1, LEFT_EYE_INNER: 362, RIGHT_EYE_INNER: 133, FOREHEAD_TOP: 10, CHIN_BOTTOM: 152
    nose = points[1]
    left_eye = points[362]
    right_eye = points[133]
    forehead = points[10]
    chin = points[152]

    eye_mid_x = (left_eye['x'] + right_eye['x']) / 2.0
    eye_dist = max(0.05, abs(left_eye['x'] - right_eye['x']))
    face_height_norm = max(0.1, abs(chin['y'] - forehead['y']))

    yaw = (nose['x'] - eye_mid_x) / (eye_dist * 0.8)
    pitch = (nose['y'] - (forehead['y'] + face_height_norm * 0.6)) / (face_height_norm * 0.5)
    roll = np.arctan2((left_eye['y'] - right_eye['y']) * height, (left_eye['x'] - right_eye['x']) * width)

    return {
        'yaw': round(float(yaw), 2),
        'pitch': round(float(pitch), 2),
        'roll': round(float(roll), 2)
    }


def matches_product_angle(pose: dict, angle: str, framed: bool) -> bool:
    if not framed or abs(pose['pitch']) > 0.22 or abs(pose['roll']) > 0.15:
        return False
    yaw = pose['yaw']
    if angle == 'FRONT':
        return abs(yaw) <= 0.20
    elif angle == 'RIGHT':
        return -0.65 <= yaw <= -0.28
    elif angle == 'LEFT':
        return 0.28 <= yaw <= 0.65
    return False


def run_evaluation_on_items(
    net: torch.nn.Module,
    items: List[dict],
    conf_threshold: float = 0.30,
    iou_threshold: float = 0.50
) -> Dict[str, Any]:
    """Runs sliding tile inference, Filter v5 postprocessing, and 1-to-1 bipartite matching."""
    net.eval()
    min_score = max(0.05, conf_threshold - 0.05)

    per_image_accepted_boxes = []
    for item in items:
        points = item['landmarks']
        bgr = item['bgr']
        if not points:
            per_image_accepted_boxes.append([])
            continue

        raw_cands = extract_p2_predictions_fast(net, bgr, points, min_score=min_score)
        cands = [c for c in raw_cands if c['score'] >= conf_threshold]
        if cands:
            boxes_t = torch.tensor([c['box'] for c in cands], dtype=torch.float32)
            scores_t = torch.tensor([c['score'] for c in cands], dtype=torch.float32)
            keep_idx = torch_nms(boxes_t, scores_t, 0.30)
            nms_cands = [cands[i] for i in keep_idx.numpy()]
        else:
            nms_cands = []

        raw_nms_boxes = [c['box'] + [c['score']] for c in nms_cands]
        vis_regs = item['allowedRegions'] if item['productAngle'] is not None else None
        acc, _ = acne_box_support.accepted_boxes(
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
        accepted = [b for blist in acc.values() for b in blist]
        per_image_accepted_boxes.append(accepted)

    # Compute bipartite matches and false positives
    total_in_scope = 0
    in_scope_tp50 = 0
    neg_total_fp = 0
    neg_photos_with_fp = 0
    total_neg_photos = 0

    size_breakdown = {
        'tiny_less_8px': {'total': 0, 'tp50': 0},
        'small_8_to_16px': {'total': 0, 'tp50': 0},
        'medium_16_to_32px': {'total': 0, 'tp50': 0}
    }

    per_target_details = []

    for item, accepted_boxes in zip(items, per_image_accepted_boxes):
        is_neg = item['isNegative']
        is_prod_pose = item['isProductPose']
        truth_boxes = item['truth']
        truth_categories = item['truthCategories']
        sha = item['sha256']

        if is_neg:
            total_neg_photos += 1
            fp_count = len(accepted_boxes)
            neg_total_fp += fp_count
            if fp_count > 0:
                neg_photos_with_fp += 1

        matched_indices50, _, _, _, _ = match_predictions_to_truth(truth_boxes, accepted_boxes, iou_threshold)
        in_scope_indices = [i for i, cat in enumerate(truth_categories) if cat == 'IN_SCOPE_VISIBLE_REGION']
        matched_in_scope50 = set(matched_indices50).intersection(set(in_scope_indices))

        if is_prod_pose and not is_neg:
            total_in_scope += len(in_scope_indices)
            in_scope_tp50 += len(matched_in_scope50)

            for idx in in_scope_indices:
                bx = truth_boxes[idx]
                dim = max(bx[2] - bx[0], bx[3] - bx[1])
                if dim < 8:
                    grp = 'tiny_less_8px'
                elif dim < 16:
                    grp = 'small_8_to_16px'
                else:
                    grp = 'medium_16_to_32px'
                size_breakdown[grp]['total'] += 1

                is_detected = (idx in matched_in_scope50)
                if is_detected:
                    size_breakdown[grp]['tp50'] += 1

                per_target_details.append({
                    'imageSha256': sha,
                    'targetIndex': idx,
                    'box': bx,
                    'dim': round(dim, 1),
                    'sizeGroup': grp,
                    'detected': is_detected
                })

    rec50 = round(in_scope_tp50 / max(total_in_scope, 1), 4) if total_in_scope > 0 else 0.0
    fp_per_photo = round(neg_total_fp / max(total_neg_photos, 1), 3) if total_neg_photos > 0 else 0.0

    return {
        'totalPhotosEvaluated': len(items),
        'positivePhotos': len([i for i in items if not i['isNegative'] and i['isProductPose']]),
        'negativePhotos': total_neg_photos,
        'inScopeTruth': total_in_scope,
        'inScopeTp50': in_scope_tp50,
        'rec50': rec50,
        'negTotalFp': neg_total_fp,
        'negPhotosWithFp': neg_photos_with_fp,
        'fpPerPhoto': fp_per_photo,
        'sizeBreakdown': {
            k: {
                'total': v['total'],
                'tp50': v['tp50'],
                'rec50': round(v['tp50'] / max(v['total'], 1), 4) if v['total'] > 0 else 0.0
            }
            for k, v in size_breakdown.items()
        },
        'targetDetails': per_target_details
    }


def main():
    print("=" * 80)
    print("RIGOROUS DUAL-SCOPE AUDIT & MODEL COMPARISON (STEPS 0 TO 4)")
    print("=" * 80)

    LOCAL_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load cached validation envelope items (exact 43 items)
    cached_images = load_canonical_validation_cache()
    print(f"Loaded {len(cached_images)} cached canonical validation items.")

    # 2. Build Preflight Audit Manifest for all items
    preflight_manifest = []
    scope_b_items = []
    scope_b_front_only_items = []

    for item in cached_images:
        sha = item['sha256']
        bgr = item['bgr']
        points = item['landmarks']
        h, w = bgr.shape[:2]
        is_neg = item['isNegative']
        angle = item['productAngle']
        in_scope_truth = len([c for c in item['truthCategories'] if c == 'IN_SCOPE_VISIBLE_REGION'])

        if not points:
            preflight_manifest.append({
                'sha256': sha,
                'isNegative': is_neg,
                'accepted': False,
                'reasons': ['NO_LANDMARKS']
            })
            continue

        eyewear_res = classify_source(bgr, points)
        framed = skin_source_framed(points, w, h)
        quality_res = compute_quality(bgr, points)
        pose_res = compute_pose(points, w, h)
        angle_matched = matches_product_angle(pose_res, angle, framed)

        reasons = []
        if eyewear_res['status'] != 'CLEAR':
            reasons.append(f"EYEWEAR_{eyewear_res['status']}(prob={eyewear_res['probability']:.4f})")
        if not framed:
            reasons.append("FRAMING_INVALID")
        if not quality_res['isValid']:
            reasons.append(f"QUALITY_{quality_res['status']}(blur={quality_res['blurScore']},lum={quality_res['avgLuminance']})")
        if not angle_matched:
            reasons.append(f"POSE_MISMATCH(angle={angle},yaw={pose_res['yaw']},pitch={pose_res['pitch']},roll={pose_res['roll']})")

        is_accepted = (len(reasons) == 0 and item['isProductPose'])

        entry = {
            'sha256': sha,
            'isNegative': is_neg,
            'productAngle': angle,
            'isProductPose': item['isProductPose'],
            'inScopeTruth': in_scope_truth,
            'eyewear': eyewear_res,
            'framed': framed,
            'quality': quality_res,
            'pose': pose_res,
            'accepted': is_accepted,
            'rejectionReasons': reasons
        }
        preflight_manifest.append(entry)

        if is_accepted:
            scope_b_items.append(item)
            if angle == 'FRONT':
                scope_b_front_only_items.append(item)

    print("\n[Scope Definition]")
    print(f"Scope A (Eski Canonical Kapsam): {len(cached_images)} total items (9 scored pos with 53 targets, 15 neg photos)")
    pos_b = [i for i in scope_b_items if not i['isNegative']]
    neg_b = [i for i in scope_b_items if i['isNegative']]
    truth_b = sum(len([c for c in i['truthCategories'] if c == 'IN_SCOPE_VISIBLE_REGION']) for i in pos_b)
    print(f"Scope B (Guncel Urun Kapilarindan Gecen Sabit Kapsam): {len(scope_b_items)} total items ({len(pos_b)} positive photos with {truth_b} targets, {len(neg_b)} verified negative photos)")
    print(f"  Accepted Positive SHAs: {[i['sha256'][:8] for i in pos_b]}")
    print(f"  Accepted Negative SHAs: {[i['sha256'][:8] for i in neg_b]}")

    # 3. Evaluate each of the 5 models under both scopes
    models_comparison = []

    net = build_yolox_p2_model()
    for mcfg in MODELS_CONFIG:
        mpath = TRIAL_DIR / mcfg['dirName'] / 'model.safetensors'
        actual_sha = sha256_file(mpath)
        assert actual_sha == mcfg['expectedSha'], f"Model SHA mismatch for {mcfg['name']}!"

        print(f"\nEvaluating: {mcfg['name']} (Epoch {mcfg['epoch']}, Step {mcfg['step']}, SHA: {actual_sha[:16]}...)")
        net.load_state_dict(load_file(str(mpath)), strict=True)

        t0 = time.time()
        res_scope_a = run_evaluation_on_items(net, cached_images, conf_threshold=0.30, iou_threshold=0.50)
        t_scope_a = time.time() - t0

        t1 = time.time()
        res_scope_b = run_evaluation_on_items(net, scope_b_items, conf_threshold=0.30, iou_threshold=0.50)
        t_scope_b = time.time() - t1

        t2 = time.time()
        res_scope_b_front = run_evaluation_on_items(net, scope_b_front_only_items, conf_threshold=0.30, iou_threshold=0.50)
        t_scope_b_front = time.time() - t2

        print(f"  Scope A: TP={res_scope_a['inScopeTp50']}/{res_scope_a['inScopeTruth']} ({res_scope_a['rec50']:.1%}) | negFP={res_scope_a['negTotalFp']} ({res_scope_a['fpPerPhoto']:.2f}/photo)")
        print(f"           tiny={res_scope_a['sizeBreakdown']['tiny_less_8px']['tp50']}/7, small={res_scope_a['sizeBreakdown']['small_8_to_16px']['tp50']}/31, med={res_scope_a['sizeBreakdown']['medium_16_to_32px']['tp50']}/15")
        print(f"  Scope B: TP={res_scope_b['inScopeTp50']}/{res_scope_b['inScopeTruth']} ({res_scope_b['rec50']:.1%}) | negFP={res_scope_b['negTotalFp']} ({res_scope_b['fpPerPhoto']:.2f}/photo)")
        print(f"           tiny={res_scope_b['sizeBreakdown']['tiny_less_8px']['tp50']}/{res_scope_b['sizeBreakdown']['tiny_less_8px']['total']}, small={res_scope_b['sizeBreakdown']['small_8_to_16px']['tp50']}/{res_scope_b['sizeBreakdown']['small_8_to_16px']['total']}, med={res_scope_b['sizeBreakdown']['medium_16_to_32px']['tp50']}/{res_scope_b['sizeBreakdown']['medium_16_to_32px']['total']}")

        models_comparison.append({
            'modelName': mcfg['name'],
            'epoch': mcfg['epoch'],
            'globalStep': mcfg['step'],
            'modelSha256': actual_sha,
            'scopeA_Canonical': res_scope_a,
            'scopeB_ProductPreflight': res_scope_b,
            'scopeB_FrontOnly': res_scope_b_front
        })

    # 4. Generate Comprehensive Audit Report
    audit_report = {
        'auditTimestamp': '2026-10-15T01:50:00+02:00',
        'auditVersion': 'CDC-Preflight-Aligned-Audit-v1',
        'eyewearClassifierContract': {
            'model': 'skin-eyewear-framefind-v1.onnx',
            'modelHash': '66f75c686974a04bf956d0ed6411315309afcabd36c400edec743953adafccb9',
            'policy': 'glasses-free-skin-capture-v1',
            'clearThreshold': 0.30,
            'uncertainThreshold': 0.50
        },
        'qualityContract': {
            'minBlurScore': 4.0,
            'minLuminance': 40.0,
            'maxLuminance': 220.0
        },
        'scopeDefinitions': {
            'scopeA_Canonical': {
                'totalItems': len(cached_images),
                'positivePhotos': 9,
                'inScopeTruth': 53,
                'negativePhotos': 15,
                'description': 'Historical canonical training evaluation scope without runtime preflight checks.'
            },
            'scopeB_ProductPreflight': {
                'totalItems': len(scope_b_items),
                'positivePhotos': len(pos_b),
                'inScopeTruth': truth_b,
                'negativePhotos': len(neg_b),
                'positiveShas': [i['sha256'] for i in pos_b],
                'negativeShas': [i['sha256'] for i in neg_b],
                'description': 'Production-gated scope: only inputs passing eyewear CLEAR, framing, blur >= 4.0, luminance in [40, 220], and pose match.'
            }
        },
        'preflightManifest': preflight_manifest,
        'modelsComparison': models_comparison
    }

    # Save to both target locations
    for target_dir in [LOCAL_AUDIT_DIR, RESEARCH_DIR]:
        out_file = target_dir / 'acne-dual-scope-audit-report.json'
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(audit_report, f, indent=2)
        print(f"Saved audit report to: {out_file}")

    print("\n" + "=" * 80)
    print("AUDIT AND COMPARISON COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    main()
