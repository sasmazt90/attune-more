#!/usr/bin/env python3
"""YOLOX-S with Native P2 Small-Object Branch (Strides [4, 8, 16, 32]).

Architecture & Contract:
- Backbone: CSPDarknet(depth=0.33, width=0.5), tapping into dark2 (stride 4, 64ch),
  dark3 (stride 8, 128ch), dark4 (stride 16, 256ch), dark5 (stride 32, 512ch).
- FPN / PANet: Real high-resolution P2 branch connected directly to dark2.
  Top-Down:
    P5 -> lateral_conv0 -> upsample -> cat(dark4) -> C3_p4
    P4 -> reduce_conv1  -> upsample -> cat(dark3) -> C3_p3
    P3 -> reduce_conv2  -> upsample -> cat(dark2) -> C3_p2 (stride 4, 64ch)
  Bottom-Up:
    P2 -> bu_conv3 (stride 2) -> cat(fpn_p3) -> C3_n2 (stride 8, 128ch)
    P3 -> bu_conv2 (stride 2) -> cat(fpn_p4) -> C3_n3 (stride 16, 256ch)
    P4 -> bu_conv1 (stride 2) -> cat(fpn_p5) -> C3_n4 (stride 32, 512ch)
  Outputs: (P2, P3, P4, P5) at strides [4, 8, 16, 32].
- Head: YOLOXHead with strides=[4, 8, 16, 32] and in_channels=[128, 256, 512, 1024].
  Width=0.5 scales input channels to [64, 128, 256, 512].
- Strict Index-Aligned Baseline Weight Transfer:
  Baseline Level 0 (P3) -> P2-Model Level 1 (P3)
  Baseline Level 1 (P4) -> P2-Model Level 2 (P4)
  Baseline Level 2 (P5) -> P2-Model Level 3 (P5)
  New Level 0 (P2) is explicitly initialized with prior_prob bias.
"""

import sys
import math
from pathlib import Path
from typing import Dict, List, Tuple, Any
import torch
import torch.nn as nn
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from yolox.models.darknet import CSPDarknet
from yolox.models.network_blocks import BaseConv, CSPLayer, DWConv
from yolox.models.yolo_head import YOLOXHead
from yolox.models.yolox import YOLOX
from yolox.models.losses import IOUloss
from yolox_numeric import install_bounds


