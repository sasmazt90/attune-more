#!/usr/bin/env python3
"""Test Scale-Guided SimOTA Anchor Assignment across Strides for Small vs Medium Lesions."""

import sys
from pathlib import Path
from collections import Counter
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model
from safetensors.torch import load_file
from yolox.models.yolo_head import bboxes_iou

BASELINE_CHECKPOINT = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/checkpoint-epoch-02-step-000496-1791911067067742300/model.safetensors'

def get_scale_guided_geometry_constraint(
    gt_bboxes_per_image, expanded_strides, x_shifts, y_shifts,
):
    """Geometry constraint with scale-to-pyramid level compatibility.
    
    Rules for lesion size s = max(w, h):
    - s < 9 px: Stride 4 ONLY (Stride >= 8 is mathematically incapable of IoU 0.50).
    - 9 <= s < 18 px: Stride 4 and Stride 8 (transition zone).
    - 18 <= s < 36 px: Stride 8 and Stride 16.
    - s >= 36 px: Stride 16 and Stride 32.
    """
    expanded_strides_per_image = expanded_strides[0]
    x_centers_per_image = ((x_shifts[0] + 0.5) * expanded_strides_per_image).unsqueeze(0)
    y_centers_per_image = ((y_shifts[0] + 0.5) * expanded_strides_per_image).unsqueeze(0)

    # Center distance
    center_radius = 1.5
    center_dist = expanded_strides_per_image.unsqueeze(0) * center_radius
    gt_bboxes_per_image_l = (gt_bboxes_per_image[:, 0:1]) - center_dist
    gt_bboxes_per_image_r = (gt_bboxes_per_image[:, 0:1]) + center_dist
    gt_bboxes_per_image_t = (gt_bboxes_per_image[:, 1:2]) - center_dist
    gt_bboxes_per_image_b = (gt_bboxes_per_image[:, 1:2]) + center_dist

    c_l = x_centers_per_image - gt_bboxes_per_image_l
    c_r = gt_bboxes_per_image_r - x_centers_per_image
    c_t = y_centers_per_image - gt_bboxes_per_image_t
    c_b = gt_bboxes_per_image_b - y_centers_per_image
    center_deltas = torch.stack([c_l, c_t, c_r, c_b], 2)
    is_in_centers = center_deltas.min(dim=-1).values > 0.0

    # Scale-to-stride compatibility mask
    # gt_bboxes_per_image: [num_gt, 4] where [cx, cy, w, h]
    gt_max_dim = torch.max(gt_bboxes_per_image[:, 2:4], dim=-1).values.unsqueeze(1) # [num_gt, 1]
    stride_row = expanded_strides_per_image.unsqueeze(0) # [1, num_anchors]

    # Stride scale rules:
    # Stride 4: valid for s < 20 px
    # Stride 8: valid for 8 <= s < 40 px
    # Stride 16: valid for 16 <= s < 80 px
    # Stride 32: valid for s >= 32 px
    scale_ok = torch.zeros_like(is_in_centers, dtype=torch.bool)
    # Stride 4
    scale_ok |= (stride_row == 4) & (gt_max_dim < 18.0)
    # Stride 8
    scale_ok |= (stride_row == 8) & (gt_max_dim >= 8.0) & (gt_max_dim < 36.0)
    # Stride 16
    scale_ok |= (stride_row == 16) & (gt_max_dim >= 18.0) & (gt_max_dim < 72.0)
    # Stride 32
    scale_ok |= (stride_row == 32) & (gt_max_dim >= 36.0)

    is_valid = is_in_centers & scale_ok
    anchor_filter = is_valid.sum(dim=0) > 0
    geometry_relation = is_valid[:, anchor_filter]

    return anchor_filter, geometry_relation

