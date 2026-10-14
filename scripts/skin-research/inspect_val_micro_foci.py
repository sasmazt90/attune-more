#!/usr/bin/env python3
"""Dissect the 7 <8px validation micro-foci in detail."""

import sys
import json
from pathlib import Path
import numpy as np
import cv2
import torch

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from prepare_canonical_validation_cache import load_canonical_validation_cache

def main():
    print("=== Dissecting Canonical Validation <8px Micro-Foci ===")
    cached = load_canonical_validation_cache()
    
    tiny_list = []
    for item in cached:
        name = item.get('fileName', item.get('sha256', 'val')[:8])
        bgr = item['bgr']
        h, w = bgr.shape[:2]
        truth = item.get('truth', [])
        cats = item.get('truthCategories', [])
        is_prod = item.get('isProductPose', False)
        if not is_prod:
            continue

        for bi, (b, cat) in enumerate(zip(truth, cats)):
            if cat != 'IN_SCOPE_VISIBLE_REGION':
                continue
            bw = b[2] - b[0]
            bh = b[3] - b[1]
            m = max(bw, bh)
            if m < 8.0:
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                x0 = max(0, int(cx - 16))
                y0 = max(0, int(cy - 16))
                x1 = min(w, int(cx + 16))
                y1 = min(h, int(cy + 16))
                local_crop = bgr[y0:y1, x0:x1]

                bx0, by0 = max(0, int(b[0])), max(0, int(b[1]))
                bx1, by1 = min(w, int(b[2])), min(h, int(b[3]))
                spot = bgr[by0:by1, bx0:bx1] if bx1 > bx0 and by1 > by0 else None
                spot_mean = spot.mean() if spot is not None else 0.0
                ring_mean = local_crop.mean() if local_crop.size > 0 else 0.0
                contrast = abs(spot_mean - ring_mean)

                tiny_list.append({
                    'image': name,
                    'box_index': bi,
                    'box': [float(x) for x in b],
                    'width': float(bw),
                    'height': float(bh),
                    'max_dim': float(m),
                    'area_px': float(bw * bh),
                    'contrast_bgr_delta': float(contrast),
                    'photo_resolution': f"{w}x{h}"
                })

    print(f"Total <8px validation lesions found: {len(tiny_list)}")
    for i, t in enumerate(tiny_list):
        print(f"  [{i+1}] Image: {t['image']} | Box: {t['box']} | Dim: {t['width']:.1f}x{t['height']:.1f} px (Area: {t['area_px']:.1f} px^2) | Contrast: {t['contrast_bgr_delta']:.2f}")

    out_file = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/val_micro_foci_dissection.json'
    out_file.write_text(json.dumps(tiny_list, indent=2), 'utf8')
    print(f"Saved dissection to {out_file}")

if __name__ == '__main__':
    main()