class YOLOPAFPN_P2(nn.Module):
    """YOLO-PAFPN with real high-resolution P2 branch (stride 4) connected to CSPDarknet dark2."""

    def __init__(
        self,
        depth=0.33,
        width=0.5,
        in_features=("dark2", "dark3", "dark4", "dark5"),
        in_channels=[128, 256, 512, 1024],
        depthwise=False,
        act="silu",
    ):
        super().__init__()
        self.backbone = CSPDarknet(depth, width, out_features=in_features, depthwise=depthwise, act=act)
        self.in_features = in_features
        self.in_channels = in_channels
        Conv = DWConv if depthwise else BaseConv

        # Channels scaled by width:
        # in_channels[0]*w = 64 (dark2)
        # in_channels[1]*w = 128 (dark3)
        # in_channels[2]*w = 256 (dark4)
        # in_channels[3]*w = 512 (dark5)
        c2 = int(in_channels[0] * width)  # 64
        c3 = int(in_channels[1] * width)  # 128
        c4 = int(in_channels[2] * width)  # 256
        c5 = int(in_channels[3] * width)  # 512

        self.upsample = nn.Upsample(scale_factor=2, mode="nearest")

        # --- Top-Down FPN Path ---
        # Level 5 -> 4
        self.lateral_conv0 = BaseConv(c5, c4, 1, 1, act=act)  # 512 -> 256
        self.C3_p4 = CSPLayer(c4 * 2, c4, round(3 * depth), False, depthwise=depthwise, act=act)  # 512 -> 256

        # Level 4 -> 3
        self.reduce_conv1 = BaseConv(c4, c3, 1, 1, act=act)  # 256 -> 128
        self.C3_p3 = CSPLayer(c3 * 2, c3, round(3 * depth), False, depthwise=depthwise, act=act)  # 256 -> 128

        # Level 3 -> 2 (NEW REAL P2 BRANCH)
        self.reduce_conv2 = BaseConv(c3, c2, 1, 1, act=act)  # 128 -> 64
        self.C3_p2 = CSPLayer(c2 * 2, c2, round(3 * depth), False, depthwise=depthwise, act=act)  # 128 -> 64

        # --- Bottom-Up PANet Path ---
        # Level 2 -> 3 (NEW REAL P2 BOTTOM-UP)
        self.bu_conv3 = Conv(c2, c2, 3, 2, act=act)  # stride 2, 64 -> 64
        self.C3_n2 = CSPLayer(c2 * 2, c3, round(3 * depth), False, depthwise=depthwise, act=act)  # 128 -> 128

        # Level 3 -> 4
        self.bu_conv2 = Conv(c3, c3, 3, 2, act=act)  # stride 2, 128 -> 128
        self.C3_n3 = CSPLayer(c3 * 2, c4, round(3 * depth), False, depthwise=depthwise, act=act)  # 256 -> 256

        # Level 4 -> 5
        self.bu_conv1 = Conv(c4, c4, 3, 2, act=act)  # stride 2, 256 -> 256
        self.C3_n4 = CSPLayer(c4 * 2, c5, round(3 * depth), False, depthwise=depthwise, act=act)  # 512 -> 512

        # Zero-initialized residual gate for P2 injection: preserves pre-trained P3/P4/P5 at step 0
        self.p2_gate = nn.Parameter(torch.zeros(1))

    def forward(self, input_tensor):
        # 1. CSPDarknet Backbone
        out_features = self.backbone(input_tensor)
        x3 = out_features["dark2"]  # stride 4, 64ch
        x2 = out_features["dark3"]  # stride 8, 128ch
        x1 = out_features["dark4"]  # stride 16, 256ch
        x0 = out_features["dark5"]  # stride 32, 512ch

        # 2. Top-Down FPN
        fpn_out0 = self.lateral_conv0(x0)            # stride 32, 256ch
        f_out0 = self.upsample(fpn_out0)             # stride 16, 256ch
        f_out0 = torch.cat([f_out0, x1], 1)          # 512ch
        f_out0 = self.C3_p4(f_out0)                  # stride 16, 256ch

        fpn_out1 = self.reduce_conv1(f_out0)         # stride 16, 128ch
        f_out1 = self.upsample(fpn_out1)             # stride 8, 128ch
        f_out1 = torch.cat([f_out1, x2], 1)          # 256ch
        base_p3 = self.C3_p3(f_out1)                 # stride 8, 128ch (Exact baseline P3 output!)

        # P2 Top-Down
        fpn_out2 = self.reduce_conv2(base_p3)        # stride 8, 64ch
        f_out2 = self.upsample(fpn_out2)             # stride 4, 64ch
        f_out2 = torch.cat([f_out2, x3], 1)          # 128ch
        pan_out3 = self.C3_p2(f_out2)                # stride 4, 64ch (P2 Output)

        # 3. Bottom-Up PANet with Zero-Init Gate preserving baseline P3 at step 0
        p_out2 = self.bu_conv3(pan_out3)             # stride 8, 64ch
        p_out2 = torch.cat([p_out2, fpn_out2], 1)    # 128ch
        p2_inj = self.C3_n2(p_out2)                  # stride 8, 128ch
        pan_out2 = base_p3 + self.p2_gate * p2_inj   # stride 8, 128ch (P3 Output)

        p_out1 = self.bu_conv2(pan_out2)             # stride 16, 128ch
        p_out1 = torch.cat([p_out1, fpn_out1], 1)    # 256ch
        pan_out1 = self.C3_n3(p_out1)                # stride 16, 256ch (P4 Output)

        p_out0 = self.bu_conv1(pan_out1)             # stride 32, 256ch
        p_out0 = torch.cat([p_out0, fpn_out0], 1)    # 512ch
        pan_out0 = self.C3_n4(p_out0)                # stride 32, 512ch (P5 Output)

        # Outputs in order: P2 (stride 4), P3 (stride 8), P4 (stride 16), P5 (stride 32)
        return (pan_out3, pan_out2, pan_out1, pan_out0)


