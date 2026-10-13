#!/usr/bin/env python3
"""Sigmoid Focal Objectness Loss with Soft Boundary Weighting and Strict Unknown Masking.

Contract & Rules (Item 3):
1. Numerically stable Sigmoid Focal Loss:
   alpha = 0.25, gamma = 2.0.
   FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)
2. Strict Anchor Masking:
   - All assigned positive anchors (truth > 0) are unconditionally preserved.
   - UNKNOWN anchors (truth == 0 and known == False) are zeroed out (receive zero loss/gradient).
   - Only known negative anchors (truth == 0 and known == True) receive background loss.
3. Boundary Weighting:
   - Distance-based soft boundary weights applied strictly to known negative anchors.
   - Positives and unknowns are never softened into negatives.
4. Metric Decomposition:
   - Separately logs pos_obj_loss, neg_obj_loss, and anchor statistics.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class SigmoidFocalObjectnessLoss(nn.Module):
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0):
        super().__init__()
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.known = None              # Tensor [N, 1] bool: True for known negative anchors
        self.boundary_weights = None    # Tensor [N, 1] float: 0.2..1.0 for known negatives
        self.last_metrics = {}

    def forward(self, logits: torch.Tensor, truth: torch.Tensor) -> torch.Tensor:
        """Args:
            logits: Predicted objectness logits, shape [N, 1]
            truth: Ground truth objectness targets, shape [N, 1], values in {0, 1}
        """
        # Numerically stable focal formulation
        p = torch.sigmoid(logits)
        pt = p * truth + (1.0 - p) * (1.0 - truth)
        alpha_factor = self.alpha * truth + (1.0 - self.alpha) * (1.0 - truth)
        modulating_factor = (1.0 - pt).clamp(min=0.0, max=1.0) ** self.gamma
        bce = F.binary_cross_entropy_with_logits(logits, truth, reduction="none")
        focal_loss = alpha_factor * modulating_factor * bce

        # 1. Mask unknown background anchors
        is_pos = (truth > 0)
        if self.known is not None and self.known.shape == logits.shape:
            is_known_neg = self.known & (~is_pos)
            valid_mask = is_pos | is_known_neg
        else:
            is_known_neg = (~is_pos)
            valid_mask = torch.ones_like(truth, dtype=torch.bool)

        # 2. Apply boundary weights only to known negatives
        weights = torch.ones_like(focal_loss)
        if self.boundary_weights is not None and self.boundary_weights.shape == logits.shape:
            weights = torch.where(is_pos, torch.ones_like(weights), self.boundary_weights)

        # 3. Final active loss
        active_loss = focal_loss * valid_mask.to(focal_loss.dtype) * weights

        # 4. Metric logging for transparent inspection
        with torch.no_grad():
            num_pos = is_pos.sum().item()
            num_known_neg = is_known_neg.sum().item()
            pos_loss_val = (active_loss * is_pos.to(active_loss.dtype)).sum().item()
            neg_loss_val = (active_loss * is_known_neg.to(active_loss.dtype)).sum().item()
            self.last_metrics = {
                'alpha': self.alpha,
                'gamma': self.gamma,
                'numPosAnchors': num_pos,
                'numKnownNegAnchors': num_known_neg,
                'numUnknownMaskedAnchors': (~valid_mask).sum().item(),
                'posObjLoss': pos_loss_val,
                'negObjLoss': neg_loss_val,
                'meanPosLoss': (pos_loss_val / max(num_pos, 1)),
                'meanNegLoss': (neg_loss_val / max(num_known_neg, 1))
            }

        return active_loss


if __name__ == '__main__':
    print("=== Testing Sigmoid Focal Objectness Loss ===")
    fl = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
    
    # Batch with 10 anchors: 2 pos, 4 known neg, 4 unknown
    logits = torch.tensor([
        [2.0], [1.5],          # 2 positives (confident)
        [-2.0], [0.5],         # 2 known negatives (one hard neg at 0.5)
        [-3.0], [-1.0],        # 2 known negatives (easy)
        [1.0], [0.0],          # 2 unknown skin
        [-1.0], [-2.0]         # 2 unknown skin
    ], requires_grad=True)
    
    truth = torch.tensor([
        [1.0], [1.0],
        [0.0], [0.0],
        [0.0], [0.0],
        [0.0], [0.0],
        [0.0], [0.0]
    ])
    
    fl.known = torch.tensor([
        [False], [False],      # Positives
        [True], [True],        # Known negs
        [True], [True],        # Known negs
        [False], [False],      # Unknowns
        [False], [False]       # Unknowns
    ])
    
    fl.boundary_weights = torch.tensor([
        [1.0], [1.0],
        [1.0], [0.5],          # Boundary weight on hard neg
        [1.0], [0.8],
        [0.0], [0.0],
        [0.0], [0.0]
    ])
    
    loss = fl(logits, truth)
    total_loss = loss.sum()
    total_loss.backward()
    
    print("Loss values per anchor:\n", loss.detach().numpy().flatten())
    print("Gradients:\n", logits.grad.numpy().flatten())
    print("Metrics:", fl.last_metrics)
    
    # Verify unknown anchors have 0 loss and 0 gradient
    assert (loss[6:].detach().numpy() == 0).all()
    assert (logits.grad[6:].numpy() == 0).all()
    print("Unknown masking and gradient isolation verified successfully.")
