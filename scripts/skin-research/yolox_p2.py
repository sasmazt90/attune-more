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


def load_baseline_weights_to_p2_model(
    p2_net: YOLOX,
    baseline_weights_path: Path
) -> Dict[str, any]:
    """Transfer weights from 3-scale Baseline to 4-scale P2 Model with exact index alignment.
    
    Mapping Rules:
    - Backbone:
      * All CSPDarknet weights (stem, dark2, dark3, dark4, dark5) transfer directly.
      * PAFPN layers (lateral_conv0, C3_p4, reduce_conv1, C3_p3, bu_conv2, C3_n3, bu_conv1, C3_n4) transfer directly.
      * New P2 PAFPN layers (reduce_conv2, C3_p2, bu_conv3, C3_n2, p2_gate) are initialized explicitly.
    - Head:
      * Baseline index 0 (P3, stride 8)  -> P2-Model index 1 (P3, stride 8).
      * Baseline index 1 (P4, stride 16) -> P2-Model index 2 (P4, stride 16).
      * Baseline index 2 (P5, stride 32) -> P2-Model index 3 (P5, stride 32).
      * P2-Model index 0 (P2, stride 4) is NEW and initialized explicitly.
    """
    baseline_weights_path = Path(baseline_weights_path)
    assert baseline_weights_path.exists(), f"Baseline weights not found: {baseline_weights_path}"
    baseline_state = load_file(str(baseline_weights_path))
    p2_state = p2_net.state_dict()

    transferred = {}
    new_initialized = []
    
    # 1. Backbone direct transfers
    for k, v in baseline_state.items():
        if k.startswith('backbone.'):
            if k in p2_state and p2_state[k].shape == v.shape:
                transferred[k] = v

    # 2. Head index-shifted transfers:
    # Baseline stems.0 -> P2 stems.1, etc.
    head_submodules = ['stems', 'cls_convs', 'reg_convs', 'cls_preds', 'reg_preds', 'obj_preds']
    
    for old_idx in range(3):
        new_idx = old_idx + 1  # Shift by 1 because P2 takes index 0
        for sub in head_submodules:
            prefix_old = f"head.{sub}.{old_idx}"
            prefix_new = f"head.{sub}.{new_idx}"
            for k, v in baseline_state.items():
                if k.startswith(prefix_old):
                    suffix = k[len(prefix_old):]
                    k_new = prefix_new + suffix
                    if k_new in p2_state and p2_state[k_new].shape == v.shape:
                        transferred[k_new] = v

    # 3. Explicit initialization for new layers
    # Apply to p2_net before loading transferred weights
    p2_net.head.initialize_biases(prior_prob=0.01)
    
    # Custom init for new P2 PAFPN layers and stem
    for module_name, m in p2_net.named_modules():
        if module_name in [
            'backbone.reduce_conv2', 'backbone.C3_p2',
            'backbone.bu_conv3', 'backbone.C3_n2',
            'head.stems.0', 'head.cls_convs.0', 'head.reg_convs.0'
        ]:
            for p_name, param in m.named_parameters():
                full_param_name = f"{module_name}.{p_name}"
                if 'weight' in p_name and param.dim() >= 2:
                    nn.init.kaiming_normal_(param, mode="fan_out", nonlinearity="relu")
                elif 'bias' in p_name:
                    nn.init.zeros_(param)
                new_initialized.append(full_param_name)

    # 4. Explicit zero/prior initialization for new P2 prediction heads and residual gate
    with torch.no_grad():
        p2_net.backbone.p2_gate.zero_()
        prior_bias = -math.log((1.0 - 0.01) / 0.01)
        nn.init.zeros_(p2_net.head.obj_preds[0].weight)
        p2_net.head.obj_preds[0].bias.fill_(prior_bias)
        nn.init.zeros_(p2_net.head.cls_preds[0].weight)
        p2_net.head.cls_preds[0].bias.fill_(prior_bias)
        nn.init.zeros_(p2_net.head.reg_preds[0].weight)
        p2_net.head.reg_preds[0].bias.zero_()
        # Set prior box size to 8px: exp(log(2)) * 4 = 8px
        p2_net.head.reg_preds[0].bias[2:4].fill_(math.log(2.0))

    # 5. Load transferred parameters into state dict
    msg = p2_net.load_state_dict(transferred, strict=False)

    # Strict contract validation: only predefined new P2 layers can be missing
    new_prefixes = (
        'backbone.reduce_conv2', 'backbone.C3_p2', 'backbone.bu_conv3',
        'backbone.C3_n2', 'backbone.p2_gate', 'head.stems.0',
        'head.cls_convs.0', 'head.reg_convs.0', 'head.cls_preds.0',
        'head.reg_preds.0', 'head.obj_preds.0'
    )
    for k in msg.missing_keys:
        assert k.startswith(new_prefixes), f"Unexpected missing key outside P2 branch: {k}"
    assert len(msg.missing_keys) == 92, f"Expected exactly 92 new P2 parameters, got {len(msg.missing_keys)}"
    assert len(msg.unexpected_keys) == 0, f"Unexpected keys in transfer: {msg.unexpected_keys}"
    
    report = {
        'baselineWeightsPath': str(baseline_weights_path),
        'transferredParamCount': len(transferred),
        'missingInBaseline': msg.missing_keys,
        'unexpectedInBaseline': msg.unexpected_keys,
        'newInitializedCount': len(new_initialized),
        'totalModelParams': len(p2_state)
    }
    return report


