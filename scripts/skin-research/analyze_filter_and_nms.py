#!/usr/bin/env python3
"""Deep dive into filter and NMS staging on Scope B and Hair Controls."""

import sys
import json
from pathlib import Path
import torch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from prepare_canonical_validation_cache import load_canonical_validation_cache
import acne_box_support
from torchvision.ops import nms as torch_nms, box_iou

cached = {it['sha256']: it for it in load_canonical_validation_cache()}
raw_cache = torch.load(ROOT / 'audit-results/acne-input-audit-20261015/raw_decoded_scope_b_candidates.pt')

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

def analyze_model(mkey):
    print("=" * 80)
    print(f"ANALYSIS FOR MODEL: {mkey}")
    print("=" * 80)

    for sha in SCOPE_B_NEGATIVE_SHAS:
        raw = raw_cache[mkey][sha]
        c_item = cached[sha]
        conf_mask = raw['scores'] >= 0.30
        conf_indices = torch.where(conf_mask)[0]
        if len(conf_indices) == 0:
            print(f"Photo {sha[:8]}: 0 candidates >= 0.30")
            continue
        keep = torch_nms(raw['boxes'][conf_indices], raw['scores'][conf_indices], 0.30)
        boxes = raw['boxes'][conf_indices][keep]
        scores = raw['scores'][conf_indices][keep]
        raw_nms_boxes = [boxes[i].tolist() + [scores[i].item()] for i in range(len(boxes))]

        orig_a, orig_r = acne_box_support.accepted_boxes(
            raw_nms_boxes, c_item['envelopes'], c_item['skin_support'], c_item['hair'], c_item['exclusion'],
            sha, c_item['scale'], c_item['origin'],
            visible_regions=c_item['allowedRegions'],
            landmarks=c_item['landmarks'],
            source_shape=(c_item['height'], c_item['width'])
        )
        n_acc = sum(len(v) for v in orig_a.values())
        print(f"Photo {sha[:8]}: nms_candidates={len(raw_nms_boxes)}, accepted={n_acc}, rejected={len(orig_r)}")
        for reg, blist in orig_a.items():
            for b in blist:
                conf = b['confidence']
                print(f"   [ACCEPTED FP] reg={reg} conf={conf:.3f} box=[{b['x']:.1f}, {b['y']:.1f}, {b['width']:.1f}, {b['height']:.1f}]")
        for r in orig_r:
            bx = r['box']
            reason = r['reason']
            conf = bx[4]
            # Inspect mask values at center and box
            x0, y0 = c_item['origin']; scale = c_item['scale']
            w_m, h_m = c_item['skin_support'].shape[1], c_item['skin_support'].shape[0]
            cx = min(w_m - 1, max(0, int(((bx[0] + bx[2]) / 2.0 - x0) * scale)))
            cy = min(h_m - 1, max(0, int(((bx[1] + bx[3]) / 2.0 - y0) * scale)))
            a = max(0, int((bx[0] - x0) * scale))
            b = max(0, int((bx[1] - y0) * scale))
            c = min(w_m, int(np.ceil((bx[2] - x0) * scale)))
            d = min(h_m, int(np.ceil((bx[3] - y0) * scale)))
            hair_c = bool(c_item['hair'][cy, cx])
            skin_c = bool(c_item['skin_support'][cy, cx])
            excl_c = bool(c_item['exclusion'][cy, cx])
            hair_frac = float((c_item['hair'][b:d, a:c] > 0).mean())
            skin_frac = float(c_item['skin_support'][b:d, a:c].mean())
            excl_frac = float((c_item['exclusion'][b:d, a:c] > 0).mean())
            print(f"   [REJECTED] reason={reason} conf={conf:.3f} box=[{bx[0]:.1f}, {bx[1]:.1f}, {bx[2]:.1f}, {bx[3]:.1f}]")
            print(f"              center: hair={hair_c}, skin={skin_c}, excl={excl_c} | box: hair={hair_frac:.3f}, skin={skin_frac:.3f}, excl={excl_frac:.3f}")

if __name__ == '__main__':
    for m in ['step0', 'epoch4']:
        analyze_model(m)
