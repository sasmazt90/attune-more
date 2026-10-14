#!/usr/bin/env python3
"""Inspect SimOTA Anchor Assignment across Strides for Small vs Medium Lesions."""

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
from train_p2_focused_trial import warm_start_level0_from_baseline

BASELINE_CHECKPOINT = ROOT / 'audit-results/acne-candidate-p2-focal-20261013/checkpoint-epoch-02-step-000496-1791911067067742300/model.safetensors'

def main():
    print("Testing SimOTA anchor assignment on YOLOX P2 model...")
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    load_file_dict = load_file(str(BASELINE_CHECKPOINT))
    net.load_state_dict(load_file_dict)
    warm_start_level0_from_baseline(net)
    net.eval()

    # Image tensor
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

        gt_classes = torch.tensor([0.0])
        fg_mask_cand, geometry_relation = net.head.get_geometry_constraint(
            gt_box,
            expanded_strides_cat,
            x_shifts_cat,
            y_shifts_cat,
        )
        cand_strides = expanded_strides_cat[0][fg_mask_cand].tolist()
        cand_counter = Counter(cand_strides)
        print(f"  Candidate Anchors in Geometry Constraint (center_radius=1.5):")
        for s in [4, 8, 16, 32]:
            print(f"    Stride {s:2d}: {cand_counter.get(float(s), 0)} candidates")

        cand_bboxes = bbox_preds[0][fg_mask_cand]
        from yolox.models.yolo_head import bboxes_iou
        pair_wise_ious = bboxes_iou(gt_box, cand_bboxes, False)
        
        cls_preds_ = cls_preds[0][fg_mask_cand]
        obj_preds_ = obj_preds[0][fg_mask_cand]
        cls_preds_sig = (cls_preds_.float().sigmoid() * obj_preds_.float().sigmoid()).sqrt()
        pair_wise_cls_loss = F.binary_cross_entropy(
            cls_preds_sig.unsqueeze(0),
            torch.ones_like(cls_preds_sig.unsqueeze(0)),
            reduction="none"
        ).sum(-1)
        pair_wise_ious_loss = -torch.log(pair_wise_ious + 1e-8)
        cost = (
            pair_wise_cls_loss
            + 3.0 * pair_wise_ious_loss
            + float(1e6) * (~geometry_relation)
        )

        for s in [4, 8]:
            s_mask = (torch.tensor(cand_strides) == s)
            if s_mask.sum() > 0:
                s_costs = cost[0][s_mask]
                s_ious = pair_wise_ious[0][s_mask]
                s_cls = pair_wise_cls_loss[0][s_mask]
                s_pred_w = cand_bboxes[s_mask, 2]
                s_pred_h = cand_bboxes[s_mask, 3]
                print(f"    Stride {s} best candidate:")
                best_idx = torch.argmin(s_costs)
                print(f"      Cost: {s_costs[best_idx].item():.4f} (cls_loss: {s_cls[best_idx].item():.4f}, iou_loss: {pair_wise_ious_loss[0][s_mask][best_idx].item():.4f})")
                print(f"      Pred IoU: {s_ious[best_idx].item():.4f}, Pred box size: ({s_pred_w[best_idx].item():.1f}, {s_pred_h[best_idx].item():.1f})")

        (
            gt_matched_classes,
            fg_mask,
            pred_ious_this_matching,
            matched_gt_inds,
            num_fg,
        ) = net.head.get_assignments(
            0,
            1,
            gt_box,
            gt_classes,
            bbox_preds[0],
            expanded_strides_cat,
            x_shifts_cat,
            y_shifts_cat,
            cls_preds,
            obj_preds,
        )

        matched_strides = expanded_strides_cat[0][fg_mask].tolist()
        stride_counts = Counter(matched_strides)
        print(f"  Assigned Foreground Anchors (num_fg = {num_fg}):")
        for s in [4, 8, 16, 32]:
            print(f"    Stride {s:2d}: {stride_counts.get(float(s), 0)} anchors")
        print(f"  Matched pred IoUs: {[round(iou.item(), 3) for iou in pred_ious_this_matching]}")

if __name__ == '__main__':
    main()
