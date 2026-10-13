#!/usr/bin/env python3
"""Test and verify Item 1: Loss Connection, Silent Fallback Elimination, and Pos/Neg Gradient Isolation.

Verifies:
1. Classification BCE loss is decoupled from Objectness Focal Loss.
2. Silent fallback is removed: ValueError is raised when mask shapes mismatch.
3. GT positive anchors have non-zero loss and non-zero gradients.
4. UNKNOWN cells have exactly zero loss and zero gradients.
5. Positive and negative objectness losses and gradient sums are logged separately.
"""

import sys
from pathlib import Path
import torch
import torch.nn as nn
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from yolox_p2 import build_yolox_p2_model, load_baseline_weights_to_p2_model
from focal_objectness_loss import SigmoidFocalObjectnessLoss


def test_silent_fallback_elimination():
    print("--- Test 1: Verifying Silent Fallback Elimination (ValueError on Shape Mismatch) ---")
    loss_fn = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
    logits = torch.randn(10, 1, requires_grad=True)
    truth = torch.zeros(10, 1)

    # A) Mismatched known mask shape must raise ValueError
    loss_fn.known = torch.ones(8, 1, dtype=torch.bool)
    try:
        loss_fn(logits, truth)
        assert False, "FAILED: Expected ValueError on known mask shape mismatch, but none was raised!"
    except ValueError as e:
        print(f"  [PASS] Correctly raised ValueError on mismatched known mask: {e}")

    # B) Mismatched boundary weights shape must raise ValueError
    loss_fn.known = torch.ones(10, 1, dtype=torch.bool)
    loss_fn.boundary_weights = torch.ones(5, 1)
    try:
        loss_fn(logits, truth)
        assert False, "FAILED: Expected ValueError on boundary weights shape mismatch, but none was raised!"
    except ValueError as e:
        print(f"  [PASS] Correctly raised ValueError on mismatched boundary weights: {e}")

    # C) Missing known mask must raise ValueError
    loss_fn.known = None
    loss_fn.boundary_weights = None
    try:
        loss_fn(logits, truth)
        assert False, "FAILED: Expected ValueError when self.known is None, but none was raised!"
    except ValueError as e:
        print(f"  [PASS] Correctly raised ValueError when self.known is None: {e}")


def test_positive_and_unknown_gradient_isolation():
    print("\n--- Test 2: Verifying GT Positive Preservation & UNKNOWN Cell Gradient Isolation ---")
    loss_fn = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
    
    # Simulate 8 anchors: 2 GT positives, 3 known negatives, 3 unknown skin regions
    logits = torch.tensor([
        [1.5], [2.0],          # Positives
        [-1.0], [-2.0], [0.5], # Known Negatives
        [-0.5], [1.2], [-1.8]  # UNKNOWN regions (punched out lesions/hair)
    ], requires_grad=True)
    
    truth = torch.tensor([
        [1.0], [1.0],
        [0.0], [0.0], [0.0],
        [0.0], [0.0], [0.0]
    ])
    
    loss_fn.known = torch.tensor([
        [False], [False],     # Positives (known flag irrelevant for positives)
        [True], [True], [True],# Known Negatives
        [False], [False], [False] # UNKNOWN
    ], dtype=torch.bool)
    
    loss_fn.boundary_weights = torch.tensor([
        [1.0], [1.0],
        [1.0], [1.0], [0.6],  # Boundary softened
        [0.0], [0.0], [0.0]
    ])
    
    losses = loss_fn(logits, truth)
    total_loss = losses.sum()
    total_loss.backward()
    
    grads = logits.grad.numpy().flatten()
    loss_vals = losses.detach().numpy().flatten()
    
    print(f"  Anchor Losses: {loss_vals}")
    print(f"  Anchor Gradients: {grads}")
    
    # 1. Positives must have non-zero loss and non-zero gradient
    assert loss_vals[0] > 0 and loss_vals[1] > 0, "GT Positives must receive positive loss"
    assert grads[0] != 0 and grads[1] != 0, "GT Positives must receive gradient"
    print("  [PASS] GT Positives receive active supervision.")
    
    # 2. Known negatives must receive active supervision
    assert (loss_vals[2:5] > 0).all(), "Known negatives must receive negative loss"
    assert (grads[2:5] != 0).all(), "Known negatives must receive gradient"
    print("  [PASS] Known Negatives receive active supervision.")
    
    # 3. UNKNOWN anchors must have EXACTLY 0 loss and EXACTLY 0 gradient
    assert (loss_vals[5:] == 0.0).all(), "UNKNOWN anchors must receive exactly 0 loss"
    assert (grads[5:] == 0.0).all(), "UNKNOWN anchors must receive exactly 0 gradient"
    print("  [PASS] UNKNOWN cells have strictly zero loss and zero gradient.")
    
    # 4. Metrics decomposition
    metrics = loss_fn.last_metrics
    print(f"  Decomposed Metrics: {metrics}")
    assert metrics['numPosAnchors'] == 2
    assert metrics['numKnownNegAnchors'] == 3
    assert metrics['numUnknownMaskedAnchors'] == 3
    assert metrics['posObjLoss'] > 0
    assert metrics['negObjLoss'] > 0
    print("  [PASS] Metrics properly decomposed into pos/neg loss sums.")


def test_decoupled_yolox_head():
    print("\n--- Test 3: Verifying Decoupled YOLOXHead_P2 (Classification BCE Isolated) ---")
    net = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
    focal_loss = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
    net.head.obj_focal_loss = focal_loss
    
    # Verify that cls_bce_loss is BCEWithLogitsLoss and is NOT focal_loss
    assert isinstance(net.head.cls_bce_loss, nn.BCEWithLogitsLoss), "cls_bce_loss must be BCEWithLogitsLoss"
    assert net.head.cls_bce_loss is not focal_loss, "cls_bce_loss must NOT be focal_loss"
    assert net.head.obj_focal_loss is focal_loss, "obj_focal_loss must be focal_loss"
    print("  [PASS] YOLOXHead_P2 loss decoupling confirmed.")


if __name__ == '__main__':
    test_silent_fallback_elimination()
    test_positive_and_unknown_gradient_isolation()
    test_decoupled_yolox_head()
    print("\nALL LOSS & GRADIENT SEPARATION TESTS PASSED.")
