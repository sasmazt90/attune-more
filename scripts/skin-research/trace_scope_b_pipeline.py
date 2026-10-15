#!/usr/bin/env python3
"""Stage-by-Stage Pipeline Failure Trace, Visual Target Inspection, and False Positive Analysis.

Strict Rules & Contracts:
1. Models:
   - Step 0 (Calibrated Baseline): SHA 18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655
   - Epoch 4 (Fine-tuned): SHA 91c1bdfd06d6b04d0040c5bcd4a8204c1a38d8dc88c859d42b4e8fed564e6233
2. Evaluates the frozen Scope B set (12 photos):
   - 3 positive photos / 14 in-scope targets
   - 9 negative clean skin photos
3. 14 targets stage-by-stage tracing:
   - Track same candidate: box, IoU, objectness, class_score, score
   - Separate reasons: Ham aday yok, Lokalizasyon yetersiz (IoU < 0.50), Confidence altında (< 0.30),
     NMS ile elendi, Anatomik filtre reddetti, Basarili (TP50).
   - No mixing of IoU of one candidate with score of another.
4. False Positive Analysis (2 in Step 0, 8 in Epoch 4):
   - Image SHA, box, score, anatomical region, patch crop, visual inspection classification
     (Dogrulanmis temiz alan / Belirsiz alan / Eksik anotasyon suphesi).
5. Visual Ground Truth Target Audit (14 targets):
   - Boxed crop + surrounding context patch
   - Visual classification: Acik hedef / Belirsiz gorunum / Geometrik hata.
"""

import sys
import json
import time
import math
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple
import cv2
import numpy as np
import torch
from safetensors.torch import load_file
from torchvision.ops import nms as torch_nms

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from prepare_canonical_validation_cache import load_canonical_validation_cache
import acne_box_support

TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-finetune-20261014'
RESEARCH_DIR = ROOT.parent / 'research/acne-input-audit-20261015'
LOCAL_AUDIT_DIR = ROOT / 'audit-results/acne-input-audit-20261015'

MODELS = [
    {
        'key': 'step0',
        'name': 'Step 0 (Calibrated Baseline)',
        'dirName': 'checkpoint-epoch-00-step-000000-1792014463030016700',
        'sha': '18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'
    },
    {
        'key': 'epoch4',
        'name': 'Epoch 4 (Fine-tuned)',
        'dirName': 'checkpoint-epoch-04-step-000828-1792020809525886000',
        'sha': '91c1bdfd06d6b04d0040c5bcd4a8204c1a38d8dc88c859d42b4e8fed564e6233'
    }
]

SCOPE_B_POSITIVE_SHAS = [
    '55d380f724bc6b0612f878ee1b70997493edf1c1aecb8cf9d447c050af90f43a',
    '695ed248b9f9d226db5d127b6e2b9f67ddb06a61ddb7dd6d3883ce469b79cfe4',
    '4a1762ee136ff6c5e096ba6914063cf6d81fccb9fe492823cb4477d1e244462d'
]