def main():
    print("Testing Scale-Guided SimOTA anchor assignment on YOLOX P2 model...")
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    load_file_dict = load_file(str(BASELINE_CHECKPOINT))
    net.load_state_dict(load_file_dict)
    net.eval()

    x = torch.zeros((1, 3, 384, 384), dtype=torch.float32)

    test_boxes = [
        ("Micro (6px)", torch.tensor([[192.0, 192.0, 6.0, 6.0]])),
        ("Small (10px)", torch.tensor([[192.0, 192.0, 10.0, 10.0]])),
        ("Small-Med (14px)", torch.tensor([[192.0, 192.0, 14.0, 14.0]])),
        ("Medium (20px)", torch.tensor([[192.0, 192.0, 20.0, 20.0]])),
    ]

    fpn_outs = net.backbone(x)

    for label, gt_box in test_boxes:
        print(f"\n=======================================================")
        print(f"Testing {label} with GT box: {gt_box.tolist()[0]}")
        print(f"=======================================================")

        outputs = []
        origin_preds = []
        x_shifts = []
        y_shifts = []
        expanded_strides = []

        for k, (stride_this_level, xin_feat) in enumerate(zip(net.head.strides, fpn_outs)):
            feat = xin_feat
            feat = net.head.stems[k](feat)
            cls_feat = feat
            reg_feat = feat

            cls_output = net.head.cls_preds[k](net.head.cls_convs[k](cls_feat))
            reg_output = net.head.reg_preds[k](net.head.reg_convs[k](reg_feat))
            obj_output = net.head.obj_preds[k](reg_feat)

            output = torch.cat([reg_output, obj_output, cls_output], 1)
            output, grid = net.head.get_output_and_grid(
                output, k, stride_this_level, xin_feat.type()
            )
            x_shifts.append(grid[:, :, 0])
            y_shifts.append(grid[:, :, 1])
            expanded_strides.append(
                torch.zeros(1, grid.shape[1]).fill_(stride_this_level).type_as(xin_feat)
            )
            outputs.append(output)

        outputs_cat = torch.cat(outputs, 1)
        x_shifts_cat = torch.cat(x_shifts, 1)
        y_shifts_cat = torch.cat(y_shifts, 1)
        expanded_strides_cat = torch.cat(expanded_strides, 1)

        bbox_preds = outputs_cat[:, :, :4]
        obj_preds = outputs_cat[:, :, 4:5]
        cls_preds = outputs_cat[:, :, 5:]

        # Use scale-guided geometry constraint!
        fg_mask, geometry_relation = get_scale_guided_geometry_constraint(
            gt_box,
            expanded_strides_cat,
            x_shifts_cat,
            y_shifts_cat,
        )

        bboxes_preds_per_image = bbox_preds[0][fg_mask]
        cls_preds_ = cls_preds[0][fg_mask]
        obj_preds_ = obj_preds[0][fg_mask]
        num_in_boxes_anchor = bboxes_preds_per_image.shape[0]

        pair_wise_ious = bboxes_iou(gt_box, bboxes_preds_per_image, False)
        gt_cls_per_image = torch.ones((1, 1), dtype=torch.float32)
        pair_wise_ious_loss = -torch.log(pair_wise_ious + 1e-8)

        cls_preds_sig = (cls_preds_.float().sigmoid() * obj_preds_.float().sigmoid()).sqrt()
        pair_wise_cls_loss = F.binary_cross_entropy(
            cls_preds_sig.unsqueeze(0),
            gt_cls_per_image.unsqueeze(1).repeat(1, num_in_boxes_anchor, 1),
            reduction="none"
        ).sum(-1)

        cost = (
            pair_wise_cls_loss
            + 3.0 * pair_wise_ious_loss
            + float(1e6) * (~geometry_relation)
        )

        num_fg, gt_matched_classes, pred_ious_this_matching, matched_gt_inds = net.head.simota_matching(
            cost, pair_wise_ious, torch.tensor([0.0]), 1, fg_mask
        )

        matched_strides = expanded_strides_cat[0][fg_mask].tolist()
        stride_counts = Counter(matched_strides)
        print(f"  Assigned Foreground Anchors (num_fg = {num_fg}):")
        for s in [4, 8, 16, 32]:
            print(f"    Stride {s:2d}: {stride_counts.get(float(s), 0)} anchors")
        print(f"  Matched pred IoUs: {[round(iou.item(), 3) for iou in pred_ious_this_matching]}")

if __name__ == '__main__':
    main()
