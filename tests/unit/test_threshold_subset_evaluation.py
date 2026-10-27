import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "skin-research" / "evaluate_threshold_subsets.py"
SPEC = importlib.util.spec_from_file_location("threshold_subset", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def prediction(label, confidence, x=10, y=10, width=4, height=4):
    return {"class": label, "confidence": confidence, "x": x, "y": y, "width": width, "height": height}


def test_reuses_one_response_for_monotonic_threshold_subsets():
    result = MODULE.summarise(
        [prediction("akne", 0.55), prediction("akne", 0.16), prediction("kizariklik", 0.09)],
        [0.50, 0.08, 0.15],
    )
    assert result["thresholds"] == {
        "0.08": {"total": 3, "byClass": {"akne": 2, "kizariklik": 1}},
        "0.15": {"total": 2, "byClass": {"akne": 2}},
        "0.50": {"total": 1, "byClass": {"akne": 1}},
    }


def test_reports_near_identical_cross_class_boxes_without_deleting_them():
    result = MODULE.summarise(
        [prediction("akne", 0.20), prediction("kizariklik", 0.10)], [0.08]
    )
    assert len(result["nearIdenticalCrossClassBoxes"]) == 1
    assert result["nearIdenticalCrossClassBoxes"][0]["classes"] == ["akne", "kizariklik"]


def test_rejects_invalid_thresholds():
    try:
        MODULE.summarise([], [-0.01])
    except ValueError as error:
        assert "within" in str(error)
    else:
        raise AssertionError("invalid threshold accepted")