def build_p2_param_groups(
    net: nn.Module,
    lr_p2: float = 1e-4,
    lr_backbone: float = 1e-5,
    weight_decay: float = 0.0005
) -> Tuple[List[Dict[str, any]], Dict[str, any]]:
    """Build unified parameter groups for YOLOX-S P2 small-foci training.
    
    Groups:
    1. Frozen: stem and dark2 in CSPDarknet (requires_grad = False).
    2. P2 Head and FPN/PANet Branch (lr = lr_p2):
       - backbone.reduce_conv2
       - backbone.C3_p2
       - backbone.bu_conv3
       - backbone.C3_n2
       - backbone.p2_gate
       - head.stems.0
       - head.cls_convs.0
       - head.reg_convs.0
       - head.cls_preds.0
       - head.reg_preds.0
       - head.obj_preds.0
       Must contain exactly 58 tensors and 742,791 parameters.
    3. Pretrained Backbone & Heads (lr = lr_backbone):
       - Remaining PAFPN and head levels (1, 2, 3 -> P3, P4, P5) and dark3, dark4, dark5.
       Must contain exactly 219 tensors and 8,896,786 parameters.
    """
    frozen_count = 0
    frozen_params = []
    for k, p in net.named_parameters():
        if k.startswith(('backbone.backbone.stem.', 'backbone.backbone.dark2.')):
            p.requires_grad = False
            frozen_count += 1
            frozen_params.append((k, p))
        else:
            p.requires_grad = True

    p2_prefixes = (
        'backbone.reduce_conv2.', 'backbone.C3_p2.', 'backbone.bu_conv3.',
        'backbone.C3_n2.', 'backbone.p2_gate', 'head.stems.0.',
        'head.cls_convs.0.', 'head.reg_convs.0.', 'head.cls_preds.0.',
        'head.reg_preds.0.', 'head.obj_preds.0.'
    )

    p2_params = []
    p2_names = []
    backbone_params = []
    backbone_names = []

    for k, p in net.named_parameters():
        if not p.requires_grad:
            continue
        if k == 'backbone.p2_gate' or any(k.startswith(pfx) for pfx in p2_prefixes):
            p2_params.append(p)
            p2_names.append(k)
        else:
            backbone_params.append(p)
            backbone_names.append(k)

    # Assertions
    assert len(p2_params) > 0, "P2 parameter group is empty!"
    assert len(backbone_params) > 0, "Backbone parameter group is empty!"
    
    # Check no overlap
    p2_set = set(id(p) for p in p2_params)
    bb_set = set(id(p) for p in backbone_params)
    overlap = p2_set & bb_set
    assert len(overlap) == 0, f"Overlapping parameters between P2 and Backbone groups: {len(overlap)}"

    # Check complete partition of trainable parameters
    trainable_all = [p for p in net.parameters() if p.requires_grad]
    assert len(p2_params) + len(backbone_params) == len(trainable_all), (
        f"Partition mismatch: {len(p2_params)} + {len(backbone_params)} != {len(trainable_all)}"
    )

    # Check exact counts
    assert len(p2_params) == 58, f"Expected 58 P2 parameter tensors, got {len(p2_params)}"
    assert sum(p.numel() for p in p2_params) == 742791, (
        f"Expected 742,791 P2 parameters, got {sum(p.numel() for p in p2_params)}"
    )
    assert len(backbone_params) == 219, f"Expected 219 backbone tensors, got {len(backbone_params)}"
    assert sum(p.numel() for p in backbone_params) == 8896786, (
        f"Expected 8,896,786 backbone parameters, got {sum(p.numel() for p in backbone_params)}"
    )

    param_groups = [
        {'params': p2_params, 'lr': lr_p2, 'weight_decay': weight_decay, 'name': 'p2_branch_and_head'},
        {'params': backbone_params, 'lr': lr_backbone, 'weight_decay': weight_decay, 'name': 'backbone_and_other_heads'}
    ]

    receipt = {
        'p2Group': {
            'tensorCount': len(p2_params),
            'parameterCount': sum(p.numel() for p in p2_params),
            'lr': lr_p2,
            'prefixes': list(p2_prefixes),
            'sampleNames': p2_names[:5] + p2_names[-5:]
        },
        'backboneGroup': {
            'tensorCount': len(backbone_params),
            'parameterCount': sum(p.numel() for p in backbone_params),
            'lr': lr_backbone,
            'sampleNames': backbone_names[:5] + backbone_names[-5:]
        },
        'frozenGroup': {
            'tensorCount': frozen_count,
            'parameterCount': sum(p.numel() for _, p in frozen_params)
        },
        'totalTrainableParams': sum(p.numel() for p in trainable_all),
        'totalModelParams': sum(p.numel() for p in net.parameters())
    }

    return param_groups, receipt


