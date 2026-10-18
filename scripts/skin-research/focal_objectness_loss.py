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
        if self.known is not None:
            if self.known.shape != logits.shape:
                raise ValueError(
                    f"Shape mismatch in SigmoidFocalObjectnessLoss: known mask {tuple(self.known.shape)} "
                    f"does not match logits {tuple(logits.shape)}. Silent fallback is forbidden."
                )
            is_known_neg = self.known & (~is_pos)
            valid_mask = is_pos | is_known_neg
        else:
            raise ValueError(
                "SigmoidFocalObjectnessLoss requires self.known to be set to prevent unverified skin/lesions "
                "from being trained as negative background. Silent fallback is forbidden."
            )

        # 2. Apply boundary weights only to known negatives
        weights = torch.ones_like(focal_loss)
        if self.boundary_weights is not None:
            if self.boundary_weights.shape != logits.shape:
                raise ValueError(
                    f"Shape mismatch in SigmoidFocalObjectnessLoss: boundary_weights {tuple(self.boundary_weights.shape)} "
                    f"does not match logits {tuple(logits.shape)}. Silent fallback is forbidden."
                )
            weights = torch.where(is_pos, torch.ones_like(weights), self.boundary_weights)

        # 3. Final active loss
        active_loss = focal_loss * valid_mask.to(focal_loss.dtype) * weights

        # 4. Metric logging for transparent inspection
        with torch.no_grad():
            num_pos = int(is_pos.sum().item())
            num_known_neg = int(is_known_neg.sum().item())
            num_unknown = int((~valid_mask).sum().item())
            raw_pos_val = float((active_loss * is_pos.to(active_loss.dtype)).sum().item())
            raw_neg_val = float((active_loss * is_known_neg.to(active_loss.dtype)).sum().item())
            self.last_metrics = {
                'alpha': self.alpha,
                'gamma': self.gamma,
                'raw_pos_obj_loss': raw_pos_val,
                'raw_neg_obj_loss': raw_neg_val,
                'norm_pos_obj_loss': raw_pos_val,
                'norm_neg_obj_loss': raw_neg_val,
                'pos_obj_loss': raw_pos_val,
                'neg_obj_loss': raw_neg_val,
                'posObjLoss': raw_pos_val,
                'negObjLoss': raw_neg_val,
                'num_fg': float(num_pos),
                'num_pos_anchors': num_pos,
                'num_known_neg_anchors': num_known_neg,
                'num_unknown_anchors': num_unknown,
                'numPosAnchors': num_pos,
                'numKnownNegAnchors': num_known_neg,
                'numUnknownMaskedAnchors': num_unknown,
                'meanPosLoss': (raw_pos_val / max(num_pos, 1)),
                'meanNegLoss': (raw_neg_val / max(num_known_neg, 1))
            }

        return active_loss

    def record_normalized(self, num_fg: float, norm_pos: float, norm_neg: float):
        """Update metrics with normalized losses when num_fg is applied by the head."""
        if hasattr(self, 'last_metrics') and isinstance(self.last_metrics, dict):
            self.last_metrics['num_fg'] = float(num_fg)
            self.last_metrics['norm_pos_obj_loss'] = float(norm_pos)
            self.last_metrics['norm_neg_obj_loss'] = float(norm_neg)
            self.last_metrics['pos_obj_loss'] = float(norm_pos)
            self.last_metrics['neg_obj_loss'] = float(norm_neg)

    @property
    def last_stats(self) -> dict:
        """Alias property matching training script expectations."""
        return self.last_metrics
