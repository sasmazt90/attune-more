#!/usr/bin/env python3
"""Evaluate locked-method predictions on independent physical-camera truth.

This evaluator computes capture-level per-class and slice metrics.  It does
not tune thresholds, does not convert unknown/unassessable truth to negative,
and does not claim localization or product activation acceptance.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


PREDICTIONS = {"positive", "negative", "unavailable"}
OPAQUE_RE = re.compile(r"^[a-z][a-z0-9_-]*_[0-9a-f]{16,64}$")
FORBIDDEN_KEYS = {
    "name", "filename", "filepath", "path", "uri", "url", "email", "phone",
    "address", "rawimage", "imagebytes", "bytes", "confidence", "score",
    "probability", "thresholdcandidate", "suggestedthreshold",
}
SLICE_FIELDS = ("deviceClass", "lightingBin", "skinToneBin", "pose")


class CameraEvaluationError(ValueError):
    """Raised when method locking, completeness, or privacy fails."""


def _opaque(value: Any, field: str) -> str:
    if not isinstance(value, str) or OPAQUE_RE.fullmatch(value) is None:
        raise CameraEvaluationError(f"{field} must be an opaque reference")
    return value


def _assert_no_forbidden_keys(value: Any, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).lower())
            if normalized in FORBIDDEN_KEYS:
                raise CameraEvaluationError(f"forbidden private/tuning field at {location}.{key}")
            _assert_no_forbidden_keys(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, f"{location}[{index}]")


def _metrics(counts: dict[str, int]) -> dict[str, Any]:
    tp, fp, fn, tn = (counts[key] for key in ("tp", "fp", "fn", "tn"))
    truth_positives = tp + fn
    precision = tp / (tp + fp) if tp + fp else (0.0 if truth_positives else None)
    recall = tp / truth_positives if truth_positives else None
    if precision is not None and recall is not None:
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    else:
        f1 = None
    eligible = counts["eligibleTruth"]
    scorable = counts["scorablePredictions"]
    return {
        **counts,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "availability": scorable / eligible if eligible else None,
    }


def _new_counts() -> dict[str, int]:
    return {
        "tp": 0, "fp": 0, "fn": 0, "tn": 0,
        "eligibleTruth": 0, "scorablePredictions": 0,
        "unavailablePredictions": 0, "unknownTruthExcluded": 0,
        "unassessableTruthExcluded": 0,
    }


def _update(counts: dict[str, int], truth: str, prediction: str) -> None:
    if truth == "unknown":
        counts["unknownTruthExcluded"] += 1
        return
    if truth == "unassessable":
        counts["unassessableTruthExcluded"] += 1
        return
    counts["eligibleTruth"] += 1
    if prediction == "unavailable":
        counts["unavailablePredictions"] += 1
        if truth == "positive":
            counts["fn"] += 1
        return
    counts["scorablePredictions"] += 1
    if truth == "positive" and prediction == "positive":
        counts["tp"] += 1
    elif truth == "positive" and prediction == "negative":
        counts["fn"] += 1
    elif truth == "evaluated_negative" and prediction == "positive":
        counts["fp"] += 1
    elif truth == "evaluated_negative" and prediction == "negative":
        counts["tn"] += 1
    else:
        raise CameraEvaluationError("unexpected truth/prediction state")


def evaluate(camera_manifest: dict[str, Any], expert_truth: dict[str, Any], prediction_receipt: dict[str, Any]) -> dict[str, Any]:
    _assert_no_forbidden_keys(camera_manifest, "cameraManifest")
    _assert_no_forbidden_keys(expert_truth, "expertTruth")
    _assert_no_forbidden_keys(prediction_receipt, "predictionReceipt")

    if camera_manifest.get("methodVersion") != "physical-camera-benchmark-manifest-v1":
        raise CameraEvaluationError("camera manifest method identity changed")
    if camera_manifest.get("sourceType") != "physical-camera" or camera_manifest.get("generated") is not False:
        raise CameraEvaluationError("camera evaluation requires physical captures")
    if camera_manifest.get("split") != "camera_final":
        raise CameraEvaluationError("camera evaluation requires camera_final")
    if expert_truth.get("methodVersion") != "physical-camera-expert-truth-v1":
        raise CameraEvaluationError("expert truth method identity changed")
    if expert_truth.get("modelProposalUsedAsTruth") is not False:
        raise CameraEvaluationError("model proposal cannot become expert truth")
    if expert_truth.get("missingTruthInterpretedAsNegative") is not False:
        raise CameraEvaluationError("missing truth cannot become negative")

    method_ref = _opaque(prediction_receipt.get("methodRef"), "methodRef")
    threshold_lock_ref = _opaque(prediction_receipt.get("thresholdLockRef"), "thresholdLockRef")
    if prediction_receipt.get("thresholdsLockedBeforeCameraFinal") is not True:
        raise CameraEvaluationError("thresholds must be locked before camera_final")
    if prediction_receipt.get("cameraFinalUsedForThresholdSelection") is not False:
        raise CameraEvaluationError("camera_final cannot select thresholds")
    if prediction_receipt.get("methodMutatedAfterLock") is not False:
        raise CameraEvaluationError("method cannot change after lock")
    method_version = prediction_receipt.get("methodVersion")
    if not isinstance(method_version, str) or not method_version.strip():
        raise CameraEvaluationError("methodVersion must be non-empty")

    captures = camera_manifest.get("captures")
    if not isinstance(captures, list) or not captures:
        raise CameraEvaluationError("camera manifest has no captures")
    capture_by_ref = {item.get("captureRef"): item for item in captures}
    if len(capture_by_ref) != len(captures) or None in capture_by_ref:
        raise CameraEvaluationError("camera capture references are invalid")

    activated = expert_truth.get("activatedClasses")
    truth_rows = expert_truth.get("truth")
    if not isinstance(activated, list) or not activated or not isinstance(truth_rows, list):
        raise CameraEvaluationError("expert truth inventory is invalid")
    truth_by_key = {(row.get("captureRef"), row.get("classId")): row for row in truth_rows}
    expected = {(capture_ref, class_id) for capture_ref in capture_by_ref for class_id in activated}
    if len(truth_by_key) != len(truth_rows) or set(truth_by_key) != expected:
        raise CameraEvaluationError("expert truth matrix is incomplete or duplicated")

    records = prediction_receipt.get("records")
    if not isinstance(records, list):
        raise CameraEvaluationError("prediction records must be an array")
    predictions: dict[tuple[str, str], str] = {}
    for row in records:
        if not isinstance(row, dict):
            raise CameraEvaluationError("prediction record must be an object")
        key = (row.get("captureRef"), row.get("classId"))
        if key not in expected:
            raise CameraEvaluationError("prediction is outside the camera/class matrix")
        if key in predictions:
            raise CameraEvaluationError("duplicate prediction record")
        decision = row.get("decision")
        if decision not in PREDICTIONS:
            raise CameraEvaluationError("invalid prediction decision")
        predictions[key] = decision
    if set(predictions) != expected:
        raise CameraEvaluationError("every camera/class cell requires an explicit prediction")

    class_counts = {class_id: _new_counts() for class_id in activated}
    slice_counts: dict[str, dict[str, dict[str, dict[str, int]]]] = {
        field: defaultdict(lambda: {class_id: _new_counts() for class_id in activated})
        for field in SLICE_FIELDS
    }
    failures: list[dict[str, str]] = []
    for capture_ref, class_id in sorted(expected):
        truth = truth_by_key[(capture_ref, class_id)]["decision"]
        prediction = predictions[(capture_ref, class_id)]
        _update(class_counts[class_id], truth, prediction)
        capture = capture_by_ref[capture_ref]
        for field in SLICE_FIELDS:
            value = capture.get(field)
            if not isinstance(value, str) or not value:
                raise CameraEvaluationError(f"camera manifest missing {field}")
            _update(slice_counts[field][value][class_id], truth, prediction)
        if truth == "positive" and prediction != "positive":
            failures.append({"captureRef": capture_ref, "classId": class_id, "failure": "false_negative" if prediction == "negative" else "unavailable_on_positive"})
        elif truth == "evaluated_negative" and prediction == "positive":
            failures.append({"captureRef": capture_ref, "classId": class_id, "failure": "false_positive"})
        elif truth == "evaluated_negative" and prediction == "unavailable":
            failures.append({"captureRef": capture_ref, "classId": class_id, "failure": "unavailable_on_evaluated_negative"})

    per_class = {class_id: _metrics(class_counts[class_id]) for class_id in sorted(activated)}
    per_slice = {
        field: {
            value: {class_id: _metrics(counts[class_id]) for class_id in sorted(activated)}
            for value, counts in sorted(values.items())
        }
        for field, values in slice_counts.items()
    }
    return {
        "schemaVersion": 1,
        "methodVersion": "physical-camera-capture-level-evaluation-v1",
        "evaluatedMethodRef": method_ref,
        "evaluatedMethodVersion": method_version,
        "thresholdLockRef": threshold_lock_ref,
        "thresholdsLockedBeforeCameraFinal": True,
        "cameraFinalUsedForThresholdSelection": False,
        "classMetrics": per_class,
        "sliceMetrics": per_slice,
        "failures": failures,
        "unknownAndUnassessableExcludedNotNegative": True,
        "unavailableNeverCountsAsTrueNegative": True,
        "rednessIndependentFromSensitivity": True,
        "mapContract": {"dry": "blue", "oily": "green", "redness": "red-independent", "normal": "uncoloured-evaluated-only", "unknown": "light-grey-never-normal"},
        "captureLevelMetricsComputed": True,
        "localizationMetricsComputed": False,
        "productReplayComputed": False,
        "acceptanceThresholdsApplied": False,
        "activationAllowed": False,
        "note": "Capture-level metrics and slice failures are valid diagnostics. Localized classes still require mask/box matching, locked acceptance thresholds and product replay before activation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-manifest", type=Path, required=True)
    parser.add_argument("--expert-truth", type=Path, required=True)
    parser.add_argument("--prediction-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        json.loads(args.camera_manifest.read_text(encoding="utf-8")),
        json.loads(args.expert_truth.read_text(encoding="utf-8")),
        json.loads(args.prediction_receipt.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