def build_independent_p2_param_groups(
    net: nn.Module,
    lr_p2: float = 2e-4,
    weight_decay: float = 0.0001
) -> Tuple[List[Dict[str, any]], Dict[str, any]]:
    """Build parameter groups where ONLY Level 0 (P2 stride 4) is trainable.
    
    Strict Zero-Drift Preservation:
    - 100% of CSPDarknet backbone is FROZEN (requires_grad = False).
    - 100% of upper PAFPN levels (P3, P4, P5) are FROZEN (requires_grad = False).
    - p2_gate is strictly 0.0 and FROZEN, completely decoupling P3 features.
    - 100% of pre-trained heads (P3, P4, P5 at indices 1, 2, 3) are FROZEN.
    - Only Level 0 branch and head receive gradients.
    """
    trainable_prefixes = (
        'backbone.reduce_conv2.',
        'backbone.C3_p2.',
        'head.stems.0.',
        'head.cls_convs.0.',
        'head.reg_convs.0.',
        'head.cls_preds.0.',
        'head.reg_preds.0.',
        'head.obj_preds.0.'
    )

    trainable_params = []
    trainable_names = []
    frozen_params = []
    frozen_names = []

    # Strictly ensure p2_gate is 0.0
    with torch.no_grad():
        net.backbone.p2_gate.zero_()

    for k, p in net.named_parameters():
        if any(k.startswith(pfx) for pfx in trainable_prefixes):
            p.requires_grad = True
            trainable_params.append(p)
            trainable_names.append(k)
        else:
            p.requires_grad = False
            frozen_params.append(p)
            frozen_names.append(k)

    param_groups = [
        {'params': trainable_params, 'lr': lr_p2, 'weight_decay': weight_decay, 'name': 'level0_p2_independent'}
    ]

    receipt = {
        'trainableLevel0': {
            'tensorCount': len(trainable_params),
            'parameterCount': sum(p.numel() for p in trainable_params),
            'lr': lr_p2,
            'weight_decay': weight_decay,
            'sampleNames': trainable_names[:5] + trainable_names[-5:]
        },
        'frozenBaseline': {
            'tensorCount': len(frozen_params),
            'parameterCount': sum(p.numel() for p in frozen_params),
            'sampleNames': frozen_names[:5] + frozen_names[-5:]
        },
        'p2GateValue': net.backbone.p2_gate.item(),
        'totalModelParams': sum(p.numel() for p in net.parameters())
    }

    return param_groups, receipt


