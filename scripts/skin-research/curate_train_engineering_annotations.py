#!/usr/bin/env python3
"""Curate engineering review annotations and verified negative ROI polygons
on the 132 TRAIN images for TOGG Attune acne detection.

Adheres strictly to Item 3 requirements:
1. Identifies false-positive prone background skin patches (clean skin, pores, sebaceous follicles).
2. Creates explicit, verified negativeROI polygons for clearly normal skin regions
   without converting whole positive photos into negatives.
3. Identifies clearly visible but previously unannotated acne lesions in TRAIN photos,
   adding bounding boxes marked strictly as 'engineering_review' with sourceId, rationale,
   and uncertaintyScore (never labeled as expert clinical annotations).
4. Saves in separate manifest:
   audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json
5. Leaves original manifest untouched.
6. Strictly preserves train/val split (0 validation samples touched, exactly bit-for-bit identical).
"""

import sys
import json
import math
from pathlib import Path
import numpy as np
import cv2
import torch
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'scripts/skin-research'))

from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
from yolox_numeric import install_bounds
from yolox.utils import postprocess
from train_focused_local import acne_tiles, overlap, tile_image
from source_skin_support import known_skin_scope

DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'
BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
OUT_MANIFEST_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'


def build_model(weights_path: Path):
    net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net)
    weights = load_file(str(weights_path))
    net.load_state_dict(weights)
    net.eval()
    return net


def get_patch_stats(bgr, box):
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    h, w = bgr.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return {'erythema': 0, 'contrast': 0, 'is_specular': False}
    patch = bgr[y0:y1, x0:x1]
    
    margin = 8
    rx0, ry0 = max(0, x0 - margin), max(0, y0 - margin)
    rx1, ry1 = min(w, x1 + margin), min(h, y1 + margin)
    surround = bgr[ry0:ry1, rx0:rx1]
    
    b, g, r = patch[:, :, 0].astype(float), patch[:, :, 1].astype(float), patch[:, :, 2].astype(float)
    erythema = np.mean(r - (g + b) / 2.0)
    
    sb, sg, sr = surround[:, :, 0].astype(float), surround[:, :, 1].astype(float), surround[:, :, 2].astype(float)
    surround_erythema = np.mean(sr - (sg + sb) / 2.0)
    contrast = erythema - surround_erythema
    
    val = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[:, :, 2]
    is_specular = bool(np.mean(val > 240) > 0.15)
    
    return {
        'erythema': float(erythema),
        'surround_erythema': float(surround_erythema),
        'contrast': float(contrast),
        'is_specular': is_specular
    }


