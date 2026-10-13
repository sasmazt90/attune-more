import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from acne_metrics import compute_iou, match_predictions_to_truth, compute_scope_recall


def test_compute_iou():
    box_a = [10.0, 10.0, 20.0, 20.0]
    box_b = [10.0, 10.0, 20.0, 20.0]
    assert compute_iou(box_a, box_b) == 1.0

    box_c = [15.0, 10.0, 25.0, 20.0]
    # Inter: 5 * 10 = 50, Area_a=100, Area_c=100, Union=150 -> IoU = 50 / 150 = 1/3
    assert abs(compute_iou(box_a, box_c) - 1.0 / 3.0) < 1e-5

    box_d = [30.0, 30.0, 40.0, 40.0]
    assert compute_iou(box_a, box_d) == 0.0


def test_match_predictions_to_truth_1to1():
    truth = [
        [10.0, 10.0, 20.0, 20.0],
        [50.0, 50.0, 60.0, 60.0]
    ]
    # Two predictions matching the first truth box
    preds = [
        [10.0, 10.0, 20.0, 20.0, 0.95],
        [11.0, 11.0, 21.0, 21.0, 0.85]
    ]
    matched_t, matches, dups, unmatched_p, unmatched_t = match_predictions_to_truth(truth, preds, 0.50)
    assert matched_t == [0]
    assert len(matches) == 1
    assert matches[0] == (0, 0, 1.0)
    assert len(dups) == 1
    assert dups[0][0] == 0 and dups[0][1] == 1  # Pred 1 was duplicate for Truth 0
    assert unmatched_t == [1]


def test_compute_scope_recall_strict_rules():
    assert compute_scope_recall(10, 50) == 0.2000
    assert compute_scope_recall(0, 50) == 0.0000
    assert compute_scope_recall(50, 50) == 1.0000
    assert compute_scope_recall(0, 0) is None

    # Error on negative or > 1.0
    with pytest.raises(ValueError, match="outside \\[0.0, 1.0\\]"):
        compute_scope_recall(-1, 50)

    with pytest.raises(ValueError, match="outside \\[0.0, 1.0\\]"):
        compute_scope_recall(60, 50)
