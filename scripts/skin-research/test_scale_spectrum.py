#!/usr/bin/env python3
"""Test Scale-to-Stride Mapping for Fine Acne Lesions."""

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
    expanded_strides_per_image = expanded_strides[0]
    x_centers_per_image = ((x_shifts[0] + 0.5) * expanded_strides_per_image).unsqueeze(0)
    y_centers_per_image = ((y_shifts[0] + 0.5) * expanded_strides_per_image).unsqueeze(0)

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

    gt_max_dim = torch.max(gt_bboxes_per_image[:, 2:4], dim=-1).values.unsqueeze(1)
    stride_row = expanded_strides_per_image.unsqueeze(0)

    # Scale-to-stride mapping designed for skin lesion physics:
    # Stride 4 (P2): s < 14 px
    # Stride 8 (P3): 12 <= s < 36 px
    # Stride 16 (P4): 24 <= s < 72 px
    # Stride 32 (P5): s >= 48 px
    scale_ok = torch.zeros_like(is_in_centers, dtype=torch.bool)
    scale_ok |= (stride_row == 4) & (gt_max_dim < 14.0)
    scale_ok |= (stride_row == 8) & (gt_max_dim >= 12.0) & (gt_max_dim < 36.0)
    scale_ok |= (stride_row == 16) & (gt_max_dim >= 24.0) & (gt_max_dim < 72.0)
    scale_ok |= (stride_row == 32) & (gt_max_dim >= 48.0)

    is_valid = is_in_centers & scale_ok
    anchor_filter = is_valid.sum(dim=0) > 0
    geometry_relation = is_valid[:, anchor_filter]

    return anchor_filter, geometry_relation

def main():
    print("Testing Scale-Guided SimOTA on lesion size spectrum...")
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    load_file_dict = load_file(str(BASELINE_CHECKPOINT))
    net.load_state_dict(load_file_dict)
    net.eval()

    x = torch.zeros((1, 3, 384, 384), dtype=torch.float32)
    fpn_outs = net.backbone(x)

    test_sizes = [5.0, 7.0, 9.0, 11.0, 13.0, 16.0, 20.0, 25.0]

    for s in test_sizes:
        gt_box = torch.tensor([[192.0, 192.0, s, s]])
        outputs = []
        origin_preds = []
        x_shifts = []
        y_shifts = []
        expanded_strides = []

        for k, (stride_this_level, xin_feat) in enumerate(zip(net.head.strides, fpn_outs)):
            feat = xin_feat
            feat = net.head.stems[k](feat)
            cls_output = net.head.cls_preds[k](net.head.cls_convs[k](feat))
            reg_output = net.head.reg_preds[k](net.head.reg_convs[k](feat))
            obj_output = net.head.obj_preds[k](feat)

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
        print(f"Lesion {s:4.1f} px: Assigned -> Stride 4: {stride_counts.get(4.0, 0)}, Stride 8: {stride_counts.get(8.0, 0)} | Matched IoU: {[round(x.item(), 3) for x in pred_ious_this_matching]}")

if __name__ == '__main__':
    main()