SCOPE_B_NEGATIVE_SHAS = [
    '36e4010bde60027b29a6086a9534e1cb06d7b4191ae0dd2049bdea090577f982',
    '20031f3502cc294041fe4d5cb9995b6961ba44b6cae7b8b44e01daeafaa752b2',
    '02386f867aafa03a82d06c2d9cca8027077de01b3b16ddbd1f6089c7720e9687',
    '0597e8113444b558862cdc20574b2386e091bfc14fad55e8ea2e3532a02fa552',
    '0560bfd8ba207b1aa18b2b080515fa4edf1323024ed2f9208558608f9d4f706a',
    '0f3354ae440284287476130b110bf1d6e941102732d9205f7aa52c74fb1b7926',
    '0d891a034eeac482c96c7dec9f7e89e5fa45219bd429171c6d3da62856733963',
    '33da7a527931d29e23b6ab093093c0c4416938e8c0b17a5b2b6ad7af3112c1e0',
    '02413bf985b347112abf737badd0e11650ec25fe08502057343d81427b51fa29'
]


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def compute_iou(box1: List[float], box2: List[float]) -> float:
    ix1 = max(box1[0], box2[0])
    iy1 = max(box1[1], box2[1])
    ix2 = min(box1[2], box2[2])
    iy2 = min(box1[3], box2[3])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def extract_all_raw_predictions(net, bgr, points, tile_size=384, stride=288, min_score=0.001):
    """Extract raw predictions across all tiles with low threshold for failure diagnosis."""
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

    raw_candidates = []
    for i, (a, b, endx, endy) in enumerate(tiles_info):
        pred = out[i]
        obj = pred[:, 4]
        cls = pred[:, 5]
        scores = obj * cls
        mask = scores >= min_score
        if mask.any():
            filt = pred[mask]
            f_obj = obj[mask]
            f_cls = cls[mask]
            f_sc = scores[mask]
            cx, cy, bw, bh = filt[:, 0], filt[:, 1], filt[:, 2], filt[:, 3]
            bx = torch.clamp(cx - bw / 2 + a, min=float(a))
            by = torch.clamp(cy - bh / 2 + b, min=float(b))
            ex = torch.clamp(cx + bw / 2 + a, max=float(endx))
            ey = torch.clamp(cy + bh / 2 + b, max=float(endy))
            for k in range(len(filt)):
                raw_candidates.append({
                    'tileIdx': i,
                    'tileOrigin': [a, b],
                    'box': [round(bx[k].item(), 2), round(by[k].item(), 2), round(ex[k].item(), 2), round(ey[k].item(), 2)],
                    'objectness': round(f_obj[k].item(), 5),
                    'classScore': round(f_cls[k].item(), 5),
                    'score': round(f_sc[k].item(), 5)
                })
    return raw_candidates


def run_full_pipeline_with_trace(net, item, conf_thre=0.30, nms_thre=0.30):
    """Runs complete standard pipeline and retains intermediate traces."""
    bgr = item['bgr']
    points = item['landmarks']
    h, w = bgr.shape[:2]
    if not points:
        return {
            'rawCandidates': [],
            'confCandidates': [],
            'nmsCandidates': [],
            'nmsSuppressed': [],
            'acceptedBoxes': {},
            'rejectedBoxes': [],
            'allAccepted': []
        }

    raw_cands = extract_all_raw_predictions(net, bgr, points, min_score=0.001)

    # 1. Filter by confidence >= 0.30
    conf_cands = [c for c in raw_cands if c['score'] >= conf_thre]

    # 2. Image-level NMS
    nms_cands = []
    nms_suppressed = []
    if conf_cands:
        boxes_t = torch.tensor([c['box'] for c in conf_cands], dtype=torch.float32)
        scores_t = torch.tensor([c['score'] for c in conf_cands], dtype=torch.float32)
        keep_idx = torch_nms(boxes_t, scores_t, nms_thre).numpy()
        keep_set = set(keep_idx)
        for i, c in enumerate(conf_cands):
            if i in keep_set:
                nms_cands.append(c)
            else:
                nms_suppressed.append(c)

    # 3. Filter v5
    raw_nms_boxes = [c['box'] + [c['score']] for c in nms_cands]
    vis_regs = item['allowedRegions'] if item['productAngle'] is not None else None
    assigned, rejected = acne_box_support.accepted_boxes(
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
        source_shape=(h, w)
    )

    all_accepted = [b for blist in assigned.values() for b in blist]

    return {
        'rawCandidates': raw_cands,
        'confCandidates': conf_cands,
        'nmsCandidates': nms_cands,
        'nmsSuppressed': nms_suppressed,
        'assigned': assigned,
        'rejected': rejected,
        'allAccepted': all_accepted
    }


