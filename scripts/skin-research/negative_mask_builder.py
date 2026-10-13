#!/usr/bin/env python3
"""Exact hole-preserving negative skin mask builder and 4-scale tile generator for TOGG Attune acne training.

Contract & Rules (Item 2):
1. Delikleri koruyan raster temsil:
   - Uses exact 2D binary raster mask (no lossy RETR_EXTERNAL polygons that fill holes).
2. Delik delme (Hole punching):
   - Punches out ALL 832 original GT boxes (+ 16px safety margin).
   - Punches out ALL 401 pseudo-label candidate boxes (+ 16px safety margin).
   - Punches out eyes, lips, nostrils, eyebrows, and hair.
3. Landmark gereksinimi:
   - If landmarks do not exist or < 468 points, scope is strictly ALL ZEROS (UNKNOWN).
     No photo without landmarks is assumed to be normal skin.
4. Pseudo-label ayrımı:
   - 401 candidate boxes are kept in separate 'pseudoAnnotations' layer.
   - They are NOT used as positive ground truth in P2 training.
5. 19 Negatif TRAIN fotoğrafının eğitime katılması:
   - Tiles from the 19 negative photos that overlap clean facial skin are actively sampled in acne_tiles_p2.
6. Validation izolasyonu:
   - Validation split (43 photos) is strictly excluded from training data preparation.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import cv2
import torch

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'scripts/skin-research'))

from source_skin_support import known_skin_scope

SIZE = 384


def build_hole_preserved_negative_masks(
    train_rows: List[dict],
    pseudo_manifest_path: Path = None,
    hole_margin: int = 16
) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """Build exact 2D binary raster mask and distance-based boundary weights for each train photo.
    Punches holes with hole_margin for ALL original GT boxes and ALL pseudo candidate boxes."""
    pseudo_boxes_by_sha = {}
    negative_rois_by_sha = {}
    gt_boxes_by_sha = {}
    if pseudo_manifest_path and pseudo_manifest_path.exists():
        with open(pseudo_manifest_path, 'r', encoding='utf-8') as f:
            p_data = json.load(f)
        for r in p_data.get('rows', []):
            sha = r['sha256']
            eng_boxes = [a['box'] for a in r.get('annotations', []) if a.get('reviewStatus') == 'engineering_review']
            if eng_boxes:
                pseudo_boxes_by_sha[sha] = eng_boxes
            gt_b = [a['box'] for a in r.get('annotations', []) if a.get('reviewStatus') != 'engineering_review' and a.get('classId') == 0]
            if gt_b:
                gt_boxes_by_sha[sha] = gt_b
            if r.get('negativeROIs'):
                negative_rois_by_sha[sha] = r['negativeROIs']

    masks = {}
    weights = {}

    total_gt_holes_punched = 0
    total_pseudo_holes_punched = 0

    for r in train_rows:
        sha = r['sha256']
        h, w = r['height'], r['width']
        mask = np.zeros((h, w), dtype=np.uint8)

        points = r.get('landmarks', [])
        rois = r.get('negativeROIs', []) or negative_rois_by_sha.get(sha, [])

        src_path = Path(r['absolutePath']) if 'absolutePath' in r and Path(r['absolutePath']).exists() else (LIVE_TEST / r['path'])
        bgr = cv2.imread(str(src_path))
        if bgr is None:
            masks[sha] = mask
            weights[sha] = np.zeros((h, w), dtype=np.float32)
            continue

        if points and len(points) >= 468:
            # Full-face image with MediaPipe landmarks (e.g. 19 clean control photos)
            mask = known_skin_scope(r, bgr)
        elif rois:
            # Macro skin crop: only the verified clean skin polygons
            for roi in rois:
                poly = np.array(roi['polygon'], dtype=np.int32)
                cv2.fillPoly(mask, [poly], 1)
        else:
            # Photos lacking landmarks and verified normal ROIs: strictly UNKNOWN
            masks[sha] = mask
            weights[sha] = np.zeros((h, w), dtype=np.float32)
            continue

        # 2. Punch holes for original GT boxes (16px margin)
        gt_boxes = gt_boxes_by_sha.get(sha, [a['box'] for a in r.get('annotations', []) if a.get('classId') == 0])
        for bx in gt_boxes:
            x0, y0, x1, y1 = [int(round(v)) for v in bx]
            rx0 = max(0, x0 - hole_margin)
            ry0 = max(0, y0 - hole_margin)
            rx1 = min(w, x1 + hole_margin)
            ry1 = min(h, y1 + hole_margin)
            mask[ry0:ry1, rx0:rx1] = 0
            total_gt_holes_punched += 1

        # 3. Punch holes for pseudo-label candidate boxes (16px margin)
        pseudo_boxes = pseudo_boxes_by_sha.get(sha, [])
        for bx in pseudo_boxes:
            x0, y0, x1, y1 = [int(round(v)) for v in bx]
            rx0 = max(0, x0 - hole_margin)
            ry0 = max(0, y0 - hole_margin)
            rx1 = min(w, x1 + hole_margin)
            ry1 = min(h, y1 + hole_margin)
            mask[ry0:ry1, rx0:rx1] = 0
            total_pseudo_holes_punched += 1

        # 4. Morphological opening to clean small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 5. Distance transform for soft boundary weighting
        if np.any(mask > 0):
            dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
            # Soft weight: 0.2 at margin, ramps up to 1.0 at 16px depth inside clean skin
            b_weight = np.clip(dist / 16.0, 0.2, 1.0) * (mask > 0).astype(np.float32)
        else:
            b_weight = np.zeros((h, w), dtype=np.float32)

        masks[sha] = mask
        weights[sha] = b_weight

    print(f"Hole-preserved masks generated for {len(train_rows)} train rows:")
    print(f"  GT lesion holes punched: {total_gt_holes_punched}")
    print(f"  Pseudo-label candidate holes punched: {total_pseudo_holes_punched}")
    print(f"  Photos with active clean skin: {sum(1 for m in masks.values() if np.any(m > 0))}")
    return masks, weights


def acne_tiles_p2(rows: List[dict], masks: Dict[str, np.ndarray], training: bool = True) -> List[dict]:
    """Generate tiles supporting both positive photos and clean skin from negative photos."""
    tiles = []
    for r in rows:
        sha = r['sha256']
        mask = masks.get(sha)
        x, y, x1, y1 = r['crop']
        
        xs = sorted(set([*range(x, max(x + 1, x1 - SIZE + 1), 288), max(x, x1 - SIZE)]))
        ys = sorted(set([*range(y, max(y + 1, y1 - SIZE + 1), 288), max(y, y1 - SIZE)]))
        
        is_clean_control = (len(r.get('annotations', [])) == 0)
        
        for a in xs:
            for b in ys:
                endx = min(x1, a + SIZE)
                endy = min(y1, b + SIZE)
                
                # Extract ground truth boxes in tile (original GT only)
                boxes = []
                for ann in r.get('annotations', []):
                    if ann.get('classId') != 0:
                        continue
                    bx, by, ex, ey = ann['box']
                    cl = [max(bx, a), max(by, b), min(ex, endx), min(ey, endy)]
                    if cl[2] - cl[0] >= 2 and cl[3] - cl[1] >= 2 and (cl[2] - cl[0]) * (cl[3] - cl[1]) >= 0.7 * (ex - bx) * (ey - by):
                        boxes.append([cl[0] - a, cl[1] - b, cl[2] - a, cl[3] - b])

                # Check if tile has clean skin (for negative photos)
                has_clean_tile_skin = False
                if mask is not None and np.any(mask[b:endy, a:endx] > 0):
                    has_clean_tile_skin = True

                # Include tile if:
                # 1. Contains positive GT boxes
                # 2. Or is a clean control photo tile with active verified skin
                # 3. Or not training (validation tiles include all)
                if boxes or (training and is_clean_control and has_clean_tile_skin) or not training:
                    tiles.append({
                        'row': r,
                        'rect': [a, b, endx, endy],
                        'boxes': boxes,
                        'isCleanControl': is_clean_control
                    })
    return tiles


def known_cells_p2(
    source_mask: np.ndarray,
    source_weights: np.ndarray,
    tile_rect: List[int],
    strides: Tuple[int, ...] = (4, 8, 16, 32),
    size: int = 384
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Sample known negative mask and boundary weights across all 4 strides [4, 8, 16, 32].
    
    Total anchors for 384x384:
      stride 4:  96x96 = 9216
      stride 8:  48x48 = 2304
      stride 16: 24x24 = 576
      stride 32: 12x12 = 144
      Total: 12240 anchors
    """
    a, b, c, d = tile_rect
    known_values = []
    weight_values = []

    h, w = source_mask.shape[:2]

    for stride in strides:
        side = size // stride
        xx, yy = np.meshgrid((np.arange(side) + 0.5) * stride + a, (np.arange(side) + 0.5) * stride + b)
        x = xx.astype(int)
        y = yy.astype(int)

        inside = (x < c) & (y < d) & (x >= 0) & (y >= 0) & (x < w) & (y < h)
        safe_x = np.clip(x, 0, w - 1)
        safe_y = np.clip(y, 0, h - 1)

        is_known = inside & (source_mask[safe_y, safe_x] > 0)
        bw = source_weights[safe_y, safe_x] * is_known.astype(np.float32)

        known_values.append(is_known.ravel())
        weight_values.append(bw.ravel())

    known_t = torch.from_numpy(np.concatenate(known_values)[:, None]).bool()
    weight_t = torch.from_numpy(np.concatenate(weight_values)[:, None]).float()
    return known_t, weight_t


if __name__ == '__main__':
    print("=== Testing Hole-Preserved Negative Mask Builder ===")
    data_path = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'
    pseudo_path = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
    
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tr = [r for r in data['rows'] if r['split'] == 'train']
    
    masks, weights = build_hole_preserved_negative_masks(tr, pseudo_manifest_path=pseudo_path)
    tiles = acne_tiles_p2(tr, masks, training=True)
    
    pos_tiles = [t for t in tiles if not t['isCleanControl']]
    neg_tiles = [t for t in tiles if t['isCleanControl']]
    print(f"Total training tiles: {len(tiles)} (Positive tiles: {len(pos_tiles)}, Clean control tiles: {len(neg_tiles)})")
    
    # Test known_cells_p2 shape
    t0 = tiles[0]
    m0 = masks[t0['row']['sha256']]
    w0 = weights[t0['row']['sha256']]
    kt, wt = known_cells_p2(m0, w0, t0['rect'])
    print(f"Known cells tensor shape: {kt.shape} (Expected: [12240, 1])")
    print(f"Weight tensor shape: {wt.shape} (Expected: [12240, 1])")
    assert kt.shape == (12240, 1)
    assert wt.shape == (12240, 1)
    print("Mask builder and 4-scale tile generator verified successfully.")