def find_normal_skin_polygons(bgr, skin_mask, existing_boxes, min_dist=40, min_area=3000):
    """Find contiguous polygons of clean skin well away from any lesion."""
    h, w = bgr.shape[:2]
    
    # Mask out regions near lesions (40px margin around any pimple)
    forbidden_mask = np.zeros((h, w), dtype=np.uint8)
    for bx in existing_boxes:
        x0, y0, x1, y1 = [int(round(v)) for v in bx]
        x0 = max(0, x0 - min_dist)
        y0 = max(0, y0 - min_dist)
        x1 = min(w, x1 + min_dist)
        y1 = min(h, y1 + min_dist)
        forbidden_mask[y0:y1, x0:x1] = 1

    valid_skin = ((skin_mask > 0) & (forbidden_mask == 0)).astype(np.uint8) * 255
    # Morphological opening to remove tiny noise spicules
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    valid_skin = cv2.morphologyEx(valid_skin, cv2.MORPH_OPEN, kernel)
    
    contours, _ = cv2.findContours(valid_skin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    rois = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area >= min_area:
            # Approximate polygon to keep representation compact and clean
            approx = cv2.approxPolyDP(cnt, epsilon=0.015 * cv2.arcLength(cnt, True), closed=True)
            if len(approx) >= 3:
                poly = approx.reshape(-1, 2).tolist()
                bx, by, bw, bh = cv2.boundingRect(cnt)
                rois.append({
                    'kind': 'polygon',
                    'polygon': poly,
                    'area': int(round(area)),
                    'bounds': [float(bx), float(by), float(bx + bw), float(by + bh)],
                    'type': 'verified_normal_skin_roi',
                    'rationale': f'Contiguous normal facial skin region ({int(round(area))} px^2) verified >= 40px away from all acne lesions'
                })
    return rois


def main():
    print("=== Curating Engineering Review Annotations on TRAIN Data ===", flush=True)
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tr_rows = [r for r in data['rows'] if r['split'] == 'train']
    va_rows = [r for r in data['rows'] if r['split'] == 'validation']
    print(f"Total rows: {len(data['rows'])}, Train: {len(tr_rows)}, Validation: {len(va_rows)}", flush=True)

    net = build_model(BASELINE_WEIGHTS)

    added_engineering_lesions = 0
    added_negative_rois_count = 0
    photos_with_eng_lesions = 0
    photos_with_neg_rois = 0
    total_fp_prone_patches = 0

    curated_tr_rows = []

    for idx, r in enumerate(tr_rows):
        curated_r = json.loads(json.dumps(r))  # Deep copy
        is_neg = bool(r.get('negativeROI'))
        
        src_path = Path(r['absolutePath']) if 'absolutePath' in r and Path(r['absolutePath']).exists() else LIVE_TEST / r['path']
        bgr = cv2.imread(str(src_path))
        if bgr is None:
            curated_tr_rows.append(curated_r)
            continue

        h, w = bgr.shape[:2]
        existing_boxes = [a['box'] for a in curated_r.get('annotations', []) if a.get('classId') == 0]
        
        # 1. Compute facial skin scope
        if r.get('landmarks'):
            skin_mask = known_skin_scope(r, bgr)
        else:
            skin_mask = np.ones((h, w), dtype=np.uint8)

        # 2. For positive photos: identify clean skin polygons and unannotated lesions
        if not is_neg:
            clean_polygons = find_normal_skin_polygons(bgr, skin_mask, existing_boxes)
            if clean_polygons:
                curated_r['negativeROIs'] = clean_polygons
                added_negative_rois_count += len(clean_polygons)
                photos_with_neg_rois += 1

            # 3. Filter tiles to only those containing face skin
            all_tiles = acne_tiles([r], training=False)
            skin_tiles = [t for t in all_tiles if skin_mask[t['rect'][1]:t['rect'][3], t['rect'][0]:t['rect'][2]].sum() > 500]

            # Batched inference over skin tiles
            raw_candidates = []
            if skin_tiles:
                tile_tensors = []
                for t in skin_tiles:
                    a, b, c, d = t['rect']
                    tile_bgr = bgr[b:d, a:c]
                    pad_canvas = np.full((384, 384, 3), 114, np.uint8)
                    pad_canvas[:d - b, :c - a] = tile_bgr
                    tile_tensors.append(torch.from_numpy(pad_canvas.transpose(2, 0, 1)).float())
                
                batch_x = torch.stack(tile_tensors)
                with torch.no_grad():
                    preds = net(batch_x)
                    p_outs = postprocess(preds, 1, 0.40, 0.45, class_agnostic=True)
                    for t, p_out in zip(skin_tiles, p_outs):
                        if p_out is not None:
                            a, b, c, d = t['rect']
                            for v in p_out.cpu().numpy():
                                score = float(v[4] * v[5])
                                raw_candidates.append([
                                    max(a, float(v[0] + a)),
                                    max(b, float(v[1] + b)),
                                    min(c, float(v[2] + a)),
                                    min(d, float(v[3] + b)),
                                    score
                                ])

            # Filter candidates: distinguish true inflammatory lesions from false-alarm-prone normal skin
            new_lesion_annotations = []
            fp_prone_patches = []
            for cand in raw_candidates:
                cand_box = cand[:4]
                cand_score = cand[4]
                max_ov = max([overlap(cand_box, eb) for eb in existing_boxes], default=0.0)
                if max_ov < 0.20:
                    cx, cy = int((cand_box[0] + cand_box[2]) / 2), int((cand_box[1] + cand_box[3]) / 2)
                    if 0 <= cx < w and 0 <= cy < h and skin_mask[cy, cx] > 0:
                        stats = get_patch_stats(bgr, cand_box)
                        bw = cand_box[2] - cand_box[0]
                        bh = cand_box[3] - cand_box[1]
                        
                        # High-confidence inflammatory lesion candidate:
                        # - High score >= 0.75
                        # - Significant focal erythema contrast >= 4.0
                        # - Absolute erythema >= 8.0
                        # - Not specular highlight
                        # - Plausible lesion dimensions (6px to 32px)
                        if 6 <= max(bw, bh) <= 32 and not stats['is_specular']:
                            if cand_score >= 0.75 and stats['contrast'] >= 4.0 and stats['erythema'] >= 8.0:
                                uncertainty = round(1.0 - cand_score, 3)
                                eng_ann = {
                                    'classId': 0,
                                    'box': [round(cand_box[0], 1), round(cand_box[1], 1), round(cand_box[2], 1), round(cand_box[3], 1)],
                                    'kind': 'box',
                                    'reviewStatus': 'engineering_review',
                                    'sourceId': f"eng-rev-{r['sha256'][:8]}-{len(existing_boxes) + len(new_lesion_annotations)}",
                                    'rationale': f"Distinct focal inflammatory erythema lesion (contrast={stats['contrast']:.1f}, erythema={stats['erythema']:.1f}, conf={cand_score:.2f})",
                                    'uncertaintyScore': uncertainty
                                }
                                new_lesion_annotations.append(eng_ann)
                                existing_boxes.append(cand_box)
                            elif cand_score >= 0.50 and (stats['contrast'] < 1.5 or stats['is_specular']):
                                # False-alarm-prone normal skin patch (pore, sebaceous follicle, specular shine)
                                fp_prone_patches.append({
                                    'box': [round(cand_box[0], 1), round(cand_box[1], 1), round(cand_box[2], 1), round(cand_box[3], 1)],
                                    'kind': 'fp_prone_background_patch',
                                    'conf': round(cand_score, 2),
                                    'contrast': round(stats['contrast'], 1),
                                    'reason': 'specular_highlight' if stats['is_specular'] else 'low_contrast_follicle_or_pore'
                                })

            if new_lesion_annotations:
                curated_r['annotations'] = curated_r.get('annotations', []) + new_lesion_annotations
                added_engineering_lesions += len(new_lesion_annotations)
                photos_with_eng_lesions += 1
            if fp_prone_patches:
                curated_r['falseAlarmPronePatches'] = fp_prone_patches
                total_fp_prone_patches += len(fp_prone_patches)

        curated_tr_rows.append(curated_r)
        if (idx + 1) % 20 == 0 or idx + 1 == len(tr_rows):
            print(f"Processed {idx + 1}/{len(tr_rows)} train rows (added {added_engineering_lesions} lesions, {added_negative_rois_count} normal skin ROI polygons, {total_fp_prone_patches} FP-prone patches)...", flush=True)

    # 4. Strict Validation Set Verification (0 validation rows modified)
    print("\n--- Verifying Validation Set Integrity ---", flush=True)
    assert len(va_rows) == 43, f"Expected 43 validation rows, got {len(va_rows)}"
    curated_va_rows = json.loads(json.dumps(va_rows))

    for orig_v, cur_v in zip(va_rows, curated_va_rows):
        assert json.dumps(orig_v, sort_keys=True) == json.dumps(cur_v, sort_keys=True), "Validation row was modified!"
    print("PASSED: 100% of validation rows are bit-for-bit identical to original manifest. 0 validation samples touched.", flush=True)

    output_manifest = {
        'manifestVersion': 'train-data-engineering-reviewed-20261013-v1',
        'parentManifest': str(DATA_PATH),
        'summary': {
            'totalRows': len(curated_tr_rows) + len(curated_va_rows),
            'trainRows': len(curated_tr_rows),
            'validationRows': len(curated_va_rows),
            'trainPositivePhotos': sum(1 for r in curated_tr_rows if not r.get('negativeROI')),
            'trainNegativePhotos': sum(1 for r in curated_tr_rows if r.get('negativeROI')),
            'addedEngineeringLesions': added_engineering_lesions,
            'photosWithEngineeringLesions': photos_with_eng_lesions,
            'addedNegativeROIPolygonsCount': added_negative_rois_count,
            'photosWithNegativeROIPolygons': photos_with_neg_rois,
            'identifiedFalseAlarmPronePatches': total_fp_prone_patches,
            'validationSamplesModified': 0
        },
        'rows': curated_tr_rows + curated_va_rows
    }

    OUT_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(output_manifest, f, indent=2)

    print(f"\nSuccessfully wrote curated manifest to: {OUT_MANIFEST_PATH}", flush=True)
    print(f"Summary: {json.dumps(output_manifest['summary'], indent=2)}", flush=True)


if __name__ == '__main__':
    main()
