"""Shared deterministic evaluation metrics for acne detection across training and evaluation pipelines."""

import math
from typing import List, Tuple, Dict, Any, Optional, Set


def compute_iou(box_a, box_b) -> float:
    """Computes Intersection-over-Union between two boxes [x0, y0, x1, y1]."""
    x0 = max(box_a[0], box_b[0])
    y0 = max(box_a[1], box_b[1])
    x1 = min(box_a[2], box_b[2])
    y1 = min(box_a[3], box_b[3])
    inter = max(0.0, float(x1 - x0)) * max(0.0, float(y1 - y0))
    area_a = max(0.0, float(box_a[2] - box_a[0])) * max(0.0, float(box_a[3] - box_a[1]))
    area_b = max(0.0, float(box_b[2] - box_b[0])) * max(0.0, float(box_b[3] - box_b[1]))
    denom = area_a + area_b - inter
    return inter / denom if denom > 0.0 else 0.0


def match_predictions_to_truth(
    truth_boxes: List[List[float]],
    pred_boxes: List[Any],
    iou_thresh: float = 0.50
) -> Tuple[List[int], List[Tuple[int, int, float]], List[Tuple[int, int, float]], List[int], List[int]]:
    """Greedy 1-to-1 bipartite matching between truth boxes and predictions.
    
    Predictions can be either lists/tuples [x0, y0, x1, y1, conf] or dicts {'x', 'y', 'width', 'height', 'confidence'}.
    Returns:
      matched_truth_indices: list of matched truth indices (at most one per prediction)
      matches: list of (truth_idx, pred_idx, iou)
      duplicate_matches: list of (truth_idx, pred_idx, iou) where pred matched an already-matched truth box
      unmatched_pred_indices: list of pred indices that did not match any truth box
      unmatched_truth_indices: list of truth indices that were not matched by any prediction
    """
    if not truth_boxes or not pred_boxes:
        return [], [], [], list(range(len(pred_boxes))), list(range(len(truth_boxes)))

    normalized_preds = []
    for p in pred_boxes:
        if isinstance(p, dict):
            bx0 = float(p['x'])
            by0 = float(p['y'])
            bx1 = bx0 + float(p['width'])
            by1 = by0 + float(p['height'])
            conf = float(p.get('confidence', 1.0))
        else:
            bx0, by0, bx1, by1 = float(p[0]), float(p[1]), float(p[2]), float(p[3])
            conf = float(p[4]) if len(p) > 4 else 1.0
        normalized_preds.append([bx0, by0, bx1, by1, conf])

    # Rank predictions by confidence descending
    indexed_preds = sorted(enumerate(normalized_preds), key=lambda x: x[1][4], reverse=True)

    matched_truth = {}
    matched_preds = {}
    matches = []
    duplicate_matches = []

    for pred_idx, pbox in indexed_preds:
        best_iou = 0.0
        best_truth_idx = -1
        for truth_idx, tbox in enumerate(truth_boxes):
            iou = compute_iou(tbox, pbox[:4])
            if iou > best_iou:
                best_iou = iou
                best_truth_idx = truth_idx

        if best_iou >= iou_thresh and best_truth_idx >= 0:
            if best_truth_idx not in matched_truth:
                matched_truth[best_truth_idx] = (pred_idx, best_iou)
                matched_preds[pred_idx] = (best_truth_idx, best_iou)
                matches.append((best_truth_idx, pred_idx, best_iou))
            else:
                duplicate_matches.append((best_truth_idx, pred_idx, best_iou))

    matched_truth_indices = sorted(matched_truth.keys())
    unmatched_pred_indices = [i for i in range(len(pred_boxes)) if i not in matched_preds]
    unmatched_truth_indices = [i for i in range(len(truth_boxes)) if i not in matched_truth]

    return matched_truth_indices, matches, duplicate_matches, unmatched_pred_indices, unmatched_truth_indices


def compute_scope_recall(tp: int, truth: int) -> Optional[float]:
    """Calculates recall strictly within the same scope.
    
    Rules:
    - Same scope for numerator and denominator.
    - If truth <= 0, returns None (null).
    - If recall is not in [0.0, 1.0], raises ValueError (no clamping allowed).
    """
    if truth <= 0:
        return None
    recall = tp / truth
    if recall < 0.0 or recall > 1.0:
        raise ValueError(f"Recall calculation error: tp={tp}, truth={truth}, recall={recall} is outside [0.0, 1.0]")
    return round(float(recall), 4)