class YOLOXHead_P2(YOLOXHead):
    """YOLOX Head with explicit Focal Objectness Loss separation and UNKNOWN mask enforcement."""

    def __init__(
        self,
        num_classes,
        width=1.0,
        strides=[4, 8, 16, 32],
        in_channels=[128, 256, 512, 1024],
        act="silu",
        depthwise=False,
        loss_type="iou",
    ):
        super().__init__(num_classes, width, strides=strides, in_channels=in_channels, act=act, depthwise=depthwise)
        self.loss_type = loss_type
        self.iou_loss = IOUloss(reduction="none", loss_type=loss_type)
        self.cls_bce_loss = nn.BCEWithLogitsLoss(reduction="none")
        self.obj_focal_loss = None

    def get_geometry_constraint(
        self, gt_bboxes_per_image, expanded_strides, x_shifts, y_shifts,
    ):
        """Scale-guided geometry constraint matching physical lesion size to pyramid stride.

        Rules:
        - Stride 4 (P2): s < 14 px (crucial for micro/tiny lesions where stride 8 cannot achieve IoU 0.50).
        - Stride 8 (P3): 12 <= s < 36 px (preserves baseline acne representation for small-med & med).
        - Stride 16 (P4): 24 <= s < 72 px.
        - Stride 32 (P5): s >= 48 px.
        """
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

        scale_ok = torch.zeros_like(is_in_centers, dtype=torch.bool)
        scale_ok |= (stride_row == 4) & (gt_max_dim < 14.0)
        scale_ok |= (stride_row == 8) & (gt_max_dim >= 12.0) & (gt_max_dim < 36.0)
        scale_ok |= (stride_row == 16) & (gt_max_dim >= 24.0) & (gt_max_dim < 72.0)
        scale_ok |= (stride_row == 32) & (gt_max_dim >= 48.0)

        is_valid = is_in_centers & scale_ok
        anchor_filter = is_valid.sum(dim=0) > 0
        geometry_relation = is_valid[:, anchor_filter]

        return anchor_filter, geometry_relation

    def get_losses(
        self,
        imgs,
        x_shifts,
        y_shifts,
        expanded_strides,
        labels,
        outputs,
        origin_preds,
        dtype,
    ):
        import torch.nn.functional as F
        bbox_preds = outputs[:, :, :4]  # [batch, n_anchors_all, 4]
        obj_preds = outputs[:, :, 4:5]  # [batch, n_anchors_all, 1]
        cls_preds = outputs[:, :, 5:]  # [batch, n_anchors_all, n_cls]

        nlabel = (labels.sum(dim=2) > 0).sum(dim=1)  # number of objects

        total_num_anchors = outputs.shape[1]
        x_shifts = torch.cat(x_shifts, 1)  # [1, n_anchors_all]
        y_shifts = torch.cat(y_shifts, 1)  # [1, n_anchors_all]
        expanded_strides = torch.cat(expanded_strides, 1)
        if self.use_l1:
            origin_preds = torch.cat(origin_preds, 1)

        cls_targets = []
        reg_targets = []
        l1_targets = []
        obj_targets = []
        fg_masks = []

        num_fg = 0.0
        num_gts = 0.0

        for batch_idx in range(outputs.shape[0]):
            num_gt = int(nlabel[batch_idx])
            num_gts += num_gt
            if num_gt == 0:
                cls_target = outputs.new_zeros((0, self.num_classes))
                reg_target = outputs.new_zeros((0, 4))
                l1_target = outputs.new_zeros((0, 4))
                obj_target = outputs.new_zeros((total_num_anchors, 1))
                fg_mask = outputs.new_zeros(total_num_anchors).bool()
            else:
                gt_bboxes_per_image = labels[batch_idx, :num_gt, 1:5]
                gt_classes = labels[batch_idx, :num_gt, 0]
                bboxes_preds_per_image = bbox_preds[batch_idx]

                (
                    gt_matched_classes,
                    fg_mask,
                    pred_ious_this_matching,
                    matched_gt_inds,
                    num_fg_img,
                ) = self.get_assignments(
                    batch_idx,
                    num_gt,
                    gt_bboxes_per_image,
                    gt_classes,
                    bboxes_preds_per_image,
                    expanded_strides,
                    x_shifts,
                    y_shifts,
                    cls_preds,
                    obj_preds,
                )

                num_fg += num_fg_img

                cls_target = F.one_hot(
                    gt_matched_classes.to(torch.int64), self.num_classes
                ) * pred_ious_this_matching.unsqueeze(-1)
                obj_target = fg_mask.unsqueeze(-1)
                reg_target = gt_bboxes_per_image[matched_gt_inds]
                if self.use_l1:
                    l1_target = self.get_l1_target(
                        outputs.new_zeros((num_fg_img, 4)),
                        gt_bboxes_per_image[matched_gt_inds],
                        expanded_strides[0][fg_mask],
                        x_shifts=x_shifts[0][fg_mask],
                        y_shifts=y_shifts[0][fg_mask],
                    )

            cls_targets.append(cls_target)
            reg_targets.append(reg_target)
            obj_targets.append(obj_target.to(dtype))
            fg_masks.append(fg_mask)
            if self.use_l1:
                l1_targets.append(l1_target)

        cls_targets = torch.cat(cls_targets, 0)
        reg_targets = torch.cat(reg_targets, 0)
        obj_targets = torch.cat(obj_targets, 0)
        fg_masks = torch.cat(fg_masks, 0)
        if self.use_l1:
            l1_targets = torch.cat(l1_targets, 0)

        num_fg = max(num_fg, 1)
        loss_iou = (
            self.iou_loss(bbox_preds.view(-1, 4)[fg_masks], reg_targets)
        ).sum() / num_fg
        self.last_raw_loc_loss = loss_iou

        # Dedicated Objectness Loss: Focal Objectness Loss with balanced pos/neg normalization
        if self.obj_focal_loss is not None:
            # Detached native tile boxes let an explicit reviewed non-target
            # object supervise an otherwise UNKNOWN emitter anchor. This is
            # TRAIN-only label scope; model inference/parameters are unchanged.
            self.obj_focal_loss.decoded_boxes = bbox_preds.detach().reshape(-1, 4)
            raw_obj_loss = self.obj_focal_loss(obj_preds.view(-1, 1), obj_targets)
            is_pos = (obj_targets > 0)
            is_neg = (obj_targets == 0)
            if self.obj_focal_loss.known is not None:
                is_neg = is_neg & self.obj_focal_loss.known

            raw_pos = (raw_obj_loss * is_pos.to(raw_obj_loss.dtype)).sum()
            raw_neg = (raw_obj_loss * is_neg.to(raw_obj_loss.dtype)).sum()

            norm_pos = raw_pos / num_fg
            num_known_neg = max(float(is_neg.sum().item()), 1.0)
            w_neg = 20.0
            norm_neg = (raw_neg / num_known_neg) * w_neg
            loss_obj = norm_pos + norm_neg

            self.last_norm_pos = norm_pos
            self.last_norm_neg = norm_neg
            self.last_obj_preds = obj_preds
            self.last_cls_preds = cls_preds
            self.last_is_pos = is_pos
            self.last_is_neg = is_neg

            if hasattr(self.obj_focal_loss, 'last_metrics') and hasattr(self.obj_focal_loss, 'record_normalized'):
                self.obj_focal_loss.record_normalized(
                    num_fg=num_fg,
                    norm_pos=norm_pos.item() if isinstance(norm_pos, torch.Tensor) else float(norm_pos),
                    norm_neg=norm_neg.item() if isinstance(norm_neg, torch.Tensor) else float(norm_neg),
                )
        else:
            loss_obj = (
                self.bcewithlog_loss(obj_preds.view(-1, 1), obj_targets)
            ).sum() / num_fg

        # Dedicated Classification Loss: strictly standard BCE
        loss_cls = (
            self.cls_bce_loss(
                cls_preds.view(-1, self.num_classes)[fg_masks], cls_targets
            )
        ).sum() / num_fg

        if self.use_l1:
            loss_l1 = (
                self.l1_loss(origin_preds.view(-1, 4)[fg_masks], l1_targets)
            ).sum() / num_fg
        else:
            loss_l1 = 0.0

        reg_weight = 5.0
        weighted_loc_loss = reg_weight * loss_iou
        self.last_weighted_loc_loss = weighted_loc_loss
        loss = weighted_loc_loss + loss_obj + loss_cls + loss_l1

        return (
            loss,
            weighted_loc_loss,
            loss_obj,
            loss_cls,
            loss_l1,
            num_fg / max(num_gts, 1),
        )


def build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5, loss_type="iou") -> YOLOX:
    """Build complete YOLOX-S detector equipped with P2 small-object head."""
    in_channels = [128, 256, 512, 1024]
    strides = [4, 8, 16, 32]
    backbone = YOLOPAFPN_P2(depth=depth, width=width, in_channels=in_channels)
    head = YOLOXHead_P2(
        num_classes=num_classes,
        width=width,
        strides=strides,
        in_channels=in_channels,
        loss_type=loss_type,
    )
    net = YOLOX(backbone, head)
    install_bounds(net)
    return net