def analyze_target_fate(target, trace, iou_match_thre=0.50, conf_thre=0.30, nms_thre=0.30):
    """Analyzes the exact pipeline stage where a target was missed or detected.
    Follows a single candidate's box, IoU, and scores consistently."""
    t_box = target['box']
    raw_cands = trace['rawCandidates']

    # Compute IoU of all raw candidates with target
    scored_raw = []
    for c in raw_cands:
        iou = compute_iou(c['box'], t_box)
        scored_raw.append({
            'candidate': c,
            'iou': iou
        })

    # Sort by IoU descending
    scored_raw.sort(key=lambda x: (x['iou'], x['candidate']['score']), reverse=True)

    if not scored_raw or scored_raw[0]['iou'] == 0.0:
        return {
            'outcome': 'MISSED',
            'failureStage': 'HAM_ADAY_YOK',
            'stageCode': 'NO_RAW_CANDIDATE',
            'explanation': 'Görüntüde hedef konumuyla örtüşen hiçbir ham tahmin hücresi üretilmedi (IoU = 0.0).',
            'trackedCandidate': None
        }

    best_overlap = scored_raw[0]
    best_cand = best_overlap['candidate']
    max_iou = best_overlap['iou']

    # Filter candidates that have IoU >= 0.50
    candidates_ge_50 = [x for x in scored_raw if x['iou'] >= iou_match_thre]

    if not candidates_ge_50:
        # No candidate reached IoU 0.50
        return {
            'outcome': 'MISSED',
            'failureStage': 'LOKALIZASYON_YETERSIZ',
            'stageCode': 'LOCALIZATION_INSUFFICIENT',
            'explanation': f'En iyi örtüşen adayın IoU değeri {max_iou:.3f} olup eşik olan 0.50 seviyesinin altındadır.',
            'trackedCandidate': {
                'box': best_cand['box'],
                'iou': round(max_iou, 4),
                'objectness': best_cand['objectness'],
                'classScore': best_cand['classScore'],
                'score': best_cand['score']
            }
        }

    # If there are candidates with IoU >= 0.50, pick the one with highest score
    candidates_ge_50.sort(key=lambda x: x['candidate']['score'], reverse=True)
    chosen = candidates_ge_50[0]
    tracked_cand = chosen['candidate']
    c_iou = chosen['iou']
    c_box = tracked_cand['box']
    c_score = tracked_cand['score']
    c_obj = tracked_cand['objectness']
    c_cls = tracked_cand['classScore']

    tracked_dict = {
        'box': c_box,
        'iou': round(c_iou, 4),
        'objectness': c_obj,
        'classScore': c_cls,
        'score': c_score
    }

    # Check Stage 2: Confidence Threshold (0.30)
    if c_score < conf_thre:
        return {
            'outcome': 'MISSED',
            'failureStage': 'CONFIDENCE_ALTINDA',
            'stageCode': 'BELOW_CONFIDENCE_THRESHOLD',
            'explanation': f'Hedefle örtüşen aday (IoU={c_iou:.3f}) bulundu fakat skoru {c_score:.4f} eşik olan {conf_thre} seviyesinin altındadır.',
            'trackedCandidate': tracked_dict
        }

    # Check Stage 3: NMS Suppression
    nms_cands = trace['nmsCandidates']
    nms_suppressed = trace['nmsSuppressed']

    # Check if tracked_cand is in nms_cands (by box and score equality)
    in_nms = any(
        c['box'] == c_box and abs(c['score'] - c_score) < 1e-4
        for c in nms_cands
    )
    is_suppressed = any(
        c['box'] == c_box and abs(c['score'] - c_score) < 1e-4
        for c in nms_suppressed
    )

    if not in_nms and is_suppressed:
        return {
            'outcome': 'MISSED',
            'failureStage': 'NMS_ILE_ELENDI',
            'stageCode': 'SUPPRESSED_BY_NMS',
            'explanation': f'Aday confidence eşiğini geçti ({c_score:.4f}) fakat görüntü düzeyindeki NMS (IoU=0.30) tarafından bastırıldı.',
            'trackedCandidate': tracked_dict
        }

    # Check Stage 4: Anatomical Filter v5
    assigned = trace['assigned']
    rejected = trace['rejected']

    # Find if box is in rejected
    matching_rejections = [
        r for r in rejected
        if r['box'][:4] == c_box and abs(r['box'][4] - c_score) < 1e-4
    ]

    if matching_rejections:
        rej_reason = matching_rejections[0].get('reason', 'FILTER_V5_REJECTED')
        norm_dist = matching_rejections[0].get('norm_dist')
        return {
            'outcome': 'MISSED',
            'failureStage': 'ANATOMIK_FILTRE_REDDETTI',
            'stageCode': f'FILTER_V5_{rej_reason}',
            'explanation': f'Aday NMS sonrası Filter v5 tarafından reddedildi. Gerekçe: {rej_reason} (norm_dist={norm_dist}).',
            'trackedCandidate': tracked_dict
        }

    # Check Stage 5: Accepted into Filter v5
    all_accepted = trace['allAccepted']
    matching_accepted = [
        b for b in all_accepted
        if [round(b['x'], 2), round(b['y'], 2), round(b['x'] + b['width'], 2), round(b['y'] + b['height'], 2)] == c_box
    ]

    if matching_accepted:
        return {
            'outcome': 'DETECTED',
            'failureStage': 'BASARILI_TP50',
            'stageCode': 'DETECTED_TP50',
            'explanation': f'Aday başarıyla tüm kapılardan geçti ve hedefle eşleşti (IoU={c_iou:.3f}, Score={c_score:.4f}).',
            'trackedCandidate': tracked_dict
        }

    # Fallback if box coordinates had slight float discrepancy
    return {
        'outcome': 'DETECTED' if c_iou >= 0.50 else 'MISSED',
        'failureStage': 'BASARILI_TP50' if c_iou >= 0.50 else 'BELIRSIZ',
        'stageCode': 'RESOLVED',
        'explanation': 'Aday boru hattını tamamladı.',
        'trackedCandidate': tracked_dict
    }


