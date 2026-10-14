#!/usr/bin/env python3
"""Diagnose Raw Level 0 (P2) Proposals on Validation Images."""

import sys
import json
from pathlib import Path
import numpy as np
import cv2
import torch

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from model_identity import TRUE_BASELINE_EPOCH02_PATH, TRUE_BASELINE_EPOCH02_SHA, load_verified_model
from safetensors.torch import load_file
from prepare_canonical_validation_cache import load_canonical_validation_cache
from acne_preprocessing import extract_tile_bgr, tile_to_tensor, TILE_SIZE, STRIDE, PAD_VAL
from yolox.models.yolo_head import bboxes_iou

def inspect_image_proposals(net, full_bgr, gt_boxes, img_name=""):
    print(f"\n=======================================================")
    print(f"Inspecting {img_name}: {len(gt_boxes)} GT lesions")
    print(f"=======================================================")
    
    H, W = full_bgr.shape[:2]
    net.eval()
    
    # Run full sliding window on image with very low confidence threshold (0.01)
    # Collect all proposals from Stride 4 (P2) vs Strides 8/16/32
    proposals_p2 = []
    proposals_other = []
    
    step = STRIDE # 288
    tile_size = TILE_SIZE # 384
    
    for y0 in range(0, max(1, H - tile_size + 1), step):
        for x0 in range(0, max(1, W - tile_size + 1), step):
            y1 = y0 + tile_size
            x1 = x0 + tile_size
            tile = extract_tile_bgr(full_bgr, (x0, y0, x1, y1), tile_size=tile_size, pad_val=PAD_VAL)
            inp = tile_to_tensor(tile).unsqueeze(0)
            
            with torch.no_grad():
                # Get raw outputs from head before decode/NMS
                fpn_outs = net.backbone(inp)
                
                # Check Stride 4 outputs specifically
                # Stride 4 is index 0
                feat0 = fpn_outs[0]
                cls_feat0 = net.head.cls_convs[0](net.head.stems[0](feat0))
                reg_feat0 = net.head.reg_convs[0](net.head.stems[0](feat0))
                cls_output0 = net.head.cls_preds[0](cls_feat0)
                reg_output0 = net.head.reg_preds[0](reg_feat0)
                obj_output0 = net.head.obj_preds[0](reg_feat0)
                
                # Sigmoids
                obj_sig0 = obj_output0.sigmoid()[0, 0] # [96, 96]
                cls_sig0 = cls_output0.sigmoid()[0, 0] # [96, 96]
                score0 = (obj_sig0 * cls_sig0).sqrt()  # [96, 96]
                
                max_score0 = score0.max().item()
                max_obj0 = obj_sig0.max().item()
                max_cls0 = cls_sig0.max().item()
                
                # Find any grid cells with score > 0.05
                high_mask = score0 > 0.05
                if high_mask.sum() > 0:
                    y_idxs, x_idxs = torch.where(high_mask)
                    for yi, xi in zip(y_idxs, x_idxs):
                        sc = score0[yi, xi].item()
                        ob = obj_sig0[yi, xi].item()
                        cl = cls_sig0[yi, xi].item()
                        # Box in crop coordinates
                        cx = (xi.float() + 0.5 + reg_output0[0, 0, yi, xi]) * 4.0
                        cy = (yi.float() + 0.5 + reg_output0[0, 1, yi, xi]) * 4.0
                        bw = torch.exp(reg_output0[0, 2, yi, xi]) * 4.0
                        bh = torch.exp(reg_output0[0, 3, yi, xi]) * 4.0
                        # Convert to full image coordinates
                        abs_cx = x0 + cx.item()
                        abs_cy = y0 + cy.item()
                        proposals_p2.append({
                            'score': sc, 'obj': ob, 'cls': cl,
                            'box': [abs_cx - bw.item()/2, abs_cy - bh.item()/2, abs_cx + bw.item()/2, abs_cy + bh.item()/2],
                            'size': (bw.item(), bh.item())
                        })

    print(f"  P2 proposals with score > 0.05: {len(proposals_p2)}")
    if proposals_p2:
        top_p2 = sorted(proposals_p2, key=lambda x: x['score'], reverse=True)[:5]
        for p in top_p2:
            print(f"    P2 cand: score={p['score']:.4f} (obj={p['obj']:.4f}, cls={p['cls']:.4f}) size={p['size'][0]:.1f}x{p['size'][1]:.1f} at center ({p['box'][0]+p['size'][0]/2:.1f}, {p['box'][1]+p['size'][1]/2:.1f})")

    # Match against GT lesions
    for gt in gt_boxes:
        gx0, gy0, gx1, gy1 = gt
        gw, gh = gx1 - gx0, gy1 - gy0
        gcx, gcy = (gx0 + gx1)/2, (gy0 + gy1)/2
        cat = 'tiny (<8px)' if max(gw, gh) < 8 else 'small (8-16px)' if max(gw, gh) < 16 else 'medium (16-32px)'
        
        # Check closest P2 proposal
        closest_p2 = None
        min_dist = 999999.0
        for p in proposals_p2:
            pcx = (p['box'][0] + p['box'][2]) / 2
            pcy = (p['box'][1] + p['box'][3]) / 2
            dist = np.hypot(pcx - gcx, pcy - gcy)
            if dist < min_dist:
                min_dist = dist
                closest_p2 = p

        gt_tensor = torch.tensor([[gcx, gcy, gw, gh]])
        print(f"  GT [{cat}]: size {gw:.1f}x{gh:.1f} at ({gcx:.1f}, {gcy:.1f})")
        if closest_p2 and min_dist < 20.0:
            p_box = torch.tensor([[
                (closest_p2['box'][0]+closest_p2['box'][2])/2,
                (closest_p2['box'][1]+closest_p2['box'][3])/2,
                closest_p2['size'][0], closest_p2['size'][1]
            ]])
            iou = bboxes_iou(gt_tensor, p_box, False).item()
            print(f"    -> Closest P2 (dist={min_dist:.1f}px): score={closest_p2['score']:.4f} (obj={closest_p2['obj']:.4f}, cls={closest_p2['cls']:.4f}), IoU={iou:.4f}, size={closest_p2['size'][0]:.1f}x{closest_p2['size'][1]:.1f}")
        else:
            print(f"    -> NO P2 proposal within 20px (closest dist={min_dist:.1f}px)")


def main():
    print("Testing Level 0 proposal diagnostics on validation images...")
    
    # 1. Load baseline model
    net, sha = load_verified_model(TRUE_BASELINE_EPOCH02_PATH, expected_sha=TRUE_BASELINE_EPOCH02_SHA)
    
    # 2. Load validation cache
    cached = load_canonical_validation_cache()
    pos_items = [item for item in cached if item.get('isProductPose') and not item.get('isNegative') and len(item.get('truth', [])) > 0]
    print(f"Found {len(pos_items)} in-scope positive product pose validation images.")
    
    # Inspect first 3 images containing tiny/small lesions
    for item in pos_items[:3]:
        full_bgr = item['bgr']
        gt_boxes = item['truth']
        inspect_image_proposals(net, full_bgr, gt_boxes, img_name=item['fileName'])

if __name__ == '__main__':
    main()
