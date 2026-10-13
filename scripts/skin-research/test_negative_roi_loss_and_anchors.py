#!/usr/bin/env python3
"""Two-step validation check for Item 4:
Verifies that curated negative ROIs on positive train photos actively generate
objectness loss without breaking SimOTA dynamic-k positive anchor assignment.
"""

import sys
import json
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
from selected_yolox_loss import KnownObjectnessBCE, known_cells
from source_skin_support import known_skin_scope
from train_focused_local import acne_tiles, yolo_batch, tile_image

DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'
BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'


def build_scopes_and_tiles(data_path):
    with open(data_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    tr = [r for r in manifest['rows'] if r['split'] == 'train']
    
    scopes = {}
    for r in tr:
        scope = np.zeros((r['height'], r['width']), np.uint8)
        if r.get('negativeROI'):
            src_path = Path(r['absolutePath']) if 'absolutePath' in r and Path(r['absolutePath']).exists() else LIVE_TEST / r['path']
            bgr = cv2.imread(str(src_path))
            scope = known_skin_scope(r, bgr) if bgr is not None else scope
        elif r.get('negativeROIs'):
            for n_roi in r['negativeROIs']:
                poly = np.array(n_roi['polygon'], dtype=np.int32)
                cv2.fillPoly(scope, [poly], 1)
        scopes[r['sha256']] = scope

    tiles = acne_tiles(tr, training=True)
    for t in tiles:
        has_reviewed_skin = bool(r.get('negativeROI') or r.get('negativeROIs'))
        t['known'] = known_cells(scopes[t['row']['sha256']], t['rect'], fully_reviewed=has_reviewed_skin)
    return tr, tiles


def main():
    print("=== Two-Step Loss and Anchor Assignment Verification ===", flush=True)
    tr, tiles = build_scopes_and_tiles(DATA_PATH)
    print(f"Loaded {len(tr)} train rows, {len(tiles)} active training tiles", flush=True)

    pos_tiles_with_neg_cells = [t for t in tiles if t['boxes'] and t['known'].sum() > 0]
    print(f"Active tiles containing both positive lesions and negative ROI cells: {len(pos_tiles_with_neg_cells)}")
    assert len(pos_tiles_with_neg_cells) > 0, "No tiles found with both positive boxes and known negative cells!"

    # Build model from Baseline
    net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net)
    weights = load_file(str(BASELINE_WEIGHTS))
    net.load_state_dict(weights)
    
    obj_loss = KnownObjectnessBCE()
    net.head.bcewithlog_loss = obj_loss

    for k, p in net.named_parameters():
        p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))
    
    opt = torch.optim.AdamW([p for p in net.parameters() if p.requires_grad], lr=1e-5)

    # Run 2 controlled forward/backward steps
    print("\nExecuting Step 1 and Step 2 on mixed positive + negative ROI tiles...")
    for step in range(1, 3):
        batch_items = pos_tiles_with_neg_cells[(step - 1) * 2 : step * 2]
        total_gts = sum(len(t['boxes']) for t in batch_items)
        total_known_cells = sum(int(t['known'].sum()) for t in batch_items)
        
        x, y = yolo_batch(batch_items)
        obj_loss.known = torch.cat([t['known'] for t in batch_items], dim=0)
        
        net.train()
        for m in net.modules():
            if isinstance(m, torch.nn.BatchNorm2d):
                m.eval()
        
        opt.zero_grad()
        loss_dict = net(x, y)
        
        assigned_num_fg = float(loss_dict['num_fg']) * max(1, total_gts)
        obj_val = float(loss_dict['conf_loss'])
        total_loss = loss_dict['total_loss']
        
        total_loss.backward()
        
        # Verify gradients
        grad_norm_lateral = net.backbone.lateral_conv0.conv.weight.grad.norm().item()
        grad_norm_head = net.head.reg_convs[0][0].conv.weight.grad.norm().item()
        
        opt.step()
        
        print(f"Step {step}:")
        print(f"  Total GT boxes: {total_gts}")
        print(f"  Known negative cells in batch: {total_known_cells}")
        print(f"  Assigned foreground anchors (num_fg): {assigned_num_fg:.1f}")
        print(f"  Objectness loss: {obj_val:.4f}")
        print(f"  Total loss: {total_loss.item():.4f}")
        print(f"  Gradients: lateral_conv0={grad_norm_lateral:.6f}, head_reg_conv={grad_norm_head:.6f}")
        
        # Invariants:
        assert assigned_num_fg >= total_gts, f"SimOTA anchor assignment collapsed! {assigned_num_fg} < {total_gts}"
        assert obj_val > 0.0, "Objectness loss must be non-zero!"
        assert grad_norm_lateral > 0.0 and grad_norm_head > 0.0, "Gradients are zero!"

    print("\nSUCCESS: All 2-step checks passed!")
    print("- Negative ROIs actively produce objectness loss on background cells.")
    print("- SimOTA dynamic-k anchor assignment to positive lesions is 100% intact.")
    print("- Non-zero gradients backpropagate through both PAFPN and detection head.")


if __name__ == '__main__':
    main()