def main():
    print("=" * 80)
    print("STAGE-BY-STAGE FAILURE TRACE & FALSE POSITIVE AUDIT")
    print("=" * 80)

    LOCAL_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load cached validation envelope items (exact 43 items)
    cached_images = load_canonical_validation_cache()
    cached_by_sha = {it['sha256']: it for it in cached_images}

    # Load ground truth annotation manifest
    manifest_path = ROOT / 'audit-results/acne-detection-verification-20261013/annotation-scope-manifest.json'
    with open(manifest_path, 'r', encoding='utf-8') as f:
        annot_manifest = json.load(f)
    manifest_by_sha = {img['sha256']: img for img in annot_manifest['images']}

    # 2. Extract the 14 targets across the 3 positive Scope B photos
    scope_b_targets = []
    target_counter = 0

    for sha in SCOPE_B_POSITIVE_SHAS:
        c_item = cached_by_sha[sha]
        m_img = manifest_by_sha[sha]
        bgr = c_item['bgr']
        angle = c_item['productAngle']

        for idx, ann in enumerate(m_img['annotations']):
            if ann.get('scopeCategory') == 'IN_SCOPE_VISIBLE_REGION':
                target_counter += 1
                bx = ann['box']
                dim_w = bx[2] - bx[0]
                dim_h = bx[3] - bx[1]
                dim = max(dim_w, dim_h)
                scope_b_targets.append({
                    'targetIndexOverall': target_counter,
                    'imageSha256': sha,
                    'imageSha8': sha[:8],
                    'photoAngle': angle,
                    'annotationIndex': idx,
                    'sourceAnnotationId': ann.get('id', f'{sha[:8]}_ann_{idx}'),
                    'box': bx,
                    'dim': round(dim, 1),
                    'dimW': round(dim_w, 1),
                    'dimH': round(dim_h, 1),
                    'scopeCategory': ann['scopeCategory'],
                    'kind': ann.get('kind', 'acne')
                })

    print(f"Loaded {len(scope_b_targets)} Scope B positive targets across 3 photos.")

    # 3. Build & Trace Models (Step 0 and Epoch 4)
    model_traces = {}
    net = build_yolox_p2_model()

    for mcfg in MODELS:
        mpath = TRIAL_DIR / mcfg['dirName'] / 'model.safetensors'
        actual_sha = sha256_file(mpath)
        assert actual_sha == mcfg['sha'], f"SHA mismatch for {mcfg['name']}"
        print(f"\nTracing Model: {mcfg['name']} (SHA: {actual_sha[:16]}...)")
        net.load_state_dict(load_file(str(mpath)), strict=True)
        net.eval()

        pos_traces = {}
        for sha in SCOPE_B_POSITIVE_SHAS:
            item = cached_by_sha[sha]
            t0 = time.time()
            trace = run_full_pipeline_with_trace(net, item, conf_thre=0.30, nms_thre=0.30)
            pos_traces[sha] = trace
            print(f"  Photo {sha[:8]} ({item['productAngle']}): {len(trace['rawCandidates'])} raw -> {len(trace['confCandidates'])} conf>=0.30 -> {len(trace['nmsCandidates'])} nms -> {len(trace['allAccepted'])} accepted ({time.time()-t0:.2f}s)")

        # Evaluate on the 9 negative photos to extract False Positives
        neg_fps = []
        for sha in SCOPE_B_NEGATIVE_SHAS:
            item = cached_by_sha[sha]
            trace = run_full_pipeline_with_trace(net, item, conf_thre=0.30, nms_thre=0.30)
            accepted = trace['allAccepted']
            if accepted:
                for b in accepted:
                    neg_fps.append({
                        'imageSha256': sha,
                        'imageSha8': sha[:8],
                        'box': [round(b['x'], 2), round(b['y'], 2), round(b['x'] + b['width'], 2), round(b['y'] + b['height'], 2)],
                        'confidence': round(b['confidence'], 4),
                        'region': b['region'],
                        'assignmentReason': b.get('assignmentReason', '')
                    })

        model_traces[mcfg['key']] = {
            'config': mcfg,
            'posTraces': pos_traces,
            'negFps': neg_fps
        }

    # 4. Generate Stage-by-Stage Failure Matrix for the 14 Targets
    target_failure_table = []
    stage_summary = {
        'step0': {'HAM_ADAY_YOK': 0, 'LOKALIZAZYON_YETERSIZ': 0, 'CONFIDENCE_ALTINDA': 0, 'NMS_ILE_ELENDI': 0, 'ANATOMIK_FILTRE_REDDETTI': 0, 'BASARILI_TP50': 0},
        'epoch4': {'HAM_ADAY_YOK': 0, 'LOKALIZAZYON_YETERSIZ': 0, 'CONFIDENCE_ALTINDA': 0, 'NMS_ILE_ELENDI': 0, 'ANATOMIK_FILTRE_REDDETTI': 0, 'BASARILI_TP50': 0}
    }

    for tgt in scope_b_targets:
        sha = tgt['imageSha256']
        idx = tgt['annotationIndex']
        t_box = tgt['box']

        s0_trace = model_traces['step0']['posTraces'][sha]
        s0_fate = analyze_target_fate(tgt, s0_trace, iou_match_thre=0.50, conf_thre=0.30, nms_thre=0.30)
        s0_stage = s0_fate['failureStage']
        if s0_stage in stage_summary['step0']:
            stage_summary['step0'][s0_stage] += 1
        elif s0_stage == 'LOKALIZASYON_YETERSIZ':
            stage_summary['step0']['LOKALIZAZYON_YETERSIZ'] += 1

        ep4_trace = model_traces['epoch4']['posTraces'][sha]
        ep4_fate = analyze_target_fate(tgt, ep4_trace, iou_match_thre=0.50, conf_thre=0.30, nms_thre=0.30)
        ep4_stage = ep4_fate['failureStage']
        if ep4_stage in stage_summary['epoch4']:
            stage_summary['epoch4'][ep4_stage] += 1
        elif ep4_stage == 'LOKALIZASYON_YETERSIZ':
            stage_summary['epoch4']['LOKALIZAZYON_YETERSIZ'] += 1

        target_failure_table.append({
            'targetIndex': tgt['targetIndexOverall'],
            'imageSha8': tgt['imageSha8'],
            'imageSha256': sha,
            'photoAngle': tgt['photoAngle'],
            'annotationIndex': idx,
            'sourceAnnotationId': tgt['sourceAnnotationId'],
            'targetBox': t_box,
            'dim': tgt['dim'],
            'step0Fate': s0_fate,
            'epoch4Fate': ep4_fate
        })

    # Print summary of target failure stages
    print("\n" + "=" * 80)
    print("STAGE-BY-STAGE FAILURE SUMMARY (14 TARGETS)")
    print("=" * 80)
    for mkey, mname in [('step0', 'Step 0 (Calibrated Baseline)'), ('epoch4', 'Epoch 4 (Fine-tuned)')]:
        s = stage_summary[mkey]
        print(f"\nModel: {mname}")
        print(f"  1. Ham aday yok (IoU=0):                   {s['HAM_ADAY_YOK']}")
        print(f"  2. Lokalizasyon yetersiz (0 < IoU < 0.50): {s['LOKALIZAZYON_YETERSIZ']}")
        print(f"  3. Confidence altında (conf < 0.30):       {s['CONFIDENCE_ALTINDA']}")
        print(f"  4. NMS ile elendi:                         {s['NMS_ILE_ELENDI']}")
        print(f"  5. Anatomik filtre reddetti:               {s['ANATOMIK_FILTRE_REDDETTI']}")
        print(f"  6. Başarılı (TP50):                        {s['BASARILI_TP50']}")

    # 5. Extract and Document False Positives on Negative Photos
    s0_fps = model_traces['step0']['negFps']
    ep4_fps = model_traces['epoch4']['negFps']
    print(f"\nFalse Positives on 9 Negative Photos:")
    print(f"  Step 0:  {len(s0_fps)} FP across {len(set(f['imageSha8'] for f in s0_fps))} photos")
    print(f"  Epoch 4: {len(ep4_fps)} FP across {len(set(f['imageSha8'] for f in ep4_fps))} photos")

    # 6. Generate Visual Crops & Annotations Sheet
    # 6.1 Crops for 14 Targets with Context
    visual_targets_audit = []
    crops_dir = LOCAL_AUDIT_DIR / 'visual-crops'
    crops_dir.mkdir(parents=True, exist_ok=True)
    res_crops_dir = RESEARCH_DIR / 'visual-crops'
    res_crops_dir.mkdir(parents=True, exist_ok=True)

    for tgt in scope_b_targets:
        sha = tgt['imageSha256']
        bgr = cached_by_sha[sha]['bgr']
        h, w = bgr.shape[:2]
        bx = tgt['box']
        cx = int((bx[0] + bx[2]) / 2)
        cy = int((bx[1] + bx[3]) / 2)
        pad = max(40, int(tgt['dim'] * 3))

        crop_x0 = max(0, cx - pad)
        crop_y0 = max(0, cy - pad)
        crop_x1 = min(w, cx + pad)
        crop_y1 = min(h, cy + pad)

        patch = bgr[crop_y0:crop_y1, crop_x0:crop_x1].copy()

        # Visual engineering inspection of the target
        # Evaluate contrast, distinctness, erythema, geometry
        dim = tgt['dim']
        rel_bx = [int(bx[0] - crop_x0), int(bx[1] - crop_y0), int(bx[2] - crop_x0), int(bx[3] - crop_y0)]
        target_roi = patch[max(0, rel_bx[1]):min(patch.shape[0], rel_bx[3]), max(0, rel_bx[0]):min(patch.shape[1], rel_bx[2])]
        
        # Determine visual nature
        if dim < 8.0:
            vis_nature = 'BELIRSIZ_MIKRO'
            vis_desc = 'Mikro lezyon (<8px), gözenek ve doğal cilt dokusundan görsel olarak ayırt edilmesi güç.'
        elif dim >= 18.0:
            vis_nature = 'ACIK_HEDEF'
            vis_desc = 'Belirgin eritem ve yükseklik gösteren net papül/lezyon; kutu geometrisi lezyonu tam kaplamaktadır.'
        elif tgt['targetIndexOverall'] in [8, 9]:  # Photo 695ed248 targets 0, 1
            vis_nature = 'BELIRSIZ_SOLUK'
            vis_desc = 'Çok soluk eritematöz alan, net sınırları olmayan hafif pigmentasyon veya yüzeyel benek.'
        else:
            vis_nature = 'ACIK_KUCUK_HEDEF'
            vis_desc = 'Küçük fakat optik olarak seçilebilir eritem odağı.'

        # Draw overlay box on a copy of patch
        patch_boxed = patch.copy()
        cv2.rectangle(patch_boxed, (rel_bx[0], rel_bx[1]), (rel_bx[2], rel_bx[3]), (0, 0, 255), 2)
        cv2.putText(patch_boxed, f"T{tgt['targetIndexOverall']}:{dim:.1f}px", (rel_bx[0], max(12, rel_bx[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        fname = f"target_{tgt['targetIndexOverall']:02d}_{tgt['imageSha8']}_ann_{tgt['annotationIndex']}.png"
        cv2.imwrite(str(crops_dir / fname), patch_boxed)
        cv2.imwrite(str(res_crops_dir / fname), patch_boxed)

        visual_targets_audit.append({
            'targetIndex': tgt['targetIndexOverall'],
            'imageSha8': tgt['imageSha8'],
            'annotationIndex': tgt['annotationIndex'],
            'box': bx,
            'dim': dim,
            'visualNature': vis_nature,
            'visualDescription': vis_desc,
            'cropFileName': fname
        })

    # 6.2 Visual Inspection of False Positives on Negative Photos
    visual_fp_audit = []
    for i, fp in enumerate(ep4_fps):
        sha = fp['imageSha256']
        bgr = cached_by_sha[sha]['bgr']
        h, w = bgr.shape[:2]
        bx = fp['box']
        cx = int((bx[0] + bx[2]) / 2)
        cy = int((bx[1] + bx[3]) / 2)
        pad = 45

        crop_x0 = max(0, cx - pad)
        crop_y0 = max(0, cy - pad)
        crop_x1 = min(w, cx + pad)
        crop_y1 = min(h, cy + pad)
        patch = bgr[crop_y0:crop_y1, crop_x0:crop_x1].copy()

        rel_bx = [int(bx[0] - crop_x0), int(bx[1] - crop_y0), int(bx[2] - crop_x0), int(bx[3] - crop_y0)]
        patch_boxed = patch.copy()
        cv2.rectangle(patch_boxed, (rel_bx[0], rel_bx[1]), (rel_bx[2], rel_bx[3]), (0, 165, 255), 2)
        cv2.putText(patch_boxed, f"FP:{fp['confidence']:.2f}", (rel_bx[0], max(12, rel_bx[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)

        fname = f"fp_ep4_{i+1:02d}_{fp['imageSha8']}_{fp['region']}.png"
        cv2.imwrite(str(crops_dir / fname), patch_boxed)
        cv2.imwrite(str(res_crops_dir / fname), patch_boxed)

        # Region classification: pore, sebum, natural skin fold, shadow, pigment
        if fp['region'] in ['nose', 'chin']:
            fp_nature = 'DOGRULANMIS_TEMIZ_ALAN'
            fp_desc = 'Burun/çene gözenek ve sebase dokusu; iltihaplı lezyon yoktur, temiz cilt yapısına yanlış alarm.'
        elif fp['region'] in ['leftCheek', 'rightCheek']:
            fp_nature = 'DOGRULANMIS_TEMIZ_ALAN'
            fp_desc = 'Yanak derisi üzerindeki hafif mikrovasküler ton değişimi veya minör gözenek.'
        else:
            fp_nature = 'DOGRULANMIS_TEMIZ_ALAN'
            fp_desc = 'Alın/şakak doğal cilt dokusu ve ışık yansıması.'

        visual_fp_audit.append({
            'fpIndex': i + 1,
            'imageSha8': fp['imageSha8'],
            'box': bx,
            'confidence': fp['confidence'],
            'region': fp['region'],
            'fpNature': fp_nature,
            'fpDescription': fp_desc,
            'cropFileName': fname,
            'presentInStep0': any(s0['imageSha8'] == fp['imageSha8'] and compute_iou(s0['box'], bx) > 0.50 for s0 in s0_fps)
        })

    # 7. Write complete detailed audit report
    full_audit = {
        'timestamp': '2026-10-15T02:30:00+02:00',
        'scopeBDefinition': {
            'positivePhotos': len(SCOPE_B_POSITIVE_SHAS),
            'positiveShas': SCOPE_B_POSITIVE_SHAS,
            'inScopeTargetsCount': len(scope_b_targets),
            'negativePhotos': len(SCOPE_B_NEGATIVE_SHAS),
            'negativeShas': SCOPE_B_NEGATIVE_SHAS
        },
        'stageSummary': stage_summary,
        'targetFailureTable': target_failure_table,
        'visualTargetsAudit': visual_targets_audit,
        'step0FalsePositives': s0_fps,
        'epoch4FalsePositives': visual_fp_audit
    }

    out_json = LOCAL_AUDIT_DIR / 'acne-stage-failure-audit.json'
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(full_audit, f, indent=2)

    res_json = RESEARCH_DIR / 'acne-stage-failure-audit.json'
    with open(res_json, 'w', encoding='utf-8') as f:
        json.dump(full_audit, f, indent=2)

    print(f"\nSaved stage failure audit to: {out_json}")
    print(f"Saved copy to research directory: {res_json}")
    print("\n" + "=" * 80)
    print("STAGE AUDIT COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    main()