def build_finetune_param_groups(
    net: YOLOX,
    lr_p2: float = 1.5e-4,
    lr_heads: float = 3.0e-5,
    lr_pafpn: float = 1.5e-5,
    lr_backbone: float = 5.0e-6,
    weight_decay: float = 1e-4,
    unfreeze_backbone: bool = True
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Build multi-tier differential learning rate parameter groups for full skin fine-tuning.
    
    Tiers:
    1. Level 0 (P2 branch + head + p2_gate): lr_p2 (~1.5e-4)
    2. Upper detection heads (P3, P4, P5 stems, convs, preds): lr_heads (~3.0e-5)
    3. Upper PAFPN fusion (lateral_conv0, reduce_conv1, C3_p3/p4/n3/n4, bu_conv1/2): lr_pafpn (~1.5e-5)
    4. Backbone feature adaptation (dark2, dark3, dark4, dark5): lr_backbone (~5.0e-6)
    """
    p2_prefixes = (
        'backbone.reduce_conv2.', 'backbone.C3_p2.', 'backbone.bu_conv3.', 'backbone.C3_n2.', 'backbone.p2_gate',
        'head.stems.0.', 'head.cls_convs.0.', 'head.reg_convs.0.', 'head.cls_preds.0.', 'head.reg_preds.0.', 'head.obj_preds.0.'
    )
    head_prefixes = ('head.stems.', 'head.cls_convs.', 'head.reg_convs.', 'head.cls_preds.', 'head.reg_preds.', 'head.obj_preds.')
    pafpn_prefixes = (
        'backbone.lateral_conv0.', 'backbone.C3_p4.', 'backbone.reduce_conv1.', 'backbone.C3_p3.',
        'backbone.bu_conv2.', 'backbone.C3_n3.', 'backbone.bu_conv1.', 'backbone.C3_n4.'
    )
    backbone_prefixes = ('backbone.backbone.dark3.', 'backbone.backbone.dark4.', 'backbone.backbone.dark5.', 'backbone.backbone.dark2.')

    g_p2, g_heads, g_pafpn, g_backbone, g_stem = [], [], [], [], []
    n_p2, n_heads, n_pafpn, n_backbone, n_stem = [], [], [], [], []

    for name, p in net.named_parameters():
        if any(name.startswith(pfx) for pfx in p2_prefixes):
            p.requires_grad = True
            g_p2.append(p)
            n_p2.append(name)
        elif any(name.startswith(pfx) for pfx in head_prefixes):
            p.requires_grad = True
            g_heads.append(p)
            n_heads.append(name)
        elif any(name.startswith(pfx) for pfx in pafpn_prefixes):
            p.requires_grad = True
            g_pafpn.append(p)
            n_pafpn.append(name)
        elif any(name.startswith(pfx) for pfx in backbone_prefixes):
            p.requires_grad = unfreeze_backbone
            if unfreeze_backbone:
                g_backbone.append(p)
                n_backbone.append(name)
            else:
                g_stem.append(p)
                n_stem.append(name)
        else:
            # Stem kept frozen to preserve low-level primitive filters
            p.requires_grad = False
            g_stem.append(p)
            n_stem.append(name)

    param_groups = [
        {'params': g_p2, 'lr': lr_p2, 'weight_decay': weight_decay, 'name': 'level0_p2_task'},
        {'params': g_heads, 'lr': lr_heads, 'weight_decay': weight_decay, 'name': 'pretrained_heads'},
        {'params': g_pafpn, 'lr': lr_pafpn, 'weight_decay': weight_decay, 'name': 'pafpn_fusion'},
    ]
    if unfreeze_backbone and g_backbone:
        param_groups.append(
            {'params': g_backbone, 'lr': lr_backbone, 'weight_decay': weight_decay, 'name': 'backbone_adaptation'}
        )

    receipt = {
        'level0_p2_task': {
            'tensorCount': len(g_p2),
            'paramCount': sum(p.numel() for p in g_p2),
            'lr': lr_p2
        },
        'pretrained_heads': {
            'tensorCount': len(g_heads),
            'paramCount': sum(p.numel() for p in g_heads),
            'lr': lr_heads
        },
        'pafpn_fusion': {
            'tensorCount': len(g_pafpn),
            'paramCount': sum(p.numel() for p in g_pafpn),
            'lr': lr_pafpn
        },
        'backbone_adaptation': {
            'tensorCount': len(g_backbone),
            'paramCount': sum(p.numel() for p in g_backbone),
            'lr': lr_backbone if unfreeze_backbone else 0.0,
            'unfrozen': unfreeze_backbone
        },
        'frozen_stem': {
            'tensorCount': len(g_stem),
            'paramCount': sum(p.numel() for p in g_stem)
        },
        'totalTrainableTensors': sum(len(g['params']) for g in param_groups),
        'totalTrainableParams': sum(sum(p.numel() for p in g['params']) for g in param_groups),
        'totalModelParams': sum(p.numel() for p in net.parameters())
    }

    return param_groups, receipt


if __name__ == '__main__':
    print("=== Testing YOLOX-S with P2 Branch Architecture ===")
    model = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    
    # Test forward pass with dummy BGR tile
    dummy_input = torch.randn(2, 3, 384, 384)
    model.eval()
    with torch.no_grad():
        detections = model(dummy_input)
    print(f"Inference output shape: {detections.shape} (Expected: [2, 12240, 6])")
    assert detections.shape == (2, 12240, 6), f"Shape mismatch: {detections.shape}"
    
    # Test weight loading
    baseline_path = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
    if baseline_path.exists():
        rep = load_baseline_weights_to_p2_model(model, baseline_path)
        print(f"Transferred: {rep['transferredParamCount']} parameters from Baseline.")
        print(f"Missing in Baseline (New P2 layers): {len(rep['missingInBaseline'])} parameters.")
        # Verify Level 1 has transferred weights while Level 0 is initialized
        print("Weight transfer successfully verified.")
